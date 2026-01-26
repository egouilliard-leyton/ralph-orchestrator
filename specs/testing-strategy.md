# Ralph Orchestrator: Workflow Self-Test Harness Specification

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Design Document

This document defines the testing strategy for the Ralph orchestrator, including the mock Claude CLI, fixture repositories, and integration test specifications. The harness enables reliable testing of the orchestrator workflow without requiring real Claude API calls.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Testing Layers](#2-testing-layers)
3. [Mock Claude CLI](#3-mock-claude-cli)
4. [Fixture Repositories](#4-fixture-repositories)
5. [Unit Tests](#5-unit-tests)
6. [Integration Tests](#6-integration-tests)
7. [Autopilot Contract Tests](#7-autopilot-contract-tests)
8. [Test Infrastructure](#8-test-infrastructure)
9. [CI/CD Integration](#9-cicd-integration)
10. [Manual Integration Testing](#10-manual-integration-testing)

---

## 1. Overview

### 1.1 Design Goals

1. **No real Claude API calls in CI** - Tests must run without network access or API keys
2. **Deterministic outputs** - Same inputs produce same outputs for reproducible tests
3. **Full workflow coverage** - Test all phases: task advancement, gates, guardrails, verification
4. **Fast feedback** - Unit tests under 5 seconds, integration tests under 60 seconds
5. **Realistic scenarios** - Fixture repos mimic real project structures

### 1.2 Testing Pyramid

```
                    ┌─────────────────┐
                    │    Manual E2E   │  ← Optional: Real Claude
                    │   (Real Claude) │     for final validation
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │    Integration Tests        │  ← Mock Claude + Fixture Repos
              │   (Mock Claude + Fixtures)  │     Full workflow validation
              └──────────────┬──────────────┘
                             │
     ┌───────────────────────▼───────────────────────┐
     │              Unit Tests                        │  ← Pure logic, no mocks
     │  (Token, Checksum, Parsing, Guardrails, etc.) │     Fast, isolated tests
     └────────────────────────────────────────────────┘
```

### 1.3 Environment Variable Override

The orchestrator supports `RALPH_CLAUDE_CMD` to override the Claude CLI command:

```bash
# Default (production)
RALPH_CLAUDE_CMD="claude"

# Testing (mock)
RALPH_CLAUDE_CMD="python tests/mock_claude/mock_claude.py"
```

This enables testing without modifying any orchestrator code.

---

## 2. Testing Layers

### 2.1 Unit Tests (No External Dependencies)

| Module | Test Focus | Expected Count |
|--------|------------|----------------|
| `session/token.py` | Token generation, format validation | 5-8 |
| `session/checksum.py` | SHA-256 computation, tamper detection | 5-8 |
| `tasks/parser.py` | prd.json parsing, CR markdown parsing | 10-15 |
| `tasks/selector.py` | Priority ordering, subtask handling | 8-10 |
| `tasks/status.py` | Status updates, checksum integration | 6-8 |
| `agents/signals.py` | Signal extraction, token validation | 10-12 |
| `agents/guardrails.py` | Path matching, glob patterns | 8-10 |
| `gates/conditions.py` | When-condition evaluation | 5-6 |
| `config.py` | Config loading, schema validation | 10-12 |

### 2.2 Integration Tests (Mock Claude + Fixture Repos)

| Test Suite | Coverage | Fixture |
|------------|----------|---------|
| `test_task_loop.py` | Task advancement with valid signals | `python_min` |
| `test_invalid_signals.py` | Signal rejection, retry behavior | `python_min` |
| `test_tampering.py` | Checksum verification, abort on tamper | `python_min` |
| `test_guardrails.py` | Test-agent file restrictions | `fullstack_min` |
| `test_gates.py` | Gate ordering, fatal vs warning | `node_min` |
| `test_services.py` | Service lifecycle (mocked health) | `fullstack_min` |
| `test_fix_loops.py` | Runtime fix iteration behavior | `fullstack_min` |
| `test_autopilot.py` | Full autopilot pipeline | `autopilot_min` |

### 2.3 Contract Tests (Schema Validation)

| Contract | Validates |
|----------|-----------|
| `prd.json` | Generated task lists match schema |
| `analysis.json` | Autopilot analysis output schema |
| `session.json` | Session state files |
| `timeline.jsonl` | Event log entries |
| `task-status.json` | Task status format |

---

## 3. Mock Claude CLI

### 3.1 Purpose

The mock Claude CLI simulates the `claude` command-line tool, returning deterministic outputs based on input patterns. It enables testing all agent interactions without real API calls.

### 3.2 Architecture

```
tests/mock_claude/
├── mock_claude.py          # Main entry point (executable)
├── scenarios.py            # Scenario definitions
├── responses/              # Canned response templates
│   ├── implementation.py   # Implementation agent responses
│   ├── test_writing.py     # Test-writing agent responses
│   ├── review.py           # Review agent responses
│   ├── fix.py              # Fix agent responses
│   ├── planning.py         # Planning agent responses
│   └── autopilot.py        # Autopilot-specific responses
└── fixtures/               # Response data files
    ├── valid_task_done.txt
    ├── invalid_token.txt
    ├── no_signal.txt
    └── review_rejected.txt
```

### 3.3 Mock CLI Behavior

```python
#!/usr/bin/env python3
"""
Mock Claude CLI for Ralph Orchestrator Testing.

Usage:
    RALPH_CLAUDE_CMD="python tests/mock_claude/mock_claude.py" ralph run ...

Behavior is controlled via:
1. Environment variables (MOCK_SCENARIO, MOCK_RESPONSE)
2. Prompt content patterns (special directives in prompts)
3. Default scenario (returns valid completion signals)

Exit codes:
    0 - Success (response written to stdout)
    1 - Simulated failure (timeout, error)
"""

import sys
import os
import re
import json
import argparse
from typing import Optional


class MockClaudeCLI:
    """Simulates Claude CLI for testing."""
    
    def __init__(self):
        self.scenario = os.environ.get("MOCK_SCENARIO", "default")
        self.prompt = ""
        self.model = "mock-model"
        
    def parse_args(self):
        """Parse Claude CLI arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--prompt", required=False)
        parser.add_argument("-m", "--model", default="mock-model")
        parser.add_argument("--print", action="store_true")
        parser.add_argument("--output-format", default="text")
        parser.add_argument("--allowedTools", nargs="*")
        parser.add_argument("--max-turns", type=int)
        args, _ = parser.parse_known_args()
        
        self.model = args.model
        
        # Read prompt from stdin if not provided
        if args.prompt:
            self.prompt = args.prompt
        elif not sys.stdin.isatty():
            self.prompt = sys.stdin.read()
        
        return args
    
    def extract_session_token(self) -> Optional[str]:
        """Extract session token from prompt."""
        # Look for token pattern in prompt
        match = re.search(r'SESSION_TOKEN[:\s]+"?(ralph-[\d-]+[a-f0-9]+)"?', self.prompt)
        if match:
            return match.group(1)
        
        # Try alternative pattern
        match = re.search(r'session="(ralph-[\d-]+[a-f0-9]+)"', self.prompt)
        if match:
            return match.group(1)
            
        return None
    
    def extract_task_id(self) -> Optional[str]:
        """Extract current task ID from prompt."""
        match = re.search(r'Task[:\s]+(T-\d{3})', self.prompt)
        if match:
            return match.group(1)
        return "T-001"  # Default
    
    def detect_role(self) -> str:
        """Detect agent role from prompt content."""
        prompt_lower = self.prompt.lower()
        
        if "review" in prompt_lower and "read-only" in prompt_lower:
            return "review"
        elif "test" in prompt_lower and "guardrail" in prompt_lower:
            return "test_writing"
        elif "fix" in prompt_lower or "error" in prompt_lower:
            return "fix"
        elif "plan" in prompt_lower and "read-only" in prompt_lower:
            return "planning"
        elif "ui" in prompt_lower and "browser" in prompt_lower:
            return "ui_planning" if "read-only" in prompt_lower else "ui_implementation"
        elif "robot" in prompt_lower:
            return "robot_planning" if "read-only" in prompt_lower else "robot_implementation"
        elif "analysis" in prompt_lower or "report" in prompt_lower:
            return "analysis"
        elif "prd" in prompt_lower and "generate" in prompt_lower:
            return "prd_generation"
        elif "tasks" in prompt_lower and "generate" in prompt_lower:
            return "tasks_generation"
        else:
            return "implementation"
    
    def check_special_directives(self) -> Optional[str]:
        """Check for special testing directives in prompt."""
        # Special directive: SIMULATE_*
        if "SIMULATE_INVALID_TOKEN" in self.prompt:
            return "invalid_token"
        elif "SIMULATE_NO_SIGNAL" in self.prompt:
            return "no_signal"
        elif "SIMULATE_TIMEOUT" in self.prompt:
            return "timeout"
        elif "SIMULATE_REVIEW_REJECT" in self.prompt:
            return "review_rejected"
        elif "SIMULATE_GATES_FAIL" in self.prompt:
            return "gates_fail"
        elif "SIMULATE_GUARDRAIL_VIOLATION" in self.prompt:
            return "guardrail_violation"
        return None
    
    def generate_response(self) -> str:
        """Generate appropriate response based on scenario and role."""
        # Check for special directives first
        directive = self.check_special_directives()
        if directive:
            return self._directive_response(directive)
        
        # Check environment override
        if self.scenario != "default":
            return self._scenario_response(self.scenario)
        
        # Generate based on detected role
        role = self.detect_role()
        return self._role_response(role)
    
    def _directive_response(self, directive: str) -> str:
        """Generate response for special directive."""
        token = self.extract_session_token() or "UNKNOWN"
        task_id = self.extract_task_id()
        
        if directive == "invalid_token":
            return f'''I've completed the implementation!

<task-done session="wrong-token-12345">
Task {task_id} is complete with an invalid token.
</task-done>'''
        
        elif directive == "no_signal":
            return '''I've made the changes you requested. The implementation 
looks good and should work correctly.

Changes made:
- Updated the auth module
- Added new test cases
- Fixed the configuration

Let me know if you need anything else!'''
        
        elif directive == "timeout":
            # Simulate timeout by sleeping (handled by test timeout)
            import time
            time.sleep(3600)  # Will be killed by test timeout
            return ""
        
        elif directive == "review_rejected":
            return f'''<review-rejected session="{token}">
Issues found during code review:

1. Missing error handling for edge cases
2. No logging for authentication failures  
3. Test coverage below 80%

Please address these issues before approval.
</review-rejected>'''
        
        elif directive == "guardrail_violation":
            return f'''I've made the following changes:

1. Updated tests/test_auth.py ✓
2. Modified src/main.py (added logging)  ← VIOLATION
3. Created tests/test_utils.py ✓

<tests-done session="{token}">
Tests completed with file modifications.
</tests-done>'''
        
        return ""
    
    def _scenario_response(self, scenario: str) -> str:
        """Generate response for predefined scenario."""
        token = self.extract_session_token() or "mock-token"
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
            
            "analysis_output": json.dumps({
                "priority_item": "Fix user authentication flow",
                "description": "Update the login form validation",
                "rationale": "High impact, low effort fix",
                "acceptance_criteria": [
                    "Login form validates email format",
                    "Error messages are user-friendly"
                ],
                "branch_name": "ralph/fix-auth-validation"
            }),
        }
        
        return scenarios.get(scenario, scenarios["success"])
    
    def _role_response(self, role: str) -> str:
        """Generate response based on agent role."""
        token = self.extract_session_token() or "mock-token"
        task_id = self.extract_task_id()
        
        responses = {
            "implementation": f'''I've implemented the requested changes.

Changes made:
- Created src/auth/service.py with AuthService class
- Added JWT token generation and validation
- Updated src/config.py with auth settings

<task-done session="{token}">
Task {task_id} implementation complete.
</task-done>''',
            
            "test_writing": f'''I've written comprehensive tests for the implementation.

Tests created:
- tests/test_auth_service.py
  - test_create_token_returns_jwt
  - test_verify_token_valid
  - test_verify_token_expired_raises

<tests-done session="{token}">
Tests written for task {task_id}.
</tests-done>''',
            
            "review": f'''Code review completed.

Checklist:
✓ Implementation matches acceptance criteria
✓ Tests cover happy path and edge cases
✓ Code follows project conventions
✓ No security vulnerabilities detected

<review-approved session="{token}">
Task {task_id} approved for completion.
</review-approved>''',
            
            "fix": f'''I've fixed the identified issues.

Fixes applied:
- Added missing error handling
- Improved logging for auth failures
- Increased test coverage to 85%

<fix-done session="{token}">
Fixes complete for task {task_id}.
</fix-done>''',
            
            "planning": f'''Analysis complete. Here's my plan:

<ui-plan session="{token}">
## Root Cause Analysis
The login form is not validating input before submission.

## Proposed Fix
1. Add client-side validation
2. Update error message styling
3. Add loading state to submit button

## Files to Modify
- frontend/src/components/LoginForm.tsx
- frontend/src/styles/forms.css
</ui-plan>''',
            
            "ui_planning": f'''UI test analysis complete.

<ui-plan session="{token}">
## Failures Detected
- Login button not responding to click
- Form validation messages not visible

## Investigation
The button click handler is not attached correctly.

## Fix Plan
1. Check event binding in LoginForm component
2. Verify button is not disabled incorrectly
</ui-plan>''',
            
            "ui_implementation": f'''UI fixes implemented.

<ui-fix-done session="{token}">
Fixed login form button handler and validation display.
</ui-fix-done>''',
            
            "analysis": json.dumps({
                "priority_item": "Fix user authentication flow",
                "description": "The login form has validation issues causing user friction.",
                "rationale": "15% of users abandon signup due to confusing error messages.",
                "acceptance_criteria": [
                    "Email validation shows clear error for invalid format",
                    "Password requirements are displayed upfront",
                    "Submit button is disabled until form is valid"
                ],
                "estimated_tasks": 8,
                "branch_name": "ralph/fix-auth-flow"
            }),
            
            "prd_generation": '''# PRD: Fix User Authentication Flow

## Overview
Update the login form to provide better validation feedback.

## Goals
- Reduce signup abandonment by 50%
- Improve error message clarity

## Tasks

### T-001: Add email format validation
### T-002: Display password requirements
### T-003: Add form state management
### T-004: Update error message styling
### T-005: Add loading state to submit''',
            
            "tasks_generation": json.dumps({
                "project": "Fix Authentication Flow",
                "branchName": "ralph/fix-auth-flow",
                "description": "Improve login form validation and UX",
                "tasks": [
                    {
                        "id": "T-001",
                        "title": "Add email format validation",
                        "description": "Validate email format on input change",
                        "acceptanceCriteria": [
                            "Invalid email shows error message",
                            "Valid email clears error"
                        ],
                        "priority": 1,
                        "passes": False,
                        "notes": ""
                    },
                    {
                        "id": "T-002",
                        "title": "Display password requirements",
                        "description": "Show password rules before user types",
                        "acceptanceCriteria": [
                            "Requirements visible on form load",
                            "Met requirements show checkmark"
                        ],
                        "priority": 2,
                        "passes": False,
                        "notes": ""
                    }
                ]
            }, indent=2),
        }
        
        return responses.get(role, responses["implementation"])
    
    def run(self) -> int:
        """Main entry point."""
        self.parse_args()
        
        # Check for timeout simulation
        if "SIMULATE_TIMEOUT" in self.prompt:
            import time
            time.sleep(3600)
            return 1
        
        response = self.generate_response()
        print(response)
        return 0


def main():
    cli = MockClaudeCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
```

### 3.4 Scenario Control

Tests control mock behavior via:

1. **Environment Variables**:
   ```bash
   MOCK_SCENARIO=invalid_token python -m pytest tests/integration/
   ```

2. **Prompt Directives** (embedded in test prompts):
   ```python
   prompt = """
   SESSION_TOKEN: ralph-20260125-143052-abc123
   Task: T-001
   
   <!-- SIMULATE_INVALID_TOKEN -->
   
   Implement the authentication service...
   """
   ```

3. **Response Override Files**:
   ```bash
   MOCK_RESPONSE_FILE=tests/fixtures/custom_response.txt ralph run ...
   ```

### 3.5 Signal Variations

The mock supports these signal variations for testing:

| Signal Type | Valid Example | Test Scenario |
|-------------|---------------|---------------|
| `task-done` | `<task-done session="ralph-...">` | Normal completion |
| `tests-done` | `<tests-done session="ralph-...">` | Test writing complete |
| `review-approved` | `<review-approved session="ralph-...">` | Review passes |
| `review-rejected` | `<review-rejected session="ralph-...">Issues...</review-rejected>` | Review fails |
| `fix-done` | `<fix-done session="ralph-...">` | Fix complete |
| Invalid token | `<task-done session="wrong-token">` | Token mismatch |
| Missing signal | Plain text response | No signal detected |

---

## 4. Fixture Repositories

### 4.1 Purpose

Fixture repos are minimal, self-contained project structures used for integration testing. Each fixture is designed to test specific scenarios.

### 4.2 Fixture Structure

```
tests/fixtures/
├── python_min/           # Minimal Python project
│   ├── pyproject.toml
│   ├── src/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── tests/
│   │   └── test_main.py
│   └── .ralph/
│       ├── ralph.yml
│       └── prd.json
│
├── node_min/             # Minimal Node.js project
│   ├── package.json
│   ├── src/
│   │   └── index.js
│   └── .ralph/
│       ├── ralph.yml
│       └── prd.json
│
├── fullstack_min/        # Minimal fullstack project
│   ├── pyproject.toml
│   ├── src/
│   │   └── api/
│   │       └── main.py
│   ├── frontend/
│   │   ├── package.json
│   │   └── src/
│   │       └── App.tsx
│   ├── tests/
│   │   └── test_api.py
│   └── .ralph/
│       ├── ralph.yml
│       └── prd.json
│
└── autopilot_min/        # Minimal autopilot scenario
    ├── pyproject.toml
    ├── src/
    │   └── main.py
    ├── reports/
    │   └── weekly-report.md
    └── .ralph/
        ├── ralph.yml
        └── prd.json
```

### 4.3 Python Minimal Fixture

```python
# tests/fixtures/python_min/pyproject.toml
[project]
name = "fixture-python-min"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# tests/fixtures/python_min/src/main.py
"""Minimal main module for testing."""

def hello() -> str:
    return "Hello, World!"

def add(a: int, b: int) -> int:
    return a + b
```

```python
# tests/fixtures/python_min/tests/test_main.py
"""Tests for main module."""
from src.main import hello, add

def test_hello():
    assert hello() == "Hello, World!"

def test_add():
    assert add(2, 3) == 5
```

```yaml
# tests/fixtures/python_min/.ralph/ralph.yml
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  build:
    - name: syntax
      cmd: "python -m py_compile src/main.py"
      when: pyproject.toml
      timeout_seconds: 30
      fatal: true

  full:
    - name: pytest
      cmd: "python -m pytest tests/ -x --tb=short"
      when: pyproject.toml
      timeout_seconds: 120
      fatal: true

test_paths:
  - tests/**

git:
  base_branch: main

limits:
  max_iterations: 5
  claude_timeout: 300
```

```json
// tests/fixtures/python_min/.ralph/prd.json
{
  "project": "Python Minimal Fixture",
  "branchName": "ralph/test-fixture",
  "description": "Test fixture for integration testing",
  "tasks": [
    {
      "id": "T-001",
      "title": "Add multiply function",
      "description": "Add a multiply function to the main module",
      "acceptanceCriteria": [
        "File `src/main.py` contains function `multiply`",
        "Run `python -c \"from src.main import multiply; assert multiply(3, 4) == 12\"` - exits with code 0"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    },
    {
      "id": "T-002",
      "title": "Add tests for multiply",
      "description": "Add unit tests for the multiply function",
      "acceptanceCriteria": [
        "File `tests/test_main.py` contains `test_multiply`",
        "Run `python -m pytest tests/test_main.py -v -k multiply` - exits with code 0"
      ],
      "priority": 2,
      "passes": false,
      "notes": ""
    }
  ]
}
```

### 4.4 Node Minimal Fixture

```json
// tests/fixtures/node_min/package.json
{
  "name": "fixture-node-min",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "test": "node --test src/*.test.js",
    "lint": "echo 'Lint placeholder'"
  }
}
```

```javascript
// tests/fixtures/node_min/src/index.js
export function hello() {
  return "Hello, World!";
}

export function add(a, b) {
  return a + b;
}
```

```yaml
# tests/fixtures/node_min/.ralph/ralph.yml
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  build:
    - name: syntax
      cmd: "node --check src/index.js"
      when: package.json
      timeout_seconds: 30
      fatal: true

  full:
    - name: test
      cmd: "npm test"
      when: package.json
      timeout_seconds: 120
      fatal: true

test_paths:
  - "**/*.test.js"
  - "**/*.spec.js"

git:
  base_branch: main

limits:
  max_iterations: 5
  claude_timeout: 300
```

### 4.5 Fullstack Minimal Fixture

```yaml
# tests/fixtures/fullstack_min/.ralph/ralph.yml
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

services:
  backend:
    start:
      dev: "python -m http.server {port}"
      prod: "python -m http.server {port}"
    port: 8000
    health:
      - /
    timeout: 10

  frontend:
    build: "echo 'Build placeholder'"
    serve:
      dev: "cd frontend && npm run dev -- --port {port}"
      prod: "cd frontend && npm run preview -- --port {port}"
    port: 5173
    timeout: 10

gates:
  build:
    - name: python-syntax
      cmd: "python -m py_compile src/api/main.py"
      when: pyproject.toml
      timeout_seconds: 30
      fatal: true

    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      when: frontend/package.json
      timeout_seconds: 60
      fatal: true

  full:
    - name: pytest
      cmd: "python -m pytest tests/ -x --tb=short"
      when: pyproject.toml
      timeout_seconds: 120
      fatal: true

test_paths:
  - tests/**
  - frontend/**/*.test.*
  - frontend/**/*.spec.*

git:
  base_branch: main

limits:
  max_iterations: 5
  claude_timeout: 300
```

### 4.6 Autopilot Minimal Fixture

```markdown
<!-- tests/fixtures/autopilot_min/reports/weekly-report.md -->
# Weekly Product Report - 2026-01-20

## Key Metrics
- Active Users: 1,234 (↑ 5%)
- Signups: 89 (↓ 12%)
- Error Rate: 0.3%

## Top Issues

### 1. Login Form Validation (High Priority)
Users report confusing error messages when entering invalid email formats.
Impact: 15% signup abandonment at this step.

### 2. Dark Mode Toggle (Medium Priority)  
Feature request with 47 upvotes.
Users want system preference detection.

### 3. Page Load Performance (Low Priority)
Dashboard takes 2.3s to load on mobile.
Target: Under 1.5s.

## Recommendations
Focus on login form UX improvements for maximum conversion impact.
```

```yaml
# tests/fixtures/autopilot_min/.ralph/ralph.yml
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  full:
    - name: syntax
      cmd: "python -m py_compile src/main.py"
      when: pyproject.toml
      timeout_seconds: 30
      fatal: true

test_paths:
  - tests/**

autopilot:
  enabled: true
  reports_dir: ./reports
  branch_prefix: ralph/
  create_pr: false  # Disabled for testing
  
  analysis:
    provider: anthropic
    recent_days: 7
  
  prd:
    mode: autonomous
    output_dir: ./tasks
  
  tasks:
    output: .ralph/prd.json
    min_count: 2
    max_count: 10

git:
  base_branch: main

limits:
  max_iterations: 5
  claude_timeout: 300
```

---

## 5. Unit Tests

### 5.1 Token Tests

```python
# tests/unit/test_token.py
"""Unit tests for session token generation and validation."""
import pytest
import re
from ralph.session.token import TokenGenerator


class TestTokenGenerator:
    """Tests for TokenGenerator class."""
    
    def test_generate_returns_string(self):
        """Token generation returns a string."""
        token = TokenGenerator.generate()
        assert isinstance(token, str)
    
    def test_generate_format(self):
        """Token matches expected format: ralph-YYYYMMDD-HHMMSS-[hex]."""
        token = TokenGenerator.generate()
        pattern = r'^ralph-\d{8}-\d{6}-[a-f0-9]{16}$'
        assert re.match(pattern, token), f"Token {token} doesn't match pattern"
    
    def test_generate_uniqueness(self):
        """Each call generates a unique token."""
        tokens = [TokenGenerator.generate() for _ in range(100)]
        assert len(tokens) == len(set(tokens)), "Duplicate tokens generated"
    
    def test_validate_correct_format(self):
        """Valid token format passes validation."""
        token = "ralph-20260125-143052-a1b2c3d4e5f6g7h8"
        assert TokenGenerator.validate(token) is True
    
    def test_validate_wrong_prefix(self):
        """Wrong prefix fails validation."""
        token = "other-20260125-143052-a1b2c3d4e5f6g7h8"
        assert TokenGenerator.validate(token) is False
    
    def test_validate_short_token(self):
        """Short token fails validation."""
        token = "ralph-20260125-143052-abc"
        assert TokenGenerator.validate(token) is False
    
    def test_validate_empty_string(self):
        """Empty string fails validation."""
        assert TokenGenerator.validate("") is False
    
    def test_validate_none(self):
        """None fails validation."""
        assert TokenGenerator.validate(None) is False
```

### 5.2 Checksum Tests

```python
# tests/unit/test_checksum.py
"""Unit tests for checksum computation and verification."""
import pytest
import tempfile
from pathlib import Path
from ralph.session.checksum import ChecksumManager


class TestChecksumManager:
    """Tests for ChecksumManager class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)
    
    @pytest.fixture
    def checksum_mgr(self, temp_dir):
        """Create ChecksumManager instance."""
        return ChecksumManager(temp_dir)
    
    def test_compute_returns_sha256_format(self, checksum_mgr, temp_dir):
        """Checksum has correct sha256: prefix format."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        
        checksum = checksum_mgr.compute(test_file)
        
        assert checksum.startswith("sha256:")
        assert len(checksum) == 7 + 64  # "sha256:" + 64 hex chars
    
    def test_compute_deterministic(self, checksum_mgr, temp_dir):
        """Same content produces same checksum."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        
        checksum1 = checksum_mgr.compute(test_file)
        checksum2 = checksum_mgr.compute(test_file)
        
        assert checksum1 == checksum2
    
    def test_compute_different_content(self, checksum_mgr, temp_dir):
        """Different content produces different checksum."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("hello")
        file2.write_text("world")
        
        assert checksum_mgr.compute(file1) != checksum_mgr.compute(file2)
    
    def test_store_creates_sha256_file(self, checksum_mgr, temp_dir):
        """store() creates .sha256 sidecar file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        
        checksum_mgr.store(test_file)
        
        sha_file = temp_dir / "test.sha256"
        assert sha_file.exists()
    
    def test_verify_returns_true_for_valid(self, checksum_mgr, temp_dir):
        """verify() returns True for unmodified file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        checksum_mgr.store(test_file)
        
        assert checksum_mgr.verify(test_file) is True
    
    def test_verify_returns_false_for_tampered(self, checksum_mgr, temp_dir):
        """verify() returns False for modified file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        checksum_mgr.store(test_file)
        
        # Modify file after storing checksum
        test_file.write_text("tampered content")
        
        assert checksum_mgr.verify(test_file) is False
    
    def test_verify_raises_on_missing_checksum(self, checksum_mgr, temp_dir):
        """verify() raises error when checksum file missing."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        # Don't store checksum
        
        with pytest.raises(Exception):  # ChecksumMissingError
            checksum_mgr.verify(test_file)
```

### 5.3 Signal Validation Tests

```python
# tests/unit/test_signals.py
"""Unit tests for agent signal validation."""
import pytest
from ralph.agents.signals import SignalValidator, SignalResult, SignalType


class TestSignalValidator:
    """Tests for SignalValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create validator with test token."""
        return SignalValidator("ralph-20260125-143052-a1b2c3d4e5f6g7h8")
    
    def test_validate_task_done_valid(self, validator):
        """Valid task-done signal returns VALID."""
        output = '''
        Implementation complete!
        
        <task-done session="ralph-20260125-143052-a1b2c3d4e5f6g7h8">
        Task T-001 is done.
        </task-done>
        '''
        
        result, task_id = validator.validate_task_done(output)
        
        assert result == SignalResult.VALID
        assert task_id == "T-001"
    
    def test_validate_task_done_invalid_token(self, validator):
        """Invalid token returns INVALID_TOKEN."""
        output = '''
        <task-done session="wrong-token">
        Task T-001 is done.
        </task-done>
        '''
        
        result, _ = validator.validate_task_done(output)
        
        assert result == SignalResult.INVALID_TOKEN
    
    def test_validate_task_done_no_signal(self, validator):
        """Missing signal returns NO_SIGNAL."""
        output = '''
        I've completed the implementation.
        The changes look good.
        '''
        
        result, _ = validator.validate_task_done(output)
        
        assert result == SignalResult.NO_SIGNAL
    
    def test_validate_review_approved(self, validator):
        """Valid review-approved signal returns VALID with APPROVED."""
        output = '''
        <review-approved session="ralph-20260125-143052-a1b2c3d4e5f6g7h8">
        Code looks good!
        </review-approved>
        '''
        
        result, status = validator.validate_review(output)
        
        assert result == SignalResult.VALID
        assert status == "APPROVED"
    
    def test_validate_review_rejected(self, validator):
        """Valid review-rejected signal returns VALID with rejection reason."""
        output = '''
        <review-rejected session="ralph-20260125-143052-a1b2c3d4e5f6g7h8">
        Missing error handling.
        </review-rejected>
        '''
        
        result, status = validator.validate_review(output)
        
        assert result == SignalResult.VALID
        assert "REJECTED" in status
        assert "error handling" in status
    
    def test_extract_task_id_from_content(self, validator):
        """Task ID extracted from signal content."""
        output = '''
        <task-done session="ralph-20260125-143052-a1b2c3d4e5f6g7h8">
        Task T-003: Add authentication - complete
        </task-done>
        '''
        
        _, task_id = validator.validate_task_done(output)
        
        assert task_id == "T-003"
```

### 5.4 Guardrails Tests

```python
# tests/unit/test_guardrails.py
"""Unit tests for test agent path guardrails."""
import pytest
from ralph.agents.guardrails import TestPathGuardrail


class TestTestPathGuardrail:
    """Tests for TestPathGuardrail class."""
    
    @pytest.fixture
    def guardrail(self):
        """Create guardrail with default patterns."""
        return TestPathGuardrail()
    
    def test_is_allowed_test_directory(self, guardrail):
        """Files in tests/ directory are allowed."""
        assert guardrail.is_allowed("tests/test_auth.py") is True
        assert guardrail.is_allowed("tests/unit/test_service.py") is True
    
    def test_is_allowed_test_suffix(self, guardrail):
        """Files with .test.* suffix are allowed."""
        assert guardrail.is_allowed("frontend/src/App.test.tsx") is True
        assert guardrail.is_allowed("frontend/components/Button.test.js") is True
    
    def test_is_allowed_spec_suffix(self, guardrail):
        """Files with .spec.* suffix are allowed."""
        assert guardrail.is_allowed("frontend/src/utils.spec.ts") is True
    
    def test_is_allowed_cypress_directory(self, guardrail):
        """Files in cypress/ directory are allowed."""
        assert guardrail.is_allowed("frontend/cypress/e2e/login.cy.ts") is True
    
    def test_is_not_allowed_source_files(self, guardrail):
        """Source files are not allowed."""
        assert guardrail.is_allowed("src/main.py") is False
        assert guardrail.is_allowed("src/auth/service.py") is False
        assert guardrail.is_allowed("frontend/src/App.tsx") is False
    
    def test_is_not_allowed_config_files(self, guardrail):
        """Configuration files are not allowed."""
        assert guardrail.is_allowed("pyproject.toml") is False
        assert guardrail.is_allowed("package.json") is False
        assert guardrail.is_allowed(".ralph/ralph.yml") is False
    
    def test_custom_patterns(self):
        """Custom patterns can be provided."""
        guardrail = TestPathGuardrail(patterns=["custom_tests/**"])
        
        assert guardrail.is_allowed("custom_tests/test_foo.py") is True
        assert guardrail.is_allowed("tests/test_bar.py") is False
    
    def test_find_violations(self, guardrail):
        """find_violations identifies non-test file changes."""
        before = {"src/main.py"}
        after = {"src/main.py", "src/auth.py", "tests/test_auth.py"}
        
        violations = guardrail.find_violations(before, after)
        
        assert "src/auth.py" in violations
        assert "tests/test_auth.py" not in violations
```

### 5.5 Task Parser Tests

```python
# tests/unit/test_parser.py
"""Unit tests for task parsing."""
import pytest
import json
import tempfile
from pathlib import Path
from ralph.tasks.parser import TaskParser, Task, TaskList


class TestTaskParser:
    """Tests for TaskParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create TaskParser instance."""
        return TaskParser()
    
    @pytest.fixture
    def sample_prd_json(self):
        """Sample prd.json content."""
        return {
            "project": "Test Project",
            "branchName": "ralph/test",
            "description": "Test description",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "First task",
                    "description": "Do the first thing",
                    "acceptanceCriteria": ["Criterion 1"],
                    "priority": 1,
                    "passes": False,
                    "notes": ""
                },
                {
                    "id": "T-002",
                    "title": "Second task",
                    "description": "Do the second thing",
                    "acceptanceCriteria": ["Criterion 2", "Criterion 3"],
                    "priority": 2,
                    "passes": False,
                    "notes": ""
                }
            ]
        }
    
    def test_parse_prd_json(self, parser, sample_prd_json):
        """Parse valid prd.json returns TaskList."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_prd_json, f)
            f.flush()
            
            task_list = parser.parse_prd_json(Path(f.name))
        
        assert task_list.project == "Test Project"
        assert len(task_list.tasks) == 2
        assert task_list.tasks[0].id == "T-001"
    
    def test_parse_prd_json_task_structure(self, parser, sample_prd_json):
        """Parsed tasks have correct structure."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_prd_json, f)
            f.flush()
            
            task_list = parser.parse_prd_json(Path(f.name))
        
        task = task_list.tasks[0]
        assert isinstance(task, Task)
        assert task.title == "First task"
        assert task.priority == 1
        assert task.passes is False
        assert len(task.acceptance_criteria) == 1
    
    def test_parse_prd_json_with_subtasks(self, parser):
        """Parse tasks with subtasks."""
        prd = {
            "project": "Test",
            "description": "Test",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Parent task",
                    "description": "Parent",
                    "acceptanceCriteria": ["Parent criterion"],
                    "priority": 1,
                    "passes": False,
                    "notes": "",
                    "subtasks": [
                        {
                            "id": "T-001.1",
                            "title": "Subtask 1",
                            "acceptanceCriteria": ["Sub criterion"],
                            "passes": False,
                            "notes": ""
                        }
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(prd, f)
            f.flush()
            
            task_list = parser.parse_prd_json(Path(f.name))
        
        assert len(task_list.tasks[0].subtasks) == 1
        assert task_list.tasks[0].subtasks[0].id == "T-001.1"
    
    def test_parse_missing_required_field(self, parser):
        """Parse fails on missing required field."""
        invalid_prd = {
            "project": "Test",
            # Missing "description"
            "tasks": []
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_prd, f)
            f.flush()
            
            with pytest.raises(Exception):  # ValidationError
                parser.parse_prd_json(Path(f.name))
```

---

## 6. Integration Tests

### 6.1 Task Advancement Test

```python
# tests/integration/test_task_loop.py
"""Integration tests for task advancement workflow."""
import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Set mock Claude before importing ralph
os.environ["RALPH_CLAUDE_CMD"] = "python tests/mock_claude/mock_claude.py"

from ralph.cli import run_command
from ralph.session import SessionManager
from ralph.tasks import TaskParser


class TestTaskAdvancement:
    """Test task advancement through the workflow."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy python_min fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "python_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        
        # Initialize git repo (required for some operations)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        
        return fixture_dst
    
    def test_task_advances_on_valid_signal(self, fixture_repo):
        """Task status advances when valid completion signal received."""
        os.chdir(fixture_repo)
        
        # Run ralph with max 1 iteration (just first task)
        result = run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Load task status
        parser = TaskParser()
        task_list = parser.parse_prd_json(fixture_repo / ".ralph/prd.json")
        
        # First task should be marked complete (mock returns valid signal)
        assert task_list.tasks[0].passes is True
    
    def test_multiple_tasks_advance_sequentially(self, fixture_repo):
        """Multiple tasks advance in priority order."""
        os.chdir(fixture_repo)
        
        # Run ralph for all tasks
        result = run_command(["run", "--prd-json", ".ralph/prd.json"])
        
        parser = TaskParser()
        task_list = parser.parse_prd_json(fixture_repo / ".ralph/prd.json")
        
        # All tasks should be complete
        for task in task_list.tasks:
            assert task.passes is True, f"Task {task.id} not completed"
    
    def test_session_artifacts_created(self, fixture_repo):
        """Session directory and artifacts are created."""
        os.chdir(fixture_repo)
        
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        session_dir = fixture_repo / ".ralph-session"
        
        assert session_dir.exists()
        assert (session_dir / "session.json").exists()
        assert (session_dir / "task-status.json").exists()
        assert (session_dir / "logs" / "timeline.jsonl").exists()
```

### 6.2 Invalid Signal Test

```python
# tests/integration/test_invalid_signals.py
"""Integration tests for signal rejection and retry."""
import pytest
import os
import shutil
from pathlib import Path

os.environ["RALPH_CLAUDE_CMD"] = "python tests/mock_claude/mock_claude.py"

from ralph.cli import run_command


class TestInvalidSignals:
    """Test handling of invalid completion signals."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "python_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_invalid_token_rejected(self, fixture_repo):
        """Invalid token in signal triggers rejection."""
        os.chdir(fixture_repo)
        
        # Add directive to prd.json to trigger invalid token response
        prd_file = fixture_repo / ".ralph/prd.json"
        content = prd_file.read_text()
        content = content.replace(
            '"title": "Add multiply function"',
            '"title": "Add multiply function SIMULATE_INVALID_TOKEN"'
        )
        prd_file.write_text(content)
        
        # Run should detect invalid token and retry
        result = run_command([
            "run", "--prd-json", ".ralph/prd.json",
            "--max-iterations", "2"
        ])
        
        # Check timeline for rejection event
        timeline = (fixture_repo / ".ralph-session/logs/timeline.jsonl").read_text()
        assert "invalid_token" in timeline.lower() or "rejected" in timeline.lower()
    
    def test_no_signal_triggers_retry(self, fixture_repo):
        """Missing signal triggers retry with feedback."""
        os.chdir(fixture_repo)
        
        # Modify task to trigger no-signal response
        prd_file = fixture_repo / ".ralph/prd.json"
        content = prd_file.read_text()
        content = content.replace(
            '"title": "Add multiply function"',
            '"title": "Add multiply function SIMULATE_NO_SIGNAL"'
        )
        prd_file.write_text(content)
        
        result = run_command([
            "run", "--prd-json", ".ralph/prd.json",
            "--max-iterations", "3"
        ])
        
        # Task should not advance (all iterations got no signal)
        from ralph.tasks import TaskParser
        parser = TaskParser()
        task_list = parser.parse_prd_json(fixture_repo / ".ralph/prd.json")
        
        assert task_list.tasks[0].passes is False
```

### 6.3 Tampering Detection Test

```python
# tests/integration/test_tampering.py
"""Integration tests for tamper detection."""
import pytest
import os
import json
import shutil
from pathlib import Path

os.environ["RALPH_CLAUDE_CMD"] = "python tests/mock_claude/mock_claude.py"

from ralph.cli import run_command
from ralph.session.checksum import ChecksumManager


class TestTamperDetection:
    """Test checksum-based tamper detection."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "python_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_checksum_created_on_session_start(self, fixture_repo):
        """Checksum file created when session starts."""
        os.chdir(fixture_repo)
        
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        checksum_file = fixture_repo / ".ralph-session/task-status.sha256"
        assert checksum_file.exists()
    
    def test_checksum_updated_on_task_complete(self, fixture_repo):
        """Checksum updated after task status change."""
        os.chdir(fixture_repo)
        
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Read checksum
        checksum_file = fixture_repo / ".ralph-session/task-status.sha256"
        checksum1 = checksum_file.read_text().strip()
        
        # Run another iteration
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        checksum2 = checksum_file.read_text().strip()
        
        # Checksum should change as task status updated
        assert checksum1 != checksum2
    
    def test_tampering_detected_aborts_session(self, fixture_repo):
        """Modifying task-status.json triggers abort."""
        os.chdir(fixture_repo)
        
        # Start a session
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Tamper with task-status.json
        status_file = fixture_repo / ".ralph-session/task-status.json"
        status = json.loads(status_file.read_text())
        status["tasks"]["T-002"] = {"passes": True}  # Fake completion
        status_file.write_text(json.dumps(status))
        
        # Next run should detect tampering
        with pytest.raises(SystemExit) as exc_info:
            run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        assert exc_info.value.code != 0  # Non-zero exit on tampering
```

### 6.4 Guardrails Test

```python
# tests/integration/test_guardrails.py
"""Integration tests for test-agent file guardrails."""
import pytest
import os
import shutil
from pathlib import Path

os.environ["RALPH_CLAUDE_CMD"] = "python tests/mock_claude/mock_claude.py"

from ralph.cli import run_command


class TestGuardrails:
    """Test test-agent path restrictions."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy fullstack fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "fullstack_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_test_files_allowed(self, fixture_repo):
        """Test agent can modify files in tests/ directory."""
        os.chdir(fixture_repo)
        
        # Create a task that triggers test writing
        prd_file = fixture_repo / ".ralph/prd.json"
        prd = json.loads(prd_file.read_text())
        prd["tasks"][0]["title"] = "Write tests"  # Triggers test_writing role
        prd_file.write_text(json.dumps(prd))
        
        result = run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Should succeed (test files are allowed)
        assert result == 0 or result is None
    
    def test_source_files_rejected(self, fixture_repo):
        """Test agent modifications to src/ are reverted."""
        os.chdir(fixture_repo)
        
        # Trigger guardrail violation scenario
        prd_file = fixture_repo / ".ralph/prd.json"
        prd = json.loads(prd_file.read_text())
        prd["tasks"][0]["title"] = "Write tests SIMULATE_GUARDRAIL_VIOLATION"
        prd_file.write_text(json.dumps(prd))
        
        # Track file before run
        src_file = fixture_repo / "src/api/main.py"
        original_content = src_file.read_text()
        
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # src file should not be modified (reverted)
        assert src_file.read_text() == original_content
```

### 6.5 Gates Ordering Test

```python
# tests/integration/test_gates.py
"""Integration tests for gate execution ordering."""
import pytest
import os
import json
import shutil
from pathlib import Path

os.environ["RALPH_CLAUDE_CMD"] = "python tests/mock_claude/mock_claude.py"

from ralph.cli import run_command


class TestGatesOrdering:
    """Test gate execution order and behavior."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy node fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "node_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_build_gates_run_first(self, fixture_repo):
        """Build gates execute before full gates."""
        os.chdir(fixture_repo)
        
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Check timeline for gate order
        timeline = (fixture_repo / ".ralph-session/logs/timeline.jsonl").read_text()
        lines = timeline.strip().split("\n")
        
        # Find gate events
        gate_events = [json.loads(l) for l in lines if "gate" in l.lower()]
        
        # Build gates should appear before full gates
        build_gate_idx = next((i for i, e in enumerate(gate_events) if "syntax" in e.get("gate", "")), -1)
        full_gate_idx = next((i for i, e in enumerate(gate_events) if "test" in e.get("gate", "")), -1)
        
        assert build_gate_idx < full_gate_idx, "Build gates should run before full gates"
    
    def test_fatal_gate_stops_execution(self, fixture_repo):
        """Fatal gate failure stops further gate execution."""
        os.chdir(fixture_repo)
        
        # Configure a failing gate
        config_file = fixture_repo / ".ralph/ralph.yml"
        config = config_file.read_text()
        config = config.replace(
            'cmd: "node --check src/index.js"',
            'cmd: "false"'  # Always fails
        )
        config_file.write_text(config)
        
        run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Check timeline - should show gate failure
        timeline = (fixture_repo / ".ralph-session/logs/timeline.jsonl").read_text()
        assert "gate_fail" in timeline
    
    def test_non_fatal_gate_continues(self, fixture_repo):
        """Non-fatal gate failure allows continuation."""
        os.chdir(fixture_repo)
        
        # Add a non-fatal gate
        config_file = fixture_repo / ".ralph/ralph.yml"
        config = config_file.read_text()
        config = config.replace(
            "fatal: true",
            "fatal: false",
            1  # Only first occurrence
        )
        config_file.write_text(config)
        
        result = run_command(["run", "--prd-json", ".ralph/prd.json", "--max-iterations", "1"])
        
        # Should complete despite gate warning
        timeline = (fixture_repo / ".ralph-session/logs/timeline.jsonl").read_text()
        assert "task_complete" in timeline or "session_end" in timeline
```

---

## 7. Autopilot Contract Tests

### 7.1 Analysis Output Test

```python
# tests/integration/test_autopilot.py
"""Integration tests for autopilot pipeline."""
import pytest
import os
import json
import shutil
from pathlib import Path

os.environ["RALPH_CLAUDE_CMD"] = "python tests/mock_claude/mock_claude.py"

from ralph.cli import run_command


class TestAutopilotAnalysis:
    """Test autopilot analysis phase."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy autopilot fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "autopilot_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_analysis_json_created(self, fixture_repo):
        """Autopilot creates analysis.json."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--dry-run"])
        
        analysis_file = fixture_repo / ".ralph/autopilot/analysis.json"
        assert analysis_file.exists()
    
    def test_analysis_json_schema(self, fixture_repo):
        """Analysis output matches expected schema."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--dry-run"])
        
        analysis_file = fixture_repo / ".ralph/autopilot/analysis.json"
        analysis = json.loads(analysis_file.read_text())
        
        # Required fields
        assert "priority_item" in analysis
        assert "description" in analysis
        assert "rationale" in analysis
        assert "acceptance_criteria" in analysis
        assert "branch_name" in analysis
        
        # Type validation
        assert isinstance(analysis["priority_item"], str)
        assert isinstance(analysis["acceptance_criteria"], list)
        assert len(analysis["acceptance_criteria"]) >= 1
    
    def test_branch_name_format(self, fixture_repo):
        """Branch name has correct prefix."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--dry-run"])
        
        analysis_file = fixture_repo / ".ralph/autopilot/analysis.json"
        analysis = json.loads(analysis_file.read_text())
        
        assert analysis["branch_name"].startswith("ralph/")


class TestAutopilotTaskGeneration:
    """Test autopilot task generation phase."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy autopilot fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "autopilot_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_prd_json_created(self, fixture_repo):
        """Autopilot creates prd.json with tasks."""
        os.chdir(fixture_repo)
        os.environ["MOCK_SCENARIO"] = "default"
        
        # Run full autopilot (not dry-run)
        run_command(["autopilot", "--reports", "./reports", "--no-create-pr"])
        
        prd_file = fixture_repo / ".ralph/prd.json"
        assert prd_file.exists()
        
        prd = json.loads(prd_file.read_text())
        assert "tasks" in prd
        assert len(prd["tasks"]) >= 2
    
    def test_tasks_schema_valid(self, fixture_repo):
        """Generated tasks match prd.json schema."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--no-create-pr"])
        
        prd_file = fixture_repo / ".ralph/prd.json"
        prd = json.loads(prd_file.read_text())
        
        for task in prd["tasks"]:
            assert "id" in task
            assert "title" in task
            assert "acceptanceCriteria" in task
            assert "priority" in task
            assert "passes" in task
            
            # ID format
            assert task["id"].startswith("T-")
            
            # Initial state
            assert task["passes"] is False
    
    def test_task_count_within_bounds(self, fixture_repo):
        """Task count within configured bounds."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--no-create-pr"])
        
        # Read config for bounds
        config_file = fixture_repo / ".ralph/ralph.yml"
        import yaml
        config = yaml.safe_load(config_file.read_text())
        min_count = config["autopilot"]["tasks"]["min_count"]
        max_count = config["autopilot"]["tasks"]["max_count"]
        
        prd_file = fixture_repo / ".ralph/prd.json"
        prd = json.loads(prd_file.read_text())
        
        assert min_count <= len(prd["tasks"]) <= max_count


class TestAutopilotRunState:
    """Test autopilot run state persistence."""
    
    @pytest.fixture
    def fixture_repo(self, tmp_path):
        """Copy autopilot fixture to temp directory."""
        fixture_src = Path(__file__).parent.parent / "fixtures" / "autopilot_min"
        fixture_dst = tmp_path / "repo"
        shutil.copytree(fixture_src, fixture_dst)
        os.system(f"cd {fixture_dst} && git init && git add . && git commit -m 'Initial'")
        return fixture_dst
    
    def test_run_state_created(self, fixture_repo):
        """Run state file created during autopilot."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--no-create-pr"])
        
        runs_dir = fixture_repo / ".ralph/autopilot/runs"
        assert runs_dir.exists()
        
        run_files = list(runs_dir.glob("*.json"))
        assert len(run_files) >= 1
    
    def test_run_state_schema(self, fixture_repo):
        """Run state matches expected schema."""
        os.chdir(fixture_repo)
        
        run_command(["autopilot", "--reports", "./reports", "--no-create-pr"])
        
        runs_dir = fixture_repo / ".ralph/autopilot/runs"
        run_file = list(runs_dir.glob("*.json"))[0]
        run_state = json.loads(run_file.read_text())
        
        # Required fields
        assert "run_id" in run_state
        assert "started_at" in run_state
        assert "status" in run_state
```

---

## 8. Test Infrastructure

### 8.1 pytest Configuration

```ini
# tests/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Markers
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (mock Claude + fixtures)
    slow: Tests that take longer than 10 seconds
    autopilot: Autopilot-specific tests

# Default options
addopts = -v --tb=short

# Timeout per test (integration tests may take longer)
timeout = 60
timeout_method = thread
```

### 8.2 Conftest Fixtures

```python
# tests/conftest.py
"""Shared test fixtures."""
import os
import pytest
import tempfile
from pathlib import Path

# Set mock Claude globally
os.environ.setdefault("RALPH_CLAUDE_CMD", "python tests/mock_claude/mock_claude.py")


@pytest.fixture(scope="session")
def mock_claude_path():
    """Path to mock Claude executable."""
    return Path(__file__).parent / "mock_claude" / "mock_claude.py"


@pytest.fixture
def temp_dir():
    """Create temporary directory for test."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def fixture_python_min(tmp_path):
    """Copy python_min fixture to temp directory."""
    import shutil
    src = Path(__file__).parent / "fixtures" / "python_min"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    os.system(f"cd {dst} && git init && git add . && git commit -m 'Initial'")
    return dst


@pytest.fixture
def fixture_node_min(tmp_path):
    """Copy node_min fixture to temp directory."""
    import shutil
    src = Path(__file__).parent / "fixtures" / "node_min"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    os.system(f"cd {dst} && git init && git add . && git commit -m 'Initial'")
    return dst


@pytest.fixture
def fixture_fullstack_min(tmp_path):
    """Copy fullstack_min fixture to temp directory."""
    import shutil
    src = Path(__file__).parent / "fixtures" / "fullstack_min"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    os.system(f"cd {dst} && git init && git add . && git commit -m 'Initial'")
    return dst


@pytest.fixture
def fixture_autopilot_min(tmp_path):
    """Copy autopilot_min fixture to temp directory."""
    import shutil
    src = Path(__file__).parent / "fixtures" / "autopilot_min"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    os.system(f"cd {dst} && git init && git add . && git commit -m 'Initial'")
    return dst
```

### 8.3 Test Running

```bash
# Run all tests
pytest

# Run unit tests only
pytest -m unit

# Run integration tests only
pytest -m integration

# Run with coverage
pytest --cov=ralph --cov-report=html

# Run specific test file
pytest tests/unit/test_token.py

# Run with verbose output
pytest -v --tb=long

# Run autopilot tests only
pytest -m autopilot
```

---

## 9. CI/CD Integration

### 9.1 GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run unit tests
        run: |
          pytest -m unit -v --tb=short
  
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Set up Node.js (for node fixtures)
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Run integration tests
        run: |
          pytest -m integration -v --tb=short
        env:
          RALPH_CLAUDE_CMD: python tests/mock_claude/mock_claude.py
  
  coverage:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run with coverage
        run: |
          pytest --cov=ralph --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

### 9.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: unit-tests
        name: Unit Tests
        entry: pytest -m unit -x --tb=line
        language: system
        pass_filenames: false
        always_run: true
```

---

## 10. Manual Integration Testing

### 10.1 Purpose

For final validation before major releases, run end-to-end tests with real Claude API.

### 10.2 Prerequisites

- Claude CLI installed and authenticated
- GitHub CLI (`gh`) for PR tests
- Test repository with minimal project

### 10.3 Manual Test Checklist

```markdown
# Ralph Manual Integration Test

## Environment
- [ ] Claude CLI version: _____
- [ ] Python version: _____
- [ ] Test repo: _____

## Task Loop Tests

### T1: Basic Task Completion
- [ ] Run: `ralph run --prd-json .ralph/prd.json --max-iterations 1`
- [ ] Verify: First task marked complete
- [ ] Verify: session.json created with valid token
- [ ] Verify: timeline.jsonl has events

### T2: Full Task List
- [ ] Run: `ralph run --prd-json .ralph/prd.json`
- [ ] Verify: All tasks complete
- [ ] Verify: Gates passed

### T3: Review Rejection Recovery
- [ ] Create task that fails review
- [ ] Verify: Retry with feedback
- [ ] Verify: Eventually passes

## Verification Tests

### V1: Runtime Health
- [ ] Run: `ralph verify`
- [ ] Verify: Backend starts and healthy
- [ ] Verify: Frontend builds and serves

### V2: UI Tests (if configured)
- [ ] Verify: Agent-browser tests run
- [ ] Verify: Screenshots captured

## Autopilot Tests

### A1: Analysis
- [ ] Run: `ralph autopilot --dry-run`
- [ ] Verify: analysis.json created
- [ ] Verify: Priority item reasonable

### A2: Full Pipeline
- [ ] Run: `ralph autopilot --no-create-pr`
- [ ] Verify: PRD generated
- [ ] Verify: Tasks generated
- [ ] Verify: Tasks executed

### A3: PR Creation
- [ ] Run: `ralph autopilot --create-pr`
- [ ] Verify: PR created on GitHub
- [ ] Verify: PR has correct title/body

## Notes
_____
```

### 10.4 Test Data Generation

For consistent manual testing:

```bash
# Generate a sample report
cat > reports/test-report.md << 'EOF'
# Test Report - Manual Testing

## Issue: Login Validation
The login form accepts invalid email formats.
Priority: High
Impact: User friction

## Issue: Missing Loading State
Submit button has no loading indicator.
Priority: Medium
EOF

# Generate a sample prd.json
ralph import --cr changes/test-cr.md
```

---

## Appendix A: Mock Claude Response Templates

### A.1 Implementation Response

```
I've implemented the requested changes.

Changes made:
- Created {files} with {feature}
- Added {tests} for verification
- Updated configuration

{acceptance_criteria_verification}

<task-done session="{session_token}">
Task {task_id} implementation complete.
{summary}
</task-done>
```

### A.2 Review Response (Approved)

```
Code review completed.

Checklist:
✓ Implementation matches acceptance criteria
✓ Tests cover happy path and edge cases
✓ Code follows project conventions
✓ No security vulnerabilities

<review-approved session="{session_token}">
Task {task_id} approved.
</review-approved>
```

### A.3 Review Response (Rejected)

```
Code review completed with issues.

Issues found:
- {issue_1}
- {issue_2}

<review-rejected session="{session_token}">
Please address these issues:
{detailed_issues}
</review-rejected>
```

---

*End of Testing Strategy Specification*
