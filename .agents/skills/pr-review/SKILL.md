---
name: pr-review
description: >-
  Review Douki PRs or local diffs for correctness, scope, source safety,
  schema compatibility, tests and benchmark impact.
---

# Review a Douki pull request

**Use for PR, branch or local-diff review.** It is read-only unless the user
explicitly asks to submit a review or edit code. Apply
[minimal-change](../minimal-change/SKILL.md).

## Inputs

- Inspect exact base/head SHAs, diff, commits, body, comments and CI.
- For local work, inspect status, staged and uncommitted changes separately.
- Never claim CI or coverage passed without evidence.

## Read and reason

1. State the intended contract and affected boundary.
2. Trace public API/CLI, `_base`, `_python`, static enrichment, runtime help,
   benchmarks and release workflows.
3. Probe annotation-first schema, missing annotations, stale names, AST reverse
   rewrites, `getdoc`/`help` mutation, registration boundaries, gitignore
   discovery and migration compatibility.
4. Compare tests against existing parametrized matrices.
5. Check ASV compatibility and the benchmark's status against both revisions.

## Severity

- P0/P1: source mutation, foreign package help mutation, schema breakage,
  incorrect CLI/write behavior or unsafe benchmark/release behavior.
- P2: reproducible sync/check/migration/help regression or essential missing test.
- Non-blocking: narrow maintainability or scope reduction.

Each finding needs location, impact, evidence and a minimal correction.

```markdown
## Blocking findings

- [P1] <finding> — path:line Contract / impact / evidence / correction

## Non-blocking

- <only useful follow-up>

## Verification

- Confirmed: <actual evidence>
- Not verified: <specific risk>

## Recommendation

Request changes / No blockers / Unable to conclude
```
