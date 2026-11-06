# Douki

**YAML docstrings with types supplied by annotations.**

Write descriptions in your docstrings and types in Python annotations.
Douki enriches documentation when you inspect it, while its CLI validates
and formats the YAML in your source files.

```python
def add(a: int, b: int = 0) -> int:
    """
    title: Add two integers.
    parameters:
      a: First value.
      b: Second value.
    returns: Sum of a and b.
    """
    return a + b
```

## Inspect documentation

```python
import douki

print(douki.getdoc(add))  # YAML with inferred parameter and return types

douki.help(add)          # Display enriched help

douki.enable()           # Opt in for this interpreter session
help(add)                # Now uses Douki for Douki-documented objects

douki.disable()          # Restore the previous helper
```

No per-function decorator is required. Importing Douki does not change
Python's help system. The original `add.__doc__` remains authored text.
Ordinary Python objects and help topics retain the standard help interface.

## Format and validate source

```bash
pip install douki

douki check src/  # Report formatting differences and schema errors
douki sync src/   # Apply YAML formatting
```

`check` and `sync` require annotations for parameters, return values and
documented attributes. Use `-> None` for functions without a result;
implicit method receivers are exempt. Authored `type` fields are rejected
by the schema. Remove only those fields from existing docstrings and put
types in annotations instead. Keep `parameters`, `returns` and `attributes`
with their descriptions: annotations supply types, not explanations.

`sync` formats YAML without inserting annotation types or changing parameter
entries. It preserves descriptions, examples and explicit null defaults.
Dynamic inspection raises `DocumentationError` for missing annotations.

The CLI can remain a development dependency. Install Douki in the running
interpreter when using `getdoc`, `help` or `enable`.

Documentation generators can use the public `enrich`, `Signature` and
`Parameter` API with statically collected types, without importing the
project being documented. See the [usage guide](usage.md).

Douki respects `.gitignore` by default. Override it with
`--no-respect-gitignore` or `[tool.douki] respect-gitignore = false`.

- [Installation](installation.md)
- [Usage guide](usage.md)
- [Performance benchmarks](performance.md)
- [Changelog](changelog.md)
- [Contributing](contributing.md)
