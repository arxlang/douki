"""tests/test_core.py - unit tests for YAML-first *douki*
Verify that:
* YAML docstrings are converted to numpydoc blocks.
* Generic type printing works (`list[int]`).
* `typing.Annotated` metadata propagates.
* Class-level decoration adds *Attributes* and auto-decorates methods.
* The decorator is idempotent.
"""

from __future__ import annotations

from typing import Annotated

import douki
import pytest

from douki import DocString


def _strip(text: str) -> str:
    """Normalize whitespace."""
    return '\n'.join(ln.rstrip() for ln in text.splitlines() if ln.rstrip())


def test_function_parameters_and_returns():
    """Decorator should inject Parameters / Returns blocks."""

    @douki(params={'x': 'The x value'}, returns='x squared')
    def square(x: int) -> int:
        """
        title: square a value
        parameters:
          x:
            type: int
            description: placeholder
        returns:
          - type: int
            description: placeholder
        """
        return x * x

    doc = _strip(square.__doc__ or '')
    assert 'Parameters' in doc and 'Returns' in doc
    assert 'x : int' in doc and 'The x value' in doc
    assert 'x squared' in doc


def test_generic_type_rendering():
    @douki
    def give_first(values: list[int]) -> int:
        """
        title: generic list example
        parameters:
          values:
            type: list[int]
            description: input list of integers
        returns:
          - type: int
            description: first element
        """
        return values[0]

    assert 'values : list[int]' in (give_first.__doc__ or '')


def test_annotated_descriptions_and_defaults():
    @douki
    def add(
        x: Annotated[int, DocString('first term')] = 2,
        y: Annotated[int, 'second term'] = 3,
    ) -> Annotated[int, DocString('sum')]:
        """
        title: add two numbers
        parameters:
          x:
            type: Annotated[int, DocString('first term')]
            description: first term
          y:
            type: Annotated[int, second term]
            description: second term
        returns:
          - type: Annotated[int, DocString('sum')]
            description: sum
        """
        return x + y

    doc = _strip(add.__doc__ or '')
    assert 'first term' in doc and 'default is `2`' in doc
    assert 'second term' in doc and 'default is `3`' in doc
    assert 'sum' in doc


def test_class_attributes_and_methods():
    @douki(class_vars={'a': 'Alpha', 'b': 'Bravo'})
    class Demo:
        """title: demo class"""

        a: int = 1
        b: int = 2

        def add(self, value: int) -> int:
            """
            title: add internal attrs
            parameters:
              value:
                type: int
                description: extra value to add
            returns:
              - type: int
                description: sum of a, b, and value
            """
            return self.a + self.b + value

    cls_doc = _strip(Demo.__doc__ or '')
    assert (
        'Attributes' in cls_doc and 'a : int' in cls_doc and 'Alpha' in cls_doc
    )
    assert 'b : int' in cls_doc and 'Bravo' in cls_doc

    meth_doc = _strip(Demo.add.__doc__ or '')
    assert (
        'Parameters' in meth_doc
        and 'value : int' in meth_doc
        and 'Returns' in meth_doc
    )


def test_idempotency():
    @douki
    def mul(x: int, y: int) -> int:
        """
        title: multiply two ints
        parameters:
          x:
            type: int
            description: left operand
          y:
            type: int
            description: right operand
        returns:
          - type: int
            description: product of x and y
        """
        return x * y

    first = mul.__doc__ or ''
    douki(mul)
    second = mul.__doc__ or ''
    assert first == second and first.count('Parameters') == 1


def test_invalid_yaml_docstring_raises():
    """Check a docstring missing the required ``title`` key."""

    # YAML lacks the required 'title:' field
    with pytest.raises(ValueError):

        @douki
        def bad(x: int) -> int:
            """
            parameters:
              x:
                type: int
                description: just a number
            returns:
              - type: int
                description: the same number
            """
            return x
