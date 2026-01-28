"""Agent prompt templates for Ralph orchestrator.

Provides prompt builders for different agent roles:
- Implementation: Code implementation based on task description
- Test-writing: Write tests for implemented features (guardrailed)
- Review: Code review against acceptance criteria (read-only)
- Fix: Fix issues identified by gates or review
- UI Testing: Browser exploration and Robot Framework test generation (guardrailed)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class AgentRole(str, Enum):
    """Agent roles in the verified loop."""
    IMPLEMENTATION = "implementation"
    TEST_WRITING = "test_writing"
    REVIEW = "review"
    FIX = "fix"
    UI_PLANNING = "ui_planning"
    UI_IMPLEMENTATION = "ui_implementation"
    ROBOT_PLANNING = "robot_planning"
    ROBOT_IMPLEMENTATION = "robot_implementation"
    UI_TESTING = "ui_testing"


@dataclass
class TaskContext:
    """Context for a task being executed."""
    task_id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    notes: str = ""
    previous_feedback: Optional[str] = None
    gate_output: Optional[str] = None
    review_feedback: Optional[str] = None


def build_implementation_prompt(
    task: TaskContext,
    session_token: str,
    project_description: str = "",
    agents_md_content: str = "",
    report_path: Optional[str] = None,
) -> str:
    """Build prompt for implementation agent.
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        project_description: Project description from prd.json.
        agents_md_content: Content of AGENTS.md for context.
        report_path: Path to write agent report (append-only).
        
    Returns:
        Complete prompt string.
    """
    criteria_list = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    
    feedback_section = ""
    if task.previous_feedback:
        feedback_section = f"""
## Previous Feedback

The previous attempt had issues that need to be addressed:

{task.previous_feedback}

Please address these issues in this iteration.
"""
    
    if task.gate_output:
        feedback_section += f"""
## Gate Failure Output

The build/test gates failed with the following output:

```
{task.gate_output}
```

Please fix these issues.
"""
    
    if task.review_feedback:
        feedback_section += f"""
## Review Feedback

The code review found the following issues:

{task.review_feedback}

Please address these issues to get approval.
"""
    
    agents_section = ""
    if agents_md_content:
        agents_section = f"""
## Project Context (AGENTS.md)

{agents_md_content}
"""
    
    report_section = ""
    if report_path:
        report_section = f"""
## Report Output

Write a brief summary of your work to: {report_path}
This is an append-only file. Add a timestamped section for each iteration.
Format:
```
## Implementation - [timestamp]
- What was done
- Files modified
- Notes for next iteration (if any)
```
"""
    
    return f"""# Implementation Task

You are implementing a task for a software project.

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Acceptance Criteria

{criteria_list}
{agents_section}
{feedback_section}{report_section}
## Instructions

1. Implement the required changes to satisfy all acceptance criteria
2. Follow project conventions and best practices
3. When complete, output the completion signal

## Completion Signal

When you have completed the implementation, you MUST output this signal:

