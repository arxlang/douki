"""
title: Public API for syncing Douki YAML docstrings.
summary: >-
  Provides the ``sync_source`` and ``resolve_files`` dispatch functions that
  route to the appropriate language plugin. Also re-exports language-agnostic
  base types.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import List, Optional

from douki._base.sync import (
    DocstringValidationError,
    FuncInfo,
    ParamInfo,
    sync_docstring,
    validate_docstring,
)

__all__ = [
    'DocstringValidationError',
    'FuncInfo',
    'ParamInfo',
    'resolve_files',
    'sync_docstring',
    'sync_source',
    'validate_docstring',
]


def _ensure_plugins() -> None:
    """
    title: Import language plugins to trigger auto-registration.
    """
    import douki._python  # noqa: F401


def resolve_files(
    files: Optional[List[Path]] = None,
    *,
    lang: str = 'python',
    respect_gitignore: Optional[bool] = None,
) -> List[Path]:
    """
    title: Resolve paths into source files for the given language.
    parameters:
      files:
        type: Optional[List[Path]]
      lang:
        type: str
      respect_gitignore:
        type: Optional[bool]
        optional: true
    returns:
      type: List[Path]
    """
    from douki._base.language import get_language

    _ensure_plugins()
    language = get_language(lang)
    discovery = language.config.load_discovery_config(Path.cwd())
    if respect_gitignore is not None:
        discovery = replace(
            discovery,
            respect_gitignore=respect_gitignore,
        )
    raw = files if files else [Path('.')]
    return language.config.collect_files(raw, discovery)


def sync_source(
    source: str,
    *,
    lang: str = 'python',
    migrate: Optional[str] = None,
) -> str:
    """
    title: Synchronize Douki YAML docstrings in *source*.
    summary: Dispatches to the appropriate language plugin based on *lang*.
    parameters:
      source:
        type: str
      lang:
        type: str
      migrate:
        type: Optional[str]
        optional: true
    returns:
      type: str
    """
    from douki._base.language import get_language

    _ensure_plugins()
    language = get_language(lang)
    return language.sync_source(source, migrate=migrate)
