"""Tests for main module."""

from src.main import hello, add


def test_hello():
    """Test hello function returns greeting."""
    assert hello() == "Hello, World!"


def test_add():
    """Test add function."""
    assert add(2, 3) == 5


def test_add_negative():
    """Test add with negative numbers."""
    assert add(-1, 1) == 0