```
<task-done session="{session_token}">
Implementation complete. Changes:
- [describe what you changed]
</task-done>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def build_test_writing_prompt(
    task: TaskContext,
    session_token: str,
    test_paths: List[str],
    project_description: str = "",
    report_path: Optional[str] = None,
) -> str:
    """Build prompt for test-writing agent (guardrailed).
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        test_paths: Allowed test file patterns.
        project_description: Project description.
        report_path: Path to write agent report (append-only).
        
    Returns:
        Complete prompt string.
    """
    criteria_list = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    test_paths_list = "\n".join(f"- {p}" for p in test_paths)
    
    report_section = ""
    if report_path:
        report_section = f"""
## Report Output

Write a brief summary of your work to: {report_path}
This is an append-only file. Add a timestamped section for each iteration.
Format:
```
## Test Writing - [timestamp]
- Tests created/modified
- Coverage notes
- Issues encountered (if any)
```
"""
    
    return f"""# Test-Writing Task (GUARDRAILED)

You are writing tests for implemented features.

## CRITICAL FILE RESTRICTIONS

You may ONLY create/modify files matching these patterns:
{test_paths_list}

**ALLOWED:**
- Python test files (e.g., `tests/**/test_*.py`, `tests/**/*_test.py`)
- Test fixture files, conftest.py

**FORBIDDEN (will be reverted):**
- ANY markdown files (*.md) in tests/ - DO NOT create documentation in tests/
- ANY source files outside test directories
- Test result documents or reports in tests/

Any modifications to forbidden paths will be **automatically reverted**.

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Acceptance Criteria

{criteria_list}

## TEST QUALITY RULES

You MUST follow these rules to avoid writing broken tests:

1. **Only assert on REAL public APIs**: Do not invent or assume attributes, methods, or behaviors that don't exist. Read the actual source code to verify what the API provides before writing assertions.

2. **Prefer black-box assertions**: Test observable behavior rather than internal implementation:
   - CLI output and exit codes
   - File existence and content
   - Schema/structure validity
   - HTTP responses
   - Log output
   Avoid testing private attributes or internal state unless explicitly required.

3. **Keep scope tight**: Only write tests that verify the task's acceptance criteria. Do not add speculative tests for features not mentioned in the criteria.

4. **Verify imports work**: Before using any import in a test, confirm the module and symbol exist in the codebase.

5. **No documentation in tests/**: Do not create `.md` files, test reports, or narrative documents in `tests/`. Write only executable test code.
{report_section}
## Instructions

1. Read the implementation to understand what APIs and behaviors actually exist
2. Write focused tests that validate each acceptance criterion
3. Cover happy path and realistic edge cases
4. Only create/modify files in test directories (no .md files!)
5. Follow project testing conventions

## Completion Signal

When you have completed writing tests, output:

```
<tests-done session="{session_token}">
Tests written:
- [list of test files/functions]
</tests-done>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def build_review_prompt(
    task: TaskContext,
    session_token: str,
    project_description: str = "",
    report_path: Optional[str] = None,
) -> str:
    """Build prompt for review agent (read-only).
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        project_description: Project description.
        report_path: Path to write agent report (append-only).
        
    Returns:
        Complete prompt string.
    """
    criteria_list = "\n".join(f"- [ ] {c}" for c in task.acceptance_criteria)
    
    report_section = ""
    if report_path:
        report_section = f"""
## Report Output

Write your review findings to: {report_path}
This is an append-only file. Add a timestamped section for each review.
Format:
```
## Review - [timestamp]
- Criteria checked: [list]
- Result: APPROVED / REJECTED
- Issues (if any): [list]
```
"""
    
    return f"""# Code Review Task (READ-ONLY)

You are reviewing code changes against acceptance criteria.

## IMPORTANT: READ-ONLY MODE

You may NOT modify any files. You can only:
- Read files to review the implementation
- Approve or reject based on criteria

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Acceptance Criteria Checklist

{criteria_list}
{report_section}
## Instructions

1. Review the implementation against each acceptance criterion
2. Check for code quality, security, and best practices
3. Verify tests exist and cover the implementation
4. Output approval or rejection with feedback

## Completion Signal

If ALL criteria are satisfied, output:

```
<review-approved session="{session_token}">
Code review passed. All acceptance criteria verified.
</review-approved>
```

If ANY criterion is NOT satisfied, output:

```
<review-rejected session="{session_token}">
Issues found:
- [list specific issues]
</review-rejected>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def build_fix_prompt(
    task: TaskContext,
    session_token: str,
    failure_context: str,
    project_description: str = "",
) -> str:
    """Build prompt for fix agent.
    
    Args:
        task: Task context.
        session_token: Session token for completion signal.
        failure_context: Description of what failed and why.
        project_description: Project description.
        
    Returns:
        Complete prompt string.
    """
    return f"""# Fix Task

You are fixing issues that were identified during verification.

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Failure Context

{failure_context}

## Instructions

1. Analyze the failure output to understand the root cause
2. Make minimal changes to fix the identified issues
3. Ensure fixes don't break other functionality
4. Output the completion signal when done

## Completion Signal

