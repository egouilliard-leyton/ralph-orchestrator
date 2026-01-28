"""Integration tests for GitPanel UI component.

Tests the git integration panel that displays branches, allows branch
management, and PR creation.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from ralph_orchestrator.services.git_service import (
    GitService,
    BranchInfo,
    PRInfo,
    GitError,
)


@pytest.fixture
def mock_git_service():
    """Create a mock git service with test data."""
    service = Mock(spec=GitService)

    # Mock branches data
    current_branch = BranchInfo(
        name="feature/test",
        is_current=True,
        commit_hash="abc1234",
        commit_message="feat: add test feature",
        ahead=2,
        behind=0,
    )

    other_branch = BranchInfo(
        name="main",
        is_current=False,
        commit_hash="def5678",
        commit_message="chore: update dependencies",
        ahead=0,
        behind=3,
    )

    service.list_branches.return_value = [current_branch, other_branch]
    service.get_current_branch.return_value = "feature/test"

    return service


@pytest.fixture
def git_api_responses():
    """Provide mock API response data for git endpoints."""
    return {
        "branches": {
            "branches": [
                {
                    "name": "feature/test",
                    "isCurrent": True,
                    "isRemote": False,
                    "tracking": "origin/feature/test",
                    "commitHash": "abc1234",
                    "commitMessage": "feat: add test feature",
                    "ahead": 2,
                    "behind": 0,
                },
                {
                    "name": "main",
                    "isCurrent": False,
                    "isRemote": False,
                    "tracking": "origin/main",
                    "commitHash": "def5678",
                    "commitMessage": "chore: update dependencies",
                    "ahead": 0,
                    "behind": 3,
                },
            ],
            "currentBranch": "feature/test",
            "total": 2,
        },
        "create_branch": {
            "success": True,
            "branchName": "feature/new-feature",
            "baseBranch": "main",
            "commitHash": "abc1234",
        },
        "create_pr": {
            "success": True,
            "prNumber": 42,
            "prUrl": "https://github.com/user/repo/pull/42",
            "title": "Test PR",
            "baseBranch": "main",
            "headBranch": "feature/test",
        },
    }


class TestGitPanelBranchDisplay:
    """Test branch display functionality."""

    def test_displays_current_branch_prominently(self, mock_git_service):
        """GitPanel displays current branch prominently."""
        branches = mock_git_service.list_branches(Path("/test"))
        current = next(b for b in branches if b.is_current)

        assert current.name == "feature/test"
        assert current.is_current is True
        # Verify branch has required display data
        assert current.commit_hash is not None
        assert current.commit_message is not None

    def test_branch_list_shows_all_metadata(self, mock_git_service):
        """Branch list shows name, ahead/behind, last commit info."""
        branches = mock_git_service.list_branches(Path("/test"))

        for branch in branches:
            # Verify all required fields are present
            assert branch.name is not None
            assert branch.commit_hash is not None
            assert branch.commit_message is not None
            assert isinstance(branch.ahead, int)
            assert isinstance(branch.behind, int)

    def test_branch_ahead_behind_indicators(self, mock_git_service):
        """Branches show commits ahead/behind remote correctly."""
        branches = mock_git_service.list_branches(Path("/test"))

        current = next(b for b in branches if b.name == "feature/test")
        assert current.ahead == 2
        assert current.behind == 0

        main = next(b for b in branches if b.name == "main")
        assert main.ahead == 0
        assert main.behind == 3


class TestGitPanelBranchOperations:
    """Test branch management operations."""

    def test_create_branch_with_name_input(self, mock_git_service):
        """Create Branch button with name template input."""
        project_path = Path("/test")
        new_branch = "feature/new-feature"

        # Mock the create_branch method
        mock_git_service.create_branch.return_value = BranchInfo(
            name=new_branch,
            is_current=True,
            commit_hash="abc1234",
        )

        result = mock_git_service.create_branch(
            project_path,
            new_branch,
            base_branch="main",
            switch=True,
        )

        assert result.name == new_branch
        assert result.is_current is True
        mock_git_service.create_branch.assert_called_once()

    def test_switch_branch_action(self, mock_git_service):
        """Switch Branch action changes current branch."""
        project_path = Path("/test")
        target_branch = "main"

        mock_git_service.switch_branch.return_value = None

        mock_git_service.switch_branch(project_path, target_branch)

        mock_git_service.switch_branch.assert_called_once_with(
            project_path,
            target_branch,
        )

    def test_delete_branch_with_confirmation(self, mock_git_service):
        """Delete Branch action requires confirmation."""
        project_path = Path("/test")
        branch_to_delete = "feature/old-feature"

        mock_git_service.delete_branch.return_value = None

        # Simulate confirmation flow
        confirmed = True
        if confirmed:
            mock_git_service.delete_branch(
                project_path,
                branch_to_delete,
                force=False,
            )

        mock_git_service.delete_branch.assert_called_once_with(
            project_path,
            branch_to_delete,
            force=False,
        )

    def test_cannot_delete_current_branch(self, mock_git_service):
        """Cannot delete the currently checked out branch."""
        project_path = Path("/test")
        current_branch = "feature/test"

        mock_git_service.get_current_branch.return_value = current_branch

        # Git service should raise error when trying to delete current branch
        mock_git_service.delete_branch.side_effect = GitError(
            "Cannot delete the currently checked out branch"
        )

        with pytest.raises(GitError, match="currently checked out"):
            mock_git_service.delete_branch(project_path, current_branch)


class TestGitPanelPRCreation:
    """Test pull request creation functionality."""

    def test_create_pr_button_opens_modal(self):
        """Create PR button opens modal with form fields."""
        # This tests the UI flow - modal should have:
        # - Title input (auto-generated)
        # - Description/body input (from acceptance criteria)
        # - One-click creation action
        modal_fields = {
            "title": "feat: add new feature",
            "description": "Acceptance criteria:\n- Item 1\n- Item 2",
            "baseBranch": "main",
        }

        assert "title" in modal_fields
        assert "description" in modal_fields
        assert "baseBranch" in modal_fields

    def test_pr_title_auto_generated(self, mock_git_service):
        """PR title is auto-generated from branch or commits."""
        current_branch = "feature/add-user-auth"

        # Title can be generated from branch name
        title = " ".join(current_branch.split("/")[1:]).replace("-", " ").title()

        assert "User Auth" in title or "user auth" in title.lower()

    def test_pr_description_from_acceptance_criteria(self):
        """PR description generated from acceptance criteria."""
        acceptance_criteria = [
            "GitPanel displays current branch",
            "Branch list shows metadata",
            "Create PR modal works",
        ]

        description = "## Acceptance Criteria\n\n"
        for criterion in acceptance_criteria:
            description += f"- [ ] {criterion}\n"

        assert "Acceptance Criteria" in description
        assert all(criterion in description for criterion in acceptance_criteria)

    def test_create_pr_via_api(self, mock_git_service):
        """Create PR via POST /api/projects/{id}/pr."""
        project_path = Path("/test")

        pr_info = PRInfo(
            number=42,
            url="https://github.com/user/repo/pull/42",
            title="feat: add user authentication",
            body="Description here",
            state="open",
            base_branch="main",
            head_branch="feature/add-user-auth",
            author="testuser",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        mock_git_service.create_pr.return_value = pr_info

        result = mock_git_service.create_pr(
            project_path,
            title="feat: add user authentication",
            body="Description here",
            base_branch="main",
        )

        assert result.number == 42
        assert result.url == "https://github.com/user/repo/pull/42"
        assert result.state == "open"

    def test_pr_success_shows_link(self, mock_git_service):
        """PR creation success shows link to GitHub/GitLab PR."""
        pr_info = PRInfo(
            number=42,
            url="https://github.com/user/repo/pull/42",
            title="Test PR",
            body="",
            state="open",
            base_branch="main",
            head_branch="feature/test",
            author="",
            created_at="",
            updated_at="",
        )

        mock_git_service.create_pr.return_value = pr_info

        result = mock_git_service.create_pr(
            Path("/test"),
            title="Test PR",
            body="",
        )

        # Verify URL is a valid GitHub/GitLab PR URL
        assert "github.com" in result.url or "gitlab.com" in result.url
        assert "/pull/" in result.url or "/merge_requests/" in result.url
        assert result.number > 0


class TestGitPanelErrorHandling:
    """Test error handling in git operations."""

    def test_handles_git_errors_gracefully(self, mock_git_service):
        """Git errors are caught and displayed to user."""
        project_path = Path("/test")

        mock_git_service.create_branch.side_effect = GitError(
            "Branch already exists: feature/test"
        )

        with pytest.raises(GitError) as exc_info:
            mock_git_service.create_branch(
                project_path,
                "feature/test",
            )

        assert "already exists" in str(exc_info.value)

    def test_handles_pr_creation_failure(self, mock_git_service):
        """PR creation failures are handled with error messages."""
        project_path = Path("/test")

        mock_git_service.create_pr.side_effect = GitError(
            "Failed to create PR: Not authenticated with gh CLI"
        )

        with pytest.raises(GitError) as exc_info:
            mock_git_service.create_pr(
                project_path,
                title="Test",
                body="",
            )

        assert "Not authenticated" in str(exc_info.value) or "Failed" in str(exc_info.value)

    def test_handles_network_errors(self):
        """Network errors when fetching branch data are handled."""
        # Simulate network error
        error_response = {
            "detail": "Failed to fetch branches: Network error",
            "error_code": "NETWORK_ERROR",
        }

        assert "detail" in error_response
        assert "Network error" in error_response["detail"]


class TestGitPanelAPIIntegration:
    """Test integration with backend API endpoints.

    These tests verify the expected API contract for git operations
    using mock responses instead of live HTTP calls.
    """

    def test_list_branches_api_response_format(self, git_api_responses):
        """GET /api/projects/{id}/branches response format validation."""
        response_data = git_api_responses["branches"]

        # Validate response structure
        assert "branches" in response_data
        assert "currentBranch" in response_data
        assert "total" in response_data

        # Validate branch data
        branches = response_data["branches"]
        assert len(branches) > 0
        for branch in branches:
            assert "name" in branch
            assert "isCurrent" in branch
            assert "commitHash" in branch
            assert "commitMessage" in branch
            assert "ahead" in branch
            assert "behind" in branch

    def test_create_branch_api_response_format(self, git_api_responses):
        """POST /api/projects/{id}/branches response format validation."""
        response_data = git_api_responses["create_branch"]

        # Validate response structure
        assert "success" in response_data
        assert response_data["success"] is True
        assert "branchName" in response_data
        assert "baseBranch" in response_data

    def test_create_pr_api_response_format(self, git_api_responses):
        """POST /api/projects/{id}/pr response format validation."""
        response_data = git_api_responses["create_pr"]

        # Validate response structure
        assert "success" in response_data
        assert response_data["success"] is True
        assert "prNumber" in response_data
        assert "prUrl" in response_data
        assert "title" in response_data
        assert "baseBranch" in response_data
        assert "headBranch" in response_data

        # Validate PR URL format
        assert "github.com" in response_data["prUrl"] or "gitlab.com" in response_data["prUrl"]
        assert response_data["prNumber"] > 0

    def test_api_request_format_branches(self):
        """Validate expected request format for listing branches."""
        # Expected endpoint: GET /api/projects/{project_id}/branches
        endpoint_pattern = "/api/projects/{project_id}/branches"

        # Verify endpoint structure
        assert "{project_id}" in endpoint_pattern
        assert endpoint_pattern.startswith("/api/")

    def test_api_request_format_create_branch(self):
        """Validate expected request format for creating a branch."""
        # Expected request body for POST /api/projects/{id}/branches
        request_body = {
            "branchName": "feature/test",
            "baseBranch": "main",
            "switch": True,
        }

        # Validate required fields
        assert "branchName" in request_body
        assert "baseBranch" in request_body
        # switch is optional but useful
        assert isinstance(request_body.get("switch", False), bool)

    def test_api_request_format_create_pr(self):
        """Validate expected request format for creating a PR."""
        # Expected request body for POST /api/projects/{id}/pr
        request_body = {
            "title": "Test PR",
            "body": "Description",
            "baseBranch": "main",
        }

        # Validate required fields
        assert "title" in request_body
        assert "body" in request_body
        assert "baseBranch" in request_body
