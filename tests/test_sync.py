"""
title: Tests for douki.sync — the core sync engine.
"""

from __future__ import annotations

# -------------------------------------------------------------------
# validate_docstring
# -------------------------------------------------------------------
import pytest

from douki._base.sync import (
    DocstringValidationError,
    ParamInfo,
    _extract_returns_desc,
    _load_docstring_yaml,
    _yaml_scalar,
    sync_docstring,
    validate_docstring,
)
from douki._python.defaults import PYTHON_DEFAULTS
from douki._python.extractor import extract_functions
from douki._python.sync import sync_source


def test_validate_docstring_valid() -> None:
    """
    title: Valid Douki YAML returns True.
    """
    assert validate_docstring('title: hello', 'test')


def test_validate_docstring_missing_title() -> None:
    """
    title: YAML without title raises ValueError.
    """
    with pytest.raises(ValueError, match="Missing 'title' field"):
        validate_docstring('summary: no title here', 'test')


def test_validate_docstring_plain_text() -> None:
    """
    title: Plain text docstring raises ValueError.
    """
    with pytest.raises(
        ValueError, match='Docstring is not a valid Douki YAML dictionary'
    ):
        validate_docstring('Just a plain docstring.', 'test')


def test_validate_docstring_empty() -> None:
    """
    title: Empty string returns False.
    """
    assert not validate_docstring('', 'test')


# -------------------------------------------------------------------
# extract_functions
# -------------------------------------------------------------------


def test_extract_basic_function() -> None:
    """
    title: Basic function extraction returns name, params, and return type.
    """
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
    """
    title: self and cls are excluded from extracted params.
    """
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
    """
    title: Async functions are extracted correctly.
    """
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
    """
    title: '*args and **kwargs are extracted as parameters.'
    """
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
    """
    title: Function without docstring has docstring_node None.
    """
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
    """
    title: Shorthand ParamInfo constructor for tests.
    parameters:
      name:
        type: str
      ann:
        type: str
      kind:
        type: str
    returns:
      type: ParamInfo
    """
    return ParamInfo(name=name, annotation=ann, kind=kind)


def test_sync_adds_missing_param() -> None:
    """
    title: Missing parameters are added to the docstring.
    """
    raw = 'title: test\n'
    params = [_p('x', 'int'), _p('y', 'int')]
    result = sync_docstring(raw, params, 'int')
    assert 'x:' in result
    assert 'y:' in result
    assert 'type: int' in result


def test_sync_removes_stale_param() -> None:
    """
    title: Parameters no longer in signature are removed.
    """
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
    """
    title: Existing parameter descriptions are preserved.
    """
    raw = (
        'title: test\nparameters:\n'
        '  x:\n    type: int\n'
        '    description: My custom description\n'
    )
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, 'int')
    assert 'My custom description' in result


def test_sync_updates_return_type() -> None:
    """
    title: Return type annotation is synced into returns section.
    """
    raw = 'title: test\n'
    result = sync_docstring(raw, [], 'float')
    assert 'returns:' in result
    assert 'type: float' in result


def test_sync_raises_on_non_yaml() -> None:
    """
    title: Non-YAML docstring raises ValueError.
    """
    raw = 'Just a plain docstring.'
    with pytest.raises(ValueError, match='not a valid Douki YAML'):
        sync_docstring(raw, [_p('x', 'int')], 'int')


def test_sync_idempotent() -> None:
    """
    title: Syncing a fully-synced docstring produces no changes.
    """
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
    """
    title: '*args and **kwargs produce variadic markers.'
    """
    raw = 'title: test\n'
    params = [
        _p('args', 'int', 'var_positional'),
        _p('kwargs', 'str', 'var_keyword'),
    ]
    result = sync_docstring(raw, params, 'None')
    assert 'args:' in result
    assert 'kwargs:' in result
    assert 'variadic: positional' in result
    assert 'variadic: keyword' in result
    # No quoted *args / **kwargs keys
    assert "'*args':" not in result
    assert "'**kwargs':" not in result


def test_sync_variadic_round_trip() -> None:
    """
    title: Variadic parameters survive a round-trip sync.
    """
    raw = (
        'title: test\n'
        'parameters:\n'
        '  args:\n'
        '    type: int\n'
        '    variadic: positional\n'
        '  kwargs:\n'
        '    type: str\n'
        '    variadic: keyword\n'
    )
    params = [
        _p('args', 'int', 'var_positional'),
        _p('kwargs', 'str', 'var_keyword'),
    ]
    first = sync_docstring(raw, params, 'None')
    second = sync_docstring(first, params, 'None')
    assert first == second
    assert 'variadic: positional' in first
    assert 'variadic: keyword' in first


