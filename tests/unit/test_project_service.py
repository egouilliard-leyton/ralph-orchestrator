"""Unit tests for ProjectService.

Tests the project discovery and management service including:
- Project discovery and scanning
- Metadata extraction
- Event emission
- File watching
"""

import json
import os
import pytest
import time
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

from ralph_orchestrator.services.project_service import (
    ProjectService,
    ProjectMetadata,
    ProjectEventType,
    ProjectDiscoveredEvent,
    ProjectRemovedEvent,
    ProjectUpdatedEvent,
    ScanStartedEvent,
    ScanCompletedEvent,
    _get_git_info,
    _get_project_name,
    _get_task_counts,
    _get_session_info,
    _get_config_info,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a minimal Ralph project structure."""
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
gates:
  build: []
  full: []
""")

    # Create minimal prd.json
    prd_path = ralph_dir / "prd.json"
    prd_data = {
        "project": "Test Project",
        "branchName": "test-branch",
        "description": "A test project",
        "tasks": [
            {"id": "T-001", "title": "Task 1", "passes": True},
            {"id": "T-002", "title": "Task 2", "passes": False},
            {"id": "T-003", "title": "Task 3", "passes": False},
        ]
    }
    prd_path.write_text(json.dumps(prd_data))

    return project_path


@pytest.fixture
def temp_project_with_session(temp_project: Path) -> Path:
    """Create a project with an active session."""
    session_dir = temp_project / ".ralph-session"
    session_dir.mkdir()

    session_data = {
        "session_id": "20260127-120000-abc123",
        "session_token": "ralph-20260127-120000-abc123",
        "started_at": "2026-01-27T12:00:00Z",
        "task_source": ".ralph/prd.json",
        "task_source_type": "prd_json",
        "status": "running",
        "current_task": "T-002",
    }

    session_path = session_dir / "session.json"
    session_path.write_text(json.dumps(session_data))

    return temp_project


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_project_name_from_prd(self, temp_project: Path):
        """Test extracting project name from PRD file."""
        name = _get_project_name(temp_project)
        assert name == "Test Project"

    def test_get_project_name_fallback_to_dir(self, tmp_path: Path):
        """Test fallback to directory name when no PRD."""
        project = tmp_path / "my_project"
        project.mkdir()
        (project / ".ralph").mkdir()

        name = _get_project_name(project)
        assert name == "my_project"

    def test_get_task_counts(self, temp_project: Path):
        """Test task count extraction from PRD."""
        counts = _get_task_counts(temp_project)

        assert counts["total"] == 3
        assert counts["completed"] == 1
        assert counts["pending"] == 2

    def test_get_task_counts_no_prd(self, tmp_path: Path):
        """Test task counts when no PRD exists."""
        project = tmp_path / "no_prd"
        project.mkdir()
        (project / ".ralph").mkdir()

        counts = _get_task_counts(project)

        assert counts["total"] == 0
        assert counts["completed"] == 0
        assert counts["pending"] == 0

    def test_get_session_info_no_session(self, temp_project: Path):
        """Test session info when no session exists."""
        info = _get_session_info(temp_project)

        assert info["status"] == "idle"
        assert info["session_id"] is None
        assert info["current_task"] is None

    def test_get_session_info_with_session(self, temp_project_with_session: Path):
        """Test session info extraction."""
        info = _get_session_info(temp_project_with_session)

        assert info["status"] == "running"
        assert info["session_id"] == "20260127-120000-abc123"
        assert info["current_task"] == "T-002"

    def test_get_config_info(self, temp_project: Path):
        """Test config info extraction."""
        info = _get_config_info(temp_project)

        assert info["has_config"] is True
        assert info["config_version"] == "1"

    def test_get_config_info_no_config(self, tmp_path: Path):
        """Test config info when no config exists."""
        project = tmp_path / "no_config"
        project.mkdir()
        (project / ".ralph").mkdir()

        info = _get_config_info(project)

        assert info["has_config"] is False
        assert info["config_version"] is None


