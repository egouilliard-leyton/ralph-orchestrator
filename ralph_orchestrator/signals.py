"""Signal parsing and validation for Ralph orchestrator.

Parses and validates completion signals from Claude CLI responses:
- <task-done session="TOKEN">...</task-done>
- <tests-done session="TOKEN">...</tests-done>
- <review-approved session="TOKEN">...</review-approved>
- <review-rejected session="TOKEN">...</review-rejected>
- <fix-done session="TOKEN">...</fix-done>
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class SignalType(str, Enum):
    """Types of completion signals."""
    TASK_DONE = "task-done"
    TESTS_DONE = "tests-done"
    REVIEW_APPROVED = "review-approved"
    REVIEW_REJECTED = "review-rejected"
    FIX_DONE = "fix-done"
    UI_PLAN = "ui-plan"
    UI_FIX_DONE = "ui-fix-done"
    UI_TESTS_DONE = "ui-tests-done"
    ROBOT_PLAN = "robot-plan"
    ROBOT_FIX_DONE = "robot-fix-done"
    # Subtask signals for checkpoint and escalation
    SUBTASK_COMPLETE = "subtask-complete"
    PROMOTE_SUBTASK = "promote-subtask"


# Signals that indicate completion for different roles
IMPLEMENTATION_SIGNALS = {SignalType.TASK_DONE}
TEST_WRITING_SIGNALS = {SignalType.TESTS_DONE}
REVIEW_APPROVAL_SIGNALS = {SignalType.REVIEW_APPROVED}
REVIEW_REJECTION_SIGNALS = {SignalType.REVIEW_REJECTED}
FIX_SIGNALS = {SignalType.FIX_DONE}
PLANNING_SIGNALS = {SignalType.UI_PLAN, SignalType.ROBOT_PLAN}
UI_FIX_SIGNALS = {SignalType.UI_FIX_DONE}
UI_TESTING_SIGNALS = {SignalType.UI_TESTS_DONE}
ROBOT_FIX_SIGNALS = {SignalType.ROBOT_FIX_DONE}
# Subtask signals
SUBTASK_COMPLETE_SIGNALS = {SignalType.SUBTASK_COMPLETE}
SUBTASK_PROMOTION_SIGNALS = {SignalType.PROMOTE_SUBTASK}


@dataclass
class Signal:
    """Parsed signal from Claude response."""
    signal_type: SignalType
    session_token: str
    content: str
    raw_match: str
    subtask_id: Optional[str] = None  # For subtask-complete and promote-subtask signals

    @property
    def is_approval(self) -> bool:
        """Check if signal indicates approval."""
        return self.signal_type in REVIEW_APPROVAL_SIGNALS

    @property
    def is_rejection(self) -> bool:
        """Check if signal indicates rejection."""
        return self.signal_type in REVIEW_REJECTION_SIGNALS

    @property
    def is_subtask_complete(self) -> bool:
        """Check if signal indicates subtask completion."""
        return self.signal_type in SUBTASK_COMPLETE_SIGNALS

    @property
    def is_subtask_promotion(self) -> bool:
        """Check if signal indicates subtask promotion request."""
        return self.signal_type in SUBTASK_PROMOTION_SIGNALS


@dataclass
class SignalValidationResult:
    """Result of signal validation."""
    valid: bool
    signal: Optional[Signal] = None
    error: Optional[str] = None
    expected_token: Optional[str] = None
    received_token: Optional[str] = None


def parse_signals(response: str) -> List[Signal]:
    """Parse all signals from a Claude response.
    
    Args:
        response: Full text response from Claude CLI.
        
    Returns:
        List of parsed Signal objects.
    """
    signals = []
    
    # Pattern to match any signal tag with session attribute
    # Matches: <signal-type session="token">content</signal-type>
    signal_pattern = re.compile(
        r'<(' + '|'.join(st.value for st in SignalType) + r')\s+session="([^"]+)"[^>]*>'
        r'(.*?)'
        r'</\1>',
        re.DOTALL | re.IGNORECASE
    )
    
    for match in signal_pattern.finditer(response):
        signal_type_str = match.group(1).lower()
        session_token = match.group(2)
        content = match.group(3).strip()
        
        try:
            signal_type = SignalType(signal_type_str)
            signals.append(Signal(
                signal_type=signal_type,
                session_token=session_token,
                content=content,
                raw_match=match.group(0),
            ))
        except ValueError:
            # Unknown signal type, skip
            pass
    
    return signals


def find_signal(
    response: str,
    expected_types: set[SignalType],
) -> Optional[Signal]:
    """Find first signal of expected types in response.
    
    Args:
        response: Full text response from Claude CLI.
        expected_types: Set of signal types to look for.
        
    Returns:
        First matching Signal or None.
    """
    signals = parse_signals(response)
    for signal in signals:
        if signal.signal_type in expected_types:
            return signal
    return None


def validate_signal(
    response: str,
    expected_token: str,
    expected_types: set[SignalType],
) -> SignalValidationResult:
    """Validate that response contains expected signal with correct token.
    
    Args:
        response: Full text response from Claude CLI.
        expected_token: Expected session token (must match exactly).
        expected_types: Set of acceptable signal types.
        
    Returns:
        SignalValidationResult with validation outcome.
    """
    # Find signal of expected type
    signal = find_signal(response, expected_types)
    
    if signal is None:
        # No signal found - check if there's any signal at all
        all_signals = parse_signals(response)
        if all_signals:
            wrong_type = all_signals[0]
            return SignalValidationResult(
                valid=False,
                error=f"Wrong signal type: expected one of {[t.value for t in expected_types]}, "
                      f"got {wrong_type.signal_type.value}",
                expected_token=expected_token,
                received_token=wrong_type.session_token,
            )
        return SignalValidationResult(
            valid=False,
            error="No completion signal found in response",
            expected_token=expected_token,
        )
    
    # Validate session token
    if signal.session_token != expected_token:
        return SignalValidationResult(
            valid=False,
            signal=signal,
            error=f"Session token mismatch: expected {expected_token}, "
                  f"got {signal.session_token}",
            expected_token=expected_token,
            received_token=signal.session_token,
        )
    
    return SignalValidationResult(
        valid=True,
        signal=signal,
        expected_token=expected_token,
        received_token=signal.session_token,
    )


def validate_implementation_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate implementation agent completion signal."""
    return validate_signal(response, expected_token, IMPLEMENTATION_SIGNALS)