def test_sync_variadic_backward_compat() -> None:
    """
    title: Old YAML with quoted star keys is migrated on sync.
    """
    raw = (
        'title: test\n'
        'parameters:\n'
        "  '*args':\n"
        '    type: int\n'
        '    description: positional items\n'
        "  '**kwargs':\n"
        '    type: str\n'
        '    description: keyword items\n'
    )
    params = [
        _p('args', 'int', 'var_positional'),
        _p('kwargs', 'str', 'var_keyword'),
    ]
    result = sync_docstring(raw, params, 'None')
    assert 'args:' in result
    assert 'kwargs:' in result
    assert 'variadic: positional' in result
    assert 'variadic: keyword' in result
    assert 'positional items' in result
    assert 'keyword items' in result
    # Old quoted keys gone
    assert "'*args':" not in result
    assert "'**kwargs':" not in result


def test_sync_removes_returns_for_none() -> None:
    """
    title: Returns section is removed when return type is None.
    """
    raw = 'title: test\nreturns:\n  type: str\n  description: old\n'
    result = sync_docstring(raw, [], 'None')
    assert 'returns' not in result


def test_sync_preserves_other_sections() -> None:
    """
    title: Non-parameter sections like summary and raises are preserved.
    """
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
    """
    title: Basic sync_source adds parameters and types.
    """
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
    """
    title: Plain-text docstring in source raises ValueError.
    """
    src = '''\
def plain(x: int) -> int:
    """Just a plain docstring."""
    return x
'''
    with pytest.raises(ValueError, match='not a valid Douki YAML'):
        sync_source(src)


def test_sync_source_raises_on_missing_docstring() -> None:
    """
    title: Function without any docstring raises validation error.
    """
    src = """\
def nodoc(x: int) -> int:
    return x
"""
    with pytest.raises(DocstringValidationError, match='missing docstring'):
        sync_source(src)


def test_sync_source_idempotent() -> None:
    """
    title: Syncing already-synced source produces identical output.
    """
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
    """
    title: Method sync excludes self from parameters.
    """
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
    """
    title: Complex type annotations are synced correctly.
    """
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
    """
    title: Unparseable source is returned unchanged.
    """
    src = 'def broken( -> None:\n'
    result = sync_source(src)
    assert result == src


def test_sync_source_no_functions() -> None:
    """
    title: Source with no functions is returned unchanged.
    """
    src = 'X = 42\n'
    result = sync_source(src)
    assert result == src


def test_sync_source_classdef_no_params_from_init() -> None:
    """
    title: >-
      Class docstring should NOT get parameters: from __init__; use attributes:
      instead.
    """
    src = '''\
class MyClass:
    """
    title: My class docstring
    """
    def __init__(self, count: int, name: str = "test"):
        """
        title: Init MyClass
        """
        self.count = count
        self.name = name
'''
    result = sync_source(src)
    # Class docstring should NOT have parameters: injected
    class_doc_end = result.index('def __init__')
    class_docstring_region = result[:class_doc_end]
    assert 'parameters:' not in class_docstring_region
    # But __init__ docstring SHOULD get its parameters synced
    assert 'count:' in result
    assert 'name:' in result
    assert 'type: int' in result


def test_sync_source_classdef_auto_attributes() -> None:
    """
    title: >-
      Class-level annotated vars are auto-populated into attributes: section.
    """
    src = '''\
class MyClass:
    """
    title: My class
    """
    value: int
    name: str
    def __init__(self, value: int, name: str) -> None:
        """
        title: Initialize MyClass.
        """
        self.value = value
        self.name = name
'''
    result = sync_source(src)
    # Class docstring must have attributes: with both vars
    class_doc_end = result.index('def __init__')
    class_region = result[:class_doc_end]
    assert 'attributes:' in class_region
    assert 'value:' in class_region
    assert 'name:' in class_region
    # No parameters: in the class docstring
    assert 'parameters:' not in class_region


def test_sync_source_classdef_classvar_annotation_passthrough() -> None:
    """
    title: 'ClassVar annotation flows through unchanged into attributes: type.'
    """
    src = '''\
from typing import ClassVar

class MyClass:
    """
    title: My class
    """
    MAX: ClassVar[int] = 100
    count: int
'''
    result = sync_source(src)
    # attributes: header must appear before the class body variables
    assert 'attributes:' in result
    # Both annotated vars must appear as attribute keys
    assert 'MAX:' in result
    assert 'count:' in result
    # ClassVar type flows through verbatim
    assert 'ClassVar[int]' in result
    # No parameters: should be injected into the class docstring
    assert 'parameters:' not in result


