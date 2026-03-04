"""
title: Python-specific defaults for Douki.
"""

from __future__ import annotations

from douki._base.defaults import LanguageDefaults

PYTHON_DEFAULTS = LanguageDefaults(
    visibility='public',
    mutability='mutable',
    scope_function='static',
    scope_method='instance',
    file_extensions=('.py',),
    config_files=('pyproject.toml',),
)
