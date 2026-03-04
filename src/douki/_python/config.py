"""
title: Python-specific configuration loading.
"""

from __future__ import annotations

import fnmatch
import sys

from pathlib import Path
from typing import List

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from douki._base.config import BaseConfig


class PythonConfig(BaseConfig):
    """
    title: Python language configuration loader.
    summary: >-
      Reads exclude patterns from ``pyproject.toml`` and collects ``.py``
      files.
    """

    def load_exclude_patterns(self, cwd: Path) -> List[str]:
        """
        title: Load exclude patterns from pyproject.toml in cwd or parents.
        parameters:
          cwd:
            type: Path
        returns:
          type: List[str]
        """
        curr = cwd.resolve()
        while True:
            pyproject = curr / 'pyproject.toml'
            if pyproject.is_file():
                try:
                    with pyproject.open('rb') as f:
                        data = tomllib.load(f)
                    excludes = (
                        data.get('tool', {})
                        .get('douki', {})
                        .get('exclude', [])
                    )
                    if isinstance(excludes, list):
                        return [str(e) for e in excludes]
                except Exception:
                    pass
                break
            parent = curr.parent
            if parent == curr:
                break
            curr = parent
        return []

    def collect_files(
        self, paths: List[Path], excludes: List[str]
    ) -> List[Path]:
        """
        title: Expand directories to .py files and filter excluded.
        parameters:
          paths:
            type: List[Path]
          excludes:
            type: List[str]
        returns:
          type: List[Path]
        """
        result: List[Path] = []
        for p in paths:
            if p.is_dir():
                for child in p.rglob('*.py'):
                    if not _is_excluded(child, excludes):
                        result.append(child)
            elif p.suffix == '.py':
                if not _is_excluded(p, excludes):
                    result.append(p)
        return sorted(set(result))


def _is_excluded(path: Path, excludes: List[str]) -> bool:
    """
    title: Check if path matches any of the exclude patterns.
    parameters:
      path:
        type: Path
      excludes:
        type: List[str]
    returns:
      type: bool
    """
    if not excludes:
        return False

    try:
        rel_path = path.resolve().relative_to(Path.cwd().resolve())
        path_str = rel_path.as_posix()
    except ValueError:
        # If the path is outside cwd, just use its absolute posix string.
        path_str = path.resolve().as_posix()

    for pattern in excludes:
        if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(
            path_str, f'*/{pattern}'
        ):
            return True
        if path_str.startswith(pattern.rstrip('/') + '/'):
            return True
    return False
