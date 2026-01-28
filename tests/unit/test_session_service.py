"""Unit tests for SessionService.

Tests the session management service including:
- CRUD operations for sessions
- Event emission
- Session integrity verification
"""

import json
import pytest
import time
from pathlib import Path
from typing import List

from ralph_orchestrator.services.session_service import (
    SessionService,
    SessionSummary,
    TaskStatusSummary,
    SessionEventType,
    SessionCreatedEvent,
    SessionLoadedEvent,
    SessionEndedEvent,
    SessionDeletedEvent,
    TaskStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    IterationIncrementedEvent,
    StatusChangedEvent,
    MetadataUpdatedEvent,
)
from ralph_orchestrator.session import TamperingDetectedError


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a minimal project structure (without session)."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    # Create .ralph directory
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir()

    # Create minimal ralph.yml
    config_path = ralph_dir / "ralph.yml"
    config_path.write_text("""
version: "1"
task_source:
  type: prd_json
  path: .ralph/prd.json
""")

    # Create minimal prd.json
    prd_path = ralph_dir / "prd.json"
    prd_data = {
        "project": "Test Project",
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": False},
            {"id": "T-002", "title": "Task 2", "passes": False},
        ]
    }
    prd_path.write_text(json.dumps(prd_data))

    return project_path


@pytest.fixture
def service() -> SessionService:
    """Create a fresh SessionService instance."""
    return SessionService()


class TestSessionServiceCreate:
    """Tests for CREATE operations."""

    def test_create_session(self, service: SessionService, temp_project: Path):
        """Test creating a new session."""
        session = service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
        )

        assert session is not None
        assert session.session_id is not None
        assert session.session_token is not None
        assert session.metadata.status == "running"
        assert "T-001" in session.metadata.pending_tasks
        assert "T-002" in session.metadata.pending_tasks

    def test_create_session_emits_event(self, service: SessionService, temp_project: Path):
        """Test that creating a session emits an event."""
        events: List[SessionCreatedEvent] = []

        def handler(event):
            if isinstance(event, SessionCreatedEvent):
                events.append(event)

        service.on_event(SessionEventType.SESSION_CREATED, handler)
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        assert len(events) == 1
        assert events[0].task_source == ".ralph/prd.json"
        assert "T-001" in events[0].pending_tasks

    def test_create_session_fails_if_exists(self, service: SessionService, temp_project: Path):
        """Test that creating a session fails if one already exists."""
        # Create first session
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        # Try to create another
        with pytest.raises(ValueError, match="Session already exists"):
            service.create_session(
                project_path=temp_project,
                task_source=".ralph/prd.json",
                task_source_type="prd_json",
            )


