"""
title: Migrate docstrings from other formats to Douki YAML.
notes: |
  Currently supports: **numpy** (numpydoc).
"""

from __future__ import annotations

import re
import textwrap

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------
# NumPy-style section names → Douki YAML keys
# ---------------------------------------------------------------

_NUMPY_SECTION_MAP: Dict[str, str] = {
    'parameters': 'parameters',
    'params': 'parameters',
    'arguments': 'parameters',
    'args': 'parameters',
    'returns': 'returns',
    'return': 'returns',
    'yields': 'yields',
    'yield': 'yields',
    'receives': 'receives',
    'raises': 'raises',
    'warns': 'warnings',
    'warnings': 'warnings',
    'see also': 'see_also',
    'notes': 'notes',
    'references': 'references',
    'examples': 'examples',
    'attributes': 'attributes',
    'methods': 'methods',
    'deprecated': 'deprecated',
    'other parameters': 'parameters',
}

# Sections with key-value entries (name : type \n description)
_MAP_SECTIONS = frozenset(
    {
        'parameters',
        'raises',
        'warnings',
        'attributes',
    }
)


def _is_numpydoc_docstring(raw: str) -> bool:
    """title: 'Heuristic: does *raw* look like a NumPy-style docstring?'"""
    # Must have at least one section header with dashes underline
    return bool(
        re.search(
            r'^[ \t]*\w[\w ]*\n[ \t]*-{3,}',
            raw,
            re.MULTILINE,
        )
    )


def _split_sections(
    raw: str,
) -> Tuple[str, List[Tuple[str, str]]]:
    """
    title: Split a NumPy docstring into (narrative, sections).
    returns: Each section is (header_lower, body_text).
    """
    lines = raw.splitlines()
    narrative_lines: List[str] = []
    sections: List[Tuple[str, str]] = []

    # Find section boundaries: a section starts with a header
    # line followed by a dashes line of equal or greater length.
    section_starts: List[Tuple[int, str]] = []
    for i in range(len(lines) - 1):
        header = lines[i].strip()
        dashes = lines[i + 1].strip()
        if header and dashes and set(dashes) == {'-'} and len(dashes) >= 3:
            section_starts.append((i, header.lower()))

    if not section_starts:
        return raw.strip(), []

    # Everything before first section is narrative
    narrative_lines = lines[: section_starts[0][0]]

    # Extract each section body
    for idx, (start, header) in enumerate(section_starts):
        body_start = start + 2  # skip header + dashes
        if idx + 1 < len(section_starts):
            body_end = section_starts[idx + 1][0]
        else:
            body_end = len(lines)
        body = '\n'.join(lines[body_start:body_end])
        sections.append((header, textwrap.dedent(body).strip()))

    narrative = '\n'.join(narrative_lines).strip()
    return narrative, sections


def _parse_map_section(
    body: str,
) -> Dict[str, Dict[str, str]]:
    """
    title: Parse a numpy map section (Parameters, Raises, etc).
    examples:
      - code: |
          name : type
              Description line 1
              Description line 2
          name2 : type2
              Description
    returns: A dict of ``{name: {type: ..., description: ...}}``.
    """
    result: Dict[str, Dict[str, str]] = {}
    current_name: Optional[str] = None
    current_type: str = ''
    current_desc_lines: List[str] = []

    for line in body.splitlines():
        if line and not line[0].isspace():
            # Save previous entry
            if current_name is not None:
                desc = ' '.join(
                    ln.strip() for ln in current_desc_lines
                ).strip()
                entry: Dict[str, str] = {}
                if current_type:
                    entry['type'] = current_type
                if desc:
                    entry['description'] = desc
                result[current_name] = entry

            # Parse new entry: "name : type"
            parts = line.split(':', 1)
            current_name = parts[0].strip()
            current_type = parts[1].strip() if len(parts) > 1 else ''
            current_desc_lines = []
        elif current_name is not None:
            stripped = line.strip()
            if stripped:
                current_desc_lines.append(stripped)

    # Save last entry
    if current_name is not None:
        desc = ' '.join(ln.strip() for ln in current_desc_lines).strip()
        entry2: Dict[str, str] = {}
        if current_type:
            entry2['type'] = current_type
        if desc:
            entry2['description'] = desc
        result[current_name] = entry2

    return result


