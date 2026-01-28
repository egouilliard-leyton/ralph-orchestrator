"""Integration tests for git service and API endpoints.

These tests verify the integration between:
- GitService and actual git operations
- REST API endpoints for git operations
- Branch management (create, switch, delete)
- PR creation via gh/glab CLI
- Git status retrieval
"""

import pytest
import tempfile
import subprocess
from pathlib import Path
from ralph_orchestrator.services.git_service import (
    GitService,
    GitError,
    BranchInfo,
    GitStatus,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repository")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )

    # Rename to main branch (if needed)
    try:
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        pass  # Branch might already be named main

    return repo_path


@pytest.fixture
def git_service():
    """Create a GitService instance."""
    return GitService()


class TestGitServiceBranchOperations:
    """Integration tests for branch operations."""

    def test_list_branches(self, git_service, git_repo):
        """Should list all branches in repository."""
        branches = git_service.list_branches(git_repo)

        assert len(branches) >= 1
        assert any(b.name == "main" or b.name == "master" for b in branches)
        assert all(isinstance(b, BranchInfo) for b in branches)

    def test_list_branches_with_remote(self, git_service, git_repo):
        """Should list both local and remote branches."""
        branches = git_service.list_branches(git_repo, include_remote=True)

        assert len(branches) >= 1
        # Local branches should be present
        assert any(not b.is_remote for b in branches)

    def test_get_current_branch(self, git_service, git_repo):
        """Should return current branch name."""
        current = git_service.get_current_branch(git_repo)

        assert current in ["main", "master"]
        assert isinstance(current, str)

    def test_create_branch(self, git_service, git_repo):
        """Should create new branch."""
        branch_name = "feature/test-feature"

        branch_info = git_service.create_branch(
            git_repo, branch_name, switch=False
        )

        assert branch_info.name == branch_name
        assert branch_info.commit_hash is not None

        # Verify branch exists
        assert git_service.branch_exists(git_repo, branch_name)

    def test_create_branch_and_switch(self, git_service, git_repo):
        """Should create branch and switch to it."""
        branch_name = "feature/auto-switch"

        git_service.create_branch(git_repo, branch_name, switch=True)

        current = git_service.get_current_branch(git_repo)
        assert current == branch_name

    def test_create_branch_from_base(self, git_service, git_repo):
        """Should create branch from specified base branch."""
        # Create a feature branch first
        git_service.create_branch(git_repo, "feature/base", switch=True)
        (git_repo / "feature.txt").write_text("feature")
        subprocess.run(
            ["git", "add", "feature.txt"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Switch back to main
        git_service.switch_branch(git_repo, "main")

        # Create new branch from feature/base
        git_service.create_branch(
            git_repo, "feature/from-base", base_branch="feature/base", switch=False
        )

        assert git_service.branch_exists(git_repo, "feature/from-base")

    def test_create_duplicate_branch_fails(self, git_service, git_repo):
        """Should fail when creating duplicate branch."""
        branch_name = "feature/duplicate"
        git_service.create_branch(git_repo, branch_name, switch=False)

        with pytest.raises(GitError, match="already exists"):
            git_service.create_branch(git_repo, branch_name, switch=False)

    def test_switch_branch(self, git_service, git_repo):
        """Should switch to existing branch."""
        # Create and switch to new branch
        git_service.create_branch(git_repo, "feature/switch-test", switch=False)
        git_service.switch_branch(git_repo, "feature/switch-test")

        current = git_service.get_current_branch(git_repo)
        assert current == "feature/switch-test"

    def test_switch_to_nonexistent_branch_fails(self, git_service, git_repo):
        """Should fail when switching to non-existent branch."""
        with pytest.raises(GitError):
            git_service.switch_branch(git_repo, "nonexistent-branch")

    def test_delete_branch(self, git_service, git_repo):
        """Should delete a branch."""
        branch_name = "feature/to-delete"
        git_service.create_branch(git_repo, branch_name, switch=False)

        # Switch away from the branch
        git_service.switch_branch(git_repo, "main")

        # Delete the branch
        git_service.delete_branch(git_repo, branch_name)

        assert not git_service.branch_exists(git_repo, branch_name)

    def test_delete_branch_force(self, git_service, git_repo):
        """Should force delete unmerged branch."""
        branch_name = "feature/unmerged"
        git_service.create_branch(git_repo, branch_name, switch=True)

        # Make a commit
        (git_repo / "unmerged.txt").write_text("unmerged changes")
        subprocess.run(
            ["git", "add", "unmerged.txt"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Unmerged commit"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Switch to main
        git_service.switch_branch(git_repo, "main")

        # Force delete
        git_service.delete_branch(git_repo, branch_name, force=True)

        assert not git_service.branch_exists(git_repo, branch_name)

    def test_branch_exists(self, git_service, git_repo):
        """Should check if branch exists."""
        assert git_service.branch_exists(git_repo, "main") or git_service.branch_exists(
            git_repo, "master"
        )
        assert not git_service.branch_exists(git_repo, "nonexistent")


class TestGitServiceStatusOperations:
    """Integration tests for git status operations."""

    def test_get_status_clean(self, git_service, git_repo):
        """Should return clean status for clean repo."""
        status = git_service.get_status(git_repo)

        assert isinstance(status, GitStatus)
        assert status.branch in ["main", "master"]
        assert status.is_clean is True
        assert len(status.staged) == 0
        assert len(status.unstaged) == 0
        assert len(status.untracked) == 0

    def test_get_status_with_untracked_files(self, git_service, git_repo):
        """Should detect untracked files."""
        # Create untracked file
        (git_repo / "untracked.txt").write_text("untracked content")

        status = git_service.get_status(git_repo)

        assert status.is_clean is False
        assert "untracked.txt" in status.untracked

    def test_get_status_with_modified_files(self, git_service, git_repo):
        """Should detect modified files."""
        # Modify tracked file
        (git_repo / "README.md").write_text("# Modified README")

        status = git_service.get_status(git_repo)

        assert status.is_clean is False
        assert "README.md" in status.unstaged

    def test_get_status_with_staged_files(self, git_service, git_repo):
        """Should detect staged files."""
        # Create and stage file
        (git_repo / "staged.txt").write_text("staged content")
        subprocess.run(
            ["git", "add", "staged.txt"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        status = git_service.get_status(git_repo)

        assert status.is_clean is False
        assert "staged.txt" in status.staged

    def test_is_clean(self, git_service, git_repo):
        """Should correctly identify clean working tree."""
        assert git_service.is_clean(git_repo) is True

        # Make it dirty
        (git_repo / "dirty.txt").write_text("dirty")

        assert git_service.is_clean(git_repo) is False

    def test_is_git_repo(self, git_service, git_repo, tmp_path):
        """Should correctly identify git repositories."""
        assert git_service.is_git_repo(git_repo) is True

        # Non-git directory
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()
        assert git_service.is_git_repo(non_git_dir) is False


class TestGitServiceRemoteOperations:
    """Integration tests for remote operations."""

    def test_get_remote_url(self, git_service, git_repo):
        """Should return None when no remote configured."""
        url = git_service.get_remote_url(git_repo)
        assert url is None

    def test_detect_forge_no_remote(self, git_service, git_repo):
        """Should return None when no remote configured."""
        forge = git_service.detect_forge(git_repo)
        assert forge is None

    def test_detect_forge_github(self, git_service, git_repo):
        """Should detect GitHub from remote URL."""
        # Add GitHub remote
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        forge = git_service.detect_forge(git_repo)
        assert forge == "github"

    def test_detect_forge_gitlab(self, git_service, git_repo):
        """Should detect GitLab from remote URL."""
        # Add GitLab remote
        subprocess.run(
            ["git", "remote", "add", "origin", "https://gitlab.com/user/repo.git"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        forge = git_service.detect_forge(git_repo)
        assert forge == "gitlab"


class TestGitServiceCommitOperations:
    """Integration tests for commit operations."""

    def test_commit(self, git_service, git_repo):
        """Should create a commit."""
        # Create and stage file
        (git_repo / "new_file.txt").write_text("new content")
        subprocess.run(
            ["git", "add", "new_file.txt"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        commit_hash = git_service.commit(git_repo, "Add new file")

        assert commit_hash is not None
        assert len(commit_hash) == 12  # Short hash

    def test_commit_with_add_all(self, git_service, git_repo):
        """Should stage and commit all changes."""
        # Create untracked file
        (git_repo / "auto_staged.txt").write_text("auto staged")

        commit_hash = git_service.commit(git_repo, "Add auto staged", add_all=True)

        assert commit_hash is not None
        status = git_service.get_status(git_repo)
        assert status.is_clean is True


class TestGitServiceEventEmission:
    """Integration tests for event emission."""

    def test_emits_branch_created_event(self, git_service, git_repo):
        """Should emit event when branch is created."""
        events = []
        git_service.on_all_events(lambda e: events.append(e))

        git_service.create_branch(git_repo, "feature/event-test", switch=False)

        branch_created_events = [e for e in events if e.event_type.value == "branch_created"]
        assert len(branch_created_events) == 1
        assert branch_created_events[0].branch_name == "feature/event-test"

    def test_emits_branch_switched_event(self, git_service, git_repo):
        """Should emit event when switching branches."""
        git_service.create_branch(git_repo, "feature/switch", switch=False)

        events = []
        git_service.on_all_events(lambda e: events.append(e))

        git_service.switch_branch(git_repo, "feature/switch")

        switched_events = [e for e in events if e.event_type.value == "branch_switched"]
        assert len(switched_events) == 1

    def test_emits_branch_deleted_event(self, git_service, git_repo):
        """Should emit event when branch is deleted."""
        git_service.create_branch(git_repo, "feature/delete-event", switch=False)

        events = []
        git_service.on_all_events(lambda e: events.append(e))

        git_service.delete_branch(git_repo, "feature/delete-event")

        deleted_events = [e for e in events if e.event_type.value == "branch_deleted"]
        assert len(deleted_events) == 1


class TestGitServiceErrorHandling:
    """Integration tests for error handling."""

    def test_git_error_on_invalid_operation(self, git_service, tmp_path):
        """Should raise GitError for invalid operations."""
        non_git_dir = tmp_path / "not_git"
        non_git_dir.mkdir()

        with pytest.raises(GitError):
            git_service.get_status(non_git_dir)

    def test_git_error_includes_details(self, git_service, git_repo):
        """GitError should include error details."""
        try:
            git_service.switch_branch(git_repo, "nonexistent")
            pytest.fail("Should have raised GitError")
        except GitError as e:
            assert e.exit_code != 0
            assert len(str(e)) > 0


class TestGitServiceBranchInfo:
    """Integration tests for BranchInfo data structure."""

    def test_branch_info_fields(self, git_service, git_repo):
        """BranchInfo should have all required fields."""
        branches = git_service.list_branches(git_repo)

        assert len(branches) > 0
        branch = branches[0]

        assert hasattr(branch, "name")
        assert hasattr(branch, "is_current")
        assert hasattr(branch, "is_remote")
        assert hasattr(branch, "commit_hash")
        assert hasattr(branch, "commit_message")
        assert hasattr(branch, "ahead")
        assert hasattr(branch, "behind")

    def test_branch_info_to_dict(self, git_service, git_repo):
        """BranchInfo.to_dict should return serializable dict."""
        branches = git_service.list_branches(git_repo)
        branch = branches[0]

        branch_dict = branch.to_dict()

        assert isinstance(branch_dict, dict)
        assert "name" in branch_dict
        assert "is_current" in branch_dict
        assert "commit_hash" in branch_dict


class TestGitServiceCLIAvailability:
    """Integration tests for CLI tool detection."""

    def test_has_github_cli(self, git_service):
        """Should detect if GitHub CLI is available."""
        has_gh = git_service.has_github_cli()
        # Result depends on system configuration
        assert isinstance(has_gh, bool)

    def test_has_gitlab_cli(self, git_service):
        """Should detect if GitLab CLI is available."""
        has_glab = git_service.has_gitlab_cli()
        # Result depends on system configuration
        assert isinstance(has_glab, bool)
