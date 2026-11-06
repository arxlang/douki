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
    """

    def __init__(self) -> None:
        """
        title: Initialize the Python language backend.
        """
        self._config: PythonConfig = PythonConfig()

    @property
    def name(self) -> str:
        """
        title: Language name (python).
        """
        return 'python'

    @property
    def config(self) -> BaseConfig:
        """
        title: Returns the PythonConfig instance.
        """
        return self._config

    def sync_source(
        self, source: str, *, migrate: Optional[str] = None
    ) -> str:
        """
        title: Synchronize Python source code using the AST extractor.
        parameters:
          migrate:
            optional: true
        """
        return py_sync_source(source, migrate=migrate)