def _parse_simple_section(body: str) -> str:
    """title: Parse a simple text section (returns, notes, etc)."""
    return body.strip()


def numpydoc_to_douki_yaml(raw: str) -> str:
    """
    title: Convert a NumPy-style docstring to Douki YAML format.
    returns:
      - The YAML string (without triple-quotes).
      - If *raw* is not a valid NumPy docstring, returns it unchanged.
    """
    if not _is_numpydoc_docstring(raw):
        return raw

    narrative, sections = _split_sections(raw)

    # Build Douki data structure
    data: Dict[str, Any] = {}

    # Parse narrative into title + summary
    if narrative:
        nlines = narrative.splitlines()
        data['title'] = nlines[0].rstrip('.')
        if len(nlines) > 1:
            summary = '\n'.join(nlines[1:]).strip()
            if summary:
                data['summary'] = summary
    else:
        data['title'] = 'TODO'

    # Process sections
    for header, body in sections:
        douki_key = _NUMPY_SECTION_MAP.get(header)
        if douki_key is None:
            continue

        if douki_key == 'parameters':
            data[douki_key] = _parse_map_section(body)
        elif douki_key in ('raises', 'warnings'):
            # Build list of {type, description}
            parsed = _parse_map_section(body)
            items: List[Dict[str, str]] = []
            for name, info in parsed.items():
                item: Dict[str, str] = {'type': name}
                desc = info.get('description', '')
                if desc:
                    item['description'] = desc
                items.append(item)
            data[douki_key] = items
        elif douki_key in ('returns', 'yields', 'receives'):
            # Combine multiple into a single dict {type, description}
            parsed = _parse_map_section(body)
            if parsed:
                types = []
                descs = []
                for type_name, info in parsed.items():
                    types.append(type_name)
                    desc = info.get('description', '')
                    if desc:
                        descs.append(desc.strip())

                type_str = ', '.join(types)
                if len(types) > 1:
                    type_str = f'tuple[{type_str}]'

                entry: Dict[str, str] = {'type': type_str}
                if descs:
                    entry['description'] = ' '.join(descs)
                data[douki_key] = entry
            else:
                # Simple text
                data[douki_key] = _parse_simple_section(body)
        else:
            data[douki_key] = _parse_simple_section(body)

    return _serialize_douki_yaml(data)


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


def _serialize_douki_yaml(data: Dict[str, Any]) -> str:
    """title: Serialize a Douki data dict to YAML text."""
    lines: List[str] = []
    for key in _KEY_ORDER:
        if key not in data:
            continue
        value = data[key]
        if value is None or value == '' or value == {}:
            continue

        if key == 'parameters':
            lines.append('parameters:')
            for k, v in value.items():
                if isinstance(v, dict):
                    lines.append(f'  {k}:')
                    for sk in ('type', 'description'):
                        if sk in v:
                            lines.append(f'    {sk}: {v[sk]}')
                elif v:
                    lines.append(f'  {k}: {v}')
                else:
                    lines.append(f'  {k}:')
        elif isinstance(value, list):
            lines.append(f'{key}:')
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for sk in ('type', 'description', 'code'):
                        if sk in item:
                            prefix = '- ' if first else '  '
                            lines.append(f'  {prefix}{sk}: {item[sk]}')
                            first = False
                else:
                    lines.append(f'  - {item}')
        elif isinstance(value, str) and '\n' in value:
            lines.append(f'{key}: |')
            for ln in value.splitlines():
                lines.append(f'  {ln}')
        elif isinstance(value, dict):
            lines.append(f'{key}:')
            for sk, sv in value.items():
                if isinstance(sv, str) and '\n' in sv:
                    lines.append(f'  {sk}: |')
                    for ln in sv.splitlines():
                        lines.append(f'    {ln}')
                else:
                    lines.append(f'  {sk}: {sv}')
        else:
            lines.append(f'{key}: {value}')

    # Extra keys not in canonical order
    for key in data:
        if key not in _KEY_ORDER:
            lines.append(f'{key}: {data[key]}')

    return '\n'.join(lines) + '\n'
