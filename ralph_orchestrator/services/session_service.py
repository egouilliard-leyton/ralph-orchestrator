"""Session management service.

This module provides the SessionService class for managing Ralph sessions
with CRUD operations and event emission. It enhances the existing session.py
module with a service-oriented interface suitable for both CLI and API usage.

Features:
- CRUD operations for session data
- Event emission for session state changes
- Integration with existing Session class
- Support for multi-project session management
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..session import (
    Session,
    SessionMetadata,
    TaskStatus,
    TaskStatusEntry,
    TamperingDetectedError,
    generate_session_id,
    generate_session_token,
    utc_now_iso,
)


class SessionEventType(str, Enum):
    """Types of events emitted by the session service."""
    SESSION_CREATED = "session_created"
    SESSION_LOADED = "session_loaded"
    SESSION_ENDED = "session_ended"
    SESSION_DELETED = "session_deleted"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ITERATION_INCREMENTED = "iteration_incremented"
    STATUS_CHANGED = "status_changed"
    METADATA_UPDATED = "metadata_updated"


@dataclass
class SessionEvent:
    """Base class for session events."""
    event_type: SessionEventType
    timestamp: float = field(default_factory=time.time)
    project_path: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "project_path": self.project_path,
            "session_id": self.session_id,
        }


@dataclass
class SessionCreatedEvent(SessionEvent):
    """Event emitted when a new session is created."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.SESSION_CREATED)
    task_source: str = ""
    pending_tasks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_source": self.task_source,
            "pending_tasks": self.pending_tasks,
        })
        return d


@dataclass
class SessionLoadedEvent(SessionEvent):
    """Event emitted when a session is loaded."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.SESSION_LOADED)
    status: str = ""
    tasks_completed: int = 0
    tasks_pending: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_pending": self.tasks_pending,
        })
        return d


@dataclass
class SessionEndedEvent(SessionEvent):
    """Event emitted when a session ends."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.SESSION_ENDED)
    status: str = ""  # completed, failed, aborted
    tasks_completed: int = 0
    tasks_failed: int = 0
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "failure_reason": self.failure_reason,
        })
        return d


@dataclass
class SessionDeletedEvent(SessionEvent):
    """Event emitted when a session is deleted."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.SESSION_DELETED)


@dataclass
class TaskStartedEvent(SessionEvent):
    """Event emitted when a task starts."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.TASK_STARTED)
    task_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
        })
        return d


@dataclass
class TaskCompletedEvent(SessionEvent):
    """Event emitted when a task completes successfully."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.TASK_COMPLETED)
    task_id: str = ""
    iterations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "iterations": self.iterations,
        })
        return d


@dataclass
class TaskFailedEvent(SessionEvent):
    """Event emitted when a task fails."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.TASK_FAILED)
    task_id: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "reason": self.reason,
        })
        return d


@dataclass
class IterationIncrementedEvent(SessionEvent):
    """Event emitted when iteration count increases."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.ITERATION_INCREMENTED)
    task_id: str = ""
    iteration: int = 0
    total_iterations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "iteration": self.iteration,
            "total_iterations": self.total_iterations,
        })
        return d


@dataclass
class StatusChangedEvent(SessionEvent):
    """Event emitted when session status changes."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.STATUS_CHANGED)
    old_status: str = ""
    new_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "old_status": self.old_status,
            "new_status": self.new_status,
        })
        return d


@dataclass
class MetadataUpdatedEvent(SessionEvent):
    """Event emitted when session metadata is updated."""
    event_type: SessionEventType = field(init=False, default=SessionEventType.METADATA_UPDATED)
    changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "changes": self.changes,
        })
        return d


# Type alias for event handlers
SessionEventHandler = Callable[[Any], None]


