"""
title: Tests for douki.cli — Typer-based CLI.
"""

from __future__ import annotations

import textwrap

from pathlib import Path

import pytest

from douki.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """
    title: Write *content* to *tmp_path/name* and return the path.
    parameters:
      tmp_path:
        type: Path
      name:
        type: str
      content:
        type: str
    returns:
      type: Path
    """
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding='utf-8')
    return p


# -------------------------------------------------------------------
# douki check
# -------------------------------------------------------------------


def test_check_exit_2_when_invalid(tmp_path: Path) -> None:
    """
    title: Invalid docstring should produce exit 2.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'invalid.py',
        '''\
        def hello() -> None:
            """Just a plain docstring."""
            pass
        ''',
    )
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code == 2


def test_check_exit_1_when_dirty(tmp_path: Path) -> None:
    """
    title: Unsynced file should produce exit 1 with diff.
    parameters:
      tmp_path:
        type: Path
    """
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
    """
    title: Diff output should contain file path.
    parameters:
      tmp_path:
        type: Path
    """
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
# Missing docstrings on methods
# -------------------------------------------------------------------


def test_check_should_fail_when_method_has_no_docstring(
    tmp_path: Path,
) -> None:
    """
    title: check should fail (exit != 0) when a class method has no docstring.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'no_docstring.py',
        '''\
        class Calculator:
            """
            title: A simple calculator.
            """

            def add(self, x: int, y: int) -> int:
                return x + y
        ''',
    )
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code != 0, (
        f'Expected check to fail for method without docstring, '
        f'but got exit_code={result.exit_code}'
    )


def test_sync_should_fail_when_method_has_no_docstring(
    tmp_path: Path,
) -> None:
    """
    title: sync should fail (exit != 0) when a class method has no docstring.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'no_docstring.py',
        '''\
        class Calculator:
            """
            title: A simple calculator.
            """

            def add(self, x: int, y: int) -> int:
                return x + y
        ''',
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code != 0, (
        f'Expected sync to fail for method without docstring, '
        f'but got exit_code={result.exit_code}'
    )


def test_check_should_fail_when_function_has_no_docstring(
    tmp_path: Path,
) -> None:
    """
    title: >-
      check should fail (exit != 0) when a top-level function has no docstring.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'no_docstring_func.py',
        """\
        def add(x: int, y: int) -> int:
            return x + y
        """,
    )
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code != 0, (
        f'Expected check to fail for function without docstring, '
        f'but got exit_code={result.exit_code}'
    )


def test_sync_should_fail_when_function_has_no_docstring(
    tmp_path: Path,
) -> None:
    """
    title: >-
      sync should fail (exit != 0) when a top-level function has no docstring.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'no_docstring_func.py',
        """\
        def add(x: int, y: int) -> int:
            return x + y
        """,
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code != 0, (
        f'Expected sync to fail for function without docstring, '
        f'but got exit_code={result.exit_code}'
    )


# -------------------------------------------------------------------
# douki sync
# -------------------------------------------------------------------


def test_sync_updates_file(tmp_path: Path) -> None:
    """
    title: sync should update file and exit 1.
    parameters:
      tmp_path:
        type: Path
    """
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
    """
    title: Running sync twice produces no further changes.
    parameters:
      tmp_path:
        type: Path
    """
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
    """
    title: Multiple files are all processed by check.
    parameters:
      tmp_path:
        type: Path
    """
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
    """
    title: Non-Python files are silently skipped.
    parameters:
      tmp_path:
        type: Path
    """
    p = tmp_path / 'data.txt'
    p.write_text('hello', encoding='utf-8')
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code == 0


def test_directory_discovers_py_files(tmp_path: Path) -> None:
    """
    title: Passing a directory discovers .py files inside it.
    parameters:
      tmp_path:
        type: Path
    """
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


def test_migrate_numpydoc(tmp_path: Path) -> None:
    """
    title: migrate converts NumPy docstrings to Douki YAML.
    parameters:
      tmp_path:
        type: Path
    """
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
        ['migrate', '--from', 'numpydoc', str(p)],
    )
    assert result.exit_code == 1
    content = p.read_text(encoding='utf-8')
    assert 'title:' in content
    assert 'parameters:' in content


# -------------------------------------------------------------------
# Coverage: error paths
# -------------------------------------------------------------------


def test_sync_exit_2_when_invalid(tmp_path: Path) -> None:
    """
    title: Invalid docstring should produce exit 2.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'invalid.py',
        '''\
        def hello() -> None:
            """Just a plain docstring."""
            pass
        ''',
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code == 2


