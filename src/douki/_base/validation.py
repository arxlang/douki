"""
title: Validate docstring YAML against the Douki schema.
"""

from __future__ import annotations

import json

from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import ValidationError
from jsonschema.validators import validator_for

_schema_cache: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    """
    title: Load and cache the Douki JSON schema.
    returns: Cached schema for authored Douki documentation.
    """
    global _schema_cache

    if _schema_cache is None:
        with files('douki').joinpath('schema.json').open() as fh:
            _schema_cache = json.load(fh)
    return _schema_cache


@lru_cache(maxsize=2)
def _validator(enriched: bool = False) -> Any:
    """
    title: Reuse a schema-checked JSON Schema validator across docstrings.
    parameters:
      enriched:
        description: Whether to allow annotation-derived type fields
          in generated output.
    returns: Cached validator for authored or enriched documentation.
    """
    schema = _schema()
    if enriched:
        schema = deepcopy(schema)
        for name in ('param_entry', 'attr_entry'):
            schema['definitions'][name]['anyOf'][1]['properties']['type'] = {
                'type': 'string',
            }
        schema['definitions']['description_entry']['properties']['type'] = {
            'type': 'string',
        }
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema)


def validate_schema(doc: dict[str, Any], *, enriched: bool = False) -> None:
    """
    title: Validate *doc* against the Douki JSON schema.
    parameters:
      doc:
        description: Parsed documentation mapping to validate.
      enriched:
        description: Whether to allow annotation-derived type fields
          in generated output.
    """
    try:
        _validator(enriched).validate(doc)
    except ValidationError as err:
        raise ValueError(
            f'Docstring YAML does not follow douki schema: {err.message}'
        ) from err
