"""Main module for autopilot fixture."""


def hello() -> str:
    """Return greeting."""
    return "Hello from Autopilot Fixture!"


def process_data(data: dict) -> dict:
    """Process input data."""
    return {"processed": True, **data}
