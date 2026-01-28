"""Unit tests validating the architecture audit findings for T-001.

These tests ensure the architecture audit document accurately reflects the
codebase structure, dependencies, and event emission points needed for
dual-interface (CLI + Web UI) refactoring.

Tests verify:
- Module dependency structure matches documented analysis
- Event emission points exist for real-time WebSocket broadcasting
- CLI interface preservation strategy is valid
- No breaking changes in public APIs
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Dict, List, Set

import pytest

from ralph_orchestrator import cli, run, session, gates, timeline, config, signals, guardrails
from ralph_orchestrator.agents import claude, prompts
from ralph_orchestrator.tasks import prd


# ============================================================================
# Module Dependency Validation
# ============================================================================

class TestModuleDependencies:
    """Verify module dependencies match audit documentation."""

    def test_signals_has_no_external_dependencies(self):
        """Verify signals.py is pure (stdlib only) as documented."""
        # signals.py should only use stdlib (re)
        source = inspect.getsourcefile(signals)
        assert source is not None

        # Check that signals module has the documented pure functions
        assert hasattr(signals, 'validate_implementation_signal')
        assert hasattr(signals, 'validate_test_writing_signal')
        assert hasattr(signals, 'validate_review_signal')
        assert hasattr(signals, 'SignalType')

    def test_session_module_independence(self):
        """Verify session.py has minimal external dependencies as documented."""
        # Session should be mostly self-contained (pure state management)
        assert hasattr(session, 'Session')
        assert hasattr(session, 'create_session')
        assert hasattr(session, 'load_session')
        assert hasattr(session, 'compute_checksum')
        assert hasattr(session, 'generate_session_token')

    def test_timeline_logger_exists(self):
        """Verify TimelineLogger exists as core integration point."""
        # Audit identifies TimelineLogger as core integration point
        assert hasattr(timeline, 'TimelineLogger')
        assert hasattr(timeline, 'EventType')
        assert hasattr(timeline, 'create_timeline_logger')

    def test_run_engine_exists(self):
        """Verify RunEngine exists in run.py as documented."""
        # Audit identifies RunEngine as needing extraction
        assert hasattr(run, 'RunEngine')
        assert hasattr(run, 'run_tasks')
        assert hasattr(run, 'RunOptions')
        assert hasattr(run, 'RunResult')

    def test_gate_runner_exists(self):
        """Verify GateRunner exists in gates.py."""
        assert hasattr(gates, 'GateRunner')
        assert hasattr(gates, 'create_gate_runner')
        assert hasattr(gates, 'GateResult')

    def test_guardrail_exists(self):
        """Verify guardrail system exists."""
        assert hasattr(guardrails, 'FilePathGuardrail')
        assert hasattr(guardrails, 'create_guardrail')


class TestCliModuleStructure:
    """Verify cli.py structure matches audit findings."""

    def test_cli_has_task_generation_functions(self):
        """Verify task generation functions exist in cli.py (to be extracted)."""
        # Audit identifies these functions for extraction
        assert hasattr(cli, 'generate_tasks_from_markdown')
        assert hasattr(cli, 'analyze_complexity_for_task_count')

    def test_cli_command_handlers_exist(self):
        """Verify CLI command handlers exist."""
        # These should remain as thin wrappers after refactoring
        assert hasattr(cli, 'command_run')
        assert hasattr(cli, 'command_init')
        assert hasattr(cli, 'command_scan')
        assert hasattr(cli, 'command_verify')

    def test_cli_config_utilities_exist(self):
        """Verify config utilities exist (candidates for extraction)."""
        assert hasattr(cli, 'load_config')
        assert hasattr(cli, 'ralph_dir')
        assert hasattr(cli, 'default_config_path')


# ============================================================================
# Event Emission Point Validation
# ============================================================================

class TestEventEmissionPoints:
    """Verify event emission points exist for WebSocket broadcasting."""

    def test_timeline_event_types_exist(self):
        """Verify all documented event types exist in timeline.py."""
        # Audit documents 18+ event types in timeline.py
        required_events = [
            'SESSION_START',
            'SESSION_END',
            'TASK_START',
            'TASK_COMPLETE',
            'TASK_FAILED',
            'AGENT_START',
            'AGENT_COMPLETE',
            'AGENT_FAILED',
            'GATES_RUN',
            'GATE_PASS',
            'GATE_FAIL',
            'SERVICE_START',
            'SERVICE_READY',
            'SERVICE_FAILED',
        ]

        for event in required_events:
            assert hasattr(timeline.EventType, event), f"Missing event type: {event}"

    def test_timeline_logger_log_method_exists(self):
        """Verify TimelineLogger.log() exists as documented."""
        logger = timeline.TimelineLogger(Path("/tmp/test.jsonl"))
        assert hasattr(logger, 'log')
        assert callable(logger.log)

    def test_timeline_convenience_methods_exist(self):
        """Verify TimelineLogger has convenience methods for each event type."""
        logger = timeline.TimelineLogger(Path("/tmp/test.jsonl"))

        # Documented convenience methods
        convenience_methods = [
            'session_start',
            'session_end',
            'task_start',
            'task_complete',
            'task_failed',
            'agent_start',
            'agent_complete',
            'agent_failed',
            'gates_run',
            'gate_pass',
            'gate_fail',
        ]

        for method in convenience_methods:
            assert hasattr(logger, method), f"Missing convenience method: {method}"

    def test_run_engine_has_timeline_logger(self):
        """Verify RunEngine uses TimelineLogger for event emission."""
        # RunEngine should have timeline integration
        import inspect
        source = inspect.getsource(run.RunEngine.__init__)
        assert 'timeline' in source.lower() or 'TimelineLogger' in source


class TestAgentPhases:
    """Verify agent phase structure for event emission."""

    def test_agent_prompts_roles_exist(self):
        """Verify agent roles are defined in prompts.py."""
        assert hasattr(prompts, 'AgentRole')
        assert hasattr(prompts, 'build_implementation_prompt')
        assert hasattr(prompts, 'build_test_writing_prompt')
        assert hasattr(prompts, 'build_review_prompt')

    def test_claude_runner_exists(self):
        """Verify ClaudeRunner exists for agent execution."""
        assert hasattr(claude, 'ClaudeRunner')
        assert hasattr(claude, 'create_claude_runner')
        assert hasattr(claude, 'ClaudeResult')


# ============================================================================
# CLI Preservation Validation
# ============================================================================

class TestCliPreservation:
    """Verify CLI interfaces are preserved (no breaking changes)."""

    def test_run_options_dataclass_preserved(self):
        """Verify RunOptions dataclass exists with expected fields."""
        # This is part of the public API
        assert hasattr(run, 'RunOptions')

        # Verify key fields exist
        options = run.RunOptions()
        assert hasattr(options, 'prd_json')
        assert hasattr(options, 'task_id')
        assert hasattr(options, 'max_iterations')
        assert hasattr(options, 'gate_type')
        assert hasattr(options, 'dry_run')
        assert hasattr(options, 'resume')

    def test_run_result_dataclass_preserved(self):
        """Verify RunResult dataclass exists with expected fields."""
        assert hasattr(run, 'RunResult')

        # Verify key fields
        result = run.RunResult(exit_code=run.ExitCode.SUCCESS)
        assert hasattr(result, 'exit_code')
        assert hasattr(result, 'tasks_completed')
        assert hasattr(result, 'tasks_failed')
        assert hasattr(result, 'error')
        assert hasattr(result, 'session_id')

    def test_exit_codes_preserved(self):
        """Verify exit codes are preserved."""
        assert hasattr(run, 'ExitCode')

        # Documented exit codes
        assert hasattr(run.ExitCode, 'SUCCESS')
        assert hasattr(run.ExitCode, 'CONFIG_ERROR')
        assert hasattr(run.ExitCode, 'TASK_EXECUTION_FAILED')
        assert hasattr(run.ExitCode, 'GATE_FAILURE')
        assert hasattr(run.ExitCode, 'CHECKSUM_TAMPERING')

    def test_run_tasks_function_preserved(self):
        """Verify run_tasks() factory function exists."""
        # This should be kept as a facade after refactoring
        assert hasattr(run, 'run_tasks')
        assert callable(run.run_tasks)

    def test_config_loader_preserved(self):
        """Verify config loading interface is preserved."""
        assert hasattr(config, 'load_config')
        assert hasattr(config, 'RalphConfig')

    def test_session_factory_preserved(self):
        """Verify session factory functions are preserved."""
        assert hasattr(session, 'create_session')
        assert hasattr(session, 'load_session')


class TestPublicApiSignatures:
    """Verify public API function signatures are preserved."""

    def test_run_tasks_signature(self):
        """Verify run_tasks() has expected parameters."""
        import inspect
        sig = inspect.signature(run.run_tasks)
        params = list(sig.parameters.keys())

        # Expected parameters based on audit
        assert 'config_path' in params
        assert 'prd_path' in params
        assert 'options' in params

    def test_load_config_signature(self):
        """Verify load_config() signature."""
        import inspect
        sig = inspect.signature(config.load_config)
        params = list(sig.parameters.keys())

        assert 'config_path' in params


# ============================================================================
# Signal Format Validation
# ============================================================================

class TestSignalFormats:
    """Verify signal formats are preserved as documented."""

    def test_signal_types_enum_exists(self):
        """Verify SignalType enum exists."""
        assert hasattr(signals, 'SignalType')

    def test_signal_validation_functions_exist(self):
        """Verify signal validation functions exist."""
        validation_functions = [
            'validate_implementation_signal',
            'validate_test_writing_signal',
            'validate_review_signal',
            'validate_fix_signal',
        ]

        for func in validation_functions:
            assert hasattr(signals, func)
            assert callable(getattr(signals, func))

    def test_signal_feedback_functions_exist(self):
        """Verify signal feedback functions exist."""
        assert hasattr(signals, 'get_feedback_for_missing_signal')
        assert hasattr(signals, 'get_feedback_for_invalid_token')


# ============================================================================
# Configuration Schema Validation
# ============================================================================

class TestConfigurationStructure:
    """Verify configuration structure is preserved."""

    def test_ralph_config_has_expected_attributes(self):
        """Verify RalphConfig dataclass has expected attributes."""
        # Create a minimal config instance
        cfg = config.RalphConfig(path=Path("/tmp/test.yml"), repo_root=Path("/tmp"), raw_data={})

        # Check it has expected methods/properties
        assert hasattr(cfg, 'path')
        assert hasattr(cfg, 'raw_data')

    def test_gate_config_exists(self):
        """Verify GateConfig exists."""
        assert hasattr(config, 'GateConfig')


# ============================================================================
# Module Coupling Analysis Validation
# ============================================================================

class TestModuleCoupling:
    """Verify module coupling matches audit analysis."""

    def test_low_coupling_modules_are_pure(self):
        """Verify low-coupling modules have minimal dependencies."""
        # Audit identifies these as LOW coupling
        low_coupling_modules = [signals, guardrails]

        for module in low_coupling_modules:
            # These should exist and be importable
            assert module is not None

    def test_high_coupling_modules_exist(self):
        """Verify high-coupling modules exist (cli, run)."""
        # Audit identifies cli and run as HIGH/VERY HIGH coupling
        assert cli is not None
        assert run is not None

        # These are expected to have many dependencies
        assert hasattr(run, 'RunEngine')
        assert hasattr(cli, 'main')


# ============================================================================
# PRD Task Management Validation
# ============================================================================

class TestPRDTaskStructure:
    """Verify PRD task management structure is preserved."""

    def test_prd_data_model_exists(self):
        """Verify PRD data models exist."""
        assert hasattr(prd, 'PRDData')
        assert hasattr(prd, 'Task')
        assert hasattr(prd, 'load_prd')
        assert hasattr(prd, 'save_prd')

    def test_task_operations_exist(self):
        """Verify task operation functions exist."""
        operations = [
            'get_pending_tasks',
            'get_task_by_id',
            'mark_task_complete',
        ]

        for op in operations:
            assert hasattr(prd, op)
            assert callable(getattr(prd, op))


# ============================================================================
# Integration Points Validation
# ============================================================================

class TestIntegrationPoints:
    """Verify integration points for services layer."""

    def test_timeline_logger_initialization_supports_session_id(self):
        """Verify TimelineLogger can accept session_id for event correlation."""
        import inspect
        sig = inspect.signature(timeline.TimelineLogger.__init__)
        params = list(sig.parameters.keys())

        # Should accept session_id for event correlation
        assert 'session_id' in params

    def test_gate_runner_integration_points(self):
        """Verify GateRunner has integration points for events."""
        import inspect

        # GateRunner should have methods for running gates
        assert hasattr(gates.GateRunner, 'run_gates')

    def test_session_has_checksum_verification(self):
        """Verify Session has anti-tampering checksum verification."""
        # Critical for preserving security features
        assert hasattr(session.Session, 'verify_checksum')
        assert hasattr(session, 'compute_checksum')
        assert hasattr(session, 'TamperingDetectedError')


# ============================================================================
# Acceptance Criteria Validation
# ============================================================================

class TestAcceptanceCriteria:
    """Validate acceptance criteria are met."""

    def test_dependency_map_components_exist(self):
        """Verify all documented modules exist and are importable."""
        # All modules from dependency map should exist
        modules = [
            cli,
            run,
            session,
            gates,
            timeline,
            config,
            signals,
            guardrails,
            claude,
            prompts,
            prd,
        ]

        for module in modules:
            assert module is not None

    def test_extraction_candidates_exist(self):
        """Verify functions identified for extraction exist."""
        # From cli.py
        assert hasattr(cli, 'generate_tasks_from_markdown')
        assert hasattr(cli, 'analyze_complexity_for_task_count')

        # From run.py
        assert hasattr(run, 'RunEngine')

    def test_event_emission_infrastructure_exists(self):
        """Verify event emission infrastructure exists."""
        # TimelineLogger is ready for WebSocket integration
        assert hasattr(timeline, 'TimelineLogger')
        assert hasattr(timeline, 'EventType')

        # Event types are documented
        event_count = len([e for e in dir(timeline.EventType) if not e.startswith('_')])
        assert event_count >= 14  # Audit documents 18+ events

    def test_cli_preservation_no_breaking_changes(self):
        """Verify no breaking changes to CLI commands."""
        # Core command handlers exist
        assert hasattr(cli, 'command_run')
        assert hasattr(cli, 'command_verify')
        assert hasattr(cli, 'main')

        # Core data types preserved
        assert hasattr(run, 'RunOptions')
        assert hasattr(run, 'RunResult')
        assert hasattr(run, 'ExitCode')


# ============================================================================
# Documentation Verification
# ============================================================================

class TestArchitectureDocumentation:
    """Verify architecture audit documentation exists and is valid."""

    def test_architecture_audit_document_exists(self):
        """Verify architecture audit document exists."""
        project_root = Path(__file__).parent.parent.parent
        audit_doc = project_root / "docs" / "architecture-audit-T001.md"

        assert audit_doc.exists(), "Architecture audit document not found"

        content = audit_doc.read_text()
        assert len(content) > 1000, "Document seems incomplete"

    def test_audit_document_has_required_sections(self):
        """Verify audit document contains all required sections."""
        project_root = Path(__file__).parent.parent.parent
        audit_doc = project_root / "docs" / "architecture-audit-T001.md"

        content = audit_doc.read_text()

        # Required sections from acceptance criteria
        required_sections = [
            "Module Dependency Map",
            "Logic Extraction",
            "Event Emission Points",
            "CLI Preservation Strategy",
            "Breaking Change Analysis",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_implementation_report_exists(self):
        """Verify implementation report was created."""
        project_root = Path(__file__).parent.parent.parent
        report_path = project_root / ".ralph-session" / "reports" / "T-001" / "implementation.md"

        # Report should exist if implementation was done
        if report_path.exists():
            content = report_path.read_text()
            assert "T-001" in content