def test_sync_source_classdef_attributes_preserves_description() -> None:
    """
    title: 'Existing description in attributes: is preserved after re-sync.'
    """
    src = '''\
class MyClass:
    """
    title: My class
    attributes:
      count:
        type: int
        description: The count.
    """
    count: int
'''
    result = sync_source(src)
    assert 'attributes:' in result
    assert 'The count.' in result
    # Idempotent
    second = sync_source(result)
    assert result == second


def test_sync_source_classdef_private_attrs_from_init() -> None:
    """
    title: >-
      Private attrs assigned via self._x in __init__ appear in attributes:
      section.
    """
    src = '''\
class MyClass:
    """
    title: My class
    """
    def __init__(self, count: int):
        """
        title: Initialize MyClass.
        """
        self._count = count
        self._cache = {}
'''
    result = sync_source(src)
    assert 'attributes:' in result
    assert '_count:' in result
    assert '_cache:' in result


def test_sync_source_classdef_annotated_private_attrs_from_init() -> None:
    """
    title: 'Annotated self._x: T in __init__ appears in attributes: with type.'
    """
    src = '''\
class MyClass:
    """
    title: My class
    """
    def __init__(self) -> None:
        """
        title: Initialize MyClass.
        """
        self._value: int = 0
        self._name: str = "default"
'''
    result = sync_source(src)
    assert 'attributes:' in result
    assert '_value:' in result
    assert '_name:' in result
    assert 'type: int' in result
    assert 'type: str' in result


def test_sync_source_classdef_class_level_overrides_init() -> None:
    """
    title: Class-level annotation takes precedence over self.* in __init__.
    """
    src = '''\
class MyClass:
    """
    title: My class
    """
    count: float  # class-level wins
    def __init__(self, count: int):
        """
        title: Initialize MyClass.
        """
        self.count = count
'''
    result = sync_source(src)
    # The class-level annotation (float) wins, not the __init__ assignment
    ds_start = result.index('"""') + 3
    ds_end = result.index('"""', ds_start)
    ds_region = result[ds_start:ds_end]
    assert 'type: float' in ds_region
    # Only one count: entry in the docstring
    assert ds_region.count('count:') == 1


def test_sync_source_classdef_inherits_base_attrs() -> None:
    """
    title: >-
      Derived class attributes: includes base class annotated vars from same
      file.
    """
    src = '''\
class Base:
    """
    title: Base class
    """
    x: int
    y: str

class Derived(Base):
    """
    title: Derived class
    """
    z: float
'''
    result = sync_source(src)
    # Find the Derived class docstring region
    derived_start = result.index('class Derived')
    derived_region = result[derived_start:]
    doc_start = derived_region.index('title: Derived')
    doc_end = derived_region.index('z: float')
    doc_region = derived_region[doc_start:doc_end]
    # Should contain own attr AND inherited attrs
    assert 'x:' in doc_region
    assert 'y:' in doc_region
    assert 'z:' in doc_region
    assert 'type: int' in doc_region
    assert 'type: str' in doc_region


def test_sync_source_classdef_multilevel_inheritance() -> None:
    """
    title: Multi-level inheritance chains attrs transitively.
    """
    src = '''\
class A:
    """
    title: A
    """
    a: int

class B(A):
    """
    title: B
    """
    b: str

class C(B):
    """
    title: C
    """
    c: float
'''
    result = sync_source(src)
    c_start = result.index('class C')
    c_region = result[c_start:]
    # C should have a:, b:, and c: all in its attributes
    assert 'a:' in c_region
    assert 'b:' in c_region
    assert 'c:' in c_region


def test_sync_source_classdef_own_attr_overrides_base() -> None:
    """
    title: >-
      When derived re-declares a base attr, derived type takes precedence in
      attributes:.
    """
    src = '''\
class Base:
    """
    title: Base
    """
    value: int

class Derived(Base):
    """
    title: Derived
    """
    value: float  # override with narrower type
'''
    result = sync_source(src)
    derived_start = result.index('class Derived')
    derived_region = result[derived_start:]
    # Isolate the docstring (between triple quotes)
    ds_start = derived_region.index('"""') + 3
    ds_end = derived_region.index('"""', ds_start)
    ds_region = derived_region[ds_start:ds_end]
    # Only one 'value:' entry in the docstring, and it should be float
    assert ds_region.count('value:') == 1
    assert 'type: float' in ds_region
    assert 'type: int' not in ds_region


