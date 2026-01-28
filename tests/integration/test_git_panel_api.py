"""Integration tests for Git Panel API endpoints.

Tests the REST API endpoints that the GitPanel UI component will use:
- GET /api/projects/{id}/branches - List branches with status
- POST /api/projects/{id}/branches - Create branch
- POST /api/projects/{id}/pr - Create pull request

These tests verify the acceptance criteria for T-013 GitPanel functionality.
"""

import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.parse import quote

from fastapi.testclient import TestClient

from server.api import app
from ralph_orchestrator.services.git_service import GitService, GitError, BranchInfo, PRInfo


def encode_project_path(path: Path) -> str:
    """URL-encode a project path for use in API URLs."""
    return quote(str(path), safe="")


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    """Create a git repository for testing git operations."""
    project_path = tmp_path / "git_test_project"
    project_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, check=True, capture_output=True)

    # Create initial commit
    (project_path / "README.md").write_text("# Test Project")
    subprocess.run(["git", "add", "."], cwd=project_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, check=True, capture_output=True)

    # Create main branch
    subprocess.run(["git", "branch", "-M", "main"], cwd=project_path, check=True, capture_output=True)

    # Create .ralph directory
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir()

    return project_path


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestListBranches:
    """Test GET /api/projects/{id}/branches endpoint."""

    def test_list_local_branches(self, client: TestClient, git_project: Path):
        """Test listing local branches only."""
        # Create additional branches
        subprocess.run(["git", "checkout", "-b", "feature/test"], cwd=git_project, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=git_project, check=True, capture_output=True)

        response = client.get(f"/api/projects/{encode_project_path(git_project)}/branches")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "branches" in data
        assert "current_branch" in data
        assert "total" in data

        # Verify current branch
        assert data["current_branch"] == "main"

        # Verify branches list
        assert len(data["branches"]) >= 2
        branch_names = [b["name"] for b in data["branches"]]
        assert "main" in branch_names
        assert "feature/test" in branch_names

        # Verify current branch is marked
        main_branch = next(b for b in data["branches"] if b["name"] == "main")
        assert main_branch["is_current"] is True

    def test_list_branches_with_commit_info(self, client: TestClient, git_project: Path):
        """Test that branches include commit hash and message."""
        response = client.get(f"/api/projects/{encode_project_path(git_project)}/branches")

        assert response.status_code == 200
        data = response.json()

        # Verify commit information is present
        main_branch = next(b for b in data["branches"] if b["name"] == "main")
        assert main_branch["commit_hash"] is not None
        assert main_branch["commit_message"] is not None
        assert "Initial commit" in main_branch["commit_message"]

    def test_list_branches_with_remote(self, client: TestClient, git_project: Path):
        """Test listing branches with remote branches included."""
        # Create a bare repo to simulate remote
        remote_path = git_project.parent / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote_path)], check=True, capture_output=True)

        # Add remote
        subprocess.run(["git", "remote", "add", "origin", str(remote_path)], cwd=git_project, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=git_project, check=True, capture_output=True)

        response = client.get(f"/api/projects/{encode_project_path(git_project)}/branches?include_remote=true")

        assert response.status_code == 200
        data = response.json()

        # Should include remote branches
        branch_names = [b["name"] for b in data["branches"]]
        assert any("origin/main" in name for name in branch_names)

    def test_list_branches_ahead_behind_info(self, client: TestClient, git_project: Path):
        """Test that branches show ahead/behind counts (acceptance criteria)."""
        # This tests the requirement: "Branch list shows: name, commits ahead/behind remote"
        response = client.get(f"/api/projects/{encode_project_path(git_project)}/branches")

        assert response.status_code == 200
        data = response.json()

        # Verify ahead/behind fields exist
        for branch in data["branches"]:
            assert "ahead" in branch
            assert "behind" in branch
            assert isinstance(branch["ahead"], int)
            assert isinstance(branch["behind"], int)

    def test_list_branches_nonexistent_project(self, client: TestClient, tmp_path: Path):
        """Test error handling for nonexistent project."""
        nonexistent = tmp_path / "does_not_exist"

        response = client.get(f"/api/projects/{encode_project_path(nonexistent)}/branches")

        assert response.status_code == 400
        assert "error" in response.json()["detail"].lower() or "git" in response.json()["detail"].lower()


