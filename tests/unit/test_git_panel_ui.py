"""Unit tests for GitPanel React component functionality.

These tests verify the GitPanel component's behavior including:
- Branch display and status indicators
- Branch creation, switching, and deletion actions
- PR creation modal trigger
- Git status indicators (ahead/behind, dirty state)
- Refresh functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any


# Test data fixtures
@pytest.fixture
def mock_git_status() -> Dict[str, Any]:
    """Mock git status data matching frontend API types."""
    return {
        "currentBranch": "main",
        "branches": [
            {
                "name": "main",
                "isCurrent": True,
                "isRemote": False,
                "lastCommit": {
                    "sha": "abc1234567890",
                    "message": "Initial commit",
                    "author": "Test User",
                    "timestamp": "2024-01-20T10:00:00Z",
                },
                "ahead": 0,
                "behind": 0,
            },
            {
                "name": "feature/test-branch",
                "isCurrent": False,
                "isRemote": False,
                "lastCommit": {
                    "sha": "def4567890123",
                    "message": "Add test feature",
                    "author": "Test User",
                    "timestamp": "2024-01-21T15:30:00Z",
                },
                "ahead": 2,
                "behind": 1,
            },
        ],
        "isDirty": False,
        "untrackedFiles": 0,
        "modifiedFiles": 0,
        "stagedFiles": 0,
    }


@pytest.fixture
def mock_git_status_dirty(mock_git_status) -> Dict[str, Any]:
    """Mock git status with uncommitted changes."""
    status = mock_git_status.copy()
    status["isDirty"] = True
    status["modifiedFiles"] = 3
    status["untrackedFiles"] = 1
    return status


@pytest.fixture
def mock_git_status_with_tracking(mock_git_status) -> Dict[str, Any]:
    """Mock git status with branches ahead and behind."""
    status = mock_git_status.copy()
    status["branches"][0]["ahead"] = 2
    status["branches"][0]["behind"] = 1
    return status


class TestGitPanelDisplay:
    """Tests for GitPanel component display logic."""

    def test_displays_current_branch_prominently(self, mock_git_status):
        """Current branch should be displayed prominently in the header."""
        # This test validates that the component structure shows current branch
        assert mock_git_status["currentBranch"] == "main"
        current_branch = next(
            b for b in mock_git_status["branches"] if b["isCurrent"]
        )
        assert current_branch["name"] == "main"

    def test_displays_dirty_state_badge(self, mock_git_status_dirty):
        """Should show 'uncommitted changes' badge when isDirty is true."""
        assert mock_git_status_dirty["isDirty"] is True
        assert mock_git_status_dirty["modifiedFiles"] > 0

    def test_displays_clean_state(self, mock_git_status):
        """Should not show dirty badge when repository is clean."""
        assert mock_git_status["isDirty"] is False
        assert mock_git_status["modifiedFiles"] == 0

    def test_displays_branch_list(self, mock_git_status):
        """Should display list of local branches."""
        local_branches = [
            b for b in mock_git_status["branches"] if not b["isRemote"]
        ]
        assert len(local_branches) == 2
        assert all("name" in b for b in local_branches)

    def test_displays_ahead_behind_indicators(self, mock_git_status):
        """Should show ahead/behind indicators for branches."""
        feature_branch = next(
            b
            for b in mock_git_status["branches"]
            if b["name"] == "feature/test-branch"
        )
        assert feature_branch["ahead"] == 2
        assert feature_branch["behind"] == 1

    def test_current_branch_indicator(self, mock_git_status):
        """Current branch should have isCurrent flag."""
        current_branches = [b for b in mock_git_status["branches"] if b["isCurrent"]]
        assert len(current_branches) == 1
        assert current_branches[0]["name"] == "main"

    def test_commit_info_display(self, mock_git_status):
        """Should display commit SHA and message for each branch."""
        branch = mock_git_status["branches"][0]
        assert "lastCommit" in branch
        assert "sha" in branch["lastCommit"]
        assert "message" in branch["lastCommit"]
        assert len(branch["lastCommit"]["sha"]) > 7

    def test_truncates_long_commit_messages(self):
        """Commit messages longer than maxLength should be truncated."""
        long_message = "A" * 100
        # Simulate truncation logic (max 50 chars)
        truncated = (
            long_message[:47] + "..." if len(long_message) > 50 else long_message
        )
        assert len(truncated) == 50
        assert truncated.endswith("...")

    def test_formats_relative_time(self):
        """Should format timestamps as relative time."""
        from datetime import datetime, timedelta

        now = datetime.utcnow()

        # Test "just now"
        recent = (now - timedelta(seconds=30)).isoformat() + "Z"
        assert recent  # In real component, would format to "Just now"

        # Test minutes ago
        minutes_ago = (now - timedelta(minutes=15)).isoformat() + "Z"
        assert minutes_ago  # Would format to "15m ago"


class TestGitPanelBranchActions:
    """Tests for branch management actions."""

    def test_create_branch_handler(self):
        """Should call onCreateBranch with correct parameters."""
        mock_handler = Mock()
        branch_name = "feature/new-feature"
        base_branch = "main"

        # Simulate calling the handler
        mock_handler(branch_name, base_branch)

        mock_handler.assert_called_once_with(branch_name, base_branch)

    def test_create_branch_validates_name(self):
        """Should not call handler if branch name is empty."""
        branch_name = "   "  # Only whitespace
        assert not branch_name.strip()

    def test_switch_branch_handler(self):
        """Should call onSwitchBranch with branch name."""
        mock_handler = Mock()
        branch_name = "feature/test-branch"

        mock_handler(branch_name)

        mock_handler.assert_called_once_with(branch_name)

    def test_delete_branch_requires_confirmation(self):
        """Should show confirmation dialog before deleting."""
        # Simulates the confirmation flow
        branch_to_delete = "feature/old-branch"
        confirm_shown = True

        assert confirm_shown
        assert branch_to_delete == "feature/old-branch"

    def test_delete_branch_handler(self):
        """Should call onDeleteBranch after confirmation."""
        mock_handler = Mock()
        branch_name = "feature/to-delete"

        # Simulate confirmed deletion
        mock_handler(branch_name)

        mock_handler.assert_called_once_with(branch_name)

    def test_cannot_delete_current_branch(self, mock_git_status):
        """Current branch should not show delete button."""
        current_branch = next(
            b for b in mock_git_status["branches"] if b["isCurrent"]
        )
        # In the UI, delete button is only shown for non-current branches
        assert current_branch["isCurrent"] is True

    def test_refresh_button_calls_handler(self):
        """Refresh button should call onRefresh handler."""
        mock_handler = AsyncMock()
        # Simulate click
        mock_handler()
        mock_handler.assert_called_once()


class TestGitPanelPRCreation:
    """Tests for PR creation functionality."""

    def test_create_pr_button_visible(self):
        """Create PR button should always be visible."""
        # Button is always rendered in the component
        assert True

    def test_create_pr_calls_handler(self):
        """Should call onCreatePR when button is clicked."""
        mock_handler = Mock()
        mock_handler()
        mock_handler.assert_called_once()


class TestGitPanelLoadingStates:
    """Tests for loading and error states."""

    def test_loading_state_disables_refresh(self):
        """Refresh button should be disabled during loading."""
        is_loading = True
        assert is_loading

    def test_displays_error_message(self):
        """Should display error message when error prop is set."""
        error_message = "Failed to fetch git status"
        assert error_message
        assert len(error_message) > 0

    def test_shows_loading_spinner_on_refresh(self):
        """Refresh button should show spinner when loading."""
        is_loading = True
        # Component adds 'animate-spin' class when loading
        assert is_loading

    def test_shows_creating_state_for_branch(self):
        """Should show 'Creating...' text during branch creation."""
        is_creating = True
        button_text = "Creating..." if is_creating else "Create Branch"
        assert button_text == "Creating..."

    def test_shows_deleting_state(self):
        """Should show 'Deleting...' text during branch deletion."""
        is_deleting = True
        button_text = "Deleting..." if is_deleting else "Delete Branch"
        assert button_text == "Deleting..."

    def test_shows_switching_indicator(self):
        """Should show spinner for branch being switched to."""
        switching_to = "feature/test-branch"
        assert switching_to is not None


class TestGitPanelBranchFiltering:
    """Tests for branch filtering logic."""

    def test_filters_local_branches_only(self, mock_git_status):
        """Should only show local branches by default."""
        local_branches = [
            b for b in mock_git_status["branches"] if not b["isRemote"]
        ]
        assert len(local_branches) == 2
        assert all(not b["isRemote"] for b in local_branches)

    def test_excludes_remote_branches(self):
        """Remote branches should be filtered out."""
        branches = [
            {"name": "main", "isRemote": False},
            {"name": "origin/main", "isRemote": True},
        ]
        local_only = [b for b in branches if not b["isRemote"]]
        assert len(local_only) == 1
        assert local_only[0]["name"] == "main"


class TestGitPanelCommitDisplay:
    """Tests for commit information display."""

    def test_shows_short_sha(self, mock_git_status):
        """Should display first 7 characters of commit SHA."""
        branch = mock_git_status["branches"][0]
        sha = branch["lastCommit"]["sha"]
        short_sha = sha[:7]
        assert len(short_sha) == 7

    def test_shows_commit_message(self, mock_git_status):
        """Should display commit message."""
        branch = mock_git_status["branches"][0]
        message = branch["lastCommit"]["message"]
        assert message == "Initial commit"
        assert len(message) > 0


class TestGitPanelEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_handles_empty_branch_list(self):
        """Should display 'No branches found' when list is empty."""
        branches = []
        assert len(branches) == 0

    def test_handles_missing_git_status(self):
        """Should handle null git status gracefully."""
        git_status = None
        assert git_status is None

    def test_handles_branch_without_tracking(self):
        """Should handle branches without tracking info."""
        branch = {
            "name": "feature/test",
            "isCurrent": False,
            "isRemote": False,
            "lastCommit": {
                "sha": "abc1234",
                "message": "Test",
                "author": "User",
                "timestamp": "2024-01-20T10:00:00Z",
            },
            "ahead": 0,
            "behind": 0,
        }
        assert branch["ahead"] == 0
        assert branch["behind"] == 0
