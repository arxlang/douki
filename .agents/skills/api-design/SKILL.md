---
name: api-design
description: >-
  Design minimal, consistent Douki Python APIs, CLI commands, language plugins,
  runtime help, static enrichment, and migration contracts.
---

# Design one coherent Douki API

**Use for public Python functions/classes, CLI commands, language plugins,
signatures, enrichment or migration behavior.** Apply
[minimal-change](../minimal-change/SKILL.md) and
[python-code-style](../python-code-style/SKILL.md).

## API design steps

1. Locate the nearest implementation and inspect real callers:
   - Public: `src/douki/__init__.py`, `cli.py`, `sync.py`, `migrate.py`,
     `documentation.py`, `helping.py`, `introspection.py`
   - Core: `_base/config.py`, `_base/language.py`, `_base/sync.py`,
     `_base/validation.py`
   - Python: `_python/extractor.py`, `_python/sync.py`, `_python/migrate.py`
2. Start with common usage and one meaningful invalid/boundary case.
3. Keep CLI parsing in `cli.py`, AST extraction in `_python/extractor.py`,
   YAML merge/sync behavior in `_base/sync.py`, and runtime adaptation in
   `introspection.py`.
4. Specify parameter/return types, descriptions, missing-annotation behavior,
   phase-specific errors, mutations, and exit codes.
5. Preserve the annotation-first split:
   - authored YAML: title, prose, metadata, no `type:` fields
   - enriched output: generated `type:` fields only
6. Preserve lazy public exports and explicit `@public` / `@private` visibility.

## Anti-patterns

| Avoid | Prefer |
| --- | --- |
| YAML `type:` fields as source metadata | Python annotations |
| Generic exceptions | `DocumentationError` or `DocstringValidationError` |
| Late AST rewriting in CLI code | `_python/extractor.py` and `_python/sync.py` |
| Runtime introspection that imports source | Static signatures and non-mutating `getdoc` |
| New language-specific global behavior | Registered `BaseLanguage` plugins |

Verify common usage, invalid metadata, missing annotations, and one distinct
cross-stage boundary.
