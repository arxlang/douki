# Douki

[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)![Mkdocs](https://img.shields.io/badge/Documentation%20engine-Mkdocs-orange)
[![Built with Material for MkDocs](https://img.shields.io/badge/Material_for_MkDocs-526CFE?style=for-the-badge&logo=MaterialForMkDocs&logoColor=white)](https://squidfunk.github.io/mkdocs-material/)
![Conda](https://img.shields.io/badge/Virtual%20environment-conda-brightgreen?logo=anaconda)[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
![coverage](https://img.shields.io/badge/Code%20coverage%20testing-coverage.py-blue)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![vulture](https://img.shields.io/badge/Find%20unused%20code-vulture-blue)
![McCabe](https://img.shields.io/badge/Complexity%20checker-McCabe-blue)
![mypy](https://img.shields.io/badge/Static%20typing-mypy-blue)
![pytest](https://img.shields.io/badge/Testing-pytest-cyan?logo=pytest)[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
![Makim](https://img.shields.io/badge/Automation%20task-Makim-blue)![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-blue?logo=githubactions)

Documetatio from annotations

- Software License: BSD 3 Clause

- Documentation: https://osl-incubator.github.io/douki

## Features

### CLI — `douki sync` / `douki check`

Synchronize Douki YAML docstrings with Python function
signatures. Designed to run standalone or as a **pre-commit hook**.

```bash
# Show what would change (exit 1 if diffs exist)
douki check src/

# Apply changes in-place
douki sync src/

# Specific files
douki check path/to/file.py
```

Without arguments, both commands default to the current directory.

#### Pre-commit integration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/osl-incubator/douki
    rev: v0.6.0 # pin to a release tag
    hooks:
      - id: douki-check
        name: douki check
        entry: douki check
        language: python
        types: [python]
```

## Credits

This package was created with
[scicookie](https://github.com/osl-incubator/scicookie) project template.
