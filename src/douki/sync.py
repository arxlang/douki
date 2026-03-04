"""
title: Sync Douki YAML docstrings with function/class signatures.
summary: |-
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


class DocstringValidationError(ValueError):
    """
    title: Raised when one or more docstrings in a file fail validation.
    """

    pass


@dataclass
class ParamInfo:
    """
    title: A single parameter extracted from an ``ast`` signature.
    attributes:
      name:
        type: str
      annotation:
        type: str
      kind:
        type: str
    """

    name: str
    annotation: str  # '' when absent
    # 'regular' | 'keyword_only' | 'positional_only'
    # | 'var_positional' | 'var_keyword'
    kind: str


@dataclass
class FuncInfo:
    """
    title: >-
      Everything we need to know about a single def / async def / class /
      module.
    attributes:
      name:
        type: str
      lineno:
        type: int
      params:
        type: List[ParamInfo]
      attrs:
        type: List[ParamInfo]
      return_annotation:
        type: str
      docstring_node:
        type: Optional[ast.Constant]
      is_method:
        type: bool
    """

    name: str
    lineno: int  # 1-based line of the *def* keyword, or 1 for module
    params: List[ParamInfo] = field(default_factory=list)
    # Class-level annotated vars, extracted from the class body by
    # _FuncExtractor
    attrs: List[ParamInfo] = field(default_factory=list)
    return_annotation: str = ''
    docstring_node: Optional[ast.Constant] = None
    is_method: bool = False


# ---------------------------------------------------------------------------
# AST → type-string helpers
# ---------------------------------------------------------------------------


def _annotation_to_str(node: Optional[ast.expr]) -> str:
    """
    title: Convert an AST annotation node to a readable type string.
    parameters:
      node:
        type: Optional[ast.expr]
    returns:
      type: str
    """
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
    """
    title: Determine the parameter kind.
    parameters:
      arg_name:
        type: str
      func_node:
        type: ast.FunctionDef | ast.AsyncFunctionDef
    returns:
      type: str
    """
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
    """
    title: Extract a FuncInfo from a FunctionDef/AsyncFunctionDef or ClassDef.
    parameters:
      node:
        type: ast.FunctionDef | ast.AsyncFunctionDef
      is_method:
        type: bool
    returns:
      type: FuncInfo
    """
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


class _FuncExtractor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.results: List[FuncInfo] = []
        self.in_class: bool = False
        # Maps class name → full list of attrs (own + inherited)
        # built up as we visit classes top-to-bottom.
        self._class_attrs_map: Dict[str, List[ParamInfo]] = {}

    def visit_Module(self, node: ast.Module) -> None:
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.results.append(
                FuncInfo(
                    name='<module>',
                    lineno=1,
                    docstring_node=node.body[0].value,
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        ds_node = None
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            ds_node = node.body[0].value

        # Extract class-level annotated variables for attributes: sync
        own_attrs: List[ParamInfo] = []
        for child in node.body:
            if isinstance(child, ast.AnnAssign) and isinstance(
                child.target, ast.Name
            ):
                own_attrs.append(
                    ParamInfo(
                        name=child.target.id,
                        annotation=_annotation_to_str(child.annotation),
                        kind='regular',
                    )
                )

        # Also extract self.* assignments from __init__ that are
        # not already declared at class level.
        own_names = {p.name for p in own_attrs}
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != '__init__':
                continue
            for stmt in ast.walk(child):
                # self.x: T = ... (annotated assignment)
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Attribute)
                    and isinstance(stmt.target.value, ast.Name)
                    and stmt.target.value.id == 'self'
                    and stmt.target.attr not in own_names
                ):
                    own_attrs.append(
                        ParamInfo(
                            name=stmt.target.attr,
                            annotation=_annotation_to_str(stmt.annotation),
                            kind='regular',
                        )
                    )
                    own_names.add(stmt.target.attr)
                # self.x = ... (plain assignment)
                elif isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == 'self'
                            and target.attr not in own_names
                        ):
                            own_attrs.append(
                                ParamInfo(
                                    name=target.attr,
                                    annotation='',
                                    kind='regular',
                                )
                            )
                            own_names.add(target.attr)
            break  # only process the first __init__

        # Resolve base class attrs from same-file classes (order: base first)
        inherited: List[ParamInfo] = []
        seen_names: set[str] = {p.name for p in own_attrs}
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr  # best-effort for dotted names
            if base_name and base_name in self._class_attrs_map:
                for a in self._class_attrs_map[base_name]:
                    if a.name not in seen_names:
                        inherited.append(a)
                        seen_names.add(a.name)

        # Full list: inherited first, then own attrs (own take precedence)
        all_attrs = inherited + own_attrs

        # Store for subclasses that may inherit from this class
        self._class_attrs_map[node.name] = all_attrs

        if ds_node is not None:
            self.results.append(
                FuncInfo(
                    name=node.name,
                    lineno=node.lineno,
                    # Class docstring uses attributes:, not parameters:
                    params=[],
                    attrs=all_attrs,
                    docstring_node=ds_node,
                )
            )

        old_in_class = self.in_class
        self.in_class = True
        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.results.append(_extract_func(node, is_method=self.in_class))
        old_in_class = self.in_class
        self.in_class = False  # nested functions are not methods
        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.results.append(_extract_func(node, is_method=self.in_class))
        old_in_class = self.in_class
        self.in_class = False
        self.generic_visit(node)
        self.in_class = old_in_class


def extract_functions(source: str) -> List[FuncInfo]:
    """
    title: Parse the Python source and return extracted functions/classes.
    parameters:
      source:
        type: str
    returns:
      type: List[FuncInfo]
      description: List of FuncInfo objects in the order they appear.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    extractor = _FuncExtractor()
    extractor.visit(tree)
    return extractor.results


