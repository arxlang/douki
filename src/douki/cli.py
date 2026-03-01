"""Douki CLI — ``douki sync`` and ``douki check`` commands.

Usage::

    douki sync  [FILES...]   # apply changes in-place
    douki check [FILES...]   # print diff, exit 1 if changes needed
"""

from __future__ import annotations

import difflib

from pathlib import Path
from typing import List, Optional

import typer

from rich.console import Console

from douki.sync import sync_source

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


def _collect_py_files(paths: List[Path]) -> List[Path]:
    """Expand directories to ``.py`` files and filter non-py."""
    result: List[Path] = []
    for p in paths:
        if p.is_dir():
            result.extend(sorted(p.rglob('*.py')))
        elif p.suffix == '.py':
            result.append(p)
    return sorted(set(result))


def _resolve_files(
    files: Optional[List[Path]],
) -> List[Path]:
    """Turn the optional argument into a list of .py paths."""
    raw = files if files else [Path('.')]
    py_files = _collect_py_files(raw)
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
) -> None:
    """Apply docstring sync changes to files in-place."""
    py_files = _resolve_files(files)
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
            updated = sync_source(original)
        except Exception as exc:
            console.print(
                f'[red]Error processing {filepath}:[/] {exc}',
            )
            errors = True
            continue

        if original != updated:
            filepath.write_text(updated, encoding='utf-8')
            console.print(f'[green]Updated[/] {filepath}')
        else:
            console.print(
                f'[dim]No changes[/] {filepath}',
            )

    if errors:
        raise typer.Exit(code=2)
    raise typer.Exit(code=0)


@app.command()
def check(
    files: Optional[List[Path]] = typer.Argument(
        default=None,
        help='Python files or directories (default: ".").',
    ),
) -> None:
    """Print a diff of proposed changes. Exit 1 if any."""
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
            updated = sync_source(original)
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
