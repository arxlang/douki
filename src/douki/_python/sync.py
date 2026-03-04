"""
title: Python-specific source synchronization.
summary: |-
  Wires the Python AST extractor to the base YAML sync engine,
  providing the ``sync_source`` function that operates on full
  Python source strings.
"""

from __future__ import annotations

import ast
import re

from typing import List, Optional

from douki._base.sync import (
    DocstringValidationError,
    sync_docstring,
    validate_docstring,
)
from douki._python.defaults import PYTHON_DEFAULTS
from douki._python.extractor import extract_functions


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
                func_name=func.name,
                content_indent=len(content_indent),
                language_defaults=PYTHON_DEFAULTS,
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
    title: Replace numpydoc-style docstrings with Douki YAML.
    parameters:
      source:
        type: str
    returns:
      type: str
    """
    from douki._python.migrate import numpydoc_to_douki_yaml

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
