"""Unit tests for SessionService."""

import pytest
import json
from pathlib import Path
from ralph_orchestrator.services.session_service import SessionService, SessionSummary


@pytest.fixture
def temp_project_with_session(tmp_path):
    """Create a temporary project with session data."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create .ralph-session directory
    session_dir = project_dir / ".ralph-session"
    session_dir.mkdir()
    
    # Create session.json with all required fields
    session_file = session_dir / "session.json"
    session_data = {
        "session_id": "ralph-20260128-123456-abc123",
        "session_token": "abc123",
        "started_at": 1706443200.0,
        "task_source": ".ralph/prd.json",
        "task_source_type": "prd_json",
        "status": "running"
    }
    session_file.write_text(json.dumps(session_data, indent=2))
    
    # Create logs directory
    logs_dir = session_dir / "logs"
    logs_dir.mkdir()
    
    return project_dir


@pytest.fixture
def session_service():
    """Create a SessionService instance."""
    return SessionService()


class TestSessionService:
    """Test SessionService class."""

    def test_get_session_summary(self, session_service, temp_project_with_session):
        """Test getting session summary."""
        summary = session_service.get_session_summary(temp_project_with_session)
        
        assert summary is not None
        assert summary.session_id == "ralph-20260128-123456-abc123"
        assert summary.status == "running"
        assert summary.started_at == 1706443200.0

    def test_get_session_summary_no_session(self, session_service, tmp_path):
        """Test getting session summary when no session exists."""
        empty_project = tmp_path / "empty_project"
        empty_project.mkdir()
        
        summary = session_service.get_session_summary(empty_project)
        
        assert summary is None

    def test_session_exists(self, session_service, temp_project_with_session):
        """Test checking if session exists."""
        exists = session_service.session_exists(temp_project_with_session)
        
        assert exists is True

    def test_session_not_exists(self, session_service, tmp_path):
        """Test checking if session exists when it doesn't."""
        empty_project = tmp_path / "empty_project"
        empty_project.mkdir()
        
        exists = session_service.session_exists(empty_project)
        
        assert exists is False


class TestSessionSummary:
    """Test SessionSummary dataclass."""

    def test_session_summary_creation(self):
        """Test creating SessionSummary."""
        summary = SessionSummary(
            session_id="ralph-20260128-123456-abc123",
            session_token="abc123",
            project_path=Path("/test/project"),
            status="completed",
            started_at="2026-01-28T12:34:56Z",
            ended_at=None,
            task_source=".ralph/prd.json",
            current_task=None,
            completed_tasks=["T-001"],
            pending_tasks=[],
            total_iterations=5,
            git_branch="main",
            git_commit="abc123def"
        )

        assert summary.session_id == "ralph-20260128-123456-abc123"
        assert summary.project_path == Path("/test/project")
        assert summary.status == "completed"
        assert summary.total_iterations == 5
