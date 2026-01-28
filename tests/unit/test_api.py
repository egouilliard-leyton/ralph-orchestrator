"""Unit tests for FastAPI REST API.

Tests the REST API endpoints including:
- Project management endpoints
- Task operations
- Configuration management
- Git operations
- Logs and timeline access
- CORS configuration
- Error handling and validation
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock

import yaml
from fastapi.testclient import TestClient

# Import the FastAPI app and models
from server.api import (
    app,
    get_project_service,
    get_config_service,
    get_git_service,
    get_session_service,
    _active_runs,
    ProjectResponse,
    TaskResponse,
    ConfigResponse,
    BranchResponse,
)

# Import service classes for mocking
from ralph_orchestrator.services.project_service import ProjectService, ProjectMetadata
from ralph_orchestrator.services.config_service import (
    ConfigService,
    ConfigSummary,
    ConfigValidationError,
)
from ralph_orchestrator.services.git_service import GitService, GitError, BranchInfo, PRInfo
from ralph_orchestrator.services.session_service import SessionService
from ralph_orchestrator.tasks.prd import PRDData, Task


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a minimal Ralph project with prd.json and ralph.yml."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    # Create .ralph directory
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir()

    # Create prd.json (using camelCase per schema)
    prd_data = {
        "project": "Test Project",
        "description": "A test project",
        "tasks": [
            {
                "id": "T-001",
                "title": "Task 1",
                "description": "First task",
                "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
                "priority": 1,
                "passes": False,
                "notes": "",
                "requiresTests": True,
            },
            {
                "id": "T-002",
                "title": "Task 2",
                "description": "Second task",
                "acceptanceCriteria": ["Criterion A"],
                "priority": 2,
                "passes": True,
                "notes": "Completed",
                "requiresTests": True,
            },
        ],
    }
    (ralph_dir / "prd.json").write_text(json.dumps(prd_data, indent=2))

    # Create ralph.yml
    config_data = {
        "version": "1",
        "task_source": {
            "type": "prd_json",
            "path": ".ralph/prd.json",
        },
        "git": {
            "base_branch": "main",
            "remote": "origin",
        },
        "gates": {
            "build": [{"name": "lint", "cmd": "ruff check ."}],
            "full": [{"name": "test", "cmd": "pytest"}],
        },
        "test_paths": ["tests/**"],
    }
    (ralph_dir / "ralph.yml").write_text(yaml.dump(config_data))

    # Create session directory structure
    session_dir = project_path / ".ralph-session"
    session_dir.mkdir()
    logs_dir = session_dir / "logs"
    logs_dir.mkdir()

    # Create session.json
    session_data = {"session_id": "ralph-20260127-test", "created_at": 1706372400.0}
    (session_dir / "session.json").write_text(json.dumps(session_data, indent=2))

    # Create a sample log file
    (logs_dir / "task-T-001.log").write_text("Task execution log\nLine 2\n")

    # Create timeline.jsonl
    timeline_events = [
        {"timestamp": "2026-01-27T10:00:00", "event_type": "task_started", "task_id": "T-001"},
        {"timestamp": "2026-01-27T10:05:00", "event_type": "gate_passed", "gate_name": "lint"},
    ]
    timeline_content = "\n".join(json.dumps(e) for e in timeline_events)
    (logs_dir / "timeline.jsonl").write_text(timeline_content)

    return project_path


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_project_service():
    """Mock ProjectService for testing."""
    with patch("server.api._project_service") as mock:
        service = MagicMock(spec=ProjectService)
        mock.return_value = service
        yield service


@pytest.fixture
def mock_config_service():
    """Mock ConfigService for testing."""
    with patch("server.api._config_service") as mock:
        service = MagicMock(spec=ConfigService)
        mock.return_value = service
        yield service


@pytest.fixture
def mock_git_service():
    """Mock GitService for testing."""
    with patch("server.api._git_service") as mock:
        service = MagicMock(spec=GitService)
        mock.return_value = service
        yield service


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_status(self, client, mock_project_service):
        """Health check returns service status."""
        mock_project_service.list_projects.return_value = []

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "projects_discovered" in data
        assert "active_runs" in data


# =============================================================================
# Project Endpoints Tests
# =============================================================================


class TestProjectEndpoints:
    """Tests for project management endpoints."""

    def test_list_projects_empty(self, client):
        """GET /api/projects returns empty list when no projects."""
        with patch("server.api.get_project_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_projects.return_value = []
            mock_service.discover_projects.return_value = []
            mock_get.return_value = mock_service

            response = client.get("/api/projects")

            assert response.status_code == 200
            data = response.json()
            assert data["projects"] == []
            assert data["total"] == 0

    def test_list_projects_with_data(self, client):
        """GET /api/projects returns project list."""
        with patch("server.api.get_project_service") as mock_get:
            mock_service = MagicMock()
            metadata = ProjectMetadata(
                path=Path("/test/project"),
                name="test-project",
                git_branch="main",
                git_commit="abc123",
                task_count=5,
                tasks_completed=2,
                tasks_pending=3,
                status="idle",
                has_config=True,
            )
            mock_service.list_projects.return_value = [metadata]
            mock_get.return_value = mock_service

            response = client.get("/api/projects")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["projects"]) == 1
            assert data["projects"][0]["name"] == "test-project"
            assert data["projects"][0]["task_count"] == 5

    def test_list_projects_with_refresh(self, client):
        """GET /api/projects with refresh=true forces rescan."""
        with patch("server.api.get_project_service") as mock_get:
            mock_service = MagicMock()
            mock_service.discover_projects.return_value = []
            mock_get.return_value = mock_service

            response = client.get("/api/projects?refresh=true")

            assert response.status_code == 200
            mock_service.discover_projects.assert_called_once_with(refresh=True)

    def test_get_project_found(self, client):
        """GET /api/projects/{id} returns project details."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_project_service") as mock_get:

            mock_path.return_value = Path("/test/project")
            mock_service = MagicMock()
            metadata = ProjectMetadata(
                path=Path("/test/project"),
                name="test-project",
                git_branch="main",
                status="idle",
            )
            mock_service.get_project.return_value = metadata
            mock_get.return_value = mock_service

            response = client.get("/api/projects/test-project")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-project"
            assert data["git_branch"] == "main"

    def test_get_project_not_found(self, client):
        """GET /api/projects/{id} returns 404 when project not found."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_project_service") as mock_get:

            mock_path.return_value = Path("/test/nonexistent")
            mock_service = MagicMock()
            mock_service.get_project.return_value = None
            mock_service.refresh_project.return_value = None
            mock_get.return_value = mock_service

            response = client.get("/api/projects/nonexistent")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Task Endpoints Tests
# =============================================================================


class TestTaskEndpoints:
    """Tests for task management endpoints."""

    def test_get_tasks_success(self, client, temp_project):
        """GET /api/projects/{id}/tasks returns task list."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/tasks")

            assert response.status_code == 200
            data = response.json()
            assert data["project"] == "Test Project"
            assert data["total"] == 2
            assert data["completed"] == 1  # T-002 passes
            assert data["pending"] == 1   # T-001 pending
            assert len(data["tasks"]) == 2
            assert data["tasks"][0]["id"] == "T-001"
            assert data["tasks"][1]["id"] == "T-002"

    def test_get_tasks_prd_not_found(self, client, tmp_path):
        """GET /api/projects/{id}/tasks returns 404 when prd.json missing."""
        project_path = tmp_path / "no_prd"
        project_path.mkdir()
        ralph_dir = project_path / ".ralph"
        ralph_dir.mkdir()
        # No prd.json file created

        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = project_path

            response = client.get("/api/projects/no-prd/tasks")

            assert response.status_code == 404
            assert "prd" in response.json()["detail"].lower()

    def test_get_tasks_invalid_prd(self, client, tmp_path):
        """GET /api/projects/{id}/tasks returns 400 when prd.json invalid."""
        project_path = tmp_path / "invalid_prd"
        project_path.mkdir()
        ralph_dir = project_path / ".ralph"
        ralph_dir.mkdir()
        # Create invalid prd.json
        (ralph_dir / "prd.json").write_text("invalid json {{{")

        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = project_path

            response = client.get("/api/projects/invalid-prd/tasks")

            assert response.status_code == 400
            assert "failed" in response.json()["detail"].lower()


