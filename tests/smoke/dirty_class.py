class Calculator:
    """
    title: Basic calculator
    attributes:
      result:
        type: int
        description: The last computed result.
    """

    def __init__(self, initial: int = 0):
        """
        title: Initialize Calculator
        """
        self.result = initial

    def multiply(self, a: int, b: int) -> int:
        """
        title: Multiply two numbers
        """
        return a * b
