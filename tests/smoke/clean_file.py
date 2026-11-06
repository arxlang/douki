def greet(name: str) -> str:
    """
    title: Greet someone
    parameters:
      name:
        description: The name to greet
    returns:
      description: a greeting string
    """
    return f'Hello {name}'


def add(x: int, y: int) -> int:
    """
    title: Add two integers
    parameters:
      x:
        description: First value to add.
      y:
        description: Second value to add.
    returns:
      description: Sum of the two supplied values.
    """
    return x + y


class Calculator:
    """
    title: Basic calculator
    attributes:
      result:
        description: The last computed result.
      history:
        description: All past results.
    """

    result: int
    history: list

    def __init__(self, initial: int = 0) -> None:
        """
        title: Initialize Calculator
        parameters:
          initial:
            description: Starting value of the calculator total.
        """
        self.result = initial

    def multiply(self, a: int, b: int) -> int:
        """
        title: Multiply two numbers
        parameters:
          a:
            description: first operand
          b:
            description: second operand
        returns:
          description: the product
        """
        return a * b
