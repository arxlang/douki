"""
title: Backward-compatible re-exports for douki.migrate.
summary: The actual implementation lives in ``douki._python.migrate``.
"""

from douki._python.migrate import (
    _is_numpydoc_docstring,
    _parse_map_section,
    _parse_simple_section,
    _serialize_douki_yaml,
    _split_sections,
    numpydoc_to_douki_yaml,
)

__all__ = [
    '_is_numpydoc_docstring',
    '_parse_map_section',
    '_parse_simple_section',
    '_serialize_douki_yaml',
    '_split_sections',
    'numpydoc_to_douki_yaml',
]
