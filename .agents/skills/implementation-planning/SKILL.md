---
name: implementation-planning
description: >-
  Plan feasible Douki implementations or refactors with small acceptance-driven
  steps and existing verification.
---

# Plan a reviewable Douki implementation

**Use for plans, milestones or substantial refactoring.** Apply
[minimal-change](../minimal-change/SKILL.md).

## Planning protocol

1. **Goal:** State what changes for users or contributors.
2. **Current implementation:** Inspect relevant public, core, Python, test,
   benchmark or workflow files.
3. **Acceptance criteria:** 2-5 observable behaviors, including source safety,
   reverse rewrite, missing-annotation, and exit-code behavior.
4. **Smallest vertical slice:** Include only necessary API/core/backend paths.
5. **Execution:** 3-7 meaningful steps.
6. **Verification:** Name existing pytest, smoke, linter, ASV or docs checks.
7. **Risks/out of scope:** State only real blockers or intentional exclusions.

## Output format

```markdown
## Goal

<one sentence>

## Acceptance criteria

- <observable behavior>

## Implementation

1. <owner and change>
2. <necessary integration>
3. <verification>

## Risks / out of scope

<only meaningful items>
```
