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

Register the library once in its `__init__.py`:

```python
# mylib/__init__.py
import douki

douki.register(__name__)
```

Users then call ordinary Python help:

```python
import mylib

help(mylib.add)  # Douki descriptions enriched with annotation types
help(len)        # Regular Python help
```

Registration covers the package and its submodules, including future imports.
Objects defined in other libraries retain regular help, even when re-exported
by your package. No per-function decorators or user activation calls are needed.
The shared help wrapper routes by defining package; importing Douki alone does
not install it. Original `__doc__` strings remain authored text.

Tools can call `douki.getdoc(add)` directly without registration to obtain
enriched YAML. Documentation generators can also use the static enrichment API.

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
interpreter when using `getdoc`, `help` or library registration.

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
