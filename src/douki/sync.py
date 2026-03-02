"""Sync Douki YAML docstrings with function/class signatures.

This module provides the core logic for comparing Python source code
signatures against their Douki YAML docstrings and producing an
updated source string.  It is intentionally pure — no file I/O.
"""

from __future__ import annotations

import ast
import re
import textwrap

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from douki._validation import validate_schema

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ParamInfo:
    """A single parameter extracted from an ``ast`` signature."""

    name: str
    annotation: str  # '' when absent
    # 'regular' | 'keyword_only' | 'positional_only'
    # | 'var_positional' | 'var_keyword'
    kind: str


@dataclass
class FuncInfo:
    """Everything we need to know about a single def / async def."""

    name: str
    lineno: int  # 1-based line of the *def* keyword
    params: List[ParamInfo] = field(default_factory=list)
    return_annotation: str = ''
    docstring_node: Optional[ast.Constant] = None
    is_method: bool = False


# ---------------------------------------------------------------------------
# AST → type-string helpers
# ---------------------------------------------------------------------------


def _annotation_to_str(node: Optional[ast.expr]) -> str:
    """Convert an AST annotation node to a readable type string."""
    if node is None:
        return ''

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value  # forward-reference string
        if node.value is None:
            return 'None'
        return repr(node.value)

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return f'{_annotation_to_str(node.value)}.{node.attr}'

    if isinstance(node, ast.Subscript):
        base = _annotation_to_str(node.value)
        slc = node.slice
        if isinstance(slc, ast.Tuple):
            inner = ', '.join(_annotation_to_str(e) for e in slc.elts)
        else:
            inner = _annotation_to_str(slc)
        return f'{base}[{inner}]'

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _annotation_to_str(node.left)
        right = _annotation_to_str(node.right)
        return f'{left} | {right}'

    if isinstance(node, ast.Tuple):
        return ', '.join(_annotation_to_str(e) for e in node.elts)

    if isinstance(node, ast.List):
        return '[' + ', '.join(_annotation_to_str(e) for e in node.elts) + ']'

    # Fallback: use ast.unparse (Python 3.9+)
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover
        return ''


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

_SELF_CLS = frozenset({'self', 'cls'})


