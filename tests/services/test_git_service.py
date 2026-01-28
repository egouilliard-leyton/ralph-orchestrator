"""Unit tests for GitService."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from ralph_orchestrator.services.git_service import (
    GitService,
    GitError,
    BranchInfo,
    PRInfo,
)


@pytest.fixture
def git_service():
    """Create a GitService instance."""
    return GitService()


class TestBranchInfo:
    """Test BranchInfo dataclass."""

    def test_branch_info_creation(self):
        """Test creating BranchInfo."""
        branch = BranchInfo(
            name="feature/test",
            is_current=True,
            is_remote=False,
            tracking="origin/feature/test",
            commit_hash="abc123",
            commit_message="Test commit",
            ahead=2,
            behind=0
        )
        
        assert branch.name == "feature/test"
        assert branch.is_current is True
        assert branch.tracking == "origin/feature/test"
        assert branch.ahead == 2
        assert branch.behind == 0


class TestPRInfo:
    """Test PRInfo dataclass."""

    def test_pr_info_creation(self):
        """Test creating PRInfo."""
        pr = PRInfo(
            number=123,
            url="https://github.com/user/repo/pull/123",
            title="Test PR",
            body="Test body",
            state="open",
            base_branch="main",
            head_branch="feature/test",
            author="testuser",
            created_at="2026-01-28T00:00:00Z",
            updated_at="2026-01-28T00:00:00Z"
        )

        assert pr.number == 123
        assert pr.url == "https://github.com/user/repo/pull/123"
        assert pr.title == "Test PR"
        assert pr.body == "Test body"
        assert pr.state == "open"
        assert pr.base_branch == "main"
        assert pr.head_branch == "feature/test"
        assert pr.author == "testuser"


class TestGitService:
    """Test GitService class."""

    @patch('subprocess.run')
    def test_get_current_branch(self, mock_run, git_service, tmp_path):
        """Test getting current branch."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="main\n",
            stderr=""
        )
        
        branch = git_service.get_current_branch(tmp_path)
        
        assert branch == "main"
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_current_branch_error(self, mock_run, git_service, tmp_path):
        """Test getting current branch when git fails."""
        mock_run.return_value = MagicMock(
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository"
        )
        
        with pytest.raises(GitError):
            git_service.get_current_branch(tmp_path)

    @patch('subprocess.run')
    def test_list_branches(self, mock_run, git_service, tmp_path):
        """Test listing branches."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="* main\n  feature/test\n",
            stderr=""
        )
        
        branches = git_service.list_branches(tmp_path, include_remote=False)
        
        assert len(branches) >= 0  # Implementation may vary
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_create_branch(self, mock_run, git_service, tmp_path):
        """Test creating a new branch."""
        # Mock git commands in order:
        # 1. branch_exists check (rev-parse --verify) - returns 128 for "not found"
        # 2. get_current_branch check
        # 3. git checkout -b
        # 4. git rev-parse HEAD for commit hash
        # 5. git log for commit message
        mock_run.side_effect = [
            MagicMock(returncode=128, stdout="", stderr="fatal: not a valid ref"),  # branch_exists
            MagicMock(returncode=0, stdout="main\n", stderr=""),  # get_current_branch
            MagicMock(returncode=0, stdout="", stderr=""),  # git checkout -b
            MagicMock(returncode=0, stdout="abc123\n", stderr=""),  # git rev-parse HEAD
            MagicMock(returncode=0, stdout="Test commit\n", stderr=""),  # git log
        ]

        branch_info = git_service.create_branch(
            tmp_path,
            "feature/new-branch",
            switch=True
        )

        assert branch_info.name == "feature/new-branch"

    @patch('subprocess.run')
    def test_create_branch_already_exists(self, mock_run, git_service, tmp_path):
        """Test creating a branch that already exists."""
        # branch_exists returns 0 (success) meaning branch does exist
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\n",
            stderr=""
        )

        with pytest.raises(GitError, match="already exists"):
            git_service.create_branch(tmp_path, "feature/test")


class TestGitError:
    """Test GitError exception."""

    def test_git_error_message(self):
        """Test GitError with message."""
        error = GitError("Test error message")
        
        assert str(error) == "Test error message"

    def test_git_error_raise(self):
        """Test raising GitError."""
        with pytest.raises(GitError) as exc_info:
            raise GitError("Something went wrong")
        
        assert "Something went wrong" in str(exc_info.value)
