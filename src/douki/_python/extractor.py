"""
title: Python AST-based function/class extractor.
summary: |-
  Extracts function signatures, class attributes, and docstring
  nodes from Python source code using the ``ast`` module.
"""

from __future__ import annotations

import ast

from typing import Dict, List, Optional

from douki._base.sync import FuncInfo, ParamInfo

# ---------------------------------------------------------------------------
# AST → type-string helpers
# ---------------------------------------------------------------------------


def _annotation_to_str(node: Optional[ast.expr]) -> str:
    """
    title: Convert an AST annotation node to a readable type string.
    parameters:
      node:
        type: Optional[ast.expr]
    returns:
      type: str
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

_SELF_CLS = frozenset({'self', 'cls'})


def _param_kind(
    arg_name: str, func_node: ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    """
    title: Determine the parameter kind.
    parameters:
      arg_name:
        type: str
      func_node:
        type: ast.FunctionDef | ast.AsyncFunctionDef
    returns:
      type: str
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
    parameters:
      node:
        type: ast.FunctionDef | ast.AsyncFunctionDef
      is_method:
        type: bool
    returns:
      type: FuncInfo
    """
    params: List[ParamInfo] = []
    all_args: list[ast.arg] = (
        node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    )
    if node.args.vararg:
        all_args.append(node.args.vararg)
    if node.args.kwarg:
        all_args.append(node.args.kwarg)

    for arg in all_args:
        if arg.arg in _SELF_CLS and is_method:
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


class _FuncExtractor(ast.NodeVisitor):
    """
    title: AST visitor that collects FuncInfo for each docstring site.
    attributes:
      results:
        type: List[FuncInfo]
      in_class:
        type: bool
      _class_attrs_map:
        type: Dict[str, List[ParamInfo]]
    """

    def __init__(self) -> None:
        self.results: List[FuncInfo] = []
        self.in_class: bool = False
        # Maps class name → full list of attrs (own + inherited)
        # built up as we visit classes top-to-bottom.
        self._class_attrs_map: Dict[str, List[ParamInfo]] = {}

    def visit_Module(self, node: ast.Module) -> None:
        """
        title: Extract module-level docstring.
        parameters:
          node:
            type: ast.Module
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
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        title: Extract class docstring and class-level attributes.
        parameters:
          node:
            type: ast.ClassDef
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
        own_attrs: List[ParamInfo] = []
        for child in node.body:
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
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != '__init__':
                continue
            for stmt in ast.walk(child):
                # self.x: T = ... (annotated assignment)
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Attribute)
                    and isinstance(stmt.target.value, ast.Name)
                    and stmt.target.value.id == 'self'
                    and stmt.target.attr not in own_names
                ):
                    own_attrs.append(
                        ParamInfo(
                            name=stmt.target.attr,
                            annotation=_annotation_to_str(stmt.annotation),
                            kind='regular',
                        )
                    )
                    own_names.add(stmt.target.attr)
                # self.x = ... (plain assignment)
                elif isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == 'self'
                            and target.attr not in own_names
                        ):
                            own_attrs.append(
                                ParamInfo(
                                    name=target.attr,
                                    annotation='',
                                    kind='regular',
                                )
                            )
                            own_names.add(target.attr)
            break  # only process the first __init__

        # Resolve base class attrs from same-file classes
        # (order: base first)
        inherited: List[ParamInfo] = []
        seen_names: set[str] = {p.name for p in own_attrs}
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr  # best-effort for dotted names
            if base_name and base_name in self._class_attrs_map:
                for a in self._class_attrs_map[base_name]:
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
                )
            )

        old_in_class = self.in_class
        self.in_class = True
        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        title: Extract function docstring and parameters.
        parameters:
          node:
            type: ast.FunctionDef
        """
        self.results.append(_extract_func(node, is_method=self.in_class))
        old_in_class = self.in_class
        self.in_class = False  # nested functions are not methods
        self.generic_visit(node)
        self.in_class = old_in_class

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """
        title: Extract async function docstring and parameters.
        parameters:
          node:
            type: ast.AsyncFunctionDef
        """
        self.results.append(_extract_func(node, is_method=self.in_class))
        old_in_class = self.in_class
        self.in_class = False
        self.generic_visit(node)
        self.in_class = old_in_class


def extract_functions(source: str) -> List[FuncInfo]:
    """
    title: Parse the Python source and return extracted functions/classes.
    parameters:
      source:
        type: str
    returns:
      type: List[FuncInfo]
      description: List of FuncInfo objects in the order they appear.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    extractor = _FuncExtractor()
    extractor.visit(tree)
    return extractor.results
