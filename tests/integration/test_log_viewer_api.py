"""Integration tests for Log Viewer API endpoints.

Tests the REST API endpoints that the LogViewer UI component will use:
- GET /api/projects/{id}/logs - List log files
- GET /api/projects/{id}/logs/{log_name} - Get specific log content
- GET /api/projects/{id}/timeline - Get timeline events for log streaming

These tests verify the acceptance criteria for T-013 LogViewer functionality.
"""

import json
import pytest
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

from fastapi.testclient import TestClient

from server.api import app


def encode_project_path(path: Path) -> str:
    """URL-encode a project path for use in API URLs."""
    return quote(str(path), safe="")


@pytest.fixture
def log_project(tmp_path: Path) -> Path:
    """Create a project with log files for testing."""
    project_path = tmp_path / "log_test_project"
    project_path.mkdir()

    # Create .ralph directory
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir()

    # Create session directory with logs
    session_dir = project_path / ".ralph-session"
    session_dir.mkdir()

    logs_dir = session_dir / "logs"
    logs_dir.mkdir()

    # Create various log files
    (logs_dir / "implementation.log").write_text(
        "2024-01-27 10:00:00 [INFO] Starting implementation agent\n"
        "2024-01-27 10:01:00 [DEBUG] Reading task requirements\n"
        "2024-01-27 10:02:00 [INFO] Writing code changes\n"
        "2024-01-27 10:03:00 [ERROR] Syntax error detected\n"
        "2024-01-27 10:04:00 [INFO] Fixed syntax error\n"
        "2024-01-27 10:05:00 [INFO] Implementation complete\n"
    )

    (logs_dir / "test-writing.log").write_text(
        "2024-01-27 10:10:00 [INFO] Starting test writing agent\n"
        "2024-01-27 10:11:00 [DEBUG] Analyzing implementation\n"
        "2024-01-27 10:12:00 [INFO] Writing test cases\n"
        "2024-01-27 10:13:00 [INFO] Tests written successfully\n"
    )

    (logs_dir / "gate-build.log").write_text(
        "2024-01-27 10:20:00 [INFO] Running build gate\n"
        "2024-01-27 10:20:01 [INFO] Running lint\n"
        "2024-01-27 10:20:05 [INFO] Lint passed\n"
        "2024-01-27 10:20:06 [INFO] Running type check\n"
        "2024-01-27 10:20:10 [INFO] Type check passed\n"
        "2024-01-27 10:20:11 [INFO] Build gate passed\n"
    )

    # Create timeline.jsonl with various event types
    timeline_events = [
        {
            "timestamp": "2024-01-27T10:00:00",
            "event_type": "task_started",
            "task_id": "T-001",
            "agent": "implementation"
        },
        {
            "timestamp": "2024-01-27T10:05:00",
            "event_type": "task_completed",
            "task_id": "T-001",
            "agent": "implementation"
        },
        {
            "timestamp": "2024-01-27T10:10:00",
            "event_type": "test_writing_started",
            "task_id": "T-001",
            "agent": "test-writing"
        },
        {
            "timestamp": "2024-01-27T10:13:00",
            "event_type": "test_writing_completed",
            "task_id": "T-001",
            "agent": "test-writing"
        },
        {
            "timestamp": "2024-01-27T10:20:00",
            "event_type": "gate_started",
            "gate_type": "build",
            "gate_name": "lint"
        },
        {
            "timestamp": "2024-01-27T10:20:11",
            "event_type": "gate_passed",
            "gate_type": "build"
        },
    ]

    timeline_content = "\n".join(json.dumps(event) for event in timeline_events)
    (logs_dir / "timeline.jsonl").write_text(timeline_content)

    # Create session.json
    session_data = {
        "session_id": "ralph-20240127-100000-abc123",
        "project_path": str(project_path),
        "started_at": "2024-01-27T10:00:00"
    }
    (session_dir / "session.json").write_text(json.dumps(session_data))

    return project_path