def _param_kind(
    arg_name: str, func_node: ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    """Determine the parameter kind."""
    for arg in func_node.args.posonlyargs:
        if arg.arg == arg_name:
            return 'positional_only'
    for arg in func_node.args.kwonlyargs:
        if arg.arg == arg_name:
            return 'keyword_only'
    if func_node.args.vararg and func_node.args.vararg.arg == arg_name:
        return 'var_positional'
    if func_node.args.kwarg and func_node.args.kwarg.arg == arg_name:
        return 'var_keyword'
    return 'regular'


def _extract_func(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool = False,
) -> FuncInfo:
    """Build a *FuncInfo* from an AST function node."""
    params: List[ParamInfo] = []
    all_args: list[ast.arg] = (
        node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    )
    if node.args.vararg:
        all_args.append(node.args.vararg)
    if node.args.kwarg:
        all_args.append(node.args.kwarg)

    for arg in all_args:
        if arg.arg in _SELF_CLS and is_method:
            continue
        params.append(
            ParamInfo(
                name=arg.arg,
                annotation=_annotation_to_str(arg.annotation),
                kind=_param_kind(arg.arg, node),
            )
        )

    ret = _annotation_to_str(node.returns)

    # Docstring is the first statement if it's a Constant string.
    ds_node = None
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        ds_node = node.body[0].value

    return FuncInfo(
        name=node.name,
        lineno=node.lineno,
        params=params,
        return_annotation=ret,
        docstring_node=ds_node,
        is_method=is_method,
    )


def extract_functions(source: str) -> List[FuncInfo]:
    """Parse *source* and return info about every function / method."""
    tree = ast.parse(source)
    results: List[FuncInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Determine if it is a method by checking parent
            is_method = False
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    if node in ast.iter_child_nodes(parent):
                        is_method = True
                        break
            results.append(_extract_func(node, is_method=is_method))
        elif isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    results.append(_extract_func(child, is_method=True))

    # Deduplicate (methods found by both walk and ClassDef iteration)
    seen: set[int] = set()
    unique: List[FuncInfo] = []
    for fi in results:
        key = (
            id(fi.docstring_node)
            if fi.docstring_node
            else (fi.name, fi.lineno)
        )
        if key not in seen:
            seen.add(key)  # type: ignore[arg-type]
            unique.append(fi)
    return unique


# ---------------------------------------------------------------------------
# YAML docstring sync
# ---------------------------------------------------------------------------


def _is_douki_yaml(raw: str) -> bool:
    """Check if *raw* is valid Douki YAML with a ``title``."""
    if not raw or ':' not in raw:
        return False
    try:
        data = yaml.safe_load(textwrap.dedent(raw))
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict) or 'title' not in data:
        return False
    try:
        validate_schema(data)
    except ValueError:
        return False
    return True


def _param_name_for_yaml(p: ParamInfo) -> str:
    """Produce the YAML key for a parameter."""
    if p.kind == 'var_positional':
        return f'*{p.name}'
    if p.kind == 'var_keyword':
        return f'**{p.name}'
    return p.name


def _extract_param_desc(entry: Any) -> str:
    """Read the description from an old flat or new nested param."""
    if isinstance(entry, dict):
        return str(entry.get('description', ''))
    if isinstance(entry, str):
        return entry
    return ''


def _extract_returns_desc(entry: Any) -> str:
    """Read description from old flat or new list returns."""
    if isinstance(entry, list) and entry:
        first = entry[0]
        if isinstance(first, dict):
            return str(first.get('description', ''))
        return str(first)
    if isinstance(entry, str):
        return entry
    return ''


def sync_docstring(
    raw_docstring: str,
    params: Sequence[ParamInfo],
    return_annotation: str,
    *,
    is_method: bool = False,
) -> str:
    """Merge signature info into a Douki YAML docstring.

    Returns the updated YAML (without surrounding triple-quotes).
    If not valid Douki YAML, returns it unchanged.
    """
    if not _is_douki_yaml(raw_docstring):
        return raw_docstring

    data: Dict[str, Any] = yaml.safe_load(
        textwrap.dedent(raw_docstring),
    )

    # --- parameters ---
    if params:
        existing: Dict[str, Any] = data.get('parameters', {}) or {}
        new_params: Dict[str, Any] = {}
        for p in params:
            yaml_key = _param_name_for_yaml(p)
            old = existing.get(yaml_key, None)
            desc = _extract_param_desc(old)

            entry: Dict[str, Any] = {}
            if p.annotation:
                entry['type'] = p.annotation
            if desc:
                entry['description'] = desc

            # Carry forward optional/default if nested
            if isinstance(old, dict):
                if 'optional' in old and old['optional'] is not None:
                    entry['optional'] = old['optional']
                if 'default' in old and old['default'] is not None:
                    entry['default'] = old['default']

            new_params[yaml_key] = entry
        data['parameters'] = new_params
    else:
        data.pop('parameters', None)

    # --- returns ---
    if return_annotation and return_annotation != 'None':
        existing_ret = data.get('returns')
        desc = _extract_returns_desc(existing_ret)
        ret_entry: Dict[str, Any] = {'type': return_annotation}
        if desc:
            ret_entry['description'] = desc
        data['returns'] = [ret_entry]
    elif return_annotation == 'None':
        data.pop('returns', None)

    # Rebuild YAML in canonical key order
    return _rebuild_yaml(data)


# Canonical key ordering
_KEY_ORDER = [
    'title',
    'summary',
    'deprecated',
    'visibility',
    'mutability',
    'scope',
    'parameters',
    'returns',
    'yields',
    'receives',
    'raises',
    'warnings',
    'see_also',
    'notes',
    'references',
    'examples',
    'attributes',
    'methods',
]

# Python defaults: fields with these values are omitted
_PYTHON_DEFAULTS: Dict[str, Any] = {
    'visibility': 'public',
    'mutability': 'mutable',
    'scope': 'static',
}

# Sub-keys omitted when they match these defaults
_PARAM_DEFAULTS: Dict[str, Any] = {
    'optional': None,
    'default': None,
}


def _rebuild_yaml(data: Dict[str, Any]) -> str:
    """Serialize *data* to YAML with canonical key order.

    Omits fields that match Python defaults.
    """
    ordered: List[Tuple[str, Any]] = []
    for key in _KEY_ORDER:
        if key in data:
            ordered.append((key, data[key]))
    for key in data:
        if key not in _KEY_ORDER:
            ordered.append((key, data[key]))

    lines: List[str] = []
    for key, value in ordered:
        # Skip None / empty values
        if value is None or value == '' or value == {}:
            continue
        # Skip Python defaults
        if key in _PYTHON_DEFAULTS:
            if value == _PYTHON_DEFAULTS[key]:
                continue

        if key == 'parameters':
            _emit_parameters(lines, value)
        elif key in ('returns', 'yields', 'receives'):
            _emit_typed_list(lines, key, value)
        elif key in ('raises', 'warnings'):
            _emit_raises(lines, key, value)
        elif key == 'examples' and isinstance(value, list):
            _emit_examples(lines, value)
        elif isinstance(value, dict):
            lines.append(f'{key}:')
            for k, v in value.items():
                lines.append(
                    f'  {k}: {_yaml_scalar(v)}',
                )
        elif isinstance(value, str) and '\n' in value:
            lines.append(f'{key}: |')
            for ln in value.splitlines():
                lines.append(f'  {ln}')
        else:
            lines.append(f'{key}: {_yaml_scalar(value)}')
    return '\n'.join(lines) + '\n'


def _emit_parameters(
    lines: List[str],
    params: Dict[str, Any],
) -> None:
    """Emit ``parameters:`` section."""
    lines.append('parameters:')
    for name, entry in params.items():
        if isinstance(entry, str):
            # Old flat format — still support it
            lines.append(f'  {name}: {_yaml_scalar(entry)}')
        elif isinstance(entry, dict):
            lines.append(f'  {name}:')
            for sub_key in ('type', 'optional', 'description', 'default'):
                if sub_key not in entry:
                    continue
                val = entry[sub_key]
                if sub_key in _PARAM_DEFAULTS:
                    if val == _PARAM_DEFAULTS[sub_key]:
                        continue
                lines.append(
                    f'    {sub_key}: {_yaml_scalar(val)}',
                )


def _emit_typed_list(
    lines: List[str],
    key: str,
    value: Any,
) -> None:
    """Emit returns/yields/receives as list."""
    if isinstance(value, str):
        lines.append(f'{key}: {_yaml_scalar(value)}')
        return
    if isinstance(value, list):
        lines.append(f'{key}:')
        for item in value:
            if isinstance(item, dict):
                first = True
                for sk in ('type', 'description'):
                    if sk in item:
                        prefix = '- ' if first else '  '
                        lines.append(
                            f'  {prefix}{sk}: {_yaml_scalar(item[sk])}',
                        )
                        first = False
            else:
                lines.append(f'  - {_yaml_scalar(item)}')


def _emit_raises(
    lines: List[str],
    key: str,
    value: Any,
) -> None:
    """Emit raises/warnings (dict or list format)."""
    if isinstance(value, dict):
        lines.append(f'{key}:')
        for k, v in value.items():
            lines.append(f'  {k}: {_yaml_scalar(v)}')
    elif isinstance(value, list):
        lines.append(f'{key}:')
        for item in value:
            if isinstance(item, dict):
                first = True
                for sk in ('type', 'description'):
                    if sk in item:
                        prefix = '- ' if first else '  '
                        lines.append(
                            f'  {prefix}{sk}: {_yaml_scalar(item[sk])}',
                        )
                        first = False
            else:
                lines.append(f'  - {_yaml_scalar(item)}')


def _emit_examples(
    lines: List[str],
    value: List[Any],
) -> None:
    """Emit examples as list."""
    lines.append('examples:')
    for item in value:
        if isinstance(item, dict) and 'code' in item:
            lines.append('  - code: |')
            for ln in str(item['code']).splitlines():
                lines.append(f'      {ln}')
            if 'description' in item:
                lines.append(
                    f'    description: {_yaml_scalar(item["description"])}',
                )
        elif isinstance(item, str):
            lines.append(f'  - {_yaml_scalar(item)}')


def _yaml_scalar(value: Any) -> str:
    """Format a simple scalar for inline YAML."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        if any(c in value for c in ':{}[]&*!|>\\\'"#%@`'):
            dumped = yaml.dump(
                value,
                default_flow_style=True,
            )
            dumped = dumped.removesuffix('\n')
            dumped = dumped.removesuffix('...')
            return dumped.strip()
        return value
    if value is None:
        return 'null'
    return str(value)


# ---------------------------------------------------------------------------
# Full source sync
# ---------------------------------------------------------------------------


def sync_source(
    source: str,
    *,
    migrate: Optional[str] = None,
) -> str:
    """Synchronize all Douki YAML docstrings in *source*.

    Parameters
    ----------
    source : str
        Python source code.
    migrate : str, optional
        If ``'numpy'``, convert NumPy docstrings to Douki
        YAML before syncing.

    Returns the (possibly modified) source string.
    """
    # Optional migration pass first
    if migrate == 'numpy':
        source = _migrate_numpy(source)

    try:
        funcs = extract_functions(source)
    except SyntaxError:
        return source  # unparseable → leave alone

    if not funcs:
        return source

    lines = source.splitlines(keepends=True)
    # Process in reverse line order so edits don't shift indices.
    funcs_with_ds = [f for f in funcs if f.docstring_node is not None]
    funcs_with_ds.sort(
        key=lambda f: f.docstring_node.lineno,  # type: ignore[union-attr]
        reverse=True,
    )

    for func in funcs_with_ds:
        ds_node = func.docstring_node
        assert ds_node is not None

        raw = str(ds_node.value)
        if not _is_douki_yaml(raw):
            continue

        synced = sync_docstring(
            raw,
            func.params,
            func.return_annotation,
            is_method=func.is_method,
        )
        if synced == raw:
            continue

        # We need the start/end lines of the docstring.
        ds_start = ds_node.lineno - 1  # 0-based
        ds_end = ds_node.end_lineno
        if ds_end is None:
            continue  # safety

        # Extract the original docstring region
        original_region = ''.join(lines[ds_start:ds_end])

        # Detect quote style and indentation
        stripped_first = lines[ds_start].lstrip()
        indent = lines[ds_start][: len(lines[ds_start]) - len(stripped_first)]

        # Find the quote style
        quote_match = re.search(
            r'(\"\"\"|\'\'\')',
            original_region,
        )
        if not quote_match:
            continue  # pragma: no cover
        quote = quote_match.group(1)

        # Detect content indent from existing lines
        content_indent = indent
        ds_lines = raw.split('\n')
        for dl in ds_lines[1:]:
            if dl.strip():
                leading = len(dl) - len(dl.lstrip())
                content_indent = ' ' * leading
                break

        # Rebuild the docstring with proper indentation
        synced_lines = synced.splitlines()
        formatted_lines = []
        for sl in synced_lines:
            if sl.strip():
                formatted_lines.append(content_indent + sl)
            else:
                formatted_lines.append('')
        new_content = '\n'.join(formatted_lines)

        new_docstring = f'{indent}{quote}\n{new_content}\n{indent}{quote}\n'

        lines[ds_start:ds_end] = [new_docstring]

    return ''.join(lines)


def _migrate_numpy(source: str) -> str:
    """Replace NumPy-style docstrings with Douki YAML."""
    from douki.migrate import numpy_to_douki_yaml

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    lines = source.splitlines(keepends=True)

    # Collect all docstring nodes
    ds_nodes: List[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Module,
            ),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                ds_nodes.append(node.body[0].value)

    # Process in reverse order
    ds_nodes.sort(
        key=lambda n: n.lineno,
        reverse=True,
    )

    for ds_node in ds_nodes:
        raw = str(ds_node.value)
        # Skip if already Douki YAML
        if _is_douki_yaml(raw):
            continue

        converted = numpy_to_douki_yaml(raw)
        if converted == raw:
            continue  # not a numpy docstring

        ds_start = ds_node.lineno - 1
        ds_end = ds_node.end_lineno
        if ds_end is None:
            continue

        original_region = ''.join(lines[ds_start:ds_end])
        stripped_first = lines[ds_start].lstrip()
        indent = lines[ds_start][: len(lines[ds_start]) - len(stripped_first)]

        quote_match = re.search(
            r'(\"\"\"|\'\'\')',
            original_region,
        )
        if not quote_match:
            continue  # pragma: no cover
        quote = quote_match.group(1)

        # Use body indent (4 spaces deeper than def)
        body_indent = indent
        raw_lines = raw.split('\n')
        for rl in raw_lines[1:]:
            if rl.strip():
                leading = len(rl) - len(rl.lstrip())
                body_indent = ' ' * leading
                break

        conv_lines = converted.splitlines()
        formatted = []
        for cl in conv_lines:
            if cl.strip():
                formatted.append(body_indent + cl)
            else:
                formatted.append('')
        new_content = '\n'.join(formatted)

        new_ds = f'{indent}{quote}\n{new_content}\n{indent}{quote}\n'
        lines[ds_start:ds_end] = [new_ds]

    return ''.join(lines)