class TestSessionServiceRead:
    """Tests for READ operations."""

    def test_get_session(self, service: SessionService, temp_project: Path):
        """Test getting an existing session."""
        # Create session
        created = service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        # Clear cache to force loading from disk
        service.clear_cache()

        # Get session
        loaded = service.get_session(temp_project)

        assert loaded is not None
        assert loaded.session_id == created.session_id

    def test_get_session_returns_none_if_not_exists(
        self, service: SessionService, temp_project: Path
    ):
        """Test that get_session returns None if no session exists."""
        session = service.get_session(temp_project)
        assert session is None

    def test_get_session_emits_loaded_event(
        self, service: SessionService, temp_project: Path
    ):
        """Test that loading a session emits an event."""
        events: List[SessionLoadedEvent] = []

        def handler(event):
            if isinstance(event, SessionLoadedEvent):
                events.append(event)

        # Create session
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        # Clear cache
        service.clear_cache()

        # Register handler
        service.on_event(SessionEventType.SESSION_LOADED, handler)

        # Load session
        service.get_session(temp_project)

        assert len(events) == 1
        assert events[0].status == "running"

    def test_session_exists(self, service: SessionService, temp_project: Path):
        """Test checking if session exists."""
        assert not service.session_exists(temp_project)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        assert service.session_exists(temp_project)

    def test_get_session_summary(self, service: SessionService, temp_project: Path):
        """Test getting session summary."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
        )

        summary = service.get_session_summary(temp_project)

        assert summary is not None
        assert summary.status == "running"
        assert summary.task_source == ".ralph/prd.json"
        assert len(summary.pending_tasks) == 2

    def test_get_session_summary_returns_none_if_not_exists(
        self, service: SessionService, temp_project: Path
    ):
        """Test that summary returns None if no session."""
        summary = service.get_session_summary(temp_project)
        assert summary is None

    def test_get_task_statuses(self, service: SessionService, temp_project: Path):
        """Test getting task status summaries."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
        )

        # Start and complete a task
        service.start_task(temp_project, "T-001")
        service.increment_iterations(temp_project, "T-001")
        service.complete_task(temp_project, "T-001")

        statuses = service.get_task_statuses(temp_project)

        assert len(statuses) == 2

        t001 = next(s for s in statuses if s.task_id == "T-001")
        assert t001.passes is True
        assert t001.iterations == 1

    def test_get_task_status(self, service: SessionService, temp_project: Path):
        """Test getting a specific task status."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")

        status = service.get_task_status(temp_project, "T-001")

        assert status is not None
        assert status.task_id == "T-001"
        assert status.started_at is not None

    def test_list_sessions(self, service: SessionService, tmp_path: Path):
        """Test listing sessions across multiple projects."""
        projects = []
        for name in ["proj_a", "proj_b", "proj_c"]:
            proj = tmp_path / name
            proj.mkdir()
            (proj / ".ralph").mkdir()
            projects.append(proj)

        # Create sessions for first two projects
        for proj in projects[:2]:
            service.create_session(
                project_path=proj,
                task_source=".ralph/prd.json",
                task_source_type="prd_json",
            )

        summaries = service.list_sessions(projects)

        assert len(summaries) == 2


class TestSessionServiceUpdate:
    """Tests for UPDATE operations."""

    def test_start_task(self, service: SessionService, temp_project: Path):
        """Test starting a task."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")

        session = service.get_session(temp_project)
        assert session.metadata.current_task == "T-001"
        assert session.task_status.tasks["T-001"].started_at is not None

    def test_start_task_emits_event(self, service: SessionService, temp_project: Path):
        """Test that starting a task emits an event."""
        events: List[TaskStartedEvent] = []

        def handler(event):
            if isinstance(event, TaskStartedEvent):
                events.append(event)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.on_event(SessionEventType.TASK_STARTED, handler)
        service.start_task(temp_project, "T-001")

        assert len(events) == 1
        assert events[0].task_id == "T-001"

    def test_start_task_fails_without_session(
        self, service: SessionService, temp_project: Path
    ):
        """Test that starting a task fails without a session."""
        with pytest.raises(ValueError, match="No session found"):
            service.start_task(temp_project, "T-001")

    def test_complete_task(self, service: SessionService, temp_project: Path):
        """Test completing a task."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")
        service.complete_task(temp_project, "T-001")

        session = service.get_session(temp_project)
        assert session.task_status.tasks["T-001"].passes is True
        assert "T-001" in session.metadata.completed_tasks
        assert "T-001" not in session.metadata.pending_tasks

    def test_complete_task_emits_event(self, service: SessionService, temp_project: Path):
        """Test that completing a task emits an event."""
        events: List[TaskCompletedEvent] = []

        def handler(event):
            if isinstance(event, TaskCompletedEvent):
                events.append(event)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")
        service.increment_iterations(temp_project, "T-001")
        service.increment_iterations(temp_project, "T-001")

        service.on_event(SessionEventType.TASK_COMPLETED, handler)
        service.complete_task(temp_project, "T-001")

        assert len(events) == 1
        assert events[0].task_id == "T-001"
        assert events[0].iterations == 2

    def test_fail_task(self, service: SessionService, temp_project: Path):
        """Test recording a task failure."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")
        service.fail_task(temp_project, "T-001", "Test failed: assertion error")

        session = service.get_session(temp_project)
        assert session.task_status.tasks["T-001"].last_failure == "Test failed: assertion error"

    def test_fail_task_emits_event(self, service: SessionService, temp_project: Path):
        """Test that failing a task emits an event."""
        events: List[TaskFailedEvent] = []

        def handler(event):
            if isinstance(event, TaskFailedEvent):
                events.append(event)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")

        service.on_event(SessionEventType.TASK_FAILED, handler)
        service.fail_task(temp_project, "T-001", "Max iterations reached")

        assert len(events) == 1
        assert events[0].task_id == "T-001"
        assert events[0].reason == "Max iterations reached"

    def test_increment_iterations(self, service: SessionService, temp_project: Path):
        """Test incrementing iteration count."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")

        count1 = service.increment_iterations(temp_project, "T-001")
        count2 = service.increment_iterations(temp_project, "T-001")
        count3 = service.increment_iterations(temp_project, "T-001")

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

    def test_increment_iterations_emits_event(
        self, service: SessionService, temp_project: Path
    ):
        """Test that incrementing iterations emits an event."""
        events: List[IterationIncrementedEvent] = []

        def handler(event):
            if isinstance(event, IterationIncrementedEvent):
                events.append(event)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")

        service.on_event(SessionEventType.ITERATION_INCREMENTED, handler)
        service.increment_iterations(temp_project, "T-001")

        assert len(events) == 1
        assert events[0].task_id == "T-001"
        assert events[0].iteration == 1

    def test_update_current_task(self, service: SessionService, temp_project: Path):
        """Test updating current task."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
        )

        service.update_current_task(temp_project, "T-002")

        session = service.get_session(temp_project)
        assert session.metadata.current_task == "T-002"

    def test_update_current_task_emits_event(
        self, service: SessionService, temp_project: Path
    ):
        """Test that updating current task emits metadata event."""
        events: List[MetadataUpdatedEvent] = []

        def handler(event):
            if isinstance(event, MetadataUpdatedEvent):
                events.append(event)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        service.on_event(SessionEventType.METADATA_UPDATED, handler)
        service.update_current_task(temp_project, "T-001")

        assert len(events) == 1
        assert "current_task" in events[0].changes

    def test_end_session(self, service: SessionService, temp_project: Path):
        """Test ending a session."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        service.end_session(temp_project, status="completed")

        session = service.get_session(temp_project)
        assert session.metadata.status == "completed"
        assert session.metadata.ended_at is not None

    def test_end_session_emits_events(self, service: SessionService, temp_project: Path):
        """Test that ending a session emits events."""
        status_events: List[StatusChangedEvent] = []
        ended_events: List[SessionEndedEvent] = []

        def status_handler(event):
            if isinstance(event, StatusChangedEvent):
                status_events.append(event)

        def ended_handler(event):
            if isinstance(event, SessionEndedEvent):
                ended_events.append(event)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        service.on_event(SessionEventType.STATUS_CHANGED, status_handler)
        service.on_event(SessionEventType.SESSION_ENDED, ended_handler)
        service.end_session(temp_project, status="failed", failure_reason="Test failure")

        assert len(status_events) == 1
        assert status_events[0].old_status == "running"
        assert status_events[0].new_status == "failed"

        assert len(ended_events) == 1
        assert ended_events[0].status == "failed"
        assert ended_events[0].failure_reason == "Test failure"

    def test_record_agent_output(self, service: SessionService, temp_project: Path):
        """Test recording agent output path."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        service.start_task(temp_project, "T-001")
        service.record_agent_output(
            temp_project, "T-001", "implementation", "/path/to/log.txt"
        )

        session = service.get_session(temp_project)
        assert session.task_status.tasks["T-001"].agent_outputs["implementation"] == "/path/to/log.txt"


