---
name: douki-docstrings
description: >-
  Write, validate, sync, format and migrate annotation-first Douki YAML
  docstrings with minimal source churn.
---

# Maintain Douki source contracts

**Use for docstrings, schema changes, enrichment or static sync.** Apply
[minimal-change](../minimal-change/SKILL.md).

## Authored source format

Python annotations supply types:

```python
def add(left: int, right: int = 0) -> int:
    """
    title: Add two integers.
    parameters:
      left: First addend.
      right: Optional second addend.
    returns: Sum of the addends.
    """
    return left + right
```

Rules:

- `title` is required.
- `parameters`, `attributes`, `returns`, `yields`, `receives`, `raises`,
  `warnings`, `examples`, and other fields follow `src/douki/schema.json`.
- `returns` prefers a plain string or `{description: ...}` block.
- `raises` and `warnings` are mappings; never use typed lists.
- Authored source must not contain `type:` fields.
- Void callables use `-> None`; implicit method receivers are omitted.
- Existing descriptions survive sync and enrichment.
- Nested `{description: ...}` mappings remain supported when extra fields such
  as `default` or `optional` are present.

## Enriched output

`douki.enrich`, `douki.getdoc`, and
`format_documentation(..., enriched=True)` may add generated `type:` fields.
This output is for inspection/rendering only; never write it back to source.

## Commands

```bash
poetry run douki format --check src tests benchmarks
poetry run douki check <changed-paths>
poetry run douki format src tests benchmarks
poetry run douki sync src
poetry run douki migrate --from numpydoc src
```

Repo-wide `douki check` can report pre-existing missing
attribute/parameter descriptions in existing `src/` and `tests/` files.

`sync` scaffolds missing names with `...` placeholders and reports stale names;
it does not store types. `format` changes presentation only. `migrate`
converts NumPy docstrings to Douki YAML.
