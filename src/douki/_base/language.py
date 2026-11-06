"""
title: Language plugin interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from douki._base.config import BaseConfig


class BaseLanguage(ABC):
    """
    title: Abstract base class for a language plugin.
    summary: Plugins subclass this to bind their language-specific extractor,
      sync logic, and configuration.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        title: The name of the language (e.g. 'python').
        returns: Name used to select the backend in the registry and CLI.
        """
        ...  # pragma: no cover

    @property
    @abstractmethod
    def config(self) -> BaseConfig:
        """
        title: Configuration loader for this language.
        returns: Configuration loader and file discovery settings for this
          backend.
        """
        ...  # pragma: no cover

    @abstractmethod
    def sync_source(
        self, source: str, *, migrate: Optional[str] = None
    ) -> str:
        """
        title: Synchronize docstrings in the given source code.
        parameters:
          source:
            description: Source code whose docstrings are being processed.
          migrate:
            optional: true
            description: Docstring format to convert before formatting; None
              disables migration.
        returns: Source code with formatted Douki YAML docstrings.
        """
        _ = (source, migrate)
        raise NotImplementedError  # pragma: no cover


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[BaseLanguage]] = {}


def register_language(lang_class: type[BaseLanguage]) -> None:
    """
    title: Register a language plugin class.
    parameters:
      lang_class:
        description: Backend class to register under its declared language
          name.
    """
    # Create a temporary instance just to get its name
    instance = lang_class()
    _REGISTRY[instance.name] = lang_class


def get_language(name: str) -> BaseLanguage:
    """
    title: Get an initialized language plugin by name.
    parameters:
      name:
        description: Name of a registered language backend.
    returns: New instance of the requested language backend.
    """
    if name not in _REGISTRY:
        raise ValueError(f"Language '{name}' is not registered.")
    return _REGISTRY[name]()


def get_registered_language_names() -> list[str]:
    """
    title: Return a list of registered language plugin names.
    returns: Language names in registration order.
    """
    return list(_REGISTRY.keys())
