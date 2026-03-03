# Douki

**Language-agnostic YAML docstrings for Python.**

Douki is a developer tool that uses a structured YAML format inside Python
docstrings. It keeps your docstrings in sync with your function signatures and
validates them against a schema — all without adding a runtime dependency to
your package.

## Why Douki?

- **Structured** — docstrings are YAML, not free-form text. Parameters have
  `type`, `description`, `optional`, and `default` fields.
- **Auto-synced** — `douki sync` adds new parameters, removes stale ones, and
  updates return types automatically.
- **Validated** — every docstring is checked against a JSON Schema so typos and
  invalid fields are caught early.
- **Dev-only** — Douki is a development tool. It does **not** need to be a
  runtime dependency of your package.
- **Migratable** — convert existing NumPy-style docstrings with
  `douki migrate numpydoc`.

## Quick Start

Install Douki as a dev dependency:

```bash
pip install douki
```

Write a docstring in Douki YAML format:

```python
def add(a: int, b: int = 0) -> int:
    """
    title: Add two integers
    parameters:
      a:
        type: int
        description: First value.
      b:
        type: int
        description: Second value.
        default: 0
    returns:
      type: int
      description: Sum of a and b.
    """
    return a + b
```

Sync your docstrings with the actual signatures:

```bash
# Preview changes
douki check src/

# Apply changes in-place
douki sync src/
```

## What's Next?

- [Installation](installation.md) — install via pip, conda, or from source
- [Usage Guide](usage.md) — CLI commands, YAML schema, and migration
- [Changelog](changelog.md) — release history
- [Contributing](contributing.md) — how to contribute