# =============================================================================
# Run/Stop Endpoints Tests
# =============================================================================


class TestRunStopEndpoints:
    """Tests for task execution endpoints."""

    def test_run_project_dry_run(self, client, temp_project):
        """POST /api/projects/{id}/run with dry_run returns preview."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            request_data = {
                "dry_run": True,
                "max_iterations": 200,
                "gate_type": "full",
            }
            response = client.post("/api/projects/test-project/run", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "dry_run"
            assert data["session_id"] == "dry-run"
            assert data["tasks_pending"] == 1  # Only T-001 is pending

    def test_run_project_invalid_gate_type(self, client, temp_project):
        """POST /api/projects/{id}/run with invalid gate_type returns 422."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            request_data = {
                "gate_type": "invalid",
                "dry_run": True,
            }
            response = client.post("/api/projects/test-project/run", json=request_data)

            assert response.status_code == 422  # Validation error

    def test_run_project_not_found(self, client, tmp_path):
        """POST /api/projects/{id}/run returns 404 when project not found."""
        nonexistent = tmp_path / "nonexistent"

        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = nonexistent

            request_data = {"dry_run": True}
            response = client.post("/api/projects/nonexistent/run", json=request_data)

            assert response.status_code == 404

    def test_run_project_no_pending_tasks(self, client, tmp_path):
        """POST /api/projects/{id}/run returns completed when no pending tasks."""
        project_path = tmp_path / "all_done"
        project_path.mkdir()
        ralph_dir = project_path / ".ralph"
        ralph_dir.mkdir()

        # All tasks completed (using camelCase per schema)
        prd_data = {
            "project": "All Done",
            "description": "Test",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task 1",
                    "description": "Done",
                    "acceptanceCriteria": ["A"],
                    "priority": 1,
                    "passes": True,
                    "notes": "",
                    "requiresTests": True,
                }
            ],
        }
        (ralph_dir / "prd.json").write_text(json.dumps(prd_data))

        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = project_path

            request_data = {"dry_run": False}
            response = client.post("/api/projects/all-done/run", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["tasks_pending"] == 0

    def test_stop_project_not_running(self, client, temp_project):
        """POST /api/projects/{id}/stop returns failure when not running."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.post("/api/projects/test-project/stop")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "no active execution" in data["message"].lower()


# =============================================================================
# Config Endpoints Tests
# =============================================================================


class TestConfigEndpoints:
    """Tests for configuration management endpoints."""

    def test_get_config_success(self, client, temp_project):
        """GET /api/projects/{id}/config returns configuration."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_config_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()

            summary = ConfigSummary(
                config_path=temp_project / ".ralph" / "ralph.yml",
                project_path=temp_project,
                version="1",
                task_source_type="prd_json",
                task_source_path=".ralph/prd.json",
                git_base_branch="main",
                git_remote="origin",
                gates_build_count=1,
                gates_full_count=1,
                test_paths=["tests/**"],
                has_backend=False,
                has_frontend=False,
                autopilot_enabled=False,
            )
            mock_service.get_config_summary.return_value = summary
            mock_service.get_raw_config.return_value = {"version": "1"}
            mock_get.return_value = mock_service

            response = client.get("/api/projects/test-project/config")

            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "1"
            assert data["task_source_type"] == "prd_json"
            assert data["git_base_branch"] == "main"
            assert "raw_config" in data

    def test_get_config_not_found(self, client, tmp_path):
        """GET /api/projects/{id}/config returns 404 when config missing."""
        project_path = tmp_path / "no_config"
        project_path.mkdir()

        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_config_service") as mock_get:

            mock_path.return_value = project_path
            mock_service = MagicMock()
            mock_service.get_config_summary.return_value = None
            mock_get.return_value = mock_service

            response = client.get("/api/projects/no-config/config")

            assert response.status_code == 404

    def test_update_config_success(self, client, temp_project):
        """PUT /api/projects/{id}/config updates configuration."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_config_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()

            # Mock current config
            mock_service.get_raw_config.return_value = {"version": "1"}
            mock_service.validate_config_data.return_value = (True, [])

            # Mock updated config
            updated_config = MagicMock()
            updated_config.version = "1"
            mock_service.update_config.return_value = updated_config
            mock_get.return_value = mock_service

            updates = {"git": {"base_branch": "develop"}}
            response = client.put(
                "/api/projects/test-project/config",
                json={"updates": updates, "validate_config": True}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["version"] == "1"

    def test_update_config_validation_error(self, client, temp_project):
        """PUT /api/projects/{id}/config returns 400 on validation failure from schema."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_config_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()
            mock_service.get_raw_config.return_value = {"version": "1"}
            mock_service.validate_config_data.return_value = (False, ["Invalid field"])
            mock_get.return_value = mock_service

            # Use valid structure for ConfigUpdateRequest, but let schema validation fail
            updates = {"git": {"base_branch": "invalid-chars-???"}}
            response = client.put(
                "/api/projects/test-project/config",
                json={"updates": updates, "validate_config": True}
            )

            assert response.status_code == 400
            assert "validation failed" in response.json()["detail"].lower()

    def test_update_config_invalid_structure_returns_422(self, client, temp_project):
        """PUT /api/projects/{id}/config returns 422 on structurally invalid updates."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            # Unknown top-level key should be rejected by ConfigUpdateRequest validation
            updates = {"unknown_key": "data"}
            response = client.put(
                "/api/projects/test-project/config",
                json={"updates": updates, "validate_config": True}
            )

            assert response.status_code == 422  # Pydantic validation error


# =============================================================================
# Git Endpoints Tests
# =============================================================================


class TestGitEndpoints:
    """Tests for git operations endpoints."""

    def test_list_branches_success(self, client, temp_project):
        """GET /api/projects/{id}/branches returns branch list."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()

            branches = [
                BranchInfo(
                    name="main",
                    is_current=True,
                    commit_hash="abc123",
                    commit_message="Latest commit",
                ),
                BranchInfo(
                    name="feature-branch",
                    is_current=False,
                    commit_hash="def456",
                ),
            ]
            mock_service.list_branches.return_value = branches
            mock_service.get_current_branch.return_value = "main"
            mock_get.return_value = mock_service

            response = client.get("/api/projects/test-project/branches")

            assert response.status_code == 200
            data = response.json()
            assert data["current_branch"] == "main"
            assert data["total"] == 2
            assert len(data["branches"]) == 2
            assert data["branches"][0]["name"] == "main"
            assert data["branches"][0]["is_current"] is True

    def test_list_branches_with_remote(self, client, temp_project):
        """GET /api/projects/{id}/branches with include_remote parameter."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()
            mock_service.list_branches.return_value = []
            mock_service.get_current_branch.return_value = "main"
            mock_get.return_value = mock_service

            response = client.get("/api/projects/test-project/branches?include_remote=true")

            assert response.status_code == 200
            mock_service.list_branches.assert_called_once_with(
                temp_project, include_remote=True
            )

    def test_list_branches_git_error(self, client, temp_project):
        """GET /api/projects/{id}/branches returns 400 on git error."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()
            mock_service.list_branches.side_effect = GitError("Not a git repo")
            mock_get.return_value = mock_service

            response = client.get("/api/projects/test-project/branches")

            assert response.status_code == 400
            assert "git error" in response.json()["detail"].lower()

    def test_create_branch_success(self, client, temp_project):
        """POST /api/projects/{id}/branches creates new branch."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()
            mock_service.get_current_branch.return_value = "main"

            branch_info = BranchInfo(
                name="new-feature",
                is_current=True,
                commit_hash="abc123",
            )
            mock_service.create_branch.return_value = branch_info
            mock_get.return_value = mock_service

            request_data = {
                "branch_name": "new-feature",
                "switch": True,
            }
            response = client.post(
                "/api/projects/test-project/branches",
                json=request_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["branch_name"] == "new-feature"
            assert data["commit_hash"] == "abc123"

    def test_create_branch_git_error(self, client, temp_project):
        """POST /api/projects/{id}/branches returns 400 on git error."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()
            mock_service.get_current_branch.return_value = "main"
            mock_service.create_branch.side_effect = GitError("Branch exists")
            mock_get.return_value = mock_service

            request_data = {"branch_name": "existing"}
            response = client.post(
                "/api/projects/test-project/branches",
                json=request_data
            )

            assert response.status_code == 400

    def test_create_pr_success(self, client, temp_project):
        """POST /api/projects/{id}/pr creates pull request."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()

            pr_info = PRInfo(
                number=42,
                url="https://github.com/test/repo/pull/42",
                title="Test PR",
                body="PR description",
                state="open",
                base_branch="main",
                head_branch="feature",
                author="test-user",
                created_at="2026-01-27T10:00:00Z",
                updated_at="2026-01-27T10:00:00Z",
            )
            mock_service.create_pr.return_value = pr_info
            mock_get.return_value = mock_service

            request_data = {
                "title": "Test PR",
                "body": "PR description",
                "draft": False,
            }
            response = client.post(
                "/api/projects/test-project/pr",
                json=request_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["pr_number"] == 42
            assert data["pr_url"] == "https://github.com/test/repo/pull/42"
            assert data["title"] == "Test PR"

    def test_create_pr_git_error(self, client, temp_project):
        """POST /api/projects/{id}/pr returns 400 on git error."""
        with patch("server.api.get_project_path") as mock_path, \
             patch("server.api.get_git_service") as mock_get:

            mock_path.return_value = temp_project
            mock_service = MagicMock()
            mock_service.create_pr.side_effect = GitError("No remote")
            mock_get.return_value = mock_service

            request_data = {"title": "Test PR"}
            response = client.post(
                "/api/projects/test-project/pr",
                json=request_data
            )

            assert response.status_code == 400


# =============================================================================
# Logs Endpoints Tests
# =============================================================================


class TestLogsEndpoints:
    """Tests for log file access endpoints."""

    def test_list_logs_success(self, client, temp_project):
        """GET /api/projects/{id}/logs returns log file list."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/logs")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 1
            assert len(data["logs"]) >= 1
            # Find the task log
            task_log = next((log for log in data["logs"] if "task" in log["name"]), None)
            assert task_log is not None
            assert task_log["content"] is None  # Not included by default

    def test_list_logs_with_content(self, client, temp_project):
        """GET /api/projects/{id}/logs with include_content returns content."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/logs?include_content=true")

            assert response.status_code == 200
            data = response.json()
            task_log = next((log for log in data["logs"] if "task" in log["name"]), None)
            if task_log:
                assert task_log["content"] is not None
                assert "Task execution log" in task_log["content"]

    def test_list_logs_no_logs_dir(self, client, tmp_path):
        """GET /api/projects/{id}/logs returns empty list when no logs."""
        project_path = tmp_path / "no_logs"
        project_path.mkdir()

        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = project_path

            response = client.get("/api/projects/no-logs/logs")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["logs"] == []

    def test_get_log_success(self, client, temp_project):
        """GET /api/projects/{id}/logs/{name} returns log content."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/logs/task-T-001.log")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "task-T-001.log"
            assert "Task execution log" in data["content"]

    def test_get_log_not_found(self, client, temp_project):
        """GET /api/projects/{id}/logs/{name} returns 404 when log missing."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/logs/nonexistent.log")

            assert response.status_code == 404


# =============================================================================
# Timeline Endpoints Tests
# =============================================================================


class TestTimelineEndpoints:
    """Tests for timeline access endpoints."""

    def test_get_timeline_success(self, client, temp_project):
        """GET /api/projects/{id}/timeline returns timeline events."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/timeline")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["events"]) == 2
            assert data["session_id"] == "ralph-20260127-test"
            assert data["events"][0]["event_type"] == "task_started"
            assert data["events"][1]["event_type"] == "gate_passed"

    def test_get_timeline_with_limit(self, client, temp_project):
        """GET /api/projects/{id}/timeline with limit parameter."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/timeline?limit=1")

            assert response.status_code == 200
            data = response.json()
            assert len(data["events"]) == 1
            assert data["total"] == 2  # Total count still accurate

    def test_get_timeline_with_offset(self, client, temp_project):
        """GET /api/projects/{id}/timeline with offset parameter."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            response = client.get("/api/projects/test-project/timeline?offset=1&limit=10")

            assert response.status_code == 200
            data = response.json()
            assert len(data["events"]) == 1
            assert data["events"][0]["event_type"] == "gate_passed"

    def test_get_timeline_no_file(self, client, tmp_path):
        """GET /api/projects/{id}/timeline returns empty when no timeline."""
        project_path = tmp_path / "no_timeline"
        project_path.mkdir()

        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = project_path

            response = client.get("/api/projects/no-timeline/timeline")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["events"] == []
            assert data["session_id"] is None