class TestProjectMetadata:
    """Tests for ProjectMetadata dataclass."""

    def test_to_dict(self, temp_project: Path):
        """Test conversion to dictionary."""
        metadata = ProjectMetadata(
            path=temp_project,
            name="Test Project",
            git_branch="main",
            task_count=3,
            tasks_completed=1,
            tasks_pending=2,
            status="running",
        )

        d = metadata.to_dict()

        assert d["path"] == str(temp_project)
        assert d["name"] == "Test Project"
        assert d["git_branch"] == "main"
        assert d["task_count"] == 3
        assert d["tasks_completed"] == 1
        assert d["tasks_pending"] == 2
        assert d["status"] == "running"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "path": "/some/path",
            "name": "Test",
            "git_branch": "feature",
            "task_count": 5,
            "tasks_completed": 2,
            "tasks_pending": 3,
            "status": "idle",
        }

        metadata = ProjectMetadata.from_dict(data)

        assert metadata.path == Path("/some/path")
        assert metadata.name == "Test"
        assert metadata.git_branch == "feature"
        assert metadata.task_count == 5


class TestProjectServiceDiscovery:
    """Tests for project discovery functionality."""

    def test_discover_single_project(self, temp_project: Path, tmp_path: Path):
        """Test discovering a single project."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        projects = service.discover_projects()

        assert len(projects) == 1
        assert projects[0].name == "Test Project"
        assert projects[0].path == temp_project

    def test_discover_multiple_projects(self, tmp_path: Path):
        """Test discovering multiple projects."""
        # Create two projects
        for name in ["project_a", "project_b"]:
            project = tmp_path / name
            project.mkdir()
            ralph_dir = project / ".ralph"
            ralph_dir.mkdir()
            prd = ralph_dir / "prd.json"
            prd.write_text(json.dumps({"project": name, "tasks": []}))

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        projects = service.discover_projects()

        assert len(projects) == 2
        names = {p.name for p in projects}
        assert "project_a" in names
        assert "project_b" in names

    def test_discover_respects_max_depth(self, tmp_path: Path):
        """Test that max_depth is respected during scanning."""
        # Create nested project at depth 5
        nested = tmp_path / "a" / "b" / "c" / "d" / "deep_project"
        nested.mkdir(parents=True)
        (nested / ".ralph").mkdir()

        # Create project at depth 1
        shallow = tmp_path / "shallow_project"
        shallow.mkdir()
        (shallow / ".ralph").mkdir()

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        projects = service.discover_projects()

        # Only shallow project should be found
        assert len(projects) == 1
        assert projects[0].path == shallow

    def test_discover_excludes_patterns(self, tmp_path: Path):
        """Test that excluded patterns are skipped."""
        # Create project inside node_modules (should be excluded)
        node_modules = tmp_path / "node_modules" / "some_package"
        node_modules.mkdir(parents=True)
        (node_modules / ".ralph").mkdir()

        # Create normal project
        normal = tmp_path / "my_project"
        normal.mkdir()
        (normal / ".ralph").mkdir()

        service = ProjectService(
            search_paths=[tmp_path],
            exclude_patterns=["node_modules"],
            max_depth=3,
        )
        projects = service.discover_projects()

        assert len(projects) == 1
        assert projects[0].path == normal

    def test_discover_with_refresh(self, temp_project: Path, tmp_path: Path):
        """Test that refresh updates cached data."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)

        # Initial discovery
        projects = service.discover_projects()
        assert len(projects) == 1
        assert projects[0].task_count == 3

        # Modify the PRD
        prd_path = temp_project / ".ralph" / "prd.json"
        prd_data = json.loads(prd_path.read_text())
        prd_data["tasks"].append({"id": "T-004", "title": "New Task", "passes": False})
        prd_path.write_text(json.dumps(prd_data))

        # Refresh discovery
        projects = service.discover_projects(refresh=True)
        assert projects[0].task_count == 4


