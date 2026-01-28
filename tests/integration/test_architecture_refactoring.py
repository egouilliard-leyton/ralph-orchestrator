"""Integration tests for architecture refactoring boundaries (T-001).

These tests validate that the components identified for extraction in the
architecture audit can be isolated and refactored without breaking existing
functionality.

Tests validate:
- Module independence and isolation
- Data flow through identified boundaries
- Facade pattern viability for backward compatibility
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_orchestrator.config import load_config
from ralph_orchestrator.session import create_session, load_session
from ralph_orchestrator.timeline import TimelineLogger, EventType, create_timeline_logger
from ralph_orchestrator.tasks.prd import load_prd, save_prd, get_pending_tasks, mark_task_complete
from ralph_orchestrator.gates import create_gate_runner, GateRunner
from ralph_orchestrator.signals import (
    validate_implementation_signal,
    validate_test_writing_signal,
    SignalType,
)
from ralph_orchestrator.agents.prompts import (
    build_implementation_prompt,
    build_test_writing_prompt,
    TaskContext,
)


# ============================================================================
# Session Service Extraction Validation
# ============================================================================

class TestSessionServiceExtraction:
    """Validate session.py can be wrapped as SessionService with no refactoring."""

    def test_session_is_stateless_factory(self, tmp_path: Path):
        """Verify session creation is stateless and pure."""
        # Session creation should be pure - same inputs = same structure
        session1 = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=tmp_path / "session1",
            repo_root=tmp_path,
        )

        session2 = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=tmp_path / "session2",
            repo_root=tmp_path,
        )

        # Should have same structure (but different session IDs)
        assert session1.metadata.task_source == session2.metadata.task_source
        assert session1.metadata.task_source_type == session2.metadata.task_source_type

    def test_session_operations_are_self_contained(self, tmp_path: Path):
        """Verify session operations don't depend on external state."""
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )

        # All operations should work through the session object
        session.start_task("T-001")
        session.increment_iterations("T-001")
        session.complete_task("T-001")

        # Verify persistence
        reloaded = load_session(
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )

        assert "T-001" in reloaded.metadata.completed_tasks
        assert reloaded.task_status.tasks["T-001"].passes is True

    def test_session_checksum_is_independent(self, tmp_path: Path):
        """Verify checksum validation is self-contained."""
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )

        # Checksum verification should work independently
        assert session.verify_checksum() is True


# ============================================================================
# Timeline Event Bus Integration Validation
# ============================================================================

class TestTimelineEventBusIntegration:
    """Validate TimelineLogger can be extended with EventBus."""

    def test_timeline_logger_accepts_session_correlation(self, tmp_path: Path):
        """Verify TimelineLogger supports session ID for event correlation."""
        timeline = TimelineLogger(
            timeline_path=tmp_path / "timeline.jsonl",
            session_id="test-session-123",
        )

        event = timeline.session_start(task_count=5)

        # Event should include session_id for correlation
        assert event.get("session_id") == "test-session-123"

    def test_timeline_events_are_structured(self, tmp_path: Path):
        """Verify timeline events have consistent structure for broadcasting."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")

        # Log various event types
        timeline.session_start(task_count=3)
        timeline.task_start("T-001", title="Test Task")
        timeline.agent_start("T-001", "implementation", model="claude-sonnet")
        timeline.gate_pass("pytest", duration_ms=1234)

        events = timeline.read_events()

        # All events should have required fields for WebSocket broadcasting
        for event in events:
            assert "ts" in event  # Timestamp
            assert "event" in event  # Event type

    def test_timeline_can_filter_by_task(self, tmp_path: Path):
        """Verify timeline supports task-specific event filtering."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")

        timeline.task_start("T-001", title="Task 1")
        timeline.agent_start("T-001", "implementation")
        timeline.task_start("T-002", title="Task 2")
        timeline.agent_start("T-002", "implementation")
        timeline.task_complete("T-001", iterations=1)

        # Should support filtering for real-time task-specific updates
        t001_events = timeline.get_events_for_task("T-001")
        assert len(t001_events) == 3  # start, agent_start, complete
        assert all(e.get("task_id") == "T-001" for e in t001_events)


# ============================================================================
# Gate Service Extraction Validation
# ============================================================================

