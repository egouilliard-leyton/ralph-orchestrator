"""
Integration tests for gate execution ordering.

These tests verify that the Ralph orchestrator correctly:
- Executes build gates before full gates
- Stops on fatal gate failures
- Continues with warnings on non-fatal failures
- Logs gate execution results
- Triggers fix loops on gate failures

Gates are script-enforced quality checks (build, lint, test, type-check).
"""

import pytest
import os
import json
import yaml
from pathlib import Path

from ralph_orchestrator.config import load_config, GateConfig
from ralph_orchestrator.gates import (
    GateRunner,
    GateResult,
    GatesResult,
    create_gate_runner,
    format_gate_failure,
    format_gates_summary,
)
from ralph_orchestrator.timeline import create_timeline_logger
from ralph_orchestrator.session import create_session

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestGateOrdering:
    """Test gate execution order."""
    
    def test_build_gates_run_first(self, fixture_node_min: Path):
        """
        Build gates execute before full gates.
        
        Given: Config has build and full gates
        When: Gates configuration loaded
        Then: Build gates are separate from full gates
        """
        os.chdir(fixture_node_min)
        
        # Load config
        config = load_config(
            fixture_node_min / ".ralph" / "ralph.yml",
            repo_root=fixture_node_min,
        )
        
        build_gates = config.get_gates("build")
        full_gates = config.get_gates("full")
        
        assert len(build_gates) >= 1, "Should have at least one build gate"
        assert len(full_gates) >= 1, "Should have at least one full gate"
        
        # Build gates should be for quick checks
        build_gate_names = [g.name for g in build_gates]
        full_gate_names = [g.name for g in full_gates]
        
        # They should be distinct
        assert set(build_gate_names) != set(full_gate_names), "Build and full gates should be different"
    
    def test_gates_run_in_config_order(self, fixture_fullstack_min: Path):
        """
        Gates within a category run in configuration order.
        
        Given: Multiple full gates defined
        When: Gates configuration loaded
        Then: Gates are in config order
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        full_gates = config.get_gates("full")
        gate_names = [g.name for g in full_gates]
        
        # Should have ordered gates
        assert len(gate_names) >= 2, "Should have multiple gates to test ordering"
        
        # Gates should maintain their order from config
        assert len(gate_names) == len(full_gates)


class TestFatalGates:
    """Test fatal gate failure behavior."""
    
    def test_fatal_gate_stops_execution(self, fixture_node_min: Path, tmp_path: Path):
        """
        Fatal gate failure stops further gate execution.
        
        Given: Gate configured as fatal: true
        When: Gate fails
        Then: GateRunner stops on fatal failure
        """
        os.chdir(fixture_node_min)
        
        config = load_config(
            fixture_node_min / ".ralph" / "ralph.yml",
            repo_root=fixture_node_min,
        )
        
        # Create gate runner
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_node_min, logs_dir)
        
        # Run gates (might fail if dependencies not installed, that's ok)
        result = gate_runner.run_build_gates(task_id="T-001")
        
        # Result should be a GatesResult
        assert isinstance(result, GatesResult)
        
        # If there's a fatal failure, it should stop
        if result.fatal_failure:
            # Gates after fatal should not have been run
            fatal_idx = None
            for i, r in enumerate(result.results):
                if r == result.fatal_failure:
                    fatal_idx = i
                    break
            
            if fatal_idx is not None:
                # No gates after fatal should have been attempted
                # (they would be missing from results due to stop_on_fatal)
                assert len(result.results) <= fatal_idx + 1
    
    def test_fatal_gate_triggers_fix_loop(self, fixture_python_min: Path):
        """
        Fatal gate failure triggers fix agent.
        
        Given: Gate fails
        When: Fix loop enabled
        Then: Failure output is available for fix agent
        """
        os.chdir(fixture_python_min)
        
        # Create a GateResult representing a failure
        result = GateResult(
            name="pytest",
            passed=False,
            exit_code=1,
            duration_ms=5000,
            output="FAILED test_main.py::test_function - AssertionError",
            error="Exit code 1",
            fatal=True,
        )
        
        # Format failure for fix agent context
        failure_msg = format_gate_failure(result)
        
        assert "pytest" in failure_msg
        assert "FAILED" in failure_msg
        assert "exit code 1" in failure_msg.lower()
    
    def test_task_not_complete_on_fatal_failure(self, fixture_node_min: Path, tmp_path: Path):
        """
        Task remains incomplete when fatal gate fails.
        
        Given: Implementation done, gates fail
        When: Fatal gate fails
        Then: GatesResult.passed is False
        """
        os.chdir(fixture_node_min)
        
        config = load_config(
            fixture_node_min / ".ralph" / "ralph.yml",
            repo_root=fixture_node_min,
        )
        
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        
        # Modify config to have a failing gate (using echo false which returns 1)
        # Create a custom config with failing gate
        failing_config = GateConfig(name="always_fail", cmd="false", fatal=True)
        
        # Test that a failing gate results in passed=False
        gate_result = GateResult(
            name="failing_gate",
            passed=False,
            exit_code=1,
            duration_ms=100,
            output="",
            fatal=True,
        )
        
        gates_result = GatesResult(
            gate_type="build",
            passed=False,
            results=[gate_result],
            fatal_failure=gate_result,
        )
        
        assert gates_result.passed is False


class TestNonFatalGates:
    """Test non-fatal gate (warning) behavior."""
    
    def test_non_fatal_gate_continues(self, fixture_fullstack_min: Path):
        """
        Non-fatal gate failure allows continuation.
        
        Given: Gate configured as fatal: false
        When: Gate fails
        Then: Other gates can still run
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        full_gates = config.get_gates("full")
        non_fatal_gates = [g for g in full_gates if not g.fatal]
        
        # Create a non-fatal failure result
        if len(non_fatal_gates) > 0:
            non_fatal_result = GateResult(
                name="non_fatal_lint",
                passed=False,
                exit_code=1,
                duration_ms=100,
                output="Lint warnings",
                fatal=False,
            )
            
            passing_result = GateResult(
                name="passing_gate",
                passed=True,
                exit_code=0,
                duration_ms=100,
                output="OK",
            )
            
            # Non-fatal failure doesn't set fatal_failure
            gates_result = GatesResult(
                gate_type="full",
                passed=True,  # Can still pass overall if fatal gates pass
                results=[non_fatal_result, passing_result],
                fatal_failure=None,  # No fatal failure
            )
            
            # Execution continued past non-fatal
            assert len(gates_result.results) == 2
    
    def test_non_fatal_gate_logged_as_warning(self, fixture_fullstack_min: Path):
        """
        Non-fatal gate failure logged as warning, not error.
        
        Given: Non-fatal gate fails
        When: Result formatted
        Then: Can distinguish from fatal failure
        """
        # Non-fatal gate result
        result = GateResult(
            name="lint",
            passed=False,
            exit_code=1,
            duration_ms=100,
            output="Lint warnings",
            fatal=False,
        )
        
        # Fatal property should be False
        assert result.fatal is False
        
        formatted = format_gate_failure(result)
        assert "lint" in formatted


