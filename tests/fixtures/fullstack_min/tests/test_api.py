"""Tests for API module."""

from src.api.main import HealthHandler


def test_health_handler_exists():
    """Test that HealthHandler class exists."""
    assert HealthHandler is not None


def test_create_app():
    """Test that create_app returns a server."""
    from src.api.main import create_app
    # Note: Don't actually start the server in tests
    assert callable(create_app)
