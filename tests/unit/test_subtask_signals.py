"""Unit tests for subtask signal parsing and validation."""

import pytest

from ralph_orchestrator.signals import (
    SignalType,
    Signal,
    parse_subtask_signals,
    validate_subtask_signal,
    find_subtask_completion_signals,
    find_subtask_promotion_signals,
    get_subtask_signal_format_example,
    get_subtask_promotion_format_example,
)


class TestParseSubtaskSignals:
    """Tests for parse_subtask_signals function."""

    def test_parse_subtask_complete(self):
        response = '''
        Making changes to the file...

        <subtask-complete id="T-001.1" session="ralph-test-token">
        Implemented the helper function for data validation.
        </subtask-complete>

        Moving on to the next subtask.
        '''

        signals = parse_subtask_signals(response)

        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.SUBTASK_COMPLETE
        assert signals[0].subtask_id == "T-001.1"
        assert signals[0].session_token == "ralph-test-token"
        assert "helper function" in signals[0].content

    def test_parse_promote_subtask(self):
        response = '''
        This subtask is more complex than expected.

        <promote-subtask id="T-001.3" session="ralph-test-token">
        This subtask needs its own test suite and should be handled separately.
        </promote-subtask>
        '''

        signals = parse_subtask_signals(response)

        assert len(signals) == 1
        assert signals[0].signal_type == SignalType.PROMOTE_SUBTASK
        assert signals[0].subtask_id == "T-001.3"
        assert signals[0].session_token == "ralph-test-token"
        assert "test suite" in signals[0].content

    def test_parse_multiple_signals(self):
        response = '''
        Working through subtasks...

        <subtask-complete id="T-001.1" session="token123">Done with first</subtask-complete>
        <subtask-complete id="T-001.2" session="token123">Done with second</subtask-complete>
        <promote-subtask id="T-001.3" session="token123">Too complex</promote-subtask>
        '''

        signals = parse_subtask_signals(response)

        assert len(signals) == 3
        complete_signals = [s for s in signals if s.is_subtask_complete]
        promotion_signals = [s for s in signals if s.is_subtask_promotion]

        assert len(complete_signals) == 2
        assert len(promotion_signals) == 1

    def test_parse_no_signals(self):
        response = "Just some regular text without any signals."

        signals = parse_subtask_signals(response)

        assert signals == []

    def test_parse_preserves_multiline_content(self):
        response = '''
        <subtask-complete id="T-001.1" session="token">
        This is line 1.
        This is line 2.
        This is line 3.
        </subtask-complete>
        '''

        signals = parse_subtask_signals(response)

        assert len(signals) == 1
        assert "line 1" in signals[0].content
        assert "line 3" in signals[0].content


class TestValidateSubtaskSignal:
    """Tests for validate_subtask_signal function."""

    def test_valid_signal(self):
        response = '''
        <subtask-complete id="T-001.2" session="correct-token">
        Completed the work.
        </subtask-complete>
        '''

        result = validate_subtask_signal(response, "T-001.2", "correct-token")

        assert result.valid is True
        assert result.signal is not None
        assert result.signal.subtask_id == "T-001.2"

    def test_invalid_token(self):
        response = '''
        <subtask-complete id="T-001.2" session="wrong-token">
        Completed the work.
        </subtask-complete>
        '''

        result = validate_subtask_signal(response, "T-001.2", "correct-token")

        assert result.valid is False
        assert "mismatch" in result.error.lower()

    def test_missing_signal(self):
        response = "No signals here"

        result = validate_subtask_signal(response, "T-001.2", "token")

        assert result.valid is False
        assert "no subtask-complete signal found" in result.error.lower()

    def test_wrong_subtask_id(self):
        response = '''
        <subtask-complete id="T-001.3" session="token">
        Completed different subtask.
        </subtask-complete>
        '''

        result = validate_subtask_signal(response, "T-001.2", "token")

        assert result.valid is False


class TestFindSubtaskSignals:
    """Tests for find_subtask_completion_signals and find_subtask_promotion_signals."""

    def test_find_completion_signals(self):
        response = '''
        <subtask-complete id="T-001.1" session="token">Done 1</subtask-complete>
        <subtask-complete id="T-001.2" session="token">Done 2</subtask-complete>
        <promote-subtask id="T-001.3" session="token">Promote this</promote-subtask>
        '''

        signals = find_subtask_completion_signals(response)

        assert len(signals) == 2
        subtask_ids = {s.subtask_id for s in signals}
        assert subtask_ids == {"T-001.1", "T-001.2"}

    def test_find_promotion_signals(self):
        response = '''
        <subtask-complete id="T-001.1" session="token">Done 1</subtask-complete>
        <promote-subtask id="T-001.2" session="token">Too complex</promote-subtask>
        <promote-subtask id="T-001.3" session="token">Also complex</promote-subtask>
        '''

        signals = find_subtask_promotion_signals(response)

        assert len(signals) == 2
        subtask_ids = {s.subtask_id for s in signals}
        assert subtask_ids == {"T-001.2", "T-001.3"}


class TestSignalProperties:
    """Tests for Signal class subtask-related properties."""

    def test_is_subtask_complete(self):
        signal = Signal(
            signal_type=SignalType.SUBTASK_COMPLETE,
            session_token="token",
            content="done",
            raw_match="<subtask-complete>done</subtask-complete>",
            subtask_id="T-001.1",
        )

        assert signal.is_subtask_complete is True
        assert signal.is_subtask_promotion is False

    def test_is_subtask_promotion(self):
        signal = Signal(
            signal_type=SignalType.PROMOTE_SUBTASK,
            session_token="token",
            content="reason",
            raw_match="<promote-subtask>reason</promote-subtask>",
            subtask_id="T-001.2",
        )

        assert signal.is_subtask_promotion is True
        assert signal.is_subtask_complete is False


class TestFormatExamples:
    """Tests for signal format example helpers."""

    def test_subtask_signal_format_example(self):
        example = get_subtask_signal_format_example("T-001.2", "my-token")

        assert "T-001.2" in example
        assert "my-token" in example
        assert "subtask-complete" in example

    def test_subtask_promotion_format_example(self):
        example = get_subtask_promotion_format_example("T-001.3", "my-token")

        assert "T-001.3" in example
        assert "my-token" in example
        assert "promote-subtask" in example
