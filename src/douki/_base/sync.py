"""
title: Language-agnostic YAML docstring sync engine.
summary: |-
  This module provides the core logic for merging signature information
  into Douki YAML docstrings and rebuilding the YAML output. It is
  intentionally pure — no file I/O, no AST parsing.
"""

from __future__ import annotations

import textwrap

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from douki._base.defaults import LanguageDefaults
from douki._base.validation import validate_schema

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
    title: A single parameter extracted from a source signature.
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
      Everything we need to know about a single function, class, or module
      docstring site.
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
        type: Optional[Any]
      is_method:
        type: bool
    """

    name: str
    lineno: int  # 1-based line of the *def* keyword, or 1 for module
    params: List[ParamInfo] = field(default_factory=list)
    # Class-level annotated vars, extracted from the class body by
    # the language extractor
    attrs: List[ParamInfo] = field(default_factory=list)
    return_annotation: str = ''
    docstring_node: Optional[Any] = None
    is_method: bool = False


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
    func_name: str = '<unknown>',
    content_indent: int = 4,
    language_defaults: Optional[LanguageDefaults] = None,
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
      func_name:
        type: str
      content_indent:
        type: int
      language_defaults:
        type: Optional[LanguageDefaults]
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
    defaults = (
        language_defaults.get_field_defaults()
        if language_defaults
        else _PYTHON_DEFAULTS_COMPAT
    )
    return _rebuild_yaml(data, content_indent, field_defaults=defaults)


# Canonical key ordering
_KEY_ORDER = [
    'title',
    'summary',
    'deprecated',
    'visibility',
    'mutability',
    'scope',
    'parameters',
    'attributes',
    'returns',
    'yields',
    'receives',
    'raises',
    'warnings',
    'see_also',
    'notes',
    'references',
    'examples',
    'methods',
]

# Backward-compat defaults matching the old hardcoded Python behaviour
_PYTHON_DEFAULTS_COMPAT: Dict[str, Any] = {
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


def _rebuild_yaml(
    data: Dict[str, Any],
    content_indent: int = 4,
    *,
    field_defaults: Optional[Dict[str, Any]] = None,
) -> str:
    """
    title: Serialize *data* to YAML with canonical key order.
    summary: Omits fields that match language defaults.
    parameters:
      data:
        type: Dict[str, Any]
      content_indent:
        type: int
      field_defaults:
        type: Optional[Dict[str, Any]]
    returns:
      type: str
    """
    if field_defaults is None:
        field_defaults = _PYTHON_DEFAULTS_COMPAT

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
        # Skip language defaults
        if key in field_defaults:
            if value == field_defaults[key]:
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
