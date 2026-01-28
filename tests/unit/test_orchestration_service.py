"""Unit tests for OrchestrationService.

Tests core orchestration service functionality:
- Event emission and registration
- Service initialization
- Event handler management
- Event data structures
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, Mock, patch
from pathlib import Path

import pytest

from ralph_orchestrator.services.orchestration_service import (
    OrchestrationService,
    OrchestrationEvent,
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
    OrchestrationOptions,
    OrchestrationResult,
    TaskRunResult,
    ExitCode,
)
import ast


class TestEventTypes:
    """Test event type enumeration."""

    def test_event_types_exist(self):
        """All documented event types exist."""
        assert EventType.TASK_STARTED == "task_started"
        assert EventType.TASK_COMPLETED == "task_completed"
        assert EventType.AGENT_PHASE_CHANGED == "agent_phase_changed"
        assert EventType.GATE_RUNNING == "gate_running"
        assert EventType.GATE_COMPLETED == "gate_completed"
        assert EventType.SIGNAL_DETECTED == "signal_detected"
        assert EventType.ITERATION_STARTED == "iteration_started"
        assert EventType.SESSION_STARTED == "session_started"
        assert EventType.SESSION_ENDED == "session_ended"


class TestEventDataStructures:
    """Test event data classes and serialization."""

    def test_task_started_event(self):
        """TaskStartedEvent has correct fields and serializes properly."""
        event = TaskStartedEvent(
            task_id="T-001",
            task_title="Test Task",
        )

        assert event.event_type == EventType.TASK_STARTED
        assert event.task_id == "T-001"
        assert event.task_title == "Test Task"
        assert event.timestamp > 0

        # Test serialization
        data = event.to_dict()
        assert data["event_type"] == "task_started"
        assert data["task_id"] == "T-001"
        assert data["task_title"] == "Test Task"
        assert "timestamp" in data

    def test_task_completed_event(self):
        """TaskCompletedEvent has correct fields and serializes properly."""
        event = TaskCompletedEvent(
            task_id="T-001",
            success=True,
            iterations=3,
            duration_ms=5000,
        )

        assert event.event_type == EventType.TASK_COMPLETED
        assert event.task_id == "T-001"
        assert event.success is True
        assert event.iterations == 3
        assert event.duration_ms == 5000
        assert event.failure_reason is None

        # Test serialization
        data = event.to_dict()
        assert data["event_type"] == "task_completed"
        assert data["success"] is True
        assert data["iterations"] == 3
        assert data["duration_ms"] == 5000

    def test_task_completed_event_with_failure(self):
        """TaskCompletedEvent includes failure reason when failed."""
        event = TaskCompletedEvent(
            task_id="T-001",
            success=False,
            iterations=200,
            duration_ms=60000,
            failure_reason="Max iterations reached",
        )

        assert event.success is False
        assert event.failure_reason == "Max iterations reached"

        data = event.to_dict()
        assert data["failure_reason"] == "Max iterations reached"

    def test_agent_phase_changed_event(self):
        """AgentPhaseChangedEvent has correct fields."""
        event = AgentPhaseChangedEvent(
            task_id="T-001",
            phase="implementation",
            previous_phase="review",
        )

        assert event.event_type == EventType.AGENT_PHASE_CHANGED
        assert event.task_id == "T-001"
        assert event.phase == "implementation"
        assert event.previous_phase == "review"

        data = event.to_dict()
        assert data["phase"] == "implementation"
        assert data["previous_phase"] == "review"

    def test_gate_running_event(self):
        """GateRunningEvent has correct fields."""
        event = GateRunningEvent(
            task_id="T-001",
            gate_name="lint",
            gate_type="build",
        )

        assert event.event_type == EventType.GATE_RUNNING
        assert event.gate_name == "lint"
        assert event.gate_type == "build"

        data = event.to_dict()
        assert data["gate_name"] == "lint"
        assert data["gate_type"] == "build"

    def test_gate_completed_event(self):
        """GateCompletedEvent has correct fields."""
        event = GateCompletedEvent(
            task_id="T-001",
            gate_name="test",
            gate_type="full",
            passed=True,
            duration_ms=2500,
            output=None,
        )

        assert event.event_type == EventType.GATE_COMPLETED
        assert event.passed is True
        assert event.duration_ms == 2500

        data = event.to_dict()
        assert data["passed"] is True
        assert data["duration_ms"] == 2500

    def test_signal_detected_event(self):
        """SignalDetectedEvent has correct fields."""
        event = SignalDetectedEvent(
            task_id="T-001",
            signal_type="task-done",
            valid=True,
            token_valid=True,
            agent_role="implementation",
            content="Implementation complete",
        )

        assert event.event_type == EventType.SIGNAL_DETECTED
        assert event.signal_type == "task-done"
        assert event.valid is True
        assert event.token_valid is True
        assert event.agent_role == "implementation"

        data = event.to_dict()
        assert data["signal_type"] == "task-done"
        assert data["valid"] is True

    def test_iteration_started_event(self):
        """IterationStartedEvent has correct fields."""
        event = IterationStartedEvent(
            task_id="T-001",
            iteration=3,
            max_iterations=200,
        )

        assert event.event_type == EventType.ITERATION_STARTED
        assert event.iteration == 3
        assert event.max_iterations == 200

    def test_session_started_event(self):
        """SessionStartedEvent has correct fields."""
        event = SessionStartedEvent(
            session_id="ralph-20260127-130000-abc123",
            task_count=5,
        )

        assert event.event_type == EventType.SESSION_STARTED
        assert event.session_id == "ralph-20260127-130000-abc123"
        assert event.task_count == 5

    def test_session_ended_event(self):
        """SessionEndedEvent has correct fields."""
        event = SessionEndedEvent(
            session_id="ralph-20260127-130000-abc123",
            status="completed",
            tasks_completed=5,
            tasks_failed=0,
            duration_ms=120000,
        )

        assert event.event_type == EventType.SESSION_ENDED
        assert event.status == "completed"
        assert event.tasks_completed == 5
        assert event.tasks_failed == 0


class TestEventHandlerRegistration:
    """Test event handler registration and management."""

    def _create_mock_service(self):
        """Create a minimal mock orchestration service."""
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(model="sonnet", allowed_tools=None, timeout=None))

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        timeline = Mock()
        exec_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()

        options = OrchestrationOptions()

        service = OrchestrationService(
            config=config,
            prd=prd,
            session=session,
            timeline=timeline,
            execution_logger=exec_logger,
            claude_runner=claude_runner,
            gate_runner=gate_runner,
            guardrail=guardrail,
            options=options,
        )

        return service

    def test_on_event_registers_handler(self):
        """on_event registers handler for specific event type."""
        service = self._create_mock_service()
        handler = Mock()

        service.on_event(EventType.TASK_STARTED, handler)

        assert handler in service._event_handlers[EventType.TASK_STARTED]

    def test_on_all_events_registers_global_handler(self):
        """on_all_events registers handler for all events."""
        service = self._create_mock_service()
        handler = Mock()

        service.on_all_events(handler)

        assert handler in service._global_handlers

    def test_remove_handler_removes_specific_handler(self):
        """remove_handler removes specific event handler."""
        service = self._create_mock_service()
        handler = Mock()

        service.on_event(EventType.TASK_STARTED, handler)
        assert handler in service._event_handlers[EventType.TASK_STARTED]

        service.remove_handler(EventType.TASK_STARTED, handler)
        assert handler not in service._event_handlers[EventType.TASK_STARTED]

    def test_emit_event_calls_specific_handlers(self):
        """_emit_event calls handlers registered for specific event type."""
        service = self._create_mock_service()
        handler1 = Mock()
        handler2 = Mock()

        service.on_event(EventType.TASK_STARTED, handler1)
        service.on_event(EventType.TASK_COMPLETED, handler2)

        event = TaskStartedEvent(task_id="T-001", task_title="Test")
        service._emit_event(event)

        handler1.assert_called_once_with(event)
        handler2.assert_not_called()

    def test_emit_event_calls_global_handlers(self):
        """_emit_event calls global handlers for any event."""
        service = self._create_mock_service()
        global_handler = Mock()

        service.on_all_events(global_handler)

        event1 = TaskStartedEvent(task_id="T-001", task_title="Test")
        service._emit_event(event1)

        event2 = TaskCompletedEvent(task_id="T-001", success=True, iterations=1, duration_ms=1000)
        service._emit_event(event2)

        assert global_handler.call_count == 2

    def test_emit_event_handles_handler_exceptions(self):
        """_emit_event continues even if handler raises exception."""
        service = self._create_mock_service()
        failing_handler = Mock(side_effect=Exception("Handler error"))
        working_handler = Mock()

        service.on_event(EventType.TASK_STARTED, failing_handler)
        service.on_event(EventType.TASK_STARTED, working_handler)

        event = TaskStartedEvent(task_id="T-001", task_title="Test")
        service._emit_event(event)

        # Both should be called despite first one failing
        failing_handler.assert_called_once()
        working_handler.assert_called_once()


class TestOrchestrationServiceInit:
    """Test OrchestrationService initialization."""

    def test_service_initializes_with_required_dependencies(self):
        """Service initializes with all required dependencies."""
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        timeline = Mock()
        exec_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()

        options = OrchestrationOptions(
            max_iterations=100,
            gate_type="build",
            dry_run=True,
        )

        service = OrchestrationService(
            config=config,
            prd=prd,
            session=session,
            timeline=timeline,
            execution_logger=exec_logger,
            claude_runner=claude_runner,
            gate_runner=gate_runner,
            guardrail=guardrail,
            options=options,
        )

        assert service.config == config
        assert service.prd == prd
        assert service.session == session
        assert service.options.max_iterations == 100
        assert service.options.gate_type == "build"

    def test_service_loads_agents_md_if_exists(self, tmp_path):
        """Service loads AGENTS.md content if file exists."""
        config = Mock()
        config.repo_root = tmp_path
        config.test_paths = ["tests/"]

        # Create AGENTS.md
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Custom Agent Instructions\nTest content")

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        timeline = Mock()
        exec_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()

        options = OrchestrationOptions()

        service = OrchestrationService(
            config=config,
            prd=prd,
            session=session,
            timeline=timeline,
            execution_logger=exec_logger,
            claude_runner=claude_runner,
            gate_runner=gate_runner,
            guardrail=guardrail,
            options=options,
        )

        assert "Custom Agent Instructions" in service.agents_md_content
        assert "Test content" in service.agents_md_content

    def test_service_handles_missing_agents_md(self, tmp_path):
        """Service handles missing AGENTS.md gracefully."""
        config = Mock()
        config.repo_root = tmp_path
        config.test_paths = ["tests/"]

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        timeline = Mock()
        exec_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()

        options = OrchestrationOptions()

        service = OrchestrationService(
            config=config,
            prd=prd,
            session=session,
            timeline=timeline,
            execution_logger=exec_logger,
            claude_runner=claude_runner,
            gate_runner=gate_runner,
            guardrail=guardrail,
            options=options,
        )

        assert service.agents_md_content == ""


class TestOrchestrationOptions:
    """Test OrchestrationOptions data class."""

    def test_orchestration_options_defaults(self):
        """OrchestrationOptions has sensible defaults."""
        options = OrchestrationOptions()

        assert options.prd_json is None
        assert options.task_id is None
        assert options.from_task_id is None
        assert options.max_iterations == 200
        assert options.gate_type == "full"
        assert options.dry_run is False
        assert options.resume is False
        assert options.post_verify is True

    def test_orchestration_options_custom_values(self):
        """OrchestrationOptions accepts custom values."""
        options = OrchestrationOptions(
            prd_json="/path/to/prd.json",
            task_id="T-005",
            max_iterations=50,
            gate_type="build",
            dry_run=True,
            post_verify=False,
        )

        assert options.prd_json == "/path/to/prd.json"
        assert options.task_id == "T-005"
        assert options.max_iterations == 50
        assert options.gate_type == "build"
        assert options.dry_run is True
        assert options.post_verify is False


class TestExitCode:
    """Test ExitCode enumeration."""

    def test_exit_codes_have_correct_values(self):
        """Exit codes have expected numeric values."""
        assert ExitCode.SUCCESS == 0
        assert ExitCode.CONFIG_ERROR == 1
        assert ExitCode.TASK_SOURCE_ERROR == 2
        assert ExitCode.TASK_EXECUTION_FAILED == 3
        assert ExitCode.GATE_FAILURE == 4
        assert ExitCode.POST_VERIFICATION_FAILED == 5
        assert ExitCode.CHECKSUM_TAMPERING == 6
        assert ExitCode.USER_ABORT == 7
        assert ExitCode.CLAUDE_ERROR == 8
        assert ExitCode.SERVICE_FAILURE == 9


class TestCLIAgnostic:
    """Test that OrchestrationService has no Click/CLI dependencies."""

    def test_service_has_no_click_imports(self):
        """OrchestrationService module does not import Click."""
        from ralph_orchestrator.services import orchestration_service
        import sys

        # Check if click is imported in the module
        module_code = orchestration_service.__file__
        with open(module_code, 'r') as f:
            content = f.read()

        assert 'import click' not in content.lower()
        assert 'from click' not in content.lower()

    def test_service_has_no_print_statements(self):
        """OrchestrationService does not contain print statements (uses events)."""
        from ralph_orchestrator.services import orchestration_service
        import ast

        module_code = orchestration_service.__file__
        with open(module_code, 'r') as f:
            tree = ast.parse(f.read())

        # Find all function calls to 'print'
        print_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'print':
                    print_calls.append(node)

        # Service should not have any print calls
        assert len(print_calls) == 0, "OrchestrationService should not use print(), use events instead"

    def test_service_initializes_without_cli_context(self):
        """Service can be initialized outside of CLI context."""
        from ralph_orchestrator.services.orchestration_service import OrchestrationService, OrchestrationOptions

        # Should be able to initialize without any CLI context
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

        # Should initialize successfully
        assert service is not None
        assert service.config == config


class TestGetPendingTasks:
    """Test OrchestrationService.get_pending_tasks method."""

    def test_get_pending_tasks_returns_list(self):
        """get_pending_tasks returns list of pending tasks."""
        from ralph_orchestrator.services.orchestration_service import OrchestrationService, OrchestrationOptions

        # Create mock PRD with tasks
        prd = Mock()
        task1 = Mock()
        task1.id = "T-001"
        task1.passes = False
        task2 = Mock()
        task2.id = "T-002"
        task2.passes = True
        task3 = Mock()
        task3.id = "T-003"
        task3.passes = False
        prd.tasks = [task1, task2, task3]

        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(model="sonnet", allowed_tools=None, timeout=None))

        options = OrchestrationOptions()

        service = OrchestrationService(
            config=config,
            prd=prd,
            session=Mock(session_token="test-token"),
            timeline=Mock(),
            execution_logger=Mock(),
            claude_runner=Mock(),
            gate_runner=Mock(),
            guardrail=Mock(),
            options=options,
        )

        # Mock get_pending_tasks to return pending tasks
        with patch('ralph_orchestrator.tasks.prd.get_pending_tasks') as mock_get:
            mock_get.return_value = [task1, task3]

            pending = service.get_pending_tasks()

            assert isinstance(pending, list)
            assert len(pending) == 2

    def test_get_pending_tasks_respects_task_id_filter(self):
        """get_pending_tasks respects task_id option."""
        from ralph_orchestrator.services.orchestration_service import OrchestrationService, OrchestrationOptions

        prd = Mock()
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(model="sonnet", allowed_tools=None, timeout=None))

        options = OrchestrationOptions(task_id="T-002")

        service = OrchestrationService(
            config=config,
            prd=prd,
            session=Mock(session_token="test-token"),
            timeline=Mock(),
            execution_logger=Mock(),
            claude_runner=Mock(),
            gate_runner=Mock(),
            guardrail=Mock(),
            options=options,
        )

        # Mock get_pending_tasks
        with patch('ralph_orchestrator.tasks.prd.get_pending_tasks') as mock_get:
            task2 = Mock(id="T-002")
            mock_get.return_value = [task2]

            pending = service.get_pending_tasks()

            # Verify get_pending_tasks was called with correct task_id
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['task_id'] == "T-002"


class TestOrchestrationResult:
    """Test OrchestrationResult data structure."""

    def test_orchestration_result_structure(self):
        """OrchestrationResult has expected fields."""
        from ralph_orchestrator.services.orchestration_service import (
            OrchestrationResult,
            ExitCode,
            TaskRunResult,
        )

        result = OrchestrationResult(
            exit_code=ExitCode.SUCCESS,
            tasks_completed=3,
            tasks_failed=1,
            tasks_pending=2,
            total_duration_ms=120000,
            task_results=[
                TaskRunResult(
                    task_id="T-001",
                    completed=True,
                    iterations=2,
                    duration_ms=30000,
                )
            ],
            session_id="ralph-20260127-test",
        )

        assert result.exit_code == ExitCode.SUCCESS
        assert result.tasks_completed == 3
        assert result.tasks_failed == 1
        assert result.tasks_pending == 2
        assert result.total_duration_ms == 120000
        assert len(result.task_results) == 1
        assert result.session_id == "ralph-20260127-test"
        assert result.error is None

    def test_orchestration_result_with_error(self):
        """OrchestrationResult includes error message on failure."""
        from ralph_orchestrator.services.orchestration_service import (
            OrchestrationResult,
            ExitCode,
        )

        result = OrchestrationResult(
            exit_code=ExitCode.CONFIG_ERROR,
            error="Configuration file not found",
        )

        assert result.exit_code == ExitCode.CONFIG_ERROR
        assert result.error == "Configuration file not found"
        assert result.tasks_completed == 0
        assert result.tasks_failed == 0


class TestTaskRunResult:
    """Test TaskRunResult data structure."""

    def test_task_run_result_success(self):
        """TaskRunResult represents successful task completion."""
        from ralph_orchestrator.services.orchestration_service import TaskRunResult

        result = TaskRunResult(
            task_id="T-001",
            completed=True,
            iterations=3,
            duration_ms=45000,
        )

        assert result.task_id == "T-001"
        assert result.completed is True
        assert result.iterations == 3
        assert result.duration_ms == 45000
        assert result.failure_reason is None

    def test_task_run_result_failure(self):
        """TaskRunResult includes failure reason on failure."""
        from ralph_orchestrator.services.orchestration_service import TaskRunResult

        result = TaskRunResult(
            task_id="T-002",
            completed=False,
            iterations=200,
            duration_ms=600000,
            failure_reason="Max iterations (200) reached",
        )

        assert result.task_id == "T-002"
        assert result.completed is False
        assert result.iterations == 200
        assert result.failure_reason == "Max iterations (200) reached"
