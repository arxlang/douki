"""
title: Display annotation-enriched help with explicit session activation.
"""

from __future__ import annotations

import builtins
import inspect
import pydoc

from types import FunctionType, MethodType, ModuleType
from typing import Callable

from plum import Function, dispatch
from public import private, public

from douki.introspection import (
    callable_signature,
    getdoc,
    is_douki,
    variant_doc,
    variants,
)
from douki.typechecking import typechecked

fallback_help: Callable[..., object] = builtins.help
previous_help: Callable[..., object] | None = None
no_request = object()


@private
@typechecked
def members(obj: type | ModuleType) -> list[tuple[str, object, bool]]:
    """
    title: Read container members without evaluating property descriptors.
    parameters:
      obj:
        description: Object whose documentation or members are being inspected.
    returns:
      description: Member names, objects, and flags indicating implicit
        method receivers.
    """
    values: dict[str, object] = {}
    if isinstance(obj, type):
        for owner in reversed(obj.__mro__[:-1]):
            values.update(vars(owner))
    else:
        values.update(vars(obj))
    exports = values.get('__all__') if isinstance(obj, ModuleType) else None
    result: list[tuple[str, object, bool]] = []
    for name, value in values.items():
        if isinstance(obj, ModuleType):
            if isinstance(exports, (list, tuple)):
                if name not in exports:
                    continue
            elif getattr(value, '__module__', None) != obj.__name__:
                continue
        skip = isinstance(obj, type) and isinstance(
            value,
            (FunctionType, Function),
        )
        if isinstance(value, (staticmethod, classmethod)):
            skip = isinstance(value, classmethod)
            value = value.__func__
        if (
            isinstance(value, (Function, type, property))
            or inspect.isroutine(value)
            or isinstance(exports, (list, tuple))
        ):
            result.append((name, value, skip))
    return result


@private
@typechecked
def contains_douki(obj: object, seen: set[int]) -> bool:
    """
    title: Leave ordinary Python help unchanged outside documented objects.
    parameters:
      obj:
        description: Object whose documentation or members are being
          inspected.
      seen:
        description: Visited object identities, updated to prevent recursive
          traversal.
    returns:
      description: Whether the object or any inspected member contains
        Douki documentation.
    """
    if id(obj) in seen:
        return False
    seen.add(id(obj))
    alternatives = variants(obj)
    if len(alternatives) > 1 or alternatives[0] is not obj:
        return any(
            is_douki(inspect.getdoc(item) or inspect.getdoc(obj))
            for item in alternatives
        )
    if is_douki(inspect.getdoc(obj)):
        return True
    if isinstance(obj, (type, ModuleType)):
        return any(contains_douki(item, seen) for _, item, _ in members(obj))
    return False


@private
class Renderer:
    """
    title: Render documentation without mutating objects or pydoc globals.
    """

    @typechecked
    def __init__(self) -> None:
        """
        title: Track visited containers to avoid alias cycles.
        """
        self.seen: set[int] = set()

    @dispatch
    @typechecked
    def visit(
        self,
        obj: object,
        name: str,
        skip_receiver: bool = False,
    ) -> str:
        """
        title: Use standard Python documentation for other member types.
        parameters:
          obj:
            description: Object whose documentation or members are being
              inspected.
          name:
            description: Display name for the object in the rendered help.
          skip_receiver:
            description: Whether to omit the first parameter of an unbound
              method.
        returns:
          description: Help text for the object and any supported documented
            members.
        """
        return str(pydoc.plaintext.document(obj, name))

    @dispatch
    @typechecked
    def visit(
        self,
        obj: FunctionType | MethodType | Function,
        name: str,
        skip_receiver: bool = False,
    ) -> str:
        """
        title: Render each callable variant with its own annotation types.
        parameters:
          obj:
            description: Object whose documentation or members are being
              inspected.
          name:
            description: Display name for the object in the rendered help.
          skip_receiver:
            description: Whether to omit the first parameter of an unbound
              method.
        returns:
          description: Help text for the object and any supported documented
            members.
        """
        sections: list[str] = []
        for variant in variants(obj):
            signature = callable_signature(variant)
            if skip_receiver:
                signature = signature.replace(
                    parameters=list(signature.parameters.values())[1:],
                )
            raw = variant_doc(variant, obj, skip_receiver) or ''
            sections.append(f'{name}{signature}\n{raw}')
        return '\n\n'.join(sections)

    @dispatch
    @typechecked
    def visit(
        self,
        obj: property,
        name: str,
        skip_receiver: bool = False,
    ) -> str:
        """
        title: Show property documentation without invoking its getter.
        parameters:
          obj:
            description: Object whose documentation or members are being
              inspected.
          name:
            description: Display name for the object in the rendered help.
          skip_receiver:
            description: Whether to omit the first parameter of an unbound
              method.
        returns:
          description: Help text for the object and any supported documented
            members.
        """
        return f'{name} (property)\n{getdoc(obj) or ""}'

    @dispatch
    @typechecked
    def visit(
        self,
        obj: type | ModuleType,
        name: str,
        skip_receiver: bool = False,
    ) -> str:
        """
        title: Include documented members and guard against recursive aliases.
        parameters:
          obj:
            description: Object whose documentation or members are being
              inspected.
          name:
            description: Display name for the object in the rendered help.
          skip_receiver:
            description: Whether to omit the first parameter of an unbound
              method.
        returns:
          description: Help text for the object and any supported documented
            members.
        """
        if id(obj) in self.seen:
            return f'{name} (already documented)'
        self.seen.add(id(obj))
        sections = [name, getdoc(obj) or '']
        for member_name, member, skip in members(obj):
            if contains_douki(member, set()):
                sections.append(self.visit(member, member_name, skip))
            else:
                sections.append(
                    str(
                        pydoc.plaintext.document(
                            member,
                            member_name,
                        )
                    )
                )
        return '\n\n'.join(section for section in sections if section)


@public
@typechecked
def help(request: object = no_request) -> None:
    """
    title: Display enriched object help and retain Python's topic interface.
    summary: No-argument interactive help and string topics use Python help.
    parameters:
      request:
        description: Object or topic to document; omitting it opens interactive
          Python help.
    """
    if request is no_request:
        fallback_help()
    elif isinstance(request, str):
        fallback_help(request)
    elif contains_douki(request, set()):
        name = getattr(request, '__name__', type(request).__name__)
        pydoc.pager('Help on ' + Renderer().visit(request, name) + '\n')
    else:
        fallback_help(request)


@public
@typechecked
def setup() -> None:
    """
    title: Enable enriched built-in help for this interpreter session.
    """
    global previous_help, fallback_help
    if builtins.help is help:
        return
    previous_help = builtins.help
    fallback_help = builtins.help
    setattr(builtins, 'help', help)


@public
@typechecked
def restore_help() -> None:
    """
    title: Restore the helper replaced by setup without undoing other hooks.
    """
    global previous_help
    if previous_help is not None and builtins.help is help:
        setattr(builtins, 'help', previous_help)
    previous_help = None
