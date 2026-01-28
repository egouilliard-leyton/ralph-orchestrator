"""Project discovery and management service.

This module provides the ProjectService class for discovering and managing
Ralph-configured projects. It scans the filesystem for directories containing
.ralph/ subdirectories and provides project metadata.

Features:
- Discover all Ralph projects in a given search path
- Extract project metadata (name, path, branch, task count, status)
- File watching for detecting new/removed projects
- Event emission for project state changes
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Thread, Event
from typing import Any, Callable, Dict, List, Optional, Set

import yaml


class ProjectEventType(str, Enum):
    """Types of events emitted by the project service."""
    PROJECT_DISCOVERED = "project_discovered"
    PROJECT_REMOVED = "project_removed"
    PROJECT_UPDATED = "project_updated"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"


@dataclass
class ProjectEvent:
    """Base class for project events."""
    event_type: ProjectEventType
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
        }


@dataclass
class ProjectDiscoveredEvent(ProjectEvent):
    """Event emitted when a new project is discovered."""
    event_type: ProjectEventType = field(init=False, default=ProjectEventType.PROJECT_DISCOVERED)
    project_path: str = ""
    project_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "project_path": self.project_path,
            "project_name": self.project_name,
        })
        return d


@dataclass
class ProjectRemovedEvent(ProjectEvent):
    """Event emitted when a project is no longer detected."""
    event_type: ProjectEventType = field(init=False, default=ProjectEventType.PROJECT_REMOVED)
    project_path: str = ""
    project_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "project_path": self.project_path,
            "project_name": self.project_name,
        })
        return d


@dataclass
class ProjectUpdatedEvent(ProjectEvent):
    """Event emitted when project metadata changes."""
    event_type: ProjectEventType = field(init=False, default=ProjectEventType.PROJECT_UPDATED)
    project_path: str = ""
    project_name: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "project_path": self.project_path,
            "project_name": self.project_name,
            "changes": self.changes,
        })
        return d


@dataclass
class ScanStartedEvent(ProjectEvent):
    """Event emitted when a project scan starts."""
    event_type: ProjectEventType = field(init=False, default=ProjectEventType.SCAN_STARTED)
    search_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "search_paths": self.search_paths,
        })
        return d


@dataclass
class ScanCompletedEvent(ProjectEvent):
    """Event emitted when a project scan completes."""
    event_type: ProjectEventType = field(init=False, default=ProjectEventType.SCAN_COMPLETED)
    projects_found: int = 0
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "projects_found": self.projects_found,
            "duration_ms": self.duration_ms,
        })
        return d


# Type alias for event handlers
ProjectEventHandler = Callable[[Any], None]


@dataclass
class ProjectMetadata:
    """Metadata for a discovered Ralph project."""
    # Core identifiers
    path: Path
    name: str

    # Git info
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    git_remote: Optional[str] = None

    # Task info from PRD
    task_count: int = 0
    tasks_completed: int = 0
    tasks_pending: int = 0

    # Session info
    status: str = "idle"  # idle, running, completed, failed
    session_id: Optional[str] = None
    current_task: Optional[str] = None

    # Config info
    has_config: bool = False
    config_version: Optional[str] = None

    # Timestamps
    discovered_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": str(self.path),
            "name": self.name,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
            "git_remote": self.git_remote,
            "task_count": self.task_count,
            "tasks_completed": self.tasks_completed,
            "tasks_pending": self.tasks_pending,
            "status": self.status,
            "session_id": self.session_id,
            "current_task": self.current_task,
            "has_config": self.has_config,
            "config_version": self.config_version,
            "discovered_at": self.discovered_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectMetadata":
        """Create from dictionary."""
        return cls(
            path=Path(data["path"]),
            name=data["name"],
            git_branch=data.get("git_branch"),
            git_commit=data.get("git_commit"),
            git_remote=data.get("git_remote"),
            task_count=data.get("task_count", 0),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_pending=data.get("tasks_pending", 0),
            status=data.get("status", "idle"),
            session_id=data.get("session_id"),
            current_task=data.get("current_task"),
            has_config=data.get("has_config", False),
            config_version=data.get("config_version"),
            discovered_at=data.get("discovered_at", time.time()),
            last_updated=data.get("last_updated", time.time()),
        )


def _get_git_info(project_path: Path) -> Dict[str, Optional[str]]:
    """Get git information for a project directory."""
    branch = None
    commit = None
    remote = None

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_path,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_path,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()[:12]
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_path,
        )
        if result.returncode == 0:
            remote = result.stdout.strip()
    except Exception:
        pass

    return {"branch": branch, "commit": commit, "remote": remote}


def _get_project_name(project_path: Path) -> str:
    """Extract project name from path or config."""
    # Try to get name from PRD
    prd_path = project_path / ".ralph" / "prd.json"
    if prd_path.exists():
        try:
            prd_data = json.loads(prd_path.read_text(encoding="utf-8"))
            if "project" in prd_data and prd_data["project"]:
                return prd_data["project"]
        except Exception:
            pass

    # Fallback to directory name
    return project_path.name


def _get_task_counts(project_path: Path) -> Dict[str, int]:
    """Get task counts from PRD file."""
    counts = {"total": 0, "completed": 0, "pending": 0}

    prd_path = project_path / ".ralph" / "prd.json"
    if not prd_path.exists():
        return counts

    try:
        prd_data = json.loads(prd_path.read_text(encoding="utf-8"))
        tasks = prd_data.get("tasks", [])
        counts["total"] = len(tasks)
        counts["completed"] = sum(1 for t in tasks if t.get("passes", False))
        counts["pending"] = counts["total"] - counts["completed"]
    except Exception:
        pass

    return counts


def _get_session_info(project_path: Path) -> Dict[str, Any]:
    """Get active session information."""
    info: Dict[str, Any] = {
        "status": "idle",
        "session_id": None,
        "current_task": None,
    }

    session_path = project_path / ".ralph-session" / "session.json"
    if not session_path.exists():
        return info

    try:
        session_data = json.loads(session_path.read_text(encoding="utf-8"))
        info["status"] = session_data.get("status", "idle")
        info["session_id"] = session_data.get("session_id")
        info["current_task"] = session_data.get("current_task")
    except Exception:
        pass

    return info


def _get_config_info(project_path: Path) -> Dict[str, Any]:
    """Get configuration information."""
    info: Dict[str, Any] = {
        "has_config": False,
        "config_version": None,
    }

    config_path = project_path / ".ralph" / "ralph.yml"
    if not config_path.exists():
        return info

    try:
        config_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        info["has_config"] = True
        info["config_version"] = config_data.get("version")
    except Exception:
        info["has_config"] = True  # File exists but might have issues

    return info


class ProjectService:
    """Service for discovering and managing Ralph projects.

    This service scans the filesystem for directories containing .ralph/
    subdirectories and provides project metadata. It supports event-based
    notifications for project discovery and changes, and can optionally
    watch for filesystem changes.

    Usage:
        service = ProjectService(search_paths=["/home/user/projects"])

        # Register event handlers
        service.on_event(ProjectEventType.PROJECT_DISCOVERED, my_handler)

        # Discover projects
        projects = service.discover_projects()

        # Start watching for changes (optional)
        service.start_watching()

        # Get project by path
        project = service.get_project("/home/user/projects/myapp")

        # Stop watching
        service.stop_watching()
    """

    def __init__(
        self,
        search_paths: Optional[List[Path]] = None,
        max_depth: int = 3,
        exclude_patterns: Optional[List[str]] = None,
    ):
        """Initialize the project service.

        Args:
            search_paths: List of paths to search for projects. Defaults to home directory.
            max_depth: Maximum directory depth to search. Default 3.
            exclude_patterns: Directory name patterns to exclude from search.
        """
        if search_paths is None:
            search_paths = [Path.home()]
        self.search_paths = [Path(p).resolve() for p in search_paths]

        self.max_depth = max_depth
        self.exclude_patterns = exclude_patterns or [
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            ".tox",
            "dist",
            "build",
            ".cache",
        ]

        # Discovered projects cache
        self._projects: Dict[str, ProjectMetadata] = {}

        # Event handlers
        self._event_handlers: Dict[ProjectEventType, List[ProjectEventHandler]] = {
            event_type: [] for event_type in ProjectEventType
        }
        self._global_handlers: List[ProjectEventHandler] = []

        # File watching
        self._watch_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._watch_interval: float = 5.0  # seconds

    def on_event(self, event_type: ProjectEventType, handler: ProjectEventHandler) -> None:
        """Register an event handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: Callable that receives the event.
        """
        self._event_handlers[event_type].append(handler)

    def on_all_events(self, handler: ProjectEventHandler) -> None:
        """Register a handler for all events.

        Args:
            handler: Callable that receives any event.
        """
        self._global_handlers.append(handler)

    def remove_handler(self, event_type: ProjectEventType, handler: ProjectEventHandler) -> None:
        """Remove an event handler.

        Args:
            event_type: The type of event.
            handler: The handler to remove.
        """
        if handler in self._event_handlers[event_type]:
            self._event_handlers[event_type].remove(handler)

    def _emit_event(self, event: ProjectEvent) -> None:
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

    def _should_exclude(self, dir_name: str) -> bool:
        """Check if a directory should be excluded from search."""
        for pattern in self.exclude_patterns:
            if pattern in dir_name or dir_name.startswith("."):
                return True
        return False

    def _scan_directory(
        self,
        base_path: Path,
        current_depth: int = 0,
    ) -> List[Path]:
        """Recursively scan a directory for .ralph/ subdirectories.

        Args:
            base_path: The directory to scan.
            current_depth: Current recursion depth.

        Returns:
            List of project paths (directories containing .ralph/).
        """
        projects: List[Path] = []

        if current_depth > self.max_depth:
            return projects

        try:
            # Check if this directory contains .ralph/
            ralph_dir = base_path / ".ralph"
            if ralph_dir.is_dir():
                projects.append(base_path)
                # Don't recurse further into project directories
                return projects

            # Scan subdirectories
            for entry in base_path.iterdir():
                if entry.is_dir():
                    if self._should_exclude(entry.name):
                        continue
                    try:
                        projects.extend(
                            self._scan_directory(entry, current_depth + 1)
                        )
                    except PermissionError:
                        continue

        except PermissionError:
            pass
        except Exception:
            pass

        return projects

    def _extract_metadata(self, project_path: Path) -> ProjectMetadata:
        """Extract metadata for a project.

        Args:
            project_path: Path to the project directory.

        Returns:
            ProjectMetadata instance with extracted information.
        """
        # Get project name
        name = _get_project_name(project_path)

        # Get git info
        git_info = _get_git_info(project_path)

        # Get task counts
        task_counts = _get_task_counts(project_path)

        # Get session info
        session_info = _get_session_info(project_path)

        # Get config info
        config_info = _get_config_info(project_path)

        return ProjectMetadata(
            path=project_path,
            name=name,
            git_branch=git_info.get("branch"),
            git_commit=git_info.get("commit"),
            git_remote=git_info.get("remote"),
            task_count=task_counts["total"],
            tasks_completed=task_counts["completed"],
            tasks_pending=task_counts["pending"],
            status=session_info["status"],
            session_id=session_info["session_id"],
            current_task=session_info["current_task"],
            has_config=config_info["has_config"],
            config_version=config_info["config_version"],
        )

    def discover_projects(
        self,
        refresh: bool = False,
    ) -> List[ProjectMetadata]:
        """Discover all Ralph projects in the search paths.

        Args:
            refresh: If True, rescan even if projects are cached.

        Returns:
            List of discovered ProjectMetadata instances.
        """
        start_time = time.time()

        # Emit scan started event
        self._emit_event(ScanStartedEvent(
            search_paths=[str(p) for p in self.search_paths],
        ))

        # Track current project paths for change detection
        previous_paths: Set[str] = set(self._projects.keys())
        current_paths: Set[str] = set()

        # Scan all search paths
        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            project_dirs = self._scan_directory(search_path)

            for project_path in project_dirs:
                path_key = str(project_path)
                current_paths.add(path_key)

                # Check if this is a new project or needs refresh
                if path_key not in self._projects or refresh:
                    metadata = self._extract_metadata(project_path)
                    self._projects[path_key] = metadata

                    # Emit discovered event for new projects
                    if path_key not in previous_paths:
                        self._emit_event(ProjectDiscoveredEvent(
                            project_path=path_key,
                            project_name=metadata.name,
                        ))

        # Detect removed projects
        removed_paths = previous_paths - current_paths
        for path_key in removed_paths:
            if path_key in self._projects:
                metadata = self._projects[path_key]
                del self._projects[path_key]
                self._emit_event(ProjectRemovedEvent(
                    project_path=path_key,
                    project_name=metadata.name,
                ))

        duration_ms = int((time.time() - start_time) * 1000)

        # Emit scan completed event
        self._emit_event(ScanCompletedEvent(
            projects_found=len(self._projects),
            duration_ms=duration_ms,
        ))

        return list(self._projects.values())

    def get_project(self, path: Path | str) -> Optional[ProjectMetadata]:
        """Get metadata for a specific project.

        Args:
            path: Path to the project directory.

        Returns:
            ProjectMetadata if found, None otherwise.
        """
        path_key = str(Path(path).resolve())
        return self._projects.get(path_key)

    def refresh_project(self, path: Path | str) -> Optional[ProjectMetadata]:
        """Refresh metadata for a specific project.

        Args:
            path: Path to the project directory.

        Returns:
            Updated ProjectMetadata if found, None otherwise.
        """
        path_obj = Path(path).resolve()
        path_key = str(path_obj)

        if not (path_obj / ".ralph").is_dir():
            # Project no longer exists
            if path_key in self._projects:
                metadata = self._projects[path_key]
                del self._projects[path_key]
                self._emit_event(ProjectRemovedEvent(
                    project_path=path_key,
                    project_name=metadata.name,
                ))
            return None

        old_metadata = self._projects.get(path_key)
        new_metadata = self._extract_metadata(path_obj)
        new_metadata.last_updated = time.time()

        # Detect changes
        if old_metadata:
            changes: Dict[str, Any] = {}
            for attr in ["status", "task_count", "tasks_completed", "tasks_pending",
                         "current_task", "git_branch", "git_commit"]:
                old_val = getattr(old_metadata, attr)
                new_val = getattr(new_metadata, attr)
                if old_val != new_val:
                    changes[attr] = {"old": old_val, "new": new_val}

            if changes:
                self._emit_event(ProjectUpdatedEvent(
                    project_path=path_key,
                    project_name=new_metadata.name,
                    changes=changes,
                ))

        self._projects[path_key] = new_metadata
        return new_metadata

    def list_projects(self) -> List[ProjectMetadata]:
        """Get all discovered projects.

        Returns:
            List of all cached ProjectMetadata instances.
        """
        return list(self._projects.values())

    def get_projects_by_status(self, status: str) -> List[ProjectMetadata]:
        """Get projects filtered by status.

        Args:
            status: Status to filter by (idle, running, completed, failed).

        Returns:
            List of matching ProjectMetadata instances.
        """
        return [p for p in self._projects.values() if p.status == status]

    def _watch_loop(self) -> None:
        """Background thread loop for watching project changes."""
        while not self._stop_event.is_set():
            # Refresh all known projects
            for path_key in list(self._projects.keys()):
                if self._stop_event.is_set():
                    break
                self.refresh_project(path_key)

            # Periodically rescan for new projects
            self.discover_projects(refresh=False)

            # Wait for interval or stop event
            self._stop_event.wait(self._watch_interval)

    def start_watching(self, interval: float = 5.0) -> None:
        """Start background file watching for project changes.

        Args:
            interval: Seconds between refresh cycles. Default 5.0.
        """
        if self._watch_thread is not None and self._watch_thread.is_alive():
            return  # Already watching

        self._watch_interval = interval
        self._stop_event.clear()
        self._watch_thread = Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    def stop_watching(self) -> None:
        """Stop background file watching."""
        self._stop_event.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=2.0)
            self._watch_thread = None

    def is_watching(self) -> bool:
        """Check if file watching is active."""
        return self._watch_thread is not None and self._watch_thread.is_alive()

    def clear_cache(self) -> None:
        """Clear the project cache."""
        self._projects.clear()

    def add_search_path(self, path: Path | str) -> None:
        """Add a search path.

        Args:
            path: Path to add to search paths.
        """
        resolved = Path(path).resolve()
        if resolved not in self.search_paths:
            self.search_paths.append(resolved)

    def remove_search_path(self, path: Path | str) -> None:
        """Remove a search path.

        Args:
            path: Path to remove from search paths.
        """
        resolved = Path(path).resolve()
        if resolved in self.search_paths:
            self.search_paths.remove(resolved)
