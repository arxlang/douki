"""
title: Tests for douki.sync — the core sync engine.
"""

from __future__ import annotations

# -------------------------------------------------------------------
# validate_docstring
# -------------------------------------------------------------------
import pytest

from douki.sync import (
    ParamInfo,
    extract_functions,
    sync_docstring,
    sync_source,
    validate_docstring,
)


def test_validate_docstring_valid() -> None:
    assert validate_docstring('title: hello', 'test')


def test_validate_docstring_missing_title() -> None:
    with pytest.raises(ValueError, match="Missing 'title' field"):
        validate_docstring('summary: no title here', 'test')


def test_validate_docstring_plain_text() -> None:
    with pytest.raises(
        ValueError, match='Docstring is not a valid Douki YAML dictionary'
    ):
        validate_docstring('Just a plain docstring.', 'test')


def test_validate_docstring_empty() -> None:
    assert not validate_docstring('', 'test')


# -------------------------------------------------------------------
# extract_functions
# -------------------------------------------------------------------


def test_extract_basic_function() -> None:
    src = '''\
def greet(name: str) -> str:
    """title: Say hello"""
    return f"Hello {name}"
'''
    funcs = extract_functions(src)
    assert len(funcs) == 1
    f = funcs[0]
    assert f.name == 'greet'
    assert len(f.params) == 1
    assert f.params[0].name == 'name'
    assert f.params[0].annotation == 'str'
    assert f.return_annotation == 'str'


def test_extract_ignores_self_cls() -> None:
    src = '''\
class Foo:
    def bar(self, x: int) -> int:
        """title: bar"""
        return x

    @classmethod
    def baz(cls, y: int) -> int:
        """title: baz"""
        return y
'''
    funcs = extract_functions(src)
    for f in funcs:
        for p in f.params:
            assert p.name not in ('self', 'cls')


def test_extract_async_function() -> None:
    src = '''\
async def fetch(url: str) -> bytes:
    """title: fetch url"""
    return b""
'''
    funcs = extract_functions(src)
    assert len(funcs) == 1
    assert funcs[0].name == 'fetch'
    assert funcs[0].return_annotation == 'bytes'


def test_extract_star_args() -> None:
    src = '''\
def variadic(*args: int, **kwargs: str) -> None:
    """title: variadic"""
    pass
'''
    funcs = extract_functions(src)
    assert len(funcs) == 1
    names = [p.name for p in funcs[0].params]
    assert 'args' in names
    assert 'kwargs' in names


def test_extract_no_docstring() -> None:
    src = """\
def nodoc(x: int) -> int:
    return x
"""
    funcs = extract_functions(src)
    assert len(funcs) == 1
    assert funcs[0].docstring_node is None


# -------------------------------------------------------------------
# sync_docstring
# -------------------------------------------------------------------


def _p(
    name: str,
    ann: str = '',
    kind: str = 'regular',
) -> ParamInfo:
    return ParamInfo(name=name, annotation=ann, kind=kind)


def test_sync_adds_missing_param() -> None:
    raw = 'title: test\n'
    params = [_p('x', 'int'), _p('y', 'int')]
    result = sync_docstring(raw, params, 'int')
    assert 'x:' in result
    assert 'y:' in result
    assert 'type: int' in result


def test_sync_removes_stale_param() -> None:
    raw = (
        'title: test\nparameters:\n'
        '  x:\n    type: int\n    description: old\n'
        '  z:\n    type: str\n    description: stale\n'
    )
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, 'int')
    assert 'x:' in result
    assert 'z:' not in result


def test_sync_preserves_descriptions() -> None:
    raw = (
        'title: test\nparameters:\n'
        '  x:\n    type: int\n'
        '    description: My custom description\n'
    )
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, 'int')
    assert 'My custom description' in result


def test_sync_updates_return_type() -> None:
    raw = 'title: test\n'
    result = sync_docstring(raw, [], 'float')
    assert 'returns:' in result
    assert 'type: float' in result


def test_sync_raises_on_non_yaml() -> None:
    raw = 'Just a plain docstring.'
    with pytest.raises(ValueError, match='not a valid Douki YAML'):
        sync_docstring(raw, [_p('x', 'int')], 'int')


def test_sync_idempotent() -> None:
    raw = (
        'title: test\n'
        'parameters:\n'
        '  x:\n'
        '    type: int\n'
        '    description: the x value\n'
        'returns:\n'
        '  type: int\n'
        '  description: the result\n'
    )
    params = [_p('x', 'int')]
    first = sync_docstring(raw, params, 'int')
    second = sync_docstring(first, params, 'int')
    assert first == second


def test_sync_handles_star_args() -> None:
    raw = 'title: test\n'
    params = [
        _p('args', 'int', 'var_positional'),
        _p('kwargs', 'str', 'var_keyword'),
    ]
    result = sync_docstring(raw, params, 'None')
    assert '*args:' in result
    assert '**kwargs:' in result


def test_sync_removes_returns_for_none() -> None:
    raw = 'title: test\nreturns:\n  type: str\n  description: old\n'
    result = sync_docstring(raw, [], 'None')
    assert 'returns' not in result


