"""Unit tests for GitService.

Tests the git operations service including:
- Branch operations (list, create, switch, delete)
- Status and info operations
- PR creation (mocked)
- Event emission
"""

import json
import pytest
import subprocess
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock, call

from ralph_orchestrator.services.git_service import (
    GitService,
    GitEventType,
    BranchCreatedEvent,
    BranchSwitchedEvent,
    BranchDeletedEvent,
    PRCreatedEvent,
    CommitCreatedEvent,
    PushCompletedEvent,
    FetchCompletedEvent,
    GitErrorEvent,
    BranchInfo,
    PRInfo,
    GitStatus,
    GitError,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Project")
    subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
    )

    return repo_path


@pytest.fixture
def git_repo_with_remote(git_repo: Path, tmp_path: Path) -> Path:
    """Create a git repo with a fake remote."""
    # Create a bare remote repo
    remote_path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_path)], capture_output=True)

    # Add as remote
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote_path)],
        cwd=git_repo,
        capture_output=True,
    )

    return git_repo


class TestGitServiceStatus:
    """Tests for status and info operations."""

    def test_get_status(self, git_repo: Path):
        """Test getting repository status."""
        service = GitService()

        status = service.get_status(git_repo)

        assert status.branch in ["main", "master"]
        assert len(status.commit_hash) > 0
        assert status.is_clean is True
        assert status.staged == []
        assert status.unstaged == []
        assert status.untracked == []

    def test_get_status_with_changes(self, git_repo: Path):
        """Test status with uncommitted changes."""
        # Create untracked file
        (git_repo / "new_file.txt").write_text("content")

        # Modify tracked file
        (git_repo / "README.md").write_text("# Modified")

        service = GitService()
        status = service.get_status(git_repo)

        assert status.is_clean is False
        assert "new_file.txt" in status.untracked
        # Modified file should appear somewhere in the status
        all_changes = status.unstaged + status.staged
        assert len(all_changes) > 0 or "README.md" in status.unstaged

    def test_get_status_with_staged(self, git_repo: Path):
        """Test status with staged changes."""
        (git_repo / "staged.txt").write_text("staged content")
        subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, capture_output=True)

        service = GitService()
        status = service.get_status(git_repo)

        assert "staged.txt" in status.staged

    def test_get_current_branch(self, git_repo: Path):
        """Test getting current branch name."""
        service = GitService()

        branch = service.get_current_branch(git_repo)

        assert branch in ["main", "master"]

    def test_get_remote_url(self, git_repo_with_remote: Path, tmp_path: Path):
        """Test getting remote URL."""
        service = GitService()

        url = service.get_remote_url(git_repo_with_remote)

        assert url is not None
        assert "remote.git" in url

    def test_get_remote_url_not_found(self, git_repo: Path):
        """Test getting URL for non-existent remote."""
        service = GitService()

        url = service.get_remote_url(git_repo, remote="nonexistent")

        assert url is None

    def test_detect_forge_github(self, git_repo: Path):
        """Test detecting GitHub forge."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()
        forge = service.detect_forge(git_repo)

        assert forge == "github"

    def test_detect_forge_gitlab(self, git_repo: Path):
        """Test detecting GitLab forge."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitlab.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()
        forge = service.detect_forge(git_repo)

        assert forge == "gitlab"

    def test_detect_forge_unknown(self, git_repo: Path):
        """Test forge detection with unknown URL."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@bitbucket.org:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()
        forge = service.detect_forge(git_repo)

        assert forge is None

    def test_is_git_repo(self, git_repo: Path, tmp_path: Path):
        """Test checking if path is git repo."""
        service = GitService()

        assert service.is_git_repo(git_repo) is True
        assert service.is_git_repo(tmp_path) is False

    def test_is_clean(self, git_repo: Path):
        """Test checking if working tree is clean."""
        service = GitService()

        assert service.is_clean(git_repo) is True

        # Make it dirty
        (git_repo / "dirty.txt").write_text("dirty")

        assert service.is_clean(git_repo) is False


class TestGitServiceBranches:
    """Tests for branch operations."""

    def test_list_branches(self, git_repo: Path):
        """Test listing branches."""
        service = GitService()

        branches = service.list_branches(git_repo)

        assert len(branches) >= 1
        current_branches = [b for b in branches if b.is_current]
        assert len(current_branches) == 1

    def test_list_branches_multiple(self, git_repo: Path):
        """Test listing multiple branches."""
        # Create additional branches
        subprocess.run(
            ["git", "branch", "feature-1"],
            cwd=git_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "feature-2"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()
        branches = service.list_branches(git_repo)

        branch_names = [b.name for b in branches]
        assert "feature-1" in branch_names
        assert "feature-2" in branch_names

    def test_branch_exists(self, git_repo: Path):
        """Test checking if branch exists."""
        subprocess.run(
            ["git", "branch", "existing-branch"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()

        assert service.branch_exists(git_repo, "existing-branch") is True
        assert service.branch_exists(git_repo, "nonexistent") is False

    def test_create_branch(self, git_repo: Path):
        """Test creating a branch."""
        service = GitService()

        branch_info = service.create_branch(git_repo, "new-feature")

        assert branch_info.name == "new-feature"
        assert branch_info.is_current is True
        assert service.get_current_branch(git_repo) == "new-feature"

    def test_create_branch_no_switch(self, git_repo: Path):
        """Test creating branch without switching."""
        service = GitService()
        original_branch = service.get_current_branch(git_repo)

        branch_info = service.create_branch(git_repo, "side-branch", switch=False)

        assert branch_info.name == "side-branch"
        assert service.get_current_branch(git_repo) == original_branch

    def test_create_branch_from_base(self, git_repo: Path):
        """Test creating branch from specific base."""
        # Create a branch with a commit
        subprocess.run(["git", "checkout", "-b", "base-branch"], cwd=git_repo, capture_output=True)
        (git_repo / "base.txt").write_text("base content")
        subprocess.run(["git", "add", "base.txt"], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Base commit"], cwd=git_repo, capture_output=True)

        # Go back to main
        subprocess.run(["git", "checkout", "main"], cwd=git_repo, capture_output=True, check=False)
        subprocess.run(["git", "checkout", "master"], cwd=git_repo, capture_output=True, check=False)

        service = GitService()
        service.create_branch(git_repo, "from-base", base_branch="base-branch")

        # Should have the base.txt file
        assert (git_repo / "base.txt").exists()

    def test_create_branch_already_exists(self, git_repo: Path):
        """Test creating branch that already exists."""
        subprocess.run(["git", "branch", "existing"], cwd=git_repo, capture_output=True)

        service = GitService()

        with pytest.raises(GitError) as exc_info:
            service.create_branch(git_repo, "existing")

        assert "already exists" in str(exc_info.value)

    def test_create_branch_emits_event(self, git_repo: Path):
        """Test that branch creation emits events."""
        events = []

        def handler(event):
            events.append(event)

        service = GitService()
        service.on_all_events(handler)
        service.create_branch(git_repo, "event-test")

        event_types = [e.event_type for e in events]
        assert GitEventType.BRANCH_CREATED in event_types
        assert GitEventType.BRANCH_SWITCHED in event_types

    def test_switch_branch(self, git_repo: Path):
        """Test switching branches."""
        subprocess.run(["git", "branch", "other-branch"], cwd=git_repo, capture_output=True)

        service = GitService()
        service.switch_branch(git_repo, "other-branch")

        assert service.get_current_branch(git_repo) == "other-branch"

    def test_switch_branch_emits_event(self, git_repo: Path):
        """Test that switching emits event."""
        subprocess.run(["git", "branch", "switch-target"], cwd=git_repo, capture_output=True)

        events: List[BranchSwitchedEvent] = []

        def handler(event):
            if isinstance(event, BranchSwitchedEvent):
                events.append(event)

        service = GitService()
        service.on_event(GitEventType.BRANCH_SWITCHED, handler)
        service.switch_branch(git_repo, "switch-target")

        assert len(events) == 1
        assert events[0].to_branch == "switch-target"

    def test_delete_branch(self, git_repo: Path):
        """Test deleting a branch."""
        subprocess.run(["git", "branch", "to-delete"], cwd=git_repo, capture_output=True)

        service = GitService()
        service.delete_branch(git_repo, "to-delete")

        assert service.branch_exists(git_repo, "to-delete") is False

    def test_delete_branch_force(self, git_repo: Path):
        """Test force deleting unmerged branch."""
        # Create branch with unmerged commit
        subprocess.run(["git", "checkout", "-b", "unmerged"], cwd=git_repo, capture_output=True)
        (git_repo / "unmerged.txt").write_text("content")
        subprocess.run(["git", "add", "unmerged.txt"], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Unmerged"], cwd=git_repo, capture_output=True)

        # Switch back
        subprocess.run(["git", "checkout", "main"], cwd=git_repo, capture_output=True, check=False)
        subprocess.run(["git", "checkout", "master"], cwd=git_repo, capture_output=True, check=False)

        service = GitService()
        service.delete_branch(git_repo, "unmerged", force=True)

        assert service.branch_exists(git_repo, "unmerged") is False


class TestGitServiceCommit:
    """Tests for commit operations."""

    def test_commit(self, git_repo: Path):
        """Test creating a commit."""
        (git_repo / "new_file.txt").write_text("content")
        subprocess.run(["git", "add", "new_file.txt"], cwd=git_repo, capture_output=True)

        service = GitService()
        commit_hash = service.commit(git_repo, "Test commit message")

        assert len(commit_hash) > 0

        # Verify commit was created
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "Test commit message" in result.stdout

    def test_commit_with_add_all(self, git_repo: Path):
        """Test commit with add_all flag."""
        (git_repo / "auto_add.txt").write_text("content")

        service = GitService()
        commit_hash = service.commit(git_repo, "Auto add commit", add_all=True)

        assert len(commit_hash) > 0

    def test_commit_emits_event(self, git_repo: Path):
        """Test that commit emits event."""
        (git_repo / "event_file.txt").write_text("content")
        subprocess.run(["git", "add", "event_file.txt"], cwd=git_repo, capture_output=True)

        events: List[CommitCreatedEvent] = []

        def handler(event):
            if isinstance(event, CommitCreatedEvent):
                events.append(event)

        service = GitService()
        service.on_event(GitEventType.COMMIT_CREATED, handler)
        service.commit(git_repo, "Event test commit")

        assert len(events) == 1
        assert events[0].message == "Event test commit"


class TestGitServiceRemote:
    """Tests for remote operations."""

    def test_fetch(self, git_repo_with_remote: Path):
        """Test fetching from remote."""
        # First push something
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=git_repo_with_remote,
            capture_output=True,
        )

        service = GitService()
        service.fetch(git_repo_with_remote)

        # Should not raise

    def test_fetch_emits_event(self, git_repo_with_remote: Path):
        """Test that fetch emits event."""
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=git_repo_with_remote,
            capture_output=True,
        )

        events: List[FetchCompletedEvent] = []

        def handler(event):
            if isinstance(event, FetchCompletedEvent):
                events.append(event)

        service = GitService()
        service.on_event(GitEventType.FETCH_COMPLETED, handler)
        service.fetch(git_repo_with_remote)

        assert len(events) == 1
        assert events[0].remote == "origin"

    def test_push(self, git_repo_with_remote: Path):
        """Test pushing to remote."""
        service = GitService()

        # Push should work (empty push, but should not error)
        service.push(git_repo_with_remote, set_upstream=True)

    def test_push_emits_event(self, git_repo_with_remote: Path):
        """Test that push emits event."""
        events: List[PushCompletedEvent] = []

        def handler(event):
            if isinstance(event, PushCompletedEvent):
                events.append(event)

        service = GitService()
        service.on_event(GitEventType.PUSH_COMPLETED, handler)
        service.push(git_repo_with_remote, set_upstream=True)

        assert len(events) == 1


class TestGitServicePR:
    """Tests for PR operations (mocked)."""

    def test_create_pr_github(self, git_repo: Path):
        """Test creating GitHub PR (mocked)."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()

        with patch.object(service, "_run_cli") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="https://github.com/user/repo/pull/42\n",
                returncode=0,
            )

            pr = service.create_pr(
                git_repo,
                title="Test PR",
                body="PR description",
            )

            assert pr.number == 42
            assert "github.com" in pr.url
            assert pr.title == "Test PR"

    def test_create_pr_gitlab(self, git_repo: Path):
        """Test creating GitLab MR (mocked)."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@gitlab.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()

        with patch.object(service, "_run_cli") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="https://gitlab.com/user/repo/-/merge_requests/123\n",
                returncode=0,
            )

            pr = service.create_pr(
                git_repo,
                title="Test MR",
                body="MR description",
            )

            assert pr.number == 123
            assert "gitlab.com" in pr.url

    def test_create_pr_emits_event(self, git_repo: Path):
        """Test that PR creation emits event."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        events: List[PRCreatedEvent] = []

        def handler(event):
            if isinstance(event, PRCreatedEvent):
                events.append(event)

        service = GitService()
        service.on_event(GitEventType.PR_CREATED, handler)

        with patch.object(service, "_run_cli") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="https://github.com/user/repo/pull/42\n",
                returncode=0,
            )

            service.create_pr(git_repo, title="Event Test", body="")

        assert len(events) == 1
        assert events[0].pr_number == 42

    def test_create_pr_with_template(self, git_repo: Path):
        """Test PR creation with template variables."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()

        with patch.object(service, "_run_cli") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="https://github.com/user/repo/pull/42\n",
                returncode=0,
            )

            pr = service.create_pr_from_template(
                git_repo,
                title_template="Ralph: {priority_item}",
                body_template="## Summary\n{description}",
                variables={
                    "priority_item": "Add new feature",
                    "description": "This adds a cool feature",
                },
            )

            # Verify the call was made with substituted values
            call_args = mock_run.call_args
            assert "Ralph: Add new feature" in str(call_args)

    def test_create_pr_no_forge(self, git_repo: Path):
        """Test PR creation fails without forge detection."""
        service = GitService()

        with pytest.raises(GitError) as exc_info:
            service.create_pr(git_repo, title="Test", body="")

        assert "forge" in str(exc_info.value).lower()

    def test_get_pr_github(self, git_repo: Path):
        """Test getting GitHub PR info (mocked)."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()

        pr_data = {
            "number": 42,
            "url": "https://github.com/user/repo/pull/42",
            "title": "Test PR",
            "body": "Description",
            "state": "OPEN",
            "baseRefName": "main",
            "headRefName": "feature",
            "author": {"login": "user"},
            "createdAt": "2026-01-27T00:00:00Z",
            "updatedAt": "2026-01-27T00:00:00Z",
            "isDraft": False,
            "labels": [{"name": "bug"}],
        }

        with patch.object(service, "_run_cli") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(pr_data),
                returncode=0,
            )

            pr = service.get_pr(git_repo, pr_number=42)

            assert pr is not None
            assert pr.number == 42
            assert pr.title == "Test PR"
            assert pr.author == "user"

    def test_list_prs_github(self, git_repo: Path):
        """Test listing GitHub PRs (mocked)."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            capture_output=True,
        )

        service = GitService()

        pr_list = [
            {
                "number": 1,
                "url": "https://github.com/user/repo/pull/1",
                "title": "PR 1",
                "state": "OPEN",
                "baseRefName": "main",
                "headRefName": "feature-1",
                "author": {"login": "user1"},
                "createdAt": "2026-01-27T00:00:00Z",
                "isDraft": False,
            },
            {
                "number": 2,
                "url": "https://github.com/user/repo/pull/2",
                "title": "PR 2",
                "state": "OPEN",
                "baseRefName": "main",
                "headRefName": "feature-2",
                "author": {"login": "user2"},
                "createdAt": "2026-01-26T00:00:00Z",
                "isDraft": True,
            },
        ]

        with patch.object(service, "_run_cli") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=json.dumps(pr_list),
                returncode=0,
            )

            prs = service.list_prs(git_repo)

            assert len(prs) == 2
            assert prs[0].number == 1
            assert prs[1].draft is True


class TestGitServiceEvents:
    """Tests for event handling."""

    def test_on_all_events(self, git_repo: Path):
        """Test global event handler."""
        events = []

        def handler(event):
            events.append(event)

        service = GitService()
        service.on_all_events(handler)
        service.create_branch(git_repo, "all-events-test")

        assert len(events) >= 2  # Created and switched

    def test_remove_handler(self, git_repo: Path):
        """Test removing event handler."""
        events = []

        def handler(event):
            events.append(event)

        service = GitService()
        service.on_event(GitEventType.BRANCH_CREATED, handler)
        service.remove_handler(GitEventType.BRANCH_CREATED, handler)
        service.create_branch(git_repo, "remove-handler-test")

        created_events = [e for e in events if e.event_type == GitEventType.BRANCH_CREATED]
        assert len(created_events) == 0

    def test_error_event(self, git_repo: Path):
        """Test that errors emit error events."""
        events: List[GitErrorEvent] = []

        def handler(event):
            if isinstance(event, GitErrorEvent):
                events.append(event)

        service = GitService()
        service.on_event(GitEventType.GIT_ERROR, handler)

        try:
            service.switch_branch(git_repo, "nonexistent-branch")
        except GitError:
            pass

        assert len(events) == 1
        assert events[0].operation == "checkout nonexistent-branch"


class TestGitServiceCLIDetection:
    """Tests for CLI detection."""

    def test_has_github_cli(self):
        """Test GitHub CLI detection."""
        service = GitService()

        # Just test it doesn't crash
        result = service.has_github_cli()
        assert isinstance(result, bool)

    def test_has_gitlab_cli(self):
        """Test GitLab CLI detection."""
        service = GitService()

        result = service.has_gitlab_cli()
        assert isinstance(result, bool)


class TestGitServiceDataclasses:
    """Tests for dataclass serialization."""

    def test_branch_info_to_dict(self):
        """Test BranchInfo serialization."""
        info = BranchInfo(
            name="feature",
            is_current=True,
            is_remote=False,
            tracking="origin/feature",
            commit_hash="abc123",
            commit_message="Test commit",
            ahead=2,
            behind=1,
        )

        d = info.to_dict()

        assert d["name"] == "feature"
        assert d["is_current"] is True
        assert d["tracking"] == "origin/feature"
        assert d["ahead"] == 2

    def test_pr_info_to_dict(self):
        """Test PRInfo serialization."""
        info = PRInfo(
            number=42,
            url="https://github.com/user/repo/pull/42",
            title="Test PR",
            body="Description",
            state="open",
            base_branch="main",
            head_branch="feature",
            author="user",
            created_at="2026-01-27T00:00:00Z",
            updated_at="2026-01-27T01:00:00Z",
            draft=False,
            labels=["bug", "enhancement"],
        )

        d = info.to_dict()

        assert d["number"] == 42
        assert d["author"] == "user"
        assert len(d["labels"]) == 2

    def test_git_status_to_dict(self):
        """Test GitStatus serialization."""
        status = GitStatus(
            branch="main",
            commit_hash="abc123",
            staged=["file1.txt"],
            unstaged=["file2.txt"],
            untracked=["file3.txt"],
            is_clean=False,
            ahead=1,
            behind=0,
        )

        d = status.to_dict()

        assert d["branch"] == "main"
        assert d["is_clean"] is False
        assert len(d["staged"]) == 1

    def test_branch_created_event_to_dict(self):
        """Test BranchCreatedEvent serialization."""
        event = BranchCreatedEvent(
            project_path="/path/to/project",
            branch_name="feature",
            base_branch="main",
        )

        d = event.to_dict()

        assert d["event_type"] == "branch_created"
        assert d["branch_name"] == "feature"
        assert d["base_branch"] == "main"

    def test_pr_created_event_to_dict(self):
        """Test PRCreatedEvent serialization."""
        event = PRCreatedEvent(
            project_path="/path",
            pr_number=42,
            pr_url="https://github.com/user/repo/pull/42",
            title="Test",
            base_branch="main",
            head_branch="feature",
        )

        d = event.to_dict()

        assert d["event_type"] == "pr_created"
        assert d["pr_number"] == 42


class TestGitServiceEdgeCases:
    """Tests for edge cases."""

    def test_not_a_git_repo(self, tmp_path: Path):
        """Test operations on non-git directory."""
        service = GitService()

        with pytest.raises(GitError):
            service.get_status(tmp_path)

    def test_timeout_handling(self, git_repo: Path):
        """Test command timeout handling."""
        service = GitService(timeout=1)

        # Normal operation should work
        status = service.get_status(git_repo)
        assert status is not None

    def test_switch_to_current_branch(self, git_repo: Path):
        """Test switching to current branch is a no-op."""
        service = GitService()
        current = service.get_current_branch(git_repo)

        # Should not raise or do anything
        service.switch_branch(git_repo, current)

        assert service.get_current_branch(git_repo) == current

    def test_pull(self, git_repo_with_remote: Path):
        """Test pull operation."""
        # First push
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=git_repo_with_remote,
            capture_output=True,
        )

        service = GitService()

        # Should not raise
        service.pull(git_repo_with_remote)

    def test_pull_with_rebase(self, git_repo_with_remote: Path):
        """Test pull with rebase."""
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=git_repo_with_remote,
            capture_output=True,
        )

        service = GitService()

        # Should not raise
        service.pull(git_repo_with_remote, rebase=True)