class TestSessionServiceDelete:
    """Tests for DELETE operations."""

    def test_delete_session(self, service: SessionService, temp_project: Path):
        """Test deleting a session."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        assert service.session_exists(temp_project)

        result = service.delete_session(temp_project)

        assert result is True
        assert not service.session_exists(temp_project)

    def test_delete_session_emits_event(self, service: SessionService, temp_project: Path):
        """Test that deleting a session emits an event."""
        events: List[SessionDeletedEvent] = []

        def handler(event):
            if isinstance(event, SessionDeletedEvent):
                events.append(event)

        session = service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )
        session_id = session.session_id

        service.on_event(SessionEventType.SESSION_DELETED, handler)
        service.delete_session(temp_project)

        assert len(events) == 1
        assert events[0].session_id == session_id

    def test_delete_nonexistent_session(self, service: SessionService, temp_project: Path):
        """Test deleting a non-existent session returns False."""
        result = service.delete_session(temp_project)
        assert result is False

    def test_clear_cache(self, service: SessionService, temp_project: Path):
        """Test clearing the session cache."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        path_key = str(temp_project.resolve())
        assert path_key in service._sessions

        service.clear_cache()

        assert len(service._sessions) == 0


class TestSessionServiceUtility:
    """Tests for utility methods."""

    def test_verify_session_integrity(self, service: SessionService, temp_project: Path):
        """Test verifying session integrity."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        # Should pass for fresh session
        result = service.verify_session_integrity(temp_project)
        assert result is True

    def test_verify_session_integrity_detects_tampering(
        self, service: SessionService, temp_project: Path
    ):
        """Test that tampering is detected."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        # Tamper with task status
        status_path = temp_project / ".ralph-session" / "task-status.json"
        status_data = json.loads(status_path.read_text())
        status_data["tasks"]["T-001"]["passes"] = True  # Manual tampering
        status_path.write_text(json.dumps(status_data))

        # Clear cache to force reload
        service.clear_cache()

        with pytest.raises(TamperingDetectedError):
            service.verify_session_integrity(temp_project)

    def test_get_log_path_with_session(self, service: SessionService, temp_project: Path):
        """Test getting log path with active session."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        log_path = service.get_log_path(temp_project, "implementation", "T-001")

        assert log_path.name == "T-001-implementation.log"
        assert "logs" in str(log_path)

    def test_get_log_path_without_session(
        self, service: SessionService, temp_project: Path
    ):
        """Test getting log path without session creates reasonable path."""
        log_path = service.get_log_path(temp_project, "implementation", "T-001")

        assert log_path.name == "T-001-implementation.log"

    def test_get_report_path(self, service: SessionService, temp_project: Path):
        """Test getting report path."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        report_path = service.get_report_path(temp_project, "test_writing", "T-001")

        assert report_path.name == "test-writing.md"
        assert "T-001" in str(report_path)