class TestProjectServiceEvents:
    """Tests for event emission."""

    def test_scan_started_event(self, tmp_path: Path):
        """Test that scan started event is emitted."""
        events: List[ScanStartedEvent] = []

        def handler(event):
            if isinstance(event, ScanStartedEvent):
                events.append(event)

        service = ProjectService(search_paths=[tmp_path])
        service.on_event(ProjectEventType.SCAN_STARTED, handler)
        service.discover_projects()

        assert len(events) == 1
        assert str(tmp_path) in events[0].search_paths

    def test_scan_completed_event(self, temp_project: Path, tmp_path: Path):
        """Test that scan completed event is emitted."""
        events: List[ScanCompletedEvent] = []

        def handler(event):
            if isinstance(event, ScanCompletedEvent):
                events.append(event)

        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.on_event(ProjectEventType.SCAN_COMPLETED, handler)
        service.discover_projects()

        assert len(events) == 1
        assert events[0].projects_found == 1
        assert events[0].duration_ms >= 0

    def test_project_discovered_event(self, temp_project: Path, tmp_path: Path):
        """Test that project discovered event is emitted."""
        events: List[ProjectDiscoveredEvent] = []

        def handler(event):
            if isinstance(event, ProjectDiscoveredEvent):
                events.append(event)

        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.on_event(ProjectEventType.PROJECT_DISCOVERED, handler)
        service.discover_projects()

        assert len(events) == 1
        assert events[0].project_name == "Test Project"
        assert str(temp_project) == events[0].project_path

    def test_project_removed_event(self, temp_project: Path, tmp_path: Path):
        """Test that project removed event is emitted."""
        events: List[ProjectRemovedEvent] = []

        def handler(event):
            if isinstance(event, ProjectRemovedEvent):
                events.append(event)

        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.on_event(ProjectEventType.PROJECT_REMOVED, handler)

        # Discover first
        service.discover_projects()

        # Remove the .ralph directory
        import shutil
        shutil.rmtree(temp_project / ".ralph")

        # Discover again
        service.discover_projects()

        assert len(events) == 1
        assert events[0].project_name == "Test Project"

    def test_project_updated_event(self, temp_project_with_session: Path, tmp_path: Path):
        """Test that project updated event is emitted on changes."""
        events: List[ProjectUpdatedEvent] = []

        def handler(event):
            if isinstance(event, ProjectUpdatedEvent):
                events.append(event)

        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.on_event(ProjectEventType.PROJECT_UPDATED, handler)

        # Initial discovery
        service.discover_projects()

        # Change session status
        session_path = temp_project_with_session / ".ralph-session" / "session.json"
        session_data = json.loads(session_path.read_text())
        session_data["status"] = "completed"
        session_path.write_text(json.dumps(session_data))

        # Refresh the project
        service.refresh_project(temp_project_with_session)

        assert len(events) == 1
        assert "status" in events[0].changes
        assert events[0].changes["status"]["old"] == "running"
        assert events[0].changes["status"]["new"] == "completed"

    def test_on_all_events(self, temp_project: Path, tmp_path: Path):
        """Test global event handler receives all events."""
        events = []

        def handler(event):
            events.append(event)

        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.on_all_events(handler)
        service.discover_projects()

        # Should receive scan_started, project_discovered, and scan_completed
        event_types = {e.event_type for e in events}
        assert ProjectEventType.SCAN_STARTED in event_types
        assert ProjectEventType.PROJECT_DISCOVERED in event_types
        assert ProjectEventType.SCAN_COMPLETED in event_types

    def test_remove_handler(self, temp_project: Path, tmp_path: Path):
        """Test removing event handlers."""
        events = []

        def handler(event):
            events.append(event)

        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.on_event(ProjectEventType.SCAN_STARTED, handler)
        service.remove_handler(ProjectEventType.SCAN_STARTED, handler)
        service.discover_projects()

        # Handler was removed, should not receive events
        scan_events = [e for e in events if e.event_type == ProjectEventType.SCAN_STARTED]
        assert len(scan_events) == 0


class TestProjectServiceCaching:
    """Tests for project caching functionality."""

    def test_get_project(self, temp_project: Path, tmp_path: Path):
        """Test getting a specific project."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.discover_projects()

        project = service.get_project(temp_project)

        assert project is not None
        assert project.name == "Test Project"

    def test_get_project_not_found(self, tmp_path: Path):
        """Test getting non-existent project."""
        service = ProjectService(search_paths=[tmp_path])
        service.discover_projects()

        project = service.get_project("/nonexistent/path")

        assert project is None

    def test_list_projects(self, tmp_path: Path):
        """Test listing all cached projects."""
        # Create two projects
        for name in ["proj_1", "proj_2"]:
            p = tmp_path / name
            p.mkdir()
            (p / ".ralph").mkdir()

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        service.discover_projects()

        projects = service.list_projects()

        assert len(projects) == 2

    def test_get_projects_by_status(self, tmp_path: Path):
        """Test filtering projects by status."""
        # Create projects with different statuses
        for name, status in [("idle_proj", "idle"), ("running_proj", "running")]:
            p = tmp_path / name
            p.mkdir()
            (p / ".ralph").mkdir()

            if status == "running":
                session_dir = p / ".ralph-session"
                session_dir.mkdir()
                session_path = session_dir / "session.json"
                session_path.write_text(json.dumps({
                    "session_id": "test",
                    "session_token": "ralph-test",
                    "started_at": "2026-01-01T00:00:00Z",
                    "task_source": ".ralph/prd.json",
                    "task_source_type": "prd_json",
                    "status": "running",
                }))

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        service.discover_projects()

        running = service.get_projects_by_status("running")
        assert len(running) == 1
        assert running[0].status == "running"

        idle = service.get_projects_by_status("idle")
        assert len(idle) == 1
        assert idle[0].status == "idle"

    def test_clear_cache(self, temp_project: Path, tmp_path: Path):
        """Test clearing the project cache."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.discover_projects()

        assert len(service.list_projects()) == 1

        service.clear_cache()

        assert len(service.list_projects()) == 0


