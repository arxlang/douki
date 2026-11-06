"""
title: Shared documentation enrichment and lossless YAML formatting.
"""

from __future__ import annotations

import ast
import copy

import pytest
import yaml

from douki import (
    DocumentationError,
    Parameter,
    Signature,
    enrich,
    format_documentation,
)
from douki.sync import sync_source
from typeguard import TypeCheckError


def test_enrichment_uses_annotations_and_preserves_authored_fields() -> None:
    """
    title: Required annotations supply types while descriptions are preserved.
    """
    raw = """title: Send a message
parameters:
  name:
    description: Person to greet.
    default: null
  count:
    description: How many times.
  args:
    description: Other names.
returns: >-
  The message.
notes: Keep this note.
"""
    signature = Signature(
        (
            Parameter('name', 'str'),
            Parameter('count', 'int'),
            Parameter('args', 'str', 'var_positional'),
        ),
        'str',
    )
    before = copy.deepcopy(signature)
    result = enrich(raw, signature)
    assert result['parameters'] == {
        'name': {
            'type': 'str',
            'description': 'Person to greet.',
            'default': None,
        },
        'count': {'type': 'int', 'description': 'How many times.'},
        'args': {
            'description': 'Other names.',
            'type': 'str',
            'variadic': 'positional',
        },
    }
    assert result['returns'] == {
        'description': 'The message.',
        'type': 'str',
    }
    assert result['notes'] == 'Keep this note.'
    assert (
        yaml.safe_load(format_documentation(result, enriched=True)) == result
    )
    with pytest.raises(DocumentationError, match='schema'):
        enrich(format_documentation(result, enriched=True), signature)
    assert signature == before


def test_unknown_parameters_fail_at_the_shared_boundary() -> None:
    """
    title: A renamed argument does not silently discard its documentation.
    """
    with pytest.raises(DocumentationError, match=r'signature:.*obsolete'):
        enrich(
            'title: Example\nparameters:\n  obsolete: Details',
            Signature((Parameter('current', 'int'),), 'None'),
        )


@pytest.mark.parametrize(
    'raw',
    [
        'title: [',
        'title: Example\nextra: forbidden',
        'title: Example\nparameters:\n  value: null',
        'ordinary prose',
    ],
)
def test_invalid_documents_have_a_phase(raw: str) -> None:
    """
    title: Invalid documents fail before annotation enrichment.
    """
    with pytest.raises(DocumentationError) as caught:
        enrich(raw, Signature())
    assert caught.value.phase == 'schema'


def test_metadata_validates_all_items_and_duplicate_names() -> None:
    """
    title: Invalid later collection items cannot evade runtime validation.
    """
    with pytest.raises(TypeCheckError):
        Signature((Parameter('good'), object()))  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        Signature(attributes=(Parameter('good'), 1))  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        Parameter(1)  # type: ignore[arg-type]
    with pytest.raises(TypeCheckError):
        Parameter('x', kind='unknown')  # type: ignore[arg-type]
    with pytest.raises(DocumentationError, match='Empty'):
        Parameter('')
    with pytest.raises(DocumentationError, match='Duplicate'):
        Signature((Parameter('x'), Parameter('x')))
    with pytest.raises(TypeCheckError):
        enrich('title: Test', object())  # type: ignore[arg-type]


def test_formatting_preserves_yaml_values() -> None:
    """
    title: Preserve ambiguous strings, empty maps and null defaults.
    """
    data: dict[str, object] = {
        'title': 'on',
        'summary': 'A long paragraph. ' * 10 + '\nNext paragraph.\n',
        'parameters': {
            'yes': {},
            'value': {'description': 'null', 'default': None},
        },
        'attributes': {
            'state': {
                'visibility': 'private',
                'scope': 'class',
                'mutability': 'mutable',
            },
        },
        'examples': [{'code': 'if enabled:\n    print("yes")\n'}],
        'returns': None,
    }
    before = copy.deepcopy(data)
    text = format_documentation(data)
    assert yaml.safe_load(text) == data
    assert format_documentation(yaml.safe_load(text)) == text
    assert data == before
    with pytest.raises(DocumentationError):
        format_documentation({'title': 'Test', 'unknown': 1})


def test_format_source_does_not_add_or_remove_signature_fields() -> None:
    """
    title: Source formatting leaves descriptions authored.
    """
    source = '''def changed(current: int) -> None:
    """
    returns: {description: Retain even for None.}
    parameters: {old: {description: Review this rename.}}
    title: Changed signature
    """
    return None
'''
    formatted = sync_source(source)
    original_tree = ast.parse(source)
    formatted_tree = ast.parse(formatted)
    raw = ast.get_docstring(original_tree.body[0])
    result = ast.get_docstring(formatted_tree.body[0])
    assert yaml.safe_load(raw) == yaml.safe_load(result)
    assert 'current:' not in result
    assert sync_source(formatted) == formatted
    assert ast.dump(original_tree.body[0].args) == ast.dump(
        formatted_tree.body[0].args,
    )


def test_static_adapter_matches_runtime_without_importing_source() -> None:
    """
    title: Static tools can enrich source that would fail when imported.
    """
    source = '''raise RuntimeError("must not import")
def greet(name: str, *, count: int = 1) -> str:
    """
    title: Greet someone
    parameters:
      name: Person to greet.
      count: Number of greetings.
    returns: The name repeated for each greeting.
    """
    return name * count
'''
    node = ast.parse(source).body[1]
    assert isinstance(node, ast.FunctionDef)
    signature = Signature(
        tuple(
            Parameter(arg.arg, ast.unparse(arg.annotation))
            for arg in node.args.args + node.args.kwonlyargs
        ),
        ast.unparse(node.returns),
    )
    raw = ast.get_docstring(node)
    assert raw is not None
    data = enrich(raw, signature)
    assert data['parameters']['name'] == {
        'description': 'Person to greet.',
        'type': 'str',
    }
    assert data['returns'] == {
        'description': 'The name repeated for each greeting.',
        'type': 'str',
    }
    assert 'type:' not in raw


@pytest.mark.parametrize(
    'literal',
    [
        r"'''title: Test\nnotes: 'C:\\new\\folder'\n'''",
        "'''title: Test\nnotes: 'three \"\"\" quotes'\n'''",
    ],
)
def test_source_formatting_preserves_python_string_escaping(
    literal: str,
) -> None:
    """
    title: YAML serialization must also remain a valid Python string literal.
    """
    source = (
        'def f() -> int:\n    '
        + literal
        + '  # retain this comment\n    return 1\n'
    )
    formatted = sync_source(source)
    before = ast.get_docstring(ast.parse(source).body[0])
    after = ast.get_docstring(ast.parse(formatted).body[0])
    assert yaml.safe_load(before) == yaml.safe_load(after)
    assert '# retain this comment' in formatted
    assert sync_source(formatted) == formatted


def test_inline_unicode_docstring_keeps_surrounding_code() -> None:
    """
    title: UTF-8 AST columns retain inline function definitions and returns.
    """
    source = 'def café(x: int) -> int: """title: Café"""; return x\n'
    result = sync_source(source)
    namespace: dict[str, object] = {}
    exec(result, namespace)
    assert namespace['café'](3) == 3
    assert sync_source(result) == result
