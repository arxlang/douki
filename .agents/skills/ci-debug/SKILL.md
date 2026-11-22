---
name: ci-debug
description: >-
  Investigate Douki GitHub Actions and Makim failures from the first meaningful
  error and apply the narrowest verified fix.
---

# Diagnose Douki CI failures

**Use for failed GitHub Actions jobs or Makim tasks.** Read the exact workflow,
job, step, SHA, log, Python version and OS before concluding cause.

## CI map

- Test matrix: Python 3.10-3.14 on Ubuntu, macOS and Windows.
- Linter: Ubuntu Python 3.10.
- ASV: Ubuntu Python 3.11.
- Release: Ubuntu Python 3.13 for semantic release.
- PR main must be up to date according to `gh-check-pr-is-updated`.

## Canonical checks

```bash
poetry check
poetry run makim tests.unit
poetry run makim tests.smoke
poetry run makim tests.linter
poetry run makim tests.ci
poetry run makim docs.build
poetry run makim package.build
poetry run douki format --check src tests benchmarks
poetry run douki check <changed-paths>
asv check -E existing
```

Use the targeted `douki check` on edited files. Repo-wide `douki check`
can report pre-existing missing attribute/parameter descriptions in existing
`src/` and `tests/` files.

## Failure map

| Failure | Investigate | Avoid |
| --- | --- | --- |
| Unit/coverage | focused test and 90% gate | weakening coverage |
| Smoke | CLI task and fixture file | hiding a migration/exit-code failure |
| Pre-commit | actual hook output | unrelated broad formatting |
| Mypy | strict mypy target (scripts excluded) | broad casts or ignores |
| Lockfile | manifest/lock agreement | manual lock edits |
| ASV | exact refs, ASV status and report | treating noise as regressions |
| Release/docs | workflow event, permissions and SHA | publishing or forcing refs |

Do not rerun indefinitely or suppress a hook. Report exact URL/job/SHA, first
error, evidence, minimal fix, commands and remaining uncertainty.