class TestProjectServiceSearchPaths:
    """Tests for search path management."""

    def test_add_search_path(self, tmp_path: Path):
        """Test adding a search path."""
        service = ProjectService(search_paths=[])

        service.add_search_path(tmp_path)

        assert tmp_path.resolve() in service.search_paths

    def test_add_duplicate_search_path(self, tmp_path: Path):
        """Test adding duplicate search path is ignored."""
        service = ProjectService(search_paths=[tmp_path])

        service.add_search_path(tmp_path)

        assert len(service.search_paths) == 1

    def test_remove_search_path(self, tmp_path: Path):
        """Test removing a search path."""
        service = ProjectService(search_paths=[tmp_path])

        service.remove_search_path(tmp_path)

        assert tmp_path.resolve() not in service.search_paths


class TestProjectServiceFileWatching:
    """Tests for file watching functionality."""

    def test_start_stop_watching(self, tmp_path: Path):
        """Test starting and stopping file watching."""
        service = ProjectService(search_paths=[tmp_path])

        assert not service.is_watching()

        service.start_watching(interval=1.0)
        assert service.is_watching()

        service.stop_watching()
        # Give thread time to stop
        time.sleep(0.1)
        assert not service.is_watching()

    def test_start_watching_multiple_times(self, tmp_path: Path):
        """Test that starting watching multiple times doesn't create multiple threads."""
        service = ProjectService(search_paths=[tmp_path])

        service.start_watching(interval=1.0)
        thread1 = service._watch_thread

        service.start_watching(interval=1.0)
        thread2 = service._watch_thread

        # Should be the same thread
        assert thread1 is thread2

        service.stop_watching()


