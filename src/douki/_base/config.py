"""
title: Abstract base configuration for language plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class BaseConfig(ABC):
    """
    title: Abstract configuration loader for a language backend.
    summary: >-
      Each language plugin subclasses this to define how exclude patterns and
      source files are discovered.
    """

    @abstractmethod
    def load_exclude_patterns(self, cwd: Path) -> List[str]:
        """
        title: Load exclude patterns from a config file.
        parameters:
          cwd:
            type: Path
        returns:
          type: List[str]
        """
        ...  # pragma: no cover

    @abstractmethod
    def collect_files(
        self, paths: List[Path], excludes: List[str]
    ) -> List[Path]:
        """
        title: Expand paths into source files, filtering excluded ones.
        parameters:
          paths:
            type: List[Path]
          excludes:
            type: List[str]
        returns:
          type: List[Path]
        """
        ...  # pragma: no cover
