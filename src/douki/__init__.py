"""
title: Douki, the language-agnostic YAML docstring toolkit.
"""

from __future__ import annotations

from importlib import metadata as importlib_metadata
from typing import TYPE_CHECKING

from douki.typechecking import typechecked

if TYPE_CHECKING:
    from douki.documentation import (
        DocumentationError as DocumentationError,
    )
    from douki.documentation import (
        Parameter as Parameter,
    )
    from douki.documentation import (
        Signature as Signature,
    )
    from douki.documentation import (
        enrich as enrich,
    )
    from douki.documentation import (
        format_documentation as format_documentation,
    )
    from douki.documentation import (
        validate_annotations as validate_annotations,
    )
    from douki.helping import (
        disable as disable,
    )
    from douki.helping import (
        enable as enable,
    )
    from douki.helping import (
        help as help,
    )
    from douki.introspection import getdoc as getdoc


def get_version() -> str:
    """
    title: Return the program version.
    returns:
      description: Installed package version, or the source version when
        not installed.
    """
    try:
        return importlib_metadata.version(__name__)
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover
        return '0.13.0'  # semantic-release


version = get_version()

__version__ = version
__author__ = 'Ivan Ogasawara'
__email__ = 'ivan.ogasawara@gmail.com'

__all__ = [
    'DocumentationError',
    'Parameter',
    'Signature',
    '__author__',
    '__email__',
    '__version__',
    'disable',
    'enable',
    'enrich',
    'format_documentation',
    'getdoc',
    'help',
    'validate_annotations',
]


@typechecked
def __getattr__(name: str) -> object:
    """
    title: Load optional runtime helpers only when explicitly requested.
    parameters:
      name:
        description: Public runtime helper to import on first access.
    returns:
      description: Requested helper, cached on the package for subsequent
        access.
    """
    from importlib import import_module

    modules = {
        'DocumentationError': 'documentation',
        'Parameter': 'documentation',
        'Signature': 'documentation',
        'enrich': 'documentation',
        'format_documentation': 'documentation',
        'validate_annotations': 'documentation',
        'getdoc': 'introspection',
        'help': 'helping',
        'enable': 'helping',
        'disable': 'helping',
    }
    if name not in modules:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value: object = getattr(import_module(f'douki.{modules[name]}'), name)
    globals()[name] = value
    return value