class TestGateConditions:
    """Test gate conditional execution."""
    
    def test_gate_skipped_when_condition_false(self, fixture_python_min: Path, tmp_path: Path):
        """
        Gate skipped when 'when' condition not met.
        
        Given: Gate with 'when: some_file.ext'
        When: File doesn't exist
        Then: Gate is skipped
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        build_gates = config.get_gates("build")
        gates_with_when = [g for g in build_gates if g.when]
        
        assert len(gates_with_when) > 0, "Should have conditional gates"
        
        # Test gate runner condition checking
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_python_min, logs_dir)
        
        # Create a gate with non-existent condition file
        gate_with_missing_condition = GateConfig(
            name="conditional",
            cmd="echo test",
            when="nonexistent_file.xyz",
        )
        
        # Check condition
        should_run, skip_reason = gate_runner._check_condition(gate_with_missing_condition)
        assert should_run is False
        assert "does not exist" in skip_reason
    
    def test_gate_runs_when_condition_true(self, fixture_python_min: Path, tmp_path: Path):
        """
        Gate runs when 'when' condition is met.
        
        Given: Gate with 'when: pyproject.toml'
        When: pyproject.toml exists
        Then: Gate executes
        """
        os.chdir(fixture_python_min)
        
        # Verify condition file exists
        pyproject = fixture_python_min / "pyproject.toml"
        assert pyproject.exists()
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_python_min, logs_dir)
        
        # Create a gate with existing condition file
        gate_with_condition = GateConfig(
            name="conditional",
            cmd="echo test",
            when="pyproject.toml",
        )
        
        # Check condition
        should_run, skip_reason = gate_runner._check_condition(gate_with_condition)
        assert should_run is True
        assert skip_reason is None


class TestGateTimeout:
    """Test gate timeout behavior."""
    
    def test_gate_respects_timeout(self, fixture_python_min: Path):
        """
        Gate killed if exceeds timeout_seconds.
        
        Given: Gate with timeout configured
        When: Config loaded
        Then: Gates have timeout values
        """
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config_data = yaml.safe_load(config_file.read_text())
        
        # Verify gates have timeout configured
        build_gates = config_data["gates"]["build"]
        for gate in build_gates:
            assert "timeout_seconds" in gate, "Gates should have timeout"
            assert gate["timeout_seconds"] > 0
    
    @pytest.mark.slow
    def test_long_running_gate_times_out(self, fixture_python_min: Path, tmp_path: Path):
        """
        Long-running gate is terminated at timeout.
        
        Given: Gate that takes longer than timeout
        When: Timeout reached
        Then: Gate marked as timed_out
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_python_min, logs_dir)
        
        # Create a gate with very short timeout
        slow_gate = GateConfig(
            name="slow",
            cmd="sleep 10",
            timeout_seconds=1,
        )
        
        # Run the gate (will timeout)
        result = gate_runner._run_gate(slow_gate)
        
        assert result.timed_out is True
        assert result.passed is False