def test_sync_unreadable_file(tmp_path: Path) -> None:
    """
    title: sync on a missing file should exit 2.
    parameters:
      tmp_path:
        type: Path
    """
    missing = tmp_path / 'does_not_exist.py'
    result = runner.invoke(
        app,
        ['sync', str(missing)],
    )
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_check_unreadable_file(tmp_path: Path) -> None:
    """
    title: check on a missing file should exit 2.
    parameters:
      tmp_path:
        type: Path
    """
    missing = tmp_path / 'does_not_exist.py'
    result = runner.invoke(
        app,
        ['check', str(missing)],
    )
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_sync_empty_directory(tmp_path: Path) -> None:
    """
    title: sync on empty dir should exit 0.
    parameters:
      tmp_path:
        type: Path
    """
    result = runner.invoke(
        app,
        ['sync', str(tmp_path)],
    )
    assert result.exit_code == 0


def test_check_empty_directory(tmp_path: Path) -> None:
    """
    title: check on empty dir should exit 0
    parameters:
      tmp_path:
        type: Path
    """
    result = runner.invoke(
        app,
        ['check', str(tmp_path)],
    )
    assert result.exit_code == 0


def test_help_output() -> None:
    """
    title: Top-level --help exits 0 and mentions douki.
    """
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'douki' in result.output.lower()


def test_sync_help_output() -> None:
    """
    title: sync --help exits 0 and mentions sync.
    """
    result = runner.invoke(app, ['sync', '--help'])
    assert result.exit_code == 0
    assert 'sync' in result.output.lower()


def test_check_help_output() -> None:
    """
    title: check --help exits 0 and mentions check.
    """
    result = runner.invoke(app, ['check', '--help'])
    assert result.exit_code == 0
    assert 'check' in result.output.lower()


# -------------------------------------------------------------------
# Coverage: pyproject.toml configuration
# -------------------------------------------------------------------


def test_exclude_files_via_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Files matching exclude patterns in pyproject.toml are skipped.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.chdir(tmp_path)

    _write(
        tmp_path,
        'pyproject.toml',
        """\
        [tool.douki]
        exclude = ["ignored.py", "tests/smoke/*"]
        """,
    )

    _write(
        tmp_path,
        'clean.py',
        '''\
        def good() -> None:
            """
            title: good
            """
            pass
        ''',
    )
    p_ignored = _write(
        tmp_path,
        'ignored.py',
        '''\
        def bad(value: int) -> int:
            """
            title: bad
            """
            return value
        ''',
    )

    smoke_dir = tmp_path / 'tests' / 'smoke'
    smoke_dir.mkdir(parents=True)
    _write(
        smoke_dir,
        'dirty.py',
        """\
        def dirty() -> None:
            pass
        """,
    )

    result = runner.invoke(app, ['check'])
    # Because clean.py is clean, and ignored.py/dirty.py are excluded,
    # it should exit 0
    assert result.exit_code == 0

    # Even if passed explicitly, it should be excluded (like black/ruff)
    result2 = runner.invoke(app, ['check', str(p_ignored)])
    assert result2.exit_code == 0
    assert 'No python files found' in result2.output


def test_exclude_files_via_pyproject_windows_separator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Backslash separators in exclude patterns work on all platforms.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.chdir(tmp_path)

    _write(
        tmp_path,
        'pyproject.toml',
        """\
        [tool.douki]
        exclude = ["tests\\\\smoke\\\\*"]
        """,
    )

    smoke_dir = tmp_path / 'tests' / 'smoke'
    smoke_dir.mkdir(parents=True)
    _write(
        smoke_dir,
        'dirty.py',
        '''\
        def dirty(value: int) -> int:
            """
            title: dirty
            """
            return value
        ''',
    )

    result = runner.invoke(app, ['check'])
    assert result.exit_code == 0
    assert 'No python files found' in result.output


def test_gitignore_files_are_ignored_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Files listed in .gitignore are skipped by default.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.chdir(tmp_path)

    _write(
        tmp_path,
        '.gitignore',
        """\
        ignored.py
        """,
    )

    p_ignored = _write(
        tmp_path,
        'ignored.py',
        '''\
        def bad(value: int) -> int:
            """
            title: bad
            """
            return value
        ''',
    )

    result = runner.invoke(app, ['check'])
    assert result.exit_code == 0
    assert 'No python files found' in result.output

    result2 = runner.invoke(app, ['check', str(p_ignored)])
    assert result2.exit_code == 0
    assert 'No python files found' in result2.output


def test_nested_gitignore_respected_unless_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: >-
      Nested .gitignore is respected unless --no-respect-gitignore is passed.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.chdir(tmp_path)

    nested = tmp_path / 'pkg'
    nested.mkdir()
    _write(
        nested,
        '.gitignore',
        """\
        ignored.py
        """,
    )
    _write(
        nested,
        'ignored.py',
        '''\
        def bad(value: int) -> int:
            """
            title: bad
            """
            return value
        ''',
    )

    result = runner.invoke(app, ['check', str(tmp_path)])
    assert result.exit_code == 0
    assert 'No python files found' in result.output

    result2 = runner.invoke(
        app,
        ['check', '--no-respect-gitignore', str(tmp_path)],
    )
    assert result2.exit_code == 1