def validate_test_writing_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate test-writing agent completion signal."""
    return validate_signal(response, expected_token, TEST_WRITING_SIGNALS)


def validate_review_signal(
    response: str,
    expected_token: str,
) -> Tuple[SignalValidationResult, bool]:
    """Validate review agent signal.
    
    Returns:
        Tuple of (validation_result, is_approved).
        is_approved is True if review-approved, False if review-rejected.
    """
    # Try approval first
    result = validate_signal(response, expected_token, REVIEW_APPROVAL_SIGNALS)
    if result.valid:
        return result, True
    
    # Try rejection
    result = validate_signal(response, expected_token, REVIEW_REJECTION_SIGNALS)
    if result.valid:
        return result, False
    
    # Check for either signal type for better error message
    combined = REVIEW_APPROVAL_SIGNALS | REVIEW_REJECTION_SIGNALS
    return validate_signal(response, expected_token, combined), False


def validate_fix_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate fix agent completion signal."""
    return validate_signal(response, expected_token, FIX_SIGNALS)


def get_signal_format_example(signal_type: SignalType, token: str) -> str:
    """Get example of correct signal format for feedback.
    
    Args:
        signal_type: Type of signal to show example for.
        token: Session token to include in example.
        
    Returns:
        Example signal string.
    """
    examples = {
        SignalType.TASK_DONE: f'''<task-done session="{token}">
Implementation complete. Changes:
- [list of changes made]
</task-done>''',
        
        SignalType.TESTS_DONE: f'''<tests-done session="{token}">
Tests written:
- [list of test files/functions]
</tests-done>''',
        
        SignalType.REVIEW_APPROVED: f'''<review-approved session="{token}">
Code review passed. All acceptance criteria verified.
</review-approved>''',
        
        SignalType.REVIEW_REJECTED: f'''<review-rejected session="{token}">
Issues found:
- [list of issues]
</review-rejected>''',
        
        SignalType.FIX_DONE: f'''<fix-done session="{token}">
Fixed the identified issues.
</fix-done>''',
        
        SignalType.UI_TESTS_DONE: f'''<ui-tests-done session="{token}">
## Verification Results
- [criterion 1]: PASS/FAIL - [observation]

## Tests Generated
- [list of test files]

## Issues Found
- [any issues]
</ui-tests-done>''',
    }
    
    return examples.get(signal_type, f'<{signal_type.value} session="{token}">...</{signal_type.value}>')


