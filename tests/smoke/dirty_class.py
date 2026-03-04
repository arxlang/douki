class Calculator:
    """
    title: Basic calculator
    """

    result: int
    history: list

    def __init__(self, initial: int = 0):
        """
        title: Initialize Calculator
        """
        self.result = initial
        self.history = []

    def multiply(self, a: int, b: int) -> int:
        """
        title: Multiply two numbers
        """
        return a * b
