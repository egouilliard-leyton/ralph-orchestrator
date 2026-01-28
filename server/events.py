"""Event system for real-time broadcasting.

This module provides the event infrastructure for broadcasting real-time updates
from Ralph services to WebSocket clients. It implements:

- Event base class with common fields (type, project_id, timestamp)
- Typed event classes for all UI update scenarios
- EventEmitter with subscribe/emit pattern
- EventQueue for buffering events before WebSocket broadcast

Events are designed to be serialized to JSON for WebSocket transmission and
integrate with all existing Ralph services (orchestration, session, config, git).

Usage:
    from server.events import (
        EventEmitter,
        EventQueue,
        EventType,
        TaskStartedEvent,
        TaskCompletedEvent,
    )

    # Create emitter and queue
    emitter = EventEmitter()
    queue = EventQueue(max_size=1000)

    # Subscribe to specific events
    emitter.subscribe(EventType.TASK_STARTED, lambda e: print(f"Task started: {e.task_id}"))

    # Subscribe to all events
    emitter.subscribe_all(queue.enqueue)

    # Emit events
    emitter.emit(TaskStartedEvent(
        project_id="my-project",
        task_id="T-001",
        task_title="Implement feature",
    ))

    # Get queued events for WebSocket broadcast
    events = queue.dequeue_all()
"""

from __future__ import annotations

import asyncio
import time
import uuid
from abc import ABC
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Union


class EventType(str, Enum):
    """Types of events emitted for real-time UI updates.

    Events are grouped by category:
    - Task lifecycle: TASK_STARTED, TASK_COMPLETED
    - Agent execution: AGENT_OUTPUT, AGENT_PHASE_CHANGED
    - Quality gates: GATE_RUNNING, GATE_COMPLETED
    - Signals: SIGNAL_DETECTED
    - Session management: SESSION_CHANGED
    - Configuration: CONFIG_CHANGED
    """

    # Task lifecycle events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"

    # Agent execution events
    AGENT_OUTPUT = "agent_output"
    AGENT_PHASE_CHANGED = "agent_phase_changed"

    # Quality gate events
    GATE_RUNNING = "gate_running"
    GATE_COMPLETED = "gate_completed"

    # Signal events
    SIGNAL_DETECTED = "signal_detected"

    # Session events
    SESSION_CHANGED = "session_changed"

    # Configuration events
    CONFIG_CHANGED = "config_changed"