# ---------------------------------------------------------------------------
# YAML docstring sync
# ---------------------------------------------------------------------------


def _load_docstring_yaml(raw: str) -> Dict[str, Any]:
    """
    title: Load YAML safely, converting single-line strings to titles.
    parameters:
      raw:
        type: str
    returns:
      type: Dict[str, Any]
    """
    try:
        data = yaml.safe_load(textwrap.dedent(raw))
    except yaml.YAMLError:
        raise ValueError('Could not parse YAML')

    if isinstance(data, str) and ':' not in data:
        lines = data.strip().split('\n', 1)
        if len(lines) == 1:
            data = {'title': lines[0].strip()}
        else:
            title = lines[0].strip()
            summary = lines[1].strip()
            data = {'title': title, 'summary': summary}

    if not isinstance(data, dict):
        raise ValueError('Invalid Douki YAML')

    return data


def validate_docstring(raw: str, func_name: str) -> bool:
    """
    title: Check whether *raw* is a valid Douki YAML docstring.
    parameters:
      raw:
        type: str
      func_name:
        type: str
    returns:
      type: bool
      description: True if it's a valid Douki YAML docstring.
    """
    if not raw or not raw.strip():
        return False

    try:
        data = yaml.safe_load(textwrap.dedent(raw))
    except yaml.YAMLError:
        raise ValueError('Could not parse YAML')

    if not isinstance(data, dict):
        raise ValueError('Docstring is not a valid Douki YAML dictionary')

    if 'title' not in data:
        raise ValueError("Missing 'title' field")

    try:
        validate_schema(data)
    except ValueError as e:
        raise ValueError(str(e))

    return True


def _param_name_for_yaml(p: ParamInfo) -> str:
    """
    title: Produce the YAML key for a parameter.
    parameters:
      p:
        type: ParamInfo
    returns:
      type: str
    """
    return p.name


