---
name: testing-standards
description: >-
  Select and reuse existing Douki tests, adding only distinct necessary
  coverage and targeted verification.
---

# Select meaningful Douki test coverage

**Use whenever adding, changing or reviewing tests.** Apply
[minimal-change](../minimal-change/SKILL.md).

## Pre-test audit

1. Search `tests/test_*.py`, fixtures and smoke files for the invariant.
2. Extend the closest test if one case/assertion proves the defect.
3. Add a new test only for a distinct stage or failure mode.
4. Prefer AST/extractor/base/schema tests before CLI integration duplication.

## Test map

| Area | Preferred coverage |
| --- | --- |
| Schema/annotations | `tests/test_validation.py`, `tests/test_annotations.py` |
| Static enrichment | `tests/test_documentation.py` |
| AST extraction/sync | `tests/test_sync.py` |
| CLI/discovery | `tests/test_cli.py`, `tests/test_performance_optimizations.py` |
| Runtime help/registration | `tests/test_helping.py`, `tests/test_registration.py` |
| Migration | `tests/test_migrate.py` |
| Benchmarks/report | `tests/test_benchmarks.py`, `tests/test_benchmark_report.py` |
| Smoke fixtures | `tests/smoke/*` |

## Verification

```bash
poetry run makim tests.unit
poetry run makim tests.smoke
poetry run makim tests.linter
poetry run makim tests.ci
poetry run douki format --check src tests benchmarks
poetry run douki check <changed-paths>
asv check -E existing
```

Repo-wide `douki check` can report pre-existing missing
attribute/parameter descriptions in existing `src/` and `tests/` files.

`tests.unit` requires 90% coverage. Coverage alone does not prove behavioral
correctness.
