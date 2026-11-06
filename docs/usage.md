# Usage

## Authoring

Put types in annotations and descriptions in Douki YAML:

```python
def greet(name: str, times: int = 1) -> str:
    """
    title: Greet someone.
    parameters:
      name: Person to greet.
      times: Number of greetings.
    returns:
      description: The greeting text.
    """
    return "\n".join([f"Hello, {name}!"] * times)
```

A `title` is required. Parameter entries can be description strings or
mappings with `description`, `default`, `optional` and `variadic`.
Authored `type` fields are forbidden. The shipped `douki/schema.json` defines
all supported
fields, including `attributes`, `raises`, `yields`, `examples` and `notes`.
Use plain parameter names for variadics (`args`, not `*args`).

## Formatting and validation

```bash
douki check src/     # Preview formatting differences
douki sync src/      # Apply formatting
douki check         # Discover Python files in the current directory
```

`sync` normalizes YAML formatting without copying types from annotations
into the file. It preserves authored fields, including descriptions,
empty entries, null defaults and multiline examples. It does not add or
remove parameter or attribute entries, even after a signature changes.
The enrichment API reports unknown documented parameters when those
objects are inspected. Both source checks and enrichment require annotations
for every parameter (including undocumented parameters and variadics) and
every callable's return value. Use `-> None` when a function returns nothing.
Only the actual method receiver is exempt; a static method's first argument
still requires an annotation, even when named `self` or `cls`.

Documented attributes require annotation metadata too. Class and module
annotations and property getter return annotations supply these types.
Source checks also validate instance fields collected from `__init__`.
Declare instance attributes at class scope when runtime help must find them:

```python
class Counter:
    """
    title: A counter.
    attributes:
      count: Current value.
    """
    count: int

    def __init__(self) -> None:
        """title: Initialize the counter."""
        self.count = 0
```

An annotation only inside a method is not retained in the class's runtime
metadata. Douki does not guess types from attribute values or instantiate
classes to discover fields. Static adapters must supply inherited attribute
annotations; the Python CLI resolves inheritance from earlier same-file
classes, not imported bases. An explicit local annotation avoids ambiguity.
Validation requires annotation presence, not proof of type correctness;
use a type checker such as mypy for that.

| Exit code | Meaning |
| --- | --- |
| 0 | No changes needed |
| 1 | Formatting differs (`check`) or was updated (`sync`) |
| 2 | Invalid docstrings or another processing error |

Migrating from earlier Douki releases: remove `type` fields from parameters,
attributes, returns, yields and receives, and add any missing annotations.
Expanded docstrings from older releases are no longer valid source input.
Neither `sync` nor `check` silently discards those fields. Replace typed
lists in `raises` and `warnings` with mappings, for example
`raises: {ValueError: Invalid value.}`. Exception and warning names remain
authored because Python has no corresponding declaration annotations.

The explicit `douki.sync.sync_docstring` API still generates expanded output
from annotation metadata for legacy consumers. Its input must follow the
source schema, and supplied parameters and attributes must be annotated.
An empty parameter list and empty return annotation represent a non-callable
declaration in that legacy API; use `Signature` for an unambiguous contract.
Expanded output is a rendered view, not valid source input for a second pass.

## Dynamic help

```python
import douki

text = douki.getdoc(greet)
douki.help(greet)

# Optional: use the normal help name for this session.
douki.setup()
help(greet)
douki.restore_help()
```

`getdoc` returns enriched YAML for Douki docstrings, ordinary cleaned text
for other docstrings, and `None` when documentation is absent. It never
changes `__doc__`, annotations or function identity. Repeated calls derive
the result from current metadata, so no cached types become stale.

`setup` is explicit, idempotent and session-wide. `restore_help` reinstates
the previous helper, unless another tool has since replaced it. Importing
Douki alone does not install anything. `help()` with no argument and string
requests such as `help("keywords")` retain Python's ordinary interface;
that interactive topic session does not automatically enrich its requests.
Call `help(object)` for enriched object documentation.

Class and module help includes members; property getters are never called.
Module `__all__` exports are respected. Plum dispatch implementations retain
separate types. On Python 3.11+, registered `typing.overload` declarations
also retain separate types, inheriting implementation prose when needed.
On Python 3.10 only the runtime implementation signature is available for
`typing.overload`. `getdoc` separates multiple variants with YAML `---`
document separators.

Python 3.10–3.13 use unevaluated string annotations when present; Python
3.14 uses annotationlib's string format. Douki does not call
`typing.get_type_hints` to resolve missing type-only imports. Runtime
inspection is for code already imported in the current interpreter.
Generator return annotations describe the returned iterator, including its
yield/send types when supplied through `Generator` or `AsyncGenerator`.
The `yields` and `receives` sections contain descriptions only; Douki does
not decompose the generator annotation into separate fields.

## Static documentation generators

The shared API accepts strings and typed metadata. An adapter such as
DoukiMD's Griffe collector can supply this without importing project code:

```python
from douki import Parameter, Signature, enrich, format_documentation

signature = Signature(
    parameters=(Parameter("name", "str"), Parameter("times", "int")),
    returns="str",
)
data = enrich(
    "title: Greet someone\nparameters:\n  name: Person to greet.\n",
    signature,
)
text = format_documentation(data, enriched=True)
```

`data` is a validated documentation mapping that renderers can consume
directly. Types come exclusively from annotations. Descriptions and other
metadata survive enrichment. Missing annotations raise `DocumentationError`
with phase `annotations`, listing all missing fields for that declaration.
Unknown documented parameters and duplicate signature names
raise `DocumentationError` with a processing phase. Invalid metadata types
raise Typeguard errors, including invalid items later in a collection.
`format_documentation` validates source YAML by default; `enriched=True`
explicitly permits generated type fields. The generated view must not be
written back into source or passed back into `enrich` as authored input.
`validate_annotations(signature, documentation)` exposes the same presence
checks for adapters that already hold schema-validated documentation.

Use `parameters=None` for non-callable declarations, `parameters=()` for a
function with no arguments, and `attributes=(Parameter(...), ...)` for
class/module attributes. Adapters supply each overload separately and omit
implicit receivers. `kind` accepts `regular`, `positional_only`,
`keyword_only`, `var_positional` and `var_keyword`.

This API enables a DoukiMD integration; installing this Douki version does
not by itself change DoukiMD's collector.

## Migration

```bash
douki migrate --from numpydoc src/
```

Migration converts NumPy-style descriptions into type-free YAML. Add Python
annotations first: migration never invents them from prose and fails without
writing the affected file when annotations are missing. It preserves
exception/warning names as mapping keys. Follow with `douki check src/`.

## Configuration

You can configure Douki using a `pyproject.toml` file in your project root.
Douki supports excluding files or directories using glob patterns, and it
respects `.gitignore` during file discovery by default.

```toml
[tool.douki]
# Respect `.gitignore` by default. Set to false to opt out globally.
respect-gitignore = true

# Exclude specific files or entire directories
exclude = [
  "tests/smoke/*",
  "legacy_module.py"
]
```

When running `douki sync`, `douki check`, or `douki migrate`, any file
matching these patterns will be ignored. You can override the `.gitignore`
setting for a single run with `--respect-gitignore` or
`--no-respect-gitignore`.

---

## Pre-commit integration

With Douki installed in your development environment:

```yaml
repos:
  - repo: local
    hooks:
      - id: douki
        name: Format Douki docstrings
        entry: douki sync
        language: system
        types: [python]
```

Use `douki check` instead when the hook should report differences without
writing files.
