"""Timeline event logger.

Appends JSONL events to .ralph-session/logs/timeline.jsonl matching
the TimelineEvent schema from schemas/session.schema.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EventType(str, Enum):
    """Timeline event types matching the schema."""
    # Session events
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    
    # Task events
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    
    # Agent events
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_FAILED = "agent_failed"
    
    # Gate events
    GATES_RUN = "gates_run"
    GATE_PASS = "gate_pass"
    GATE_FAIL = "gate_fail"
    
    # Service events
    SERVICE_START = "service_start"
    SERVICE_READY = "service_ready"
    SERVICE_FAILED = "service_failed"
    
    # UI test events
    UI_TEST_START = "ui_test_start"
    UI_TEST_PASS = "ui_test_pass"
    UI_TEST_FAIL = "ui_test_fail"
    
    # Fix loop events
    FIX_LOOP_START = "fix_loop_start"
    FIX_LOOP_ITERATION = "fix_loop_iteration"
    FIX_LOOP_END = "fix_loop_end"
    
    # Checksum events
    CHECKSUM_VERIFIED = "checksum_verified"
    CHECKSUM_FAILED = "checksum_failed"


class TimelineLogger:
    """Logger for timeline events in JSONL format.
    
    Each event is written as a single JSON line with at minimum:
    - ts: ISO 8601 timestamp
    - event: Event type from EventType enum
    
    Additional fields depend on the event type.
    """
    
    def __init__(
        self,
        timeline_path: Path,
        session_id: Optional[str] = None,
    ):
        """Initialize timeline logger.
        
        Args:
            timeline_path: Path to timeline.jsonl file.
            session_id: Session ID to include in all events.
        """
        self.timeline_path = timeline_path
        self.session_id = session_id
        
        # Ensure parent directory exists
        self.timeline_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file if it doesn't exist
        if not self.timeline_path.exists():
            self.timeline_path.touch()
    
    def log(
        self,
        event: EventType,
        task_id: Optional[str] = None,
        role: Optional[str] = None,
        signal: Optional[str] = None,
        gate: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log an event to the timeline.
        
        Args:
            event: Event type.
            task_id: Associated task ID.
            role: Agent role (implementation, test_writing, review, etc.).
            signal: Signal received (task-done, tests-done, etc.).
            gate: Gate name.
            service: Service name (backend, frontend).
            status: Status string.
            duration_ms: Duration in milliseconds.
            error: Error message.
            details: Additional details as a dict.
            
        Returns:
            The event dict that was written.
        """
        event_data: Dict[str, Any] = {
            "ts": utc_now_iso(),
            "event": event.value if isinstance(event, EventType) else event,
        }
        
        # Add session ID if available
        if self.session_id:
            event_data["session_id"] = self.session_id
        
        # Add optional fields if provided
        if task_id is not None:
            event_data["task_id"] = task_id
        if role is not None:
            event_data["role"] = role
        if signal is not None:
            event_data["signal"] = signal
        if gate is not None:
            event_data["gate"] = gate
        if service is not None:
            event_data["service"] = service
        if status is not None:
            event_data["status"] = status
        if duration_ms is not None:
            event_data["duration_ms"] = duration_ms
        if error is not None:
            event_data["error"] = error
        if details is not None:
            event_data["details"] = details
        
        # Write as single JSON line
        line = json.dumps(event_data, separators=(",", ":")) + "\n"
        with self.timeline_path.open("a", encoding="utf-8") as f:
            f.write(line)
        
        return event_data
    
    # Convenience methods for common events
    
    def session_start(
        self,
        task_count: int,
        config_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log session start event."""
        return self.log(
            EventType.SESSION_START,
            details={
                "task_count": task_count,
                "config_path": config_path,
            },
        )
    
    def session_end(
        self,
        status: str,
        completed_count: int,
        total_count: int,
        duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log session end event."""
        return self.log(
            EventType.SESSION_END,
            status=status,
            duration_ms=duration_ms,
            details={
                "completed_count": completed_count,
                "total_count": total_count,
            },
        )
    
    def task_start(self, task_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Log task start event."""
        return self.log(
            EventType.TASK_START,
            task_id=task_id,
            details={"title": title} if title else None,
        )
    
    def task_complete(
        self,
        task_id: str,
        iterations: int,
        duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log task completion event."""
        return self.log(
            EventType.TASK_COMPLETE,
            task_id=task_id,
            duration_ms=duration_ms,
            details={"iterations": iterations},
        )
    
    def task_failed(
        self,
        task_id: str,
        reason: str,
        iterations: int,
    ) -> Dict[str, Any]:
        """Log task failure event."""
        return self.log(
            EventType.TASK_FAILED,
            task_id=task_id,
            error=reason,
            details={"iterations": iterations},
        )
    
    def agent_start(
        self,
        task_id: str,
        role: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log agent start event."""
        return self.log(
            EventType.AGENT_START,
            task_id=task_id,
            role=role,
            details={"model": model} if model else None,
        )
    
    def agent_complete(
        self,
        task_id: str,
        role: str,
        signal: str,
        duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log agent completion event."""
        return self.log(
            EventType.AGENT_COMPLETE,
            task_id=task_id,
            role=role,
            signal=signal,
            duration_ms=duration_ms,
        )
    
    def agent_failed(
        self,
        task_id: str,
        role: str,
        error: str,
        duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log agent failure event."""
        return self.log(
            EventType.AGENT_FAILED,
            task_id=task_id,
            role=role,
            error=error,
            duration_ms=duration_ms,
        )
    
    def gates_run(
        self,
        gate_type: str,
        gate_count: int,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log gates run start event."""
        return self.log(
            EventType.GATES_RUN,
            task_id=task_id,
            details={
                "gate_type": gate_type,
                "gate_count": gate_count,
            },
        )
    
    def gate_pass(
        self,
        gate_name: str,
        duration_ms: int,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log gate pass event."""
        return self.log(
            EventType.GATE_PASS,
            task_id=task_id,
            gate=gate_name,
            status="pass",
            duration_ms=duration_ms,
        )
    
    def gate_fail(
        self,
        gate_name: str,
        error: str,
        duration_ms: int,
        task_id: Optional[str] = None,
        fatal: bool = True,
    ) -> Dict[str, Any]:
        """Log gate failure event."""
        return self.log(
            EventType.GATE_FAIL,
            task_id=task_id,
            gate=gate_name,
            status="fail",
            error=error,
            duration_ms=duration_ms,
            details={"fatal": fatal},
        )
    
    def service_start(self, service: str, port: int) -> Dict[str, Any]:
        """Log service start event."""
        return self.log(
            EventType.SERVICE_START,
            service=service,
            details={"port": port},
        )
    
    def service_ready(
        self,
        service: str,
        url: str,
        duration_ms: int,
    ) -> Dict[str, Any]:
        """Log service ready event."""
        return self.log(
            EventType.SERVICE_READY,
            service=service,
            status="ready",
            duration_ms=duration_ms,
            details={"url": url},
        )
    
    def service_failed(
        self,
        service: str,
        error: str,
        duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log service failure event."""
        return self.log(
            EventType.SERVICE_FAILED,
            service=service,
            status="failed",
            error=error,
            duration_ms=duration_ms,
        )
    
    def ui_test_start(self, test_name: str, framework: str) -> Dict[str, Any]:
        """Log UI test start event."""
        return self.log(
            EventType.UI_TEST_START,
            details={
                "test_name": test_name,
                "framework": framework,
            },
        )
    
    def ui_test_pass(
        self,
        test_name: str,
        duration_ms: int,
    ) -> Dict[str, Any]:
        """Log UI test pass event."""
        return self.log(
            EventType.UI_TEST_PASS,
            status="pass",
            duration_ms=duration_ms,
            details={"test_name": test_name},
        )
    
    def ui_test_fail(
        self,
        test_name: str,
        error: str,
        screenshot: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log UI test failure event."""
        details: Dict[str, Any] = {"test_name": test_name}
        if screenshot:
            details["screenshot"] = screenshot
        return self.log(
            EventType.UI_TEST_FAIL,
            status="fail",
            error=error,
            duration_ms=duration_ms,
            details=details,
        )
    
    def fix_loop_start(
        self,
        loop_type: str,
        max_iterations: int,
    ) -> Dict[str, Any]:
        """Log fix loop start event."""
        return self.log(
            EventType.FIX_LOOP_START,
            details={
                "loop_type": loop_type,
                "max_iterations": max_iterations,
            },
        )
    
    def fix_loop_iteration(
        self,
        loop_type: str,
        iteration: int,
        status: str,
    ) -> Dict[str, Any]:
        """Log fix loop iteration event."""
        return self.log(
            EventType.FIX_LOOP_ITERATION,
            status=status,
            details={
                "loop_type": loop_type,
                "iteration": iteration,
            },
        )
    
    def fix_loop_end(
        self,
        loop_type: str,
        success: bool,
        iterations: int,
    ) -> Dict[str, Any]:
        """Log fix loop end event."""
        return self.log(
            EventType.FIX_LOOP_END,
            status="success" if success else "failed",
            details={
                "loop_type": loop_type,
                "iterations": iterations,
                "success": success,
            },
        )
    
    def checksum_verified(self) -> Dict[str, Any]:
        """Log successful checksum verification."""
        return self.log(EventType.CHECKSUM_VERIFIED, status="verified")
    
    def checksum_failed(self, error: str) -> Dict[str, Any]:
        """Log checksum verification failure."""
        return self.log(EventType.CHECKSUM_FAILED, status="failed", error=error)
    
    def read_events(self) -> list[Dict[str, Any]]:
        """Read all events from the timeline.
        
        Returns:
            List of event dictionaries.
        """
        events = []
        if self.timeline_path.exists():
            with self.timeline_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass  # Skip malformed lines
        return events
    
    def get_events_by_type(self, event_type: EventType) -> list[Dict[str, Any]]:
        """Get all events of a specific type.
        
        Args:
            event_type: Event type to filter by.
            
        Returns:
            List of matching event dictionaries.
        """
        target = event_type.value if isinstance(event_type, EventType) else event_type
        return [e for e in self.read_events() if e.get("event") == target]
    
    def get_events_for_task(self, task_id: str) -> list[Dict[str, Any]]:
        """Get all events for a specific task.
        
        Args:
            task_id: Task ID to filter by.
            
        Returns:
            List of matching event dictionaries.
        """
        return [e for e in self.read_events() if e.get("task_id") == task_id]


def create_timeline_logger(
    session_dir: Path,
    session_id: Optional[str] = None,
) -> TimelineLogger:
    """Create a timeline logger for a session.
    
    Args:
        session_dir: Path to session directory.
        session_id: Session ID to include in events.
        
    Returns:
        TimelineLogger instance.
    """
    timeline_path = session_dir / "logs" / "timeline.jsonl"
    return TimelineLogger(timeline_path, session_id=session_id)
