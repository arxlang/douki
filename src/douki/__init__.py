"""
title: Douki, the language-agnostic YAML docstring toolkit.
"""

from __future__ import annotations

from importlib import metadata as importlib_metadata


def get_version() -> str:
    """
    title: Return the program version.
    returns:
      - type: str
    """
    try:
        return importlib_metadata.version(__name__)
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover
        return '0.8.0'  # semantic-release


version = get_version()

__version__ = version
__author__ = 'Ivan Ogasawara'
__email__ = 'ivan.ogasawara@gmail.com'

__all__ = ['__author__', '__email__', '__version__']