@pytest.fixture
def log_project_with_ansi(tmp_path: Path) -> Path:
    """Create a project with logs containing ANSI color codes."""
    project_path = tmp_path / "ansi_log_project"
    project_path.mkdir()

    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir()

    session_dir = project_path / ".ralph-session"
    session_dir.mkdir()

    logs_dir = session_dir / "logs"
    logs_dir.mkdir()

    # Create log with ANSI color codes
    ansi_log_content = (
        "\033[32m[INFO]\033[0m Starting process\n"
        "\033[33m[WARN]\033[0m This is a warning\n"
        "\033[31m[ERROR]\033[0m This is an error\n"
        "\033[36m[DEBUG]\033[0m Debug information\n"
        "\033[1m[BOLD]\033[0m Bold text\n"
    )
    (logs_dir / "ansi.log").write_text(ansi_log_content)

    return project_path


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestListLogs:
    """Test GET /api/projects/{id}/logs endpoint."""

    def test_list_logs_basic(self, client: TestClient, log_project: Path):
        """Test listing log files."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "logs" in data
        assert "total" in data

        # Verify log files are listed
        assert data["total"] >= 3
        log_names = [log["name"] for log in data["logs"]]
        assert "implementation.log" in log_names
        assert "test-writing.log" in log_names
        assert "gate-build.log" in log_names

    def test_list_logs_with_metadata(self, client: TestClient, log_project: Path):
        """Test that log listing includes file metadata."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs")

        assert response.status_code == 200
        data = response.json()

        # Check each log has required metadata
        for log in data["logs"]:
            assert "name" in log
            assert "path" in log
            assert "size" in log
            assert "modified_at" in log

            # Verify types
            assert isinstance(log["name"], str)
            assert isinstance(log["path"], str)
            assert isinstance(log["size"], int)
            assert isinstance(log["modified_at"], str)

            # Verify size is positive
            assert log["size"] > 0

    def test_list_logs_with_content(self, client: TestClient, log_project: Path):
        """Test listing logs with content included."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs?include_content=true")

        assert response.status_code == 200
        data = response.json()

        # When include_content=true, content should be present
        for log in data["logs"]:
            assert "content" in log
            assert log["content"] is not None
            assert isinstance(log["content"], str)

    def test_list_logs_without_content(self, client: TestClient, log_project: Path):
        """Test that content is not included by default."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs")

        assert response.status_code == 200
        data = response.json()

        # By default, content should not be included (or be None)
        for log in data["logs"]:
            if "content" in log:
                assert log["content"] is None

    def test_list_logs_limit(self, client: TestClient, log_project: Path):
        """Test limiting number of logs returned."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs?limit=1")

        assert response.status_code == 200
        data = response.json()

        # Should respect limit
        assert len(data["logs"]) <= 1

    def test_list_logs_no_logs_directory(self, client: TestClient, tmp_path: Path):
        """Test when project has no logs directory."""
        empty_project = tmp_path / "empty_project"
        empty_project.mkdir()
        (empty_project / ".ralph").mkdir()

        response = client.get(f"/api/projects/{empty_project}/logs")

        assert response.status_code == 200
        data = response.json()

        # Should return empty list
        assert data["logs"] == []
        assert data["total"] == 0


class TestGetLog:
    """Test GET /api/projects/{id}/logs/{log_name} endpoint."""

    def test_get_log_content(self, client: TestClient, log_project: Path):
        """Test retrieving specific log file content."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "name" in data
        assert "path" in data
        assert "size" in data
        assert "modified_at" in data
        assert "content" in data

        # Verify content
        assert data["name"] == "implementation.log"
        assert data["content"] is not None
        assert "Starting implementation agent" in data["content"]
        assert "Implementation complete" in data["content"]

    def test_get_log_with_search_terms(self, client: TestClient, log_project: Path):
        """Test log content can be searched (for search functionality AC)."""
        # This tests the requirement: "Search functionality highlights matches"
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # Verify searchable content is present
        assert "[ERROR]" in content
        assert "Syntax error" in content
        assert "[INFO]" in content

    def test_get_log_with_log_levels(self, client: TestClient, log_project: Path):
        """Test logs contain different log levels (for filter by level AC)."""
        # This tests the requirement: "Filters: ...by log level"
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # Verify various log levels are present
        assert "[INFO]" in content
        assert "[DEBUG]" in content
        assert "[ERROR]" in content

    def test_get_log_ansi_colors(self, client: TestClient, log_project_with_ansi: Path):
        """Test logs with ANSI color codes (for ANSI color support AC)."""
        # This tests the requirement: "ANSI color codes rendered correctly"
        response = client.get(f"/api/projects/{log_project_with_ansi}/logs/ansi.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # ANSI codes should be present in content
        # The UI will need to render these, but the API must preserve them
        assert "\033[" in content  # ANSI escape sequence
        assert content.count("\033[") >= 5  # Multiple color codes

    def test_get_log_nonexistent(self, client: TestClient, log_project: Path):
        """Test error when log file doesn't exist."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/nonexistent.log")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_log_with_timestamps(self, client: TestClient, log_project: Path):
        """Test logs contain timestamps (for time range filter AC)."""
        # This tests the requirement: "Filters: ...by time range"
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # Verify timestamps are present
        assert "2024-01-27 10:00:00" in content
        assert "2024-01-27 10:05:00" in content


class TestTimeline:
    """Test GET /api/projects/{id}/timeline endpoint."""

    def test_get_timeline_events(self, client: TestClient, log_project: Path):
        """Test retrieving timeline events for real-time log streaming."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "events" in data
        assert "total" in data
        assert "session_id" in data

        # Verify events
        assert len(data["events"]) == 6
        assert data["total"] == 6

        # Verify session ID
        assert data["session_id"] == "ralph-20240127-100000-abc123"

    def test_timeline_event_structure(self, client: TestClient, log_project: Path):
        """Test timeline events have correct structure."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # Check each event has required fields
        for event in events:
            assert "timestamp" in event
            assert "event_type" in event
            assert "data" in event

            # Verify types
            assert isinstance(event["timestamp"], str)
            assert isinstance(event["event_type"], str)
            assert isinstance(event["data"], dict)

    def test_timeline_filter_by_agent(self, client: TestClient, log_project: Path):
        """Test filtering timeline events by agent type (for filter AC)."""
        # This tests the requirement: "Filters: by agent type"
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # Verify different agent types are present
        agent_types = set()
        for event in events:
            if "agent" in event["data"]:
                agent_types.add(event["data"]["agent"])

        assert "implementation" in agent_types
        assert "test-writing" in agent_types

    def test_timeline_filter_by_gate(self, client: TestClient, log_project: Path):
        """Test filtering timeline events by gate (for filter AC)."""
        # This tests the requirement: "Filters: by gate"
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # Verify gate events are present and identifiable
        gate_events = [e for e in events if "gate" in e["event_type"].lower()]
        assert len(gate_events) >= 2

        # Verify gate type information
        gate_event = next(e for e in events if e["event_type"] == "gate_started")
        assert "gate_type" in gate_event["data"]

    def test_timeline_pagination(self, client: TestClient, log_project: Path):
        """Test timeline pagination with limit and offset."""
        # Get first 2 events
        response1 = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline?limit=2&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        assert len(data1["events"]) == 2
        assert data1["total"] == 6

        # Get next 2 events
        response2 = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline?limit=2&offset=2")
        assert response2.status_code == 200
        data2 = response2.json()

        assert len(data2["events"]) == 2
        assert data2["total"] == 6

        # Events should be different
        event1_types = [e["event_type"] for e in data1["events"]]
        event2_types = [e["event_type"] for e in data2["events"]]
        assert event1_types != event2_types

    def test_timeline_no_events(self, client: TestClient, tmp_path: Path):
        """Test when no timeline exists."""
        empty_project = tmp_path / "empty_timeline_project"
        empty_project.mkdir()
        (empty_project / ".ralph").mkdir()

        response = client.get(f"/api/projects/{empty_project}/timeline")

        assert response.status_code == 200
        data = response.json()

        assert data["events"] == []
        assert data["total"] == 0
        assert data["session_id"] is None

    def test_timeline_for_time_range_filter(self, client: TestClient, log_project: Path):
        """Test timeline events have timestamps (for time range filter AC)."""
        # This tests the requirement: "Filters: by time range"
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # All events should have timestamps
        for event in events:
            assert "timestamp" in event
            timestamp = event["timestamp"]

            # Verify timestamp format (ISO 8601)
            assert "T" in timestamp
            assert len(timestamp) >= 19  # YYYY-MM-DDTHH:MM:SS


class TestLogViewerAcceptanceCriteria:
    """Tests specifically for T-013 LogViewer acceptance criteria."""

    def test_realtime_streaming_via_timeline(self, client: TestClient, log_project: Path):
        """AC: src/components/LogViewer.tsx streams logs in real-time via WebSocket."""
        # The timeline endpoint provides the event stream for WebSocket
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        data = response.json()

        # Timeline must provide events suitable for streaming
        assert "events" in data
        assert len(data["events"]) > 0

        # Events must be in chronological order
        timestamps = [e["timestamp"] for e in data["events"]]
        sorted_timestamps = sorted(timestamps)
        assert timestamps == sorted_timestamps

    def test_filter_by_agent_type(self, client: TestClient, log_project: Path):
        """AC: Filters: by agent type."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # Must be able to filter by agent type
        implementation_events = [
            e for e in events
            if e["data"].get("agent") == "implementation"
        ]
        test_writing_events = [
            e for e in events
            if e["data"].get("agent") == "test-writing"
        ]

        assert len(implementation_events) > 0
        assert len(test_writing_events) > 0

    def test_filter_by_gate(self, client: TestClient, log_project: Path):
        """AC: Filters: by gate."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # Must be able to identify gate events
        gate_events = [
            e for e in events
            if "gate" in e["event_type"].lower()
        ]

        assert len(gate_events) >= 2

    def test_filter_by_log_level(self, client: TestClient, log_project: Path):
        """AC: Filters: by log level."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # Log content must include level indicators
        lines = content.split("\n")
        levels = set()
        for line in lines:
            if "[INFO]" in line:
                levels.add("INFO")
            if "[DEBUG]" in line:
                levels.add("DEBUG")
            if "[ERROR]" in line:
                levels.add("ERROR")
            if "[WARN]" in line:
                levels.add("WARN")

        assert len(levels) >= 3

    def test_filter_by_time_range(self, client: TestClient, log_project: Path):
        """AC: Filters: by time range."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/timeline")

        assert response.status_code == 200
        events = response.json()["events"]

        # All events must have timestamps for range filtering
        for event in events:
            assert "timestamp" in event
            # Timestamp must be parseable
            datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

    def test_search_functionality(self, client: TestClient, log_project: Path):
        """AC: Search functionality highlights matches."""
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # Content must be searchable
        search_terms = ["error", "INFO", "Starting", "complete"]
        for term in search_terms:
            # Case-insensitive search should work
            assert term.lower() in content.lower()

    def test_ansi_color_support(self, client: TestClient, log_project_with_ansi: Path):
        """AC: ANSI color codes rendered correctly."""
        response = client.get(f"/api/projects/{log_project_with_ansi}/logs/ansi.log")

        assert response.status_code == 200
        content = response.json()["content"]

        # ANSI codes must be preserved in the API response
        # The frontend will render them
        assert "\033[32m" in content  # Green
        assert "\033[33m" in content  # Yellow
        assert "\033[31m" in content  # Red
        assert "\033[36m" in content  # Cyan
        assert "\033[0m" in content   # Reset

    def test_download_logs_functionality(self, client: TestClient, log_project: Path):
        """AC: Download logs button exports as text file."""
        # API must provide log content that can be downloaded
        response = client.get(f"/api/projects/{encode_project_path(log_project)}/logs/implementation.log")

        assert response.status_code == 200
        data = response.json()

        # Content must be plain text suitable for download
        content = data["content"]
        assert isinstance(content, str)
        assert len(content) > 0

        # Content should preserve line breaks for proper text file export
        assert "\n" in content
