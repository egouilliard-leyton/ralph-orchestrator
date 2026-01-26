"""
Integration tests for runtime fix iteration behavior.

These tests verify that the Ralph orchestrator correctly:
- Triggers fix agent when gates fail
- Provides failure context to fix agent
- Iterates until fix succeeds or max attempts reached
- Handles different types of failures (build, test, runtime)
- Logs fix attempts and outcomes

Fix loops ensure that gate failures are automatically addressed
before task completion is finalized.
"""

import pytest
import os
import json
import yaml
from pathlib import Path

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestBuildFixLoop:
    """Test fix loop for build failures."""
    
    def test_fix_agent_called_on_build_failure(self, fixture_python_min: Path):
        """
        Fix agent called when build gate fails.
        
        Given: Build gate configured
        When: Build fails after implementation
        Then: Fix agent called with failure context
        """
        os.chdir(fixture_python_min)
        
        # Modify config to have failing build gate
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Original command should exist
        assert "build" in config["gates"]
        
        # TODO: When ralph CLI is implemented:
        # Configure build to fail
        # config["gates"]["build"][0]["cmd"] = "python -c \"import sys; sys.exit(1)\""
        # config_file.write_text(yaml.dump(config))
        # 
        # run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "3"])
        # 
        # # Check timeline for fix agent call
        # timeline_file = fixture_python_min / ".ralph-session/logs/timeline.jsonl"
        # timeline = timeline_file.read_text()
        # assert "fix" in timeline.lower()
    
    def test_build_failure_context_includes_output(self, fixture_python_min: Path):
        """
        Fix agent receives build failure output.
        
        Given: Build fails with error output
        When: Fix agent called
        Then: Prompt includes stderr/stdout from failure
        """
        # TODO: When ralph CLI is implemented:
        # Verify fix prompt includes build output
        pass
    
    def test_build_fix_retries_build(self, fixture_python_min: Path):
        """
        After fix attempt, build gate is re-run.
        
        Given: Fix agent makes changes
        When: Fix iteration completes
        Then: Build gate runs again
        """
        # TODO: When ralph CLI is implemented:
        # Verify build re-runs after fix
        pass


class TestTestFixLoop:
    """Test fix loop for test failures."""
    
    def test_fix_agent_called_on_test_failure(self, fixture_python_min: Path):
        """
        Fix agent called when test gate fails.
        
        Given: Test gate configured
        When: Tests fail after implementation
        Then: Fix agent called with test failure context
        """
        os.chdir(fixture_python_min)
        
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Verify test gate exists
        assert "full" in config["gates"]
        test_gates = [g for g in config["gates"]["full"] if "pytest" in g.get("cmd", "")]
        assert len(test_gates) >= 1 or any("test" in g.get("name", "") for g in config["gates"]["full"])
        
        # TODO: When ralph CLI is implemented:
        # Configure test to fail, verify fix agent called
    
    def test_test_failure_shows_failing_tests(self, fixture_python_min: Path):
        """
        Fix agent sees which tests failed.
        
        Given: Specific tests failing
        When: Fix agent called
        Then: Prompt includes test names and errors
        """
        # TODO: When ralph CLI is implemented:
        # Verify fix prompt includes test failure details
        pass


class TestRuntimeFixLoop:
    """Test fix loop for runtime failures."""
    
    def test_fix_agent_called_on_runtime_error(self, fixture_fullstack_min: Path):
        """
        Fix agent called when runtime health check fails.
        
        Given: Services started
        When: Health check fails
        Then: Fix agent called with runtime context
        """
        os.chdir(fixture_fullstack_min)
        
        # TODO: When ralph CLI is implemented:
        # Configure unhealthy endpoint, verify fix agent called
        pass
    
    def test_runtime_fix_includes_service_logs(self, fixture_fullstack_min: Path):
        """
        Fix agent sees service logs for runtime errors.
        
        Given: Service crashes or returns error
        When: Fix agent called
        Then: Prompt includes recent service logs
        """
        # TODO: When ralph CLI is implemented:
        # Verify fix prompt includes service logs
        pass


class TestUIFixLoop:
    """Test fix loop for UI test failures."""
    
    def test_ui_fix_includes_screenshot(self, fixture_fullstack_min: Path):
        """
        UI fix agent receives failure screenshot.
        
        Given: UI test fails
        When: Fix agent called
        Then: Screenshot of failure state available
        """
        # TODO: When ralph CLI is implemented with UI support:
        # Verify screenshot captured and referenced
        pass
    
    def test_ui_fix_has_planning_phase(self, fixture_fullstack_min: Path):
        """
        UI failures go through planning before implementation.
        
        Given: UI test fails
        When: Fix process starts
        Then: Planning agent runs first (read-only)
        """
        # TODO: When ralph CLI is implemented:
        # Verify planning phase for UI fixes
        pass


