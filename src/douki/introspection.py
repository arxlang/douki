"""
title: Read Python annotations for documentation without resolving hints.
"""

from __future__ import annotations

import inspect
import sys
import typing

from collections.abc import Sequence
from types import FunctionType, MethodType, ModuleType

import yaml

from plum import Function, Method, dispatch
from public import private, public

from douki.documentation import (
    DocumentationError,
    Parameter,
    ParameterKind,
    Signature,
    enrich,
    format_documentation,
)
from douki.typechecking import typechecked


@private
@typechecked
def display_annotation(value: object) -> str:
    """
    title: Keep forward references as text instead of evaluating them.
    parameters:
      value:
        description: Annotation value or the inspect sentinel for a missing
          annotation.
    returns: Readable annotation text, or an empty string for the missing
      sentinel.
    """
    if value is inspect.Signature.empty:
        return ''
    if isinstance(value, str):
        return value
    if value is None:
        return 'None'
    return inspect.formatannotation(value)


@private
@typechecked
def callable_signature(obj: object) -> inspect.Signature:
    """
    title: Use string annotation retrieval on Python 3.14 and later.
    parameters:
      obj:
        description: Declaration whose documentation or annotation metadata
          is needed.
    returns: Python signature with forward references left unevaluated.
    """
    if not callable(obj):
        raise DocumentationError('signature', 'Object is not callable')
    try:
        if sys.version_info >= (3, 14):
            import annotationlib

            return inspect.signature(
                obj,
                annotation_format=annotationlib.Format.STRING,
            )
        return inspect.signature(obj, eval_str=False)
    except (TypeError, ValueError) as error:
        raise DocumentationError('signature', str(error)) from error


@private
@typechecked
def callable_metadata(obj: object, skip_receiver: bool) -> Signature:
    """
    title: Adapt a Python signature to the language-independent contract.
    parameters:
      obj:
        description: Declaration whose documentation or annotation metadata
          is needed.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound method.
    returns: Language-independent parameter and return annotation metadata.
    """
    signature = callable_signature(obj)
    values = list(signature.parameters.values())
    if skip_receiver:
        values = values[1:]
    kinds: dict[inspect._ParameterKind, ParameterKind] = {
        inspect.Parameter.POSITIONAL_ONLY: 'positional_only',
        inspect.Parameter.POSITIONAL_OR_KEYWORD: 'regular',
        inspect.Parameter.KEYWORD_ONLY: 'keyword_only',
        inspect.Parameter.VAR_POSITIONAL: 'var_positional',
        inspect.Parameter.VAR_KEYWORD: 'var_keyword',
    }
    return Signature(
        parameters=tuple(
            Parameter(
                parameter.name,
                display_annotation(parameter.annotation),
                kinds[parameter.kind],
            )
            for parameter in values
        ),
        returns=display_annotation(signature.return_annotation),
    )


@private
@typechecked
def attributes(obj: type | ModuleType) -> tuple[Parameter, ...]:
    """
    title: Read declared attributes without evaluating forward references.
    parameters:
      obj:
        description: Declaration whose documentation or annotation metadata
          is needed.
    returns: Declared attribute annotations, including inherited fields and
      properties.
    """
    owners = reversed(obj.__mro__) if isinstance(obj, type) else [obj]
    result: dict[str, Parameter] = {}
    for owner in owners:
        if sys.version_info >= (3, 14):
            import annotationlib

            annotations = annotationlib.get_annotations(
                owner,
                format=annotationlib.Format.STRING,
            )
        else:
            annotations = inspect.get_annotations(owner, eval_str=False)
        for name, value in annotations.items():
            result[name] = Parameter(name, display_annotation(value))
        for name, value in vars(owner).items():
            if isinstance(value, property):
                annotation = (
                    display_annotation(
                        callable_signature(value.fget).return_annotation
                    )
                    if value.fget is not None
                    else ''
                )
                result[name] = Parameter(name, annotation)
    return tuple(result.values())


@private
@dispatch
@typechecked
def metadata(obj: object, skip_receiver: bool = False) -> Signature:
    """
    title: Reject unsupported annotation sources explicitly.
    parameters:
      obj:
        description: Declaration whose documentation or annotation
          metadata is needed.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound
          method.
    returns: Language-independent signature or attribute metadata
      for a supported declaration.
    """
    raise DocumentationError(
        'signature',
        f'Unsupported declaration: {type(obj).__name__}',
    )


@dispatch
@typechecked
def metadata(
    obj: FunctionType | MethodType,
    skip_receiver: bool = False,
) -> Signature:
    """
    title: Collect ordinary functions and bound methods.
    parameters:
      obj:
        description: Declaration whose documentation or annotation
          metadata is needed.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound
          method.
    returns: Language-independent signature or attribute metadata
      for a supported declaration.
    """
    return callable_metadata(obj, skip_receiver)


