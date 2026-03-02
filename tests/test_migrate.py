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
        'x': {'type': 'int', 'description': 'The x value.'},
        'y': {'type': 'str', 'description': 'The y value.'},
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
    # New format: nested params with type
    assert 'type: int' in result


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


def test_parse_map_no_type() -> None:
    """Entry without ': type' should have no type key."""
    body = 'x\n    The x value.'
    result = _parse_map_section(body)
    assert 'x' in result
    assert 'type' not in result['x']
    assert result['x']['description'] == 'The x value.'


def test_parse_map_no_description() -> None:
    """Entry with type but empty description should omit it."""
    body = 'x : int'
    result = _parse_map_section(body)
    assert result['x'] == {'type': 'int'}


def test_numpy_no_narrative() -> None:
    """Docstring with no summary line at all."""
    ds = '\n\nParameters\n----------\nx : int\n    Desc.\n'
    result = numpy_to_douki_yaml(ds)
    assert 'title:' in result


def test_numpy_yields_section() -> None:
    ds = 'Generate stuff.\n\nYields\n------\nint\n    A number.\n'
    result = numpy_to_douki_yaml(ds)
    assert 'yields:' in result


def test_numpy_warnings_section() -> None:
    ds = (
        'Do risky things.\n\n'
        'Warnings\n--------\n'
        'RuntimeWarning\n    Could be slow.\n'
    )
    result = numpy_to_douki_yaml(ds)
    assert 'warnings:' in result
    assert 'RuntimeWarning' in result


def test_numpy_notes_section() -> None:
    ds = 'Some function.\n\nNotes\n-----\nThis is a note.\nMulti-line note.\n'
    result = numpy_to_douki_yaml(ds)
    assert 'notes:' in result


def test_numpy_unknown_section_ignored() -> None:
    """Unknown sections should be silently skipped."""
    ds = 'Title.\n\nCustom Section\n--------------\nblah blah\n'
    result = numpy_to_douki_yaml(ds)
    assert 'title: Title' in result
    assert 'custom' not in result.lower()
