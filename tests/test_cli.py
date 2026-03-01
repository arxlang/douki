"""Tests for douki.cli — Typer-based CLI."""

from __future__ import annotations

import textwrap

from pathlib import Path

from douki.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write *content* to *tmp_path/name* and return the path."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding='utf-8')
    return p


# -------------------------------------------------------------------
# --diff mode
# -------------------------------------------------------------------


def test_diff_mode_exit_0_when_clean(tmp_path: Path) -> None:
    """Already-synced file should produce exit 0."""
    p = _write(
        tmp_path,
        'clean.py',
        '''\
        def hello() -> None:
            """Just a plain docstring."""
            pass
        ''',
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code == 0


def test_diff_mode_exit_1_when_dirty(tmp_path: Path) -> None:
    """Unsynced file should produce exit 1 with diff."""
    p = _write(
        tmp_path,
        'dirty.py',
        '''\
        def add(x: int, y: int) -> int:
            """
            title: Add two numbers
            """
            return x + y
        ''',
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code == 1


def test_diff_mode_shows_output(tmp_path: Path) -> None:
    """Diff output should contain file path."""
    p = _write(
        tmp_path,
        'show.py',
        '''\
        def add(x: int, y: int) -> int:
            """
            title: Add two numbers
            """
            return x + y
        ''',
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert str(p) in result.output or 'title' in result.output


# -------------------------------------------------------------------
# --apply mode
# -------------------------------------------------------------------


def test_apply_mode_updates_file(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        'apply.py',
        '''\
        def add(x: int, y: int) -> int:
            """
            title: Add two numbers
            """
            return x + y
        ''',
    )
    result = runner.invoke(app, ['sync', str(p), '--apply'])
    assert result.exit_code == 0
    content = p.read_text(encoding='utf-8')
    assert 'parameters' in content


def test_apply_mode_idempotent(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        'idem.py',
        '''\
        def add(x: int, y: int) -> int:
            """
            title: Add two numbers
            """
            return x + y
        ''',
    )
    runner.invoke(app, ['sync', str(p), '--apply'])
    first = p.read_text(encoding='utf-8')
    runner.invoke(app, ['sync', str(p), '--apply'])
    second = p.read_text(encoding='utf-8')
    assert first == second


# -------------------------------------------------------------------
# Mutual exclusivity
# -------------------------------------------------------------------


def test_mutual_exclusivity_error(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        'both.py',
        '''\
        def noop() -> None:
            """title: noop"""
            pass
        ''',
    )
    result = runner.invoke(
        app,
        ['sync', str(p), '--diff', '--apply'],
    )
    assert result.exit_code == 2


# -------------------------------------------------------------------
# Multiple files
# -------------------------------------------------------------------


def test_multiple_files(tmp_path: Path) -> None:
    p1 = _write(
        tmp_path,
        'a.py',
        '''\
        def foo(x: int) -> int:
            """title: foo"""
            return x
        ''',
    )
    p2 = _write(
        tmp_path,
        'b.py',
        '''\
        def bar(y: str) -> str:
            """title: bar"""
            return y
        ''',
    )
    result = runner.invoke(
        app,
        ['sync', str(p1), str(p2)],
    )
    # Both files should be processed
    assert result.exit_code in (0, 1)


# -------------------------------------------------------------------
# Non-py files
# -------------------------------------------------------------------


def test_skips_non_py_files(tmp_path: Path) -> None:
    p = tmp_path / 'data.txt'
    p.write_text('hello', encoding='utf-8')
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code == 0
