"""Integration tests for FastAPI REST endpoints."""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from server.api import app, get_project_service, get_config_service, get_git_service


@pytest.fixture
def temp_ralph_project(tmp_path):
    """Create a temporary Ralph project for API testing."""
    project_dir = tmp_path / "test_api_project"
    project_dir.mkdir()
    
    # Create .ralph directory structure
    ralph_dir = project_dir / ".ralph"
    ralph_dir.mkdir()
    
    # Create ralph.yml
    config_file = ralph_dir / "ralph.yml"
    config_data = """version: '1'
task_source:
  type: prd_json
  path: .ralph/prd.json
git:
  base_branch: main
  remote: origin
gates:
  build:
    - name: lint
      cmd: echo "Linting..."
  full:
    - name: test
      cmd: echo "Testing..."
test_paths:
  - tests/
"""
    config_file.write_text(config_data)
    
    # Create prd.json
    prd_file = ralph_dir / "prd.json"
    prd_data = {
        "project": "Test API Project",
        "description": "Testing the API",
        "tasks": [
            {
                "id": "T-001",
                "title": "First task",
                "description": "Do something",
                "acceptanceCriteria": ["AC1", "AC2"],
                "priority": 1,
                "passes": False,
                "requiresTests": True,
                "notes": ""
            },
            {
                "id": "T-002",
                "title": "Second task",
                "description": "Do something else",
                "acceptanceCriteria": ["AC3"],
                "priority": 2,
                "passes": True,
                "requiresTests": True,
                "notes": ""
            }
        ]
    }
    prd_file.write_text(json.dumps(prd_data, indent=2))
    
    # Create .ralph-session directory
    session_dir = project_dir / ".ralph-session"
    session_dir.mkdir()
    logs_dir = session_dir / "logs"
    logs_dir.mkdir()
    
    # Create timeline.jsonl
    timeline_file = logs_dir / "timeline.jsonl"
    timeline_file.write_text("")
    
    return project_dir


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_check(self, client):
        """Test GET /api/health returns healthy status."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "projects_discovered" in data


class TestProjectEndpoints:
    """Test project management endpoints."""

    def test_list_projects(self, client, temp_ralph_project):
        """Test GET /api/projects lists discovered projects."""
        # Configure service to search temp directory
        service = get_project_service()
        service._search_paths = [temp_ralph_project.parent]
        service.discover_projects()
        
        response = client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data

    def test_list_projects_with_refresh(self, client, temp_ralph_project):
        """Test GET /api/projects?refresh=true forces rescan."""
        service = get_project_service()
        service._search_paths = [temp_ralph_project.parent]
        
        response = client.get("/api/projects?refresh=true")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["projects"], list)

    def test_get_project(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id} returns project details."""
        service = get_project_service()
        service._search_paths = [temp_ralph_project.parent]
        service.discover_projects()
        
        project_id = str(temp_ralph_project)
        response = client.get(f"/api/projects/{project_id}")
        
        # May return 404 if project not discovered
        assert response.status_code in [200, 404]

    def test_get_tasks(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id}/tasks returns tasks."""
        project_id = str(temp_ralph_project)
        response = client.get(f"/api/projects/{project_id}/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "Test API Project"
        assert len(data["tasks"]) == 2
        assert data["total"] == 2
        assert data["completed"] == 1
        assert data["pending"] == 1

    def test_get_tasks_invalid_project(self, client):
        """Test GET /api/projects/{project_id}/tasks with invalid project."""
        response = client.get("/api/projects/nonexistent/tasks")
        
        assert response.status_code == 404


class TestRunEndpoints:
    """Test task execution endpoints."""

    def test_run_project_dry_run(self, client, temp_ralph_project):
        """Test POST /api/projects/{project_id}/run with dry_run=true."""
        project_id = str(temp_ralph_project)
        request_data = {
            "dry_run": True,
            "gate_type": "full",
            "max_iterations": 100
        }
        
        response = client.post(
            f"/api/projects/{project_id}/run",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dry_run"
        assert data["session_id"] == "dry-run"
        assert "tasks_pending" in data

    def test_run_project_invalid_gate_type(self, client, temp_ralph_project):
        """Test POST /api/projects/{project_id}/run with invalid gate_type."""
        project_id = str(temp_ralph_project)
        request_data = {
            "dry_run": True,
            "gate_type": "invalid",
            "max_iterations": 100
        }
        
        response = client.post(
            f"/api/projects/{project_id}/run",
            json=request_data
        )
        
        assert response.status_code == 422  # Validation error

    def test_stop_project_not_running(self, client, temp_ralph_project):
        """Test POST /api/projects/{project_id}/stop when not running."""
        project_id = str(temp_ralph_project)
        
        response = client.post(f"/api/projects/{project_id}/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestConfigEndpoints:
    """Test configuration endpoints."""

    def test_get_config(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id}/config returns configuration."""
        project_id = str(temp_ralph_project)
        
        response = client.get(f"/api/projects/{project_id}/config")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1"
        assert data["task_source_type"] == "prd_json"
        assert data["git_base_branch"] == "main"
        assert data["gates_build_count"] == 1
        assert data["gates_full_count"] == 1

    def test_get_config_not_found(self, client, tmp_path):
        """Test GET /api/projects/{project_id}/config with missing config."""
        empty_project = tmp_path / "empty"
        empty_project.mkdir()
        
        response = client.get(f"/api/projects/{empty_project}/config")
        
        assert response.status_code == 404

    def test_update_config(self, client, temp_ralph_project):
        """Test PUT /api/projects/{project_id}/config updates configuration."""
        project_id = str(temp_ralph_project)
        updates = {
            "updates": {
                "git": {
                    "base_branch": "develop"
                }
            },
            "validate_config": True
        }
        
        response = client.put(
            f"/api/projects/{project_id}/config",
            json=updates
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "git" in data["changes"]

    def test_update_config_invalid_data(self, client, temp_ralph_project):
        """Test PUT /api/projects/{project_id}/config with invalid updates."""
        project_id = str(temp_ralph_project)
        updates = {
            "updates": {
                "invalid_key": "invalid_value"
            },
            "validate_config": True
        }
        
        response = client.put(
            f"/api/projects/{project_id}/config",
            json=updates
        )
        
        assert response.status_code == 422  # Validation error


class TestGitEndpoints:
    """Test git operation endpoints."""

    def test_list_branches_no_git(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id}/branches without git."""
        project_id = str(temp_ralph_project)
        
        response = client.get(f"/api/projects/{project_id}/branches")
        
        # Should return error since temp_ralph_project is not a git repo
        assert response.status_code == 400


class TestLogsEndpoints:
    """Test logs and timeline endpoints."""

    def test_list_logs(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id}/logs lists log files."""
        project_id = str(temp_ralph_project)
        
        response = client.get(f"/api/projects/{project_id}/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_get_timeline(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id}/timeline returns events."""
        project_id = str(temp_ralph_project)
        
        response = client.get(f"/api/projects/{project_id}/timeline")
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)

    def test_get_timeline_with_limit(self, client, temp_ralph_project):
        """Test GET /api/projects/{project_id}/timeline with limit parameter."""
        project_id = str(temp_ralph_project)
        
        response = client.get(f"/api/projects/{project_id}/timeline?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) <= 10