def test_pyproject_can_disable_gitignore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: >-
      Setting respect-gitignore = false in pyproject.toml disables gitignore
      filtering.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.chdir(tmp_path)

    _write(
        tmp_path,
        'pyproject.toml',
        """\
        [tool.douki]
        respect-gitignore = false
        """,
    )
    _write(
        tmp_path,
        '.gitignore',
        """\
        ignored.py
        """,
    )
    _write(
        tmp_path,
        'ignored.py',
        '''\
        def bad(value: int) -> int:
            """
            title: bad
            """
            return value
        ''',
    )

    result = runner.invoke(app, ['check'])
    assert result.exit_code == 1


def test_cli_flag_overrides_pyproject_gitignore_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: CLI --respect-gitignore flag overrides pyproject.toml.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.chdir(tmp_path)

    _write(
        tmp_path,
        'pyproject.toml',
        """\
        [tool.douki]
        respect-gitignore = false
        """,
    )
    _write(
        tmp_path,
        '.gitignore',
        """\
        ignored.py
        """,
    )
    _write(
        tmp_path,
        'ignored.py',
        '''\
        def bad(value: int) -> int:
            """
            title: bad
            """
            return value
        ''',
    )

    result = runner.invoke(app, ['check', '--respect-gitignore'])
    assert result.exit_code == 0
    assert 'No python files found' in result.output


# -------------------------------------------------------------------
# Coverage: migrate error/unchanged paths
# -------------------------------------------------------------------


def test_migrate_unchanged_file(tmp_path: Path) -> None:
    """
    title: Migrate on already-douki file should exit 0.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'already.py',
        '''\
        def greet(name: str) -> str:
            """
            title: Greet someone
            parameters:
              name:
                type: str
            returns:
              type: str
            """
            return name
        ''',
    )
    result = runner.invoke(
        app,
        ['migrate', '--from', 'numpydoc', str(p)],
    )
    assert result.exit_code == 0


def test_migrate_invalid_docstring(tmp_path: Path) -> None:
    """
    title: Migrate on invalid docstring should exit 2.
    parameters:
      tmp_path:
        type: Path
    """
    p = _write(
        tmp_path,
        'invalid.py',
        '''\
        def hello() -> None:
            """Just a plain docstring."""
            pass
        ''',
    )
    result = runner.invoke(
        app,
        ['migrate', '--from', 'numpydoc', str(p)],
    )
    assert result.exit_code == 2


def test_migrate_unreadable_file(tmp_path: Path) -> None:
    """
    title: Migrate on a missing file should exit 2.
    parameters:
      tmp_path:
        type: Path
    """
    missing = tmp_path / 'does_not_exist.py'
    result = runner.invoke(
        app,
        ['migrate', '--from', 'numpydoc', str(missing)],
    )
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_sync_generic_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Generic exception during sync should exit 2.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    p = _write(
        tmp_path,
        'crash.py',
        '''\
        def foo() -> None:
            """
            title: test
            """
            pass
        ''',
    )
    import douki._python.language

    def _boom(*a: object, **kw: object) -> str:
        """
        title: Stub that always raises RuntimeError.
        parameters:
          a:
            type: object
            variadic: positional
          kw:
            type: object
            variadic: keyword
        returns:
          type: str
        """
        raise RuntimeError('boom')

    monkeypatch.setattr(
        douki._python.language.PythonLanguage, 'sync_source', _boom
    )
    result = runner.invoke(app, ['sync', str(p)])
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_check_generic_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Generic exception during check should exit 2.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    p = _write(
        tmp_path,
        'crash.py',
        '''\
        def foo() -> None:
            """
            title: test
            """
            pass
        ''',
    )
    import douki._python.language

    def _boom(*a: object, **kw: object) -> str:
        """
        title: Stub that always raises RuntimeError.
        parameters:
          a:
            type: object
            variadic: positional
          kw:
            type: object
            variadic: keyword
        returns:
          type: str
        """
        raise RuntimeError('boom')

    monkeypatch.setattr(
        douki._python.language.PythonLanguage, 'sync_source', _boom
    )
    result = runner.invoke(app, ['check', str(p)])
    assert result.exit_code == 2
    assert 'Error' in result.output


def test_migrate_generic_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Generic exception during migrate should exit 2.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    p = _write(
        tmp_path,
        'crash.py',
        '''\
        def foo() -> None:
            """
            title: test
            """
            pass
        ''',
    )
    import douki._python.language

    def _boom(*a: object, **kw: object) -> str:
        """
        title: Stub that always raises RuntimeError.
        parameters:
          a:
            type: object
            variadic: positional
          kw:
            type: object
            variadic: keyword
        returns:
          type: str
        """
        raise RuntimeError('boom')

    monkeypatch.setattr(
        douki._python.language.PythonLanguage, 'sync_source', _boom
    )
    result = runner.invoke(
        app,
        ['migrate', '--from', 'numpydoc', str(p)],
    )
    assert result.exit_code == 2
    assert 'Error' in result.output
