"""
title: Python language plugin.
"""

from __future__ import annotations

from typing import Optional

from douki._base.config import BaseConfig
from douki._base.language import BaseLanguage
from douki._python.config import PythonConfig
from douki._python.sync import sync_source as py_sync_source


class PythonLanguage(BaseLanguage):
    """
    title: The Douki Python language backend.
    attributes:
      _config:
        description: Configuration loader used for Python source discovery.
    """

    _config: PythonConfig

    def __init__(self) -> None:
        """
        title: Initialize the Python language backend.
        """
        self._config = PythonConfig()

    @property
    def name(self) -> str:
        """
        title: Language name (python).
        returns:
          description: Registry name identifying the Python backend.
        """
        return 'python'

    @property
    def config(self) -> BaseConfig:
        """
        title: Returns the PythonConfig instance.
        returns:
          description: Configuration loader used by this backend instance.
        """
        return self._config

    def sync_source(
        self, source: str, *, migrate: Optional[str] = None
    ) -> str:
        """
        title: Synchronize Python source code using the AST extractor.
        parameters:
          source:
            description: Source code whose docstrings are being processed.
          migrate:
            optional: true
            description: Docstring format to convert before formatting; None
              disables migration.
        returns:
          description: Python source with validated, formatted Douki YAML
            docstrings.
        """
        return py_sync_source(source, migrate=migrate)
