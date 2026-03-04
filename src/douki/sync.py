"""
title: Backward-compatible re-exports for douki.sync.
summary: >-
  The actual implementation lives in ``douki._base.sync`` (YAML engine) and
  ``douki._python`` (Python-specific extraction and sync_source). This module
  re-exports everything so that ``from douki.sync import ...`` keeps working.
"""

from douki._base.sync import (
    DocstringValidationError,
    FuncInfo,
    ParamInfo,
    _extract_param_desc,
    _extract_returns_desc,
    _load_docstring_yaml,
    _rebuild_yaml,
    _yaml_scalar,
    sync_docstring,
    validate_docstring,
)
from douki._python.extractor import extract_functions
from douki._python.sync import sync_source

__all__ = [
    'DocstringValidationError',
    'FuncInfo',
    'ParamInfo',
    '_extract_param_desc',
    '_extract_returns_desc',
    '_load_docstring_yaml',
    '_rebuild_yaml',
    '_yaml_scalar',
    'extract_functions',
    'sync_docstring',
    'sync_source',
    'validate_docstring',
]