def test_sync_source_nested_class_and_method() -> None:
    """
    title: Nested class method parameters are synced.
    """
    src = '''\
class Outer:
    """
    title: Outer
    """
    class Inner:
        """
        title: Inner
        """
        def method(self, val: float) -> bool:
            """
            title: Inner method
            """
            return True
'''
    result = sync_source(src)
    # The inner method should have its parameter synced
    assert 'val:' in result
    assert 'type: float' in result
    # parameters: only comes from the method, not from class docstrings
    assert result.count('parameters:') == 1


# -------------------------------------------------------------------
# sync_source with migrate='numpydoc'
# -------------------------------------------------------------------


def test_sync_source_migrate_numpydoc() -> None:
    """
    title: migrate=numpydoc converts NumPy docstrings to Douki YAML.
    """
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
    """
    title: migrate=numpydoc leaves existing Douki YAML unchanged.
    """
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
    """
    title: Migrated output is idempotent under plain sync.
    """
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
    """
    title: Forward-reference string annotations are extracted.
    """
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
    """
    title: Union type annotations (X | Y) are extracted.
    """
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
    """
    title: Dotted attribute annotations like os.PathLike are extracted.
    """
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
    """
    title: Subscripted tuple annotations are extracted.
    """
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
    """
    title: Subscripted list annotations are extracted.
    """
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
    """
    title: Positional-only parameters get the correct kind.
    """
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
    """
    title: Keyword-only parameters get the correct kind.
    """
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
    """
    title: returns as a list is not valid per schema.
    """
    raw = 'title: test\nreturns:\n  - type: int\n'
    params = [_p('x', 'int')]
    with pytest.raises(
        ValueError, match='Docstring YAML does not follow douki schema'
    ):
        sync_docstring(raw, params, 'int')


def test_sync_returns_flat_string() -> None:
    """
    title: returns as a plain string is valid per schema.
    """
    raw = 'title: test\nreturns: the result\n'
    result = sync_docstring(raw, [], 'int')
    assert 'returns:' in result


# -------------------------------------------------------------------
# Coverage: _is_douki_yaml rejects invalid schema
# -------------------------------------------------------------------


def test_is_douki_yaml_invalid_schema() -> None:
    """
    title: Unknown field in YAML fails schema validation.
    """
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
    """
    title: Multi-line summary is preserved through sync.
    """
    raw = 'title: test\nsummary: |\n  Line one\n  Line two\n'
    result = sync_docstring(raw, [], '')
    assert 'Line one' in result
    assert 'Line two' in result


def test_sync_with_raises_list() -> None:
    """
    title: raises section with list format is preserved.
    """
    raw = 'title: test\nraises:\n  - type: ValueError\n    description: bad\n'
    result = sync_docstring(raw, [], '')
    assert 'ValueError' in result
    assert 'bad' in result


def test_sync_with_examples_list() -> None:
    """
    title: examples section with code blocks is preserved.
    """
    raw = 'title: test\nexamples:\n  - code: |\n      add(1, 2)\n'
    result = sync_docstring(raw, [], '')
    assert 'examples:' in result
    assert 'add(1, 2)' in result


def test_sync_with_visibility_non_default() -> None:
    """
    title: Non-default visibility is preserved.
    """
    raw = 'title: test\nvisibility: private\n'
    result = sync_docstring(raw, [], '', language_defaults=PYTHON_DEFAULTS)
    assert 'visibility: private' in result


def test_sync_omits_default_visibility() -> None:
    """
    title: Default visibility (public) is omitted from output.
    """
    raw = 'title: test\nvisibility: public\n'
    result = sync_docstring(raw, [], '', language_defaults=PYTHON_DEFAULTS)
    assert 'visibility' not in result


def test_sync_with_extra_keys() -> None:
    """
    title: Extra keys like notes are preserved through sync.
    """
    raw = 'title: test\nnotes: important note\n'
    result = sync_docstring(raw, [], '')
    assert 'notes: important note' in result


# -------------------------------------------------------------------
# Coverage: _yaml_scalar edge cases
# -------------------------------------------------------------------


def test_sync_param_with_optional_true() -> None:
    """
    title: 'optional: true is preserved on parameters.'
    """
    raw = 'title: test\nparameters:\n  x:\n    type: int\n    optional: true\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'optional: true' in result


