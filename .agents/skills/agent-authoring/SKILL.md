---
name: agent-authoring
description: >-
  Create or maintain portable Douki Agent Skills with narrow triggers,
  verified repository facts and safe tool permissions.
---

# Create and maintain effective Douki skills

**Use for adding or revising `.agents/skills/**/SKILL.md`.** Do not create
platform-specific Copilot configuration.

## What a good skill contains

- YAML frontmatter whose `name` exactly matches the directory name.
- A clear description stating what and when.
- Verified Douki paths, Makim tasks, workflows, benchmark rules, and test
  conventions.
- Preconditions, evidence, decision points, validation, failure paths and stop
  conditions.
- Relative links that resolve inside `.agents/skills/`.

## Authoring procedure

1. Inspect `AGENTS.md`, `pyproject.toml`, `.makim.yaml`,
   `.pre-commit-config.yaml`, `src/douki/`, `tests/`, `scripts/`,
   `benchmarks/`, and relevant workflows.
2. Trace the real pipeline: CLI/plugin core, AST sync/schema, runtime help, and
   benchmark/release surfaces.
3. Adapt every command and path; remove compiler, monorepo, C++, Arrow, and
   DoukiMD-only concepts.
4. State when GitHub or local mutation is authorized. PR review and release
   checks are read-only unless explicitly requested.
5. Preserve the source/type contract:
   - annotations supply types
   - authored YAML supplies prose
   - enriched output may contain generated `type:` fields
6. Validate frontmatter, Markdown links, LF endings, and trailing whitespace.

**Exit:** a skill guides a safe, reproducible contribution without duplicating
`AGENTS.md` or creating platform-specific discovery.
