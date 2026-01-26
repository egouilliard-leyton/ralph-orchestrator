"""Unit tests for signal parsing and validation."""

import pytest

from ralph_orchestrator.signals import (
    SignalType,
    Signal,
    parse_signals,
    find_signal,
    validate_signal,
    validate_implementation_signal,
    validate_test_writing_signal,
    validate_review_signal,
    get_feedback_for_missing_signal,
    get_feedback_for_invalid_token,
    IMPLEMENTATION_SIGNALS,
    TEST_WRITING_SIGNALS,
    REVIEW_APPROVAL_SIGNALS,
    REVIEW_REJECTION_SIGNALS,
)


class TestSignalParsing:
    """Tests for signal parsing."""
    
    def test_parse_task_done_signal(self):
        """Parse task-done signal with session token."""
        response = '''I've completed the implementation.
        
<task-done session="ralph-20260125-143052-a1b2c3d4e5f60a1b">
Implementation complete. Changes:
- Added new function
</task-done>'''
        
        signals = parse_signals(response)
        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.TASK_DONE
        assert signals[0].session_token == "ralph-20260125-143052-a1b2c3d4e5f60a1b"
        assert "Implementation complete" in signals[0].content
    
    def test_parse_tests_done_signal(self):
        """Parse tests-done signal."""
        response = '''<tests-done session="ralph-test-token">
Tests written for the feature.
</tests-done>'''
        
        signals = parse_signals(response)
        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.TESTS_DONE
        assert signals[0].session_token == "ralph-test-token"
    
    def test_parse_review_approved_signal(self):
        """Parse review-approved signal."""
        response = '''<review-approved session="ralph-session-123">
All criteria verified.
</review-approved>'''
        
        signals = parse_signals(response)
        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.REVIEW_APPROVED
    
    def test_parse_review_rejected_signal(self):
        """Parse review-rejected signal."""
        response = '''<review-rejected session="ralph-session-123">
Issues found:
- Missing test coverage
</review-rejected>'''
        
        signals = parse_signals(response)
        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.REVIEW_REJECTED
        assert "Missing test coverage" in signals[0].content
    
    def test_parse_multiple_signals(self):
        """Parse response with multiple signals."""
        response = '''First signal:
<task-done session="token1">Done</task-done>
Second signal:
<tests-done session="token2">Tests done</tests-done>'''
        
        signals = parse_signals(response)
        assert len(signals) == 2
        assert signals[0].signal_type == SignalType.TASK_DONE
        assert signals[1].signal_type == SignalType.TESTS_DONE
    
    def test_parse_no_signals(self):
        """Handle response with no signals."""
        response = "Just a regular response with no signals."
        signals = parse_signals(response)
        assert len(signals) == 0
    
    def test_parse_malformed_signal_ignored(self):
        """Malformed signals are ignored."""
        response = '''<task-done session="token">Content'''  # Missing closing tag
        signals = parse_signals(response)
        assert len(signals) == 0


class TestSignalFinding:
    """Tests for finding specific signals."""
    
    def test_find_implementation_signal(self):
        """Find task-done signal in response."""
        response = '''<task-done session="token">Done</task-done>'''
        signal = find_signal(response, IMPLEMENTATION_SIGNALS)
        assert signal is not None
        assert signal.signal_type == SignalType.TASK_DONE
    
    def test_find_first_matching_signal(self):
        """Returns first matching signal when multiple present."""
        response = '''<tests-done session="t1">First</tests-done>
<tests-done session="t2">Second</tests-done>'''
        signal = find_signal(response, TEST_WRITING_SIGNALS)
        assert signal is not None
        assert signal.session_token == "t1"
    
    def test_find_returns_none_when_not_found(self):
        """Returns None when no matching signal found."""
        response = '''<review-approved session="token">Approved</review-approved>'''
        signal = find_signal(response, IMPLEMENTATION_SIGNALS)
        assert signal is None