def test_sync_param_with_default_value() -> None:
    """
    title: Default value is preserved on parameters.
    """
    raw = 'title: test\nparameters:\n  x:\n    type: int\n    default: 42\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'default: 42' in result


def test_sync_param_with_special_chars_desc() -> None:
    """
    title: Descriptions with YAML special chars are preserved.
    """
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
    """
    title: cls is excluded from classmethod parameters.
    """
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
    """
    title: Multiple functions in one source are all synced.
    """
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
    """
    title: No return annotation means no returns section.
    """
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


# -------------------------------------------------------------------
# Line-length wrapping (79-char limit)
# -------------------------------------------------------------------


def _long_title_src() -> str:
    """
    title: Build test source with a long | title.
    returns:
      type: str
    """
    long_title = (
        'Everything we need to know about'
        ' a single def / async def / class / module.'
    )
    return (
        'def func(x: int) -> int:\n'
        '    """\n'
        f'        title: |\n'
        f'          {long_title}\n'
        '    """\n'
        '    return x\n'
    )


def test_sync_source_wraps_long_title_block_scalar() -> None:
    """
    title: Long title in | block gets wrapped to stay within 79 chars.
    """
    result = sync_source(_long_title_src())
    for line in result.splitlines():
        assert len(line) <= 79, f'Line too long ({len(line)}): {line!r}'


def test_sync_source_wraps_long_summary_block_scalar() -> None:
    """
    title: Long summary in | block gets wrapped within 79 chars.
    """
    long_summary = (
        'Returns the updated YAML (without'
        ' surrounding triple-quotes). If not'
        ' valid Douki YAML, raises ValueError.'
    )
    src = (
        'def func() -> str:\n'
        '    """\n'
        '        title: Do something.\n'
        f'        summary: |\n'
        f'          {long_summary}\n'
        '    """\n'
        '    return ""\n'
    )
    result = sync_source(src)
    for line in result.splitlines():
        assert len(line) <= 79, f'Line too long ({len(line)}): {line!r}'


def test_sync_wraps_long_block_scalar_idempotent() -> None:
    """
    title: Wrapped block scalars are idempotent.
    """
    first = sync_source(_long_title_src())
    second = sync_source(first)
    assert first == second


def test_emit_key_value_short_block_scalar_inlined() -> None:
    """
    title: Short | values become inline after stripping trailing newline.
    """
    raw = 'title: |\n  Short title\n'
    result = sync_docstring(raw, [], '')
    assert 'title: Short title' in result


def test_sync_source_all_lines_within_79() -> None:
    """
    title: Full integration check for line length.
    """
    long_summary = (
        'This is a very long summary line that'
        ' definitely exceeds seventy-nine characters'
        ' when content indentation is accounted'
        ' for properly.'
    )
    src = (
        'def process(\n'
        '    items: list,\n'
        '    count: int,\n'
        ') -> dict:\n'
        '    """\n'
        '        title: Process items.\n'
        '        summary: |\n'
        f'          {long_summary}\n'
        '        parameters:\n'
        '          items:\n'
        '            type: list\n'
        '          count:\n'
        '            type: int\n'
        '        returns:\n'
        '          type: dict\n'
        '    """\n'
        '    return {}\n'
    )
    result = sync_source(src)
    for i, line in enumerate(result.splitlines(), 1):
        assert len(line) <= 79, f'Line {i} too long ({len(line)}): {line!r}'


# -------------------------------------------------------------------
# Coverage: _annotation_to_str edge cases
# -------------------------------------------------------------------


def test_annotation_constant_repr() -> None:
    """
    title: 'Constant annotation that is not str/None, e.g. x: 42.'
    """
    src = 'def foo(x: 42) -> None:\n    """title: test"""\n    pass\n'
    funcs = extract_functions(src)
    p = next(p for p in funcs[0].params if p.name == 'x')
    assert p.annotation == '42'


def test_annotation_bare_tuple() -> None:
    """
    title: 'Bare tuple return: (int, str).'
    """
    src = 'def foo() -> (int, str):\n    """title: test"""\n    pass\n'
    funcs = extract_functions(src)
    assert 'int' in funcs[0].return_annotation
    assert 'str' in funcs[0].return_annotation


def test_annotation_list_node() -> None:
    """
    title: 'List annotation node: [int, str].'
    """
    src = 'def foo(x: [int, str]) -> None:\n    """title: test"""\n    pass\n'
    funcs = extract_functions(src)
    p = next(p for p in funcs[0].params if p.name == 'x')
    assert 'int' in p.annotation
    assert 'str' in p.annotation