def get_feedback_for_missing_signal(
    role: str,
    expected_token: str,
) -> str:
    """Generate feedback message when signal is missing.
    
    Args:
        role: Agent role (implementation, test_writing, review, fix).
        expected_token: Expected session token.
        
    Returns:
        Feedback message with correct signal format.
    """
    role_signals = {
        "implementation": (SignalType.TASK_DONE, "implementation"),
        "test_writing": (SignalType.TESTS_DONE, "test-writing"),
        "review": (SignalType.REVIEW_APPROVED, "review"),
        "fix": (SignalType.FIX_DONE, "fix"),
        "ui_testing": (SignalType.UI_TESTS_DONE, "ui-testing"),
    }
    
    signal_type, role_name = role_signals.get(role, (SignalType.TASK_DONE, role))
    example = get_signal_format_example(signal_type, expected_token)
    
    return f"""Your response must include a completion signal.

Expected signal format for {role_name} role:

{example}

IMPORTANT: The session token must be exactly: {expected_token}

Please complete your work and include the completion signal."""


def get_feedback_for_invalid_token(
    role: str,
    expected_token: str,
    received_token: str,
) -> str:
    """Generate feedback message when token is invalid.
    
    Args:
        role: Agent role.
        expected_token: Expected session token.
        received_token: Token that was received.
        
    Returns:
        Feedback message with correct token.
    """
    return f"""Session token mismatch detected.

Received: {received_token}
Expected: {expected_token}

Please include the correct session token in your completion signal.
The session token MUST be exactly: {expected_token}"""


def validate_ui_plan_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate UI planning agent signal.
    
    Args:
        response: Full text response from Claude CLI.
        expected_token: Expected session token.
        
    Returns:
        SignalValidationResult with validation outcome.
    """
    return validate_signal(response, expected_token, {SignalType.UI_PLAN})


def validate_ui_fix_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate UI fix agent completion signal.
    
    Args:
        response: Full text response from Claude CLI.
        expected_token: Expected session token.
        
    Returns:
        SignalValidationResult with validation outcome.
    """
    return validate_signal(response, expected_token, UI_FIX_SIGNALS)


def validate_robot_plan_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate Robot planning agent signal.
    
    Args:
        response: Full text response from Claude CLI.
        expected_token: Expected session token.
        
    Returns:
        SignalValidationResult with validation outcome.
    """
    return validate_signal(response, expected_token, {SignalType.ROBOT_PLAN})


def validate_robot_fix_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate Robot fix agent completion signal.

    Args:
        response: Full text response from Claude CLI.
        expected_token: Expected session token.

    Returns:
        SignalValidationResult with validation outcome.
    """
    return validate_signal(response, expected_token, ROBOT_FIX_SIGNALS)


