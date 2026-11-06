"""
title: Regression tests for Douki performance optimizations.
"""

from __future__ import annotations

import os

from pathlib import Path
from typing import Callable, Iterator

import pytest
import yaml

from douki._base import discovery, validation
from douki._base import sync as core_sync
from douki._python.sync import sync_source


def test_source_docstring_is_parsed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Source synchronization parses each docstring once.
    """
    original_load = core_sync._safe_load
    calls: list[str] = []

    def tracked_load(raw: str) -> object:
        """
        title: Record and parse one document.
        """
        calls.append(raw)
        return original_load(raw)

    monkeypatch.setattr(core_sync, '_safe_load', tracked_load)
    source = (
        'def double(value: int) -> int:\n'
        '    """\n'
        '    title: Double a number\n'
        '    """\n'
        '    return value * 2\n'
    )
    updated = sync_source(source)
    assert len(calls) == 1
    assert 'parameters:' not in updated
    assert sync_source(updated) == updated


def test_schema_validator_is_reused() -> None:
    """
    title: Repeated validation uses the same compiled schema validator.
    """
    validation._validator.cache_clear()
    first = validation._validator()
    validation.validate_schema({'title': 'first'})
    validation.validate_schema({'title': 'second'})
    assert validation._validator() is first


def test_safe_python_yaml_loader_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Retain compatibility without the LibYAML C extension.
    """
    monkeypatch.setattr(core_sync, '_SAFE_LOADER', yaml.SafeLoader)
    assert core_sync.validate_docstring('title: safe', 'safe')
    assert core_sync.sync_docstring('title: safe', [], '') == ('title: safe\n')


def test_prunes_ignored_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Ignore whole directories before walking their children.
    """
    (tmp_path / '.gitignore').write_text('ignored/\n')
    ignored = tmp_path / 'ignored'
    ignored.mkdir()
    (ignored / 'bad.py').write_text('broken')
    (tmp_path / 'good.py').write_text('valid')

    original_walk = os.walk
    visited: list[Path] = []

    def tracked_walk(
        top: str | os.PathLike[str],
        topdown: bool = True,
        onerror: Callable[[OSError], None] | None = None,
        followlinks: bool = False,
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        """
        title: Record directories reached by discovery.
        """
        for root, dirs, names in original_walk(
            top, topdown=topdown, onerror=onerror, followlinks=followlinks
        ):
            visited.append(Path(root))
            yield root, dirs, names

    monkeypatch.setattr(discovery.os, 'walk', tracked_walk)
    files = discovery.collect_source_files(
        [tmp_path],
        file_extensions=('.py',),
        discovery=discovery.DiscoveryConfig(root=tmp_path),
    )
    assert files == [tmp_path / 'good.py']
    assert ignored not in visited


def test_negation_retains_reincluded_files(tmp_path: Path) -> None:
    """
    title: An inherited negation keeps an ignored subtree traversable.
    """
    (tmp_path / '.gitignore').write_text('ignored/\n!ignored/\n')
    ignored = tmp_path / 'ignored'
    ignored.mkdir()
    (ignored / 'allowed.py').write_text('valid')
    files = discovery.collect_source_files(
        [tmp_path],
        file_extensions=('.py',),
        discovery=discovery.DiscoveryConfig(root=tmp_path),
    )
    assert files == [ignored / 'allowed.py']


def test_prunes_configured_directory(tmp_path: Path) -> None:
    """
    title: Whole-directory exclusions prune descendants.
    """
    smoke = tmp_path / 'tests' / 'smoke'
    smoke.mkdir(parents=True)
    (smoke / 'ignored.py').write_text('ignored')
    (tmp_path / 'included.py').write_text('included')
    files = discovery.collect_source_files(
        [tmp_path],
        file_extensions=('.py',),
        discovery=discovery.DiscoveryConfig(
            root=tmp_path,
            exclude_patterns=('tests/smoke/*',),
        ),
    )
    assert files == [tmp_path / 'included.py']