def test_annotation_fallback_unparse() -> None:
    """
    title: Complex annotation that falls through to ast.unparse.
    """
    src = (
        'from typing import Callable\n'
        'def foo(x: Callable[..., int]) -> None:\n'
        '    """title: test"""\n'
        '    pass\n'
    )
    funcs = extract_functions(src)
    # Find the 'foo' function (skip module if present)
    foo = next(f for f in funcs if f.name == 'foo')
    p = next(p for p in foo.params if p.name == 'x')
    assert 'Callable' in p.annotation


# -------------------------------------------------------------------
# Coverage: module and class docstrings
# -------------------------------------------------------------------


def test_extract_module_docstring() -> None:
    """
    title: Module-level docstring should be extracted as <module>.
    """
    src = '"""title: My module"""\n\nx = 42\n'
    funcs = extract_functions(src)
    mod = [f for f in funcs if f.name == '<module>']
    assert len(mod) == 1
    assert mod[0].docstring_node is not None


def test_extract_class_docstring_no_methods() -> None:
    """
    title: Class with docstring but no methods.
    """
    src = 'class Foo:\n    """title: Foo class"""\n    x = 42\n'
    funcs = extract_functions(src)
    cls = [f for f in funcs if f.name == 'Foo']
    assert len(cls) == 1
    assert cls[0].docstring_node is not None


# -------------------------------------------------------------------
# Coverage: _load_docstring_yaml edge cases
# -------------------------------------------------------------------


def test_load_docstring_yaml_single_string() -> None:
    """
    title: Plain single-line string without colon.
    """
    result = _load_docstring_yaml('Hello world')
    assert result == {'title': 'Hello world'}


def test_load_docstring_yaml_multi_line_string() -> None:
    """
    title: Multi-line string without colons.
    """
    # YAML folds newlines in plain scalars, so safe_load joins them.
    # Use literal block to preserve newlines.
    result = _load_docstring_yaml('|\n  First line\n  Second line')
    assert result['title'] == 'First line'
    assert result['summary'] == 'Second line'


def test_load_docstring_yaml_invalid_type() -> None:
    """
    title: Non-dict, non-string YAML (e.g. a list) should raise.
    """
    import pytest

    with pytest.raises(ValueError, match='Invalid Douki YAML'):
        _load_docstring_yaml('[1, 2, 3]')


def test_load_docstring_yaml_bad_yaml() -> None:
    """
    title: Unparseable YAML should raise.
    """
    import pytest

    with pytest.raises(ValueError, match='Could not parse YAML'):
        _load_docstring_yaml(': : : [[[')


# -------------------------------------------------------------------
# Coverage: _extract_returns_desc edge cases
# -------------------------------------------------------------------


def test_extract_returns_desc_list_dict() -> None:
    """
    title: List with dict entry.
    """
    result = _extract_returns_desc(
        [{'description': 'the result', 'type': 'int'}]
    )
    assert result == 'the result'


def test_extract_returns_desc_list_string() -> None:
    """
    title: List with string entry.
    """
    result = _extract_returns_desc(['the result'])
    assert result == 'the result'


def test_extract_returns_desc_empty() -> None:
    """
    title: Non-string, non-list, non-dict returns empty.
    """
    assert _extract_returns_desc(42) == ''


def test_extract_returns_desc_string() -> None:
    """
    title: Plain string returns the string.
    """
    assert _extract_returns_desc('hello') == 'hello'


# -------------------------------------------------------------------
# Coverage: _rebuild_yaml branches (typed_list, raises dict, etc.)
# -------------------------------------------------------------------


def test_sync_with_see_also_list() -> None:
    """
    title: see_also with list of strings hits _emit_typed_list.
    """
    raw = 'title: test\nsee_also:\n  - other_func\n  - another_func\n'
    result = sync_docstring(raw, [], '')
    assert 'see_also:' in result
    assert 'other_func' in result
    assert 'another_func' in result


def test_sync_with_see_also_string() -> None:
    """
    title: see_also as plain string hits _emit_typed_list string path.
    """
    raw = 'title: test\nsee_also: other_func\n'
    result = sync_docstring(raw, [], '')
    assert 'see_also: other_func' in result


