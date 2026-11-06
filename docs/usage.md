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
mappings with `description`, `type`, `default`, `optional` and `variadic`.
Types are optional. The shipped `douki/schema.json` defines all supported
fields, including `attributes`, `raises`, `yields`, `examples` and `notes`.
Use plain parameter names for variadics (`args`, not `*args`).

## Formatting and validation

```bash
douki check src/     # Preview formatting differences
douki sync src/      # Apply formatting
douki check         # Discover Python files in the current directory
```

`sync` normalizes YAML formatting without copying types from annotations
into the file. It preserves authored fields, including explicit types,
empty entries, null defaults and multiline examples. It does not add or
remove parameter or attribute entries, even after a signature changes.
The enrichment API reports unknown documented parameters when those
objects are inspected.

| Exit code | Meaning |
| --- | --- |
| 0 | No changes needed |
| 1 | Formatting differs (`check`) or was updated (`sync`) |
| 2 | Invalid docstrings or another processing error |

Migrating from earlier Douki releases: existing expanded docstrings remain
valid. Remove redundant `type` fields when you want annotations to be the
only authored type information. `sync` will not reinsert them. The explicit
`douki.sync.sync_docstring` API retains its legacy expansion behavior for
existing consumers; source formatting no longer calls that API.

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
Generator return annotations describe the returned iterator; `yields` and
`receives` descriptions/types are preserved as authored.

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
text = format_documentation(data)
```

`data` is a validated documentation mapping that renderers can consume
directly. Annotations take precedence over explicit types; unannotated
parameters keep authored types. Descriptions and other metadata survive
enrichment. Unknown documented parameters and duplicate signature names
raise `DocumentationError` with a processing phase. Invalid metadata types
raise Typeguard errors, including invalid items later in a collection.

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

Migration converts authored NumPy-style documentation into YAML and keeps
its documented types. It does not import the project or infer missing
annotation types. Follow with `douki check src/`.

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