# =============================================================================
# CORS Tests
# =============================================================================


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_allows_localhost_origins(self, client):
        """CORS middleware allows configured localhost origins."""
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200
        # TestClient doesn't fully process CORS headers, but endpoint works


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_invalid_json_returns_422(self, client):
        """Invalid JSON in request body returns 422."""
        response = client.post(
            "/api/projects/test/run",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_required_fields_returns_422(self, client, temp_project):
        """Missing required fields in request returns 422."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            # CreateBranchRequest requires branch_name
            response = client.post(
                "/api/projects/test-project/branches",
                json={}
            )

            assert response.status_code == 422

    def test_validation_error_on_field_constraints(self, client, temp_project):
        """Field constraint violations return 422."""
        with patch("server.api.get_project_path") as mock_path:
            mock_path.return_value = temp_project

            # max_iterations must be >= 1
            response = client.post(
                "/api/projects/test-project/run",
                json={"max_iterations": 0, "dry_run": True}
            )

            assert response.status_code == 422


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestConfigUpdateRequestValidation:
    """Tests for ConfigUpdateRequest input validation."""

    def test_valid_updates_accepted(self, client, temp_project):
        """Valid update structures pass validation."""
        from server.api import ConfigUpdateRequest

        valid_updates = {
            "git": {"base_branch": "develop"},
            "test_paths": ["tests/**", "spec/**"],
        }

        request = ConfigUpdateRequest(updates=valid_updates)
        assert request.updates == valid_updates

    def test_unknown_top_level_keys_rejected(self, client, temp_project):
        """Unknown top-level keys are rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "unknown_key": "value",
            "git": {"base_branch": "main"},
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigUpdateRequest(updates=invalid_updates)

        assert "unknown_key" in str(exc_info.value).lower()

    def test_invalid_version_type_rejected(self, client, temp_project):
        """Non-string version is rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {"version": 123}

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_invalid_task_source_type_rejected(self, client, temp_project):
        """Invalid task_source.type value is rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "task_source": {"type": "invalid_type", "path": ".ralph/prd.json"},
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigUpdateRequest(updates=invalid_updates)

        assert "prd_json" in str(exc_info.value) or "cr_markdown" in str(exc_info.value)

    def test_non_dict_task_source_rejected(self, client, temp_project):
        """Non-object task_source is rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {"task_source": "not_an_object"}

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_non_array_gates_rejected(self, client, temp_project):
        """Non-array gates.build/full are rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "gates": {"build": "not_an_array"},
        }

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_invalid_gate_structure_rejected(self, client, temp_project):
        """Gate items that aren't objects are rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "gates": {"build": ["not_an_object"]},
        }

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_invalid_gate_name_type_rejected(self, client, temp_project):
        """Non-string gate name is rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "gates": {"build": [{"name": 123, "cmd": "test"}]},
        }

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_non_array_test_paths_rejected(self, client, temp_project):
        """Non-array test_paths is rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {"test_paths": "not_an_array"}

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_non_string_test_path_rejected(self, client, temp_project):
        """Non-string items in test_paths are rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {"test_paths": ["valid", 123, "also_valid"]}

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_invalid_limits_field_type_rejected(self, client, temp_project):
        """Non-integer limits fields are rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "limits": {"claude_timeout": "not_an_int"},
        }

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_invalid_autopilot_boolean_rejected(self, client, temp_project):
        """Non-boolean autopilot.enabled is rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "autopilot": {"enabled": "yes"},
        }

        with pytest.raises(ValidationError):
            ConfigUpdateRequest(updates=invalid_updates)

    def test_unknown_agent_type_rejected(self, client, temp_project):
        """Unknown agent types in agents config are rejected."""
        from server.api import ConfigUpdateRequest
        from pydantic import ValidationError

        invalid_updates = {
            "agents": {"unknown_agent": {"model": "test"}},
        }

        with pytest.raises(ValidationError) as exc_info:
            ConfigUpdateRequest(updates=invalid_updates)

        assert "unknown_agent" in str(exc_info.value).lower()

    def test_valid_agents_config_accepted(self, client, temp_project):
        """Valid agents configuration passes validation."""
        from server.api import ConfigUpdateRequest

        valid_updates = {
            "agents": {
                "implementation": {"model": "claude-sonnet-4-20250514", "timeout": 1800},
                "test_writing": {"timeout": 900},
                "review": {},
            },
        }

        request = ConfigUpdateRequest(updates=valid_updates)
        assert request.updates == valid_updates

    def test_complex_valid_config_accepted(self, client, temp_project):
        """Complex valid configuration passes validation."""
        from server.api import ConfigUpdateRequest

        valid_updates = {
            "version": "1",
            "task_source": {"type": "prd_json", "path": ".ralph/prd.json"},
            "git": {"base_branch": "develop", "remote": "upstream"},
            "gates": {
                "build": [{"name": "lint", "cmd": "ruff check ."}],
                "full": [{"name": "test", "cmd": "pytest"}],
            },
            "test_paths": ["tests/**", "**/*.spec.*"],
            "limits": {"claude_timeout": 1800, "max_iterations": 30},
            "autopilot": {"enabled": True, "create_pr": True},
        }

        request = ConfigUpdateRequest(updates=valid_updates)
        assert request.updates == valid_updates


