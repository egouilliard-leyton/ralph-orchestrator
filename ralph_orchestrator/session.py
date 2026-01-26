"""Session management with anti-gaming features.

Creates and manages .ralph-session/ directory structure:
- session.json: Session metadata
- task-status.json: Task completion status
- task-status.sha256: Checksum for tamper detection
- logs/timeline.jsonl: Event timeline
- logs/: Agent and gate output logs
- artifacts/: Screenshots, reports, etc.
- pids/: Service PID files
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_session_id() -> str:
    """Generate a unique session ID (YYYYMMDD-HHMMSS-hex)."""
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d-%H%M%S")
    random_hex = secrets.token_hex(8)
    return f"{date_part}-{random_hex}"


def generate_session_token(session_id: str) -> str:
    """Generate a session token for signal validation."""
    return f"ralph-{session_id}"


def get_git_info() -> Dict[str, Optional[str]]:
    """Get current git branch and commit hash."""
    branch = None
    commit = None
    
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
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
        )
        if result.returncode == 0:
            commit = result.stdout.strip()[:12]  # Short hash
    except Exception:
        pass
    
    return {"branch": branch, "commit": commit}


@dataclass
class TaskStatusEntry:
    """Status entry for a single task."""
    passes: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    iterations: int = 0
    last_failure: Optional[str] = None
    agent_outputs: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result: Dict[str, Any] = {"passes": self.passes}
        if self.started_at:
            result["started_at"] = self.started_at
        if self.completed_at:
            result["completed_at"] = self.completed_at
        if self.iterations:
            result["iterations"] = self.iterations
        if self.last_failure:
            result["last_failure"] = self.last_failure
        if self.agent_outputs:
            result["agent_outputs"] = self.agent_outputs
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStatusEntry":
        """Create from dictionary."""
        return cls(
            passes=data.get("passes", False),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            iterations=data.get("iterations", 0),
            last_failure=data.get("last_failure"),
            agent_outputs=data.get("agent_outputs", {}),
        )


@dataclass
class TaskStatus:
    """Task status container with checksum support."""
    checksum: str
    last_updated: str
    tasks: Dict[str, TaskStatusEntry] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without checksum for hashing)."""
        return {
            "checksum": self.checksum,
            "last_updated": self.last_updated,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
        }
    
    def to_dict_for_checksum(self) -> Dict[str, Any]:
        """Convert to dictionary for checksum calculation (without checksum field)."""
        return {
            "last_updated": self.last_updated,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStatus":
        """Create from dictionary."""
        tasks = {}
        for task_id, entry_data in data.get("tasks", {}).items():
            tasks[task_id] = TaskStatusEntry.from_dict(entry_data)
        return cls(
            checksum=data.get("checksum", ""),
            last_updated=data.get("last_updated", ""),
            tasks=tasks,
        )


def compute_checksum(data: Dict[str, Any]) -> str:
    """Compute SHA-256 checksum of data."""
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    hash_bytes = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    return f"sha256:{hash_bytes}"


@dataclass
class SessionMetadata:
    """Session metadata stored in session.json."""
    session_id: str
    session_token: str
    started_at: str
    task_source: str
    task_source_type: str
    status: str = "running"  # running, completed, failed, aborted
    
    # Optional fields
    ended_at: Optional[str] = None
    config_path: Optional[str] = None
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    current_task: Optional[str] = None
    completed_tasks: List[str] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    total_iterations: int = 0
    failure_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result: Dict[str, Any] = {
            "session_id": self.session_id,
            "session_token": self.session_token,
            "started_at": self.started_at,
            "task_source": self.task_source,
            "task_source_type": self.task_source_type,
            "status": self.status,
        }
        if self.ended_at:
            result["ended_at"] = self.ended_at
        if self.config_path:
            result["config_path"] = self.config_path
        if self.git_branch:
            result["git_branch"] = self.git_branch
        if self.git_commit:
            result["git_commit"] = self.git_commit
        if self.current_task:
            result["current_task"] = self.current_task
        if self.completed_tasks:
            result["completed_tasks"] = self.completed_tasks
        if self.pending_tasks:
            result["pending_tasks"] = self.pending_tasks
        if self.total_iterations:
            result["total_iterations"] = self.total_iterations
        if self.failure_reason:
            result["failure_reason"] = self.failure_reason
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            session_token=data["session_token"],
            started_at=data["started_at"],
            task_source=data["task_source"],
            task_source_type=data["task_source_type"],
            status=data.get("status", "running"),
            ended_at=data.get("ended_at"),
            config_path=data.get("config_path"),
            git_branch=data.get("git_branch"),
            git_commit=data.get("git_commit"),
            current_task=data.get("current_task"),
            completed_tasks=data.get("completed_tasks", []),
            pending_tasks=data.get("pending_tasks", []),
            total_iterations=data.get("total_iterations", 0),
            failure_reason=data.get("failure_reason"),
        )