@dataclass
class SessionSummary:
    """Summary information about a session."""
    session_id: str
    session_token: str
    project_path: Path
    status: str
    started_at: str
    ended_at: Optional[str]
    task_source: str
    current_task: Optional[str]
    completed_tasks: List[str]
    pending_tasks: List[str]
    total_iterations: int
    git_branch: Optional[str]
    git_commit: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "session_token": self.session_token,
            "project_path": str(self.project_path),
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "task_source": self.task_source,
            "current_task": self.current_task,
            "completed_tasks": self.completed_tasks,
            "pending_tasks": self.pending_tasks,
            "total_iterations": self.total_iterations,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
        }


@dataclass
class TaskStatusSummary:
    """Summary of a task's status within a session."""
    task_id: str
    passes: bool
    started_at: Optional[str]
    completed_at: Optional[str]
    iterations: int
    last_failure: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "passes": self.passes,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "iterations": self.iterations,
            "last_failure": self.last_failure,
        }


class SessionService:
    """Service for managing Ralph sessions with CRUD operations.

    This service provides a unified interface for session management that can be
    used by both CLI and API interfaces. It wraps the core Session class and adds
    event emission for state changes.

    Usage:
        service = SessionService()

        # Register event handlers
        service.on_event(SessionEventType.TASK_COMPLETED, my_handler)

        # Create a new session
        session = service.create_session(
            project_path=Path("/path/to/project"),
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
        )

        # Get session summary
        summary = service.get_session_summary(project_path)

        # Update task status
        service.start_task(project_path, "T-001")
        service.complete_task(project_path, "T-001")

        # End session
        service.end_session(project_path, "completed")
    """

    def __init__(self):
        """Initialize the session service."""
        # Cache of active sessions keyed by project path
        self._sessions: Dict[str, Session] = {}

        # Event handlers
        self._event_handlers: Dict[SessionEventType, List[SessionEventHandler]] = {
            event_type: [] for event_type in SessionEventType
        }
        self._global_handlers: List[SessionEventHandler] = []

    def on_event(self, event_type: SessionEventType, handler: SessionEventHandler) -> None:
        """Register an event handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: Callable that receives the event.
        """
        self._event_handlers[event_type].append(handler)

    def on_all_events(self, handler: SessionEventHandler) -> None:
        """Register a handler for all events.

        Args:
            handler: Callable that receives any event.
        """
        self._global_handlers.append(handler)

    def remove_handler(self, event_type: SessionEventType, handler: SessionEventHandler) -> None:
        """Remove an event handler.

        Args:
            event_type: The type of event.
            handler: The handler to remove.
        """
        if handler in self._event_handlers[event_type]:
            self._event_handlers[event_type].remove(handler)

    def _emit_event(self, event: SessionEvent) -> None:
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
        """Get normalized path key for caching."""
        return str(Path(project_path).resolve())

    def _get_session_dir(self, project_path: Path | str) -> Path:
        """Get the session directory for a project."""
        return Path(project_path).resolve() / ".ralph-session"

    # =========================================================================
    # CREATE operations
    # =========================================================================

    def create_session(
        self,
        project_path: Path | str,
        task_source: str,
        task_source_type: str,
        config_path: Optional[str] = None,
        pending_tasks: Optional[List[str]] = None,
    ) -> Session:
        """Create a new session for a project.

        Args:
            project_path: Path to the project directory.
            task_source: Path to the task source file (relative to project).
            task_source_type: Type of task source (prd_json, cr_markdown).
            config_path: Path to config file (optional).
            pending_tasks: List of pending task IDs.

        Returns:
            Initialized Session instance.

        Raises:
            ValueError: If session already exists for this project.
        """
        path_key = self._get_path_key(project_path)
        project_path_obj = Path(project_path).resolve()
        session_dir = self._get_session_dir(project_path)

        # Check if session already exists
        if session_dir.exists() and (session_dir / "session.json").exists():
            raise ValueError(f"Session already exists for project: {project_path}")

        # Create and initialize session
        session = Session(session_dir=session_dir, repo_root=project_path_obj)
        session.initialize(
            task_source=task_source,
            task_source_type=task_source_type,
            config_path=config_path,
            pending_tasks=pending_tasks,
        )

        # Cache the session
        self._sessions[path_key] = session

        # Emit event
        self._emit_event(SessionCreatedEvent(
            project_path=path_key,
            session_id=session.session_id,
            task_source=task_source,
            pending_tasks=list(pending_tasks) if pending_tasks else [],
        ))

        return session

    # =========================================================================
    # READ operations
    # =========================================================================

    def get_session(
        self,
        project_path: Path | str,
        verify_checksum: bool = True,
    ) -> Optional[Session]:
        """Get the session for a project, loading if necessary.

        Args:
            project_path: Path to the project directory.
            verify_checksum: Whether to verify checksum on load.

        Returns:
            Session instance if exists, None otherwise.
        """
        path_key = self._get_path_key(project_path)

        # Check cache first
        if path_key in self._sessions:
            return self._sessions[path_key]

        # Try to load from disk
        session_dir = self._get_session_dir(project_path)
        if not session_dir.exists() or not (session_dir / "session.json").exists():
            return None

        try:
            session = Session(
                session_dir=session_dir,
                repo_root=Path(project_path).resolve(),
            )
            session.load(verify_checksum=verify_checksum)

            # Cache the session
            self._sessions[path_key] = session

            # Emit event
            if session.metadata:
                self._emit_event(SessionLoadedEvent(
                    project_path=path_key,
                    session_id=session.session_id,
                    status=session.metadata.status,
                    tasks_completed=len(session.metadata.completed_tasks),
                    tasks_pending=len(session.metadata.pending_tasks),
                ))

            return session

        except (FileNotFoundError, TamperingDetectedError):
            return None

    def session_exists(self, project_path: Path | str) -> bool:
        """Check if a session exists for a project.

        Args:
            project_path: Path to the project directory.

        Returns:
            True if session exists.
        """
        session_dir = self._get_session_dir(project_path)
        return session_dir.exists() and (session_dir / "session.json").exists()

    def get_session_summary(self, project_path: Path | str) -> Optional[SessionSummary]:
        """Get a summary of the session for a project.

        Args:
            project_path: Path to the project directory.

        Returns:
            SessionSummary if session exists, None otherwise.
        """
        session = self.get_session(project_path)
        if session is None or session.metadata is None:
            return None

        meta = session.metadata
        return SessionSummary(
            session_id=meta.session_id,
            session_token=meta.session_token,
            project_path=Path(project_path).resolve(),
            status=meta.status,
            started_at=meta.started_at,
            ended_at=meta.ended_at,
            task_source=meta.task_source,
            current_task=meta.current_task,
            completed_tasks=list(meta.completed_tasks),
            pending_tasks=list(meta.pending_tasks),
            total_iterations=meta.total_iterations,
            git_branch=meta.git_branch,
            git_commit=meta.git_commit,
        )

    def get_task_statuses(self, project_path: Path | str) -> List[TaskStatusSummary]:
        """Get status summaries for all tasks in a session.

        Args:
            project_path: Path to the project directory.

        Returns:
            List of TaskStatusSummary instances.
        """
        session = self.get_session(project_path)
        if session is None or session.task_status is None:
            return []

        summaries = []
        for task_id, entry in session.task_status.tasks.items():
            summaries.append(TaskStatusSummary(
                task_id=task_id,
                passes=entry.passes,
                started_at=entry.started_at,
                completed_at=entry.completed_at,
                iterations=entry.iterations,
                last_failure=entry.last_failure,
            ))

        return summaries

    def get_task_status(
        self,
        project_path: Path | str,
        task_id: str,
    ) -> Optional[TaskStatusSummary]:
        """Get status for a specific task.

        Args:
            project_path: Path to the project directory.
            task_id: The task ID.

        Returns:
            TaskStatusSummary if found, None otherwise.
        """
        session = self.get_session(project_path)
        if session is None or session.task_status is None:
            return None

        entry = session.task_status.tasks.get(task_id)
        if entry is None:
            return None

        return TaskStatusSummary(
            task_id=task_id,
            passes=entry.passes,
            started_at=entry.started_at,
            completed_at=entry.completed_at,
            iterations=entry.iterations,
            last_failure=entry.last_failure,
        )

    def list_sessions(self, project_paths: List[Path | str]) -> List[SessionSummary]:
        """Get summaries for sessions across multiple projects.

        Args:
            project_paths: List of project paths to check.

        Returns:
            List of SessionSummary instances for existing sessions.
        """
        summaries = []
        for path in project_paths:
            summary = self.get_session_summary(path)
            if summary is not None:
                summaries.append(summary)
        return summaries

    # =========================================================================
    # UPDATE operations
    # =========================================================================

    def start_task(self, project_path: Path | str, task_id: str) -> None:
        """Mark a task as started.

        Args:
            project_path: Path to the project directory.
            task_id: The task ID to start.

        Raises:
            ValueError: If session doesn't exist.
        """
        path_key = self._get_path_key(project_path)
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        session.start_task(task_id)

        self._emit_event(TaskStartedEvent(
            project_path=path_key,
            session_id=session.session_id,
            task_id=task_id,
        ))

    def complete_task(self, project_path: Path | str, task_id: str) -> None:
        """Mark a task as completed.

        Args:
            project_path: Path to the project directory.
            task_id: The task ID to complete.

        Raises:
            ValueError: If session doesn't exist.
        """
        path_key = self._get_path_key(project_path)
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        # Get iterations before completing
        iterations = 0
        if session.task_status and task_id in session.task_status.tasks:
            iterations = session.task_status.tasks[task_id].iterations

        session.complete_task(task_id)

        self._emit_event(TaskCompletedEvent(
            project_path=path_key,
            session_id=session.session_id,
            task_id=task_id,
            iterations=iterations,
        ))

    def fail_task(self, project_path: Path | str, task_id: str, reason: str) -> None:
        """Record a task failure.

        Args:
            project_path: Path to the project directory.
            task_id: The task ID that failed.
            reason: The failure reason.

        Raises:
            ValueError: If session doesn't exist.
        """
        path_key = self._get_path_key(project_path)
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        session.fail_task(task_id, reason)

        self._emit_event(TaskFailedEvent(
            project_path=path_key,
            session_id=session.session_id,
            task_id=task_id,
            reason=reason,
        ))

    def increment_iterations(self, project_path: Path | str, task_id: str) -> int:
        """Increment iteration count for a task.

        Args:
            project_path: Path to the project directory.
            task_id: The task ID.

        Returns:
            New iteration count.

        Raises:
            ValueError: If session doesn't exist.
        """
        path_key = self._get_path_key(project_path)
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        iteration = session.increment_iterations(task_id)

        total_iterations = 0
        if session.metadata:
            total_iterations = session.metadata.total_iterations

        self._emit_event(IterationIncrementedEvent(
            project_path=path_key,
            session_id=session.session_id,
            task_id=task_id,
            iteration=iteration,
            total_iterations=total_iterations,
        ))

        return iteration

    def update_current_task(self, project_path: Path | str, task_id: str) -> None:
        """Update the current task being executed.

        Args:
            project_path: Path to the project directory.
            task_id: The current task ID.

        Raises:
            ValueError: If session doesn't exist.
        """
        path_key = self._get_path_key(project_path)
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        old_task = session.metadata.current_task if session.metadata else None
        session.update_current_task(task_id)

        self._emit_event(MetadataUpdatedEvent(
            project_path=path_key,
            session_id=session.session_id,
            changes={"current_task": {"old": old_task, "new": task_id}},
        ))

    def end_session(
        self,
        project_path: Path | str,
        status: str = "completed",
        failure_reason: Optional[str] = None,
    ) -> None:
        """End a session.

        Args:
            project_path: Path to the project directory.
            status: Final status (completed, failed, aborted).
            failure_reason: Reason for failure (if status is failed).

        Raises:
            ValueError: If session doesn't exist.
        """
        path_key = self._get_path_key(project_path)
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        # Get stats before ending
        tasks_completed = 0
        tasks_failed = 0
        if session.metadata:
            tasks_completed = len(session.metadata.completed_tasks)
            tasks_failed = len(session.metadata.pending_tasks)

        # Track status change
        old_status = session.metadata.status if session.metadata else "unknown"

        session.end_session(status=status, failure_reason=failure_reason)

        # Emit status changed event
        self._emit_event(StatusChangedEvent(
            project_path=path_key,
            session_id=session.session_id,
            old_status=old_status,
            new_status=status,
        ))

        # Emit session ended event
        self._emit_event(SessionEndedEvent(
            project_path=path_key,
            session_id=session.session_id,
            status=status,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            failure_reason=failure_reason,
        ))

    def record_agent_output(
        self,
        project_path: Path | str,
        task_id: str,
        role: str,
        log_path: str,
    ) -> None:
        """Record the path to an agent's output log.

        Args:
            project_path: Path to the project directory.
            task_id: The task ID.
            role: The agent role.
            log_path: Path to the log file.

        Raises:
            ValueError: If session doesn't exist.
        """
        session = self.get_session(project_path)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        session.record_agent_output(task_id, role, log_path)

    # =========================================================================
    # DELETE operations
    # =========================================================================

    def delete_session(self, project_path: Path | str) -> bool:
        """Delete a session and its data.

        Args:
            project_path: Path to the project directory.

        Returns:
            True if session was deleted, False if it didn't exist.
        """
        path_key = self._get_path_key(project_path)
        session_dir = self._get_session_dir(project_path)

        # Get session ID before deletion for event
        session_id = None
        session = self.get_session(project_path)
        if session:
            session_id = session.session_id

        # Remove from cache
        if path_key in self._sessions:
            del self._sessions[path_key]

        # Remove from disk
        if session_dir.exists():
            import shutil
            shutil.rmtree(session_dir)

            self._emit_event(SessionDeletedEvent(
                project_path=path_key,
                session_id=session_id,
            ))

            return True

        return False

    def clear_cache(self) -> None:
        """Clear the session cache."""
        self._sessions.clear()

    # =========================================================================
    # Utility methods
    # =========================================================================

    def verify_session_integrity(self, project_path: Path | str) -> bool:
        """Verify session checksum integrity.

        Args:
            project_path: Path to the project directory.

        Returns:
            True if checksum is valid.

        Raises:
            TamperingDetectedError: If checksum verification fails.
        """
        session = self.get_session(project_path, verify_checksum=False)

        if session is None:
            raise ValueError(f"No session found for project: {project_path}")

        return session.verify_checksum()

    def get_log_path(
        self,
        project_path: Path | str,
        name: str,
        task_id: Optional[str] = None,
    ) -> Path:
        """Get path for a log file.

        Args:
            project_path: Path to the project directory.
            name: Log name.
            task_id: Optional task ID.

        Returns:
            Path for the log file.
        """
        session = self.get_session(project_path)

        if session is None:
            # Create path even without session
            session_dir = self._get_session_dir(project_path)
            logs_dir = session_dir / "logs"
            if task_id:
                return logs_dir / f"{task_id}-{name}.log"
            return logs_dir / f"{name}.log"

        return session.get_log_path(name, task_id)

    def get_report_path(
        self,
        project_path: Path | str,
        role: str,
        task_id: str,
    ) -> Path:
        """Get canonical path for an agent's report file.

        Args:
            project_path: Path to the project directory.
            role: Agent role.
            task_id: Task ID.

        Returns:
            Path for the report file.
        """
        session = self.get_session(project_path)

        if session is None:
            # Create path even without session
            session_dir = self._get_session_dir(project_path)
            role_kebab = role.replace("_", "-")
            return session_dir / "reports" / task_id / f"{role_kebab}.md"

        return session.get_report_path(role, task_id)
