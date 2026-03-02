"""Tests for douki._validation — schema validation."""

from __future__ import annotations

import pytest

from douki._validation import validate_schema


def test_valid_schema() -> None:
    """Valid doc should not raise."""
    validate_schema({'title': 'hello'})


def test_invalid_schema_raises() -> None:
    """Missing title should raise ValueError."""
    with pytest.raises(ValueError, match='douki schema'):
        validate_schema({'parameters': {}})


def test_invalid_extra_field_raises() -> None:
    """Unknown field should raise ValueError."""
    with pytest.raises(ValueError, match='douki schema'):
        validate_schema(
            {'title': 'test', 'unknown_field': 'bad'},
        )
