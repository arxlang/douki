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
        """
        ...  # pragma: no cover

    @property
    @abstractmethod
    def config(self) -> BaseConfig:
        """
        title: Configuration loader for this language.
        """
        ...  # pragma: no cover

    @abstractmethod
    def sync_source(
        self, source: str, *, migrate: Optional[str] = None
    ) -> str:
        """
        title: Synchronize docstrings in the given source code.
        parameters:
          migrate:
            optional: true
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
    """
    # Create a temporary instance just to get its name
    instance = lang_class()
    _REGISTRY[instance.name] = lang_class


def get_language(name: str) -> BaseLanguage:
    """
    title: Get an initialized language plugin by name.
    """
    if name not in _REGISTRY:
        raise ValueError(f"Language '{name}' is not registered.")
    return _REGISTRY[name]()


def get_registered_language_names() -> list[str]:
    """
    title: Return a list of registered language plugin names.
    """
    return list(_REGISTRY.keys())
