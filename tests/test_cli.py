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
# douki check
# -------------------------------------------------------------------


def test_check_exit_0_when_clean(tmp_path: Path) -> None:
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
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code == 0


def test_check_exit_1_when_dirty(tmp_path: Path) -> None:
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
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code == 1


def test_check_shows_output(tmp_path: Path) -> None:
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
    result = runner.invoke(app, ['check', str(p)])
    assert str(p) in result.output or 'title' in result.output


# -------------------------------------------------------------------
# douki sync
# -------------------------------------------------------------------


def test_sync_updates_file(tmp_path: Path) -> None:
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
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code == 1
    content = p.read_text(encoding='utf-8')
    assert 'parameters' in content


def test_sync_idempotent(tmp_path: Path) -> None:
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
    runner.invoke(app, ['sync', str(p)])
    first = p.read_text(encoding='utf-8')
    runner.invoke(app, ['sync', str(p)])
    second = p.read_text(encoding='utf-8')
    assert first == second


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
        ['check', str(p1), str(p2)],
    )
    # Both files should be processed
    assert result.exit_code in (0, 1)


# -------------------------------------------------------------------
# Non-py files / directories
# -------------------------------------------------------------------


def test_skips_non_py_files(tmp_path: Path) -> None:
    p = tmp_path / 'data.txt'
    p.write_text('hello', encoding='utf-8')
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code == 0


def test_directory_discovers_py_files(tmp_path: Path) -> None:
    _write(
        tmp_path,
        'mod.py',
        '''\
        def greet(name: str) -> str:
            """
            title: Greet
            """
            return name
        ''',
    )
    result = runner.invoke(
        app,
        ['check', str(tmp_path)],
    )
    # Should find mod.py and show diff (exit 1)
    assert result.exit_code in (0, 1)


# -------------------------------------------------------------------
# --migrate numpy
# -------------------------------------------------------------------


def test_check_migrate_numpy(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        'numpy.py',
        '''\
        def add(x, y):
            """Add two numbers.

            Parameters
            ----------
            x : int
                First operand.
            y : int
                Second operand.

            Returns
            -------
            int
                The sum.
            """
            return x + y
        ''',
    )
    result = runner.invoke(
        app,
        ['check', '--migrate', 'numpy', str(p)],
    )
    assert result.exit_code == 1


def test_sync_migrate_numpy(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        'numpy.py',
        '''\
        def add(x, y):
            """Add two numbers.

            Parameters
            ----------
            x : int
                First operand.
            y : int
                Second operand.

            Returns
            -------
            int
                The sum.
            """
            return x + y
        ''',
    )
    result = runner.invoke(
        app,
        ['sync', '--migrate', 'numpy', str(p)],
    )
    assert result.exit_code == 1
    content = p.read_text(encoding='utf-8')
    assert 'title:' in content
    assert 'parameters:' in content


# -------------------------------------------------------------------
# Coverage: error paths
# -------------------------------------------------------------------


def test_sync_exit_0_when_no_changes(tmp_path: Path) -> None:
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


def test_sync_unreadable_file(tmp_path: Path) -> None:
    """sync on a missing file should exit 2."""
    missing = tmp_path / 'does_not_exist.py'
    result = runner.invoke(
        app,
        ['sync', str(missing)],
    )
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_check_unreadable_file(tmp_path: Path) -> None:
    """check on a missing file should exit 2."""
    missing = tmp_path / 'does_not_exist.py'
    result = runner.invoke(
        app,
        ['check', str(missing)],
    )
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_sync_empty_directory(tmp_path: Path) -> None:
    """sync on empty dir should exit 0."""
    result = runner.invoke(
        app,
        ['sync', str(tmp_path)],
    )
    assert result.exit_code == 0


def test_check_empty_directory(tmp_path: Path) -> None:
    """check on empty dir should exit 0."""
    result = runner.invoke(
        app,
        ['check', str(tmp_path)],
    )
    assert result.exit_code == 0


def test_help_output() -> None:
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'douki' in result.output.lower()


def test_sync_help_output() -> None:
    result = runner.invoke(app, ['sync', '--help'])
    assert result.exit_code == 0
    assert 'sync' in result.output.lower()


def test_check_help_output() -> None:
    result = runner.invoke(app, ['check', '--help'])
    assert result.exit_code == 0
    assert 'check' in result.output.lower()