def test_sync_with_references_list() -> None:
    """
    title: references as a list.
    """
    raw = (
        'title: test\n'
        'references:\n'
        '  - https://example.com\n'
        '  - https://other.com\n'
    )
    result = sync_docstring(raw, [], '')
    assert 'references:' in result
    assert 'https://example.com' in result


def test_sync_with_raises_dict_format() -> None:
    """
    title: raises as a dict hits _emit_raises dict path.
    """
    raw = 'title: test\nraises:\n  ValueError: bad input\n'
    result = sync_docstring(raw, [], '')
    assert 'raises:' in result
    assert 'ValueError' in result


def test_sync_with_methods_list() -> None:
    """
    title: methods section with list of strings.
    """
    raw = 'title: test\nmethods:\n  - method_one\n  - method_two\n'
    result = sync_docstring(raw, [], '')
    assert 'methods:' in result
    assert 'method_one' in result


def test_sync_with_examples_string_items() -> None:
    """
    title: examples list with plain string items.
    """
    raw = 'title: test\nexamples:\n  - "print(1)"\n  - "print(2)"\n'
    result = sync_docstring(raw, [], '')
    assert 'examples:' in result
    assert 'print(1)' in result


def test_sync_with_example_code_and_description() -> None:
    """
    title: example with both code and description.
    """
    raw = (
        'title: test\n'
        'examples:\n'
        '  - code: |\n'
        '      x = 1\n'
        '    description: Basic assignment\n'
    )
    result = sync_docstring(raw, [], '')
    assert 'examples:' in result
    assert 'x = 1' in result
    assert 'Basic assignment' in result


def test_sync_with_returns_string() -> None:
    """
    title: returns as plain string hits _emit_typed_entry string path.
    """
    raw = 'title: test\nreturns: the result\n'
    result = sync_docstring(raw, [], '')
    assert 'returns: the result' in result


def test_sync_with_yields_dict() -> None:
    """
    title: yields as dict.
    """
    raw = 'title: test\nyields:\n  type: int\n  description: a number\n'
    result = sync_docstring(raw, [], '')
    assert 'yields:' in result
    assert 'type: int' in result


# -------------------------------------------------------------------
# Coverage: _yaml_scalar null
# -------------------------------------------------------------------


def test_yaml_scalar_null() -> None:
    """
    title: None is serialized as null.
    """
    assert _yaml_scalar(None) == 'null'


def test_yaml_scalar_bool() -> None:
    """
    title: Booleans are serialized as true/false.
    """
    assert _yaml_scalar(True) == 'true'
    assert _yaml_scalar(False) == 'false'


# -------------------------------------------------------------------
# Coverage: sync_docstring whitespace-only
# -------------------------------------------------------------------


def test_sync_docstring_whitespace_only() -> None:
    """
    title: Whitespace-only raw returns unchanged.
    """
    raw = '  \n  '
    result = sync_docstring(raw, [], '')
    assert result == raw


# -------------------------------------------------------------------
# Coverage: _emit_key_value wrapping for true multiline
# -------------------------------------------------------------------


def test_sync_wraps_long_line_in_multiline_block() -> None:
    """
    title: A true multi-line block with one very long line wraps it.
    """
    long_line = 'word ' * 20  # ~100 chars
    raw = (
        'title: test\n'
        'summary: |-\n'
        f'  {long_line.strip()}\n'
        '  Short second line.\n'
    )
    result = sync_docstring(raw, [], '')
    for line in result.splitlines():
        assert len(line) <= 79 or ' ' not in line.strip(), (
            f'Line too long: {line!r}'
        )


# -------------------------------------------------------------------
# Coverage: _migrate_numpydoc SyntaxError
# -------------------------------------------------------------------


def test_sync_source_migrate_syntax_error() -> None:
    """
    title: Unparseable source with migrate=numpydoc returns unchanged.
    """
    src = 'def broken( -> None:\n'
    result = sync_source(src, migrate='numpydoc')
    assert result == src


# -------------------------------------------------------------------
# Coverage: sync_source error accumulation (ValueError in sync)
# -------------------------------------------------------------------


def test_sync_source_validation_errors_multiple() -> None:
    """
    title: Multiple invalid docstrings accumulate errors.
    """
    src = (
        'def a() -> None:\n'
        '    """Just plain text."""\n'
        '    pass\n'
        '\n'
        'def b() -> None:\n'
        '    """Also plain text."""\n'
        '    pass\n'
    )
    from douki._base.sync import DocstringValidationError

    with pytest.raises(DocstringValidationError):
        sync_source(src)


# -------------------------------------------------------------------
# Coverage: param with optional=null (skip default)
# -------------------------------------------------------------------