class TestSessionServiceEvents:
    """Tests for event handling."""

    def test_on_all_events(self, service: SessionService, temp_project: Path):
        """Test global event handler."""
        events = []

        def handler(event):
            events.append(event)

        service.on_all_events(handler)
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )
        service.start_task(temp_project, "T-001")

        event_types = {e.event_type for e in events}
        assert SessionEventType.SESSION_CREATED in event_types
        assert SessionEventType.TASK_STARTED in event_types

    def test_remove_handler(self, service: SessionService, temp_project: Path):
        """Test removing an event handler."""
        events = []

        def handler(event):
            events.append(event)

        service.on_event(SessionEventType.SESSION_CREATED, handler)
        service.remove_handler(SessionEventType.SESSION_CREATED, handler)

        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        created_events = [
            e for e in events if e.event_type == SessionEventType.SESSION_CREATED
        ]
        assert len(created_events) == 0


class TestSessionServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_session_with_string_path(self, service: SessionService, temp_project: Path):
        """Test getting session using string path instead of Path object."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        # Clear cache and get with string
        service.clear_cache()
        session = service.get_session(str(temp_project))

        assert session is not None

    def test_create_session_without_pending_tasks(
        self, service: SessionService, temp_project: Path
    ):
        """Test creating session with no pending tasks."""
        session = service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=None,
        )

        assert session is not None
        assert len(session.metadata.pending_tasks) == 0

    def test_multiple_task_operations(self, service: SessionService, temp_project: Path):
        """Test multiple tasks can be managed in parallel."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002", "T-003"],
        )

        # Start multiple tasks
        service.start_task(temp_project, "T-001")
        service.increment_iterations(temp_project, "T-001")
        service.complete_task(temp_project, "T-001")

        service.start_task(temp_project, "T-002")
        service.fail_task(temp_project, "T-002", "Test error")

        service.start_task(temp_project, "T-003")

        # Verify all states
        statuses = service.get_task_statuses(temp_project)
        assert len(statuses) == 3

        t001 = next(s for s in statuses if s.task_id == "T-001")
        assert t001.passes is True
        assert t001.iterations == 1

        t002 = next(s for s in statuses if s.task_id == "T-002")
        assert t002.passes is False
        assert t002.last_failure == "Test error"

        t003 = next(s for s in statuses if s.task_id == "T-003")
        assert t003.started_at is not None
        assert t003.completed_at is None

    def test_task_status_not_found(self, service: SessionService, temp_project: Path):
        """Test getting status for non-existent task."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
        )

        status = service.get_task_status(temp_project, "T-999")
        assert status is None

    def test_complete_task_without_start(self, service: SessionService, temp_project: Path):
        """Test completing a task that wasn't explicitly started."""
        service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
        )

        # Complete without explicit start (should auto-start)
        service.complete_task(temp_project, "T-001")

        status = service.get_task_status(temp_project, "T-001")
        assert status.passes is True

    def test_session_with_config_path(self, service: SessionService, temp_project: Path):
        """Test creating session with explicit config path."""
        session = service.create_session(
            project_path=temp_project,
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            config_path=".ralph/ralph.yml",
        )

        assert session is not None

    def test_list_sessions_with_empty_list(self, service: SessionService):
        """Test listing sessions with empty project list."""
        summaries = service.list_sessions([])
        assert len(summaries) == 0

    def test_increment_iterations_without_session(
        self, service: SessionService, temp_project: Path
    ):
        """Test that incrementing iterations fails without a session."""
        with pytest.raises(ValueError, match="No session found"):
            service.increment_iterations(temp_project, "T-001")

    def test_update_current_task_without_session(
        self, service: SessionService, temp_project: Path
    ):
        """Test that updating current task fails without a session."""
        with pytest.raises(ValueError, match="No session found"):
            service.update_current_task(temp_project, "T-001")

    def test_end_session_without_session(
        self, service: SessionService, temp_project: Path
    ):
        """Test that ending a non-existent session fails."""
        with pytest.raises(ValueError, match="No session found"):
            service.end_session(temp_project)

    def test_verify_session_integrity_without_session(
        self, service: SessionService, temp_project: Path
    ):
        """Test that verifying non-existent session fails."""
        with pytest.raises(ValueError, match="No session found"):
            service.verify_session_integrity(temp_project)


