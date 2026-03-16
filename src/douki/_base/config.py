"""
title: Abstract base configuration for language plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from douki._base.discovery import (
    DiscoveryConfig,
    collect_source_files,
    load_douki_discovery_config,
)


class BaseConfig(ABC):
    """
    title: Abstract configuration loader for a language backend.
    summary: >-
      Each language plugin subclasses this to define how exclude patterns and
      source files are discovered.
    """

    @property
    @abstractmethod
    def file_extensions(self) -> tuple[str, ...]:
        """
        title: File extensions handled by the language backend.
        returns:
          type: tuple[str, Ellipsis]
        """
        ...  # pragma: no cover

    def load_discovery_config(self, cwd: Path) -> DiscoveryConfig:
        """
        title: Load shared discovery settings from project configuration.
        parameters:
          cwd:
            type: Path
        returns:
          type: DiscoveryConfig
        """
        return load_douki_discovery_config(cwd)

    def collect_files(
        self,
        paths: list[Path],
        discovery: DiscoveryConfig,
    ) -> list[Path]:
        """
        title: Expand paths into source files, filtering excluded ones.
        parameters:
          paths:
            type: list[Path]
          discovery:
            type: DiscoveryConfig
        returns:
          type: list[Path]
        """
        return collect_source_files(
            paths,
            file_extensions=self.file_extensions,
            discovery=discovery,
        )