@dataclass
class Event(ABC):
    """Base class for all events.

    All events include:
    - event_type: The type of event (from EventType enum)
    - project_id: ID of the project this event relates to
    - timestamp: Unix timestamp when the event was created
    - event_id: Unique identifier for this event instance

    Subclasses add type-specific data fields.
    """

    event_type: EventType
    project_id: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization.

        Returns:
            Dictionary with event data suitable for JSON encoding.
        """
        return {
            "event_type": self.event_type.value,
            "project_id": self.project_id,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }


# =============================================================================
# Task lifecycle events
# =============================================================================


@dataclass
class TaskStartedEvent(Event):
    """Event emitted when a task begins execution.

    Attributes:
        task_id: Unique identifier for the task (e.g., "T-001")
        task_title: Human-readable title of the task
        total_tasks: Total number of tasks in the session
        task_index: Index of this task (1-based) in the session
    """

    event_type: EventType = field(init=False, default=EventType.TASK_STARTED)
    task_id: str = ""
    task_title: str = ""
    total_tasks: int = 0
    task_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "task_title": self.task_title,
            "total_tasks": self.total_tasks,
            "task_index": self.task_index,
        })
        return d


@dataclass
class TaskCompletedEvent(Event):
    """Event emitted when a task finishes execution (success or failure).

    Attributes:
        task_id: Unique identifier for the task
        success: Whether the task completed successfully
        iterations: Number of iterations taken to complete
        duration_ms: Total duration in milliseconds
        failure_reason: Reason for failure (if success is False)
    """

    event_type: EventType = field(init=False, default=EventType.TASK_COMPLETED)
    task_id: str = ""
    success: bool = False
    iterations: int = 0
    duration_ms: int = 0
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "success": self.success,
            "iterations": self.iterations,
            "duration_ms": self.duration_ms,
            "failure_reason": self.failure_reason,
        })
        return d


# =============================================================================
# Agent execution events
# =============================================================================


@dataclass
class AgentOutputEvent(Event):
    """Event emitted when an agent produces output.

    Used for streaming agent output to the UI in real-time.

    Attributes:
        task_id: Task the agent is working on
        agent_role: Role of the agent (implementation, test_writing, review, fix)
        output: The output text/content from the agent
        is_complete: Whether this is the final output chunk
        iteration: Current iteration number
    """

    event_type: EventType = field(init=False, default=EventType.AGENT_OUTPUT)
    task_id: str = ""
    agent_role: str = ""  # "implementation", "test_writing", "review", "fix"
    output: str = ""
    is_complete: bool = False
    iteration: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "agent_role": self.agent_role,
            "output": self.output,
            "is_complete": self.is_complete,
            "iteration": self.iteration,
        })
        return d


@dataclass
class AgentPhaseChangedEvent(Event):
    """Event emitted when transitioning between agent phases.

    Attributes:
        task_id: Task being executed
        phase: New phase (implementation, test_writing, review, fix)
        previous_phase: Previous phase (None if this is the first phase)
        iteration: Current iteration number
    """

    event_type: EventType = field(init=False, default=EventType.AGENT_PHASE_CHANGED)
    task_id: str = ""
    phase: str = ""  # "implementation", "test_writing", "review", "fix"
    previous_phase: Optional[str] = None
    iteration: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "phase": self.phase,
            "previous_phase": self.previous_phase,
            "iteration": self.iteration,
        })
        return d


# =============================================================================
# Quality gate events
# =============================================================================


@dataclass
class GateRunningEvent(Event):
    """Event emitted when a quality gate starts running.

    Attributes:
        task_id: Task being validated
        gate_name: Name of the gate (e.g., "lint", "test")
        gate_type: Type of gate (build or full)
        gate_index: Index of this gate (1-based) in the sequence
        total_gates: Total number of gates to run
    """

    event_type: EventType = field(init=False, default=EventType.GATE_RUNNING)
    task_id: str = ""
    gate_name: str = ""
    gate_type: str = ""  # "build" or "full"
    gate_index: int = 0
    total_gates: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "gate_name": self.gate_name,
            "gate_type": self.gate_type,
            "gate_index": self.gate_index,
            "total_gates": self.total_gates,
        })
        return d


@dataclass
class GateCompletedEvent(Event):
    """Event emitted when a quality gate finishes.

    Attributes:
        task_id: Task being validated
        gate_name: Name of the gate
        gate_type: Type of gate (build or full)
        passed: Whether the gate passed
        duration_ms: How long the gate took in milliseconds
        output: Output from the gate command (especially on failure)
        exit_code: Exit code from the gate command
    """

    event_type: EventType = field(init=False, default=EventType.GATE_COMPLETED)
    task_id: str = ""
    gate_name: str = ""
    gate_type: str = ""
    passed: bool = False
    duration_ms: int = 0
    output: Optional[str] = None
    exit_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "gate_name": self.gate_name,
            "gate_type": self.gate_type,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "output": self.output,
            "exit_code": self.exit_code,
        })
        return d


# =============================================================================
# Signal events
# =============================================================================


@dataclass
class SignalDetectedEvent(Event):
    """Event emitted when an agent completion signal is detected.

    Signals indicate agent phase completion and include anti-gaming tokens.

    Attributes:
        task_id: Task the signal relates to
        signal_type: Type of signal (task-done, tests-done, review-approved, etc.)
        valid: Whether the signal was valid (correct format)
        token_valid: Whether the session token matched (anti-gaming check)
        agent_role: Role of the agent that emitted the signal
        content: Content/summary from the signal
    """

    event_type: EventType = field(init=False, default=EventType.SIGNAL_DETECTED)
    task_id: str = ""
    signal_type: str = ""  # "task-done", "tests-done", "review-approved", "review-rejected", "fix-done"
    valid: bool = False
    token_valid: bool = False
    agent_role: str = ""
    content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "signal_type": self.signal_type,
            "valid": self.valid,
            "token_valid": self.token_valid,
            "agent_role": self.agent_role,
            "content": self.content,
        })
        return d


# =============================================================================
# Session events
# =============================================================================


@dataclass
class SessionChangedEvent(Event):
    """Event emitted when session state changes.

    Covers session creation, loading, status changes, and task status updates.

    Attributes:
        session_id: Unique session identifier
        change_type: Type of change (created, loaded, ended, task_started, task_completed, etc.)
        status: Current session status
        tasks_completed: Number of completed tasks
        tasks_pending: Number of pending tasks
        tasks_failed: Number of failed tasks
        current_task: Currently executing task ID (if any)
        failure_reason: Reason for session failure (if applicable)
        metadata: Additional metadata about the change
    """

    event_type: EventType = field(init=False, default=EventType.SESSION_CHANGED)
    session_id: str = ""
    change_type: str = ""  # "created", "loaded", "ended", "status_changed", "task_started", "task_completed", "task_failed"
    status: str = ""  # "running", "completed", "failed", "aborted"
    tasks_completed: int = 0
    tasks_pending: int = 0
    tasks_failed: int = 0
    current_task: Optional[str] = None
    failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "session_id": self.session_id,
            "change_type": self.change_type,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_pending": self.tasks_pending,
            "tasks_failed": self.tasks_failed,
            "current_task": self.current_task,
            "failure_reason": self.failure_reason,
            "metadata": self.metadata,
        })
        return d


# =============================================================================
# Configuration events
# =============================================================================


@dataclass
class ConfigChangedEvent(Event):
    """Event emitted when configuration changes.

    Covers config creation, updates, deletion, and validation failures.

    Attributes:
        config_path: Path to the configuration file
        change_type: Type of change (created, updated, deleted, reloaded, validation_failed)
        changes: Dictionary of changed fields (for updates)
        errors: List of validation errors (for validation_failed)
        version: Configuration version
    """

    event_type: EventType = field(init=False, default=EventType.CONFIG_CHANGED)
    config_path: str = ""
    change_type: str = ""  # "created", "updated", "deleted", "reloaded", "validation_failed"
    changes: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
            "change_type": self.change_type,
            "changes": self.changes,
            "errors": self.errors,
            "version": self.version,
        })
        return d


# =============================================================================
# Event handler type aliases
# =============================================================================

EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]  # Can be sync or async


# =============================================================================
# EventEmitter class
# =============================================================================


class EventEmitter:
    """Event emitter with subscribe/emit pattern.

    Provides a pub/sub mechanism for events. Handlers can subscribe to:
    - Specific event types
    - All events
    - Specific project IDs

    Thread-safe for concurrent emit/subscribe operations.

    Usage:
        emitter = EventEmitter()

        # Subscribe to specific event type
        emitter.subscribe(EventType.TASK_STARTED, my_handler)

        # Subscribe to all events
        emitter.subscribe_all(my_global_handler)

        # Subscribe to events for specific project
        emitter.subscribe_project("my-project", my_project_handler)

        # Emit an event
        emitter.emit(TaskStartedEvent(project_id="my-project", task_id="T-001"))
    """

    def __init__(self):
        """Initialize the event emitter."""
        # Handlers for specific event types
        self._type_handlers: Dict[EventType, List[EventHandler]] = {
            event_type: [] for event_type in EventType
        }

        # Handlers for all events
        self._global_handlers: List[EventHandler] = []

        # Handlers for specific projects
        self._project_handlers: Dict[str, List[EventHandler]] = {}

        # Lock for thread safety
        self._lock = Lock()

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: The type of event to subscribe to.
            handler: Callable that receives the event.
        """
        with self._lock:
            if handler not in self._type_handlers[event_type]:
                self._type_handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events.

        Args:
            handler: Callable that receives any event.
        """
        with self._lock:
            if handler not in self._global_handlers:
                self._global_handlers.append(handler)

    def subscribe_project(self, project_id: str, handler: EventHandler) -> None:
        """Subscribe to events for a specific project.

        Args:
            project_id: ID of the project to subscribe to.
            handler: Callable that receives events for this project.
        """
        with self._lock:
            if project_id not in self._project_handlers:
                self._project_handlers[project_id] = []
            if handler not in self._project_handlers[project_id]:
                self._project_handlers[project_id].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from a specific event type.

        Args:
            event_type: The type of event.
            handler: The handler to remove.
        """
        with self._lock:
            if handler in self._type_handlers[event_type]:
                self._type_handlers[event_type].remove(handler)

    def unsubscribe_all(self, handler: EventHandler) -> None:
        """Unsubscribe a global handler.

        Args:
            handler: The handler to remove.
        """
        with self._lock:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)

    def unsubscribe_project(self, project_id: str, handler: EventHandler) -> None:
        """Unsubscribe from project events.

        Args:
            project_id: ID of the project.
            handler: The handler to remove.
        """
        with self._lock:
            if project_id in self._project_handlers:
                if handler in self._project_handlers[project_id]:
                    self._project_handlers[project_id].remove(handler)
                # Clean up empty lists
                if not self._project_handlers[project_id]:
                    del self._project_handlers[project_id]

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribed handlers.

        Events are delivered to:
        1. Type-specific handlers
        2. Global handlers
        3. Project-specific handlers (if project_id matches)

        Handler exceptions are caught and logged but don't prevent
        delivery to other handlers.

        Args:
            event: The event to emit.
        """
        with self._lock:
            # Get copies of handler lists to avoid modification during iteration
            type_handlers = list(self._type_handlers.get(event.event_type, []))
            global_handlers = list(self._global_handlers)
            project_handlers = list(self._project_handlers.get(event.project_id, []))

        # Call type-specific handlers
        for handler in type_handlers:
            try:
                handler(event)
            except Exception:
                # Don't let handler errors break emission
                pass

        # Call global handlers
        for handler in global_handlers:
            try:
                handler(event)
            except Exception:
                pass

        # Call project-specific handlers
        for handler in project_handlers:
            try:
                handler(event)
            except Exception:
                pass

    async def emit_async(self, event: Event) -> None:
        """Emit an event asynchronously.

        Similar to emit() but awaits coroutine handlers.

        Args:
            event: The event to emit.
        """
        with self._lock:
            type_handlers = list(self._type_handlers.get(event.event_type, []))
            global_handlers = list(self._global_handlers)
            project_handlers = list(self._project_handlers.get(event.project_id, []))

        all_handlers = type_handlers + global_handlers + project_handlers

        for handler in all_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    def clear_handlers(self, event_type: Optional[EventType] = None) -> None:
        """Clear handlers.

        Args:
            event_type: If specified, clear only handlers for this type.
                       If None, clear all handlers.
        """
        with self._lock:
            if event_type is not None:
                self._type_handlers[event_type] = []
            else:
                for et in EventType:
                    self._type_handlers[et] = []
                self._global_handlers = []
                self._project_handlers = {}

    def handler_count(self, event_type: Optional[EventType] = None) -> int:
        """Get the number of registered handlers.

        Args:
            event_type: If specified, count only handlers for this type.
                       If None, count all handlers.

        Returns:
            Number of registered handlers.
        """
        with self._lock:
            if event_type is not None:
                return len(self._type_handlers.get(event_type, []))
            else:
                count = len(self._global_handlers)
                for handlers in self._type_handlers.values():
                    count += len(handlers)
                for handlers in self._project_handlers.values():
                    count += len(handlers)
                return count


# =============================================================================
# EventQueue class
# =============================================================================


class EventQueue:
    """Queue for buffering events before WebSocket broadcast.

    Events are enqueued as they're emitted and dequeued for broadcast
    to WebSocket clients. Supports:
    - Maximum queue size with oldest-event eviction
    - Thread-safe operations
    - Filtering by event type or project ID
    - Async support for WebSocket integration

    Usage:
        queue = EventQueue(max_size=1000)

        # Enqueue events (typically from EventEmitter)
        queue.enqueue(event)

        # Dequeue all events for broadcast
        events = queue.dequeue_all()

        # Dequeue with filter
        task_events = queue.dequeue_all(event_types={EventType.TASK_STARTED, EventType.TASK_COMPLETED})

        # Async dequeue (waits for events if queue is empty)
        events = await queue.dequeue_async(timeout=5.0)
    """

    def __init__(self, max_size: int = 1000):
        """Initialize the event queue.

        Args:
            max_size: Maximum number of events to buffer. Oldest events
                     are evicted when this limit is reached.
        """
        self._max_size = max_size
        self._queue: Deque[Event] = deque(maxlen=max_size)
        self._lock = Lock()
        self._event = asyncio.Event() if asyncio.get_event_loop_policy() else None
        self._async_event: Optional[asyncio.Event] = None

    def _get_async_event(self) -> asyncio.Event:
        """Get or create the async event for signaling."""
        if self._async_event is None:
            self._async_event = asyncio.Event()
        return self._async_event

    def enqueue(self, event: Event) -> None:
        """Add an event to the queue.

        Thread-safe. If the queue is at max capacity, the oldest
        event is automatically evicted.

        Args:
            event: The event to enqueue.
        """
        with self._lock:
            self._queue.append(event)

        # Signal async waiters
        if self._async_event is not None:
            self._async_event.set()

    def dequeue(self) -> Optional[Event]:
        """Remove and return the oldest event from the queue.

        Returns:
            The oldest event, or None if the queue is empty.
        """
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def dequeue_all(
        self,
        event_types: Optional[Set[EventType]] = None,
        project_id: Optional[str] = None,
    ) -> List[Event]:
        """Remove and return all events from the queue.

        Args:
            event_types: If specified, only return events of these types.
            project_id: If specified, only return events for this project.

        Returns:
            List of events (empty if queue is empty).
        """
        with self._lock:
            if not self._queue:
                return []

            # Get all events
            events = list(self._queue)
            self._queue.clear()

        # Apply filters if specified
        if event_types is not None:
            events = [e for e in events if e.event_type in event_types]

        if project_id is not None:
            events = [e for e in events if e.project_id == project_id]

        return events

    async def dequeue_async(
        self,
        timeout: Optional[float] = None,
        event_types: Optional[Set[EventType]] = None,
        project_id: Optional[str] = None,
    ) -> List[Event]:
        """Asynchronously dequeue events, waiting if queue is empty.

        Args:
            timeout: Maximum time to wait in seconds. None means wait forever.
            event_types: If specified, only return events of these types.
            project_id: If specified, only return events for this project.

        Returns:
            List of events.
        """
        async_event = self._get_async_event()

        # Check if we have events already
        events = self.dequeue_all(event_types=event_types, project_id=project_id)
        if events:
            return events

        # Wait for events
        try:
            await asyncio.wait_for(async_event.wait(), timeout=timeout)
            async_event.clear()
        except asyncio.TimeoutError:
            pass

        return self.dequeue_all(event_types=event_types, project_id=project_id)

    def peek(self) -> Optional[Event]:
        """Return the oldest event without removing it.

        Returns:
            The oldest event, or None if the queue is empty.
        """
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def peek_all(self) -> List[Event]:
        """Return all events without removing them.

        Returns:
            List of all events in the queue.
        """
        with self._lock:
            return list(self._queue)

    def size(self) -> int:
        """Get the current number of events in the queue.

        Returns:
            Number of events.
        """
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if the queue has no events.
        """
        with self._lock:
            return len(self._queue) == 0

    def clear(self) -> int:
        """Clear all events from the queue.

        Returns:
            Number of events that were cleared.
        """
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    @property
    def max_size(self) -> int:
        """Get the maximum queue size."""
        return self._max_size