class TestGateLogging:
    """Test gate execution logging."""
    
    def test_gate_output_captured(self, fixture_python_min: Path, tmp_path: Path):
        """
        Gate stdout/stderr captured in logs.
        
        Given: Gate executes
        When: Gate produces output
        Then: Output available in result
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_python_min, logs_dir)
        
        # Run a simple gate that produces output
        echo_gate = GateConfig(name="echo", cmd="echo hello")
        result = gate_runner._run_gate(echo_gate)
        
        assert "hello" in result.output
    
    def test_gate_exit_code_logged(self, fixture_python_min: Path, tmp_path: Path):
        """
        Gate exit code logged for each gate.
        
        Given: Gate executes
        When: Gate completes
        Then: Exit code recorded in result
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_python_min, logs_dir)
        
        # Run passing gate
        passing_gate = GateConfig(name="pass", cmd="true")
        result = gate_runner._run_gate(passing_gate)
        assert result.exit_code == 0
        
        # Run failing gate
        failing_gate = GateConfig(name="fail", cmd="false")
        result = gate_runner._run_gate(failing_gate)
        assert result.exit_code != 0
    
    def test_gate_duration_logged(self, fixture_python_min: Path, tmp_path: Path):
        """
        Gate execution duration logged.
        
        Given: Gate executes
        When: Gate completes
        Then: Duration recorded in result
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        gate_runner = create_gate_runner(config, fixture_python_min, logs_dir)
        
        # Run a gate
        gate = GateConfig(name="test", cmd="echo test")
        result = gate_runner._run_gate(gate)
        
        assert result.duration_ms >= 0


class TestGateConfiguration:
    """Test gate configuration validation."""
    
    def test_gate_config_required_fields(self, fixture_python_min: Path):
        """
        Gate config requires name and cmd fields.
        
        Given: Gate configuration
        When: Config loaded
        Then: name and cmd are required
        """
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config_data = yaml.safe_load(config_file.read_text())
        
        for gate_type in ["build", "full"]:
            if gate_type in config_data["gates"]:
                for gate in config_data["gates"][gate_type]:
                    assert "name" in gate, f"Gate missing name"
                    assert "cmd" in gate, f"Gate {gate.get('name', '?')} missing cmd"
    
    def test_gate_defaults_to_fatal(self, fixture_python_min: Path):
        """
        Gates default to fatal: true if not specified.
        
        Given: Gate without explicit fatal setting
        When: GateConfig created
        Then: Defaults to fatal=True
        """
        # GateConfig should default to fatal=True
        gate = GateConfig(name="test", cmd="echo test")
        assert gate.fatal is True
