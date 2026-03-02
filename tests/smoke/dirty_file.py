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


def greet(name: str, greeting: str = 'Hello') -> str:
    """
    title: Greet someone
    parameters:
      name:
        type: str
      greeting:
        type: str
    returns:
      - type: str
    """
    return f'{greeting} {name}'
