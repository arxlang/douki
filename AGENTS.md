# Working on Douki

## Repository snapshot

- Package: `douki`, a Python annotation-first YAML docstring toolkit.
- Python: `>=3.10,<4`. CI tests 3.10-3.14 on Ubuntu, macOS, and Windows;
  the linter uses Ubuntu Python 3.10 and ASV uses Python 3.11.
- Runtime: `atpublic`, `plum-dispatch`, `typeguard`, `pyyaml`, `jsonschema`,
  `typer`, `rich`, and `tomli` on Python below 3.11.
- CLI: `douki = douki.cli:app`.
- MkDocs builds API and usage documentation; `docs/index.md` is a symlink to
  `../README.md`.

## Architecture and invariants

The source pipeline has three main ownership boundaries:

1. Public API and CLI:
   - `src/douki/__init__.py`, `cli.py`, `sync.py`, `migrate.py`,
     `documentation.py`, `helping.py`, `introspection.py`, `typechecking.py`,
     and `schema.json`.
2. Language-neutral core:
   - `_base/config.py`, `defaults.py`, `discovery.py`, `language.py`,
     `sync.py`, and `validation.py`.
3. Python backend:
   - `_python/config.py`, `defaults.py`, `extractor.py`, `language.py`,
     `migrate.py`, and `sync.py`.

Important contracts:

- Python annotations supply types. YAML docstrings supply title, prose,
  parameters, attributes, raises, warnings, and other metadata.
- Authored YAML must not contain `type:` fields. `-> None` is required for a
  void callable; implicit method receivers are exempt.
- `schema.json` accepts authored source and a separate enriched validator
  permits generated `type:` fields.
- Static synchronization uses the Python AST and rewrites docstring regions in
  reverse line order. Preserve idempotence and source quoting/spacing.
- `douki.enrich`, `douki.getdoc`, and `douki.help` may add generated types,
  but never write them back into source.
- `register(package)` is package-scoped and must not mutate foreign objects or
  descendants outside the registered dotted boundary.
- `getdoc` and `help` must not execute properties or call user functions.
- `documentation.py` raises `DocumentationError`; CLI synchronization raises
  `DocstringValidationError`.

## Code conventions

- Use explicit `atpublic` `@public` / `@private` visibility.
- Import the package runtime wrapper from `douki.typechecking`, not raw
  `typeguard.typechecked`.
- The wrapper checks all collection items and fails closed on forward refs.
- Use Plum dispatch in `helping.py` and `introspection.py` with fail-closed
  fallbacks.
- Ruff uses 79 columns, single quotes, and
  `E, F, YTT, RUF, I001, UP006, UP007`; it excludes `docs/`.
- Strict mypy targets Python 3.10, enables `check_untyped_defs`, excludes
  `scripts/`, and uses no-redef overrides for `introspection.py` and `helping.py`.
- Bandit excludes `tests/`. Vulture excludes `tests/`, has minimum confidence
  80, and enables its whitelist. mccabe flags cyclomatic complexity >=10
  (`python -m mccabe --min 10`).

## Canonical verification

```bash
poetry check
poetry run makim tests.unit
poetry run makim tests.smoke
poetry run makim tests.linter
poetry run makim tests.ci
poetry run makim docs.build
poetry run makim package.build
poetry run makim release.dry

poetry run douki format --check src tests benchmarks
poetry run douki check <changed-paths>
```

Use `poetry run douki check <changed-paths>` for a focused check of edited
files. Repo-wide `douki check` can report pre-existing missing
attribute/parameter descriptions in several existing `src/` and `tests/`
files.

`tests.unit` requires 90% coverage. `tests.smoke` covers help, clean, dirty,
sync/idempotence, NumPy migration, and class/method sync. `release.ci` is manual
`workflow_dispatch` only.

## Benchmarks

For changes under `benchmarks/`:

```bash
asv check -E existing
```

Never update `poetry.lock` solely for ASV. PR benchmark jobs compare exact base
and head SHAs. ASV execution failures fail CI; measured regressions are
advisory. The trusted comment workflow must not execute PR code.

## Reusable Agent Skills

| Skill | Use |
| --- | --- |
| [agent-authoring](.agents/skills/agent-authoring/SKILL.md) | Add or maintain agent skills |
| [api-design](.agents/skills/api-design/SKILL.md) | Design APIs and CLI contracts |
| [ci-debug](.agents/skills/ci-debug/SKILL.md) | Diagnose CI and Makim failures |
| [douki-docstrings](.agents/skills/douki-docstrings/SKILL.md) | Maintain annotation-first docstrings |
| [fix-issue](.agents/skills/fix-issue/SKILL.md) | Reproduce and fix defects |
| [implementation-planning](.agents/skills/implementation-planning/SKILL.md) | Produce reviewable plans |
| [minimal-change](.agents/skills/minimal-change/SKILL.md) | Default scope-control procedure |
| [open-pr](.agents/skills/open-pr/SKILL.md) | Create or update a scoped PR |
| [pr-review](.agents/skills/pr-review/SKILL.md) | Review PRs and local diffs |
| [python-code-style](.agents/skills/python-code-style/SKILL.md) | Python implementation conventions |
| [release-check](.agents/skills/release-check/SKILL.md) | Review release readiness |
| [testing-standards](.agents/skills/testing-standards/SKILL.md) | Select focused tests |
| [triage-issues](.agents/skills/triage-issues/SKILL.md) | Classify and route issues |

Apply [minimal-change](.agents/skills/minimal-change/SKILL.md) and
[implementation-planning](.agents/skills/implementation-planning/SKILL.md) as
defaults.
