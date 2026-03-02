def greet(name: str) -> str:
    """
    title: Greet someone
    parameters:
      name:
        type: str
        description: The name to greet
    returns:
      - type: str
        description: a greeting string
    """
    return f'Hello {name}'


def add(x: int, y: int) -> int:
    """
    title: Add two integers
    parameters:
      x:
        type: int
      y:
        type: int
    returns:
      - type: int
    """
    return x + y


class Calculator:
    """
    title: Basic calculator
    """

    def multiply(self, a: int, b: int) -> int:
        """
        title: Multiply two numbers
        parameters:
          a:
            type: int
            description: first operand
          b:
            type: int
            description: second operand
        returns:
          - type: int
            description: the product
        """
        return a * b
