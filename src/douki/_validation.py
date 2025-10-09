"""Validate docstring YAML."""

from __future__ import annotations

import json

from importlib.resources import files
from typing import Any

from jsonschema import ValidationError, validate

_schema_cache: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    global _schema_cache

    if _schema_cache is None:
        with files('doxs').joinpath('schema.json').open() as fh:
            _schema_cache = json.load(fh)
    return _schema_cache


def validate_schema(doc: dict[str, Any]) -> None:
    try:
        validate(instance=doc, schema=_schema())
    except ValidationError as err:
        raise ValueError(
            f'Docstring YAML does not follow doxs schema: {err.message}'
        ) from err