def test_sync_preserves_other_sections() -> None:
    raw = (
        'title: test\n'
        'summary: A summary\n'
        'raises:\n'
        '  - type: ValueError\n'
        '    description: bad value\n'
        'notes: some notes\n'
    )
    result = sync_docstring(raw, [], 'None')
    assert 'summary:' in result
    assert 'ValueError' in result
    assert 'notes:' in result


# -------------------------------------------------------------------
# sync_source (integration)
# -------------------------------------------------------------------


def test_sync_source_basic() -> None:
    src = '''\
def add(x: int, y: int) -> int:
    """
    title: Add two numbers
    """
    return x + y
'''
    result = sync_source(src)
    assert 'parameters:' in result
    assert 'x:' in result
    assert 'y:' in result
    assert 'type: int' in result


def test_sync_source_raises_on_non_yaml_docstring() -> None:
    src = '''\
def plain(x: int) -> int:
    """Just a plain docstring."""
    return x
'''
    with pytest.raises(ValueError, match='not a valid Douki YAML'):
        sync_source(src)


def test_sync_source_skips_no_docstring() -> None:
    src = """\
def nodoc(x: int) -> int:
    return x
"""
    result = sync_source(src)
    assert result == src


def test_sync_source_idempotent() -> None:
    src = '''\
def greet(name: str) -> str:
    """
    title: Greet someone
    parameters:
      name:
        type: str
        description: The name
    returns:
      type: str
      description: greeting
    """
    return f"Hello {name}"
'''
    first = sync_source(src)
    second = sync_source(first)
    assert first == second


def test_sync_source_method_ignores_self() -> None:
    src = '''\
class Foo:
    def bar(self, x: int) -> int:
        """
        title: Bar method
        """
        return x
'''
    result = sync_source(src)
    assert 'self' not in result.split('title')[1]
    assert 'x:' in result


def test_sync_source_complex_types() -> None:
    src = '''\
from typing import Optional, List

def process(
    items: List[str],
    count: Optional[int] = None,
) -> dict[str, int]:
    """
    title: Process items
    """
    return {}
'''
    result = sync_source(src)
    assert 'items:' in result
    assert 'count:' in result


def test_sync_source_preserves_syntax_error() -> None:
    src = 'def broken( -> None:\n'
    result = sync_source(src)
    assert result == src


def test_sync_source_no_functions() -> None:
    src = 'X = 42\n'
    result = sync_source(src)
    assert result == src


# -------------------------------------------------------------------
# sync_source with migrate='numpydoc'
# -------------------------------------------------------------------


def test_sync_source_migrate_numpydoc() -> None:
    src = '''\
def add(x, y):
    """Add two numbers.

    Parameters
    ----------
    x : int
        First operand.
    y : int
        Second operand.

    Returns
    -------
    int
        The sum.
    """
    return x + y
'''
    result = sync_source(src, migrate='numpydoc')
    assert 'title:' in result
    assert 'parameters:' in result
    assert 'returns:' in result


def test_sync_source_migrate_leaves_yaml_alone() -> None:
    src = '''\
def greet(name: str) -> str:
    """
    title: Greet someone
    parameters:
      name:
        type: str
        description: The name
    returns:
      type: str
      description: greeting
    """
    return f"Hello {name}"
'''
    result = sync_source(src, migrate='numpydoc')
    second = sync_source(result, migrate='numpydoc')
    assert result == second


def test_sync_source_migrate_then_sync() -> None:
    src = '''\
def add(x: int, y: int) -> int:
    """Add two numbers.

    Parameters
    ----------
    x : int
        First operand.
    y : int
        Second operand.

    Returns
    -------
    int
        The sum.
    """
    return x + y
'''
    result = sync_source(src, migrate='numpydoc')
    assert 'title:' in result
    second = sync_source(result)
    assert result == second


# -------------------------------------------------------------------
# Coverage: annotation converters
# -------------------------------------------------------------------


def test_extract_forward_ref_annotation() -> None:
    src = '''\
def foo(x: 'MyClass') -> 'MyClass':
    """
    title: forward ref test
    """
    pass
'''
    result = sync_source(src)
    assert 'MyClass' in result


def test_extract_union_annotation() -> None:
    src = '''\
def foo(x: int | str) -> int | None:
    """
    title: union test
    """
    pass
'''
    result = sync_source(src)
    assert 'int | str' in result


def test_extract_attribute_annotation() -> None:
    src = '''\
import os

def foo(x: os.PathLike) -> None:
    """
    title: attribute test
    """
    pass
'''
    result = sync_source(src)
    assert 'os.PathLike' in result


def test_extract_tuple_annotation() -> None:
    src = '''\
def foo(x: tuple[int, str]) -> None:
    """
    title: tuple test
    """
    pass
'''
    result = sync_source(src)
    assert 'tuple' in result


def test_extract_list_annotation_bare() -> None:
    src = '''\
def foo(x: list[int]) -> None:
    """
    title: list test
    """
    pass
'''
    result = sync_source(src)
    assert 'list' in result


