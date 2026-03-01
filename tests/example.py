"""example.py - showcase for YAML-first *douki*

Run with:
    python -m tests/example.py

It prints the generated numpydoc docstrings for a variety of objects.
"""

from __future__ import annotations

from typing import Annotated, Any, Generator, Iterable

import douki

from douki import DocString


@douki
def add(x: int, y: int) -> int:
    """
    title: Add two integers
    summary: |
        Returns the sum of *x* and *y*.
    parameters:
        x: first operand
        y: second operand
    returns: the arithmetic sum
    raises:
        ValueError: If either operand is negative.
    see_also: identity, multiply
    notes: |
        This is a trivial example.
    examples: |
        >>> add(2, 3)
        5
    """
    if x < 0 or y < 0:
        raise ValueError
    return x + y


@douki
def identity(value: Any) -> Any:
    """
    title: Identity (deprecated)
    summary: Returns *value* unchanged.
    deprecated: Use ``copy.deepcopy`` instead.
    parameters:
        value: (Any)
    returns: the input value as-is
    warnings:
        RuntimeWarning: Passing mutable objects returns a reference.
    examples: |
        >>> identity(5)
        5
    """
    return value


@douki
def fib(n: int) -> Generator[int, None, None]:
    """
    title: Fibonacci generator
    parameters:
        n: Number of terms to generate
    returns: (Generator[int, None, None])
    yields: successive Fibonacci numbers up to *n*
    examples: |
        >>> list(fib(5))
        [0, 1, 1, 2, 3]
    """
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b


@douki
def accumulate(values: Iterable[int]) -> int:
    """
    title: Sum an iterable
    parameters:
        values: (Iterable[int])
    returns: total sum
    receives: iterable of integers
    """
    return sum(values)


@douki(class_vars={'a': 'Alpha', 'b': 'Bravo'})
class BasicCalculator:
    """
    title: Very small demo calculator
    attributes:
        a: First term of internal state
        b: Second term of internal state
    methods: add, multiply
    """

    a: int = 1
    b: int = 2

    def add(self) -> int:
        """
        title: Sum of internal operands
        returns: Sum of *self.a* and *self.b*
        """
        return self.a + self.b

    @douki(params={'scalar': 'Factor'}, returns='Scaled sum')
    def multiply(self, scalar: int) -> int:
        """
        title: Multiply by *scalar*
        parameters:
            scalar: Number to multiply by (overridden by decorator)
        returns: (int)
        """
        return (self.a + self.b) * scalar


@douki
class FancyCalculator:
    """
    title: Annotated attribute demo
    """

    x: Annotated[float, DocString('First floating-point operand')] = 2.5
    y: Annotated[float, 'Second floating-point operand'] = 4.0

    def power(
        self,
        base: Annotated[float, DocString('Base')] = 2.0,
        exp: Annotated[float, 'Exponent'] = 3.0,
    ) -> Annotated[float, DocString('base ** exp')]:
        """
        title: Raise *base* to *exp*
        parameters:
            base: the base number
            exp: the exponent value
        returns: result of ``base ** exp``
        """
        return base**exp


PI: float = 3.141592653589793
E: float = 2.718281828459045


def _demo() -> None:  # pragma: no cover
    print('Generated docstrings\n' + '=' * 80)
    for obj in (
        add,
        identity,
        fib,
        accumulate,
        BasicCalculator,
        BasicCalculator.add,
        BasicCalculator.multiply,
        FancyCalculator,
        FancyCalculator.power,
    ):
        print(f'\n>>> help({obj.__qualname__})')
        print('-' * 80)
        print(obj.__doc__)


if __name__ == '__main__':  # pragma: no cover
    _demo()
