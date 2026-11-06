"""
title: Dynamic documentation, object help and explicit session setup.
"""

from __future__ import annotations

import builtins
import inspect
import pydoc
import sys

from types import ModuleType

import douki
import pytest
import yaml

from douki import helping
from douki.introspection import callable_signature, metadata
from douki.typechecking import typechecked
from plum import dispatch


def greet(name: str, /, *others: str, count: int = 1, **options: bool) -> str:
    """
    title: Greet someone.
    parameters:
      name: The person's name.
      others: More people.
      count: Number of greetings.
      options: Greeting options.
    """
    return name * count


def test_getdoc_enriches_without_mutation_or_calling() -> None:
    """
    title: Lazy enrichment preserves identity, behavior and stored metadata.
    """
    doc = greet.__doc__
    annotations = dict(greet.__annotations__)
    data = yaml.safe_load(douki.getdoc(greet))
    assert data['parameters']['name']['type'] == 'str'
    assert data['parameters']['others']['variadic'] == 'positional'
    assert data['parameters']['options']['variadic'] == 'keyword'
    assert data['returns']['type'] == 'str'
    assert greet.__doc__ == doc
    assert greet.__annotations__ == annotations
    assert greet('Ada', count=2) == 'AdaAda'
    assert douki.getdoc(greet) == douki.getdoc(greet)


def test_forward_references_and_typeguard_wrapper() -> None:
    """
    title: Documentation does not resolve missing type-only imports.
    """

    @typechecked
    def typed(value: MissingType) -> list[MissingType]:  # noqa: F821
        """
        title: Forward references
        """
        raise AssertionError('never call')

    text = douki.getdoc(typed)
    assert 'MissingType' in text
    assert 'list[MissingType]' in text


def test_evaluated_annotations_and_none_return() -> None:
    """
    title: Eager annotation values are displayed consistently.
    """

    def eager(value: object) -> None:
        """
        title: Eager annotations
        """

    eager.__annotations__ = {'value': list[str], 'return': None}
    data = yaml.safe_load(douki.getdoc(eager))
    assert data['parameters']['value']['type'] == 'list[str]'
    assert data['returns']['type'] == 'None'


def test_setup_is_explicit_idempotent_and_reversible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Setup intercepts object help and restores the original helper.
    """
    original = builtins.help
    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    try:
        douki.setup()
        douki.setup()
        assert builtins.help is douki.help
        help(greet)
        assert 'type: str' in output[0]
        assert 'type:' not in greet.__doc__
    finally:
        douki.restore_help()
    assert builtins.help is original
    douki.restore_help()
    assert builtins.help is original


def test_restore_does_not_overwrite_another_tools_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Restoration respects a helper installed after Douki.
    """
    original = builtins.help
    try:
        douki.setup()
        monkeypatch.setattr(builtins, 'help', print)
        douki.restore_help()
        assert builtins.help is print
    finally:
        monkeypatch.setattr(builtins, 'help', original)
        monkeypatch.setattr(helping, 'fallback_help', original)


def test_topics_interactive_help_and_other_objects_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Non-object help requests retain the normal Python interface.
    """
    calls: list[tuple[object, ...]] = []

    def record(*args: object) -> None:
        """
        title: Record delegated help requests
        """
        calls.append(args)

    monkeypatch.setattr(helping, 'fallback_help', record)
    douki.help()
    douki.help('keywords')
    douki.help(42)
    assert calls == [(), ('keywords',), (42,)]


def test_classes_properties_receivers_and_module_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Class and module help enrich members without invoking properties.
    """

    class Base:
        """
        title: Base
        """

        count: int

        def method(self, value: int) -> int:
            """
            title: Method
            """
            raise AssertionError('never call')

    class Example(Base):
        """
        title: Example
        """

        count: float

        @property
        def size(self) -> int:
            """
            title: Size
            """
            raise AssertionError('never call')

        @staticmethod
        def static(self: str) -> str:
            """
            title: A static parameter really named self
            """
            raise AssertionError('never call')

        @classmethod
        def create(cls, value: bool) -> Example:
            """
            title: Create
            """
            raise AssertionError('never call')

    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.help(Example)
    assert 'type: float' in output[0]
    assert 'size (property)' in output[0]
    assert 'self:\n    type: str' in output[0]
    assert 'cls:' not in output[0]
    assert 'method(value:' in output[0]
    module = ModuleType('test_helping_example')
    module.__doc__ = 'title: Test module'
    module.Example = Example
    Example.__module__ = module.__name__
    douki.help(module)
    assert 'size (property)' in output[1]
    assert 'type: float' in output[1]
    assert 'type: bool' in douki.getdoc(Example.create)
    assert 'type: int' in douki.getdoc(Example().method)
    assert 'type: int' in douki.getdoc(Example.size)