def _extract_param_desc(entry: Any) -> str:
    """
    title: Read the description from an old flat or new nested param.
    parameters:
      entry:
        type: Any
    returns:
      type: str
    """
    if isinstance(entry, dict):
        return str(entry.get('description', ''))
    if isinstance(entry, str):
        return entry
    return ''


def _extract_returns_desc(entry: Any) -> str:
    """
    title: Extract the existing description for returns/yields.
    parameters:
      entry:
        type: Any
    returns:
      type: str
    """
    if isinstance(entry, list) and entry:
        first = entry[0]
        if isinstance(first, dict):
            return str(first.get('description', ''))
        return str(first)
    if isinstance(entry, dict):
        return str(entry.get('description', ''))
    if isinstance(entry, str):
        return entry
    return ''


def sync_docstring(
    raw_docstring: str,
    params: Sequence[ParamInfo],
    return_annotation: str,
    *,
    attrs: Sequence[ParamInfo] = (),
    is_method: bool = False,
    func_name: str = '<unknown>',
    content_indent: int = 4,
) -> str:
    """
    title: Merge signature info into a Douki YAML docstring.
    summary: >-
      Returns the updated YAML (without surrounding triple-quotes). If not
      valid Douki YAML, raises ValueError.
    parameters:
      raw_docstring:
        type: str
      params:
        type: Sequence[ParamInfo]
      return_annotation:
        type: str
      attrs:
        type: Sequence[ParamInfo]
        description: >-
          Class-level annotated variables used to sync the attributes: section.
          Only meaningful for ClassDef docstrings.
      is_method:
        type: bool
      func_name:
        type: str
      content_indent:
        type: int
    returns:
      type: str
    """
    if not validate_docstring(raw_docstring, func_name):
        return raw_docstring

    data: Dict[str, Any] = _load_docstring_yaml(raw_docstring)

    # --- parameters ---
    if params:
        existing: Dict[str, Any] = data.get('parameters', {}) or {}
        new_params: Dict[str, Any] = {}
        for p in params:
            yaml_key = _param_name_for_yaml(p)
            # Look up by plain name first, then fall back to
            # legacy '*name' / '**name' keys for backward compat.
            old = existing.get(yaml_key, None)
            if old is None and p.kind == 'var_positional':
                old = existing.get(f'*{p.name}', None)
            if old is None and p.kind == 'var_keyword':
                old = existing.get(f'**{p.name}', None)
            desc = _extract_param_desc(old)

            entry: Dict[str, Any] = {}
            if p.annotation:
                entry['type'] = p.annotation
            if desc:
                entry['description'] = desc

            # Set variadic attribute
            if p.kind == 'var_positional':
                entry['variadic'] = 'positional'
            elif p.kind == 'var_keyword':
                entry['variadic'] = 'keyword'

            # Carry forward optional/default/variadic if nested
            if isinstance(old, dict):
                if 'optional' in old and old['optional'] is not None:
                    entry['optional'] = old['optional']
                if 'default' in old and old['default'] is not None:
                    entry['default'] = old['default']
                # Preserve variadic from old entry if not
                # already set by kind
                if (
                    'variadic' not in entry
                    and 'variadic' in old
                    and old['variadic']
                ):
                    entry['variadic'] = old['variadic']

            new_params[yaml_key] = entry
        data['parameters'] = new_params
    else:
        data.pop('parameters', None)

    # --- attributes (class-level annotated vars) ---
    if attrs:
        existing_attrs: Dict[str, Any] = data.get('attributes', {}) or {}
        new_attrs: Dict[str, Any] = {}
        for a in attrs:
            old_a = existing_attrs.get(a.name)
            desc = _extract_param_desc(old_a)
            attr_entry: Dict[str, Any] = {}
            if a.annotation:
                attr_entry['type'] = a.annotation
            if desc:
                attr_entry['description'] = desc
            # Carry forward description and optional from existing entry
            if isinstance(old_a, dict):
                if 'optional' in old_a and old_a['optional'] is not None:
                    attr_entry['optional'] = old_a['optional']
            new_attrs[a.name] = attr_entry
        data['attributes'] = new_attrs
    # Note: we do NOT pop attributes: when attrs is empty —
    # the developer may have manually written it.

    # --- returns ---
    if return_annotation and return_annotation != 'None':
        existing_ret = data.get('returns')
        desc = _extract_returns_desc(existing_ret)
        ret_entry: Dict[str, Any] = {'type': return_annotation}
        if desc:
            ret_entry['description'] = desc
        data['returns'] = ret_entry
    elif return_annotation == 'None':
        data.pop('returns', None)

    # Rebuild YAML in canonical key order
    return _rebuild_yaml(data, content_indent)


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
    'variadic': None,
}


