"""
title: Required annotations and source-only schema validation.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import douki
import pytest
import yaml

from douki._base.sync import (
    DocstringValidationError,
    ParamInfo,
    sync_docstring,
    validate_docstring,
)
from douki.cli import app
from douki.sync import sync_source
from typer.testing import CliRunner


@pytest.mark.parametrize(
    'field', ['parameters', 'attributes', 'returns', 'yields', 'receives']
)
def test_source_schema_rejects_type_fields(field: str) -> None:
    """
    title: Type fields are forbidden in every authored annotation entry.
    """
    entry = {'description': 'Details.', 'type': 'int'}
    data = {
        'title': 'Example',
        field: (
            {'value': entry}
            if field in ('parameters', 'attributes')
            else entry
        ),
    }
    raw = yaml.safe_dump(data)
    with pytest.raises(ValueError, match='schema'):
        validate_docstring(raw, 'example')
    with pytest.raises(douki.DocumentationError, match='schema'):
        douki.enrich(raw, douki.Signature())
    with pytest.raises(douki.DocumentationError, match='schema'):
        douki.format_documentation(data)
    assert (
        yaml.safe_load(douki.format_documentation(data, enriched=True)) == data
    )
    # The generated-document validator must not alter the source schema.
    with pytest.raises(ValueError, match='schema'):
        validate_docstring(raw, 'example')


def test_schema_keeps_exception_names_and_arbitrary_defaults() -> None:
    """
    title: Exception names and mapping defaults do not become annotations.
    """
    raw = """title: Example
parameters:
  type:
    description: A parameter named type.
    default: {type: example}
raises:
  ValueError: Invalid value.
warnings:
  RuntimeWarning: Slow operation.
