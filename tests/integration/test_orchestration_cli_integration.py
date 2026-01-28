"""Integration tests for OrchestrationService CLI compatibility.

Tests that the new OrchestrationService maintains backward compatibility
with existing CLI functionality (ralph run command).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ralph_orchestrator.run import run_tasks, RunOptions

# Skip tests requiring mock when real Claude is configured
requires_mock = pytest.mark.skipif(
    "mock_claude" not in os.environ.get("RALPH_CLAUDE_CMD", ""),
    reason="Requires mock Claude (RALPH_CLAUDE_CMD set externally)"
)


@pytest.mark.integration
class TestCLICompatibility:
    """Test that ralph run command works with new orchestration service."""

    @requires_mock
    def test_ralph_run_with_orchestration_service(self, fixture_python_min, mock_scenario_default):
        """ralph run command executes successfully using new service."""
        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project description",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test task",
                    "description": "A simple test task",
                    "acceptanceCriteria": ["Code runs", "Tests pass"],
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

        # Run with new service
        options = RunOptions(
            prd_json=str(prd_path),
            max_iterations=5,
            gate_type="none",
            post_verify=False,
        )

        result = run_tasks(
            config_path=repo / ".ralph" / "ralph.yml",
            prd_path=prd_path,
            options=options,
        )

        # Verify execution completed successfully
        assert result.exit_code == 0
        assert result.tasks_completed == 1
        assert result.tasks_failed == 0
        assert result.session_id is not None

    def test_ralph_run_dry_run_mode(self, fixture_python_min):
        """ralph run --dry-run works with new service."""
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
                    "title": "Task 1",
                    "description": "First task",
                    "acceptanceCriteria": ["Done"],
                    "priority": 1,
                    "passes": False,
                    "notes": ""
                },
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "description": "Second task",
                    "acceptanceCriteria": ["Done"],
                    "priority": 2,
                    "passes": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Run dry-run
        options = RunOptions(
            prd_json=str(prd_path),
            dry_run=True,
        )

        result = run_tasks(
            config_path=repo / ".ralph" / "ralph.yml",
            prd_path=prd_path,
            options=options,
        )

        # Verify dry run completes without executing tasks
        assert result.exit_code == 0
        assert result.tasks_completed == 0
        assert result.tasks_pending == 2

    @requires_mock
    def test_ralph_run_creates_session_artifacts(self, fixture_python_min, mock_scenario_default):
        """ralph run creates expected session artifacts (logs, timeline)."""
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

        # Run tasks
        options = RunOptions(
            prd_json=str(prd_path),
            max_iterations=5,
            gate_type="none",
            post_verify=False,
        )

        result = run_tasks(
            config_path=repo / ".ralph" / "ralph.yml",
            prd_path=prd_path,
            options=options,
        )

        # Verify session artifacts exist
        session_dir = repo / ".ralph-session"
        assert session_dir.exists()

        assert (session_dir / "session.json").exists()
        assert (session_dir / "task-status.json").exists()
        assert (session_dir / "logs").is_dir()
        assert (session_dir / "logs" / "timeline.jsonl").exists()

    @requires_mock
    def test_ralph_run_with_specific_task_id(self, fixture_python_min, mock_scenario_default):
        """ralph run --task-id executes only specified task."""
        repo = fixture_python_min
        os.chdir(repo)

        # Prepare prd.json with multiple tasks
        prd_data = {
            "project": "Test Project",
            "branchName": "feature/test",
            "description": "Test project",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task 1",
                    "description": "First task",
                    "acceptanceCriteria": ["Done"],
                    "priority": 1,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                },
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "description": "Second task",
                    "acceptanceCriteria": ["Done"],
                    "priority": 2,
                    "passes": False,
                    "requiresTests": False,
                    "notes": ""
                }
            ]
        }

        prd_path = repo / ".ralph" / "prd.json"
        prd_path.parent.mkdir(exist_ok=True)
        prd_path.write_text(json.dumps(prd_data, indent=2))

        # Run with specific task ID
        options = RunOptions(
            prd_json=str(prd_path),
            task_id="T-002",
            max_iterations=5,
            gate_type="none",
            post_verify=False,
        )

        result = run_tasks(
            config_path=repo / ".ralph" / "ralph.yml",
            prd_path=prd_path,
            options=options,
        )

        # Verify only T-002 was executed
        assert result.exit_code == 0
        assert result.tasks_completed == 1

        # Verify T-001 is still pending
        prd_after = json.loads(prd_path.read_text())
        assert prd_after["tasks"][0]["passes"] is False  # T-001
        assert prd_after["tasks"][1]["passes"] is True   # T-002

    def test_ralph_run_with_invalid_config_path(self):
        """ralph run with invalid config path returns CONFIG_ERROR."""
        from ralph_orchestrator.services.orchestration_service import ExitCode

        result = run_tasks(
            config_path=Path("/nonexistent/ralph.yml"),
            options=RunOptions(),
        )

        assert result.exit_code == ExitCode.CONFIG_ERROR
        assert result.error is not None

    def test_ralph_run_with_invalid_prd_path(self, fixture_python_min):
        """ralph run with invalid prd.json path returns TASK_SOURCE_ERROR."""
        from ralph_orchestrator.services.orchestration_service import ExitCode
        repo = fixture_python_min
        os.chdir(repo)

        result = run_tasks(
            config_path=repo / ".ralph" / "ralph.yml",
            prd_path=Path("/nonexistent/prd.json"),
            options=RunOptions(),
        )

        assert result.exit_code == ExitCode.TASK_SOURCE_ERROR
        assert result.error is not None


@pytest.mark.integration
class TestRunEngineIntegration:
    """Test RunEngine class integration with OrchestrationService."""

    @requires_mock
    def test_run_engine_uses_orchestration_service(self, fixture_python_min, mock_scenario_default):
        """RunEngine delegates to OrchestrationService internally."""
        from ralph_orchestrator.config import load_config
        from ralph_orchestrator.tasks.prd import load_prd
        from ralph_orchestrator.session import create_session
        from ralph_orchestrator.timeline import create_timeline_logger
        from ralph_orchestrator.execution_log import create_execution_logger
        from ralph_orchestrator.agents.claude import create_claude_runner
        from ralph_orchestrator.gates import create_gate_runner
        from ralph_orchestrator.guardrails import create_guardrail
        from ralph_orchestrator.run import RunEngine, RunOptions

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

        # Set up components
        config = load_config(repo / ".ralph" / "ralph.yml")
        prd = load_prd(prd_path)
        session = create_session(
            task_source=str(prd_path),
            task_source_type="prd_json",
            config_path=str(config.path),
            pending_tasks=["T-001"],
            repo_root=config.repo_root,
        )
        timeline = create_timeline_logger(session.session_dir, session.session_id)
        exec_logger = create_execution_logger(session.session_dir, session.session_id, str(prd_path))
        claude_runner = create_claude_runner(config, session.logs_dir, timeline, config.repo_root)
        gate_runner = create_gate_runner(config, config.repo_root, session.logs_dir, timeline)
        guardrail = create_guardrail(config.test_paths, config.repo_root, timeline)

        options = RunOptions(
            max_iterations=5,
            gate_type="none",
            post_verify=False,
        )

        # Create engine
        engine = RunEngine(
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

        # Verify engine has service property
        assert engine.service is not None
        assert hasattr(engine.service, "run")
        assert hasattr(engine.service, "on_event")

        # Run the engine
        result = engine.run()

        # Verify result
        assert result.exit_code == 0
        assert result.tasks_completed == 1


@pytest.mark.integration
class TestBackwardCompatibility:
    """Test backward compatibility with existing run.py behavior."""

    def test_existing_unit_tests_still_pass(self, fixture_python_min):
        """Existing code that uses run.py still works."""
        # This test verifies that existing run.py exports are still available
        from ralph_orchestrator.run import (
            ExitCode,
            TaskRunResult,
            OrchestrationOptions,
            OrchestrationResult,
            RunEngine,
            RunOptions,
            run_tasks,
        )

        # All these should be importable without error
        assert ExitCode is not None
        assert TaskRunResult is not None
        assert OrchestrationOptions is not None
        assert OrchestrationResult is not None
        assert RunEngine is not None
        assert RunOptions is not None
        assert run_tasks is not None

    def test_run_options_converts_to_orchestration_options(self):
        """RunOptions.to_orchestration_options() works correctly."""
        from ralph_orchestrator.run import RunOptions
        from ralph_orchestrator.services.orchestration_service import OrchestrationOptions

        run_opts = RunOptions(
            prd_json="/path/to/prd.json",
            task_id="T-005",
            max_iterations=50,
            gate_type="build",
            dry_run=True,
            post_verify=False,
        )

        orch_opts = run_opts.to_orchestration_options()

        assert isinstance(orch_opts, OrchestrationOptions)
        assert orch_opts.prd_json == "/path/to/prd.json"
        assert orch_opts.task_id == "T-005"
        assert orch_opts.max_iterations == 50
        assert orch_opts.gate_type == "build"
        assert orch_opts.dry_run is True
        assert orch_opts.post_verify is False
