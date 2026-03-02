"""Tests for douki.sync — the core sync engine."""

from __future__ import annotations

from douki.sync import (
    ParamInfo,
    _is_douki_yaml,
    extract_functions,
    sync_docstring,
    sync_source,
)

# -------------------------------------------------------------------
# _is_douki_yaml
# -------------------------------------------------------------------


def test_is_douki_yaml_valid() -> None:
    assert _is_douki_yaml('title: hello')


def test_is_douki_yaml_missing_title() -> None:
    assert not _is_douki_yaml('summary: no title here')


def test_is_douki_yaml_plain_text() -> None:
    assert not _is_douki_yaml('Just a plain docstring.')


def test_is_douki_yaml_empty() -> None:
    assert not _is_douki_yaml('')


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


def test_sync_skips_non_yaml() -> None:
    raw = 'Just a plain docstring.'
    result = sync_docstring(raw, [_p('x', 'int')], 'int')
    assert result == raw


def test_sync_idempotent() -> None:
    raw = (
        'title: test\n'
        'parameters:\n'
        '  x:\n'
        '    type: int\n'
        '    description: the x value\n'
        'returns:\n'
        '  - type: int\n'
        '    description: the result\n'
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
    raw = 'title: test\nreturns:\n  - type: str\n    description: old\n'
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


def test_sync_source_skips_non_yaml_docstring() -> None:
    src = '''\
def plain(x: int) -> int:
    """Just a plain docstring."""
    return x
'''
    result = sync_source(src)
    assert result == src


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
      - type: str
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
# sync_source with migrate='numpy'
# -------------------------------------------------------------------


def test_sync_source_migrate_numpy() -> None:
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
    result = sync_source(src, migrate='numpy')
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
      - type: str
        description: greeting
    """
    return f"Hello {name}"
'''
    result = sync_source(src, migrate='numpy')
    second = sync_source(result, migrate='numpy')
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
    result = sync_source(src, migrate='numpy')
    assert 'title:' in result
    second = sync_source(result)
    assert result == second