def test_plum_variants_keep_their_own_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Dispatch overloads retain separate documentation and result types.
    """

    @dispatch
    def choose(value: int) -> int:
        """
        title: Integer variant
        """
        return value

    @dispatch
    def choose(value: str) -> str:  # noqa: F811
        """
        title: String variant
        """
        return value

    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.help(choose)
    assert 'type: int' in output[0]
    assert 'type: str' in output[0]
    documents = list(yaml.safe_load_all(douki.getdoc(choose)))
    assert {doc['returns']['type'] for doc in documents} == {'int', 'str'}


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason='typing.get_overloads was added in Python 3.11',
)
def test_typing_overloads_inherit_prose_but_not_types() -> None:
    """
    title: Overload types come from each declaration, not implementation.
    """

    namespace = {'__name__': __name__}
    exec(
        'from typing import overload\n'
        '@overload\n'
        'def convert(value: int) -> int: ...\n'
        '@overload\n'
        'def convert(value: str) -> str: ...\n'
        'def convert(value: int | str) -> int | str:\n'
        '    """title: Convert a value"""\n'
        '    return value\n',
        namespace,
    )
    convert = namespace['convert']
    documents = list(yaml.safe_load_all(douki.getdoc(convert)))
    assert {doc['returns']['type'] for doc in documents} == {'int', 'str'}
    assert all(doc['title'] == 'Convert a value' for doc in documents)


def test_plain_docstrings_missing_docs_and_unsupported_metadata() -> None:
    """
    title: Ordinary inspection works and unsupported metadata fails clearly.
    """
    assert douki.getdoc(len) == inspect.getdoc(len)
    assert douki.getdoc(ModuleType('empty')) is None
    with pytest.raises(douki.DocumentationError, match='Unsupported'):
        metadata(42)
    with pytest.raises(douki.DocumentationError, match='not callable'):
        callable_signature(42)
    assert douki.getdoc(property()) is None


def test_normal_functions_and_modules_use_original_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Installing Douki does not replace standard documentation elsewhere.
    """
    calls: list[object] = []
    monkeypatch.setattr(helping, 'fallback_help', calls.append)
    douki.help(len)
    douki.help(sys)
    assert calls == [len, sys]


def test_module_exports_and_recursive_class_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Explicit re-exports are enriched and alias cycles terminate.
    """

    class Container:
        """
        title: Recursive container
        """

    Container.alias = Container
    module = ModuleType('exported')
    module.__all__ = ['Container', 'greet', 'answer']
    module.Container = Container
    module.greet = greet
    module.answer = 42
    module.hidden = greet
    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.help(module)
    assert 'already documented' in output[0]
    assert 'type: str' in output[0]
    assert 'answer = 42' in output[0]
    assert 'hidden' not in output[0]


def test_getdoc_accepts_flow_yaml_and_reports_invalid_douki() -> None:
    """
    title: Douki detection honors YAML syntax and keeps validation errors.
    """

    def example(value: str) -> str:
        """
        title: Flow YAML
        parameters:
          value: Description
        """
        return value

    assert 'type: str' in douki.getdoc(example)
    example.__doc__ = 'title: ['
    with pytest.raises(douki.DocumentationError, match='schema'):
        douki.getdoc(example)


def test_bound_plum_methods_keep_variants_and_remove_receivers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Bound dispatch methods use variant metadata, not concatenated prose.
    """

    class Converter:
        """
        title: Converter
        """

        @dispatch
        def convert(self, value: int) -> int:
            """
            title: Integer
            """
            return value

        @dispatch
        def convert(self, value: str) -> str:  # noqa: F811
            """
            title: Text
            """
            return value

    method = Converter().convert
    documents = list(yaml.safe_load_all(douki.getdoc(method)))
    assert {doc['returns']['type'] for doc in documents} == {'int', 'str'}
    assert all('self' not in doc['parameters'] for doc in documents)
    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.help(method)
    assert 'type: int' in output[0]
    assert 'type: str' in output[0]
    assert '(self' not in output[0]
