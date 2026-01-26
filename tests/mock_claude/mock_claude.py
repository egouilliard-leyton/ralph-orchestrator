#!/usr/bin/env python3
"""
Mock Claude CLI for Ralph Orchestrator Testing.

This mock simulates the Claude CLI for integration testing without
requiring real API calls. Behavior is controlled via:

1. Environment variables (MOCK_SCENARIO, MOCK_RESPONSE_FILE)
2. Prompt content patterns (SIMULATE_* directives)
3. Default behavior (returns valid completion signals)

Usage:
    RALPH_CLAUDE_CMD="python tests/mock_claude/mock_claude.py" ralph run ...

Environment Variables:
    MOCK_SCENARIO: Predefined scenario name (default, invalid_token, no_signal, etc.)
    MOCK_RESPONSE_FILE: Path to file containing custom response
    MOCK_DELAY: Artificial delay in seconds (for timeout testing)

Exit codes:
    0 - Success (response written to stdout)
    1 - Simulated failure
"""

import sys
import os
import re
import json
import argparse
import time
from typing import Optional, Dict, Any
from pathlib import Path


class MockClaudeCLI:
    """Simulates Claude CLI for testing Ralph orchestrator."""
    
    def __init__(self):
        self.scenario = os.environ.get("MOCK_SCENARIO", "default")
        self.response_file = os.environ.get("MOCK_RESPONSE_FILE")
        self.delay = float(os.environ.get("MOCK_DELAY", "0"))
        self.prompt = ""
        self.model = "mock-model"
        self.args: Optional[argparse.Namespace] = None
        
    def parse_args(self) -> argparse.Namespace:
        """Parse Claude CLI arguments."""
        parser = argparse.ArgumentParser(description="Mock Claude CLI")
        parser.add_argument("-p", "--prompt", required=False, help="Prompt text")
        parser.add_argument("-m", "--model", default="mock-model", help="Model name")
        parser.add_argument("--print", action="store_true", help="Print mode")
        parser.add_argument("--output-format", default="text", help="Output format")
        parser.add_argument("--allowedTools", nargs="*", help="Allowed tools")
        parser.add_argument("--max-turns", type=int, help="Max turns")
        parser.add_argument("--timeout", type=int, help="Timeout in seconds")
        parser.add_argument("prompt_positional", nargs="?", help="Positional prompt")
        
        self.args, _ = parser.parse_known_args()
        self.model = self.args.model
        
        # Get prompt from various sources
        if self.args.prompt:
            self.prompt = self.args.prompt
        elif self.args.prompt_positional:
            self.prompt = self.args.prompt_positional
        elif not sys.stdin.isatty():
            self.prompt = sys.stdin.read()
        
        return self.args
    
    def extract_session_token(self) -> Optional[str]:
        """Extract session token from prompt."""
        patterns = [
            # Standard format: ralph-YYYYMMDD-HHMMSS-[hex16]
            r'\b(ralph-\d{8}-\d{6}-[a-f0-9]{16})\b',
            # Flexible format with alphanumeric suffix
            r'SESSION_TOKEN[:\s]+"?(ralph-[\w-]+)"?',
            r'session="(ralph-[\w-]+)"',
            r'session token[:\s]+"?(ralph-[\w-]+)"?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.prompt, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "ralph-mock-00000000-000000-0000000000000000"
    
    def extract_task_id(self) -> str:
        """Extract current task ID from prompt."""
        patterns = [
            r'Task[:\s]+(T-\d{3})',
            r'task_id[:\s]+"?(T-\d{3})"?',
            r'\b(T-\d{3})\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.prompt, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "T-001"
    
    def detect_role(self) -> str:
        """Detect agent role from prompt content."""
        prompt_lower = self.prompt.lower()
        
        # Check for specific role indicators (order matters - more specific first)
        # Use word boundary matching for short keywords to avoid false positives
        role_indicators = [
            # Tasks generation (check before prd due to "prd.json" substring)
            ("generate tasks", "", "tasks_generation"),
            ("tasks", "generate", "tasks_generation"),
            ("convert", "prd.json", "tasks_generation"),
            # PRD generation
            ("create prd", "", "prd_generation"),
            ("generate prd", "", "prd_generation"),
            # Review/test/fix roles
            ("code review", "read-only", "review"),
            ("review the code", "", "review"),
            ("review agent", "", "review"),
            ("test-writing", "", "test_writing"),
            ("test agent", "guardrail", "test_writing"),
            ("write tests", "", "test_writing"),
            ("fix task", "", "fix"),
            ("fix agent", "", "fix"),
            ("runtime fix", "", "fix"),
            ("fix issues", "", "fix"),
            ("fix the following", "", "fix"),
            ("fix the identified", "", "fix"),
            ("plan", "read-only", "planning"),
            # UI roles - use longer patterns to avoid false positives
            ("ui test", "read-only", "ui_planning"),
            ("ui fix", "", "ui_implementation"),
            ("agent-browser", "read-only", "ui_planning"),
            ("agent-browser", "fix", "ui_implementation"),
            # Robot roles
            ("robot framework", "read-only", "robot_planning"),
            ("robot framework", "implement", "robot_implementation"),
            ("robot test", "", "robot_planning"),
            # Analysis roles
            ("analysis", "report", "analysis"),
            ("analyze", "report", "analysis"),
            ("analyze", "priorities", "analysis"),
        ]
        
        for keyword1, keyword2, role in role_indicators:
            if keyword1 in prompt_lower:
                if not keyword2 or keyword2 in prompt_lower:
                    return role
        
        return "implementation"
    
    def check_special_directives(self) -> Optional[str]:
        """Check for special testing directives in prompt."""
        directives = [
            "SIMULATE_INVALID_TOKEN",
            "SIMULATE_NO_SIGNAL",
            "SIMULATE_TIMEOUT",
            "SIMULATE_REVIEW_REJECT",
            "SIMULATE_GATES_FAIL",
            "SIMULATE_GUARDRAIL_VIOLATION",
            "SIMULATE_ANALYSIS_FAIL",
            "SIMULATE_EMPTY_RESPONSE",
        ]
        
        for directive in directives:
            if directive in self.prompt:
                return directive.replace("SIMULATE_", "").lower()
        
        return None
    
    def generate_response(self) -> str:
        """Generate appropriate response based on scenario and role."""
        # Apply delay if configured
        if self.delay > 0:
            time.sleep(self.delay)
        
        # Check for custom response file
        if self.response_file and Path(self.response_file).exists():
            return Path(self.response_file).read_text()
        
        # Check for special directives
        directive = self.check_special_directives()
        if directive:
            return self._directive_response(directive)
        
        # Check environment scenario
        if self.scenario != "default":
            return self._scenario_response(self.scenario)
        
        # Generate based on detected role
        role = self.detect_role()
        return self._role_response(role)
    
    def _directive_response(self, directive: str) -> str:
        """Generate response for special directive."""
        token = self.extract_session_token()
        task_id = self.extract_task_id()
        
        responses = {
            "invalid_token": f'''I've completed the implementation!

<task-done session="wrong-token-invalid-12345678">
Task {task_id} is complete with an invalid token.
</task-done>''',

            "no_signal": '''I've made the changes you requested. The implementation 
looks good and should work correctly.

Changes made:
- Updated the auth module
- Added new test cases
- Fixed the configuration

Let me know if you need anything else!''',

            "timeout": "",  # Will be handled by delay

            "review_reject": f'''<review-rejected session="{token}">
Issues found during code review:

1. Missing error handling for edge cases
2. No logging for authentication failures  
3. Test coverage below 80%

Please address these issues before approval.
</review-rejected>''',

            "gates_fail": f'''<task-done session="{token}">
Task {task_id} implementation complete.
Note: Build may fail due to syntax error introduced.
</task-done>''',

            "guardrail_violation": f'''I've made the following changes:

1. Updated tests/test_auth.py - Added new test cases
2. Modified src/main.py - Added logging (VIOLATION)
3. Created tests/test_utils.py - Helper tests

<tests-done session="{token}">
Tests completed with file modifications.
</tests-done>''',

            "analysis_fail": "Error: Unable to analyze report. Invalid format.",

            "empty_response": "",
        }
        
        return responses.get(directive, responses["no_signal"])
    
    def _scenario_response(self, scenario: str) -> str:
        """Generate response for predefined scenario."""
        token = self.extract_session_token()
        task_id = self.extract_task_id()
        
        scenarios = {
            "success": f'''<task-done session="{token}">
Task {task_id} completed successfully.
Files modified: src/auth.py, tests/test_auth.py
</task-done>''',

            "all_tasks_complete": f'''All tasks have been completed!

<task-done session="{token}">
Final task {task_id} is complete.
</task-done>''',

            "review_approve": f'''<review-approved session="{token}">
Code review passed. All criteria met.
</review-approved>''',

            "review_reject": f'''<review-rejected session="{token}">
Issues: Missing tests for edge cases.
</review-rejected>''',

            "tests_done": f'''<tests-done session="{token}">
Tests written for {task_id}:
- test_feature_works
- test_feature_edge_case
</tests-done>''',

            "fix_done": f'''<fix-done session="{token}">
Fixed the identified issues.
</fix-done>''',
        }
        
        return scenarios.get(scenario, scenarios["success"])
    
    def _role_response(self, role: str) -> str:
        """Generate response based on agent role."""
        token = self.extract_session_token()
        task_id = self.extract_task_id()
        
        responses: Dict[str, str] = {
            "implementation": f'''I've implemented the requested changes.

Changes made:
- Created src/auth/service.py with AuthService class
- Added JWT token generation and validation
- Updated src/config.py with auth settings

Verification:
- Syntax check passed
- Import test passed

<task-done session="{token}">
Task {task_id} implementation complete.
</task-done>''',

            "test_writing": f'''I've written comprehensive tests for the implementation.

Tests created in tests/test_auth_service.py:
- test_create_token_returns_jwt
- test_verify_token_valid  
- test_verify_token_expired_raises
- test_verify_token_invalid_raises

All tests are focused on the test directory as required.

<tests-done session="{token}">
Tests written for task {task_id}.
</tests-done>''',

            "review": f'''Code review completed.

Checklist:
✓ Implementation matches acceptance criteria
✓ Tests cover happy path and edge cases
✓ Code follows project conventions
✓ No security vulnerabilities detected
✓ Error handling is appropriate

<review-approved session="{token}">
Task {task_id} approved for completion.
</review-approved>''',

            "fix": f'''I've fixed the identified issues.

Fixes applied:
- Added missing error handling in auth service
- Improved logging for authentication failures
- Increased test coverage to 85%

Build verification passed.

<fix-done session="{token}">
Fixes complete for task {task_id}.
</fix-done>''',

            "planning": f'''Analysis complete. Here's my plan:

<ui-plan session="{token}">
## Root Cause Analysis
The identified issue stems from incorrect validation logic.

## Proposed Fix
1. Update validation function
2. Add error message styling
3. Add loading state

## Files to Modify
- src/components/Form.tsx
- src/styles/forms.css
- tests/test_form.py
</ui-plan>''',

            "ui_planning": f'''UI test analysis complete.

<ui-plan session="{token}">
## Failures Detected
- Form validation not triggering on blur
- Error message not visible

## Investigation
Event handler binding issue in Form component.

## Fix Plan
1. Add onBlur handler
2. Update error visibility logic
3. Add aria-invalid attribute
</ui-plan>''',

            "ui_implementation": f'''UI fixes implemented.

Changes:
- Fixed event handler binding
- Added proper error display
- Updated accessibility attributes

<ui-fix-done session="{token}">
Fixed form validation and error display.
</ui-fix-done>''',

            "robot_planning": f'''Robot Framework test analysis.

<robot-plan session="{token}">
## Failed Tests
- Login Form Validation Test
- Submit Button State Test

## Analysis
Locators need updating after UI changes.

## Fix Plan
1. Update element locators
2. Add wait conditions
3. Increase timeout for async operations
</robot-plan>''',

            "robot_implementation": f'''Robot Framework fixes applied.

<robot-fix-done session="{token}">
Updated test locators and wait conditions.
</robot-fix-done>''',

            "analysis": self._analysis_response(),

            "prd_generation": self._prd_response(),

            "tasks_generation": self._tasks_response(),
        }
        
        return responses.get(role, responses["implementation"])
    
    def _analysis_response(self) -> str:
        """Generate analysis JSON response."""
        return json.dumps({
            "priority_item": "Fix user authentication flow",
            "description": "The login form has validation issues causing user friction. "
                          "Users report confusing error messages when entering invalid email formats.",
            "rationale": "This issue affects 15% of signup attempts and has high impact on conversion. "
                        "It's a focused fix that doesn't require database changes.",
            "acceptance_criteria": [
                "Email validation shows clear error for invalid format",
                "Password requirements are displayed before typing",
                "Submit button is disabled until form is valid",
                "Error messages use user-friendly language"
            ],
            "estimated_tasks": 8,
            "branch_name": "ralph/fix-auth-validation",
            "excluded_items": [
                {"item": "Dark mode toggle", "reason": "Lower priority - cosmetic only"},
                {"item": "Performance optimization", "reason": "Requires more investigation"}
            ]
        }, indent=2)
    
    def _prd_response(self) -> str:
        """Generate PRD markdown response."""
        return '''# PRD: Fix User Authentication Flow

## Overview
Update the login form to provide better validation feedback and improve user experience.

## Goals
- Reduce signup abandonment by 50%
- Improve error message clarity
- Add proper form validation states

## Tasks

### T-001: Add email format validation
Validate email format on input change and show inline error.

**Acceptance Criteria:**
- Invalid email shows error message below input
- Valid email clears error message
- Error styling matches design system

### T-002: Display password requirements
Show password requirements before user starts typing.

**Acceptance Criteria:**
- Requirements visible on form load
- Met requirements show checkmark
- Unmet requirements show X

### T-003: Add form state management
Manage form validation state properly.

**Acceptance Criteria:**
- Submit disabled until all fields valid
- Loading state on submit
- Error state on API failure

### T-004: Update error message styling
Ensure error messages are accessible and visible.

**Acceptance Criteria:**
- aria-invalid attribute on invalid fields
- Error messages have proper contrast
- Screen reader announces errors

### T-005: Add loading state to submit button
Show loading indicator during form submission.

**Acceptance Criteria:**
- Button shows spinner on click
- Button is disabled during loading
- Success/error state after response

## Non-Goals
- Dark mode support (separate PR)
- Password strength meter
- Social login

## Success Metrics
- Signup completion rate increases by 10%
- Form error rate decreases by 50%
- No new accessibility violations'''
    
    def _tasks_response(self) -> str:
        """Generate tasks JSON response."""
        return json.dumps({
            "project": "Fix Authentication Flow",
            "branchName": "ralph/fix-auth-validation",
            "description": "Improve login form validation and user experience",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Add email format validation",
                    "description": "Validate email format on input change and display inline error",
                    "acceptanceCriteria": [
                        "File `src/components/LoginForm.tsx` contains email validation logic",
                        "Invalid email shows error message below input field",
                        "Run `npm test -- --testPathPattern=LoginForm` - exits with code 0"
                    ],
                    "priority": 1,
                    "passes": False,
                    "notes": ""
                },
                {
                    "id": "T-002",
                    "title": "Display password requirements",
                    "description": "Show password requirements before user starts typing",
                    "acceptanceCriteria": [
                        "Password requirements visible on form load",
                        "Met requirements show checkmark indicator",
                        "agent-browser: open /login - password requirements visible"
                    ],
                    "priority": 2,
                    "passes": False,
                    "notes": ""
                },
                {
                    "id": "T-003",
                    "title": "Add form validation state",
                    "description": "Implement proper form state management",
                    "acceptanceCriteria": [
                        "Submit button disabled until form valid",
                        "File `src/hooks/useFormValidation.ts` exists",
                        "Run `npm test` - exits with code 0"
                    ],
                    "priority": 3,
                    "passes": False,
                    "notes": ""
                },
                {
                    "id": "T-004",
                    "title": "Update error styling",
                    "description": "Ensure error messages are accessible",
                    "acceptanceCriteria": [
                        "Invalid fields have aria-invalid='true'",
                        "Error messages have role='alert'",
                        "Color contrast ratio meets WCAG AA"
                    ],
                    "priority": 4,
                    "passes": False,
                    "notes": ""
                },
                {
                    "id": "T-005",
                    "title": "Add submit loading state",
                    "description": "Show loading indicator during submission",
                    "acceptanceCriteria": [
                        "Button shows spinner during API call",
                        "Button disabled while loading",
                        "agent-browser: click Submit - loading state visible"
                    ],
                    "priority": 5,
                    "passes": False,
                    "notes": ""
                }
            ]
        }, indent=2)
    
    def run(self) -> int:
        """Main entry point."""
        self.parse_args()
        
        # Handle timeout simulation
        directive = self.check_special_directives()
        if directive == "timeout":
            # Sleep for a very long time (will be killed by test timeout)
            time.sleep(3600)
            return 1
        
        response = self.generate_response()
        print(response)
        return 0


def main():
    """Main entry point."""
    cli = MockClaudeCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
