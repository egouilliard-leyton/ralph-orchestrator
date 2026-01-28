"""Unit tests for the event system.

Tests cover:
- Event class serialization (to_dict)
- EventEmitter subscribe/emit pattern
- EventQueue buffering and dequeuing
- Service bridge integration
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from server.events import (
    Event,
    EventType,
    EventEmitter,
    EventQueue,
    TaskStartedEvent,
    TaskCompletedEvent,
    AgentOutputEvent,
    AgentPhaseChangedEvent,
    GateRunningEvent,
    GateCompletedEvent,
    SignalDetectedEvent,
    SessionChangedEvent,
    ConfigChangedEvent,
    create_service_bridge,
)


# =============================================================================
# Event class tests
# =============================================================================


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_are_strings(self):
        """All event types should be string values."""
        for event_type in EventType:
            assert isinstance(event_type.value, str)

    def test_required_event_types_exist(self):
        """All required event types should be defined."""
        required_types = [
            "task_started",
            "task_completed",
            "agent_output",
            "agent_phase_changed",
            "gate_running",
            "gate_completed",
            "signal_detected",
            "session_changed",
            "config_changed",
        ]
        values = [e.value for e in EventType]
        for required in required_types:
            assert required in values, f"Missing event type: {required}"


class TestTaskStartedEvent:
    """Tests for TaskStartedEvent."""

    def test_create_with_defaults(self):
        """Event can be created with minimal parameters."""
        event = TaskStartedEvent(project_id="test-project")
        assert event.event_type == EventType.TASK_STARTED
        assert event.project_id == "test-project"
        assert event.task_id == ""
        assert event.task_title == ""
        assert event.timestamp > 0
        assert event.event_id is not None

    def test_create_with_all_fields(self):
        """Event can be created with all fields."""
        event = TaskStartedEvent(
            project_id="test-project",
            task_id="T-001",
            task_title="Implement feature",
            total_tasks=5,
            task_index=1,
        )
        assert event.task_id == "T-001"
        assert event.task_title == "Implement feature"
        assert event.total_tasks == 5
        assert event.task_index == 1

    def test_to_dict(self):
        """to_dict returns serializable dictionary."""
        event = TaskStartedEvent(
            project_id="test-project",
            task_id="T-001",
            task_title="Implement feature",
            total_tasks=5,
            task_index=1,
        )
        d = event.to_dict()

        assert d["event_type"] == "task_started"
        assert d["project_id"] == "test-project"
        assert d["task_id"] == "T-001"
        assert d["task_title"] == "Implement feature"
        assert d["total_tasks"] == 5
        assert d["task_index"] == 1
        assert "timestamp" in d
        assert "event_id" in d


class TestTaskCompletedEvent:
    """Tests for TaskCompletedEvent."""

    def test_create_success(self):
        """Event for successful task completion."""
        event = TaskCompletedEvent(
            project_id="test-project",
            task_id="T-001",
            success=True,
            iterations=3,
            duration_ms=5000,
        )
        assert event.event_type == EventType.TASK_COMPLETED
        assert event.success is True
        assert event.failure_reason is None

    def test_create_failure(self):
        """Event for failed task completion."""
        event = TaskCompletedEvent(
            project_id="test-project",
            task_id="T-001",
            success=False,
            iterations=10,
            duration_ms=30000,
            failure_reason="Max iterations reached",
        )
        assert event.success is False
        assert event.failure_reason == "Max iterations reached"

    def test_to_dict(self):
        """to_dict includes all fields."""
        event = TaskCompletedEvent(
            project_id="test-project",
            task_id="T-001",
            success=False,
            iterations=10,
            duration_ms=30000,
            failure_reason="Max iterations reached",
        )
        d = event.to_dict()

        assert d["success"] is False
        assert d["iterations"] == 10
        assert d["duration_ms"] == 30000
        assert d["failure_reason"] == "Max iterations reached"


class TestAgentOutputEvent:
    """Tests for AgentOutputEvent."""

    def test_create_streaming_output(self):
        """Event for streaming agent output."""
        event = AgentOutputEvent(
            project_id="test-project",
            task_id="T-001",
            agent_role="implementation",
            output="Starting implementation...",
            is_complete=False,
            iteration=1,
        )
        assert event.event_type == EventType.AGENT_OUTPUT
        assert event.agent_role == "implementation"
        assert event.is_complete is False

    def test_to_dict(self):
        """to_dict includes agent-specific fields."""
        event = AgentOutputEvent(
            project_id="test-project",
            task_id="T-001",
            agent_role="review",
            output="Review complete",
            is_complete=True,
            iteration=2,
        )
        d = event.to_dict()

        assert d["agent_role"] == "review"
        assert d["output"] == "Review complete"
        assert d["is_complete"] is True
        assert d["iteration"] == 2


class TestAgentPhaseChangedEvent:
    """Tests for AgentPhaseChangedEvent."""

    def test_first_phase(self):
        """Event for initial phase (no previous phase)."""
        event = AgentPhaseChangedEvent(
            project_id="test-project",
            task_id="T-001",
            phase="implementation",
            previous_phase=None,
            iteration=1,
        )
        assert event.phase == "implementation"
        assert event.previous_phase is None

    def test_phase_transition(self):
        """Event for phase transition."""
        event = AgentPhaseChangedEvent(
            project_id="test-project",
            task_id="T-001",
            phase="test_writing",
            previous_phase="implementation",
            iteration=1,
        )
        assert event.phase == "test_writing"
        assert event.previous_phase == "implementation"


class TestGateRunningEvent:
    """Tests for GateRunningEvent."""

    def test_create(self):
        """Event for gate starting."""
        event = GateRunningEvent(
            project_id="test-project",
            task_id="T-001",
            gate_name="lint",
            gate_type="build",
            gate_index=1,
            total_gates=3,
        )
        assert event.event_type == EventType.GATE_RUNNING
        assert event.gate_name == "lint"
        assert event.gate_type == "build"


class TestGateCompletedEvent:
    """Tests for GateCompletedEvent."""

    def test_create_passed(self):
        """Event for passed gate."""
        event = GateCompletedEvent(
            project_id="test-project",
            task_id="T-001",
            gate_name="lint",
            gate_type="build",
            passed=True,
            duration_ms=1500,
        )
        assert event.passed is True
        assert event.output is None

    def test_create_failed(self):
        """Event for failed gate."""
        event = GateCompletedEvent(
            project_id="test-project",
            task_id="T-001",
            gate_name="test",
            gate_type="full",
            passed=False,
            duration_ms=5000,
            output="3 tests failed",
            exit_code=1,
        )
        assert event.passed is False
        assert event.output == "3 tests failed"
        assert event.exit_code == 1


class TestSignalDetectedEvent:
    """Tests for SignalDetectedEvent."""

    def test_valid_signal(self):
        """Event for valid signal detection."""
        event = SignalDetectedEvent(
            project_id="test-project",
            task_id="T-001",
            signal_type="task-done",
            valid=True,
            token_valid=True,
            agent_role="implementation",
            content="Implementation complete",
        )
        assert event.event_type == EventType.SIGNAL_DETECTED
        assert event.valid is True
        assert event.token_valid is True

    def test_invalid_token(self):
        """Event for signal with invalid token."""
        event = SignalDetectedEvent(
            project_id="test-project",
            task_id="T-001",
            signal_type="task-done",
            valid=True,
            token_valid=False,
            agent_role="implementation",
        )
        assert event.valid is True
        assert event.token_valid is False


class TestSessionChangedEvent:
    """Tests for SessionChangedEvent."""

    def test_session_created(self):
        """Event for session creation."""
        event = SessionChangedEvent(
            project_id="test-project",
            session_id="20260127-120000-abc123",
            change_type="created",
            status="running",
            tasks_pending=5,
        )
        assert event.event_type == EventType.SESSION_CHANGED
        assert event.change_type == "created"

    def test_session_ended(self):
        """Event for session end."""
        event = SessionChangedEvent(
            project_id="test-project",
            session_id="20260127-120000-abc123",
            change_type="ended",
            status="completed",
            tasks_completed=5,
            tasks_pending=0,
        )
        assert event.change_type == "ended"
        assert event.status == "completed"


class TestConfigChangedEvent:
    """Tests for ConfigChangedEvent."""

    def test_config_updated(self):
        """Event for config update."""
        event = ConfigChangedEvent(
            project_id="test-project",
            config_path="/path/to/ralph.yml",
            change_type="updated",
            changes={"gates.full": [{"name": "test", "cmd": "pytest"}]},
            version="1",
        )
        assert event.event_type == EventType.CONFIG_CHANGED
        assert event.change_type == "updated"
        assert "gates.full" in event.changes

    def test_validation_failed(self):
        """Event for validation failure."""
        event = ConfigChangedEvent(
            project_id="test-project",
            config_path="/path/to/ralph.yml",
            change_type="validation_failed",
            errors=["Invalid task_source type"],
        )
        assert event.change_type == "validation_failed"
        assert len(event.errors) == 1


# =============================================================================
# EventEmitter tests
# =============================================================================


class TestEventEmitter:
    """Tests for EventEmitter class."""

    def test_subscribe_and_emit(self):
        """Subscribe to event type and emit event."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        def handler(event: Event):
            received_events.append(event)

        emitter.subscribe(EventType.TASK_STARTED, handler)

        event = TaskStartedEvent(project_id="test")
        emitter.emit(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    def test_subscribe_all(self):
        """Global handler receives all events."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        emitter.subscribe_all(lambda e: received_events.append(e))

        emitter.emit(TaskStartedEvent(project_id="test"))
        emitter.emit(TaskCompletedEvent(project_id="test"))

        assert len(received_events) == 2

    def test_subscribe_project(self):
        """Project handler only receives events for that project."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        emitter.subscribe_project("project-a", lambda e: received_events.append(e))

        emitter.emit(TaskStartedEvent(project_id="project-a"))
        emitter.emit(TaskStartedEvent(project_id="project-b"))

        assert len(received_events) == 1
        assert received_events[0].project_id == "project-a"

    def test_unsubscribe(self):
        """Handler can be unsubscribed."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        def handler(event: Event):
            received_events.append(event)

        emitter.subscribe(EventType.TASK_STARTED, handler)
        emitter.emit(TaskStartedEvent(project_id="test"))

        emitter.unsubscribe(EventType.TASK_STARTED, handler)
        emitter.emit(TaskStartedEvent(project_id="test"))

        assert len(received_events) == 1

    def test_unsubscribe_all(self):
        """Global handler can be unsubscribed."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        def handler(event: Event):
            received_events.append(event)

        emitter.subscribe_all(handler)
        emitter.emit(TaskStartedEvent(project_id="test"))

        emitter.unsubscribe_all(handler)
        emitter.emit(TaskStartedEvent(project_id="test"))

        assert len(received_events) == 1

    def test_unsubscribe_project(self):
        """Project handler can be unsubscribed."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        def handler(event: Event):
            received_events.append(event)

        emitter.subscribe_project("test-project", handler)
        emitter.emit(TaskStartedEvent(project_id="test-project"))

        emitter.unsubscribe_project("test-project", handler)
        emitter.emit(TaskStartedEvent(project_id="test-project"))

        assert len(received_events) == 1

    def test_handler_error_does_not_break_emission(self):
        """Handler errors don't prevent other handlers from receiving events."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        def failing_handler(event: Event):
            raise ValueError("Handler error")

        def working_handler(event: Event):
            received_events.append(event)

        emitter.subscribe(EventType.TASK_STARTED, failing_handler)
        emitter.subscribe(EventType.TASK_STARTED, working_handler)

        emitter.emit(TaskStartedEvent(project_id="test"))

        assert len(received_events) == 1

    def test_clear_handlers(self):
        """Handlers can be cleared."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        emitter.subscribe(EventType.TASK_STARTED, lambda e: received_events.append(e))
        emitter.subscribe_all(lambda e: received_events.append(e))

        emitter.clear_handlers()
        emitter.emit(TaskStartedEvent(project_id="test"))

        assert len(received_events) == 0

    def test_clear_handlers_specific_type(self):
        """Handlers for specific type can be cleared."""
        emitter = EventEmitter()
        task_started_events: List[Event] = []
        task_completed_events: List[Event] = []

        emitter.subscribe(EventType.TASK_STARTED, lambda e: task_started_events.append(e))
        emitter.subscribe(EventType.TASK_COMPLETED, lambda e: task_completed_events.append(e))

        emitter.clear_handlers(EventType.TASK_STARTED)

        emitter.emit(TaskStartedEvent(project_id="test"))
        emitter.emit(TaskCompletedEvent(project_id="test"))

        assert len(task_started_events) == 0
        assert len(task_completed_events) == 1

    def test_handler_count(self):
        """Handler count is tracked correctly."""
        emitter = EventEmitter()

        assert emitter.handler_count() == 0

        emitter.subscribe(EventType.TASK_STARTED, lambda e: None)
        emitter.subscribe(EventType.TASK_STARTED, lambda e: None)
        emitter.subscribe_all(lambda e: None)

        assert emitter.handler_count() == 3
        assert emitter.handler_count(EventType.TASK_STARTED) == 2
        assert emitter.handler_count(EventType.TASK_COMPLETED) == 0

    def test_duplicate_subscription_ignored(self):
        """Same handler subscribed twice is only called once."""
        emitter = EventEmitter()
        call_count = 0

        def handler(event: Event):
            nonlocal call_count
            call_count += 1

        emitter.subscribe(EventType.TASK_STARTED, handler)
        emitter.subscribe(EventType.TASK_STARTED, handler)

        emitter.emit(TaskStartedEvent(project_id="test"))

        assert call_count == 1


class TestEventEmitterAsync:
    """Tests for EventEmitter async functionality."""

    @pytest.mark.asyncio
    async def test_emit_async(self):
        """Async emit works with coroutine handlers."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        async def async_handler(event: Event):
            await asyncio.sleep(0.01)
            received_events.append(event)

        emitter.subscribe(EventType.TASK_STARTED, async_handler)

        await emitter.emit_async(TaskStartedEvent(project_id="test"))

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_emit_async_mixed_handlers(self):
        """Async emit works with both sync and async handlers."""
        emitter = EventEmitter()
        received_events: List[Event] = []

        def sync_handler(event: Event):
            received_events.append(("sync", event))

        async def async_handler(event: Event):
            await asyncio.sleep(0.01)
            received_events.append(("async", event))

        emitter.subscribe(EventType.TASK_STARTED, sync_handler)
        emitter.subscribe(EventType.TASK_STARTED, async_handler)

        await emitter.emit_async(TaskStartedEvent(project_id="test"))

        assert len(received_events) == 2


# =============================================================================
# EventQueue tests
# =============================================================================


class TestEventQueue:
    """Tests for EventQueue class."""

    def test_enqueue_and_dequeue(self):
        """Events can be enqueued and dequeued."""
        queue = EventQueue()

        event = TaskStartedEvent(project_id="test")
        queue.enqueue(event)

        dequeued = queue.dequeue()
        assert dequeued == event
        assert queue.is_empty()

    def test_dequeue_empty(self):
        """Dequeueing empty queue returns None."""
        queue = EventQueue()
        assert queue.dequeue() is None

    def test_fifo_order(self):
        """Events are dequeued in FIFO order."""
        queue = EventQueue()

        event1 = TaskStartedEvent(project_id="test", task_id="T-001")
        event2 = TaskStartedEvent(project_id="test", task_id="T-002")
        event3 = TaskStartedEvent(project_id="test", task_id="T-003")

        queue.enqueue(event1)
        queue.enqueue(event2)
        queue.enqueue(event3)

        assert queue.dequeue().task_id == "T-001"
        assert queue.dequeue().task_id == "T-002"
        assert queue.dequeue().task_id == "T-003"

    def test_dequeue_all(self):
        """All events can be dequeued at once."""
        queue = EventQueue()

        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-001"))
        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-002"))

        events = queue.dequeue_all()
        assert len(events) == 2
        assert queue.is_empty()

    def test_dequeue_all_with_type_filter(self):
        """Events can be filtered by type when dequeueing."""
        queue = EventQueue()

        queue.enqueue(TaskStartedEvent(project_id="test"))
        queue.enqueue(TaskCompletedEvent(project_id="test"))
        queue.enqueue(TaskStartedEvent(project_id="test"))

        events = queue.dequeue_all(event_types={EventType.TASK_STARTED})
        assert len(events) == 2
        assert all(e.event_type == EventType.TASK_STARTED for e in events)

    def test_dequeue_all_with_project_filter(self):
        """Events can be filtered by project when dequeueing."""
        queue = EventQueue()

        queue.enqueue(TaskStartedEvent(project_id="project-a"))
        queue.enqueue(TaskStartedEvent(project_id="project-b"))
        queue.enqueue(TaskStartedEvent(project_id="project-a"))

        events = queue.dequeue_all(project_id="project-a")
        assert len(events) == 2
        assert all(e.project_id == "project-a" for e in events)

    def test_max_size_eviction(self):
        """Oldest events are evicted when queue reaches max size."""
        queue = EventQueue(max_size=3)

        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-001"))
        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-002"))
        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-003"))
        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-004"))

        assert queue.size() == 3
        events = queue.dequeue_all()
        # Oldest event (T-001) should be evicted
        assert events[0].task_id == "T-002"

    def test_peek(self):
        """Peek returns oldest event without removing it."""
        queue = EventQueue()

        event = TaskStartedEvent(project_id="test")
        queue.enqueue(event)

        peeked = queue.peek()
        assert peeked == event
        assert queue.size() == 1

    def test_peek_empty(self):
        """Peeking empty queue returns None."""
        queue = EventQueue()
        assert queue.peek() is None

    def test_peek_all(self):
        """Peek all returns all events without removing them."""
        queue = EventQueue()

        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-001"))
        queue.enqueue(TaskStartedEvent(project_id="test", task_id="T-002"))

        events = queue.peek_all()
        assert len(events) == 2
        assert queue.size() == 2

    def test_size(self):
        """Size returns correct count."""
        queue = EventQueue()
        assert queue.size() == 0

        queue.enqueue(TaskStartedEvent(project_id="test"))
        assert queue.size() == 1

        queue.enqueue(TaskStartedEvent(project_id="test"))
        assert queue.size() == 2

    def test_is_empty(self):
        """is_empty returns correct state."""
        queue = EventQueue()
        assert queue.is_empty()

        queue.enqueue(TaskStartedEvent(project_id="test"))
        assert not queue.is_empty()

        queue.dequeue()
        assert queue.is_empty()

    def test_clear(self):
        """Clear removes all events and returns count."""
        queue = EventQueue()

        queue.enqueue(TaskStartedEvent(project_id="test"))
        queue.enqueue(TaskStartedEvent(project_id="test"))

        count = queue.clear()
        assert count == 2
        assert queue.is_empty()

    def test_max_size_property(self):
        """Max size is accessible."""
        queue = EventQueue(max_size=500)
        assert queue.max_size == 500


class TestEventQueueAsync:
    """Tests for EventQueue async functionality."""

    @pytest.mark.asyncio
    async def test_dequeue_async_with_events(self):
        """Async dequeue returns events immediately if available."""
        queue = EventQueue()

        queue.enqueue(TaskStartedEvent(project_id="test"))

        events = await queue.dequeue_async(timeout=0.1)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_dequeue_async_timeout(self):
        """Async dequeue times out on empty queue."""
        queue = EventQueue()

        start = time.time()
        events = await queue.dequeue_async(timeout=0.1)
        elapsed = time.time() - start

        assert len(events) == 0
        assert elapsed >= 0.1


# =============================================================================
# Service bridge tests
# =============================================================================


class TestServiceBridge:
    """Tests for service bridge functions."""

    def test_create_service_bridge_returns_handlers(self):
        """Bridge creation returns handlers for all services."""
        emitter = EventEmitter()
        bridge = create_service_bridge(emitter, "test-project")

        assert "orchestration" in bridge
        assert "session" in bridge
        assert "config" in bridge
        assert "git" in bridge
        assert all(callable(h) for h in bridge.values())

    def test_orchestration_bridge_task_started(self):
        """Orchestration bridge forwards task_started events."""
        emitter = EventEmitter()
        received_events: List[Event] = []
        emitter.subscribe_all(lambda e: received_events.append(e))

        bridge = create_service_bridge(emitter, "test-project")

        # Simulate OrchestrationService event
        @dataclass
        class MockOrchestrEvent:
            event_type: Enum = field(default=None)
            task_id: str = ""
            task_title: str = ""

        class MockEventType(str, Enum):
            TASK_STARTED = "task_started"

        mock_event = MockOrchestrEvent(
            event_type=MockEventType.TASK_STARTED,
            task_id="T-001",
            task_title="Test task",
        )

        bridge["orchestration"](mock_event)

        assert len(received_events) == 1
        assert isinstance(received_events[0], TaskStartedEvent)
        assert received_events[0].task_id == "T-001"
        assert received_events[0].project_id == "test-project"

    def test_orchestration_bridge_task_completed(self):
        """Orchestration bridge forwards task_completed events."""
        emitter = EventEmitter()
        received_events: List[Event] = []
        emitter.subscribe_all(lambda e: received_events.append(e))

        bridge = create_service_bridge(emitter, "test-project")

        @dataclass
        class MockEvent:
            event_type: Enum = field(default=None)
            task_id: str = ""
            success: bool = False
            iterations: int = 0
            duration_ms: int = 0
            failure_reason: str = None

        class MockEventType(str, Enum):
            TASK_COMPLETED = "task_completed"

        mock_event = MockEvent(
            event_type=MockEventType.TASK_COMPLETED,
            task_id="T-001",
            success=True,
            iterations=3,
            duration_ms=5000,
        )

        bridge["orchestration"](mock_event)

        assert len(received_events) == 1
        assert isinstance(received_events[0], TaskCompletedEvent)
        assert received_events[0].success is True
        assert received_events[0].iterations == 3

    def test_session_bridge(self):
        """Session bridge forwards session events."""
        emitter = EventEmitter()
        received_events: List[Event] = []
        emitter.subscribe_all(lambda e: received_events.append(e))

        bridge = create_service_bridge(emitter, "test-project")

        @dataclass
        class MockSessionEvent:
            event_type: Enum = field(default=None)
            session_id: str = ""
            status: str = ""
            tasks_completed: int = 0
            tasks_pending: int = 0
            tasks_failed: int = 0
            task_id: str = None
            failure_reason: str = None

        class MockEventType(str, Enum):
            SESSION_CREATED = "session_created"

        mock_event = MockSessionEvent(
            event_type=MockEventType.SESSION_CREATED,
            session_id="20260127-120000-abc123",
            status="running",
            tasks_pending=5,
        )

        bridge["session"](mock_event)

        assert len(received_events) == 1
        assert isinstance(received_events[0], SessionChangedEvent)
        assert received_events[0].change_type == "created"
        assert received_events[0].session_id == "20260127-120000-abc123"

    def test_config_bridge(self):
        """Config bridge forwards config events."""
        emitter = EventEmitter()
        received_events: List[Event] = []
        emitter.subscribe_all(lambda e: received_events.append(e))

        bridge = create_service_bridge(emitter, "test-project")

        @dataclass
        class MockConfigEvent:
            event_type: Enum = field(default=None)
            config_path: str = ""
            changes: dict = field(default_factory=dict)
            errors: list = field(default_factory=list)
            version: str = ""

        class MockEventType(str, Enum):
            CONFIG_UPDATED = "config_updated"

        mock_event = MockConfigEvent(
            event_type=MockEventType.CONFIG_UPDATED,
            config_path="/path/to/ralph.yml",
            changes={"gates": "updated"},
            version="1",
        )

        bridge["config"](mock_event)

        assert len(received_events) == 1
        assert isinstance(received_events[0], ConfigChangedEvent)
        assert received_events[0].change_type == "updated"
        assert received_events[0].changes == {"gates": "updated"}

    def test_git_bridge(self):
        """Git bridge forwards git events as session metadata."""
        emitter = EventEmitter()
        received_events: List[Event] = []
        emitter.subscribe_all(lambda e: received_events.append(e))

        bridge = create_service_bridge(emitter, "test-project")

        @dataclass
        class MockGitEvent:
            event_type: Enum = field(default=None)
            branch_name: str = ""
            base_branch: str = ""

        class MockEventType(str, Enum):
            BRANCH_CREATED = "branch_created"

        mock_event = MockGitEvent(
            event_type=MockEventType.BRANCH_CREATED,
            branch_name="feature/test",
            base_branch="main",
        )

        bridge["git"](mock_event)

        assert len(received_events) == 1
        assert isinstance(received_events[0], SessionChangedEvent)
        assert received_events[0].change_type == "git_update"
        assert received_events[0].metadata["git_event"] == "branch_created"
        assert received_events[0].metadata["branch_name"] == "feature/test"


# =============================================================================
# Integration tests
# =============================================================================


class TestIntegration:
    """Integration tests for the complete event system."""

    def test_emitter_to_queue_flow(self):
        """Events flow from emitter to queue correctly."""
        emitter = EventEmitter()
        queue = EventQueue()

        # Connect emitter to queue
        emitter.subscribe_all(queue.enqueue)

        # Emit various events
        emitter.emit(TaskStartedEvent(project_id="test", task_id="T-001"))
        emitter.emit(AgentPhaseChangedEvent(project_id="test", task_id="T-001", phase="implementation"))
        emitter.emit(GateRunningEvent(project_id="test", task_id="T-001", gate_name="lint"))
        emitter.emit(TaskCompletedEvent(project_id="test", task_id="T-001", success=True))

        # Verify all events queued
        events = queue.dequeue_all()
        assert len(events) == 4
        assert events[0].event_type == EventType.TASK_STARTED
        assert events[1].event_type == EventType.AGENT_PHASE_CHANGED
        assert events[2].event_type == EventType.GATE_RUNNING
        assert events[3].event_type == EventType.TASK_COMPLETED

    def test_multiple_project_isolation(self):
        """Events for different projects are isolated."""
        emitter = EventEmitter()
        project_a_events: List[Event] = []
        project_b_events: List[Event] = []

        emitter.subscribe_project("project-a", lambda e: project_a_events.append(e))
        emitter.subscribe_project("project-b", lambda e: project_b_events.append(e))

        emitter.emit(TaskStartedEvent(project_id="project-a", task_id="T-001"))
        emitter.emit(TaskStartedEvent(project_id="project-b", task_id="T-002"))
        emitter.emit(TaskCompletedEvent(project_id="project-a", task_id="T-001"))

        assert len(project_a_events) == 2
        assert len(project_b_events) == 1
        assert all(e.project_id == "project-a" for e in project_a_events)
        assert all(e.project_id == "project-b" for e in project_b_events)

    def test_event_serialization_round_trip(self):
        """Events can be serialized to dict and contain all necessary data."""
        import json

        event = TaskCompletedEvent(
            project_id="test-project",
            task_id="T-001",
            success=True,
            iterations=5,
            duration_ms=10000,
        )

        # Serialize to JSON
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)

        # Deserialize and verify
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "task_completed"
        assert parsed["project_id"] == "test-project"
        assert parsed["task_id"] == "T-001"
        assert parsed["success"] is True
        assert parsed["iterations"] == 5
        assert parsed["duration_ms"] == 10000
        assert "timestamp" in parsed
        assert "event_id" in parsed
