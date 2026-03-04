"""
title: Backward-compatible re-exports for douki._validation.
summary: The actual implementation lives in ``douki._base.validation``.
"""

from douki._base.validation import validate_schema

__all__ = ['validate_schema']
