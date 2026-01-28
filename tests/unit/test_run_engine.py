"""Unit tests for RunEngine wrapping OrchestrationService.

Tests that RunEngine properly delegates to OrchestrationService and
maintains backward compatibility while adding CLI-specific output.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

from ralph_orchestrator.run import (
    RunEngine,
    RunOptions,
    RunResult,
)
from ralph_orchestrator.services.orchestration_service import (
    OrchestrationService,
    OrchestrationOptions,
    OrchestrationResult,
    ExitCode,
    EventType,
    TaskStartedEvent,
    TaskCompletedEvent,
)


@pytest.mark.unit
class TestRunEngineInitialization:
    """Test RunEngine initialization and setup."""

    def _create_mock_dependencies(self):
        """Create mock dependencies for RunEngine."""
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(
            model="sonnet",
            allowed_tools=None,
            timeout=None,
        ))

        prd = Mock()
        session = Mock()
        session.session_token = "test-token-123"
        session.session_id = "ralph-20260127-test"
        timeline = Mock()
        execution_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()
        options = RunOptions()

        return {
            "config": config,
            "prd": prd,
            "session": session,
            "timeline": timeline,
            "execution_logger": execution_logger,
            "claude_runner": claude_runner,
            "gate_runner": gate_runner,
            "guardrail": guardrail,
            "options": options,
        }

    def test_run_engine_creates_orchestration_service(self):
        """RunEngine creates underlying OrchestrationService."""
        deps = self._create_mock_dependencies()

        engine = RunEngine(**deps)

        # Verify service was created
        assert engine._service is not None
        assert isinstance(engine._service, OrchestrationService)

    def test_run_engine_exposes_service_property(self):
        """RunEngine exposes underlying service via property."""
        deps = self._create_mock_dependencies()

        engine = RunEngine(**deps)

        # Service is accessible
        service = engine.service
        assert service is not None
        assert isinstance(service, OrchestrationService)

    def test_run_engine_converts_run_options_to_orchestration_options(self):
        """RunEngine converts RunOptions to OrchestrationOptions."""
        deps = self._create_mock_dependencies()
        deps["options"] = RunOptions(
            prd_json="/path/to/prd.json",
            task_id="T-005",
            max_iterations=50,
            gate_type="build",
            dry_run=True,
            post_verify=False,
        )

        engine = RunEngine(**deps)

        # Verify service received correct options
        service_options = engine._service.options
        assert service_options.prd_json == "/path/to/prd.json"
        assert service_options.task_id == "T-005"
        assert service_options.max_iterations == 50
        assert service_options.gate_type == "build"
        assert service_options.dry_run is True
        assert service_options.post_verify is False

    def test_run_engine_registers_cli_event_handlers(self):
        """RunEngine registers CLI event handlers on service."""
        deps = self._create_mock_dependencies()

        with patch.object(OrchestrationService, 'on_event') as mock_on_event:
            engine = RunEngine(**deps)

            # Verify CLI handlers were registered
            mock_on_event.assert_any_call(EventType.TASK_STARTED, engine._on_task_started)
            mock_on_event.assert_any_call(EventType.TASK_COMPLETED, engine._on_task_completed)
            mock_on_event.assert_any_call(EventType.AGENT_PHASE_CHANGED, engine._on_agent_phase_changed)
            mock_on_event.assert_any_call(EventType.GATE_COMPLETED, engine._on_gate_completed)


@pytest.mark.unit
class TestRunEngineDelegation:
    """Test that RunEngine delegates correctly to OrchestrationService."""

    def _create_mock_dependencies(self):
        """Create mock dependencies for RunEngine."""
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(return_value=Mock(
            model="sonnet",
            allowed_tools=None,
            timeout=None,
        ))

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        session.session_id = "ralph-20260127-test"
        session.logs_dir = Path("/tmp/logs")
        timeline = Mock()
        execution_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()
        options = RunOptions()

        return {
            "config": config,
            "prd": prd,
            "session": session,
            "timeline": timeline,
            "execution_logger": execution_logger,
            "claude_runner": claude_runner,
            "gate_runner": gate_runner,
            "guardrail": guardrail,
            "options": options,
        }

    def test_run_engine_delegates_to_service_run(self):
        """RunEngine.run() delegates to service.run()."""
        deps = self._create_mock_dependencies()
        engine = RunEngine(**deps)

        # Mock service.run()
        mock_result = OrchestrationResult(
            exit_code=ExitCode.SUCCESS,
            tasks_completed=2,
            tasks_failed=0,
            total_duration_ms=120000,
            session_id="ralph-20260127-test",
        )

        with patch.object(engine._service, 'run', return_value=mock_result) as mock_run:
            with patch.object(engine._service, 'get_pending_tasks', return_value=[Mock(), Mock()]):
                result = engine.run()

            # Verify service.run was called
            mock_run.assert_called_once()

        # Verify result was converted to RunResult
        assert isinstance(result, RunResult)
        assert result.exit_code == ExitCode.SUCCESS
        assert result.tasks_completed == 2

    def test_run_engine_converts_orchestration_result_to_run_result(self):
        """RunEngine converts OrchestrationResult to RunResult."""
        deps = self._create_mock_dependencies()
        engine = RunEngine(**deps)

        orchestration_result = OrchestrationResult(
            exit_code=ExitCode.TASK_EXECUTION_FAILED,
            tasks_completed=1,
            tasks_failed=1,
            tasks_pending=3,
            total_duration_ms=60000,
            error="Task failed after max iterations",
            session_id="ralph-20260127-test",
        )

        with patch.object(engine._service, 'run', return_value=orchestration_result):
            with patch.object(engine._service, 'get_pending_tasks', return_value=[Mock()]):
                result = engine.run()

        # Verify all fields converted correctly
        assert result.exit_code == ExitCode.TASK_EXECUTION_FAILED
        assert result.tasks_completed == 1
        assert result.tasks_failed == 1
        assert result.tasks_pending == 3
        assert result.total_duration_ms == 60000
        assert result.error == "Task failed after max iterations"
        assert result.session_id == "ralph-20260127-test"

    def test_run_engine_delegates_event_registration(self):
        """RunEngine.on_event() delegates to service."""
        deps = self._create_mock_dependencies()
        engine = RunEngine(**deps)

        handler = Mock()

        with patch.object(engine._service, 'on_event') as mock_on_event:
            engine.on_event(EventType.TASK_STARTED, handler)

        mock_on_event.assert_called_once_with(EventType.TASK_STARTED, handler)

    def test_run_engine_delegates_global_event_registration(self):
        """RunEngine.on_all_events() delegates to service."""
        deps = self._create_mock_dependencies()
        engine = RunEngine(**deps)

        handler = Mock()

        with patch.object(engine._service, 'on_all_events') as mock_on_all:
            engine.on_all_events(handler)

        mock_on_all.assert_called_once_with(handler)


@pytest.mark.unit
class TestRunEngineEmptyTaskHandling:
    """Test RunEngine handling of empty task lists."""

    def _create_mock_dependencies(self):
        """Create mock dependencies for RunEngine."""
        config = Mock()
        config.repo_root = Path("/tmp/test")
        config.test_paths = ["tests/"]

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        session.session_id = "ralph-20260127-test"
        timeline = Mock()
        execution_logger = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()
        options = RunOptions()

        return {
            "config": config,
            "prd": prd,
            "session": session,
            "timeline": timeline,
            "execution_logger": execution_logger,
            "claude_runner": claude_runner,
            "gate_runner": gate_runner,
            "guardrail": guardrail,
            "options": options,
        }

    def test_run_engine_handles_no_pending_tasks(self):
        """RunEngine handles empty task list gracefully."""
        deps = self._create_mock_dependencies()
        engine = RunEngine(**deps)

        # Mock empty task list
        with patch.object(engine._service, 'get_pending_tasks', return_value=[]):
            result = engine.run()

        # Should return success with no tasks
        assert result.exit_code == ExitCode.SUCCESS
        assert result.tasks_completed == 0
        assert result.tasks_failed == 0


@pytest.mark.unit
class TestRunOptionsConversion:
    """Test RunOptions to OrchestrationOptions conversion."""

    def test_run_options_to_orchestration_options_preserves_all_fields(self):
        """RunOptions.to_orchestration_options() preserves all fields."""
        run_options = RunOptions(
            prd_json="/custom/path.json",
            task_id="T-123",
            from_task_id="T-100",
            max_iterations=75,
            gate_type="build",
            dry_run=True,
            resume=True,
            post_verify=False,
            verbose=True,  # Note: verbose is RunOptions-specific
        )

        orch_options = run_options.to_orchestration_options()

        # Verify all orchestration-relevant fields preserved
        assert orch_options.prd_json == "/custom/path.json"
        assert orch_options.task_id == "T-123"
        assert orch_options.from_task_id == "T-100"
        assert orch_options.max_iterations == 75
        assert orch_options.gate_type == "build"
        assert orch_options.dry_run is True
        assert orch_options.resume is True
        assert orch_options.post_verify is False

    def test_run_options_to_orchestration_options_excludes_cli_fields(self):
        """RunOptions.to_orchestration_options() excludes CLI-only fields."""
        run_options = RunOptions(verbose=True)
        orch_options = run_options.to_orchestration_options()

        # verbose is CLI-specific, should not be in OrchestrationOptions
        assert not hasattr(orch_options, 'verbose')


@pytest.mark.unit
class TestRunResultConversion:
    """Test RunResult creation from OrchestrationResult."""

    def test_run_result_from_orchestration_result_success(self):
        """RunResult.from_orchestration_result() converts success case."""
        orch_result = OrchestrationResult(
            exit_code=ExitCode.SUCCESS,
            tasks_completed=5,
            tasks_failed=0,
            tasks_pending=0,
            total_duration_ms=300000,
            session_id="ralph-20260127-test",
        )

        run_result = RunResult.from_orchestration_result(orch_result)

        assert run_result.exit_code == ExitCode.SUCCESS
        assert run_result.tasks_completed == 5
        assert run_result.tasks_failed == 0
        assert run_result.tasks_pending == 0
        assert run_result.total_duration_ms == 300000
        assert run_result.session_id == "ralph-20260127-test"
        assert run_result.error is None

    def test_run_result_from_orchestration_result_with_error(self):
        """RunResult.from_orchestration_result() converts error case."""
        orch_result = OrchestrationResult(
            exit_code=ExitCode.CONFIG_ERROR,
            error="Configuration file not found: ralph.yml",
            session_id=None,
        )

        run_result = RunResult.from_orchestration_result(orch_result)

        assert run_result.exit_code == ExitCode.CONFIG_ERROR
        assert run_result.error == "Configuration file not found: ralph.yml"
        assert run_result.tasks_completed == 0
        assert run_result.tasks_failed == 0
