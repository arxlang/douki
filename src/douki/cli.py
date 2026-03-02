"""Douki CLI — ``douki sync`` and ``douki check`` commands.

Usage::

    douki sync  [FILES...]   # apply changes in-place
    douki check [FILES...]   # print diff, exit 1 if changes needed
"""

from __future__ import annotations

import difflib
import fnmatch
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer

from rich.console import Console

from douki.sync import sync_source


class MigrateFormat(str, Enum):
    """Supported migration source formats."""

    numpy = 'numpy'


app = typer.Typer(
    name='douki',
    help='Douki — language-agnostic YAML docstring toolkit.',
    add_completion=False,
)

console = Console(stderr=True)
out_console = Console()  # stdout


@app.callback()
def _main() -> None:
    """Douki — language-agnostic YAML docstring toolkit."""


def _load_exclude_patterns(cwd: Path) -> List[str]:
    """Load exclude patterns from pyproject.toml in cwd or parents."""
    curr = cwd.resolve()
    while True:
        pyproject = curr / 'pyproject.toml'
        if pyproject.is_file():
            try:
                with pyproject.open('rb') as f:
                    data = tomllib.load(f)
                excludes = (
                    data.get('tool', {}).get('douki', {}).get('exclude', [])
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


def _is_excluded(path: Path, excludes: List[str]) -> bool:
    """Check if path matches any of the exclude patterns."""
    if not excludes:
        return False
    path_str = path.as_posix()
    for pattern in excludes:
        if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(
            path_str, f'*/{pattern}'
        ):
            return True
        if path_str.startswith(pattern.rstrip('/') + '/'):
            return True
    return False


def _collect_py_files(paths: List[Path], excludes: List[str]) -> List[Path]:
    """Expand directories to ``.py`` files and filter non-py and excluded."""
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


def _resolve_files(
    files: Optional[List[Path]],
) -> List[Path]:
    """Turn the optional argument into a list of .py paths."""
    excludes = _load_exclude_patterns(Path.cwd())
    raw = files if files else [Path('.')]
    py_files = _collect_py_files(raw, excludes)
    if not py_files:
        console.print('[dim]No .py files found.[/]')
        raise typer.Exit(code=0)
    return py_files


def _print_diff(
    path: Path,
    original: str,
    updated: str,
) -> bool:
    """Print a coloured unified diff.

    Return True if there is a diff.
    """
    if original == updated:
        return False

    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )

    for line in diff_lines:
        line = line.rstrip('\n')
        if line.startswith('+++') or line.startswith('---'):
            out_console.print(line, style='bold')
        elif line.startswith('@@'):
            out_console.print(line, style='cyan')
        elif line.startswith('+'):
            out_console.print(line, style='green')
        elif line.startswith('-'):
            out_console.print(line, style='red')
        else:
            out_console.print(line)

    return True


@app.command()
def sync(
    files: Optional[List[Path]] = typer.Argument(
        default=None,
        help='Python files or directories (default: ".").',
    ),
    migrate: Optional[MigrateFormat] = typer.Option(
        None,
        '--migrate',
        help='Migrate from another docstring format.',
    ),
) -> None:
    """Apply docstring sync changes to files in-place."""
    migrate_val = migrate.value if migrate else None
    py_files = _resolve_files(files)
    errors = False
    changed = 0
    unchanged = 0

    for filepath in py_files:
        try:
            original = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            console.print(
                f'[red]Error reading {filepath}:[/] {exc}',
            )
            errors = True
            continue

        try:
            updated = sync_source(
                original,
                migrate=migrate_val,
            )
        except Exception as exc:
            console.print(
                f'[red]Error processing {filepath}:[/] {exc}',
            )
            errors = True
            continue

        if original != updated:
            filepath.write_text(updated, encoding='utf-8')
            console.print(f'[green]Updated[/] {filepath}')
            changed += 1
        else:
            console.print(
                f'[dim]No changes[/] {filepath}',
            )
            unchanged += 1

    # Summary
    console.print()
    console.print(
        f'[bold]{changed} updated[/], {unchanged} unchanged',
    )

    if errors:
        raise typer.Exit(code=2)
    if changed:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@app.command()
def check(
    files: Optional[List[Path]] = typer.Argument(
        default=None,
        help='Python files or directories (default: ".").',
    ),
    migrate: Optional[MigrateFormat] = typer.Option(
        None,
        '--migrate',
        help='Migrate from another docstring format.',
    ),
) -> None:
    """Print a diff of proposed changes. Exit 1 if any."""
    migrate_val = migrate.value if migrate else None
    py_files = _resolve_files(files)
    any_diff = False
    errors = False

    for filepath in py_files:
        try:
            original = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            console.print(
                f'[red]Error reading {filepath}:[/] {exc}',
            )
            errors = True
            continue

        try:
            updated = sync_source(
                original,
                migrate=migrate_val,
            )
        except Exception as exc:
            console.print(
                f'[red]Error processing {filepath}:[/] {exc}',
            )
            errors = True
            continue

        if _print_diff(filepath, original, updated):
            any_diff = True

    if errors:
        raise typer.Exit(code=2)
    if any_diff:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


if __name__ == '__main__':
    app()
