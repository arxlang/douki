"""
title: Display annotation-enriched help for registered packages.
"""

from __future__ import annotations

import builtins
import inspect
import pydoc

from types import FunctionType, MethodType, ModuleType
from typing import Callable

from plum import Function, dispatch
from public import private, public

from douki.documentation import (
    DocumentationError,
    Signature,
    enrich,
    format_documentation,
)
from douki.introspection import (
    attributes,
    callable_signature,
    is_douki,
    metadata,
    variants,
)
from douki.typechecking import typechecked

fallback_help: Callable[..., object] = builtins.help
registered_packages: set[str] = set()
no_request = object()


@private
@dispatch
@typechecked
def owner(obj: object) -> str | None:
    """
    title: Leave unsupported objects outside package-specific help.
    parameters:
      obj: Object whose defining module is being checked.
    returns: None when the object has no supported declaration identity.
    """
    return None


@dispatch
@typechecked
def owner(obj: ModuleType) -> str | None:
    """
    title: Identify a module by its full import name.
    parameters:
      obj: Module whose registration scope is being checked.
    returns: The module's full import name.
    """
    return obj.__name__


@dispatch
@typechecked
def owner(obj: FunctionType | MethodType | Function | type) -> str | None:
    """
    title: Use the defining module rather than a re-export location.
    parameters:
      obj: Function, method, dispatch function, or class to locate.
    returns: Defining module name, or None when unavailable.
    """
    name = obj.__module__
    return name if isinstance(name, str) else None


@dispatch
@typechecked
def owner(obj: property) -> str | None:
    """
    title: Locate a property through its getter without calling it.
    parameters:
      obj: Property whose registration scope is being checked.
    returns: The getter's defining module, or None without a getter.
    """
    return owner(obj.fget)


@private
@typechecked
def is_registered(obj: object) -> bool:
    """
    title: Match exact registered modules and their dotted descendants.
    parameters:
      obj: Declaration to check before inspecting its documentation.
    returns: Whether the declaration belongs to a registered package.
    """
    name = owner(obj)
    return name is not None and any(
        name == package or name.startswith(package + '.')
        for package in registered_packages
    )


@private
@typechecked
def own_doc(obj: object) -> str | None:
    """
    title: Read authored prose without inheriting another declaration's docs.
    parameters:
      obj: Declaration whose own docstring is needed.
    returns: Cleaned authored text, or None when absent.
    """
    raw = getattr(obj, '__doc__', None)
    return inspect.cleandoc(raw) if isinstance(raw, str) else None


@private
@typechecked
def variant_text(obj: object, implementation: object) -> str | None:
    """
    title: Use implementation prose for typing overloads without mixing owners.
    parameters:
      obj: Overload declaration whose own prose takes precedence.
      implementation: Registered implementation providing fallback prose.
    returns: Authored overload or implementation text, or None when absent.
    """
    raw = own_doc(obj)
    target = (
        implementation.__func__
        if isinstance(implementation, MethodType)
        else implementation
    )
    # Plum's combined docstring can include implementations from other
    # packages. Each implementation must supply its own prose instead.
    if raw is None and not isinstance(target, Function):
        raw = own_doc(implementation)
    return raw


@private
@dispatch
@typechecked
def help_metadata(obj: object, skip_receiver: bool = False) -> Signature:
    """
    title: Collect callable metadata through the shared fail-closed adapter.
    parameters:
      obj: Registered declaration whose annotations are needed.
      skip_receiver: Whether to omit an unbound method's first parameter.
    returns: Annotation metadata for the supported declaration.
    """
    return metadata(obj, skip_receiver)


@dispatch
@typechecked
def help_metadata(
    obj: type | ModuleType,
    skip_receiver: bool = False,
) -> Signature:
    """
    title: Limit container metadata to registered attribute owners.
    parameters:
      obj: Registered class or module whose fields are being documented.
      skip_receiver: Unused for declarations without a callable signature.
    returns: Attributes declared by registered modules and classes.
    """
    return Signature(attributes=attributes(obj, include=is_registered))


@private
@typechecked
def render_doc(obj: object, raw: str, skip_receiver: bool = False) -> str:
    """
    title: Enrich owned documentation with package-scoped metadata.
    parameters:
      obj: Registered declaration being rendered.
      raw: Authored Douki YAML belonging to the declaration.
      skip_receiver: Whether to omit an unbound method's first parameter.
    returns: Generated YAML containing authored prose and annotation types.
    """
    return format_documentation(
        enrich(raw, help_metadata(obj, skip_receiver)), enriched=True
    )


@private
@typechecked
def members(obj: type | ModuleType) -> list[tuple[str, object, bool]]:
    """
    title: Read container members without evaluating property descriptors.
    parameters:
      obj:
        description: Object whose documentation or members are being inspected.
    returns: Member names, objects, and flags indicating implicit method
      receivers.
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
    title: Leave ordinary Python help unchanged outside documented
      objects.
    parameters:
      obj:
        description: Object whose documentation or members are being
          inspected.
      seen:
        description: Visited object identities, updated to prevent
          recursive traversal.
    returns: Whether the object or any inspected member contains
      Douki documentation.
    """
    if not is_registered(obj) or id(obj) in seen:
        return False
    seen.add(id(obj))
    alternatives = variants(obj)
    if len(alternatives) > 1 or alternatives[0] is not obj:
        return any(
            is_registered(item) and is_douki(variant_text(item, obj))
            for item in alternatives
        )
    if is_douki(own_doc(obj)):
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
        returns: Help text for the object and any supported documented members.
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
        returns: Help text for the object and any supported documented members.
        """
        sections: list[str] = []
        for variant in variants(obj):
            if not is_registered(variant):
                sections.append(str(pydoc.plaintext.document(variant, name)))
                continue
            raw = variant_text(variant, obj)
            if raw is None or not is_douki(raw):
                sections.append(str(pydoc.plaintext.document(variant, name)))
                continue
            signature = callable_signature(variant)
            if skip_receiver:
                signature = signature.replace(
                    parameters=list(signature.parameters.values())[1:],
                )
            rendered = render_doc(variant, raw, skip_receiver)
            sections.append(f'{name}{signature}\n{rendered}')
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
        returns: Help text for the object and any supported documented members.
        """
        return f'{name} (property)\n{render_doc(obj, own_doc(obj) or "")}'

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
        returns: Help text for the object and any supported documented members.
        """
        if id(obj) in self.seen:
            return f'{name} (already documented)'
        self.seen.add(id(obj))
        raw = own_doc(obj)
        documentation = (
            render_doc(obj, raw)
            if raw is not None and is_douki(raw)
            else inspect.getdoc(obj) or ''
        )
        sections = [name, documentation]
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
    title: Route registered objects to Douki and other requests to Python
      help.
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
def register(package: str) -> None:
    """
    title: Register a library for annotation-enriched help.
    summary: Call once from the library's __init__.py using __name__.
      Registration includes future submodules without importing them.
      Other packages continue to use the previously installed help
      helper.
    parameters:
      package: Full module or package import name to register.
    raises:
      DocumentationError: The name is empty or is not a dotted identifier.
    """
    global fallback_help
    if not all(part.isidentifier() for part in package.split('.')):
        raise DocumentationError('registration', 'Expected a dotted name')
    # Install once. A later helper may delegate back to ours, so capturing
    # it again would create a recursion cycle or overwrite another hook.
    if not registered_packages and builtins.help is not help:
        fallback_help = builtins.help
        setattr(builtins, 'help', help)
    registered_packages.add(package)
