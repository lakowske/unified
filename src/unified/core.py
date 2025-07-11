"""Core functionality for the clean Python project."""

from typing import Union


def greet(name: str) -> str:
    """Greet a person with their name.

    Args:
        name: The name of the person to greet.

    Returns:
        A greeting message.

    Example:
        >>> greet("World")
        'Hello, World!'
    """
    if not isinstance(name, str):
        raise TypeError("Name must be a string")
    if not name.strip():
        raise ValueError("Name cannot be empty")
    return f"Hello, {name}!"


def calculate_sum(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Calculate the sum of two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.

    Example:
        >>> calculate_sum(2, 3)
        5
        >>> calculate_sum(2.5, 1.5)
        4.0
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Both arguments must be numbers")
    return a + b


def main() -> None:
    """Main entry point for the application."""
    print(greet("World"))
    print(f"2 + 3 = {calculate_sum(2, 3)}")
    print(f"2.5 + 1.5 = {calculate_sum(2.5, 1.5)}")


if __name__ == "__main__":
    main()