"""
    assert validate_docstring(raw, 'example')
    for field in ('raises', 'warnings'):
        with pytest.raises(ValueError, match='schema'):
            validate_docstring(
                f'title: Example\n{field}: [{{type: ValueError}}]', 'example'
            )


@pytest.mark.parametrize(
    ('definition', 'missing'),
    [
        ('def example(value) -> None:', "parameter 'value'"),
        ('def example(value, /) -> None:', "parameter 'value'"),
        ('def example(*, value) -> None:', "parameter 'value'"),
        ('def example(*args) -> None:', "parameter 'args'"),
        ('def example(**kwargs) -> None:', "parameter 'kwargs'"),
        ('def example(self) -> None:', "parameter 'self'"),
        ('def example(value: int):', 'return value'),
        ('async def example(value: int):', 'return value'),
        ('def example(value: " ") -> None:', "parameter 'value'"),
    ],
)
def test_source_and_runtime_require_all_annotations(
    definition: str, missing: str
) -> None:
    """
    title: Undocumented parameters and return values still require types.
    """
    source = definition + '\n    """title: Example"""\n    pass\n'
    with pytest.raises(DocstringValidationError, match=missing):
        sync_source(source)
    namespace: dict[str, object] = {}
    exec(source, namespace)
    for inspect_doc in (douki.getdoc, douki.help):
        with pytest.raises(douki.DocumentationError, match=missing) as caught:
            inspect_doc(namespace['example'])
        assert caught.value.phase == 'annotations'


def test_shared_api_reports_every_missing_annotation() -> None:
    """
    title: Static documentation collectors receive one actionable diagnostic.
    """
    signature = douki.Signature(
        (douki.Parameter('a'), douki.Parameter('b')),
        attributes=(douki.Parameter('count'),),
    )
    with pytest.raises(douki.DocumentationError) as caught:
        douki.enrich('title: Example', signature)
    for missing in ("parameter 'a'", "parameter 'b'", 'return', "'count'"):
        assert missing in str(caught.value)
    assert caught.value.phase == 'annotations'


@pytest.mark.parametrize('container', ['module', 'class'])
def test_documented_attributes_need_declarations(container: str) -> None:
    """
    title: An attribute value cannot substitute for an annotation.
    """
    raw = 'title: Example\nattributes:\n  count: Number of items.\n'
    obj = (
        ModuleType('example')
        if container == 'module'
        else type('Example', (), {})
    )
    obj.__doc__ = raw
    obj.count = 1
    with pytest.raises(douki.DocumentationError, match="attribute 'count'"):
        douki.getdoc(obj)
    obj.__annotations__ = {'count': int}
    assert (
        yaml.safe_load(douki.getdoc(obj))['attributes']['count']['type']
        == 'int'
    )
    source = '"""' + raw + '"""\ncount = 1\n'
    if container == 'class':
        source = 'class Example:\n' + ''.join(
            '    ' + line for line in source.splitlines(keepends=True)
        )
    with pytest.raises(DocstringValidationError, match="attribute 'count'"):
        sync_source(source)
    assert 'type:' not in sync_source(
        source.replace('count =', 'count: int =')
    )


def test_receivers_are_exempt_by_binding_not_parameter_name() -> None:
    """
    title: Only the bound receiver is exempt from annotation requirements.
    """
    source = '''class Example:
    """title: Example"""
    def method(receiver, value: int) -> None:
        """title: Method"""
    @classmethod
    def create(receiver, value: int) -> None:
        """title: Create"""
    @staticmethod
    def static(self: int) -> None:
        """title: Static"""
'''
    assert sync_source(sync_source(source)) == sync_source(source)
    namespace: dict[str, object] = {}
    exec(source, namespace)
    example = namespace['Example']
    assert 'receiver:' not in douki.getdoc(example().method)
    assert 'receiver:' not in douki.getdoc(example.create)
    assert 'self:' in douki.getdoc(example.static)
    with pytest.raises(DocstringValidationError, match="parameter 'self'"):
        sync_source(source.replace('self: int', 'self'))
    with pytest.raises(DocstringValidationError, match="parameter 'value'"):
        sync_source(source.replace('value: int', 'value'))


def test_annotated_properties_supply_attribute_types() -> None:
    """
    title: Property annotations are read without calling the getter.
    """
    source = '''class Example:
    """
    title: Example
    attributes:
      size: Number of items.
    """
    @property
    def size(self) -> int:
        """title: Size"""
        raise AssertionError('must not call')
'''
    assert 'type:' not in sync_source(source)
    namespace: dict[str, object] = {}
    exec(source, namespace)
    data = yaml.safe_load(douki.getdoc(namespace['Example']))
    assert data['attributes']['size']['type'] == 'int'
    with pytest.raises(
        DocstringValidationError, match='Missing type annotations'
    ):
        sync_source(source.replace(' -> int', ''))


@pytest.mark.parametrize('command', ['check', 'sync', 'migrate'])
def test_cli_rejects_missing_annotations_without_writing(
    command: str, tmp_path: Path
) -> None:
    """
    title: Annotation failures produce exit two and preserve source files.
    """
    source = 'def example(value):\n    """title: Example"""\n    pass\n'
    path = tmp_path / 'example.py'
    path.write_text(source)
    args = [command, str(path)]
    if command == 'migrate':
        args.extend(['--from', 'numpydoc'])
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert "parameter 'value'" in result.output
    assert 'return value' in ' '.join(result.output.split())
    assert path.read_text() == source


def test_missing_annotations_are_aggregated_across_declarations() -> None:
    """
    title: Source diagnostics include every invalid declaration.
    """
    source = '''def first(value) -> None:
    """title: First"""
def second() :
    """title: Second"""
'''
    with pytest.raises(DocstringValidationError) as caught:
        sync_source(source)
    assert "'first': annotations:" in str(caught.value)
    assert "'second': annotations:" in str(caught.value)


def test_explicit_none_forward_refs_and_no_arguments_are_valid() -> None:
    """
    title: Validation checks annotation presence without evaluating names.
    """
    source = '''from __future__ import annotations
def example(value: MissingType) -> None:
    """title: Example"""
def empty() -> None:
    """title: Empty"""
'''
    assert 'type:' not in sync_source(source)
    namespace: dict[str, object] = {}
    exec(source, namespace)
    assert 'MissingType' in douki.getdoc(namespace['example'])
    assert (
        yaml.safe_load(douki.getdoc(namespace['empty']))['returns']['type']
        == 'None'
    )


def test_instance_annotations_respect_scopes_and_inheritance() -> None:
    """
    title: Constructor assignments retain declared and inherited types.
    """
    source = '''class Base:
    """title: Base"""
    count: int
class Child(Base):
    """title: Child"""
    def __init__(receiver) -> None:
        """title: Initialize"""
        receiver.count = 1
        receiver.name = ''
        receiver.name: str
        def nested(self: object) -> None:
            """title: Nested"""
            self.unrelated = 1
'''
    assert 'type:' not in sync_source(source)
    with pytest.raises(DocstringValidationError, match="attribute 'name'"):
        sync_source(source.replace('        receiver.name: str\n', ''))


def test_legacy_expansion_does_not_bypass_annotation_validation() -> None:
    """
    title: Legacy consumers must also supply types for callable metadata.
    """
    with pytest.raises(douki.DocumentationError, match="parameter 'value'"):
        sync_docstring(
            'title: Example', [ParamInfo('value', '', 'regular')], 'None'
        )
    with pytest.raises(douki.DocumentationError, match='return value'):
        sync_docstring(
            'title: Example', [ParamInfo('value', 'int', 'regular')], ''
        )
