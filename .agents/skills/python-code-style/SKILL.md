---
name: python-code-style
description: >-
  Apply Douki Python conventions: strict typing, atpublic, @typechecked,
  Plum dispatch, Ruff, schema validation and security-quality tooling.
---

# Python implementation conventions for Douki

**Use for Python edits and reviews.** Apply
[minimal-change](../minimal-change/SKILL.md).

## Visibility and runtime checks

- Use `@public` / `@private` from `atpublic`.
- Import `@typechecked` from `douki.typechecking`, not raw
  `typeguard.typechecked`.
- Douki's wrapper checks all collection items and fails closed on forward refs.
- Strict mypy targets Python 3.10 and enables `check_untyped_defs`.
- Scripts are excluded. `introspection.py` and `helping.py` permit no-redef.

```python
from public import public

from douki.documentation import DocumentationError
from douki.typechecking import typechecked

@public
@typechecked
def require_name(name: str) -> str:
    """
    title: Validate a required name.
    parameters:
      name: Name supplied by the caller.
    returns: Validated, non-empty name.
    """
    if not name:
        raise DocumentationError('signature', 'Name cannot be empty')
    return name
```

## Formatting and dispatch

- Ruff 79 columns, single quotes.
- Lint rules: `E, F, YTT, RUF, I001, UP006, UP007`.
- Ruff formatting and `douki format` are pre-commit responsibilities.
- Use Plum dispatch in `helping.py` and `introspection.py`; every type-varying
  visitor should have a fail-closed fallback.
- Use `DocumentationError` for shared API failures and
  `DocstringValidationError` for source synchronization batches.
- Public exports are lazy in `src/douki/__init__.py`.

## Quality tools

- Bandit excludes `tests/`.
- Vulture excludes `tests/`, minimum confidence 80, `make_whitelist = true`.
- mccabe flags cyclomatic complexity >=10:
  `python -m mccabe --min 10`.

## Verification

```bash
poetry run makim tests.unit
poetry run makim tests.linter
poetry run douki format --check src tests benchmarks
poetry run douki check <changed-paths>
```

Repo-wide `douki check` can report pre-existing missing
attribute/parameter descriptions in existing `src/` and `tests/` files.
