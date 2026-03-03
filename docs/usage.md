# Usage Guide

## CLI Commands

Douki provides two commands: `sync` and `check`.

### `douki sync`

Applies changes to your Python files in-place. Adds missing parameters,
removes stale ones, and updates return types.

```bash
# Sync all .py files in src/
douki sync src/

# Sync specific files
douki sync src/mymodule.py

# Sync current directory (default)
douki sync
```

**Exit codes:**

| Code | Meaning            |
| ---- | ------------------ |
| `0`  | No changes needed  |
| `1`  | Files were updated |
| `2`  | Errors occurred    |

### `douki check`

Prints a unified diff of proposed changes **without** modifying files.
Ideal for CI pipelines and pre-commit hooks.

```bash
# Check all .py files in src/
douki check src/

# Check current directory (default)
douki check
```

**Exit codes:**

| Code | Meaning                              |
| ---- | ------------------------------------ |
| `0`  | No changes needed                    |
| `1`  | Diffs exist (files would be changed) |
| `2`  | Errors occurred                      |

---

## Douki YAML Schema

Douki docstrings are YAML blocks inside triple-quoted strings. Every
docstring **must** have a `title` field.

### Minimal Example

```python
def greet(name: str) -> str:
    """
    title: Greet someone by name
    """
    return f"Hello {name}"
```

Running `douki sync` will automatically fill in the `parameters` and
`returns` sections based on the function signature.

### Full Example

```python
def add(a: int, b: int = 0) -> int:
    """
    title: Add two integers
    summary: |
      Returns the arithmetic sum of two values.
    parameters:
      a:
        type: int
        description: First value.
      b:
        type: int
        description: Second value.
        optional: true
        default: 0
    returns:
      type: int
      description: Sum of a and b.
    raises:
      - type: ValueError
        description: If either value is negative.
    examples:
      - code: |
          add(1, 2)  # -> 3
    notes: This is a trivial example.
    """
    if a < 0 or b < 0:
        raise ValueError
    return a + b
```

### Classes and Methods

Douki fully supports synchronizing docstrings for methods and classes.
When synchronizing a class docstring, Douki will automatically extract the parameters of the class's `__init__` method and add them to the class docstring's `parameters` section. Methods (including nested methods and `@classmethod`) are fully supported and will have their `parameters` and `returns` sections synchronized.

### All Fields

| Field        | Type                 | Description                                          |
| ------------ | -------------------- | ---------------------------------------------------- |
| `title`      | `string`             | **Required.** Short title for the function.          |
| `summary`    | `string`             | Extended description. Supports multi-line with `\|`. |
| `deprecated` | `string`             | Deprecation notice.                                  |
| `visibility` | `enum`               | `public` · `private` · `protected` · `internal`      |
| `mutability` | `enum`               | `mutable` · `immutable` · `constant`                 |
| `scope`      | `enum`               | `instance` · `static` · `class`                      |
| `parameters` | `object`             | Map of parameter name → entry (see below).           |
| `returns`    | `object` or `string` | Single `{type, description}` or plain text.          |
| `yields`     | `object` or `string` | Like `returns`, for generators.                      |
| `receives`   | `object` or `string` | Like `returns`, for generators.                      |
| `raises`     | `list` or `object`   | List of `{type, description}` or dict map.           |
| `warnings`   | `list` or `object`   | List of `{type, description}` or dict map.           |
| `see_also`   | `string` or `list`   | Related functions or references.                     |
| `notes`      | `string`             | Additional notes.                                    |
| `references` | `string`             | External references or citations.                    |
| `examples`   | `string` or `list`   | Usage examples.                                      |
| `attributes` | `object`             | For classes: map of attribute name → entry.          |
| `methods`    | `string` or `list`   | For classes: method names.                           |

### Parameter Entry

Each parameter can be a simple string (description only) or a structured
object:

```yaml
parameters:
  name:
    type: str
    description: The person's name.
    optional: true
    default: "World"
```

| Sub-field     | Type      | Description                                                                          |
| ------------- | --------- | ------------------------------------------------------------------------------------ |
| `type`        | `string`  | Type annotation (informational).                                                     |
| `description` | `string`  | Description of the parameter.                                                        |
| `optional`    | `boolean` | Whether the parameter is optional.                                                   |
| `default`     | `any`     | Default value.                                                                       |
| `variadic`    | `enum`    | `positional` (for `*args`) · `keyword` (for `**kwargs`). Omitted for regular params. |

#### Variadic Parameters

For `*args` and `**kwargs`, use the plain parameter name as the key
and set the `variadic` attribute:

```yaml
parameters:
  args:
    type: int
    variadic: positional
  kwargs:
    type: str
    variadic: keyword
```

### Python Defaults

For Python projects, fields are **omitted** when they match their defaults
to keep output minimal:

| Field        | Default                                     | When omitted             |
| ------------ | ------------------------------------------- | ------------------------ |
| `visibility` | `public`                                    | Almost always for Python |
| `mutability` | `mutable`                                   | Almost always for Python |
| `scope`      | `static` (functions) / `instance` (methods) | Almost always            |
| `optional`   | `null`                                      | When not explicitly set  |
| `default`    | `null`                                      | When not explicitly set  |
| `variadic`   | `null`                                      | When not explicitly set  |

---

## Migration

### From NumPy-style Docstrings

Douki can convert NumPy-style docstrings to Douki YAML format:

```bash
# Preview what the migration would look like
douki check src/

# Apply the migration using the new dedicated command
douki migrate numpydoc src/
```

**Before:**

```python
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
```

**After:**

```python
def add(x, y):
    """
    title: Add two numbers
    parameters:
      x:
        type: int
        description: First operand.
      y:
        type: int
        description: Second operand.
    returns:
      type: int
      description: The sum.
    """
    return x + y
```

---

## Configuration

You can configure Douki using a `pyproject.toml` file in your project root. Currently, Douki supports excluding files or directories using glob patterns.

```toml
[tool.douki]
# Exclude specific files or entire directories
exclude = [
  "tests/smoke/*",
  "legacy_module.py"
]
```

When running `douki sync` or `douki check`, any file matching these patterns will be ignored.

---

## Pre-commit Integration

Add Douki as a pre-commit hook to catch docstring issues automatically:

### Check mode (recommended for CI)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/osl-incubator/douki
    rev: v0.7.0
    hooks:
      - id: douki-check
        name: douki check
        entry: douki check
        language: python
        types: [python]
```

### Sync mode (auto-fix)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/osl-incubator/douki
    rev: v0.7.0
    hooks:
      - id: douki-sync
        name: douki sync
        entry: douki sync
        language: python
        types: [python]
```