class TamperingDetectedError(Exception):
    """Raised when checksum tampering is detected."""
    pass


class Session:
    """Ralph session manager.
    
    Handles creation and management of .ralph-session/ directory structure
    with anti-gaming checksum verification.
    """
    
    def __init__(
        self,
        session_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ):
        """Initialize session manager.
        
        Args:
            session_dir: Path to session directory. Defaults to .ralph-session.
            repo_root: Repository root. Defaults to current working directory.
        """
        if repo_root is None:
            repo_root = Path.cwd()
        self.repo_root = repo_root.resolve()
        
        if session_dir is None:
            # Check environment override
            env_session_dir = os.environ.get("RALPH_SESSION_DIR")
            if env_session_dir:
                session_dir = Path(env_session_dir)
            else:
                session_dir = self.repo_root / ".ralph-session"
        
        self.session_dir = session_dir.resolve()
        self.metadata: Optional[SessionMetadata] = None
        self.task_status: Optional[TaskStatus] = None
        self._initialized = False
    
    @property
    def session_json_path(self) -> Path:
        """Path to session.json."""
        return self.session_dir / "session.json"
    
    @property
    def task_status_path(self) -> Path:
        """Path to task-status.json."""
        return self.session_dir / "task-status.json"
    
    @property
    def task_status_checksum_path(self) -> Path:
        """Path to task-status.sha256."""
        return self.session_dir / "task-status.sha256"
    
    @property
    def timeline_path(self) -> Path:
        """Path to timeline.jsonl."""
        return self.session_dir / "logs" / "timeline.jsonl"
    
    @property
    def logs_dir(self) -> Path:
        """Path to logs directory."""
        return self.session_dir / "logs"
    
    @property
    def artifacts_dir(self) -> Path:
        """Path to artifacts directory."""
        return self.session_dir / "artifacts"
    
    @property
    def pids_dir(self) -> Path:
        """Path to PIDs directory."""
        return self.session_dir / "pids"
    
    @property
    def screenshots_dir(self) -> Path:
        """Path to screenshots directory."""
        return self.artifacts_dir / "screenshots"
    
    @property
    def session_token(self) -> Optional[str]:
        """Get the session token (for signal validation)."""
        if self.metadata:
            return self.metadata.session_token
        return None
    
    @property
    def session_id(self) -> Optional[str]:
        """Get the session ID."""
        if self.metadata:
            return self.metadata.session_id
        return None
    
    def initialize(
        self,
        task_source: str,
        task_source_type: str,
        config_path: Optional[str] = None,
        pending_tasks: Optional[List[str]] = None,
    ) -> "Session":
        """Initialize a new session.
        
        Creates the session directory structure and initial files.
        
        Args:
            task_source: Path to the task source file.
            task_source_type: Type of task source (prd_json, cr_markdown).
            config_path: Path to the configuration file.
            pending_tasks: List of pending task IDs.
            
        Returns:
            Self for chaining.
        """
        # Create directory structure
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.pids_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate session ID and token
        session_id = generate_session_id()
        session_token = generate_session_token(session_id)
        
        # Get git info
        git_info = get_git_info()
        
        # Create session metadata
        self.metadata = SessionMetadata(
            session_id=session_id,
            session_token=session_token,
            started_at=utc_now_iso(),
            task_source=task_source,
            task_source_type=task_source_type,
            config_path=config_path,
            git_branch=git_info.get("branch"),
            git_commit=git_info.get("commit"),
            pending_tasks=pending_tasks or [],
        )
        
        # Create initial task status
        self.task_status = TaskStatus(
            checksum="",
            last_updated=utc_now_iso(),
            tasks={},
        )
        
        # Initialize task status entries for pending tasks
        for task_id in (pending_tasks or []):
            self.task_status.tasks[task_id] = TaskStatusEntry()
        
        # Save files
        self._save_session_metadata()
        self._save_task_status()
        
        # Create empty timeline
        self.timeline_path.touch()
        
        self._initialized = True
        return self
    
    def load(self, verify_checksum: bool = True) -> "Session":
        """Load an existing session.
        
        Args:
            verify_checksum: Whether to verify the task status checksum.
            
        Returns:
            Self for chaining.
            
        Raises:
            FileNotFoundError: If session files don't exist.
            TamperingDetectedError: If checksum verification fails.
        """
        if not self.session_json_path.exists():
            raise FileNotFoundError(f"Session not found: {self.session_json_path}")
        
        # Load session metadata
        data = json.loads(self.session_json_path.read_text(encoding="utf-8"))
        self.metadata = SessionMetadata.from_dict(data)
        
        # Load task status
        if self.task_status_path.exists():
            status_data = json.loads(self.task_status_path.read_text(encoding="utf-8"))
            self.task_status = TaskStatus.from_dict(status_data)
            
            # Verify checksum if requested
            if verify_checksum:
                self.verify_checksum()
        
        self._initialized = True
        return self
    
    def _save_session_metadata(self) -> None:
        """Save session metadata to session.json."""
        if self.metadata is None:
            raise RuntimeError("Session not initialized")
        
        content = json.dumps(self.metadata.to_dict(), indent=2) + "\n"
        self.session_json_path.write_text(content, encoding="utf-8")
    
    def _save_task_status(self) -> None:
        """Save task status with checksum."""
        if self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        # Update timestamp
        self.task_status.last_updated = utc_now_iso()
        
        # Compute checksum
        checksum_data = self.task_status.to_dict_for_checksum()
        self.task_status.checksum = compute_checksum(checksum_data)
        
        # Save task status
        content = json.dumps(self.task_status.to_dict(), indent=2) + "\n"
        self.task_status_path.write_text(content, encoding="utf-8")
        
        # Save separate checksum file
        self.task_status_checksum_path.write_text(
            self.task_status.checksum + "\n",
            encoding="utf-8",
        )
    
    def verify_checksum(self) -> bool:
        """Verify task status checksum.
        
        Returns:
            True if checksum is valid.
            
        Raises:
            TamperingDetectedError: If checksum doesn't match.
        """
        if self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        # Load external checksum file
        external_checksum = None
        if self.task_status_checksum_path.exists():
            external_checksum = self.task_status_checksum_path.read_text(
                encoding="utf-8"
            ).strip()
        
        # Compute expected checksum
        checksum_data = self.task_status.to_dict_for_checksum()
        expected_checksum = compute_checksum(checksum_data)
        
        # Verify embedded checksum matches computed
        if self.task_status.checksum != expected_checksum:
            raise TamperingDetectedError(
                f"Task status checksum mismatch: embedded={self.task_status.checksum}, "
                f"computed={expected_checksum}"
            )
        
        # Verify external checksum file matches (if exists)
        if external_checksum and external_checksum != expected_checksum:
            raise TamperingDetectedError(
                f"External checksum file mismatch: file={external_checksum}, "
                f"computed={expected_checksum}"
            )
        
        return True
    
    def update_current_task(self, task_id: str) -> None:
        """Update the current task being executed."""
        if self.metadata is None:
            raise RuntimeError("Session not initialized")
        
        self.metadata.current_task = task_id
        self._save_session_metadata()
    
    def start_task(self, task_id: str) -> None:
        """Mark a task as started."""
        if self.metadata is None or self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        self.metadata.current_task = task_id
        
        if task_id not in self.task_status.tasks:
            self.task_status.tasks[task_id] = TaskStatusEntry()
        
        self.task_status.tasks[task_id].started_at = utc_now_iso()
        
        self._save_session_metadata()
        self._save_task_status()
    
    def complete_task(self, task_id: str) -> None:
        """Mark a task as completed."""
        if self.metadata is None or self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        # Update task status
        if task_id not in self.task_status.tasks:
            self.task_status.tasks[task_id] = TaskStatusEntry()
        
        entry = self.task_status.tasks[task_id]
        entry.passes = True
        entry.completed_at = utc_now_iso()
        
        # Update session metadata
        if task_id not in self.metadata.completed_tasks:
            self.metadata.completed_tasks.append(task_id)
        if task_id in self.metadata.pending_tasks:
            self.metadata.pending_tasks.remove(task_id)
        if self.metadata.current_task == task_id:
            self.metadata.current_task = None
        
        self._save_session_metadata()
        self._save_task_status()
    
    def fail_task(self, task_id: str, reason: str) -> None:
        """Record a task failure."""
        if self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        if task_id not in self.task_status.tasks:
            self.task_status.tasks[task_id] = TaskStatusEntry()
        
        self.task_status.tasks[task_id].last_failure = reason
        self._save_task_status()
    
    def increment_iterations(self, task_id: str) -> int:
        """Increment iteration count for a task."""
        if self.metadata is None or self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        if task_id not in self.task_status.tasks:
            self.task_status.tasks[task_id] = TaskStatusEntry()
        
        self.task_status.tasks[task_id].iterations += 1
        self.metadata.total_iterations += 1
        
        self._save_session_metadata()
        self._save_task_status()
        
        return self.task_status.tasks[task_id].iterations
    
    def record_agent_output(self, task_id: str, role: str, log_path: str) -> None:
        """Record the path to an agent's output log."""
        if self.task_status is None:
            raise RuntimeError("Session not initialized")
        
        if task_id not in self.task_status.tasks:
            self.task_status.tasks[task_id] = TaskStatusEntry()
        
        self.task_status.tasks[task_id].agent_outputs[role] = log_path
        self._save_task_status()
    
    def end_session(
        self,
        status: str = "completed",
        failure_reason: Optional[str] = None,
    ) -> None:
        """End the session.
        
        Args:
            status: Final status (completed, failed, aborted).
            failure_reason: Reason for failure (if status is failed).
        """
        if self.metadata is None:
            raise RuntimeError("Session not initialized")
        
        self.metadata.status = status
        self.metadata.ended_at = utc_now_iso()
        self.metadata.current_task = None
        
        if failure_reason:
            self.metadata.failure_reason = failure_reason
        
        self._save_session_metadata()
    
    def get_log_path(self, name: str, task_id: Optional[str] = None) -> Path:
        """Get a path for a log file.
        
        Args:
            name: Log name (e.g., "implementation", "gates", "review").
            task_id: Task ID to include in filename.
            
        Returns:
            Path for the log file.
        """
        if task_id:
            filename = f"{task_id}-{name}.log"
        else:
            filename = f"{name}.log"
        return self.logs_dir / filename
    
    def exists(self) -> bool:
        """Check if session exists."""
        return self.session_json_path.exists()
    
    def is_running(self) -> bool:
        """Check if session is currently running."""
        if self.metadata is None:
            return False
        return self.metadata.status == "running"
    
    def cleanup(self) -> None:
        """Clean up session directory (for testing)."""
        import shutil
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)
        self.metadata = None
        self.task_status = None
        self._initialized = False


def create_session(
    task_source: str,
    task_source_type: str,
    config_path: Optional[str] = None,
    pending_tasks: Optional[List[str]] = None,
    session_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Session:
    """Create and initialize a new session.
    
    Args:
        task_source: Path to the task source file.
        task_source_type: Type of task source.
        config_path: Path to configuration file.
        pending_tasks: List of pending task IDs.
        session_dir: Session directory path.
        repo_root: Repository root path.
        
    Returns:
        Initialized Session instance.
    """
    session = Session(session_dir=session_dir, repo_root=repo_root)
    session.initialize(
        task_source=task_source,
        task_source_type=task_source_type,
        config_path=config_path,
        pending_tasks=pending_tasks,
    )
    return session


def load_session(
    session_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    verify_checksum: bool = True,
) -> Session:
    """Load an existing session.
    
    Args:
        session_dir: Session directory path.
        repo_root: Repository root path.
        verify_checksum: Whether to verify checksum.
        
    Returns:
        Loaded Session instance.
    """
    session = Session(session_dir=session_dir, repo_root=repo_root)
    session.load(verify_checksum=verify_checksum)
    return session
