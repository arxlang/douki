---
name: open-pr
description: >-
  Open or update a scoped arxlang/douki pull request with a Conventional Commit
  title and repository PR-template checks.
---

# Open or update a Douki PR

**Use only when explicitly asked to create, push, open or update a PR.** Apply
[minimal-change](../minimal-change/SKILL.md) and
[pr-review](../pr-review/SKILL.md). Never infer authority to merge, publish,
tag or force-push.

## Preflight

1. Identify upstream `arxlang/douki`, the requested fork, branch, base and SHA.
2. Confirm the PR branch is current with upstream `main`; Douki's
   `check-branch` workflow requires a rebased/current branch.
3. Inspect `git status` and the complete diff.
4. Run focused tests, `poetry check`, pre-commit and ASV checks when relevant.

## PR quality gate

- Title uses Conventional Commit format, for example
  `fix(sync): preserve class attribute descriptions`.
- Align the body with `.github/PULL_REQUEST_TEMPLATE.md`:
  - Pull Request description
  - How to test these changes
  - Pull Request checklists
  - Additional information
  - Reviewer's checklist
- Include exact commands/results and limitations.
- No duplicate tests, lockfile-only ASV edits, unrelated formatting or generated
  benchmark history.

Commit, push or open only with authorization. Never merge or force-update refs.
Never run `release.ci` or publish in PR follow-up.

Done: report branch, base SHA, PR URL/compare URL, validation and blockers.