class TestPydanticModels:
    """Tests for Pydantic model conversions."""

    def test_project_response_from_metadata(self):
        """ProjectResponse.from_metadata converts correctly."""
        metadata = ProjectMetadata(
            path=Path("/test"),
            name="test",
            git_branch="main",
            task_count=5,
        )

        response = ProjectResponse.from_metadata(metadata)

        assert response.name == "test"
        assert response.path == "/test"
        assert response.git_branch == "main"
        assert response.task_count == 5

    def test_task_response_from_task(self):
        """TaskResponse.from_task converts correctly."""
        task = Task(
            id="T-001",
            title="Test Task",
            description="Description",
            acceptance_criteria=["A", "B"],
            priority=1,
            passes=True,
            notes="Done",
            requires_tests=False,
        )

        response = TaskResponse.from_task(task)

        assert response.id == "T-001"
        assert response.title == "Test Task"
        assert response.passes is True
        assert response.requires_tests is False

    def test_branch_response_from_branch_info(self):
        """BranchResponse.from_branch_info converts correctly."""
        info = BranchInfo(
            name="main",
            is_current=True,
            commit_hash="abc123",
            ahead=2,
            behind=1,
        )

        response = BranchResponse.from_branch_info(info)

        assert response.name == "main"
        assert response.is_current is True
        assert response.commit_hash == "abc123"
        assert response.ahead == 2
        assert response.behind == 1