@dispatch
@typechecked
def metadata(
    obj: type | ModuleType,
    skip_receiver: bool = False,
) -> Signature:
    """
    title: Collect module and class attribute annotations.
    parameters:
      obj:
        description: Declaration whose documentation or annotation
          metadata is needed.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound
          method.
    returns: Language-independent signature or attribute metadata
      for a supported declaration.
    """
    return Signature(attributes=attributes(obj))


@dispatch
@typechecked
def metadata(obj: property, skip_receiver: bool = False) -> Signature:
    """
    title: Document a property's getter without executing it.
    parameters:
      obj:
        description: Declaration whose documentation or annotation
          metadata is needed.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound
          method.
    returns: Language-independent signature or attribute metadata
      for a supported declaration.
    """
    if obj.fget is None:
        return Signature()
    return callable_metadata(obj.fget, True)


@private
@typechecked
def is_douki(raw: str | None) -> bool:
    """
    title: Recognize literal Douki YAML including quoted and flow-style keys.
    parameters:
      raw:
        description: Cleaned docstring text, or None when no docstring exists.
    returns: Whether the docstring parses as a mapping containing a title key.
    """
    if raw is None:
        return False
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        if raw.lstrip().startswith('title:'):
            raise DocumentationError('schema', str(error)) from error
        return False
    return isinstance(data, dict) and 'title' in data


@public
@typechecked
def getdoc(obj: object, *, skip_receiver: bool = False) -> str | None:
    """
    title: Return enriched Douki YAML or an ordinary cleaned docstring.
    summary: The object's original __doc__ is never changed.
    parameters:
      obj:
        description: Declaration whose documentation or annotation metadata
          is needed.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound method.
    returns: Enriched Douki YAML, cleaned ordinary prose, or None when no
      docstring exists.
    """
    alternatives = variants(obj)
    if len(alternatives) > 1 or alternatives[0] is not obj:
        documents = [
            variant_doc(variant, obj, skip_receiver)
            for variant in alternatives
        ]
        return '\n---\n'.join(doc for doc in documents if doc) or None
    raw = inspect.getdoc(obj)
    if raw is None:
        return None
    # Ordinary prose remains ordinary prose. A title key opts into Douki.
    if not is_douki(raw):
        return raw
    return format_documentation(
        enrich(raw, metadata(obj, skip_receiver)), enriched=True
    )


@private
@typechecked
def variants(obj: object) -> tuple[object, ...]:
    """
    title: Retain distinct typing overloads and Plum implementations.
    parameters:
      obj:
        description: Declaration whose documentation or annotation metadata
          is needed.
    returns: Distinct overload implementations, or the original object as
      a single item.
    """
    target = obj.__func__ if isinstance(obj, MethodType) else obj
    if isinstance(obj, Function) or (
        isinstance(obj, MethodType) and hasattr(target, 'methods')
    ):
        methods = getattr(target, 'methods')
        if not isinstance(methods, Sequence) or not all(
            isinstance(method, Method) for method in methods
        ):
            raise DocumentationError('signature', 'Invalid dispatch methods')
        implementations = tuple(
            dict.fromkeys(method.implementation for method in methods)
        )
        if not implementations:
            raise DocumentationError('signature', 'No dispatch methods')
        if isinstance(obj, MethodType):
            return tuple(MethodType(f, obj.__self__) for f in implementations)
        return implementations
    if isinstance(target, FunctionType) and hasattr(typing, 'get_overloads'):
        overloads = typing.get_overloads(target)
        if overloads:
            if isinstance(obj, MethodType):
                return tuple(MethodType(f, obj.__self__) for f in overloads)
            return tuple(overloads)
    return (obj,)


@private
@typechecked
def variant_doc(
    obj: object,
    implementation: object,
    skip_receiver: bool,
) -> str | None:
    """
    title: Combine each overload's types with its own or implementation prose.
    parameters:
      obj:
        description: Declaration whose documentation or annotation metadata
          is needed.
      implementation:
        description: Implementation supplying prose when an overload has
          no docstring.
      skip_receiver:
        description: Whether to omit the first parameter of an unbound method.
    returns: Enriched variant documentation, ordinary prose, or None when
      absent.
    """
    raw = inspect.getdoc(obj) or inspect.getdoc(implementation)
    if raw is None:
        return None
    if not is_douki(raw):
        return raw
    return format_documentation(
        enrich(raw, metadata(obj, skip_receiver)), enriched=True
    )