# -------------------------------------------------------------------
# Coverage: _param_kind
# -------------------------------------------------------------------


def test_extract_positional_only() -> None:
    src = '''\
def foo(x: int, /, y: int) -> None:
    """
    title: positional only test
    """
    pass
'''
    funcs = extract_functions(src)
    assert len(funcs) == 1
    kinds = {p.name: p.kind for p in funcs[0].params}
    assert kinds['x'] == 'positional_only'
    assert kinds['y'] == 'regular'


def test_extract_keyword_only() -> None:
    src = '''\
def foo(*, key: str) -> None:
    """
    title: keyword only test
    """
    pass
'''
    funcs = extract_functions(src)
    assert len(funcs) == 1
    kinds = {p.name: p.kind for p in funcs[0].params}
    assert kinds['key'] == 'keyword_only'


# -------------------------------------------------------------------
# Coverage: _extract_returns_desc edge cases
# -------------------------------------------------------------------


def test_sync_returns_list_string_items() -> None:
    raw = 'title: test\nreturns:\n  - type: int\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, 'int')
    assert 'returns:' in result


def test_sync_raises_on_old_flat_returns() -> None:
    raw = 'title: test\nreturns: the result\n'
    with pytest.raises(
        ValueError, match='Docstring YAML does not follow douki schema'
    ):
        sync_docstring(raw, [], 'int')


# -------------------------------------------------------------------
# Coverage: _is_douki_yaml rejects invalid schema
# -------------------------------------------------------------------


def test_is_douki_yaml_invalid_schema() -> None:
    # Has title but unknown field should fail schema validation
    with pytest.raises(
        ValueError, match='Docstring YAML does not follow douki schema'
    ):
        validate_docstring(
            'title: test\nunknown_field: bad',
            'test',
        )


# -------------------------------------------------------------------
# Coverage: _rebuild_yaml branches
# -------------------------------------------------------------------


def test_sync_with_multiline_summary() -> None:
    raw = 'title: test\nsummary: |\n  Line one\n  Line two\n'
    result = sync_docstring(raw, [], '')
    assert 'Line one' in result
    assert 'Line two' in result


def test_sync_with_raises_list() -> None:
    raw = 'title: test\nraises:\n  - type: ValueError\n    description: bad\n'
    result = sync_docstring(raw, [], '')
    assert 'ValueError' in result
    assert 'bad' in result


def test_sync_with_examples_list() -> None:
    raw = 'title: test\nexamples:\n  - code: |\n      add(1, 2)\n'
    result = sync_docstring(raw, [], '')
    assert 'examples:' in result
    assert 'add(1, 2)' in result


def test_sync_with_visibility_non_default() -> None:
    raw = 'title: test\nvisibility: private\n'
    result = sync_docstring(raw, [], '')
    assert 'visibility: private' in result


def test_sync_omits_default_visibility() -> None:
    raw = 'title: test\nvisibility: public\n'
    result = sync_docstring(raw, [], '')
    assert 'visibility' not in result


def test_sync_with_extra_keys() -> None:
    raw = 'title: test\nnotes: important note\n'
    result = sync_docstring(raw, [], '')
    assert 'notes: important note' in result


# -------------------------------------------------------------------
# Coverage: _yaml_scalar edge cases
# -------------------------------------------------------------------


def test_sync_param_with_optional_true() -> None:
    raw = 'title: test\nparameters:\n  x:\n    type: int\n    optional: true\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'optional: true' in result


def test_sync_param_with_default_value() -> None:
    raw = 'title: test\nparameters:\n  x:\n    type: int\n    default: 42\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'default: 42' in result


def test_sync_param_with_special_chars_desc() -> None:
    raw = (
        'title: test\n'
        'parameters:\n'
        '  x:\n'
        '    type: int\n'
        '    description: "value: important"\n'
    )
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'important' in result


# -------------------------------------------------------------------
# Coverage: method detection
# -------------------------------------------------------------------


def test_extract_classmethod() -> None:
    src = '''\
class Foo:
    @classmethod
    def create(cls, x: int) -> 'Foo':
        """
        title: Factory method
        """
        return cls()
'''
    funcs = extract_functions(src)
    # cls should be excluded
    for f in funcs:
        if f.name == 'create':
            assert all(p.name != 'cls' for p in f.params)


def test_sync_source_multiple_functions() -> None:
    src = '''\
def add(x: int, y: int) -> int:
    """
    title: Add
    """
    return x + y

def sub(x: int, y: int) -> int:
    """
    title: Subtract
    """
    return x - y
'''
    result = sync_source(src)
    assert 'parameters:' in result
    # Both functions should be synced
    assert result.count('parameters:') == 2


def test_sync_source_with_no_return_annotation() -> None:
    src = '''\
def foo(x: int):
    """
    title: No return
    """
    pass
'''
    result = sync_source(src)
    assert 'x:' in result
    # No return annotation → no returns section
    assert 'returns:' not in result


def test_sync_with_old_flat_params_preserved() -> None:
    """
    title: Ensure old flat string params still work
    """
    raw = 'title: test\nparameters:\n  x: my description\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'my description' in result
