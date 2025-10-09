'''
Douki core library - YAML-first flavour.

Turns YAML-formatted docstrings into enriched *numpydoc* sections.

Example
-------
```python
@douki  # or simply ``@douki`` if you re-export apply at top level
def add(x: int, y: int) -> int:
    """
    title: Return the sum of two integers
    summary: |
        This function returns the sum of two integer numbers.
    parameters:  # noqa
        x: The first operand
        y: The second operand
    returns: Sum of *x* and *y*
    """
    return x + y
```

The decorator will append a numpydoc block like:

```
Return the sum of two integers.

This function returns the sum of two integer numbers.

Parameters
----------
x : int, default is `…`
    The first operand
...
```
'''

from __future__ import annotations

import inspect
import textwrap

from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import yaml

from typing_extensions import ParamSpec
from typing_extensions import get_type_hints as get_type_hints_ext

from douki._validation import validate_schema

__all__ = ['DocString', 'apply']
_SENTINEL = '__doxs_applied__'

T = TypeVar('T', bound=type)
P = ParamSpec('P')
R = TypeVar('R')


@dataclass
class DocString:
    """Carry a description inside ``typing.Annotated`` metadata."""

    description: str


def _parse_yaml(raw: str) -> Dict[str, Any]:
    """Parse *raw* as YAML or raise ``ValueError``."""

    if not raw or ':' not in raw:
        raise ValueError("Docstring is not valid YAML: missing ':'")
    try:
        data = yaml.safe_load(textwrap.dedent(raw))
    except yaml.YAMLError as exc:  # pragma: no cover
        raise ValueError(f'Docstring is not valid YAML: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('YAML root must be a mapping')

    validate_schema(data)

    return data


def _narrative(yaml_dict: Dict[str, Any]) -> str:
    title = str(yaml_dict.get('title', '')).strip()
    summary = str(yaml_dict.get('summary', '')).rstrip()
    parts: List[str] = []
    if title:
        parts.append(title if title.endswith('.') else title + '.')
    if summary:
        parts.append(summary)
    return '\n\n'.join(parts).strip()


def apply(
    _obj: Any = None,
    *,
    class_vars: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    returns: Optional[Union[str, List[str]]] = None,
) -> Any:
    """Decorate a class or callable and convert YAML → numpydoc."""

    def decorator(obj: Any) -> Any:
        if inspect.isclass(obj):
            return _decorate_class(obj, class_vars or {})
        if callable(obj):
            return _decorate_func(obj, params or {}, returns)
        return obj

    return decorator if _obj is None else decorator(_obj)


def _decorate_class(cls: T, overrides: dict[str, str]) -> T:
    if getattr(cls, _SENTINEL, False):
        return cls

    yaml_dict = _parse_yaml(inspect.getdoc(cls) or '')
    narrative = _narrative(yaml_dict)

    # -------- build *Attributes* -----------------------------------------
    try:
        annotations = get_type_hints(cls, include_extras=True)
    except TypeError:
        annotations = get_type_hints_ext(cls, include_extras=True)

    a_lines: List[str] = []
    for name, ann in annotations.items():
        typ, desc, default = _parse_annotation(
            ann, getattr(cls, name, inspect._empty)
        )
        desc = overrides.get(
            name, yaml_dict.get('attributes', {}).get(name, desc)
        )
        line = f'{name} : {typ}'
        if default is not inspect._empty:
            line += f', default is `{default!r}`'
        a_lines.append(line)
        if desc:
            a_lines.append(f'    {desc}')
    attr_block = '\n'.join(a_lines)

    # -------- build *Methods* automatically ------------------------------
    def _fmt_sig(sig: inspect.Signature) -> str:
        parts: List[str] = []
        for p in sig.parameters.values():
            if p.name in {'self', 'cls'}:
                continue
            if p.default is inspect.Parameter.empty:
                parts.append(p.name)
            else:
                parts.append(f'{p.name}={p.default!r}')
        return '(' + ', '.join(parts) + ')'

    m_lines: List[str] = []
    for name, member in vars(cls).items():
        if name.startswith('__') or not callable(member):
            continue

        sig = inspect.signature(member)
        try:
            yml = _parse_yaml(inspect.getdoc(member) or '')
            short = str(
                yml.get('title', '') or yml.get('summary', '')
            ).splitlines()[0]
        except Exception:
            short = ''

        m_lines.append(f'{name}{_fmt_sig(sig)}')  # e.g. colorspace(c='rgb')
        if short:
            m_lines.append(f'    {short}')
    meth_block = '\n'.join(m_lines)

    parts = [narrative] if narrative else []
    if attr_block:
        parts.append('Attributes\n----------\n' + attr_block)
    if meth_block:
        parts.append('Methods\n-------\n' + meth_block)

    cls.__doc__ = '\n\n'.join(parts).strip()

    # auto-decorate methods (after documentation extracted)
    for n, m in vars(cls).items():
        if (
            n.startswith('__')
            or not callable(m)
            or getattr(m, _SENTINEL, False)
        ):
            continue
        setattr(cls, n, apply(m))

    setattr(cls, _SENTINEL, True)
    return cls


def _decorate_func(
    func: Callable[P, R],
    param_over: Dict[str, str],
    returns_over: Optional[Union[str, List[str]]],
) -> Callable[P, R]:
    if getattr(func, _SENTINEL, False):
        return func

    yaml_dict = _parse_yaml(inspect.getdoc(func) or '')
    narrative = _narrative(yaml_dict)

    params_map = {**yaml_dict.get('parameters', {}), **param_over}
    returns_txt = (
        returns_over
        if returns_over is not None
        else yaml_dict.get('returns', '')
    )
    yields_txt = yaml_dict.get('yields', '')
    receives = yaml_dict.get('receives', '')
    raises_map = yaml_dict.get('raises', {})
    warns_map = yaml_dict.get('warnings', {})
    deprecated = yaml_dict.get('deprecated', '')
    see_also = yaml_dict.get('see_also', '')
    notes = yaml_dict.get('notes', '')
    refs = yaml_dict.get('references', '')
    examples = yaml_dict.get('examples', '')

    sig = inspect.signature(func)
    hints = get_type_hints(func, include_extras=True)

    # Parameters
    p_lines: List[str] = []
    for name, p in sig.parameters.items():
        if name in {'self', 'cls'}:
            continue
        ann = hints.get(name, p.annotation)
        default = (
            p.default
            if p.default is not inspect.Parameter.empty
            else inspect._empty
        )
        typ, desc_from_ann, default = _parse_annotation(ann, default)
        desc = params_map.get(name, desc_from_ann)
        line = f'{name} : {typ}'
        if default is not inspect._empty:
            line += f', default is `{default!r}`'
        p_lines.append(line)
        if desc:
            p_lines.append(f'    {desc}')
    param_block = '\n'.join(p_lines) or 'None'

    # Returns / Yields / Receives
    ret_ann = hints.get('return', sig.return_annotation)
    ret_type, ret_desc, _ = _parse_annotation(ret_ann, inspect._empty)
    if returns_txt:
        ret_desc = (
            returns_txt
            if isinstance(returns_txt, str)
            else '; '.join(returns_txt)
        )

    def _simple_block(name: str, text: str) -> str:
        return f'{name}\n{"-" * len(name)}\n{text.strip()}' if text else ''

    returns_block = (
        _simple_block(
            'Returns', ret_type + ('\n    ' + ret_desc if ret_desc else '')
        )
        if ret_type and ret_type != 'None'
        else ''
    )
    yields_block = _simple_block('Yields', yields_txt)
    receives_block = _simple_block('Receives', receives)

    # Raises / Warnings
    def _map_block(title: str, m: Dict[str, str]) -> str:
        if not m:
            return ''
        lines = [f'{k}\n    {v}' if v else k for k, v in m.items()]
        return f'{title}\n{"-" * len(title)}\n' + '\n'.join(lines)

    raises_block = _map_block('Raises', raises_map)
    warns_block = _map_block('Warnings', warns_map)

    # Assemble in canonical numpydoc order
    sections = [
        s
        for s in [
            _simple_block('Deprecated', deprecated),
            _simple_block('Parameters', param_block),
            returns_block,
            yields_block,
            receives_block,
            raises_block,
            warns_block,
            _simple_block('See Also', see_also),
            _simple_block('Notes', notes),
            _simple_block('References', refs),
            _simple_block('Examples', examples),
        ]
        if s
    ]

    doc = '\n\n'.join([narrative, *sections]).strip()
    func.__doc__ = doc
    setattr(func, _SENTINEL, True)
    return func


def _parse_annotation(annotation: Any, default: Any) -> tuple[str, str, Any]:
    desc = ''
    typ_name = ''

    if get_origin(annotation) is Annotated:
        base, *meta = get_args(annotation)
        typ_name = _type_to_str(base)
        for m in meta:
            if isinstance(m, str):
                desc = m
                break
            if hasattr(m, 'description'):
                desc = m.description
                break
    elif annotation is inspect._empty:
        typ_name = 'Any'
    else:
        typ_name = _type_to_str(annotation)

    return typ_name, desc, default


def _type_to_str(tp: Any) -> str:
    origin = get_origin(tp)
    if origin is None:
        return getattr(tp, '__name__', str(tp))
    args = ', '.join(_type_to_str(arg) for arg in get_args(tp))
    return f'{origin.__name__}[{args}]'