class TestFixLoopIteration:
    """Test fix loop iteration behavior."""
    
    def test_max_fix_iterations_respected(self, fixture_python_min: Path):
        """
        Fix loop stops after max iterations.
        
        Given: Max iterations configured
        When: Fix keeps failing
        Then: Stops at max and reports failure
        """
        os.chdir(fixture_python_min)
        
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Verify max iterations configured
        assert "limits" in config
        assert "post_verify_iterations" in config["limits"] or "max_iterations" in config["limits"]
        
        # TODO: When ralph CLI is implemented:
        # Configure persistent failure, verify stops at max
    
    def test_fix_iteration_count_logged(self, fixture_python_min: Path):
        """
        Each fix iteration is logged.
        
        Given: Fix loop running
        When: Multiple iterations occur
        Then: Each iteration logged with number
        """
        # TODO: When ralph CLI is implemented:
        # Verify iteration logging
        pass
    
    def test_successful_fix_exits_loop(self, fixture_python_min: Path):
        """
        Fix loop exits on successful fix.
        
        Given: Fix agent fixes the issue
        When: Gates pass
        Then: Loop exits and task proceeds
        """
        # TODO: When ralph CLI is implemented:
        # Verify early exit on success
        pass


class TestFixLoopFeedback:
    """Test feedback accumulation in fix loop."""
    
    def test_previous_attempts_in_feedback(self, fixture_python_min: Path):
        """
        Previous fix attempts included in prompt.
        
        Given: Multiple fix iterations
        When: Next iteration starts
        Then: Previous attempts summarized in prompt
        """
        # TODO: When ralph CLI is implemented:
        # Verify feedback accumulation
        pass
    
    def test_feedback_prevents_same_fix(self, fixture_python_min: Path):
        """
        Feedback helps avoid repeating failed fixes.
        
        Given: Previous fix attempt failed
        When: Next iteration
        Then: Prompt indicates what was tried
        """
        # TODO: When ralph CLI is implemented:
        # Verify feedback includes previous attempts
        pass


class TestFixLoopSignals:
    """Test fix agent completion signals."""
    
    def test_fix_done_signal_recognized(self, fixture_python_min: Path, mock_claude_path: Path):
        """
        Fix-done signal recognized and validated.
        
        Given: Fix agent returns fix-done signal
        When: Signal validated
        Then: Session token verified
        """
        import subprocess
        import sys
        
        prompt = '''SESSION_TOKEN: "ralph-test-token"
        
Fix the following error:
Build failed with syntax error in main.py
'''
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "<fix-done" in result.stdout
        assert "ralph-test-token" in result.stdout
    
    def test_fix_signal_invalid_token_rejected(self, fixture_python_min: Path):
        """
        Fix signal with invalid token is rejected.
        
        Given: Fix agent returns signal with wrong token
        When: Signal validated
        Then: Fix not accepted, retry triggered
        """
        # TODO: When ralph CLI is implemented:
        # Verify invalid token handling in fix loop
        pass


class TestFixLoopGateIntegration:
    """Test fix loop integration with gates."""
    
    def test_only_failed_gates_re_run(self, fixture_python_min: Path):
        """
        Only failed gates re-run after fix, not all gates.
        
        Given: Multiple gates, one fails
        When: Fix succeeds
        Then: Only failed gate re-runs (optimization)
        """
        # This is an optimization - may not be implemented in v1
        # TODO: Document expected behavior
        pass
    
    def test_all_gates_pass_before_task_complete(self, fixture_python_min: Path):
        """
        All gates must pass for task to complete.
        
        Given: Build gate fixed
        When: Test gate still fails
        Then: Task not marked complete
        """
        # TODO: When ralph CLI is implemented:
        # Verify all gates must pass
        pass


class TestFixLoopTimeouts:
    """Test fix loop timeout behavior."""
    
    def test_fix_agent_has_timeout(self, fixture_python_min: Path):
        """
        Fix agent call has timeout.
        
        Given: Fix loop running
        When: Fix agent takes too long
        Then: Timeout triggered, iteration fails
        """
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Verify timeout configured
        assert "limits" in config
        assert "claude_timeout" in config["limits"]
        
        timeout = config["limits"]["claude_timeout"]
        assert timeout > 0
    
    def test_total_fix_time_limited(self, fixture_python_min: Path):
        """
        Total time for all fix iterations is limited.
        
        Given: Multiple fix iterations
        When: Total time exceeds limit
        Then: Fix loop aborted
        """
        # TODO: When ralph CLI is implemented:
        # Verify total time limit
        pass


class TestFixLoopLogging:
    """Test fix loop logging and artifacts."""
    
    def test_fix_attempts_logged_to_timeline(self, fixture_python_min: Path):
        """
        Fix attempts logged to timeline.
        
        Given: Fix loop running
        When: Iterations occur
        Then: Each logged with timestamp and outcome
        """
        # TODO: When ralph CLI is implemented:
        # Verify timeline logging
        pass
    
    def test_fix_agent_output_saved(self, fixture_python_min: Path):
        """
        Fix agent output saved for debugging.
        
        Given: Fix agent runs
        When: Output generated
        Then: Output saved to session logs
        """
        # TODO: When ralph CLI is implemented:
        # Verify output artifacts
        pass
    
    def test_file_changes_tracked_per_fix(self, fixture_python_min: Path):
        """
        File changes tracked for each fix iteration.
        
        Given: Fix agent modifies files
        When: Iteration completes
        Then: Changes recorded for potential rollback
        """
        # TODO: When ralph CLI is implemented:
        # Verify change tracking
        pass
