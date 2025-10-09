"""Douki."""

from __future__ import annotations

import sys
import types

from importlib import import_module
from importlib import metadata as importlib_metadata
from typing import Any


def get_version() -> str:
    """Return the program version."""
    try:
        return importlib_metadata.version(__name__)
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover
        return '0.6.0'  # semantic-release


core = import_module('.core', __name__)
apply = core.apply
DocString = core.DocString


class _CallableModule(types.ModuleType):
    """A module that can also be used as a decorator."""

    # allow @douki(...)
    def __call__(self, _obj: Any = None, **kwargs: Any) -> Any:
        """Allow calling the module with @douki"""
        return apply(_obj, **kwargs)


self_module = sys.modules[__name__]
self_module.__class__ = _CallableModule


version = get_version()

__version__ = version
__author__ = 'Ivan Ogasawara'
__email__ = 'ivan.ogasawara@gmail.com'

__all__ = ['DocString', '__author__', '__email__', '__version__', 'apply']
