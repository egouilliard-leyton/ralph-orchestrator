"""Agent prompt templates for Ralph orchestrator.

Provides prompt builders for different agent roles:
- Implementation: Code implementation based on task description
- Test-writing: Write tests for implemented features (guardrailed)
- Review: Code review against acceptance criteria (read-only)
- Fix: Fix issues identified by gates or review
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
) -> str:
    """Build prompt for implementation agent.
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        project_description: Project description from prd.json.
        agents_md_content: Content of AGENTS.md for context.
        
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
    
    return f"""# Implementation Task

You are implementing a task for a software project.

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Acceptance Criteria

{criteria_list}
{agents_section}
{feedback_section}
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
) -> str:
    """Build prompt for test-writing agent (guardrailed).
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        test_paths: Allowed test file patterns.
        project_description: Project description.
        
    Returns:
        Complete prompt string.
    """
    criteria_list = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    test_paths_list = "\n".join(f"- {p}" for p in test_paths)
    
    return f"""# Test-Writing Task (GUARDRAILED)

You are writing tests for implemented features.

## IMPORTANT RESTRICTIONS

You may ONLY modify files matching these patterns:
{test_paths_list}

DO NOT modify any source files outside test directories.
Any modifications to source files will be automatically reverted.

## Project
{project_description}

## Task: {task.task_id} - {task.title}

{task.description}

## Acceptance Criteria

{criteria_list}

## Instructions

1. Write comprehensive tests for the implemented feature
2. Cover happy path and edge cases
3. Only create/modify files in test directories
4. Follow project testing conventions

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
) -> str:
    """Build prompt for review agent (read-only).
    
    Args:
        task: Task context with description and criteria.
        session_token: Session token for completion signal.
        project_description: Project description.
        
    Returns:
        Complete prompt string.
    """
    criteria_list = "\n".join(f"- [ ] {c}" for c in task.acceptance_criteria)
    
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
    
    # Implementation and fix roles (full access)
    return ["Read", "Write", "Glob", "LS", "Grep", "Shell", "Edit"]