class TestSignalValidation:
    """Tests for signal validation."""
    
    def test_validate_correct_signal_and_token(self):
        """Validation passes with correct signal type and token."""
        response = '''<task-done session="ralph-correct-token">Done</task-done>'''
        result = validate_signal(response, "ralph-correct-token", IMPLEMENTATION_SIGNALS)
        
        assert result.valid is True
        assert result.signal is not None
        assert result.error is None
    
    def test_validate_wrong_token(self):
        """Validation fails with wrong token."""
        response = '''<task-done session="wrong-token">Done</task-done>'''
        result = validate_signal(response, "expected-token", IMPLEMENTATION_SIGNALS)
        
        assert result.valid is False
        assert "mismatch" in result.error.lower()
        assert result.expected_token == "expected-token"
        assert result.received_token == "wrong-token"
    
    def test_validate_missing_signal(self):
        """Validation fails when signal is missing."""
        response = "No signal here."
        result = validate_signal(response, "token", IMPLEMENTATION_SIGNALS)
        
        assert result.valid is False
        assert "No completion signal" in result.error
    
    def test_validate_wrong_signal_type(self):
        """Validation fails with wrong signal type."""
        response = '''<tests-done session="token">Tests</tests-done>'''
        result = validate_signal(response, "token", IMPLEMENTATION_SIGNALS)
        
        assert result.valid is False
        assert "Wrong signal type" in result.error


class TestImplementationSignalValidation:
    """Tests for implementation signal validation."""
    
    def test_valid_implementation_signal(self):
        """Valid task-done signal passes."""
        response = '''<task-done session="ralph-session">Done</task-done>'''
        result = validate_implementation_signal(response, "ralph-session")
        assert result.valid is True
    
    def test_invalid_token_fails(self):
        """Wrong token fails validation."""
        response = '''<task-done session="wrong">Done</task-done>'''
        result = validate_implementation_signal(response, "correct")
        assert result.valid is False


class TestTestWritingSignalValidation:
    """Tests for test-writing signal validation."""
    
    def test_valid_tests_done_signal(self):
        """Valid tests-done signal passes."""
        response = '''<tests-done session="ralph-session">Tests written</tests-done>'''
        result = validate_test_writing_signal(response, "ralph-session")
        assert result.valid is True


class TestReviewSignalValidation:
    """Tests for review signal validation."""
    
    def test_review_approval_returns_true(self):
        """Review approval returns is_approved=True."""
        response = '''<review-approved session="token">Approved</review-approved>'''
        result, is_approved = validate_review_signal(response, "token")
        
        assert result.valid is True
        assert is_approved is True
    
    def test_review_rejection_returns_false(self):
        """Review rejection returns is_approved=False."""
        response = '''<review-rejected session="token">Issues found</review-rejected>'''
        result, is_approved = validate_review_signal(response, "token")
        
        assert result.valid is True
        assert is_approved is False
    
    def test_missing_review_signal(self):
        """Missing review signal fails validation."""
        response = "No review signal."
        result, is_approved = validate_review_signal(response, "token")
        
        assert result.valid is False
        assert is_approved is False


class TestFeedbackGeneration:
    """Tests for feedback message generation."""
    
    def test_missing_signal_feedback_includes_example(self):
        """Missing signal feedback includes format example."""
        feedback = get_feedback_for_missing_signal("implementation", "ralph-token-123")
        
        assert "task-done" in feedback
        assert "ralph-token-123" in feedback
        assert "session" in feedback
    
    def test_invalid_token_feedback_shows_both_tokens(self):
        """Invalid token feedback shows expected and received."""
        feedback = get_feedback_for_invalid_token("implementation", "expected-token", "received-token")
        
        assert "expected-token" in feedback
        assert "received-token" in feedback
        assert "mismatch" in feedback.lower()
    
    def test_feedback_for_test_writing_role(self):
        """Feedback for test-writing role uses tests-done signal."""
        feedback = get_feedback_for_missing_signal("test_writing", "token")
        assert "tests-done" in feedback
    
    def test_feedback_for_review_role(self):
        """Feedback for review role uses review-approved signal."""
        feedback = get_feedback_for_missing_signal("review", "token")
        assert "review-approved" in feedback
