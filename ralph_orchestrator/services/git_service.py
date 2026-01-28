"""Git operations service.

This module provides the GitService class for managing git operations including
branch management and PR creation via GitHub/GitLab APIs.

Features:
- Branch operations (list, create, switch, delete)
- PR creation with template-based descriptions
- Support for GitHub (gh CLI) and GitLab (glab CLI)
- Secure credential handling via CLI tools
- Event emission for git state changes
- CLI-agnostic interface for both CLI and API usage
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class GitEventType(str, Enum):
    """Types of events emitted by the git service."""
    BRANCH_CREATED = "branch_created"
    BRANCH_SWITCHED = "branch_switched"
    BRANCH_DELETED = "branch_deleted"
    PR_CREATED = "pr_created"
    PR_UPDATED = "pr_updated"
    COMMIT_CREATED = "commit_created"
    PUSH_COMPLETED = "push_completed"
    FETCH_COMPLETED = "fetch_completed"
    GIT_ERROR = "git_error"


@dataclass
class GitEvent:
    """Base class for git events."""
    event_type: GitEventType
    timestamp: float = field(default_factory=time.time)
    project_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "project_path": self.project_path,
        }


@dataclass
class BranchCreatedEvent(GitEvent):
    """Event emitted when a branch is created."""
    event_type: GitEventType = field(init=False, default=GitEventType.BRANCH_CREATED)
    branch_name: str = ""
    base_branch: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "branch_name": self.branch_name,
            "base_branch": self.base_branch,
        })
        return d


@dataclass
class BranchSwitchedEvent(GitEvent):
    """Event emitted when switching branches."""
    event_type: GitEventType = field(init=False, default=GitEventType.BRANCH_SWITCHED)
    from_branch: str = ""
    to_branch: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "from_branch": self.from_branch,
            "to_branch": self.to_branch,
        })
        return d


@dataclass
class BranchDeletedEvent(GitEvent):
    """Event emitted when a branch is deleted."""
    event_type: GitEventType = field(init=False, default=GitEventType.BRANCH_DELETED)
    branch_name: str = ""
    was_remote: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "branch_name": self.branch_name,
            "was_remote": self.was_remote,
        })
        return d


@dataclass
class PRCreatedEvent(GitEvent):
    """Event emitted when a PR is created."""
    event_type: GitEventType = field(init=False, default=GitEventType.PR_CREATED)
    pr_number: int = 0
    pr_url: str = ""
    title: str = ""
    base_branch: str = ""
    head_branch: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "title": self.title,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
        })
        return d


@dataclass
class PRUpdatedEvent(GitEvent):
    """Event emitted when a PR is updated."""
    event_type: GitEventType = field(init=False, default=GitEventType.PR_UPDATED)
    pr_number: int = 0
    pr_url: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "changes": self.changes,
        })
        return d


@dataclass
class CommitCreatedEvent(GitEvent):
    """Event emitted when a commit is created."""
    event_type: GitEventType = field(init=False, default=GitEventType.COMMIT_CREATED)
    commit_hash: str = ""
    message: str = ""
    files_changed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "commit_hash": self.commit_hash,
            "message": self.message,
            "files_changed": self.files_changed,
        })
        return d


@dataclass
class PushCompletedEvent(GitEvent):
    """Event emitted when push completes."""
    event_type: GitEventType = field(init=False, default=GitEventType.PUSH_COMPLETED)
    branch: str = ""
    remote: str = ""
    commits_pushed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "branch": self.branch,
            "remote": self.remote,
            "commits_pushed": self.commits_pushed,
        })
        return d


@dataclass
class FetchCompletedEvent(GitEvent):
    """Event emitted when fetch completes."""
    event_type: GitEventType = field(init=False, default=GitEventType.FETCH_COMPLETED)
    remote: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "remote": self.remote,
        })
        return d


@dataclass
class GitErrorEvent(GitEvent):
    """Event emitted when a git error occurs."""
    event_type: GitEventType = field(init=False, default=GitEventType.GIT_ERROR)
    operation: str = ""
    error: str = ""
    exit_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "operation": self.operation,
            "error": self.error,
            "exit_code": self.exit_code,
        })
        return d


# Type alias for event handlers
GitEventHandler = Callable[[Any], None]


@dataclass
class BranchInfo:
    """Information about a git branch."""
    name: str
    is_current: bool = False
    is_remote: bool = False
    tracking: Optional[str] = None
    commit_hash: Optional[str] = None
    commit_message: Optional[str] = None
    ahead: int = 0
    behind: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "is_current": self.is_current,
            "is_remote": self.is_remote,
            "tracking": self.tracking,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "ahead": self.ahead,
            "behind": self.behind,
        }


@dataclass
class PRInfo:
    """Information about a pull request."""
    number: int
    url: str
    title: str
    body: str
    state: str  # open, closed, merged
    base_branch: str
    head_branch: str
    author: str
    created_at: str
    updated_at: str
    draft: bool = False
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "number": self.number,
            "url": self.url,
            "title": self.title,
            "body": self.body,
            "state": self.state,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "draft": self.draft,
            "labels": self.labels,
        }


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str
    commit_hash: str
    staged: List[str]
    unstaged: List[str]
    untracked: List[str]
    is_clean: bool
    ahead: int = 0
    behind: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "branch": self.branch,
            "commit_hash": self.commit_hash,
            "staged": self.staged,
            "unstaged": self.unstaged,
            "untracked": self.untracked,
            "is_clean": self.is_clean,
            "ahead": self.ahead,
            "behind": self.behind,
        }


class GitError(Exception):
    """Raised when a git operation fails."""

    def __init__(self, message: str, exit_code: int = 1, output: str = ""):
        self.exit_code = exit_code
        self.output = output
        super().__init__(message)


class GitService:
    """Service for git operations.

    This service provides branch management and PR creation capabilities,
    supporting both GitHub (gh CLI) and GitLab (glab CLI) for remote operations.
    All credentials are handled securely through the CLI tools.

    Usage:
        service = GitService()

        # Register event handlers
        service.on_event(GitEventType.BRANCH_CREATED, my_handler)

        # List branches
        branches = service.list_branches(Path("/path/to/project"))

        # Create and switch to a new branch
        service.create_branch(
            Path("/path/to/project"),
            "feature/my-feature",
            base_branch="main",
        )

        # Create a PR
        pr = service.create_pr(
            Path("/path/to/project"),
            title="My Feature",
            body="Description of changes",
        )
    """

    def __init__(
        self,
        github_cli: str = "gh",
        gitlab_cli: str = "glab",
        timeout: int = 60,
    ):
        """Initialize the git service.

        Args:
            github_cli: Path or name of GitHub CLI (gh).
            gitlab_cli: Path or name of GitLab CLI (glab).
            timeout: Default timeout for git operations in seconds.
        """
        self.github_cli = github_cli
        self.gitlab_cli = gitlab_cli
        self.timeout = timeout

        # Event handlers
        self._event_handlers: Dict[GitEventType, List[GitEventHandler]] = {
            event_type: [] for event_type in GitEventType
        }
        self._global_handlers: List[GitEventHandler] = []

    def on_event(self, event_type: GitEventType, handler: GitEventHandler) -> None:
        """Register an event handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: Callable that receives the event.
        """
        self._event_handlers[event_type].append(handler)

    def on_all_events(self, handler: GitEventHandler) -> None:
        """Register a handler for all events.

        Args:
            handler: Callable that receives any event.
        """
        self._global_handlers.append(handler)

    def remove_handler(self, event_type: GitEventType, handler: GitEventHandler) -> None:
        """Remove an event handler.

        Args:
            event_type: The type of event.
            handler: The handler to remove.
        """
        if handler in self._event_handlers[event_type]:
            self._event_handlers[event_type].remove(handler)

    def _emit_event(self, event: GitEvent) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: The event to emit.
        """
        # Call specific handlers
        for handler in self._event_handlers[event.event_type]:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors break the service

        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                pass

    def _get_path_key(self, project_path: Path | str) -> str:
        """Get normalized path key."""
        return str(Path(project_path).resolve())

    def _run_git(
        self,
        project_path: Path | str,
        args: List[str],
        timeout: Optional[int] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a git command.

        Args:
            project_path: Path to the project directory.
            args: Git command arguments.
            timeout: Timeout in seconds.
            check: If True, raise on non-zero exit.

        Returns:
            CompletedProcess instance.

        Raises:
            GitError: If check is True and command fails.
        """
        path_key = self._get_path_key(project_path)
        cmd = ["git"] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                cwd=project_path,
            )

            if check and result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                self._emit_event(GitErrorEvent(
                    project_path=path_key,
                    operation=" ".join(args[:2]),
                    error=error_msg,
                    exit_code=result.returncode,
                ))
                raise GitError(
                    f"Git command failed: {error_msg}",
                    exit_code=result.returncode,
                    output=result.stdout,
                )

            return result

        except subprocess.TimeoutExpired as e:
            self._emit_event(GitErrorEvent(
                project_path=path_key,
                operation=" ".join(args[:2]),
                error="Operation timed out",
                exit_code=-1,
            ))
            raise GitError(f"Git command timed out: {' '.join(args)}") from e

    def _run_cli(
        self,
        project_path: Path | str,
        cli: str,
        args: List[str],
        timeout: Optional[int] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a CLI command (gh or glab).

        Args:
            project_path: Path to the project directory.
            cli: CLI command (gh or glab).
            args: CLI arguments.
            timeout: Timeout in seconds.
            check: If True, raise on non-zero exit.

        Returns:
            CompletedProcess instance.

        Raises:
            GitError: If check is True and command fails.
        """
        path_key = self._get_path_key(project_path)
        cmd = [cli] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                cwd=project_path,
            )

            if check and result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                self._emit_event(GitErrorEvent(
                    project_path=path_key,
                    operation=f"{cli} " + " ".join(args[:2]),
                    error=error_msg,
                    exit_code=result.returncode,
                ))
                raise GitError(
                    f"{cli} command failed: {error_msg}",
                    exit_code=result.returncode,
                    output=result.stdout,
                )

            return result

        except FileNotFoundError:
            raise GitError(f"{cli} CLI not found. Please install it first.")
        except subprocess.TimeoutExpired as e:
            self._emit_event(GitErrorEvent(
                project_path=path_key,
                operation=f"{cli} " + " ".join(args[:2]),
                error="Operation timed out",
                exit_code=-1,
            ))
            raise GitError(f"{cli} command timed out: {' '.join(args)}") from e

    # =========================================================================
    # Status and info
    # =========================================================================

    def get_status(self, project_path: Path | str) -> GitStatus:
        """Get git repository status.

        Args:
            project_path: Path to the project directory.

        Returns:
            GitStatus instance.
        """
        # Get current branch
        branch_result = self._run_git(project_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_result.stdout.strip()

        # Get commit hash
        hash_result = self._run_git(project_path, ["rev-parse", "HEAD"])
        commit_hash = hash_result.stdout.strip()[:12]

        # Get status
        status_result = self._run_git(project_path, ["status", "--porcelain"])
        # Use splitlines() to avoid stripping leading spaces from git status output
        # (e.g., " M filename" where leading space indicates not staged)
        lines = status_result.stdout.splitlines() if status_result.stdout else []

        staged = []
        unstaged = []
        untracked = []

        for line in lines:
            if len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            filename = line[3:]

            if index_status in "MADRCU":
                staged.append(filename)
            if worktree_status in "MADRU":
                unstaged.append(filename)
            if index_status == "?" and worktree_status == "?":
                untracked.append(filename)

        # Get ahead/behind counts
        ahead = 0
        behind = 0
        try:
            tracking_result = self._run_git(
                project_path,
                ["rev-list", "--left-right", "--count", f"HEAD...@{{u}}"],
                check=False,
            )
            if tracking_result.returncode == 0:
                parts = tracking_result.stdout.strip().split()
                if len(parts) == 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
        except Exception:
            pass

        is_clean = not staged and not unstaged and not untracked

        return GitStatus(
            branch=branch,
            commit_hash=commit_hash,
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            is_clean=is_clean,
            ahead=ahead,
            behind=behind,
        )

    def get_current_branch(self, project_path: Path | str) -> str:
        """Get the current branch name.

        Args:
            project_path: Path to the project directory.

        Returns:
            Current branch name.
        """
        result = self._run_git(project_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def get_remote_url(
        self,
        project_path: Path | str,
        remote: str = "origin",
    ) -> Optional[str]:
        """Get the URL for a remote.

        Args:
            project_path: Path to the project directory.
            remote: Remote name.

        Returns:
            Remote URL if exists, None otherwise.
        """
        result = self._run_git(
            project_path,
            ["remote", "get-url", remote],
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def detect_forge(self, project_path: Path | str) -> Optional[str]:
        """Detect the git forge (GitHub or GitLab).

        Args:
            project_path: Path to the project directory.

        Returns:
            "github", "gitlab", or None if unknown.
        """
        url = self.get_remote_url(project_path)
        if not url:
            return None

        if "github.com" in url or "github:" in url:
            return "github"
        elif "gitlab.com" in url or "gitlab:" in url:
            return "gitlab"

        return None

    # =========================================================================
    # Branch operations
    # =========================================================================

    def list_branches(
        self,
        project_path: Path | str,
        include_remote: bool = False,
    ) -> List[BranchInfo]:
        """List git branches.

        Args:
            project_path: Path to the project directory.
            include_remote: If True, include remote branches.

        Returns:
            List of BranchInfo instances.
        """
        args = ["branch", "-v"]
        if include_remote:
            args.append("-a")

        result = self._run_git(project_path, args)

        branches = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            is_current = line.startswith("*")
            line = line.lstrip("* ")

            # Parse branch info
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue

            name = parts[0]
            commit_hash = parts[1] if len(parts) > 1 else None
            commit_message = parts[2] if len(parts) > 2 else None

            # Check if remote branch
            is_remote = name.startswith("remotes/")
            if is_remote:
                name = name.replace("remotes/", "", 1)

            branches.append(BranchInfo(
                name=name,
                is_current=is_current,
                is_remote=is_remote,
                commit_hash=commit_hash,
                commit_message=commit_message,
            ))

        return branches

    def branch_exists(
        self,
        project_path: Path | str,
        branch_name: str,
        check_remote: bool = False,
    ) -> bool:
        """Check if a branch exists.

        Args:
            project_path: Path to the project directory.
            branch_name: Branch name to check.
            check_remote: If True, also check remote branches.

        Returns:
            True if branch exists.
        """
        # Check local
        result = self._run_git(
            project_path,
            ["rev-parse", "--verify", branch_name],
            check=False,
        )
        if result.returncode == 0:
            return True

        # Check remote
        if check_remote:
            result = self._run_git(
                project_path,
                ["rev-parse", "--verify", f"origin/{branch_name}"],
                check=False,
            )
            return result.returncode == 0

        return False

    def create_branch(
        self,
        project_path: Path | str,
        branch_name: str,
        base_branch: Optional[str] = None,
        switch: bool = True,
    ) -> BranchInfo:
        """Create a new branch.

        Args:
            project_path: Path to the project directory.
            branch_name: Name for the new branch.
            base_branch: Base branch to create from (default: current).
            switch: If True, switch to the new branch.

        Returns:
            BranchInfo for the created branch.

        Raises:
            GitError: If branch already exists or creation fails.
        """
        path_key = self._get_path_key(project_path)

        if self.branch_exists(project_path, branch_name):
            raise GitError(f"Branch already exists: {branch_name}")

        # Get current branch for event
        current_branch = self.get_current_branch(project_path)
        actual_base = base_branch or current_branch

        # Create branch
        if switch:
            args = ["checkout", "-b", branch_name]
            if base_branch:
                args.append(base_branch)
        else:
            args = ["branch", branch_name]
            if base_branch:
                args.append(base_branch)

        self._run_git(project_path, args)

        # Emit event
        self._emit_event(BranchCreatedEvent(
            project_path=path_key,
            branch_name=branch_name,
            base_branch=actual_base,
        ))

        if switch:
            self._emit_event(BranchSwitchedEvent(
                project_path=path_key,
                from_branch=current_branch,
                to_branch=branch_name,
            ))

        # Get branch info
        result = self._run_git(project_path, ["rev-parse", "HEAD"])
        commit_hash = result.stdout.strip()[:12]

        return BranchInfo(
            name=branch_name,
            is_current=switch,
            commit_hash=commit_hash,
        )

    def switch_branch(
        self,
        project_path: Path | str,
        branch_name: str,
        create: bool = False,
    ) -> None:
        """Switch to a branch.

        Args:
            project_path: Path to the project directory.
            branch_name: Branch to switch to.
            create: If True, create the branch if it doesn't exist.

        Raises:
            GitError: If branch doesn't exist and create is False.
        """
        path_key = self._get_path_key(project_path)
        current_branch = self.get_current_branch(project_path)

        if current_branch == branch_name:
            return  # Already on this branch

        if create:
            args = ["checkout", "-B", branch_name]
        else:
            args = ["checkout", branch_name]

        self._run_git(project_path, args)

        # Emit event
        self._emit_event(BranchSwitchedEvent(
            project_path=path_key,
            from_branch=current_branch,
            to_branch=branch_name,
        ))

    def delete_branch(
        self,
        project_path: Path | str,
        branch_name: str,
        force: bool = False,
        delete_remote: bool = False,
        remote: str = "origin",
    ) -> None:
        """Delete a branch.

        Args:
            project_path: Path to the project directory.
            branch_name: Branch to delete.
            force: If True, force delete even if not merged.
            delete_remote: If True, also delete from remote.
            remote: Remote name.

        Raises:
            GitError: If deletion fails.
        """
        path_key = self._get_path_key(project_path)

        # Delete local
        args = ["branch", "-D" if force else "-d", branch_name]
        self._run_git(project_path, args)

        # Emit local delete event
        self._emit_event(BranchDeletedEvent(
            project_path=path_key,
            branch_name=branch_name,
            was_remote=False,
        ))

        # Delete remote
        if delete_remote:
            self._run_git(project_path, ["push", remote, "--delete", branch_name])

            self._emit_event(BranchDeletedEvent(
                project_path=path_key,
                branch_name=branch_name,
                was_remote=True,
            ))

    # =========================================================================
    # Remote operations
    # =========================================================================

    def fetch(
        self,
        project_path: Path | str,
        remote: str = "origin",
        prune: bool = True,
    ) -> None:
        """Fetch from remote.

        Args:
            project_path: Path to the project directory.
            remote: Remote to fetch from.
            prune: If True, prune deleted remote branches.
        """
        path_key = self._get_path_key(project_path)

        args = ["fetch", remote]
        if prune:
            args.append("--prune")

        self._run_git(project_path, args)

        self._emit_event(FetchCompletedEvent(
            project_path=path_key,
            remote=remote,
        ))

    def push(
        self,
        project_path: Path | str,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
        force: bool = False,
    ) -> None:
        """Push to remote.

        Args:
            project_path: Path to the project directory.
            remote: Remote to push to.
            branch: Branch to push (default: current).
            set_upstream: If True, set upstream tracking.
            force: If True, force push.
        """
        path_key = self._get_path_key(project_path)

        current_branch = self.get_current_branch(project_path)
        target_branch = branch or current_branch

        args = ["push", remote, target_branch]
        if set_upstream:
            args.insert(1, "-u")
        if force:
            args.insert(1, "--force-with-lease")

        self._run_git(project_path, args)

        self._emit_event(PushCompletedEvent(
            project_path=path_key,
            branch=target_branch,
            remote=remote,
        ))

    def pull(
        self,
        project_path: Path | str,
        remote: str = "origin",
        branch: Optional[str] = None,
        rebase: bool = False,
    ) -> None:
        """Pull from remote.

        Args:
            project_path: Path to the project directory.
            remote: Remote to pull from.
            branch: Branch to pull (default: current).
            rebase: If True, rebase instead of merge.
        """
        current_branch = self.get_current_branch(project_path)
        target_branch = branch or current_branch

        args = ["pull"]
        if rebase:
            args.append("--rebase")
        args.extend([remote, target_branch])

        self._run_git(project_path, args)

    # =========================================================================
    # Commit operations
    # =========================================================================

    def commit(
        self,
        project_path: Path | str,
        message: str,
        add_all: bool = False,
    ) -> str:
        """Create a commit.

        Args:
            project_path: Path to the project directory.
            message: Commit message.
            add_all: If True, stage all changes first.

        Returns:
            Commit hash.

        Raises:
            GitError: If nothing to commit or commit fails.
        """
        path_key = self._get_path_key(project_path)

        if add_all:
            self._run_git(project_path, ["add", "-A"])

        result = self._run_git(project_path, ["commit", "-m", message])

        # Get commit hash
        hash_result = self._run_git(project_path, ["rev-parse", "HEAD"])
        commit_hash = hash_result.stdout.strip()[:12]

        # Get files changed count
        files_changed = 0
        stat_result = self._run_git(
            project_path,
            ["diff", "--stat", "HEAD~1", "HEAD"],
            check=False,
        )
        if stat_result.returncode == 0:
            lines = stat_result.stdout.strip().split("\n")
            if lines:
                last_line = lines[-1]
                match = re.search(r"(\d+) files? changed", last_line)
                if match:
                    files_changed = int(match.group(1))

        self._emit_event(CommitCreatedEvent(
            project_path=path_key,
            commit_hash=commit_hash,
            message=message,
            files_changed=files_changed,
        ))

        return commit_hash

    # =========================================================================
    # PR operations
    # =========================================================================

    def create_pr(
        self,
        project_path: Path | str,
        title: str,
        body: str = "",
        base_branch: Optional[str] = None,
        head_branch: Optional[str] = None,
        draft: bool = False,
        labels: Optional[List[str]] = None,
        template_vars: Optional[Dict[str, str]] = None,
    ) -> PRInfo:
        """Create a pull request.

        Uses gh CLI for GitHub or glab CLI for GitLab.

        Args:
            project_path: Path to the project directory.
            title: PR title.
            body: PR body/description.
            base_branch: Target branch (default: main/master).
            head_branch: Source branch (default: current).
            draft: If True, create as draft.
            labels: Labels to add.
            template_vars: Variables for template substitution in body.

        Returns:
            PRInfo for the created PR.

        Raises:
            GitError: If PR creation fails.
        """
        path_key = self._get_path_key(project_path)
        forge = self.detect_forge(project_path)

        if not forge:
            raise GitError("Could not detect forge (GitHub/GitLab) from remote URL")

        current_branch = self.get_current_branch(project_path)
        head = head_branch or current_branch

        # Apply template variables
        if template_vars:
            for key, value in template_vars.items():
                body = body.replace(f"{{{key}}}", value)

        if forge == "github":
            return self._create_github_pr(
                project_path,
                title=title,
                body=body,
                base_branch=base_branch,
                head_branch=head,
                draft=draft,
                labels=labels,
            )
        elif forge == "gitlab":
            return self._create_gitlab_pr(
                project_path,
                title=title,
                body=body,
                base_branch=base_branch,
                head_branch=head,
                draft=draft,
                labels=labels,
            )
        else:
            raise GitError(f"Unsupported forge: {forge}")

    def _create_github_pr(
        self,
        project_path: Path | str,
        title: str,
        body: str,
        base_branch: Optional[str],
        head_branch: str,
        draft: bool,
        labels: Optional[List[str]],
    ) -> PRInfo:
        """Create a GitHub pull request using gh CLI."""
        path_key = self._get_path_key(project_path)

        args = ["pr", "create", "--title", title, "--body", body]

        if base_branch:
            args.extend(["--base", base_branch])
        if draft:
            args.append("--draft")
        if labels:
            for label in labels:
                args.extend(["--label", label])

        result = self._run_cli(project_path, self.github_cli, args)

        # Parse PR URL from output
        pr_url = result.stdout.strip().split("\n")[-1]

        # Extract PR number from URL
        pr_number = 0
        match = re.search(r"/pull/(\d+)", pr_url)
        if match:
            pr_number = int(match.group(1))

        # Emit event
        self._emit_event(PRCreatedEvent(
            project_path=path_key,
            pr_number=pr_number,
            pr_url=pr_url,
            title=title,
            base_branch=base_branch or "main",
            head_branch=head_branch,
        ))

        return PRInfo(
            number=pr_number,
            url=pr_url,
            title=title,
            body=body,
            state="open",
            base_branch=base_branch or "main",
            head_branch=head_branch,
            author="",
            created_at="",
            updated_at="",
            draft=draft,
            labels=labels or [],
        )

    def _create_gitlab_pr(
        self,
        project_path: Path | str,
        title: str,
        body: str,
        base_branch: Optional[str],
        head_branch: str,
        draft: bool,
        labels: Optional[List[str]],
    ) -> PRInfo:
        """Create a GitLab merge request using glab CLI."""
        path_key = self._get_path_key(project_path)

        args = ["mr", "create", "--title", title, "--description", body]

        if base_branch:
            args.extend(["--target-branch", base_branch])
        if draft:
            args.append("--draft")
        if labels:
            args.extend(["--label", ",".join(labels)])

        result = self._run_cli(project_path, self.gitlab_cli, args)

        # Parse MR URL from output
        mr_url = result.stdout.strip().split("\n")[-1]

        # Extract MR number from URL
        mr_number = 0
        match = re.search(r"/merge_requests/(\d+)", mr_url)
        if match:
            mr_number = int(match.group(1))

        # Emit event
        self._emit_event(PRCreatedEvent(
            project_path=path_key,
            pr_number=mr_number,
            pr_url=mr_url,
            title=title,
            base_branch=base_branch or "main",
            head_branch=head_branch,
        ))

        return PRInfo(
            number=mr_number,
            url=mr_url,
            title=title,
            body=body,
            state="open",
            base_branch=base_branch or "main",
            head_branch=head_branch,
            author="",
            created_at="",
            updated_at="",
            draft=draft,
            labels=labels or [],
        )

    def get_pr(
        self,
        project_path: Path | str,
        pr_number: Optional[int] = None,
    ) -> Optional[PRInfo]:
        """Get PR information.

        Args:
            project_path: Path to the project directory.
            pr_number: PR number (default: current branch's PR).

        Returns:
            PRInfo if found, None otherwise.
        """
        forge = self.detect_forge(project_path)

        if forge == "github":
            return self._get_github_pr(project_path, pr_number)
        elif forge == "gitlab":
            return self._get_gitlab_pr(project_path, pr_number)

        return None

    def _get_github_pr(
        self,
        project_path: Path | str,
        pr_number: Optional[int],
    ) -> Optional[PRInfo]:
        """Get GitHub PR info."""
        args = ["pr", "view"]
        if pr_number:
            args.append(str(pr_number))
        args.extend(["--json", "number,url,title,body,state,baseRefName,headRefName,author,createdAt,updatedAt,isDraft,labels"])

        try:
            result = self._run_cli(project_path, self.github_cli, args)
            import json
            data = json.loads(result.stdout)

            return PRInfo(
                number=data["number"],
                url=data["url"],
                title=data["title"],
                body=data.get("body", ""),
                state=data["state"].lower(),
                base_branch=data["baseRefName"],
                head_branch=data["headRefName"],
                author=data["author"]["login"] if data.get("author") else "",
                created_at=data.get("createdAt", ""),
                updated_at=data.get("updatedAt", ""),
                draft=data.get("isDraft", False),
                labels=[l["name"] for l in data.get("labels", [])],
            )
        except (GitError, KeyError):
            return None

    def _get_gitlab_pr(
        self,
        project_path: Path | str,
        mr_number: Optional[int],
    ) -> Optional[PRInfo]:
        """Get GitLab MR info."""
        args = ["mr", "view"]
        if mr_number:
            args.append(str(mr_number))
        args.extend(["-F", "json"])

        try:
            result = self._run_cli(project_path, self.gitlab_cli, args)
            import json
            data = json.loads(result.stdout)

            return PRInfo(
                number=data["iid"],
                url=data["web_url"],
                title=data["title"],
                body=data.get("description", ""),
                state=data["state"],
                base_branch=data["target_branch"],
                head_branch=data["source_branch"],
                author=data["author"]["username"] if data.get("author") else "",
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                draft=data.get("draft", False),
                labels=data.get("labels", []),
            )
        except (GitError, KeyError):
            return None

    def list_prs(
        self,
        project_path: Path | str,
        state: str = "open",
        limit: int = 30,
    ) -> List[PRInfo]:
        """List pull requests.

        Args:
            project_path: Path to the project directory.
            state: Filter by state (open, closed, all).
            limit: Maximum number of PRs to return.

        Returns:
            List of PRInfo instances.
        """
        forge = self.detect_forge(project_path)

        if forge == "github":
            return self._list_github_prs(project_path, state, limit)
        elif forge == "gitlab":
            return self._list_gitlab_prs(project_path, state, limit)

        return []

    def _list_github_prs(
        self,
        project_path: Path | str,
        state: str,
        limit: int,
    ) -> List[PRInfo]:
        """List GitHub PRs."""
        args = [
            "pr", "list",
            "--state", state,
            "--limit", str(limit),
            "--json", "number,url,title,state,baseRefName,headRefName,author,createdAt,isDraft",
        ]

        try:
            result = self._run_cli(project_path, self.github_cli, args)
            import json
            data = json.loads(result.stdout)

            return [
                PRInfo(
                    number=pr["number"],
                    url=pr["url"],
                    title=pr["title"],
                    body="",
                    state=pr["state"].lower(),
                    base_branch=pr["baseRefName"],
                    head_branch=pr["headRefName"],
                    author=pr["author"]["login"] if pr.get("author") else "",
                    created_at=pr.get("createdAt", ""),
                    updated_at="",
                    draft=pr.get("isDraft", False),
                )
                for pr in data
            ]
        except (GitError, KeyError):
            return []

    def _list_gitlab_prs(
        self,
        project_path: Path | str,
        state: str,
        limit: int,
    ) -> List[PRInfo]:
        """List GitLab MRs."""
        args = ["mr", "list", "-F", "json"]

        if state != "all":
            args.extend(["--state", state])

        try:
            result = self._run_cli(project_path, self.gitlab_cli, args)
            import json
            data = json.loads(result.stdout)

            return [
                PRInfo(
                    number=mr["iid"],
                    url=mr["web_url"],
                    title=mr["title"],
                    body="",
                    state=mr["state"],
                    base_branch=mr["target_branch"],
                    head_branch=mr["source_branch"],
                    author=mr["author"]["username"] if mr.get("author") else "",
                    created_at=mr.get("created_at", ""),
                    updated_at="",
                    draft=mr.get("draft", False),
                )
                for mr in data[:limit]
            ]
        except (GitError, KeyError):
            return []

    # =========================================================================
    # PR templates
    # =========================================================================

    def create_pr_from_template(
        self,
        project_path: Path | str,
        title_template: str,
        body_template: str,
        variables: Dict[str, str],
        base_branch: Optional[str] = None,
        draft: bool = False,
        labels: Optional[List[str]] = None,
    ) -> PRInfo:
        """Create a PR using templates.

        Args:
            project_path: Path to the project directory.
            title_template: Title template with {placeholders}.
            body_template: Body template with {placeholders}.
            variables: Variables for template substitution.
            base_branch: Target branch.
            draft: If True, create as draft.
            labels: Labels to add.

        Returns:
            PRInfo for the created PR.
        """
        # Apply template variables
        title = title_template
        body = body_template

        for key, value in variables.items():
            title = title.replace(f"{{{key}}}", value)
            body = body.replace(f"{{{key}}}", value)

        return self.create_pr(
            project_path,
            title=title,
            body=body,
            base_branch=base_branch,
            draft=draft,
            labels=labels,
        )

    # =========================================================================
    # Utility methods
    # =========================================================================

    def is_git_repo(self, project_path: Path | str) -> bool:
        """Check if a path is a git repository.

        Args:
            project_path: Path to check.

        Returns:
            True if it's a git repository.
        """
        result = self._run_git(
            project_path,
            ["rev-parse", "--git-dir"],
            check=False,
        )
        return result.returncode == 0

    def is_clean(self, project_path: Path | str) -> bool:
        """Check if working tree is clean.

        Args:
            project_path: Path to the project directory.

        Returns:
            True if clean (no uncommitted changes).
        """
        status = self.get_status(project_path)
        return status.is_clean

    def has_github_cli(self) -> bool:
        """Check if GitHub CLI is available."""
        try:
            subprocess.run(
                [self.github_cli, "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def has_gitlab_cli(self) -> bool:
        """Check if GitLab CLI is available."""
        try:
            subprocess.run(
                [self.gitlab_cli, "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
