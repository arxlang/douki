---
name: minimal-change
description: >-
  Keep Douki changes and PRs minimal without compromising correctness,
  coverage, source safety or benchmark compatibility.
---

# Minimal necessary change

**Use for every implementation, plan, test, review or documentation task.**---
name: minimal-change
description: >-
  Keep Douki changes and PRs minimal without compromising correctness,
  coverage, source safety or benchmark compatibility.
---

# Minimal necessary change

**Use for every implementation, plan, test, review or documentation task.**

## First establish the change

1. Read the request and current behavior.
2. Inspect only relevant source, tests, scripts, benchmarks and workflows.
3. Reuse existing AST, schema, plugin, formatting and runtime helpers.
4. Identify the smallest existing test or Makim task that proves the behavior.

## Decision table

| Proposed change | Normally do | Expand only when |
| --- | --- | --- |
| Rename | Preserve it | Meaning or correctness requires it |
| Restructure | Keep local structure | Current ownership prevents correctness |
| Add helper | Reuse direct code | Real callers need it |
| Add test | Search existing tests first | Distinct behavior lacks coverage |
| Add docs | Update existing page | Public behavior needs it |
| Change CI/dependency | Usually avoid | Delivery or verification requires it |

## Invariants

- Keep authored YAML free of `type:` fields.
- Preserve reverse-line AST rewrites and idempotence.
- Never mutate `__doc__` in `getdoc` or `help`.
- Keep `register()` package-scoped and foreign objects standard.
- Preserve 90% coverage and the ASV base/head compatibility rules.
- Do not replace or duplicate benchmark baseline definitions casually.
- Do not edit `poetry.lock` solely for ASV.

Stop when the requested behavior works and relevant checks pass or blockers are
explicit. Remove incidental formatting and documentation.


## First establish the change

1. Read the request and current behavior.
2. Inspect only relevant source, tests, scripts, benchmarks and workflows.
3. Reuse existing AST, schema, plugin, formatting and runtime helpers.
4. Identify the smallest existing test or Makim task that proves the behavior.

## Decision table

| Proposed change | Normally do | Expand only when |
| --- | --- | --- |
| Rename | Preserve it | Meaning or correctness requires it |
| Restructure | Keep local structure | Current ownership prevents correctness |
| Add helper | Reuse direct code | Real callers need it |
| Add test | Search existing tests first | Distinct behavior lacks coverage |
| Add docs | Update existing page | Public behavior needs it |
| Change CI/dependency | Usually avoid | Delivery or verification requires it |

## Invariants

- Keep authored YAML free of `type:` fields.
- Preserve reverse-line AST rewrites and idempotence.
- Never mutate `__doc__` in `getdoc` or `help`.
- Keep `register()` package-scoped and foreign objects standard.
- Preserve 90% coverage and the ASV base/head compatibility rules.
- Do not replace or duplicate benchmark baseline definitions casually.
- Do not edit `poetry.lock` solely for ASV.

Stop when the requested behavior works and relevant checks pass or blockers are
explicit. Remove incidental formatting and documentation.
