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
    returns:
      description: Sum of a and b.
    """
    return a + b
```

## Inspect documentation

```python
import douki

print(douki.getdoc(add))  # YAML with inferred parameter and return types

douki.help(add)          # Display enriched help

douki.setup()            # Opt in for this interpreter session
help(add)                # Now uses Douki for Douki-documented objects

douki.restore_help()     # Restore the previous helper
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

`sync` does not insert annotation types, add or remove parameter entries,
or overwrite authored types. Existing explicit types remain valid; they
can be removed when the signature supplies them. Formatting preserves the
YAML values, including descriptions, examples and explicit null defaults.

The CLI can remain a development dependency. Install Douki in the running
interpreter when using `getdoc`, `help` or `setup`.

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