class TestGateServiceExtraction:
    """Validate GateRunner can be extracted as GateService."""

    def test_gate_runner_is_reusable(self, fixture_python_min: Path):
        """Verify GateRunner can be instantiated and reused."""
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )

        timeline = create_timeline_logger(
            fixture_python_min / ".ralph-session" / "logs" / "timeline.jsonl"
        )

        # Should be able to create runner independently
        # Note: create_gate_runner takes config, not gates -
        # the runner internally uses config.get_gates() when run_gates() is called
        runner = create_gate_runner(
            config=config,
            timeline=timeline,
            repo_root=fixture_python_min,
            logs_dir=fixture_python_min / ".ralph-session" / "logs",
        )

        assert isinstance(runner, GateRunner)

    def test_gate_results_are_structured(self, fixture_python_min: Path):
        """Verify gate results have consistent structure."""
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )

        timeline = create_timeline_logger(
            fixture_python_min / ".ralph-session" / "logs" / "timeline.jsonl"
        )

        runner = create_gate_runner(
            config=config,
            timeline=timeline,
            repo_root=fixture_python_min,
            logs_dir=fixture_python_min / ".ralph-session" / "logs",
        )

        # Gate results should be structured for API responses
        # run_gates returns GatesResult which has 'passed', 'results', and 'total_duration_ms'
        result = runner.run_gates(gate_type="build", task_id="TEST")

        assert hasattr(result, 'passed')
        assert hasattr(result, 'results')  # GatesResult uses 'results' not 'gate_results'
        assert hasattr(result, 'total_duration_ms')  # Property name is 'total_duration_ms'


# ============================================================================
# Agent Prompt Service Extraction Validation
# ============================================================================

class TestAgentPromptServiceExtraction:
    """Validate agent prompt building can be extracted as service."""

    def test_prompt_building_is_pure(self, fixture_python_min: Path):
        """Verify prompt building is pure function (same input = same output)."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        task = prd.tasks[0]

        context = TaskContext(
            task_id=task.id,
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
        )

        # Build prompt twice with same parameters
        prompt1 = build_implementation_prompt(
            context,
            session_token="ralph-test-session",
            project_description=prd.description,
            report_path=str(Path("/tmp/report.md")),
        )
        prompt2 = build_implementation_prompt(
            context,
            session_token="ralph-test-session",
            project_description=prd.description,
            report_path=str(Path("/tmp/report.md")),
        )

        # Should be identical (pure function)
        assert prompt1 == prompt2

    def test_prompts_contain_required_elements(self, fixture_python_min: Path):
        """Verify prompts contain required session tokens and signals."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        task = prd.tasks[0]

        context = TaskContext(
            task_id=task.id,
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
        )

        impl_prompt = build_implementation_prompt(
            context,
            session_token="ralph-test-12345",
            project_description=prd.description,
            report_path=str(Path("/tmp/report.md")),
        )
        test_prompt = build_test_writing_prompt(
            context,
            session_token="ralph-test-12345",
            test_paths=["tests/**/*.py"],
            project_description=prd.description,
            report_path=str(Path("/tmp/report.md")),
        )

        # Prompts must include session token for anti-gaming
        assert "ralph-test-12345" in impl_prompt
        assert "ralph-test-12345" in test_prompt

        # Prompts must include completion signal instructions
        assert "<task-done" in impl_prompt
        assert "<tests-done" in test_prompt


# ============================================================================
# Signal Parsing Service Validation
# ============================================================================

class TestSignalParsingService:
    """Validate signal parsing is pure and reusable."""

    def test_signal_validation_is_pure(self):
        """Verify signal validation is stateless."""
        response = """
Implementation complete.

<task-done session="ralph-test-123">
All changes implemented successfully.
</task-done>
"""

        # Validate twice - should get same result
        result1 = validate_implementation_signal(response, "ralph-test-123")
        result2 = validate_implementation_signal(response, "ralph-test-123")

        # SignalValidationResult has 'valid' and 'signal' attributes
        # signal.signal_type contains the SignalType enum
        assert result1.signal.signal_type == result2.signal.signal_type
        assert result1.valid == result2.valid
        assert result1.signal.signal_type == SignalType.TASK_DONE

    def test_signal_validation_detects_invalid_tokens(self):
        """Verify signal validation detects token mismatches."""
        response = """
<task-done session="ralph-wrong-token">
Done
</task-done>
"""

        result = validate_implementation_signal(response, "ralph-correct-token")

        assert result.signal.signal_type == SignalType.TASK_DONE
        assert result.valid is False  # valid is False when token doesn't match


# ============================================================================
# PRD Task Service Extraction Validation
# ============================================================================

