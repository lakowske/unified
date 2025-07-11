"""Tests for core functionality."""

from typing import Any

import pytest

from unified.core import calculate_sum, greet


def test_greet_with_valid_name() -> None:
    """Test greeting with a valid name."""
    result = greet("Alice")
    assert result == "Hello, Alice!"


def test_greet_with_empty_name() -> None:
    """Test greeting with an empty name raises ValueError."""
    with pytest.raises(ValueError, match="Name cannot be empty"):
        greet("")


def test_greet_with_whitespace_name() -> None:
    """Test greeting with whitespace-only name raises ValueError."""
    with pytest.raises(ValueError, match="Name cannot be empty"):
        greet("   ")


def test_greet_with_non_string() -> None:
    """Test greeting with non-string input raises TypeError."""
    invalid_input: Any = 123
    with pytest.raises(TypeError, match="Name must be a string"):
        greet(invalid_input)


def test_calculate_sum_integers() -> None:
    """Test sum calculation with integers."""
    result = calculate_sum(2, 3)
    assert result == 5


def test_calculate_sum_floats() -> None:
    """Test sum calculation with floats."""
    result = calculate_sum(2.5, 1.5)
    assert result == 4.0


def test_calculate_sum_mixed() -> None:
    """Test sum calculation with mixed int and float."""
    result = calculate_sum(2, 3.5)
    assert result == 5.5


def test_calculate_sum_with_non_numbers() -> None:
    """Test sum calculation with non-numeric input raises TypeError."""
    invalid_first: Any = "2"
    invalid_second: Any = "3"

    with pytest.raises(TypeError, match="Both arguments must be numbers"):
        calculate_sum(invalid_first, 3)

    with pytest.raises(TypeError, match="Both arguments must be numbers"):
        calculate_sum(2, invalid_second)
