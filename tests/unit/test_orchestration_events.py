"""Unit tests for OrchestrationService event emission.

Tests that events are emitted at correct points during execution:
- task_started, task_completed
- agent_phase_changed
- gate_running, gate_completed
- signal_detected
- iteration_started
- session_started, session_ended
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ralph_orchestrator.services.orchestration_service import (
    EventType,
    TaskStartedEvent,
    TaskCompletedEvent,
    AgentPhaseChangedEvent,
    GateRunningEvent,
    GateCompletedEvent,
    SignalDetectedEvent,
    IterationStartedEvent,
    SessionStartedEvent,
    SessionEndedEvent,
)

# Skip tests requiring mock when real Claude is configured
requires_mock = pytest.mark.skipif(
    "mock_claude" not in os.environ.get("RALPH_CLAUDE_CMD", ""),
    reason="Requires mock Claude (RALPH_CLAUDE_CMD set externally)"
)


@pytest.mark.integration
@requires_mock
class TestEventEmissionDuringExecution:
    """Test that events are emitted at correct points during task execution."""

    def test_task_started_event_emitted(self, fixture_python_min, mock_scenario_default):
        """task_started event is emitted when task begins."""
        from ralph_orchestrator.run import run_tasks, RunOptions

        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Works"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Track events
        events_received = []

        def capture_event(event):
            events_received.append(event)

        # Patch OrchestrationService to capture events
        from ralph_orchestrator.run import RunEngine
        original_init = RunEngine.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.service.on_event(EventType.TASK_STARTED, capture_event)

        with patch.object(RunEngine, "__init__", patched_init):
            options = RunOptions(
                prd_json=str(prd_path),
                max_iterations=5,
                gate_type="none",
                post_verify=False,
            )

            run_tasks(
                config_path=repo / ".ralph" / "ralph.yml",
                prd_path=prd_path,
                options=options,
            )

        # Verify event was emitted
        assert len(events_received) > 0
        task_started_events = [e for e in events_received if isinstance(e, TaskStartedEvent)]
        assert len(task_started_events) == 1
        assert task_started_events[0].task_id == "T-001"
        assert task_started_events[0].task_title == "Test task"

    def test_task_completed_event_emitted(self, fixture_python_min, mock_scenario_default):
        """task_completed event is emitted when task finishes."""
        from ralph_orchestrator.run import run_tasks, RunOptions

        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Works"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Track events
        events_received = []

        def capture_event(event):
            events_received.append(event)

        # Patch OrchestrationService to capture events
        from ralph_orchestrator.run import RunEngine
        original_init = RunEngine.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.service.on_event(EventType.TASK_COMPLETED, capture_event)

        with patch.object(RunEngine, "__init__", patched_init):
            options = RunOptions(
                prd_json=str(prd_path),
                max_iterations=5,
                gate_type="none",
                post_verify=False,
            )

            run_tasks(
                config_path=repo / ".ralph" / "ralph.yml",
                prd_path=prd_path,
                options=options,
            )

        # Verify event was emitted
        assert len(events_received) > 0
        task_completed_events = [e for e in events_received if isinstance(e, TaskCompletedEvent)]
        assert len(task_completed_events) == 1
        assert task_completed_events[0].task_id == "T-001"
        assert task_completed_events[0].success is True
        assert task_completed_events[0].iterations >= 1
        assert task_completed_events[0].duration_ms > 0

    def test_agent_phase_changed_events_emitted(self, fixture_python_min, mock_scenario_default):
        """agent_phase_changed events emitted for phase transitions."""
        from ralph_orchestrator.run import run_tasks, RunOptions

        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Works"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": True,  # Enable test writing phase
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Track events
        events_received = []

        def capture_event(event):
            events_received.append(event)

        # Patch OrchestrationService to capture events
        from ralph_orchestrator.run import RunEngine
        original_init = RunEngine.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.service.on_event(EventType.AGENT_PHASE_CHANGED, capture_event)

        with patch.object(RunEngine, "__init__", patched_init):
            options = RunOptions(
                prd_json=str(prd_path),
                max_iterations=5,
                gate_type="none",
                post_verify=False,
            )

            run_tasks(
                config_path=repo / ".ralph" / "ralph.yml",
                prd_path=prd_path,
                options=options,
            )

        # Verify phase change events were emitted
        phase_events = [e for e in events_received if isinstance(e, AgentPhaseChangedEvent)]
        assert len(phase_events) >= 3  # implementation, test_writing, review

        phases_seen = [e.phase for e in phase_events]
        assert "implementation" in phases_seen
        assert "test_writing" in phases_seen
        assert "review" in phases_seen

    def test_signal_detected_events_emitted(self, fixture_python_min, mock_scenario_default):
        """signal_detected events emitted when agents emit signals."""
        from ralph_orchestrator.run import run_tasks, RunOptions

        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Works"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Track events
        events_received = []

        def capture_event(event):
            events_received.append(event)

        # Patch OrchestrationService to capture events
        from ralph_orchestrator.run import RunEngine
        original_init = RunEngine.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.service.on_event(EventType.SIGNAL_DETECTED, capture_event)

        with patch.object(RunEngine, "__init__", patched_init):
            options = RunOptions(
                prd_json=str(prd_path),
                max_iterations=5,
                gate_type="none",
                post_verify=False,
            )

            run_tasks(
                config_path=repo / ".ralph" / "ralph.yml",
                prd_path=prd_path,
                options=options,
            )

        # Verify signal events were emitted
        signal_events = [e for e in events_received if isinstance(e, SignalDetectedEvent)]
        assert len(signal_events) >= 2  # At least implementation and review

        # Check signal types
        signal_types = [e.signal_type for e in signal_events]
        assert any("task-done" in st or st == "task-done" for st in signal_types)
        assert any("review-approved" in st or st == "review-approved" for st in signal_types)

    def test_session_started_and_ended_events(self, fixture_python_min, mock_scenario_default):
        """session_started and session_ended events emitted."""
        from ralph_orchestrator.run import run_tasks, RunOptions

        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Works"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Track events
        events_received = []

        def capture_event(event):
            events_received.append(event)

        # Patch OrchestrationService to capture events
        from ralph_orchestrator.run import RunEngine
        original_init = RunEngine.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.service.on_all_events(capture_event)

        with patch.object(RunEngine, "__init__", patched_init):
            options = RunOptions(
                prd_json=str(prd_path),
                max_iterations=5,
                gate_type="none",
                post_verify=False,
            )

            run_tasks(
                config_path=repo / ".ralph" / "ralph.yml",
                prd_path=prd_path,
                options=options,
            )

        # Verify session events
        session_started = [e for e in events_received if isinstance(e, SessionStartedEvent)]
        session_ended = [e for e in events_received if isinstance(e, SessionEndedEvent)]

        assert len(session_started) == 1
        assert len(session_ended) == 1

        assert session_started[0].task_count == 1
        assert session_ended[0].status == "completed"
        assert session_ended[0].tasks_completed == 1
        assert session_ended[0].tasks_failed == 0

    def test_iteration_started_events_emitted(self, fixture_python_min, mock_scenario_default):
        """iteration_started events emitted for each iteration."""
        from ralph_orchestrator.run import run_tasks, RunOptions

        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Works"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Track events
        events_received = []

        def capture_event(event):
            events_received.append(event)

        # Patch OrchestrationService to capture events
        from ralph_orchestrator.run import RunEngine
        original_init = RunEngine.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.service.on_event(EventType.ITERATION_STARTED, capture_event)

        with patch.object(RunEngine, "__init__", patched_init):
            options = RunOptions(
                prd_json=str(prd_path),
                max_iterations=5,
                gate_type="none",
                post_verify=False,
            )

            run_tasks(
                config_path=repo / ".ralph" / "ralph.yml",
                prd_path=prd_path,
                options=options,
            )

        # Verify iteration events
        iteration_events = [e for e in events_received if isinstance(e, IterationStartedEvent)]
        assert len(iteration_events) >= 1

        # Check iteration numbers are sequential
        iterations = [e.iteration for e in iteration_events]
        assert iterations[0] == 1


@pytest.mark.unit
class TestEventHandlerInvocation:
    """Test that event handlers are invoked correctly."""

    def test_multiple_handlers_for_same_event(self):
        """Multiple handlers can be registered for same event type."""
        from ralph_orchestrator.services.orchestration_service import OrchestrationService, OrchestrationOptions

        # Create minimal mock service
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(model="sonnet", allowed_tools=None, timeout=None))

        service = OrchestrationService(
            config=config,
            prd=Mock(),
            session=Mock(session_token="test-token"),
            timeline=Mock(),
            execution_logger=Mock(),
            claude_runner=Mock(),
            gate_runner=Mock(),
            guardrail=Mock(),
            options=OrchestrationOptions(),
        )

        # Register multiple handlers
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        service.on_event(EventType.TASK_STARTED, handler1)
        service.on_event(EventType.TASK_STARTED, handler2)
        service.on_event(EventType.TASK_STARTED, handler3)

        # Emit event
        event = TaskStartedEvent(task_id="T-001", task_title="Test")
        service._emit_event(event)

        # Verify all handlers called
        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)
        handler3.assert_called_once_with(event)

    def test_global_handler_receives_all_events(self):
        """Global handler receives all event types."""
        from ralph_orchestrator.services.orchestration_service import OrchestrationService, OrchestrationOptions

        # Create minimal mock service
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(model="sonnet", allowed_tools=None, timeout=None))

        service = OrchestrationService(
            config=config,
            prd=Mock(),
            session=Mock(session_token="test-token"),
            timeline=Mock(),
            execution_logger=Mock(),
            claude_runner=Mock(),
            gate_runner=Mock(),
            guardrail=Mock(),
            options=OrchestrationOptions(),
        )

        # Register global handler
        global_handler = Mock()
        service.on_all_events(global_handler)

        # Emit different event types
        event1 = TaskStartedEvent(task_id="T-001", task_title="Test")
        event2 = TaskCompletedEvent(task_id="T-001", success=True, iterations=1, duration_ms=1000)
        event3 = AgentPhaseChangedEvent(task_id="T-001", phase="implementation")

        service._emit_event(event1)
        service._emit_event(event2)
        service._emit_event(event3)

        # Verify global handler called for all
        assert global_handler.call_count == 3
        global_handler.assert_any_call(event1)
        global_handler.assert_any_call(event2)
        global_handler.assert_any_call(event3)

    def test_event_handler_can_access_event_data(self):
        """Event handlers can access event data for monitoring."""
        from ralph_orchestrator.services.orchestration_service import OrchestrationService, OrchestrationOptions

        # Create minimal mock service
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(model="sonnet", allowed_tools=None, timeout=None))

        service = OrchestrationService(
            config=config,
            prd=Mock(),
            session=Mock(session_token="test-token"),
            timeline=Mock(),
            execution_logger=Mock(),
            claude_runner=Mock(),
            gate_runner=Mock(),
            guardrail=Mock(),
            options=OrchestrationOptions(),
        )

        # Register handler that captures event data
        captured_data = []

        def monitoring_handler(event):
            captured_data.append({
                "type": event.event_type,
                "timestamp": event.timestamp,
                "data": event.to_dict(),
            })

        service.on_all_events(monitoring_handler)

        # Emit events
        service._emit_event(TaskStartedEvent(task_id="T-001", task_title="Test Task"))
        service._emit_event(GateCompletedEvent(
            task_id="T-001",
            gate_name="lint",
            gate_type="build",
            passed=True,
            duration_ms=1500,
        ))

        # Verify captured data
        assert len(captured_data) == 2
        assert captured_data[0]["type"] == EventType.TASK_STARTED
        assert captured_data[0]["data"]["task_id"] == "T-001"
        assert captured_data[1]["type"] == EventType.GATE_COMPLETED
        assert captured_data[1]["data"]["gate_name"] == "lint"
        assert captured_data[1]["data"]["passed"] is True