class TestPRDTaskServiceExtraction:
    """Validate PRD operations can be extracted as TaskService."""

    def test_prd_operations_are_independent(self, fixture_python_min: Path, tmp_path: Path):
        """Verify PRD operations don't depend on CLI context."""
        # Copy PRD to temp location
        original_prd = fixture_python_min / ".ralph" / "prd.json"
        temp_prd = tmp_path / "prd.json"
        temp_prd.write_text(original_prd.read_text())

        # Load and manipulate independently
        prd = load_prd(temp_prd)
        pending = get_pending_tasks(prd)

        assert len(pending) > 0

        # Mark task complete
        mark_task_complete(prd, pending[0].id, notes="Done", save=True)

        # Reload and verify
        reloaded = load_prd(temp_prd)
        assert reloaded.tasks[0].passes is True

    def test_task_filtering_supports_api_queries(self, fixture_python_min: Path):
        """Verify task filtering supports REST API use cases."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")

        # Should support various filtering patterns for API
        all_pending = get_pending_tasks(prd)
        specific_task = get_pending_tasks(prd, task_id="T-001")

        assert len(specific_task) <= 1
        assert len(all_pending) >= len(specific_task)


# ============================================================================
# Config Service Extraction Validation
# ============================================================================

class TestConfigServiceExtraction:
    """Validate config loading can be extracted as ConfigService."""

    def test_config_loading_is_stateless(self, fixture_python_min: Path):
        """Verify config loading is pure and repeatable."""
        config_path = fixture_python_min / ".ralph" / "ralph.yml"

        # Load twice
        config1 = load_config(config_path, repo_root=fixture_python_min)
        config2 = load_config(config_path, repo_root=fixture_python_min)

        # Should be equivalent
        assert config1.version == config2.version
        assert config1.task_source_type == config2.task_source_type

    def test_config_supports_path_resolution(self, fixture_python_min: Path):
        """Verify config path resolution works for services."""
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )

        # Should resolve paths relative to repo root
        resolved = config.resolve_path(".ralph/prd.json")
        assert resolved.is_absolute()
        assert resolved.exists()


# ============================================================================
# Backward Compatibility Facade Validation
# ============================================================================

class TestBackwardCompatibilityFacades:
    """Validate facade pattern for backward compatibility."""

    def test_session_factories_can_wrap_service(self, tmp_path: Path):
        """Verify session factories can be thin wrappers."""
        # Current factory-based approach supports facade pattern
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )

        # Factory returns Session object - can be wrapped by service
        assert hasattr(session, 'start_task')
        assert hasattr(session, 'complete_task')

    def test_timeline_factory_supports_dependency_injection(self, tmp_path: Path):
        """Verify timeline factory supports DI for EventBus."""
        # Factory pattern allows injecting EventBus in future
        timeline = create_timeline_logger(
            tmp_path / "timeline.jsonl",
            session_id="test-123",
        )

        # Current interface is clean for extension
        assert hasattr(timeline, 'log')
        assert hasattr(timeline, 'timeline_path')


# ============================================================================
# Data Flow Validation Through Boundaries
# ============================================================================

class TestDataFlowThroughBoundaries:
    """Validate data flows correctly through identified service boundaries."""

    def test_config_to_gates_data_flow(self, fixture_python_min: Path):
        """Verify data flows from config to gate execution."""
        # Config -> Gates boundary
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )

        gates = config.get_gates("build")
        assert len(gates) > 0

        # Gates should be usable by GateService
        # Note: create_gate_runner takes config object, gates are accessed internally
        timeline = create_timeline_logger(
            fixture_python_min / ".ralph-session" / "logs" / "timeline.jsonl"
        )

        runner = create_gate_runner(
            config=config,
            timeline=timeline,
            repo_root=fixture_python_min,
            logs_dir=fixture_python_min / ".ralph-session" / "logs",
        )

        assert runner is not None

    def test_prd_to_task_context_data_flow(self, fixture_python_min: Path):
        """Verify data flows from PRD to task execution context."""
        # PRD -> TaskContext boundary
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        task = prd.tasks[0]

        # Should be able to create TaskContext from PRD
        context = TaskContext(
            task_id=task.id,
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
        )

        # Context should be usable for prompt generation
        prompt = build_implementation_prompt(
            context,
            session_token="ralph-test",
            project_description=prd.description,
            report_path=str(Path("/tmp/report.md")),
        )
        assert task.id in prompt
        assert task.title in prompt

    def test_session_to_timeline_data_flow(self, tmp_path: Path):
        """Verify session and timeline can coordinate."""
        # Session <-> Timeline boundary
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )

        timeline = create_timeline_logger(
            session.session_dir,
            session_id=session.session_id,
        )

        # Should be able to log coordinated events
        timeline.session_start(task_count=1)
        session.start_task("T-001")
        timeline.task_start("T-001", title="Test")

        events = timeline.read_events()
        assert len(events) == 2
        assert all(e.get("session_id") == session.session_id for e in events)
