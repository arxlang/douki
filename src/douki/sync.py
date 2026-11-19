"""
title: Public API for syncing Douki YAML docstrings.
summary: Routes source synchronization, formatting, validation and
  file discovery through language plugins, and re-exports shared
  base types.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

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
    'check_source',
    'format_source',
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
    files: Optional[list[Path]] = None,
    *,
    lang: str = 'python',
    respect_gitignore: Optional[bool] = None,
) -> list[Path]:
    """
    title: Resolve paths into source files for the given language.
    parameters:
      files: >-
        Files or directories to process; an empty value uses the current
        directory.
      lang: Registered language backend used to process the source.
      respect_gitignore:
        optional: true
        description: >-
          Override gitignore filtering; None uses the project setting.
    returns: >-
      Sorted, unique source paths after applying discovery and exclusion
      rules.
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
    title: Synchronize documentation structure with source declarations.
    summary: Dispatches to the appropriate language plugin based
      on *lang*.
    parameters:
      source: Source code whose docstrings are being processed.
      lang: Registered language backend used to process the source.
      migrate:
        optional: true
        description: >-
          Docstring format to convert before formatting; None disables
          migration.
    returns: Source with scaffolded documentation and no authored
      types.
    """
    from douki._base.language import get_language

    _ensure_plugins()
    language = get_language(lang)
    return language.sync_source(source, migrate=migrate)


def format_source(source: str, *, lang: str = 'python') -> str:
    """
    title: Format source docstrings without syncing signature metadata.
    parameters:
      source: Source code to format.
      lang: Registered source language.
    returns: Formatted source code.
    """
    from douki._base.language import get_language

    _ensure_plugins()
    return get_language(lang).format_source(source)


def check_source(source: str, *, lang: str = 'python') -> None:
    """
    title: Validate annotations and documentation completeness.
    parameters:
      source: Source code to validate.
      lang: Registered source language.
    """
    from douki._base.language import get_language

    _ensure_plugins()
    get_language(lang).check_source(source)
