"""Unit tests for ProjectService."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from ralph_orchestrator.services.project_service import (
    ProjectService,
    ProjectMetadata,
    ProjectEventType,
    ProjectDiscoveredEvent,
    ProjectRemovedEvent,
)


@pytest.fixture
def temp_ralph_project(tmp_path):
    """Create a temporary Ralph project for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create .ralph directory
    ralph_dir = project_dir / ".ralph"
    ralph_dir.mkdir()
    
    # Create minimal ralph.yml (version must be "1" not "1.0")
    config_file = ralph_dir / "ralph.yml"
    config_file.write_text("""version: '1'
git:
  base_branch: main
task_source:
  type: prd_json
  path: .ralph/prd.json
gates:
  full:
    - name: test
      cmd: echo ok
""")

    # Create minimal prd.json with camelCase fields matching schema
    prd_file = ralph_dir / "prd.json"
    prd_data = {
        "project": "Test Project",
        "description": "A test project",
        "tasks": [
            {
                "id": "T-001",
                "title": "Task 1",
                "description": "First task",
                "acceptanceCriteria": ["AC1"],
                "priority": 1,
                "passes": False
            },
            {
                "id": "T-002",
                "title": "Task 2",
                "description": "Second task",
                "acceptanceCriteria": ["AC2"],
                "priority": 2,
                "passes": True
            }
        ]
    }
    prd_file.write_text(json.dumps(prd_data, indent=2))
    
    return project_dir


@pytest.fixture
def project_service(tmp_path):
    """Create a ProjectService instance."""
    return ProjectService(search_paths=[tmp_path])


class TestProjectMetadata:
    """Test ProjectMetadata dataclass."""

    def test_project_metadata_creation(self):
        """Test creating ProjectMetadata."""
        metadata = ProjectMetadata(
            path=Path("/test/project"),
            name="test_project",
            git_branch="main",
            task_count=5,
            tasks_completed=2
        )
        
        assert metadata.path == Path("/test/project")
        assert metadata.name == "test_project"
        assert metadata.git_branch == "main"
        assert metadata.task_count == 5
        assert metadata.tasks_completed == 2
        assert metadata.tasks_pending == 0  # default value


class TestProjectService:
    """Test ProjectService class."""

    def test_discover_projects(self, project_service, temp_ralph_project):
        """Test discovering Ralph projects."""
        projects = project_service.discover_projects()

        assert len(projects) == 1
        # Project name comes from prd.json "project" field, not directory name
        assert projects[0].name == "Test Project"
        assert projects[0].task_count == 2
        assert projects[0].tasks_completed == 1
        assert projects[0].tasks_pending == 1

    def test_list_projects(self, project_service, temp_ralph_project):
        """Test listing projects after discovery."""
        # Discover first
        project_service.discover_projects()

        # Then list
        projects = project_service.list_projects()

        assert len(projects) == 1
        assert projects[0].name == "Test Project"

    def test_get_project(self, project_service, temp_ralph_project):
        """Test getting a specific project by path."""
        project_service.discover_projects()

        metadata = project_service.get_project(temp_ralph_project)

        assert metadata is not None
        assert metadata.name == "Test Project"
        assert metadata.path == temp_ralph_project

    def test_get_project_not_found(self, project_service):
        """Test getting a non-existent project."""
        metadata = project_service.get_project(Path("/nonexistent"))
        
        assert metadata is None

    def test_refresh_project(self, project_service, temp_ralph_project):
        """Test refreshing project metadata."""
        project_service.discover_projects()

        # Refresh the project
        metadata = project_service.refresh_project(temp_ralph_project)

        assert metadata is not None
        assert metadata.name == "Test Project"

    def test_empty_search_path(self, tmp_path):
        """Test service with empty search path."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        service = ProjectService(search_paths=[empty_dir])
        projects = service.discover_projects()
        
        assert len(projects) == 0


class TestProjectEvents:
    """Test project event classes."""

    def test_project_discovered_event(self):
        """Test ProjectDiscoveredEvent."""
        event = ProjectDiscoveredEvent(
            project_path="/test/project",
            project_name="test"
        )
        data = event.to_dict()
        
        assert data["event_type"] == "project_discovered"
        assert data["project_path"] == "/test/project"
        assert data["project_name"] == "test"
        assert "timestamp" in data

    def test_project_removed_event(self):
        """Test ProjectRemovedEvent."""
        event = ProjectRemovedEvent(
            project_path="/test/project",
            project_name="test"
        )
        data = event.to_dict()
        
        assert data["event_type"] == "project_removed"
        assert data["project_path"] == "/test/project"