def _rebuild_yaml(data: Dict[str, Any], content_indent: int = 4) -> str:
    """
    title: Serialize *data* to YAML with canonical key order.
    summary: Omits fields that match Python defaults.
    parameters:
      data:
        type: Dict[str, Any]
      content_indent:
        type: int
    returns:
      type: str
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

        if key in ('parameters', 'attributes'):
            _emit_parameters(lines, key, value, content_indent)
        elif key in (
            'see_also',
            'references',
            'methods',
        ):
            _emit_typed_list(lines, key, value, content_indent)
        elif key in ('raises', 'warnings'):
            _emit_raises(lines, key, value, content_indent)
        elif key in ('returns', 'yields', 'receives'):
            _emit_typed_entry(lines, key, value, content_indent)
        elif key == 'examples' and isinstance(value, list):
            _emit_examples(lines, value, content_indent)
        elif isinstance(value, dict):
            lines.append(f'{key}:')
            for k, v in value.items():
                _emit_key_value(lines, '  ', k, v, content_indent)
        else:
            _emit_key_value(lines, '', key, value, content_indent)
    return '\n'.join(lines) + '\n'


def _emit_key_value(
    lines: List[str],
    indent_str: str,
    key: str,
    value: Any,
    content_indent: int = 4,
) -> None:
    """
    title: >-
      Safely emit a key-value pair, folding long strings into block scalars.
    parameters:
      lines:
        type: List[str]
      indent_str:
        type: str
      key:
        type: str
      value:
        type: Any
      content_indent:
        type: int
    """
    # YAML list items use "- value", dict entries use "key: value"
    is_list_item = key == '-'
    sep = ' ' if is_list_item else ': '

    if isinstance(value, str):
        # Max width for block-scalar content lines (after indent_str + "  ")
        block_width = 79 - content_indent - len(indent_str) - 2
        if block_width < 20:
            block_width = 20

        if '\n' in value:
            stripped = value.rstrip('\n')
            if '\n' not in stripped:
                # Single paragraph with trailing \n from YAML |
                prefix_len = (
                    content_indent + len(indent_str) + len(key) + len(sep)
                )
                if prefix_len + len(stripped) > 79:
                    wrapped = textwrap.fill(stripped, width=block_width)
                    lines.append(f'{indent_str}{key}{sep}>-')
                    for ln in wrapped.splitlines():
                        lines.append(f'{indent_str}  {ln}')
                    return
                # Fits on one line — emit inline
                lines.append(f'{indent_str}{key}{sep}{_yaml_scalar(stripped)}')
                return
            else:
                # True multi-line: use |- but wrap long lines
                lines.append(f'{indent_str}{key}{sep}|-')
                for ln in value.splitlines():
                    if len(ln) > block_width and ' ' in ln.strip():
                        wrapped = textwrap.fill(ln.strip(), width=block_width)
                        for wl in wrapped.splitlines():
                            lines.append(f'{indent_str}  {wl}')
                    else:
                        lines.append(f'{indent_str}  {ln}')
                return

        # Single-line string (no \n at all)
        prefix_len = content_indent + len(indent_str) + len(key) + len(sep)
        if prefix_len + len(value) > 79:
            wrapped = textwrap.fill(value, width=block_width)
            lines.append(f'{indent_str}{key}{sep}>-')
            for ln in wrapped.splitlines():
                lines.append(f'{indent_str}  {ln}')
            return

    lines.append(f'{indent_str}{key}{sep}{_yaml_scalar(value)}')


def _emit_parameters(
    lines: List[str],
    key: str,
    params: Dict[str, Any],
    content_indent: int = 4,
) -> None:
    """
    title: Emit ``parameters:`` or ``attributes:`` section.
    parameters:
      lines:
        type: List[str]
      key:
        type: str
      params:
        type: Dict[str, Any]
      content_indent:
        type: int
    """
    lines.append(f'{key}:')
    for name, entry in params.items():
        safe_name = _yaml_scalar(name)
        if isinstance(entry, str):
            # Old flat format — still support it
            lines.append(f'  {safe_name}: {_yaml_scalar(entry)}')
        elif isinstance(entry, dict):
            lines.append(f'  {safe_name}:')
            for sub_key in (
                'type',
                'optional',
                'description',
                'default',
                'variadic',
            ):
                if sub_key not in entry:
                    continue
                val = entry[sub_key]
                if sub_key in _PARAM_DEFAULTS:
                    if val == _PARAM_DEFAULTS[sub_key]:
                        continue
                _emit_key_value(lines, '    ', sub_key, val, content_indent)


def _emit_typed_list(
    lines: List[str],
    key: str,
    value: Any,
    content_indent: int = 4,
) -> None:
    """
    title: Emit list-based types (methods, attributes).
    parameters:
      lines:
        type: List[str]
      key:
        type: str
      value:
        type: Any
      content_indent:
        type: int
    """
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
                        _emit_key_value(
                            lines,
                            '  ',
                            f'{prefix}{sk}',
                            item[sk],
                            content_indent,
                        )
                        first = False
            else:
                _emit_key_value(lines, '  ', '-', item, content_indent)


def _emit_typed_entry(
    lines: List[str],
    key: str,
    value: Any,
    content_indent: int = 4,
) -> None:
    """
    title: Emit returns/yields/receives as a single dictionary.
    parameters:
      lines:
        type: List[str]
      key:
        type: str
      value:
        type: Any
      content_indent:
        type: int
    """
    if isinstance(value, str):
        lines.append(f'{key}: {_yaml_scalar(value)}')
        return
    if isinstance(value, list) and value:
        value = value[0]  # graceful downgrade from legacy list

    if isinstance(value, dict):
        lines.append(f'{key}:')
        for sk in ('type', 'description'):
            if sk in value:
                _emit_key_value(lines, '  ', sk, value[sk], content_indent)


def _emit_raises(
    lines: List[str],
    key: str,
    value: Any,
    content_indent: int = 4,
) -> None:
    """
    title: Emit raises/warnings (dict or list format).
    parameters:
      lines:
        type: List[str]
      key:
        type: str
      value:
        type: Any
      content_indent:
        type: int
    """
    if isinstance(value, dict):
        lines.append(f'{key}:')
        for k, v in value.items():
            _emit_key_value(lines, '  ', k, v, content_indent)
    elif isinstance(value, list):
        lines.append(f'{key}:')
        for item in value:
            if isinstance(item, dict):
                first = True
                for sk in ('type', 'description'):
                    if sk in item:
                        prefix = '- ' if first else '  '
                        _emit_key_value(
                            lines,
                            '  ',
                            f'{prefix}{sk}',
                            item[sk],
                            content_indent,
                        )
                        first = False
            else:
                _emit_key_value(lines, '  ', '-', item, content_indent)


def _emit_examples(
    lines: List[str],
    value: List[Any],
    content_indent: int = 4,
) -> None:
    """
    title: Emit examples as list.
    parameters:
      lines:
        type: List[str]
      value:
        type: List[Any]
      content_indent:
        type: int
    """
    lines.append('examples:')
    for item in value:
        if isinstance(item, dict) and 'code' in item:
            lines.append('  - code: |')
            for ln in str(item['code']).splitlines():
                lines.append(f'      {ln}')
            if 'description' in item:
                _emit_key_value(
                    lines,
                    '    ',
                    'description',
                    item['description'],
                    content_indent,
                )
        elif isinstance(item, str):
            _emit_key_value(lines, '  ', '-', item, content_indent)


def _yaml_scalar(value: Any) -> str:
    """
    title: Format a simple scalar for inline YAML.
    parameters:
      value:
        type: Any
    returns:
      type: str
    """
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        if any(c in value for c in ':{}[]&*!|>\\\'"#%@`\n'):
            dumped = yaml.dump(
                value,
                # Allow block style for multiline strings
                default_flow_style=False,
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
    """
    title: Synchronize all Douki YAML docstrings in *source*.
    parameters:
      source:
        type: str
        description: Python source code.
      migrate:
        type: Optional[str]
        optional: true
        description: >-
          If ``'numpydoc'``, convert NumPy docstrings to Douki YAML before
          syncing.
    returns:
      type: str
      description: The (possibly modified) source string.
    """
    # Optional migration pass first
    if migrate == 'numpydoc':
        source = _migrate_numpydoc(source)

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

    errors = []

    for func in funcs_with_ds:
        ds_node = func.docstring_node
        assert ds_node is not None

        raw = str(ds_node.value)

        # We enforce validation for every docstring that exists.
        if raw.strip():
            try:
                validate_docstring(raw, func.name)
            except ValueError as e:
                prefix = (
                    '<module>' if func.name == '<module>' else f"'{func.name}'"
                )
                errors.append(f'- {prefix}: {e}')
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

        # Detect content indent from existing lines.
        # Default to same level as the opening """, matching PEP 257 / ruff.
        content_indent = indent
        ds_lines = raw.split('\n')
        for dl in ds_lines[1:]:
            if dl.strip():
                leading = len(dl) - len(dl.lstrip())
                content_indent = ' ' * leading
                break

        try:
            synced = sync_docstring(
                raw,
                func.params,
                func.return_annotation,
                attrs=func.attrs,
                is_method=func.is_method,
                func_name=func.name,
                content_indent=len(content_indent),
            )
        except ValueError as e:
            prefix = (
                '<module>' if func.name == '<module>' else f"'{func.name}'"
            )
            errors.append(f'- {prefix}: {e}')
            continue

        if synced == raw:
            continue

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

    if errors:
        errors.reverse()
        raise DocstringValidationError('\n'.join(errors))

    return ''.join(lines)


def _migrate_numpydoc(source: str) -> str:
    """
    title: Replace numpydoc-style docstrings with Douki YAML
    parameters:
      source:
        type: str
    returns:
      type: str
    """
    from douki.migrate import numpydoc_to_douki_yaml

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

    errors = []

    for ds_node in ds_nodes:
        raw = str(ds_node.value)
        # We enforce validation for every docstring that exists.
        if raw.strip():
            # Skip if already a valid Douki YAML (we silently check)
            try:
                if validate_docstring(
                    raw, getattr(ds_node, 'id', '<unknown node>')
                ):
                    continue
            except ValueError:
                # it's not a valid douki yaml,
                # proceed to converting to see if it is numpydoc
                pass

        try:
            converted = numpydoc_to_douki_yaml(raw)
        except ValueError as e:
            node_name = getattr(ds_node, 'id', '<unknown node>')
            prefix = (
                '<module>' if node_name == '<module>' else f"'{node_name}'"
            )
            errors.append(f'- {prefix}: {e}')
            continue
        if converted == raw:
            continue  # not a numpydoc docstring

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

    if errors:
        errors.reverse()
        raise DocstringValidationError('\n'.join(errors))

    return ''.join(lines)
