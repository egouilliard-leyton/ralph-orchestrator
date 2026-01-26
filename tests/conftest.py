"""
Shared test fixtures for Ralph orchestrator tests.

This module provides pytest fixtures for unit and integration tests,
including:
- Mock Claude CLI configuration
- Fixture repository setup
- Temporary directory management
- Common test utilities
"""

import os
import sys
import pytest
import shutil
import tempfile
from pathlib import Path
from typing import Generator

# Ensure mock Claude is used by default in tests
MOCK_CLAUDE_PATH = Path(__file__).parent / "mock_claude" / "mock_claude.py"
os.environ.setdefault("RALPH_CLAUDE_CMD", f"{sys.executable} {MOCK_CLAUDE_PATH}")

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Session-scoped fixtures (created once per test session)
# =============================================================================

@pytest.fixture(scope="session")
def mock_claude_path() -> Path:
    """Return path to mock Claude executable."""
    return MOCK_CLAUDE_PATH


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


# =============================================================================
# Function-scoped fixtures (created fresh for each test)
# =============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test use.
    
    The directory is automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def isolated_cwd(temp_dir: Path) -> Generator[Path, None, None]:
    """Change to temporary directory for test, restore afterward.
    
    Useful for tests that need to run commands in a specific directory.
    """
    original_cwd = os.getcwd()
    os.chdir(temp_dir)
    try:
        yield temp_dir
    finally:
        os.chdir(original_cwd)


# =============================================================================
# Fixture repository fixtures
# =============================================================================

def _copy_fixture(fixture_name: str, tmp_path: Path, init_git: bool = True) -> Path:
    """Helper to copy a fixture repository to temp directory."""
    fixtures_base = Path(__file__).parent / "fixtures"
    src = fixtures_base / fixture_name
    dst = tmp_path / "repo"
    
    if not src.exists():
        raise FileNotFoundError(f"Fixture not found: {src}")
    
    shutil.copytree(src, dst)
    
    if init_git:
        # Initialize git repo (required for some operations)
        os.system(f"cd {dst} && git init -q && git add . && git commit -q -m 'Initial'")
    
    return dst


@pytest.fixture
def fixture_python_min(tmp_path: Path) -> Path:
    """Copy python_min fixture to temp directory with git init."""
    return _copy_fixture("python_min", tmp_path)


@pytest.fixture
def fixture_node_min(tmp_path: Path) -> Path:
    """Copy node_min fixture to temp directory with git init."""
    return _copy_fixture("node_min", tmp_path)


@pytest.fixture
def fixture_fullstack_min(tmp_path: Path) -> Path:
    """Copy fullstack_min fixture to temp directory with git init."""
    return _copy_fixture("fullstack_min", tmp_path)


@pytest.fixture
def fixture_autopilot_min(tmp_path: Path) -> Path:
    """Copy autopilot_min fixture to temp directory with git init."""
    return _copy_fixture("autopilot_min", tmp_path)


# =============================================================================
# Mock scenario fixtures
# =============================================================================

@pytest.fixture
def mock_scenario_default():
    """Set mock Claude to default (success) scenario."""
    original = os.environ.get("MOCK_SCENARIO")
    os.environ["MOCK_SCENARIO"] = "default"
    yield
    if original:
        os.environ["MOCK_SCENARIO"] = original
    else:
        os.environ.pop("MOCK_SCENARIO", None)


@pytest.fixture
def mock_scenario_invalid_token():
    """Set mock Claude to return invalid token responses."""
    original = os.environ.get("MOCK_SCENARIO")
    os.environ["MOCK_SCENARIO"] = "invalid_token"
    yield
    if original:
        os.environ["MOCK_SCENARIO"] = original
    else:
        os.environ.pop("MOCK_SCENARIO", None)


@pytest.fixture
def mock_scenario_no_signal():
    """Set mock Claude to return responses without completion signals."""
    original = os.environ.get("MOCK_SCENARIO")
    os.environ["MOCK_SCENARIO"] = "no_signal"
    yield
    if original:
        os.environ["MOCK_SCENARIO"] = original
    else:
        os.environ.pop("MOCK_SCENARIO", None)


@pytest.fixture
def mock_scenario_review_reject():
    """Set mock Claude to return review rejection."""
    original = os.environ.get("MOCK_SCENARIO")
    os.environ["MOCK_SCENARIO"] = "review_reject"
    yield
    if original:
        os.environ["MOCK_SCENARIO"] = original
    else:
        os.environ.pop("MOCK_SCENARIO", None)


# =============================================================================
# Test utilities
# =============================================================================

@pytest.fixture
def sample_prd_json() -> dict:
    """Return a sample prd.json structure for testing."""
    return {
        "project": "Test Project",
        "branchName": "ralph/test-branch",
        "description": "Test description",
        "tasks": [
            {
                "id": "T-001",
                "title": "First test task",
                "description": "Do the first thing",
                "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
                "priority": 1,
                "passes": False,
                "notes": ""
            },
            {
                "id": "T-002",
                "title": "Second test task",
                "description": "Do the second thing",
                "acceptanceCriteria": ["Criterion A"],
                "priority": 2,
                "passes": False,
                "notes": ""
            }
        ]
    }


@pytest.fixture
def sample_session_token() -> str:
    """Return a sample session token for testing."""
    return "ralph-20260125-143052-a1b2c3d4e5f60a1b"


@pytest.fixture
def sample_task_status() -> dict:
    """Return a sample task status structure for testing."""
    return {
        "checksum": "sha256:" + "a" * 64,
        "last_updated": "2026-01-25T14:30:52Z",
        "tasks": {
            "T-001": {
                "passes": True,
                "started_at": "2026-01-25T14:30:52Z",
                "completed_at": "2026-01-25T14:35:00Z",
                "iterations": 1
            },
            "T-002": {
                "passes": False,
                "started_at": "2026-01-25T14:36:00Z",
                "iterations": 2,
                "last_failure": "Review rejected: missing error handling"
            }
        }
    }


# =============================================================================
# Test markers
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (mock Claude + fixtures)"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take longer than 10 seconds"
    )
    config.addinivalue_line(
        "markers", "autopilot: Autopilot-specific tests"
    )
