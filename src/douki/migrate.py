"""
title: Public API for migrating docstrings to Douki YAML.
summary: >-
  Provides the ``migrate_source`` dispatch function that routes to the
  appropriate language plugin.
"""

from __future__ import annotations

__all__ = [
    'migrate_source',
]


def migrate_source(
    source: str,
    *,
    from_format: str,
    lang: str = 'python',
) -> str:
    """
    title: Migrate docstrings from another format to Douki YAML.
    summary: Dispatches to ``sync_source`` with the *migrate* parameter set.
    parameters:
      source:
        type: str
      from_format:
        type: str
      lang:
        type: str
        optional: true
    returns:
      type: str
    """
    from douki.sync import sync_source

    return sync_source(source, lang=lang, migrate=from_format)
