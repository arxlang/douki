"""
title: Python AST-based function/class extractor.
summary: >-
  Extracts function signatures, class attributes, and docstring

  nodes from Python source code using the ``ast`` module.
"""

from __future__ import annotations

import ast

from collections.abc import Iterator
from typing import Optional

from public import private

from douki._base.sync import FuncInfo, ParamInfo
from douki.typechecking import typechecked

# ---------------------------------------------------------------------------
# AST → type-string helpers
# ---------------------------------------------------------------------------


def _annotation_to_str(node: Optional[ast.expr]) -> str:
    """
    title: Convert an AST annotation node to a readable type string.
    """
    if node is None:
        return ''

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value  # forward-reference string
        if node.value is None:
            return 'None'
        return repr(node.value)

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return f'{_annotation_to_str(node.value)}.{node.attr}'

    if isinstance(node, ast.Subscript):
        base = _annotation_to_str(node.value)
        slc = node.slice
        if isinstance(slc, ast.Tuple):
            inner = ', '.join(_annotation_to_str(e) for e in slc.elts)
        else:
            inner = _annotation_to_str(slc)
        return f'{base}[{inner}]'

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _annotation_to_str(node.left)
        right = _annotation_to_str(node.right)
        return f'{left} | {right}'

    if isinstance(node, ast.Tuple):
        return ', '.join(_annotation_to_str(e) for e in node.elts)

    if isinstance(node, ast.List):
        return '[' + ', '.join(_annotation_to_str(e) for e in node.elts) + ']'

    # Fallback: use ast.unparse (Python 3.9+)
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover
        return ''


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _param_kind(
    arg_name: str, func_node: ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    """
    title: Determine the parameter kind.
    """
    for arg in func_node.args.posonlyargs:
        if arg.arg == arg_name:
            return 'positional_only'
    for arg in func_node.args.kwonlyargs:
        if arg.arg == arg_name:
            return 'keyword_only'
    if func_node.args.vararg and func_node.args.vararg.arg == arg_name:
        return 'var_positional'
    if func_node.args.kwarg and func_node.args.kwarg.arg == arg_name:
        return 'var_keyword'
    return 'regular'


def _extract_func(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool = False,
) -> FuncInfo:
    """
    title: Extract a FuncInfo from a FunctionDef/AsyncFunctionDef.
    """
    params: list[ParamInfo] = []
    all_args: list[ast.arg] = (
        node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    )
    if node.args.vararg:
        all_args.append(node.args.vararg)
    if node.args.kwarg:
        all_args.append(node.args.kwarg)

    positional = node.args.posonlyargs + node.args.args
    static = any(
        (isinstance(decorator, ast.Name) and decorator.id == 'staticmethod')
        or (
            isinstance(decorator, ast.Attribute)
            and decorator.attr == 'staticmethod'
        )
        for decorator in node.decorator_list
    )
    receiver = (
        positional[0] if is_method and not static and positional else None
    )
    for arg in all_args:
        if arg is receiver:
            continue
        params.append(
            ParamInfo(
                name=arg.arg,
                annotation=_annotation_to_str(arg.annotation),
                kind=_param_kind(arg.arg, node),
            )
        )

    ret = _annotation_to_str(node.returns)

    # Docstring is the first statement if it's a Constant string.
    ds_node = None
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        ds_node = node.body[0].value

    return FuncInfo(
        name=node.name,
        lineno=node.lineno,
        params=params,
        return_annotation=ret,
        docstring_node=ds_node,
        is_method=is_method,
    )


@private
@typechecked
def body_nodes(statements: list[ast.stmt]) -> Iterator[ast.AST]:
    """
    title: Walk a declaration's body without entering nested scopes.
    """
    pending: list[ast.AST] = list(reversed(statements))
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            pending.extend(reversed(list(ast.iter_child_nodes(node))))


class _FuncExtractor(ast.NodeVisitor):
    """
    title: AST visitor that collects FuncInfo for each docstring site.
    """

    def __init__(self) -> None:
        """
        title: Initialize the extractor with empty state.
        """
        self.results: list[FuncInfo] = []
        self.in_class: bool = False
        # Maps class name → full list of attrs (own + inherited)
        # built up as we visit classes top-to-bottom.
        self._class_attrs_map: dict[str, list[ParamInfo]] = {}

    def visit_Module(self, node: ast.Module) -> None:
        """
        title: Extract module-level docstring.
        """
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            self.results.append(
                FuncInfo(
                    name='<module>',
                    lineno=1,
                    docstring_node=node.body[0].value,
                    is_callable=False,
                    attrs=[
                        ParamInfo(
                            child.target.id,
                            _annotation_to_str(child.annotation),
                            'regular',
                        )
                        for child in node.body
                        if isinstance(child, ast.AnnAssign)
                        and isinstance(child.target, ast.Name)
                    ],
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        title: Extract class docstring and class-level attributes.
        """
        ds_node = None
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            ds_node = node.body[0].value

        # Extract class-level annotated variables for attributes: sync
        own_attrs: list[ParamInfo] = []
        for child in body_nodes(node.body):
            if isinstance(child, ast.AnnAssign) and isinstance(
                child.target, ast.Name
            ):
                own_attrs.append(
                    ParamInfo(
                        name=child.target.id,
                        annotation=_annotation_to_str(child.annotation),
                        kind='regular',
                    )
                )

        # Also extract self.* assignments from __init__ that are
        # not already declared at class level.
        own_names = {p.name for p in own_attrs}
        for child in node.body:
            if (
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(
                    isinstance(decorator, ast.Name)
                    and decorator.id == 'property'
                    for decorator in child.decorator_list
                )
                and child.name not in own_names
            ):
                own_attrs.append(
                    ParamInfo(
                        child.name,
                        _annotation_to_str(child.returns),
                        'regular',
                    )
                )
                own_names.add(child.name)
        declarations = own_names.copy()
        assigned: dict[str, ParamInfo] = {}
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != '__init__':
                continue
            positional = child.args.posonlyargs + child.args.args
            if not positional:
                continue
            receiver = positional[0].arg
            for stmt in body_nodes(child.body):
                # self.x: T = ... (annotated assignment)
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Attribute)
                    and isinstance(stmt.target.value, ast.Name)
                    and stmt.target.value.id == receiver
                    and stmt.target.attr not in declarations
                ):
                    annotation = _annotation_to_str(stmt.annotation)
                    if stmt.target.attr in assigned:
                        assigned.pop(stmt.target.attr).annotation = annotation
                    else:
                        own_attrs.append(
                            ParamInfo(stmt.target.attr, annotation, 'regular')
                        )
                    own_names.add(stmt.target.attr)
                    declarations.add(stmt.target.attr)
                # self.x = ... (plain assignment)
                elif isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == receiver
                            and target.attr not in own_names
                        ):
                            attribute = ParamInfo(target.attr, '', 'regular')
                            own_attrs.append(attribute)
                            assigned[target.attr] = attribute
                            own_names.add(target.attr)
            break  # only process the first __init__

        # Resolve base class attrs from same-file classes
        # (order: base first)
        inherited: list[ParamInfo] = []
        seen_names: set[str] = {p.name for p in own_attrs}
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr  # best-effort for dotted names
            if base_name and base_name in self._class_attrs_map:
                for a in self._class_attrs_map[base_name]:
                    if a.name in assigned:
                        assigned.pop(a.name).annotation = a.annotation
                    if a.name not in seen_names:
                        inherited.append(a)
                        seen_names.add(a.name)

        # Full list: inherited first, then own attrs (own take precedence)
        all_attrs = inherited + own_attrs

        # Store for subclasses that may inherit from this class
        self._class_attrs_map[node.name] = all_attrs

        if ds_node is not None:
            self.results.append(
                FuncInfo(
                    name=node.name,
                    lineno=node.lineno,
                    # Class docstring uses attributes:, not parameters:
                    params=[],
                    attrs=all_attrs,
                    docstring_node=ds_node,
                    is_callable=False,
                )
            )

        old_in_class = self.in_class
        self.in_class = True
        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        title: Extract function docstring and parameters.
        """
        self.results.append(_extract_func(node, is_method=self.in_class))
        old_in_class = self.in_class
        self.in_class = False  # nested functions are not methods
        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """
        title: Extract async function docstring and parameters.
        """
        self.results.append(_extract_func(node, is_method=self.in_class))
        old_in_class = self.in_class
        self.in_class = False
        self.generic_visit(node)
        self.in_class = old_in_class


def extract_functions(source: str) -> list[FuncInfo]:
    """
    title: Parse the Python source and return extracted functions/classes.
    returns:
      description: List of FuncInfo objects in the order they appear.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    extractor = _FuncExtractor()
    extractor.visit(tree)
    return extractor.results
