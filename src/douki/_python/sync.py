"""
title: Python-specific source synchronization.
summary: >-
  Wires the Python AST extractor to the base YAML sync engine,

  providing the ``sync_source`` function that operates on full

  Python source strings.
"""

from __future__ import annotations

import ast
import inspect
import re

from typing import Optional

from public import private

from douki._base.sync import (
    DocstringValidationError,
    FuncInfo,
    _parse_validated_docstring,
    validate_docstring,
)
from douki._python.extractor import extract_functions
from douki.documentation import (
    Parameter,
    Signature,
    format_documentation,
    validate_annotations,
)
from douki.typechecking import typechecked


@private
@typechecked
def signature_for(func: FuncInfo) -> Signature:
    """
    title: Adapt source annotations to the shared metadata contract.
    parameters:
      func: Parsed declaration metadata.
    returns: Annotation metadata without implicit method receivers.
    """
    return Signature(
        parameters=(
            tuple(Parameter(p.name, p.annotation) for p in func.params)
            if func.is_callable
            else None
        ),
        returns=func.return_annotation,
        attributes=tuple(Parameter(p.name, p.annotation) for p in func.attrs),
    )


@private
@typechecked
def needs_returns(func: FuncInfo) -> bool:
    """
    title: Determine whether a callable has a result to describe.
    parameters:
      func: Parsed function or method.
    returns: Whether a result description is needed.
    """
    return func.is_callable and func.return_annotation not in (
        'None', 'NoneType', 'NoReturn', 'Never',
        'typing.NoReturn', 'typing.Never',
    )


@private
@typechecked
def scaffold_fields(data: dict[str, object], func: FuncInfo) -> None:
    """
    title: Add missing description placeholders without storing types.
    parameters:
      data: Authored YAML validated against the source schema.
      func: Source metadata defining the expected names.
    """
    if func.is_callable:
        raw_params = data.get('parameters')
        if raw_params is not None and not isinstance(raw_params, dict):
            raise ValueError('schema: parameters must be a mapping')
        existing = dict(raw_params) if raw_params is not None else {}
        expected = {param.name for param in func.params}
        stale = sorted(set(existing) - expected)
        if stale:
            raise ValueError(
                'signature: Unknown documented parameters: '
                + ', '.join(stale)
            )
        for param in func.params:
            existing.setdefault(param.name, {'description': 'TODO'})
        if existing or 'parameters' in data:
            data['parameters'] = existing
        if needs_returns(func) and 'returns' not in data:
            data['returns'] = {'description': 'TODO'}

    if func.attrs:
        raw_attrs = data.get('attributes')
        if raw_attrs is not None and not isinstance(raw_attrs, dict):
            raise ValueError('schema: attributes must be a mapping')
        existing_attrs = dict(raw_attrs) if raw_attrs is not None else {}
        for attr in func.attrs:
            existing_attrs.setdefault(attr.name, {'description': 'TODO'})
        data['attributes'] = existing_attrs


@private
@typechecked
def has_description(value: object) -> bool:
    """
    title: Check whether a documentation field contains authored prose.
    parameters:
      value: Source YAML string or documentation entry.
    returns: False for missing, empty or TODO descriptions.
    """
    description = (
        value.get('description') if isinstance(value, dict) else value
    )
    if not isinstance(description, str):
        return False
    content = description.strip()
    return bool(content) and content.upper() != 'TODO' and not (
        content.upper().startswith('TODO:')
    )


@private
@typechecked
def completeness_errors(
    data: dict[str, object], func: FuncInfo
) -> list[str]:
    """
    title: Report missing, stale and placeholder descriptions.
    parameters:
      data: Schema-validated authored documentation.
      func: Parsed declaration metadata.
    returns: Documentation completeness diagnostics.
    """
    errors: list[str] = []
    if func.is_callable:
        documented = data.get('parameters', {})
        entries = documented if isinstance(documented, dict) else {}
        expected = {param.name for param in func.params}
        for stale in sorted(set(entries) - expected):
            errors.append(f"stale documented parameter '{stale}'")
        for name in sorted(expected):
            if not has_description(entries.get(name)):
                errors.append(f"missing description for parameter '{name}'")
        if needs_returns(func) and not has_description(data.get('returns')):
            errors.append('missing description for return value')

    documented_attrs = data.get('attributes', {})
    attr_entries = (
        documented_attrs if isinstance(documented_attrs, dict) else {}
    )
    for attr in func.attrs:
        if not has_description(attr_entries.get(attr.name)):
            errors.append(f"missing description for attribute '{attr.name}'")
    return errors