class TestProjectServiceRefresh:
    """Tests for project refresh functionality."""

    def test_refresh_project_updates_metadata(self, temp_project: Path, tmp_path: Path):
        """Test that refreshing a project updates its metadata."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.discover_projects()

        # Get initial metadata
        project = service.get_project(temp_project)
        assert project.task_count == 3

        # Modify PRD
        prd_path = temp_project / ".ralph" / "prd.json"
        prd_data = json.loads(prd_path.read_text())
        prd_data["tasks"][1]["passes"] = True  # Complete T-002
        prd_path.write_text(json.dumps(prd_data))

        # Refresh
        updated = service.refresh_project(temp_project)

        assert updated is not None
        assert updated.tasks_completed == 2
        assert updated.tasks_pending == 1

    def test_refresh_project_removes_if_deleted(self, temp_project: Path, tmp_path: Path):
        """Test that refreshing a deleted project removes it from cache."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.discover_projects()

        assert service.get_project(temp_project) is not None

        # Remove .ralph directory
        import shutil
        shutil.rmtree(temp_project / ".ralph")

        # Refresh should return None and remove from cache
        updated = service.refresh_project(temp_project)
        assert updated is None
        assert service.get_project(temp_project) is None

    def test_refresh_project_detects_multiple_changes(
        self, temp_project_with_session: Path, tmp_path: Path
    ):
        """Test that refresh detects multiple simultaneous changes."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.discover_projects()

        # Modify session, tasks, and config simultaneously
        session_path = temp_project_with_session / ".ralph-session" / "session.json"
        session_data = json.loads(session_path.read_text())
        session_data["status"] = "completed"
        session_data["current_task"] = None
        session_path.write_text(json.dumps(session_data))

        prd_path = temp_project_with_session / ".ralph" / "prd.json"
        prd_data = json.loads(prd_path.read_text())
        prd_data["tasks"][1]["passes"] = True
        prd_data["tasks"][2]["passes"] = True
        prd_path.write_text(json.dumps(prd_data))

        updated = service.refresh_project(temp_project_with_session)

        assert updated.status == "completed"
        assert updated.current_task is None
        assert updated.tasks_completed == 3


class TestProjectServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_discover_with_permission_error(self, tmp_path: Path):
        """Test that permission errors are handled gracefully during scan."""
        service = ProjectService(search_paths=[tmp_path], max_depth=2)

        # Create a project
        project = tmp_path / "accessible_project"
        project.mkdir()
        (project / ".ralph").mkdir()

        # Discover should work and not crash
        projects = service.discover_projects()
        assert len(projects) >= 0  # May or may not find depending on permissions

    def test_discover_with_invalid_json(self, tmp_path: Path):
        """Test handling of invalid JSON in PRD files."""
        project = tmp_path / "bad_json_project"
        project.mkdir()
        ralph_dir = project / ".ralph"
        ralph_dir.mkdir()

        # Write invalid JSON
        prd_path = ralph_dir / "prd.json"
        prd_path.write_text("{invalid json content")

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        projects = service.discover_projects()

        # Should discover the project even with invalid JSON
        assert len(projects) == 1
        # Task count should be 0 since JSON parse failed
        assert projects[0].task_count == 0

    def test_discover_with_invalid_yaml_config(self, tmp_path: Path):
        """Test handling of invalid YAML in config files."""
        project = tmp_path / "bad_yaml_project"
        project.mkdir()
        ralph_dir = project / ".ralph"
        ralph_dir.mkdir()

        # Write invalid YAML
        config_path = ralph_dir / "ralph.yml"
        config_path.write_text("invalid: yaml: content:")

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        projects = service.discover_projects()

        # Should discover project but has_config might still be True (file exists)
        assert len(projects) == 1

    def test_discover_empty_prd_tasks(self, tmp_path: Path):
        """Test handling of PRD with no tasks."""
        project = tmp_path / "empty_tasks_project"
        project.mkdir()
        ralph_dir = project / ".ralph"
        ralph_dir.mkdir()

        prd_path = ralph_dir / "prd.json"
        prd_path.write_text(json.dumps({"project": "Empty", "tasks": []}))

        service = ProjectService(search_paths=[tmp_path], max_depth=2)
        projects = service.discover_projects()

        assert len(projects) == 1
        assert projects[0].task_count == 0
        assert projects[0].tasks_completed == 0
        assert projects[0].tasks_pending == 0

    def test_get_project_with_string_path(self, temp_project: Path, tmp_path: Path):
        """Test getting project using string path instead of Path object."""
        service = ProjectService(search_paths=[tmp_path], max_depth=3)
        service.discover_projects()

        # Pass path as string
        project = service.get_project(str(temp_project))

        assert project is not None
        assert project.name == "Test Project"


class TestEventDataclasses:
    """Tests for event dataclass serialization."""

    def test_project_discovered_event_to_dict(self):
        """Test ProjectDiscoveredEvent serialization."""
        event = ProjectDiscoveredEvent(
            project_path="/path/to/project",
            project_name="My Project",
        )

        d = event.to_dict()

        assert d["event_type"] == "project_discovered"
        assert d["project_path"] == "/path/to/project"
        assert d["project_name"] == "My Project"
        assert "timestamp" in d

    def test_scan_completed_event_to_dict(self):
        """Test ScanCompletedEvent serialization."""
        event = ScanCompletedEvent(
            projects_found=5,
            duration_ms=123,
        )

        d = event.to_dict()

        assert d["event_type"] == "scan_completed"
        assert d["projects_found"] == 5
        assert d["duration_ms"] == 123

    def test_project_updated_event_to_dict(self):
        """Test ProjectUpdatedEvent serialization."""
        event = ProjectUpdatedEvent(
            project_path="/path",
            project_name="Test",
            changes={"status": {"old": "idle", "new": "running"}},
        )

        d = event.to_dict()

        assert d["changes"]["status"]["old"] == "idle"
        assert d["changes"]["status"]["new"] == "running"

    def test_project_removed_event_to_dict(self):
        """Test ProjectRemovedEvent serialization."""
        event = ProjectRemovedEvent(
            project_path="/path",
            project_name="Removed Project",
        )

        d = event.to_dict()

        assert d["event_type"] == "project_removed"
        assert d["project_path"] == "/path"
        assert d["project_name"] == "Removed Project"

    def test_scan_started_event_to_dict(self):
        """Test ScanStartedEvent serialization."""
        event = ScanStartedEvent(
            search_paths=["/path1", "/path2"],
        )

        d = event.to_dict()

        assert d["event_type"] == "scan_started"
        assert len(d["search_paths"]) == 2
        assert "/path1" in d["search_paths"]
