"""Douki CLI — ``douki sync`` command.

Usage::

    douki sync FILE [FILE ...] [--diff | --apply]
"""

from __future__ import annotations

import difflib

from pathlib import Path
from typing import List

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


def _print_diff(path: Path, original: str, updated: str) -> bool:
    """Print a coloured unified diff. Return True if there is a diff."""
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
    files: List[Path] = typer.Argument(
        ...,
        help='Python files to synchronize.',
        exists=True,
        readable=True,
    ),
    diff: bool = typer.Option(
        False,
        '--diff',
        help='Print a unified diff; do not modify files.',
    ),
    apply: bool = typer.Option(
        False,
        '--apply',
        help='Write changes back to files in-place.',
    ),
) -> None:
    """Synchronize Douki YAML docstrings with function signatures."""
    if diff and apply:
        console.print(
            '[bold red]Error:[/] --diff and --apply are mutually exclusive.',
        )
        raise typer.Exit(code=2)

    # Default to diff mode when neither flag is given
    mode = 'apply' if apply else 'diff'

    # Sort for deterministic output
    sorted_files = sorted(set(files))

    any_diff = False
    errors = False

    for filepath in sorted_files:
        if filepath.suffix != '.py':
            console.print(
                f'[yellow]Skipping[/] {filepath} (not a .py file)',
            )
            continue

        try:
            original = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            console.print(f'[red]Error reading {filepath}:[/] {exc}')
            errors = True
            continue

        try:
            updated = sync_source(original)
        except Exception as exc:
            console.print(f'[red]Error processing {filepath}:[/] {exc}')
            errors = True
            continue

        if mode == 'diff':
            if _print_diff(filepath, original, updated):
                any_diff = True
        else:
            # apply mode
            if original != updated:
                filepath.write_text(updated, encoding='utf-8')
                console.print(f'[green]Updated[/] {filepath}')
            else:
                console.print(f'[dim]No changes[/] {filepath}')

    if errors:
        raise typer.Exit(code=2)

    if mode == 'diff' and any_diff:
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


if __name__ == '__main__':
    app()
