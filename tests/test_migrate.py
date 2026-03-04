"""
title: Tests for douki.migrate — NumPy docstring conversion.
"""

from __future__ import annotations

from douki._python.migrate import (
    _is_numpydoc_docstring,
    _parse_map_section,
    _serialize_douki_yaml,
    _split_sections,
    numpydoc_to_douki_yaml,
)

# -------------------------------------------------------------------
# Detection
# -------------------------------------------------------------------


def test_is_numpy_basic() -> None:
    ds = 'Summary.\n\nParameters\n----------\nx : int\n    Desc.\n'
    assert _is_numpydoc_docstring(ds)


def test_is_numpy_false_for_plain() -> None:
    assert not _is_numpydoc_docstring('Just a plain docstring.')


def test_is_numpy_false_for_yaml() -> None:
    assert not _is_numpydoc_docstring('title: test\n')


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
    result = numpydoc_to_douki_yaml(ds)
    assert 'title:' in result
    assert 'parameters:' in result
    assert 'returns:' in result
    # New format: nested params with type
    assert 'type: int' in result


def test_numpy_preserves_non_numpy() -> None:
    raw = 'Just a plain docstring.'
    assert numpydoc_to_douki_yaml(raw) == raw


def test_numpy_parses_raises() -> None:
    ds = 'Do something.\n\nRaises\n------\nValueError\n    If input is bad.\n'
    result = numpydoc_to_douki_yaml(ds)
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
    result = numpydoc_to_douki_yaml(ds)
    assert 'title: Title line' in result
    assert 'summary:' in result


def test_parse_map_no_type() -> None:
    """
    title: 'Entry without '': type'' should have no type key.'
    """
    body = 'x\n    The x value.'
    result = _parse_map_section(body)
    assert 'x' in result
    assert 'type' not in result['x']
    assert result['x']['description'] == 'The x value.'


def test_parse_map_no_description() -> None:
    """
    title: Entry with type but empty description should omit it.
    """
    body = 'x : int'
    result = _parse_map_section(body)
    assert result['x'] == {'type': 'int'}


def test_numpy_no_narrative() -> None:
    """
    title: Docstring with no summary line at all.
    """
    ds = '\n\nParameters\n----------\nx : int\n    Desc.\n'
    result = numpydoc_to_douki_yaml(ds)
    assert 'title:' in result


def test_numpy_yields_section() -> None:
    ds = 'Generate stuff.\n\nYields\n------\nint\n    A number.\n'
    result = numpydoc_to_douki_yaml(ds)
    assert 'yields:' in result


def test_numpy_warnings_section() -> None:
    ds = (
        'Do risky things.\n\n'
        'Warnings\n--------\n'
        'RuntimeWarning\n    Could be slow.\n'
    )
    result = numpydoc_to_douki_yaml(ds)
    assert 'warnings:' in result
    assert 'RuntimeWarning' in result


def test_numpy_notes_section() -> None:
    ds = 'Some function.\n\nNotes\n-----\nThis is a note.\nMulti-line note.\n'
    result = numpydoc_to_douki_yaml(ds)
    assert 'notes:' in result


def test_numpy_unknown_section_ignored() -> None:
    """
    title: Unknown sections should be silently skipped.
    """
    ds = 'Title.\n\nCustom Section\n--------------\nblah blah\n'
    result = numpydoc_to_douki_yaml(ds)
    assert 'title: Title' in result
    assert 'custom' not in result.lower()


# -------------------------------------------------------------------
# Coverage: _split_sections no sections
# -------------------------------------------------------------------


def test_split_sections_no_sections() -> None:
    """
    title: No dashes sections returns (narrative, []).
    """
    narrative, sections = _split_sections('Just a plain text.\nNo sections.')
    assert narrative == 'Just a plain text.\nNo sections.'
    assert sections == []


# -------------------------------------------------------------------
# Coverage: multiple return types → tuple
# -------------------------------------------------------------------


def test_numpy_multiple_returns() -> None:
    """
    title: Multiple return entries should combine into tuple[...].
    """
    ds = (
        'Do something.\n\n'
        'Returns\n-------\n'
        'x : int\n    The x.\n'
        'y : str\n    The y.\n'
    )
    result = numpydoc_to_douki_yaml(ds)
    # Names are used as keys in _parse_map_section → tuple[x, y]
    assert 'tuple[' in result
    assert 'x' in result
    assert 'y' in result


# -------------------------------------------------------------------
# Coverage: simple text returns (no parseable entries)
# -------------------------------------------------------------------


def test_numpy_returns_simple_text() -> None:
    """
    title: Returns section with no entries gives simple text.
    """
    ds = 'Do something.\n\nReturns\n-------\n    A simple description.\n'
    result = numpydoc_to_douki_yaml(ds)
    assert 'returns:' in result


# -------------------------------------------------------------------
# Coverage: _serialize_douki_yaml edge cases
# -------------------------------------------------------------------


def test_serialize_param_empty_string() -> None:
    """
    title: Param with empty string value.
    """
    data = {
        'title': 'test',
        'parameters': {'x': {'type': 'int'}, 'y': ''},
    }
    result = _serialize_douki_yaml(data)
    assert 'y:' in result


def test_serialize_param_nonempty_string() -> None:
    """
    title: Param with non-empty string value.
    """
    data = {
        'title': 'test',
        'parameters': {'x': 'desc'},
    }
    result = _serialize_douki_yaml(data)
    assert 'x: desc' in result


def test_serialize_list_non_dict_items() -> None:
    """
    title: List with plain string items.
    """
    data = {
        'title': 'test',
        'see_also': ['func_a', 'func_b'],
    }
    result = _serialize_douki_yaml(data)
    assert '- func_a' in result
    assert '- func_b' in result


def test_serialize_dict_multiline_value() -> None:
    """
    title: Dict value containing multiline string.
    """
    data = {
        'title': 'test',
        'returns': {'type': 'int', 'description': 'line1\nline2'},
    }
    result = _serialize_douki_yaml(data)
    assert 'description: |' in result
    assert 'line1' in result
    assert 'line2' in result


def test_serialize_extra_key() -> None:
    """
    title: Key not in canonical order should still appear.
    """
    data = {'title': 'test', 'custom_key': 'value'}
    result = _serialize_douki_yaml(data)
    assert 'custom_key: value' in result


def test_serialize_empty_value_skipped() -> None:
    """
    title: None/empty values should be skipped.
    """
    data = {'title': 'test', 'summary': None, 'notes': ''}
    result = _serialize_douki_yaml(data)
    assert 'summary' not in result
    assert 'notes' not in result