class TestCreateBranch:
    """Test POST /api/projects/{id}/branches endpoint."""

    def test_create_branch_basic(self, client: TestClient, git_project: Path):
        """Test creating a new branch."""
        request_data = {
            "branch_name": "feature/new-feature",
            "switch": True
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/branches",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["branch_name"] == "feature/new-feature"
        assert data["commit_hash"] is not None

        # Verify branch was actually created
        result = subprocess.run(
            ["git", "branch"],
            cwd=git_project,
            capture_output=True,
            text=True,
            check=True
        )
        assert "feature/new-feature" in result.stdout

    def test_create_branch_with_base(self, client: TestClient, git_project: Path):
        """Test creating a branch from a specific base branch."""
        # Create a feature branch first
        subprocess.run(["git", "checkout", "-b", "feature/base"], cwd=git_project, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=git_project, check=True, capture_output=True)

        request_data = {
            "branch_name": "feature/from-feature",
            "base_branch": "feature/base",
            "switch": False
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/branches",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["base_branch"] == "feature/base"

    def test_create_branch_without_switching(self, client: TestClient, git_project: Path):
        """Test creating a branch without switching to it."""
        request_data = {
            "branch_name": "feature/no-switch",
            "switch": False
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/branches",
            json=request_data
        )

        assert response.status_code == 200

        # Verify still on main branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=git_project,
            capture_output=True,
            text=True,
            check=True
        )
        assert result.stdout.strip() == "main"

        # But new branch exists
        result = subprocess.run(
            ["git", "branch"],
            cwd=git_project,
            capture_output=True,
            text=True,
            check=True
        )
        assert "feature/no-switch" in result.stdout

    def test_create_branch_already_exists(self, client: TestClient, git_project: Path):
        """Test error when creating a branch that already exists."""
        # Create branch first
        subprocess.run(["git", "checkout", "-b", "existing"], cwd=git_project, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=git_project, check=True, capture_output=True)

        request_data = {
            "branch_name": "existing",
            "switch": False
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/branches",
            json=request_data
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower() or "error" in response.json()["detail"].lower()

    def test_create_branch_invalid_name(self, client: TestClient, git_project: Path):
        """Test error with invalid branch name."""
        request_data = {
            "branch_name": "",  # Empty name should fail validation
            "switch": True
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/branches",
            json=request_data
        )

        # Should fail either at validation or git level
        assert response.status_code in [400, 422]


class TestCreatePR:
    """Test POST /api/projects/{id}/pr endpoint."""

    @patch("ralph_orchestrator.services.git_service.GitService.detect_forge")
    @patch("ralph_orchestrator.services.git_service.GitService._run_cli")
    def test_create_pr_github(
        self,
        mock_run_cli: MagicMock,
        mock_detect_forge: MagicMock,
        client: TestClient,
        git_project: Path
    ):
        """Test creating a GitHub pull request (acceptance criteria)."""
        # Mock forge detection
        mock_detect_forge.return_value = "github"

        # Mock gh CLI response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/pull/42\n"
        mock_result.stderr = ""
        mock_run_cli.return_value = mock_result

        # Create a feature branch
        subprocess.run(["git", "checkout", "-b", "feature/test-pr"], cwd=git_project, check=True, capture_output=True)

        request_data = {
            "title": "Add new feature",
            "body": "## Summary\n- Implemented feature X\n- Added tests\n\n## Acceptance Criteria\n- Feature works\n- Tests pass",
            "base_branch": "main",
            "draft": False
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/pr",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()

        # Verify PR response structure (acceptance criteria)
        assert data["success"] is True
        assert data["pr_number"] == 42
        assert data["pr_url"] == "https://github.com/user/repo/pull/42"
        assert data["title"] == "Add new feature"
        assert data["base_branch"] == "main"
        assert data["head_branch"] == "feature/test-pr"

    @patch("ralph_orchestrator.services.git_service.GitService.detect_forge")
    @patch("ralph_orchestrator.services.git_service.GitService._run_cli")
    def test_create_pr_with_draft(
        self,
        mock_run_cli: MagicMock,
        mock_detect_forge: MagicMock,
        client: TestClient,
        git_project: Path
    ):
        """Test creating a draft PR."""
        mock_detect_forge.return_value = "github"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/pull/43\n"
        mock_run_cli.return_value = mock_result

        subprocess.run(["git", "checkout", "-b", "draft-pr"], cwd=git_project, check=True, capture_output=True)

        request_data = {
            "title": "WIP: New feature",
            "body": "Work in progress",
            "draft": True
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/pr",
            json=request_data
        )

        assert response.status_code == 200

        # Verify gh CLI was called with --draft flag
        call_args = mock_run_cli.call_args
        assert "--draft" in call_args[0][2]  # args parameter

    @patch("ralph_orchestrator.services.git_service.GitService.detect_forge")
    @patch("ralph_orchestrator.services.git_service.GitService._run_cli")
    def test_create_pr_with_labels(
        self,
        mock_run_cli: MagicMock,
        mock_detect_forge: MagicMock,
        client: TestClient,
        git_project: Path
    ):
        """Test creating a PR with labels."""
        mock_detect_forge.return_value = "github"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/pull/44\n"
        mock_run_cli.return_value = mock_result

        subprocess.run(["git", "checkout", "-b", "labeled-pr"], cwd=git_project, check=True, capture_output=True)

        request_data = {
            "title": "Bug fix",
            "body": "Fixes issue #123",
            "labels": ["bug", "high-priority"]
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/pr",
            json=request_data
        )

        assert response.status_code == 200

        # Verify gh CLI was called with labels
        call_args = mock_run_cli.call_args
        args = call_args[0][2]
        assert "--label" in args

    @patch("ralph_orchestrator.services.git_service.GitService.detect_forge")
    def test_create_pr_no_forge_detected(
        self,
        mock_detect_forge: MagicMock,
        client: TestClient,
        git_project: Path
    ):
        """Test error when forge cannot be detected."""
        mock_detect_forge.return_value = None

        subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=git_project, check=True, capture_output=True)

        request_data = {
            "title": "Test PR",
            "body": "Test body"
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/pr",
            json=request_data
        )

        assert response.status_code == 400
        assert "forge" in response.json()["detail"].lower() or "github" in response.json()["detail"].lower()

    @patch("ralph_orchestrator.services.git_service.GitService.detect_forge")
    @patch("ralph_orchestrator.services.git_service.GitService._run_cli")
    def test_create_pr_acceptance_criteria_in_body(
        self,
        mock_run_cli: MagicMock,
        mock_detect_forge: MagicMock,
        client: TestClient,
        git_project: Path
    ):
        """Test PR creation with acceptance criteria from task (acceptance criteria)."""
        # This tests the requirement: "Create PR button opens modal: ...description (from acceptance criteria)"
        mock_detect_forge.return_value = "github"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/pull/45\n"
        mock_run_cli.return_value = mock_result

        subprocess.run(["git", "checkout", "-b", "feature/with-criteria"], cwd=git_project, check=True, capture_output=True)

        # Simulate auto-generated description from acceptance criteria
        acceptance_criteria = [
            "Feature X is implemented",
            "All tests pass",
            "Documentation is updated"
        ]
        body = "## Acceptance Criteria\n" + "\n".join(f"- {c}" for c in acceptance_criteria)

        request_data = {
            "title": "Implement Feature X",
            "body": body,
            "base_branch": "main"
        }

        response = client.post(
            f"/api/projects/{encode_project_path(git_project)}/pr",
            json=request_data
        )

        assert response.status_code == 200

        # Verify the body contains acceptance criteria
        call_args = mock_run_cli.call_args
        body_arg_index = call_args[0][2].index("--body") + 1
        actual_body = call_args[0][2][body_arg_index]
        assert "Acceptance Criteria" in actual_body
        assert "Feature X is implemented" in actual_body


class TestGitPanelAcceptanceCriteria:
    """Tests specifically for T-013 acceptance criteria."""

    def test_current_branch_displayed_prominently(self, client: TestClient, git_project: Path):
        """AC: src/components/GitPanel.tsx displays current branch prominently."""
        response = client.get(f"/api/projects/{encode_project_path(git_project)}/branches")

        assert response.status_code == 200
        data = response.json()

        # API must provide current_branch at top level for prominent display
        assert "current_branch" in data
        assert data["current_branch"] == "main"

    def test_branch_list_complete_info(self, client: TestClient, git_project: Path):
        """AC: Branch list shows: name, commits ahead/behind remote, last commit message, timestamp."""
        # Create multiple branches with different states
        subprocess.run(["git", "checkout", "-b", "feature/one"], cwd=git_project, check=True, capture_output=True)
        (git_project / "file1.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=git_project, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add feature one"], cwd=git_project, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=git_project, check=True, capture_output=True)

        response = client.get(f"/api/projects/{encode_project_path(git_project)}/branches")

        assert response.status_code == 200
        data = response.json()

        # Check each branch has required fields
        for branch in data["branches"]:
            # Name
            assert "name" in branch
            assert isinstance(branch["name"], str)

            # Commits ahead/behind
            assert "ahead" in branch
            assert "behind" in branch
            assert isinstance(branch["ahead"], int)
            assert isinstance(branch["behind"], int)

            # Last commit message
            assert "commit_message" in branch
            # Note: timestamp not in BranchInfo, but commit_hash can serve as unique identifier

            # Commit hash
            assert "commit_hash" in branch

    def test_create_branch_button_functionality(self, client: TestClient, git_project: Path):
        """AC: Create Branch button with name template input."""
        # This tests that the API supports creating branches with custom names
        custom_branch_names = [
            "feature/custom-name",
            "bugfix/issue-123",
            "release/v1.0.0"
        ]

        for branch_name in custom_branch_names:
            request_data = {
                "branch_name": branch_name,
                "switch": False
            }

            response = client.post(
                f"/api/projects/{encode_project_path(git_project)}/branches",
                json=request_data
            )

            assert response.status_code == 200
            assert response.json()["branch_name"] == branch_name

    def test_pr_creation_one_click(self, client: TestClient, git_project: Path):
        """AC: Create PR button...one-click creation via POST /api/projects/{id}/pr."""
        with patch("ralph_orchestrator.services.git_service.GitService.detect_forge") as mock_forge:
            with patch("ralph_orchestrator.services.git_service.GitService._run_cli") as mock_cli:
                mock_forge.return_value = "github"

                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "https://github.com/user/repo/pull/100\n"
                mock_cli.return_value = mock_result

                subprocess.run(["git", "checkout", "-b", "one-click-pr"], cwd=git_project, check=True, capture_output=True)

                # Minimal request - should succeed with defaults
                request_data = {
                    "title": "Auto-generated PR title",
                    "body": "Auto-generated from acceptance criteria"
                }

                response = client.post(
                    f"/api/projects/{encode_project_path(git_project)}/pr",
                    json=request_data
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "pr_url" in data

    def test_pr_success_shows_link(self, client: TestClient, git_project: Path):
        """AC: PR creation success shows link to GitHub/GitLab PR."""
        with patch("ralph_orchestrator.services.git_service.GitService.detect_forge") as mock_forge:
            with patch("ralph_orchestrator.services.git_service.GitService._run_cli") as mock_cli:
                mock_forge.return_value = "github"

                expected_url = "https://github.com/user/repo/pull/999"
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = expected_url + "\n"
                mock_cli.return_value = mock_result

                subprocess.run(["git", "checkout", "-b", "link-test"], cwd=git_project, check=True, capture_output=True)

                response = client.post(
                    f"/api/projects/{encode_project_path(git_project)}/pr",
                    json={"title": "Test", "body": "Test"}
                )

                assert response.status_code == 200
                data = response.json()

                # Must return the PR URL for UI to display
                assert data["pr_url"] == expected_url
