"""
title: Tests for douki._validation — schema validation.
"""

from __future__ import annotations

import pytest

from douki._base.validation import validate_schema


def test_valid_schema() -> None:
    """
    title: Valid doc should not raise.
    """
    validate_schema({'title': 'hello'})


def test_invalid_schema_raises() -> None:
    """
    title: Missing title should raise ValueError.
    """
    with pytest.raises(ValueError, match='douki schema'):
        validate_schema({'parameters': {}})


def test_invalid_extra_field_raises() -> None:
    """
    title: Unknown field should raise ValueError.
    """
    with pytest.raises(ValueError, match='douki schema'):
        validate_schema(
            {'title': 'test', 'unknown_field': 'bad'},
        )
