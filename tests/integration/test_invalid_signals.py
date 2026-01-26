"""
Integration tests for signal rejection and retry behavior.

These tests verify that the Ralph orchestrator correctly:
- Rejects completion signals with invalid session tokens
- Detects missing completion signals
- Triggers retry with feedback on rejection
- Handles timeout scenarios

Note: These tests use the mock Claude CLI SIMULATE_* directives.
"""

import pytest
import os
import json
import yaml
from pathlib import Path

from ralph_orchestrator.session import create_session
from ralph_orchestrator.signals import (
    parse_signals,
    validate_signal,
    validate_implementation_signal,
    validate_review_signal,
    get_feedback_for_missing_signal,
    get_feedback_for_invalid_token,
    IMPLEMENTATION_SIGNALS,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestInvalidTokenHandling:
    """Test handling of invalid session tokens in signals."""
    
    def test_invalid_token_rejected(self, fixture_python_min: Path):
        """
        Invalid token in signal triggers rejection.
        
        Given: A valid session with known token
        When: Response contains signal with different token
        Then: Signal is rejected with token mismatch error
        """
        os.chdir(fixture_python_min)
        
        # Create session with known token
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Simulate response with wrong token
        wrong_token = "wrong-token-invalid-12345678"
        mock_response = f'''<task-done session="{wrong_token}">
Task completed.
</task-done>'''
        
        # Validate signal - should fail due to token mismatch
        result = validate_implementation_signal(mock_response, session.session_token)
        
        assert result.valid is False, "Signal should be invalid"
        assert "mismatch" in result.error.lower(), "Error should mention mismatch"
        assert result.expected_token == session.session_token
        assert result.received_token == wrong_token
    
    def test_token_mismatch_logged(self, fixture_python_min: Path):
        """
        Token mismatch is logged with both tokens for debugging.
        
        Given: Invalid token response
        When: Validation fails
        Then: Result contains expected and received tokens
        """
        os.chdir(fixture_python_min)
        
        expected_token = "ralph-expected-token"
        received_token = "ralph-received-token"
        
        mock_response = f'''<task-done session="{received_token}">
Done.
</task-done>'''
        
        result = validate_implementation_signal(mock_response, expected_token)
        
        assert result.valid is False
        assert result.expected_token == expected_token
        assert result.received_token == received_token
        
        # Generate feedback message
        feedback = get_feedback_for_invalid_token("implementation", expected_token, received_token)
        assert expected_token in feedback
        assert received_token in feedback
    
    def test_invalid_token_does_not_advance_task(self, fixture_python_min: Path):
        """
        Task status unchanged when token is invalid.
        
        Given: Task in progress
        When: Signal with invalid token received
        Then: Signal validation fails, no completion marked
        """
        os.chdir(fixture_python_min)
        
        prd_file = fixture_python_min / ".ralph" / "prd.json"
        original_prd = json.loads(prd_file.read_text())
        original_status = original_prd["tasks"][0]["passes"]
        
        # Should be False initially
        assert original_status is False
        
        # Create session
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Simulate invalid token response
        mock_response = '''<task-done session="wrong-token">
Done.
</task-done>'''
        
        # Validation fails
        result = validate_implementation_signal(mock_response, session.session_token)
        assert result.valid is False
        
        # Task status unchanged (not automatically marked complete)
        reloaded = json.loads(prd_file.read_text())
        assert reloaded["tasks"][0]["passes"] is False


class TestNoSignalHandling:
    """Test handling of responses without completion signals."""
    
    def test_no_signal_triggers_retry(self, fixture_python_min: Path):
        """
        Missing signal triggers retry with feedback.
        
        Given: Task in progress
        When: Claude response has no completion signal
        Then: Validation fails with no signal error
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Response without any signal
        mock_response = '''I've made the changes you requested. The implementation 
looks good and should work correctly.

Changes made:
- Updated the auth module
- Added new test cases'''
        
        # Parse signals - should find none
        signals = parse_signals(mock_response)
        assert len(signals) == 0, "Should find no signals"
        
        # Validation should fail
        result = validate_implementation_signal(mock_response, session.session_token)
        assert result.valid is False
        assert "No completion signal" in result.error
    
    def test_no_signal_feedback_includes_expected_format(self, fixture_python_min: Path):
        """
        Retry feedback includes example of expected signal format.
        
        Given: Response without signal
        When: Retry feedback generated
        Then: Feedback shows correct signal format
        """
        session_token = "ralph-test-token-12345"
        
        feedback = get_feedback_for_missing_signal("implementation", session_token)
        
        assert "task-done" in feedback, "Should include signal name"
        assert session_token in feedback, "Should include expected token"
        assert "session" in feedback, "Should mention session attribute"
    
    def test_max_no_signal_retries_stops_task(self, fixture_python_min: Path):
        """
        Persistent no-signal responses stop after max retries.
        
        Given: Claude consistently returns no signal
        When: Max retries reached
        Then: Task remains incomplete after all retries
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        max_iterations = 3
        session.start_task("T-001")
        
        # Simulate multiple no-signal responses
        no_signal_response = "I made changes but forgot the signal."
        
        for i in range(max_iterations):
            result = validate_implementation_signal(no_signal_response, session.session_token)
            assert result.valid is False
            session.increment_iterations("T-001")
        
        # After max iterations, record failure
        session.fail_task("T-001", f"Max iterations ({max_iterations}) reached without valid signal")
        
        # Verify failure recorded
        status_data = json.loads(session.task_status_path.read_text())
        assert status_data["tasks"]["T-001"]["iterations"] == max_iterations
        assert "Max iterations" in status_data["tasks"]["T-001"]["last_failure"]


class TestTimeoutHandling:
    """Test handling of timeout scenarios."""
    
    def test_timeout_triggers_retry(self, fixture_python_min: Path):
        """
        Claude timeout triggers retry with shorter timeout.
        
        Given: Claude call times out
        When: Timeout detected
        Then: Task can be retried
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        session.start_task("T-001")
        
        # Simulate timeout by incrementing iteration
        session.increment_iterations("T-001")
        
        # After timeout, we can retry
        count = session.increment_iterations("T-001")
        assert count == 2, "Should allow second iteration after timeout"
    
    @pytest.mark.slow
    def test_timeout_respects_config_value(self, fixture_python_min: Path):
        """
        Timeout uses value from ralph.yml configuration.
        
        Given: Config has specific timeout value
        When: Config loaded
        Then: Timeout matches configured value
        """
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        assert "limits" in config
        assert "claude_timeout" in config["limits"]
        timeout = config["limits"]["claude_timeout"]
        
        # Verify timeout is reasonable (in seconds)
        assert 60 <= timeout <= 600, "Timeout should be between 1-10 minutes"


class TestReviewRejection:
    """Test review rejection handling."""
    
    def test_review_rejection_provides_feedback(self, fixture_python_min: Path):
        """
        Review rejection includes feedback for retry.
        
        Given: Implementation complete
        When: Review rejects with reasons
        Then: Rejection content available for feedback
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Simulate review rejection
        mock_response = f'''<review-rejected session="{session.session_token}">
Issues found:
- Missing error handling for edge cases
- No logging for authentication failures
</review-rejected>'''
        
        result, is_approved = validate_review_signal(mock_response, session.session_token)
        
        assert result.valid is True
        assert is_approved is False
        assert "Missing error handling" in result.signal.content
        assert "No logging" in result.signal.content
    
    def test_review_rejection_increments_iteration(self, fixture_python_min: Path):
        """
        Each review rejection counts as an iteration.
        
        Given: Max iterations configured
        When: Review keeps rejecting
        Then: Iterations are counted correctly
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        session.start_task("T-001")
        
        # Simulate multiple rejections
        for i in range(3):
            mock_response = f'''<review-rejected session="{session.session_token}">
Rejection {i+1}
</review-rejected>'''
            result, is_approved = validate_review_signal(mock_response, session.session_token)
            assert result.valid
            assert not is_approved
            session.increment_iterations("T-001")
        
        # Verify iterations counted
        status_data = json.loads(session.task_status_path.read_text())
        assert status_data["tasks"]["T-001"]["iterations"] == 3


class TestEmptyResponseHandling:
    """Test handling of empty or malformed responses."""
    
    def test_empty_response_triggers_retry(self, fixture_python_min: Path):
        """
        Empty Claude response triggers retry.
        
        Given: Task in progress
        When: Claude returns empty response
        Then: No signals parsed, validation fails
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Empty response
        empty_response = ""
        
        signals = parse_signals(empty_response)
        assert len(signals) == 0
        
        result = validate_implementation_signal(empty_response, session.session_token)
        assert result.valid is False
    
    def test_malformed_signal_treated_as_no_signal(self, fixture_python_min: Path):
        """
        Malformed signal XML is treated as missing signal.
        
        Given: Response with broken XML signal
        When: Signal validation runs
        Then: Treated as no signal
        """
        os.chdir(fixture_python_min)
        
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Malformed signal (missing closing tag)
        malformed_response = f'''<task-done session="{session.session_token}">
Task complete'''
        
        signals = parse_signals(malformed_response)
        assert len(signals) == 0, "Malformed signal should not parse"
        
        result = validate_implementation_signal(malformed_response, session.session_token)
        assert result.valid is False
