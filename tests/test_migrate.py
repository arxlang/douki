"""Tests for douki.migrate — NumPy docstring conversion."""

from __future__ import annotations

from douki.migrate import (
    _is_numpy_docstring,
    _parse_map_section,
    _split_sections,
    numpy_to_douki_yaml,
)

# -------------------------------------------------------------------
# Detection
# -------------------------------------------------------------------


def test_is_numpy_basic() -> None:
    ds = 'Summary.\n\nParameters\n----------\nx : int\n    Desc.\n'
    assert _is_numpy_docstring(ds)


def test_is_numpy_false_for_plain() -> None:
    assert not _is_numpy_docstring('Just a plain docstring.')


def test_is_numpy_false_for_yaml() -> None:
    assert not _is_numpy_docstring('title: test\n')


# -------------------------------------------------------------------
# Section splitting
# -------------------------------------------------------------------


def test_split_sections_basic() -> None:
    ds = (
        'Summary line.\n\n'
        'Parameters\n----------\n'
        'x : int\n    The x.\n\n'
        'Returns\n-------\n'
        'int\n    The result.\n'
    )
    narrative, sections = _split_sections(ds)
    assert narrative == 'Summary line.'
    assert len(sections) == 2
    assert sections[0][0] == 'parameters'
    assert sections[1][0] == 'returns'


# -------------------------------------------------------------------
# Map section parsing
# -------------------------------------------------------------------


def test_parse_map_section() -> None:
    body = 'x : int\n    The x value.\ny : str\n    The y value.'
    result = _parse_map_section(body)
    assert result == {
        'x': 'The x value.',
        'y': 'The y value.',
    }


# -------------------------------------------------------------------
# Full conversion
# -------------------------------------------------------------------


def test_numpy_to_douki_basic() -> None:
    ds = (
        'Add two numbers.\n\n'
        'Parameters\n----------\n'
        'x : int\n    First operand.\n'
        'y : int\n    Second operand.\n\n'
        'Returns\n-------\n'
        'int\n    The sum.\n'
    )
    result = numpy_to_douki_yaml(ds)
    assert 'title:' in result
    assert 'parameters:' in result
    assert 'returns:' in result


def test_numpy_preserves_non_numpy() -> None:
    raw = 'Just a plain docstring.'
    assert numpy_to_douki_yaml(raw) == raw


def test_numpy_parses_raises() -> None:
    ds = 'Do something.\n\nRaises\n------\nValueError\n    If input is bad.\n'
    result = numpy_to_douki_yaml(ds)
    assert 'raises:' in result
    assert 'ValueError' in result


def test_numpy_with_summary() -> None:
    ds = (
        'Title line.\n\n'
        'Extended summary that goes\n'
        'across multiple lines.\n\n'
        'Parameters\n----------\n'
        'x : int\n    Desc.\n'
    )
    result = numpy_to_douki_yaml(ds)
    assert 'title: Title line' in result
    assert 'summary:' in result