When you have fixed the issues, output:

```
<fix-done session="{session_token}">
Fixed the identified issues:
- [describe fixes]
</fix-done>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def build_ui_planning_prompt(
    failure_description: str,
    session_token: str,
    screenshot_path: Optional[str] = None,
) -> str:
    """Build prompt for UI planning agent (read-only).
    
    Args:
        failure_description: Description of UI test failure.
        session_token: Session token.
        screenshot_path: Path to failure screenshot if available.
        
    Returns:
        Complete prompt string.
    """
    screenshot_section = ""
    if screenshot_path:
        screenshot_section = f"""
## Screenshot

Failure screenshot available at: {screenshot_path}
"""
    
    return f"""# UI Test Failure Analysis (READ-ONLY)

You are analyzing a UI test failure to create a fix plan.

## IMPORTANT: READ-ONLY MODE

You may NOT modify any files. You can only:
- Read files to understand the issue
- Create a plan for fixing the UI issue

## Failure Description

{failure_description}
{screenshot_section}
## Instructions

1. Analyze the failure to identify the root cause
2. Determine which files need to be modified
3. Create a clear plan for fixing the issue

## Output

Output your analysis and plan:

```
<ui-plan session="{session_token}">
## Root Cause Analysis
[Your analysis]

## Proposed Fix
[Step-by-step fix plan]