def validate_ui_testing_signal(
    response: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate UI testing agent completion signal.

    Args:
        response: Full text response from Claude CLI.
        expected_token: Expected session token.

    Returns:
        SignalValidationResult with validation outcome.
    """
    return validate_signal(response, expected_token, UI_TESTING_SIGNALS)


# =============================================================================
# Convenience Signal Parsing Functions
# =============================================================================

def parse_task_done_signal(response: str) -> Optional[Signal]:
    """Parse task-done signal from response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        Signal object if found, None otherwise.
    """
    return find_signal(response, IMPLEMENTATION_SIGNALS)


def parse_tests_done_signal(response: str) -> Optional[Signal]:
    """Parse tests-done signal from response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        Signal object if found, None otherwise.
    """
    return find_signal(response, TEST_WRITING_SIGNALS)


def parse_review_approved_signal(response: str) -> Optional[Signal]:
    """Parse review-approved signal from response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        Signal object if found, None otherwise.
    """
    return find_signal(response, REVIEW_APPROVAL_SIGNALS)


def parse_review_rejected_signal(response: str) -> Optional[Signal]:
    """Parse review-rejected signal from response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        Signal object if found, None otherwise.
    """
    return find_signal(response, REVIEW_REJECTION_SIGNALS)


def parse_fix_done_signal(response: str) -> Optional[Signal]:
    """Parse fix-done signal from response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        Signal object if found, None otherwise.
    """
    return find_signal(response, FIX_SIGNALS)


# =============================================================================
# Subtask Signal Parsing Functions
# =============================================================================

def parse_subtask_signals(response: str) -> List[Signal]:
    """Parse all subtask-complete and promote-subtask signals from a response.

    Subtask signals have the format:
    - <subtask-complete id="T-001.2" session="TOKEN">content</subtask-complete>
    - <promote-subtask id="T-001.3" session="TOKEN">reason</promote-subtask>

    Args:
        response: Full text response from Claude CLI.

    Returns:
        List of Signal objects with subtask_id populated.
    """
    signals = []

    # Pattern to match subtask signals with id attribute
    # Matches: <signal-type id="T-001.X" session="token">content</signal-type>
    subtask_signal_pattern = re.compile(
        r'<(subtask-complete|promote-subtask)\s+id="([^"]+)"\s+session="([^"]+)"[^>]*>'
        r'(.*?)'
        r'</\1>',
        re.DOTALL | re.IGNORECASE
    )

    for match in subtask_signal_pattern.finditer(response):
        signal_type_str = match.group(1).lower()
        subtask_id = match.group(2)
        session_token = match.group(3)
        content = match.group(4).strip()

        try:
            signal_type = SignalType(signal_type_str)
            signals.append(Signal(
                signal_type=signal_type,
                session_token=session_token,
                content=content,
                raw_match=match.group(0),
                subtask_id=subtask_id,
            ))
        except ValueError:
            # Unknown signal type, skip
            pass

    return signals


def validate_subtask_signal(
    response: str,
    subtask_id: str,
    expected_token: str,
) -> SignalValidationResult:
    """Validate a subtask completion signal for a specific subtask.

    Args:
        response: Full text response from Claude CLI.
        subtask_id: Expected subtask ID (e.g., "T-001.2").
        expected_token: Expected session token.

    Returns:
        SignalValidationResult with validation outcome.
    """
    signals = parse_subtask_signals(response)

    # Find signal for this specific subtask
    for signal in signals:
        if signal.subtask_id == subtask_id and signal.is_subtask_complete:
            if signal.session_token != expected_token:
                return SignalValidationResult(
                    valid=False,
                    signal=signal,
                    error=f"Session token mismatch: expected {expected_token}, "
                          f"got {signal.session_token}",
                    expected_token=expected_token,
                    received_token=signal.session_token,
                )
            return SignalValidationResult(
                valid=True,
                signal=signal,
                expected_token=expected_token,
                received_token=signal.session_token,
            )

    return SignalValidationResult(
        valid=False,
        error=f"No subtask-complete signal found for {subtask_id}",
        expected_token=expected_token,
    )


def find_subtask_completion_signals(response: str) -> List[Signal]:
    """Find all subtask-complete signals in a response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        List of Signal objects for completed subtasks.
    """
    signals = parse_subtask_signals(response)
    return [s for s in signals if s.is_subtask_complete]


def find_subtask_promotion_signals(response: str) -> List[Signal]:
    """Find all promote-subtask signals in a response.

    Args:
        response: Full text response from Claude CLI.

    Returns:
        List of Signal objects for subtasks to be promoted.
    """
    signals = parse_subtask_signals(response)
    return [s for s in signals if s.is_subtask_promotion]


def get_subtask_signal_format_example(subtask_id: str, token: str) -> str:
    """Get example of correct subtask signal format for feedback.

    Args:
        subtask_id: Subtask ID to include in example.
        token: Session token to include in example.

    Returns:
        Example signal string.
    """
    return f'''<subtask-complete id="{subtask_id}" session="{token}">
Summary of what was done for this subtask.
</subtask-complete>'''


def get_subtask_promotion_format_example(subtask_id: str, token: str) -> str:
    """Get example of correct subtask promotion signal format.

    Args:
        subtask_id: Subtask ID to include in example.
        token: Session token to include in example.

    Returns:
        Example signal string.
    """
    return f'''<promote-subtask id="{subtask_id}" session="{token}">
Reason for promotion: This subtask is too complex and needs its own
test suite and review cycle.
</promote-subtask>'''
