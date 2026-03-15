"""
title: "Douki CLI \u2014 ``douki sync`` and ``douki check`` commands."
examples:
  - code: |
      douki sync  [FILES...]   # apply changes in-place
      douki check [FILES...]   # print diff, exit 1 if changes needed
"""

from __future__ import annotations

import difflib

from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer

from rich.console import Console

from douki.sync import (
    DocstringValidationError,
    resolve_files,
    sync_source,
)


class MigrateFormat(str, Enum):
    """
    title: Supported migration source formats.
    """

    numpydoc = 'numpydoc'


app = typer.Typer(
    name='douki',
    help='Douki — language-agnostic YAML docstring toolkit.',
    add_completion=False,
)

console = Console(stderr=True)
out_console = Console()  # stdout


@app.callback()
def _main() -> None:
    """
    title: Douki — language-agnostic YAML docstring toolkit.
    """


def _resolve_files(
    files: Optional[List[Path]],
    lang: str,
    respect_gitignore: Optional[bool],
) -> List[Path]:
    """
    title: Turn the optional argument into a list of paths for the language.
    parameters:
      files:
        type: Optional[List[Path]]
      lang:
        type: str
      respect_gitignore:
        type: Optional[bool]
    returns:
      type: List[Path]
    """
    target_files = resolve_files(
        files,
        lang=lang,
        respect_gitignore=respect_gitignore,
    )
    if not target_files:
        console.print(f'[dim]No {lang} files found.[/]')
        raise typer.Exit(code=0)
    return target_files


def _print_diff(
    path: Path,
    original: str,
    updated: str,
) -> bool:
    """
    title: Print a coloured unified diff.
    parameters:
      path:
        type: Path
      original:
        type: str
      updated:
        type: str
    returns:
      type: bool
      description: True if there is a diff.
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
        help='Files or directories (default: ".").',
    ),
    lang: str = typer.Option(
        'python',
        '--lang',
        help='Programming language to process (e.g. "python").',
    ),
    respect_gitignore: Optional[bool] = typer.Option(
        None,
        '--respect-gitignore/--no-respect-gitignore',
        help='Respect .gitignore patterns during file discovery.',
    ),
) -> None:
    """
    title: Apply docstring sync changes to files in-place.
    parameters:
      files:
        type: Optional[List[Path]]
      lang:
        type: str
      respect_gitignore:
        type: Optional[bool]
        optional: true
    """
    target_files = _resolve_files(
        files,
        lang=lang,
        respect_gitignore=respect_gitignore,
    )
    errors = False
    changed = 0
    unchanged = 0

    for filepath in target_files:
        try:
            original = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            console.print(
                f'[red]Error reading {filepath}:[/] {exc}',
            )
            errors = True
            continue

        try:
            updated = sync_source(original, lang=lang)
        except DocstringValidationError as exc:
            console.print(
                f'\n[red]Invalid docstrings in {filepath}:[/]\n{exc}',
            )
            errors = True
            continue
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
        help='Files or directories (default: ".").',
    ),
    lang: str = typer.Option(
        'python',
        '--lang',
        help='Programming language to process (e.g. "python").',
    ),
    respect_gitignore: Optional[bool] = typer.Option(
        None,
        '--respect-gitignore/--no-respect-gitignore',
        help='Respect .gitignore patterns during file discovery.',
    ),
) -> None:
    """
    title: Print a diff of proposed changes. Exit 1 if any.
    parameters:
      files:
        type: Optional[List[Path]]
      lang:
        type: str
      respect_gitignore:
        type: Optional[bool]
        optional: true
    """
    target_files = _resolve_files(
        files,
        lang=lang,
        respect_gitignore=respect_gitignore,
    )
    any_diff = False
    errors = False

    for filepath in target_files:
        try:
            original = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            console.print(
                f'[red]Error reading {filepath}:[/] {exc}',
            )
            errors = True
            continue

        try:
            updated = sync_source(original, lang=lang)
        except DocstringValidationError as exc:
            console.print(
                f'\n[red]Invalid docstrings in {filepath}:[/]\n{exc}',
            )
            errors = True
            continue
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


@app.command()
def migrate(
    files: Optional[List[Path]] = typer.Argument(
        default=None,
        help='Files or directories (default: ".").',
    ),
    from_format: MigrateFormat = typer.Option(
        ...,
        '--from',
        help='Source docstring format (e.g., numpydoc).',
    ),
    lang: str = typer.Option(
        'python',
        '--lang',
        help='Programming language to process (e.g. "python").',
    ),
    respect_gitignore: Optional[bool] = typer.Option(
        None,
        '--respect-gitignore/--no-respect-gitignore',
        help='Respect .gitignore patterns during file discovery.',
    ),
) -> None:
    """
    title: Migrate docstrings from another format to Douki YAML.
    parameters:
      files:
        type: Optional[List[Path]]
      from_format:
        type: MigrateFormat
      lang:
        type: str
      respect_gitignore:
        type: Optional[bool]
        optional: true
    """
    migrate_val = from_format.value
    target_files = _resolve_files(
        files,
        lang=lang,
        respect_gitignore=respect_gitignore,
    )
    errors = False
    changed = 0
    unchanged = 0

    for filepath in target_files:
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
                lang=lang,
                migrate=migrate_val,
            )
        except DocstringValidationError as exc:
            console.print(
                f'\n[red]Invalid docstrings in {filepath}:[/]\n{exc}',
            )
            errors = True
            continue
        except Exception as exc:
            console.print(
                f'[red]Error processing {filepath}:[/] {exc}',
            )
            errors = True
            continue

        if original != updated:
            filepath.write_text(updated, encoding='utf-8')
            console.print(f'[green]Migrated[/] {filepath}')
            changed += 1
        else:
            console.print(
                f'[dim]No changes[/] {filepath}',
            )
            unchanged += 1

    # Summary
    console.print()
    console.print(
        f'[bold]{changed} migrated[/], {unchanged} unchanged',
    )

    if errors:
        raise typer.Exit(code=2)
    if changed:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


if __name__ == '__main__':
    app()