## Files to Modify
[List of files]
</ui-plan>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def build_ui_implementation_prompt(
    plan: str,
    session_token: str,
) -> str:
    """Build prompt for UI fix implementation agent.
    
    Args:
        plan: The fix plan from planning phase.
        session_token: Session token.
        
    Returns:
        Complete prompt string.
    """
    return f"""# UI Fix Implementation

You are implementing fixes based on the provided plan.

## Fix Plan

{plan}

## Instructions

1. Implement the fixes described in the plan
2. Make minimal changes to fix the issue
3. Test your changes locally if possible

## Completion Signal

When you have completed the fixes, output:

```
<ui-fix-done session="{session_token}">
Fixed UI issues:
- [describe fixes]
</ui-fix-done>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def build_ui_testing_prompt(
    task: TaskContext,
    session_token: str,
    base_url: str,
    robot_suite_path: str,
    project_description: str = "",
    report_path: Optional[str] = None,
) -> str:
    """Build prompt for UI testing agent (guardrailed to Robot test files).
    
    This agent uses browser-use (agent-browser CLI) to explore the frontend,
    verify implementations visually, and generate/update Robot Framework tests.
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        base_url: Base URL for the frontend (e.g., http://localhost:3000).
        robot_suite_path: Path where Robot tests can be written (e.g., tests/robot).
        project_description: Project description.
        report_path: Path to write agent report (append-only).
        
    Returns:
        Complete prompt string.
    """
    criteria_list = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    
    report_section = ""
    if report_path:
        report_section = f"""
## Report Output

Write a brief summary of your work to: {report_path}
This is an append-only file. Add a timestamped section for each iteration.
Format:
```
## UI Testing - [timestamp]
- Pages visited
- Verifications performed
- Tests generated/updated
- Issues found (if any)
```
"""
    
    return f"""# UI Testing Task (GUARDRAILED)

You are testing frontend changes using browser automation and generating Robot Framework tests.

## CRITICAL FILE RESTRICTIONS

You may ONLY create/modify files in:
- `{robot_suite_path}/**/*.robot`

**ALLOWED:**
- Robot Framework test files (.robot) in the configured suite path
- Reading any files to understand the implementation

**FORBIDDEN (will be reverted):**
- ANY source files (*.py, *.ts, *.tsx, *.js, *.jsx)
- ANY files outside `{robot_suite_path}/`
- Modifying existing non-test code

Any modifications to forbidden paths will be **automatically reverted**.

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Acceptance Criteria

{criteria_list}

## Tools Available

You have access to the `agent-browser` CLI for browser interaction:

```bash
# Open a URL in the browser
agent-browser open {base_url}

# Take a snapshot of the current page (accessibility tree)
agent-browser snapshot

# Click on an element (use ref from snapshot)
agent-browser click --ref <element_ref> --element "description"

# Type text into an element
agent-browser type --ref <element_ref> --text "text to type"

# Take a screenshot
agent-browser screenshot --filename "screenshot.png"

# Navigate to a URL
agent-browser navigate --url "{base_url}/some/path"
```

## Robot Framework Test Template

When generating tests, use this structure:

```robot
*** Settings ***
Library    Browser
Suite Setup    Open Browser    {base_url}    chromium    headless=true
Suite Teardown    Close Browser

*** Test Cases ***
[Test Name Based on Acceptance Criteria]
    [Documentation]    Verifies: [specific acceptance criterion]
    [Test steps using Browser library keywords]
    
*** Keywords ***
[Reusable keywords if needed]
```
{report_section}
## Instructions

1. **Explore the Frontend**
   - Use `agent-browser open {base_url}` to start
   - Navigate to pages/components affected by the task
   - Use `agent-browser snapshot` to understand the page structure

2. **Verify Each Acceptance Criterion**
   - Systematically check each criterion visually
   - Document what you observe vs what was expected
   - Take screenshots of important states

3. **Generate/Update Robot Framework Tests**
   - Create `.robot` files in `{robot_suite_path}/` that capture verified behavior
   - Name tests descriptively based on what they verify
   - Keep tests focused and maintainable
   - Use Browser library keywords (New Browser, New Page, Click, Fill Text, etc.)

4. **Output Results**
   - Report pass/fail for each acceptance criterion
   - List all tests generated/updated

## Completion Signal

When you have completed UI testing, output:

```
<ui-tests-done session="{session_token}">
## Verification Results
- [criterion 1]: PASS/FAIL - [observation]
- [criterion 2]: PASS/FAIL - [observation]

## Tests Generated
- {robot_suite_path}/[test_file_1.robot]: [description]
- {robot_suite_path}/[test_file_2.robot]: [description]

## Issues Found
- [any issues that need attention]
</ui-tests-done>
```

IMPORTANT: The session token must be exactly: {session_token}
"""


def get_role_description(role: AgentRole) -> str:
    """Get human-readable description of an agent role.
    
    Args:
        role: Agent role enum value.
        
    Returns:
        Description string.
    """
    descriptions = {
        AgentRole.IMPLEMENTATION: "Implementation agent (code changes)",
        AgentRole.TEST_WRITING: "Test-writing agent (guardrailed to test paths)",
        AgentRole.REVIEW: "Review agent (read-only verification)",
        AgentRole.FIX: "Fix agent (resolve verification failures)",
        AgentRole.UI_PLANNING: "UI planning agent (analyze test failures)",
        AgentRole.UI_IMPLEMENTATION: "UI implementation agent (fix UI issues)",
        AgentRole.ROBOT_PLANNING: "Robot planning agent (analyze Robot test failures)",
        AgentRole.ROBOT_IMPLEMENTATION: "Robot implementation agent (fix Robot test issues)",
        AgentRole.UI_TESTING: "UI testing agent (browser exploration and Robot test generation)",
    }
    return descriptions.get(role, str(role))


def get_allowed_tools_for_role(role: AgentRole) -> List[str]:
    """Get default allowed tools for an agent role.
    
    Args:
        role: Agent role.
        
    Returns:
        List of tool names.
    """
    # Read-only roles
    if role in (AgentRole.REVIEW, AgentRole.UI_PLANNING, AgentRole.ROBOT_PLANNING):
        return ["Read", "Glob", "LS", "Grep"]
    
    # Test-writing role (limited write access)
    if role == AgentRole.TEST_WRITING:
        return ["Read", "Write", "Glob", "LS", "Grep"]
    
    # UI testing role (limited write access + shell for agent-browser CLI)
    if role == AgentRole.UI_TESTING:
        return ["Read", "Write", "Glob", "LS", "Shell"]
    
    # Implementation and fix roles (full access)
    return ["Read", "Write", "Glob", "LS", "Grep", "Shell", "Edit"]
