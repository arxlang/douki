"""
title: Enrich documentation using language-independent signature metadata.
"""

from __future__ import annotations

import inspect

from dataclasses import dataclass
from typing import Literal, cast

import yaml

from public import private, public
from typeguard import CollectionCheckStrategy, check_type

from douki._base.sync import _KEY_ORDER, _parse_validated_docstring
from douki._base.validation import validate_schema
from douki.typechecking import typechecked

ParameterKind = Literal[
    'regular',
    'positional_only',
    'keyword_only',
    'var_positional',
    'var_keyword',
]


@public
class DocumentationError(ValueError):
    """
    title: A documentation failure with a stable processing phase.
    """

    @typechecked
    def __init__(self, phase: str, message: str) -> None:
        """
        title: Record the phase and diagnostic message.
        """
        self.phase = phase
        self.message = message
        super().__init__(f'{phase}: {message}')


@public
@dataclass(frozen=True)
class Parameter:
    """
    title: A parameter or attribute with a display annotation.
    """

    name: str
    annotation: str = ''
    kind: ParameterKind = 'regular'

    @typechecked
    def __post_init__(self) -> None:
        """
        title: Validate metadata supplied by runtime or static adapters.
        """
        check_type(self.name, str)
        check_type(self.annotation, str)
        check_type(self.kind, ParameterKind)
        if not self.name:
            raise DocumentationError('signature', 'Empty parameter name')


@public
@dataclass(frozen=True)
class Signature:
    """
    title: Types supplied by a language adapter without importing its source.
    summary: Null parameters means this declaration is not a callable.
    """

    parameters: tuple[Parameter, ...] | None = None
    returns: str = ''
    attributes: tuple[Parameter, ...] = ()

    @typechecked
    def __post_init__(self) -> None:
        """
        title: Validate every item in externally supplied metadata.
        """
        check_type(
            self.parameters,
            tuple[Parameter, ...] | None,
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        check_type(self.returns, str)
        check_type(
            self.attributes,
            tuple[Parameter, ...],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        for items in (self.parameters or (), self.attributes):
            names = [item.name for item in items]
            if len(names) != len(set(names)):
                raise DocumentationError('signature', 'Duplicate names')


@private
@typechecked
def entry(value: object) -> dict[str, object]:
    """
    title: Copy a schema-validated field while retaining authored metadata.
    """
    if isinstance(value, str):
        return {'description': value}
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    raise DocumentationError('schema', 'Expected a documentation entry')


@private
@typechecked
def merge_fields(
    existing: dict[str, object],
    parameters: tuple[Parameter, ...],
    *,
    strict: bool,
) -> dict[str, object]:
    """
    title: Merge annotation types without deleting descriptions or fallbacks.
    """
    names = {parameter.name for parameter in parameters}
    if strict and (unknown := set(existing) - names):
        raise DocumentationError(
            'signature',
            'Unknown documented parameters: ' + ', '.join(sorted(unknown)),
        )
    result = dict(existing)
    for parameter in parameters:
        field = entry(existing.get(parameter.name))
        if parameter.annotation:
            field['type'] = parameter.annotation
        if parameter.kind == 'var_positional':
            field['variadic'] = 'positional'
        elif parameter.kind == 'var_keyword':
            field['variadic'] = 'keyword'
        if field or parameter.name in existing:
            result[parameter.name] = field
    return result


@public
@typechecked
def enrich(raw_docstring: str, signature: Signature) -> dict[str, object]:
    """
    title: Return structured documentation enriched with annotation types.
    summary: Annotations take precedence over authored types. Without an
      annotation, an authored type is retained. No objects or source files
      are modified.
    """
    try:
        data = cast(
            dict[str, object],
            _parse_validated_docstring(inspect.cleandoc(raw_docstring)),
        )
    except ValueError as error:
        raise DocumentationError('schema', str(error)) from error
    if signature.parameters is not None:
        parameters = merge_fields(
            cast(dict[str, object], data.get('parameters', {})),
            signature.parameters,
            strict=True,
        )
        if parameters or 'parameters' in data:
            data['parameters'] = parameters
    if signature.attributes:
        data['attributes'] = merge_fields(
            cast(dict[str, object], data.get('attributes', {})),
            signature.attributes,
            strict=False,
        )
    if signature.returns:
        returns = entry(data.get('returns'))
        returns['type'] = signature.returns
        data['returns'] = returns
    return data


@private
class DocumentationDumper(yaml.SafeDumper):
    """
    title: Preserve multiline prose and code as literal YAML strings.
    """


@private
@typechecked
def represent_string(
    dumper: yaml.SafeDumper,
    value: str,
) -> yaml.ScalarNode:
    """
    title: Quote ambiguous scalars and preserve embedded newlines.
    """
    return dumper.represent_scalar(
        'tag:yaml.org,2002:str',
        value,
        style=(
            (
                '|'
                if any(line.startswith(' ') for line in value.splitlines())
                else '>'
            )
            if '\n' in value
            else None
        ),
    )


DocumentationDumper.add_representer(str, represent_string)


@public
@typechecked
def format_documentation(
    data: dict[str, object],
    *,
    width: int = 79,
) -> str:
    """
    title: Serialize validated documentation without changing its content.
    """
    try:
        validate_schema(data)
    except ValueError as error:
        raise DocumentationError('schema', str(error)) from error
    ordered = {key: data[key] for key in _KEY_ORDER if key in data}
    target = max(20, width)
    wrap_width = target
    for _ in range(4):
        text = yaml.dump(
            ordered,
            Dumper=DocumentationDumper,
            sort_keys=False,
            allow_unicode=True,
            width=wrap_width,
        )
        # PyYAML treats width as a hint and can overshoot by one word.
        excess = max(
            (len(line) - target for line in text.splitlines()), default=0
        )
        if excess <= 0 or wrap_width == 20:
            break
        wrap_width = max(20, wrap_width - max(excess, 8))
    return text
