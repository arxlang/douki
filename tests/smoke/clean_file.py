def greet(name: str) -> str:
    """
    title: Greet someone
    parameters:
        name: The person's name
    returns: a greeting string
    """
    return f'Hello {name}'


def add(x: int, y: int) -> int:
    """
    title: Add two integers
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
            a: first operand
            b: second operand
        returns: the product
        """
        return a * b