@typechecked
def check_source(source: str) -> None:
    """
    title: Validate annotations and authored documentation without changes.
    parameters:
      source: Python source code to validate.
    raises:
      DocstringValidationError: Missing or invalid documentation.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise DocstringValidationError(f'syntax: {error.msg}') from error

    funcs = extract_functions(source)
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and ast.get_docstring(node) is None:
            errors.append(f"- '{node.name}': missing docstring")
    for func in funcs:
        prefix = '<module>' if func.name == '<module>' else f"'{func.name}'"
        node = func.docstring_node
        if node is None:
            errors.append(f'- {prefix}: missing docstring')
            continue
        try:
            raw = inspect.cleandoc(str(node.value))
            data = _parse_validated_docstring(raw)
            validate_annotations(signature_for(func), data)
            errors.extend(
                f'- {prefix}: {problem}'
                for problem in completeness_errors(data, func)
            )
        except ValueError as error:
            errors.append(f'- {prefix}: {error}')
    if errors:
        raise DocstringValidationError('\n'.join(errors))


@typechecked
def format_source(source: str) -> str:
    """
    title: Format source docstrings without synchronizing declarations.
    parameters:
      source: Python source code with YAML docstrings.
    returns: Source with canonical YAML presentation only.
    """
    return process_source(source, scaffold=False)


@typechecked
def sync_source(
    source: str,
    *,
    migrate: Optional[str] = None,
) -> str:
    """
    title: Scaffold missing descriptions and format authored documentation.
    parameters:
      source: Python source with Douki docstrings.
      migrate: Optional source documentation format to migrate.
    returns: Source with missing entries added and no authored types.
    """
    return process_source(source, scaffold=True, migrate=migrate)


@private
@typechecked
def process_source(
    source: str,
    *,
    scaffold: bool,
    migrate: Optional[str] = None,
) -> str:
    """
    title: Format or scaffold documentation without storing types.
    parameters:
      source:
        description: Python source code.
      scaffold:
        description: Whether to scaffold missing documentation entries.
      migrate:
        optional: true
        description: Convert NumPy docstrings before processing when set.
    returns: The (possibly modified) source string.
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

    # Check for missing docstrings — every function, class, and module
    # must have a docstring.
    missing = [f for f in funcs if f.docstring_node is None]
    if missing and scaffold:
        errors = []
        for f in missing:
            prefix = '<module>' if f.name == '<module>' else f"'{f.name}'"
            errors.append(f'- {prefix}: missing docstring')
        raise DocstringValidationError('\n'.join(errors))

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

        # Parse and validate once, then pass the mapping to the sync engine.
        try:
            parsed = _parse_validated_docstring(inspect.cleandoc(raw))
            if scaffold:
                validate_annotations(signature_for(func), parsed)
                scaffold_fields(parsed, func)
        except ValueError as e:
            prefix = (
                '<module>' if func.name == '<module>' else f"'{func.name}'"
            )
            errors.append(f'- {prefix}: {e}')
            continue

        # We need the start/end lines of the docstring.
        ds_start = ds_node.lineno - 1  # 0-based
        ds_end = ds_node.end_lineno
        if ds_end is None or ds_node.end_col_offset is None:
            continue  # safety

        # AST columns are UTF-8 byte offsets. Retain adjacent comments/code.
        prefix = (
            lines[ds_start]
            .encode('utf-8')[: ds_node.col_offset]
            .decode('utf-8')
        )
        suffix = (
            lines[ds_end - 1]
            .encode('utf-8')[ds_node.end_col_offset :]
            .decode('utf-8')
        )

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
        content_indent = indent
        ds_lines = raw.split('\n')
        for dl in ds_lines[1:]:
            if dl.strip():
                leading = len(dl) - len(dl.lstrip())
                content_indent = ' ' * leading
                break

        try:
            synced = format_documentation(
                parsed,
                width=79 - len(content_indent),
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
        new_content = new_content.replace('\\', '\\\\').replace(
            quote,
            '\\' + quote,
        )
        new_docstring = (
            f'{prefix}{quote}\n{new_content}\n{indent}{quote}{suffix}'
        )

        lines[ds_start:ds_end] = [new_docstring]

    if errors:
        errors.reverse()
        raise DocstringValidationError('\n'.join(errors))

    return ''.join(lines)


def _migrate_numpydoc(source: str) -> str:
    """
    title: Replace numpydoc-style docstrings with Douki YAML.
    parameters:
      source:
        description: Source code whose docstrings are being processed.
    returns: Source with recognized NumPy docstrings converted to Douki YAML.
    """
    from douki._python.migrate import numpydoc_to_douki_yaml

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    lines = source.splitlines(keepends=True)

    # Collect all docstring nodes
    ds_nodes: list[ast.Constant] = []
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