def test_sync_param_optional_null_skipped() -> None:
    """
    title: 'optional: null should be omitted.'
    """
    raw = 'title: test\nparameters:\n  x:\n    type: int\n    optional: null\n'
    params = [_p('x', 'int')]
    result = sync_docstring(raw, params, '')
    assert 'optional' not in result


# -------------------------------------------------------------------
# Coverage: class + method sync_source integration
# -------------------------------------------------------------------


def test_sync_source_class_with_methods() -> None:
    """
    title: Class docstring and method docstrings all get synced.
    """
    src = '''\
class Calculator:
    """
    title: A simple calculator.
    """

    def add(self, a: int, b: int) -> int:
        """
        title: Add two numbers.
        """
        return a + b

    def sub(self, a: int, b: int) -> int:
        """
        title: Subtract b from a.
        """
        return a - b
'''
    result = sync_source(src)
    # Class docstring preserved
    assert 'A simple calculator' in result
    # Both methods get parameters synced (self excluded)
    assert result.count('parameters:') == 2
    assert 'a:' in result
    assert 'b:' in result
    # Return types synced
    assert 'returns:' in result


def test_sync_source_class_with_init() -> None:
    """
    title: Class with __init__ gets init params synced.
    """
    src = '''\
class Point:
    """
    title: A 2D point.
    """

    def __init__(self, x: float, y: float) -> None:
        """
        title: Create a new Point.
        """
        self.x = x
        self.y = y
'''
    result = sync_source(src)
    assert 'A 2D point' in result
    assert 'Create a new Point' in result
    assert 'x:' in result
    assert 'y:' in result
    assert 'type: float' in result
    # __init__ returns None → no returns section
    assert result.count('returns:') == 0


def test_sync_source_staticmethod() -> None:
    """
    title: Static method has no self/cls to skip.
    """
    src = '''\
class Utils:
    """
    title: Utility class.
    """

    @staticmethod
    def clamp(value: int, lo: int, hi: int) -> int:
        """
        title: Clamp value between lo and hi.
        """
        return max(lo, min(value, hi))
'''
    result = sync_source(src)
    assert 'value:' in result
    assert 'lo:' in result
    assert 'hi:' in result
    assert 'type: int' in result


def test_sync_source_class_with_attributes() -> None:
    """
    title: Class docstring with attributes section preserved.
    """
    src = '''\
class Config:
    """
    title: App configuration.
    attributes:
      debug:
        type: bool
        description: Enable debug mode.
      timeout:
        type: int
        description: Request timeout in seconds.
    """

    debug: bool = False
    timeout: int = 30
'''
    result = sync_source(src)
    assert 'attributes:' in result
    assert 'debug:' in result
    assert 'timeout:' in result
    assert 'Enable debug mode' in result


def test_sync_source_class_idempotent() -> None:
    """
    title: Class sync is idempotent.
    """
    src = '''\
class Greeter:
    """
    title: A greeter.
    """

    def greet(self, name: str) -> str:
        """
        title: Greet someone.
        parameters:
          name:
            type: str
            description: The name.
        returns:
          type: str
          description: The greeting.
        """
        return f"Hello {name}"
'''
    first = sync_source(src)
    second = sync_source(first)
    assert first == second


def test_sync_source_class_multiple_methods_all_lines_79() -> None:
    """
    title: Class with methods stays within 79 char limit.
    """
    src = '''\
class MyService:
    """
    title: A service with long descriptions.
    """

    def process(
        self,
        items: list,
        configuration: dict,
    ) -> dict:
        """
        title: Process items with configuration.
        """
        return {}

    def validate(
        self,
        data: dict,
    ) -> bool:
        """
        title: Validate data against schema.
        """
        return True
'''
    result = sync_source(src)
    for i, line in enumerate(result.splitlines(), 1):
        assert len(line) <= 79, f'Line {i} too long ({len(line)}): {line!r}'


def test_sync_source_var_args() -> None:
    """
    title: >-
      Functions with *args and **kwargs use variadic attribute instead of
      quoted keys.
    """
    src = '''\
def flexible_func(*args: int, **kwargs: str) -> None:
    """
    title: A function with arbitrary arguments.
    """
    pass
'''
    result = sync_source(src)
    assert 'args:' in result
    assert 'kwargs:' in result
    assert 'variadic: positional' in result
    assert 'variadic: keyword' in result
    assert "'*args':" not in result
    assert "'**kwargs':" not in result