# =============================================================================
# Service bridge functions
# =============================================================================


def create_service_bridge(
    emitter: EventEmitter,
    project_id: str,
) -> Dict[str, Callable]:
    """Create bridge functions to connect existing services to the event emitter.

    This function returns handlers that can be registered with existing service
    event systems to forward events to the centralized EventEmitter.

    Args:
        emitter: The EventEmitter to forward events to.
        project_id: The project ID to use for emitted events.

    Returns:
        Dictionary of handler functions keyed by service name.

    Usage:
        bridge = create_service_bridge(emitter, "my-project")

        # Register with OrchestrationService
        orchestration_service.on_all_events(bridge["orchestration"])

        # Register with SessionService
        session_service.on_all_events(bridge["session"])
    """

    def orchestration_handler(service_event: Any) -> None:
        """Bridge OrchestrationService events to EventEmitter."""
        event_type_map = {
            "task_started": EventType.TASK_STARTED,
            "task_completed": EventType.TASK_COMPLETED,
            "agent_phase_changed": EventType.AGENT_PHASE_CHANGED,
            "gate_running": EventType.GATE_RUNNING,
            "gate_completed": EventType.GATE_COMPLETED,
            "signal_detected": EventType.SIGNAL_DETECTED,
        }

        service_type = getattr(service_event, "event_type", None)
        if service_type is None:
            return

        service_type_value = service_type.value if hasattr(service_type, "value") else str(service_type)

        if service_type_value == "task_started":
            emitter.emit(TaskStartedEvent(
                project_id=project_id,
                task_id=getattr(service_event, "task_id", ""),
                task_title=getattr(service_event, "task_title", ""),
            ))
        elif service_type_value == "task_completed":
            emitter.emit(TaskCompletedEvent(
                project_id=project_id,
                task_id=getattr(service_event, "task_id", ""),
                success=getattr(service_event, "success", False),
                iterations=getattr(service_event, "iterations", 0),
                duration_ms=getattr(service_event, "duration_ms", 0),
                failure_reason=getattr(service_event, "failure_reason", None),
            ))
        elif service_type_value == "agent_phase_changed":
            emitter.emit(AgentPhaseChangedEvent(
                project_id=project_id,
                task_id=getattr(service_event, "task_id", ""),
                phase=getattr(service_event, "phase", ""),
                previous_phase=getattr(service_event, "previous_phase", None),
            ))
        elif service_type_value == "gate_running":
            emitter.emit(GateRunningEvent(
                project_id=project_id,
                task_id=getattr(service_event, "task_id", ""),
                gate_name=getattr(service_event, "gate_name", ""),
                gate_type=getattr(service_event, "gate_type", ""),
            ))
        elif service_type_value == "gate_completed":
            emitter.emit(GateCompletedEvent(
                project_id=project_id,
                task_id=getattr(service_event, "task_id", ""),
                gate_name=getattr(service_event, "gate_name", ""),
                gate_type=getattr(service_event, "gate_type", ""),
                passed=getattr(service_event, "passed", False),
                duration_ms=getattr(service_event, "duration_ms", 0),
                output=getattr(service_event, "output", None),
            ))
        elif service_type_value == "signal_detected":
            emitter.emit(SignalDetectedEvent(
                project_id=project_id,
                task_id=getattr(service_event, "task_id", ""),
                signal_type=getattr(service_event, "signal_type", ""),
                valid=getattr(service_event, "valid", False),
                token_valid=getattr(service_event, "token_valid", False),
                agent_role=getattr(service_event, "agent_role", ""),
                content=getattr(service_event, "content", None),
            ))

    def session_handler(service_event: Any) -> None:
        """Bridge SessionService events to EventEmitter."""
        service_type = getattr(service_event, "event_type", None)
        if service_type is None:
            return

        service_type_value = service_type.value if hasattr(service_type, "value") else str(service_type)

        # Map session events to SessionChangedEvent
        change_type_map = {
            "session_created": "created",
            "session_loaded": "loaded",
            "session_ended": "ended",
            "session_deleted": "deleted",
            "task_started": "task_started",
            "task_completed": "task_completed",
            "task_failed": "task_failed",
            "status_changed": "status_changed",
        }

        change_type = change_type_map.get(service_type_value)
        if change_type:
            emitter.emit(SessionChangedEvent(
                project_id=project_id,
                session_id=getattr(service_event, "session_id", ""),
                change_type=change_type,
                status=getattr(service_event, "status", ""),
                tasks_completed=getattr(service_event, "tasks_completed", 0),
                tasks_pending=getattr(service_event, "tasks_pending", 0),
                tasks_failed=getattr(service_event, "tasks_failed", 0),
                current_task=getattr(service_event, "task_id", None),
                failure_reason=getattr(service_event, "failure_reason", None),
            ))

    def config_handler(service_event: Any) -> None:
        """Bridge ConfigService events to EventEmitter."""
        service_type = getattr(service_event, "event_type", None)
        if service_type is None:
            return

        service_type_value = service_type.value if hasattr(service_type, "value") else str(service_type)

        change_type_map = {
            "config_loaded": "loaded",
            "config_updated": "updated",
            "config_created": "created",
            "config_deleted": "deleted",
            "config_reloaded": "reloaded",
            "config_validation_failed": "validation_failed",
        }

        change_type = change_type_map.get(service_type_value)
        if change_type:
            emitter.emit(ConfigChangedEvent(
                project_id=project_id,
                config_path=getattr(service_event, "config_path", ""),
                change_type=change_type,
                changes=getattr(service_event, "changes", {}),
                errors=getattr(service_event, "errors", []),
                version=getattr(service_event, "version", ""),
            ))

    def git_handler(service_event: Any) -> None:
        """Bridge GitService events to EventEmitter.

        Git events are converted to metadata in SessionChangedEvent for now,
        as they're typically related to session state.
        """
        service_type = getattr(service_event, "event_type", None)
        if service_type is None:
            return

        service_type_value = service_type.value if hasattr(service_type, "value") else str(service_type)

        # Git events are typically associated with session changes
        metadata = {
            "git_event": service_type_value,
        }

        if service_type_value == "branch_created":
            metadata["branch_name"] = getattr(service_event, "branch_name", "")
            metadata["base_branch"] = getattr(service_event, "base_branch", "")
        elif service_type_value == "commit_created":
            metadata["commit_hash"] = getattr(service_event, "commit_hash", "")
            metadata["message"] = getattr(service_event, "message", "")
        elif service_type_value == "pr_created":
            metadata["pr_number"] = getattr(service_event, "pr_number", 0)
            metadata["pr_url"] = getattr(service_event, "pr_url", "")

        emitter.emit(SessionChangedEvent(
            project_id=project_id,
            session_id="",
            change_type="git_update",
            status="",
            metadata=metadata,
        ))

    return {
        "orchestration": orchestration_handler,
        "session": session_handler,
        "config": config_handler,
        "git": git_handler,
    }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Event type enum
    "EventType",
    # Base event class
    "Event",
    # Specific event classes
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "AgentOutputEvent",
    "AgentPhaseChangedEvent",
    "GateRunningEvent",
    "GateCompletedEvent",
    "SignalDetectedEvent",
    "SessionChangedEvent",
    "ConfigChangedEvent",
    # Handler type aliases
    "EventHandler",
    "AsyncEventHandler",
    # Core classes
    "EventEmitter",
    "EventQueue",
    # Service bridge
    "create_service_bridge",
]
