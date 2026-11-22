---
name: release-check
description: >-
  Review Douki semantic-release readiness and workflows without publishing,
  tagging or changing release state.
---

# Review Douki release readiness

**Use for packaging or release-workflow questions.** This skill never
publishes, tags or creates release commits without explicit authorization.

## Evidence

- `.releaserc.json`
- `pyproject.toml`
- `docs/changelog.md`
- `poetry.lock`
- `.github/workflows/release.yaml`
- `.github/workflows/docs.yaml`
- `.makim.yaml`

## Checklist

1. Confirm `.releaserc.json` updates `src/douki/__init__.py`, `pyproject.toml`
   and `docs/changelog.md`.
2. Confirm wheel/sdist assets and release commit assets remain consistent.
3. Normal PR/push release events run `release.dry`; live publication is manual
   `workflow_dispatch` only.
4. Release workflow runs Python 3.13 and docs workflow can publish Pages.
5. If lockfiles changed, use `poetry check --lock`; never hand-edit lockfiles.

Canonical checks:

```bash
poetry check
poetry run makim tests.unit
poetry run makim tests.smoke
poetry run makim tests.linter
poetry run makim docs.build
poetry run makim package.build
poetry run makim release.dry
```

Do not run `release.ci` or publish without explicit authorization.
