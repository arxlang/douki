"""
title: Python-specific configuration loading.
"""

from __future__ import annotations

from douki._base.config import BaseConfig
from douki._python.defaults import PYTHON_DEFAULTS


class PythonConfig(BaseConfig):
    """
    title: Python language configuration loader.
    summary: Uses the shared discovery helpers to collect Python source files.
    """

    @property
    def file_extensions(self) -> tuple[str, ...]:
        """
        title: File extensions handled by the Python backend.
        returns:
          type: tuple[str, Ellipsis]
        """
        return PYTHON_DEFAULTS.file_extensions
