"""
title: Isolate package help registration between tests.
"""

import builtins

import pytest

from douki import helping


@pytest.fixture(autouse=True)
def isolated_help_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    title: Restore interpreter help and registration state after each test.
    parameters:
      monkeypatch: Fixture restoring modified attributes after the test.
    """
    monkeypatch.setattr(builtins, 'help', builtins.help)
    monkeypatch.setattr(helping, 'fallback_help', builtins.help)
    monkeypatch.setattr(helping, 'registered_packages', set())