class TestEventDataclasses:
    """Tests for event dataclass serialization."""

    def test_session_summary_to_dict(self, temp_project: Path):
        """Test SessionSummary serialization."""
        summary = SessionSummary(
            session_id="test-123",
            session_token="ralph-test-123",
            project_path=temp_project,
            status="running",
            started_at="2026-01-27T12:00:00Z",
            ended_at=None,
            task_source=".ralph/prd.json",
            current_task="T-001",
            completed_tasks=["T-000"],
            pending_tasks=["T-001", "T-002"],
            total_iterations=5,
            git_branch="main",
            git_commit="abc123",
        )

        d = summary.to_dict()

        assert d["session_id"] == "test-123"
        assert d["status"] == "running"
        assert d["current_task"] == "T-001"
        assert len(d["pending_tasks"]) == 2

    def test_task_status_summary_to_dict(self):
        """Test TaskStatusSummary serialization."""
        summary = TaskStatusSummary(
            task_id="T-001",
            passes=True,
            started_at="2026-01-27T12:00:00Z",
            completed_at="2026-01-27T12:30:00Z",
            iterations=3,
            last_failure=None,
        )

        d = summary.to_dict()

        assert d["task_id"] == "T-001"
        assert d["passes"] is True
        assert d["iterations"] == 3

    def test_session_created_event_to_dict(self):
        """Test SessionCreatedEvent serialization."""
        event = SessionCreatedEvent(
            project_path="/path/to/project",
            session_id="test-123",
            task_source=".ralph/prd.json",
            pending_tasks=["T-001", "T-002"],
        )

        d = event.to_dict()

        assert d["event_type"] == "session_created"
        assert d["task_source"] == ".ralph/prd.json"
        assert len(d["pending_tasks"]) == 2

    def test_task_completed_event_to_dict(self):
        """Test TaskCompletedEvent serialization."""
        event = TaskCompletedEvent(
            project_path="/path",
            session_id="test-123",
            task_id="T-001",
            iterations=5,
        )

        d = event.to_dict()

        assert d["event_type"] == "task_completed"
        assert d["task_id"] == "T-001"
        assert d["iterations"] == 5

    def test_session_loaded_event_to_dict(self):
        """Test SessionLoadedEvent serialization."""
        event = SessionLoadedEvent(
            project_path="/path",
            session_id="test-123",
            status="running",
            tasks_completed=2,
            tasks_pending=3,
        )

        d = event.to_dict()

        assert d["event_type"] == "session_loaded"
        assert d["status"] == "running"
        assert d["tasks_completed"] == 2

    def test_task_failed_event_to_dict(self):
        """Test TaskFailedEvent serialization."""
        event = TaskFailedEvent(
            project_path="/path",
            session_id="test-123",
            task_id="T-001",
            reason="Max iterations exceeded",
        )

        d = event.to_dict()

        assert d["event_type"] == "task_failed"
        assert d["task_id"] == "T-001"
        assert d["reason"] == "Max iterations exceeded"

    def test_iteration_incremented_event_to_dict(self):
        """Test IterationIncrementedEvent serialization."""
        event = IterationIncrementedEvent(
            project_path="/path",
            session_id="test-123",
            task_id="T-001",
            iteration=3,
            total_iterations=10,
        )

        d = event.to_dict()

        assert d["event_type"] == "iteration_incremented"
        assert d["iteration"] == 3
        assert d["total_iterations"] == 10

    def test_status_changed_event_to_dict(self):
        """Test StatusChangedEvent serialization."""
        event = StatusChangedEvent(
            project_path="/path",
            session_id="test-123",
            old_status="running",
            new_status="completed",
        )

        d = event.to_dict()

        assert d["event_type"] == "status_changed"
        assert d["old_status"] == "running"
        assert d["new_status"] == "completed"
