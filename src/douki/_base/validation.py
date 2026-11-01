"""
title: Validate docstring YAML against the Douki schema.
"""

from __future__ import annotations

import json

from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import ValidationError
from jsonschema.validators import validator_for

_schema_cache: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    """
    title: Load and cache the Douki JSON schema.
    returns:
      type: dict[str, Any]
    """
    global _schema_cache

    if _schema_cache is None:
        with files('douki').joinpath('schema.json').open() as fh:
            _schema_cache = json.load(fh)
    return _schema_cache


@lru_cache(maxsize=1)
def _validator() -> Any:
    """
    title: Reuse a schema-checked JSON Schema validator across docstrings.
    returns:
      type: Any
    """
    schema = _schema()
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema)


def validate_schema(doc: dict[str, Any]) -> None:
    """
    title: Validate *doc* against the Douki JSON schema.
    parameters:
      doc:
        type: dict[str, Any]
    """
    try:
        _validator().validate(doc)
    except ValidationError as err:
        raise ValueError(
            f'Docstring YAML does not follow douki schema: {err.message}'
        ) from err
