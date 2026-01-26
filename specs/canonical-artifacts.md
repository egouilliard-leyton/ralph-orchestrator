# Ralph Orchestrator: Canonical Artifacts Specification

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Canonical Reference

This document defines the canonical artifacts, file formats, conventions, and schemas used by the Ralph orchestrator. All implementations must conform to these specifications.

> **Related Documents:**
> - [CLI Contract](./cli-contract.md) - Complete CLI command reference
> - [Design Decisions](./design-decisions.md) - Rationale behind key decisions
> - [Markdown Import/Export](./markdown-import-export.md) - CR/PRD markdown compatibility
> - [JSON Schemas](../schemas/) - Machine-validatable schemas for all artifacts

---

## Table of Contents

1. [Overview](#1-overview)
2. [`.ralph/ralph.yml` - Configuration](#2-ralphralphyml---configuration)
3. [`.ralph/prd.json` - Task List](#3-ralphprdjson---task-list)
4. [`.ralph-session/` - Session Logs](#4-ralph-session---session-logs)
5. [`AGENTS.md` - Agent Memory](#5-agentsmd---agent-memory)
6. [`progress.txt` - Progress Log](#6-progresstxt---progress-log)
7. [Directory Structure Summary](#7-directory-structure-summary)
8. [Validation Rules](#8-validation-rules)
9. [Migration Guide](#9-migration-guide)
10. [Autopilot Artifacts](#10-autopilot-artifacts)

**Quick Reference:** See [artifacts-quick-reference.md](../docs/artifacts-quick-reference.md) for a condensed reference card.

---

## 1. Overview

Ralph uses a layered artifact system:

| Layer | Location | Purpose | Lifetime |
|-------|----------|---------|----------|
| **Config** | `.ralph/ralph.yml` | Repo-specific settings | Permanent |
| **Tasks** | `.ralph/prd.json` | Executable task list | Per feature/CR |
| **Session** | `.ralph-session/` | Run-specific logs & state | Per run |
| **Memory** | `AGENTS.md`, `progress.txt` | Cross-run learnings | Persistent |

### Key Principles

1. **Script-controlled state**: Only the orchestrator script modifies task status and checksums
2. **Tokenized signals**: Agents signal completion using session-validated tokens
3. **Append-only memory**: Progress and learnings accumulate, never overwrite
4. **JSON-first tasks**: Machine-readable task format with optional markdown compat

---

## 2. `.ralph/ralph.yml` - Configuration

### 2.1 Purpose

The configuration file captures all repo-specific settings that were previously hard-coded. It enables the same orchestrator to work across Python, Node, fullstack, or any other project type.

### 2.2 Location

```
<repo-root>/.ralph/ralph.yml
```

### 2.3 Schema

```yaml
# ============================================================
# RALPH CONFIGURATION FILE
# Version: 1
# ============================================================

version: "1"  # Required. Schema version.

# ============================================================
# TASK SOURCE
# ============================================================
# Defines where tasks are read from and their format.

task_source:
  # Type of task source
  # - prd_json: Standalone JSON file (recommended)
  # - cr_markdown: JSON block embedded in markdown
  type: prd_json  # Required. Enum: prd_json | cr_markdown

  # Path to task file(s)
  # For prd_json: exact path
  # For cr_markdown: glob pattern allowed
  path: .ralph/prd.json  # Required.

# ============================================================
# SERVICES (optional)
# ============================================================
# Define services for runtime verification. Omit if not needed.

services:
  backend:
    # Commands to start the service
    start:
      dev: "uv run uvicorn src.api.main:app --reload --port {port}"
      prod: "uv run uvicorn src.api.main:app --port {port}"
    
    # Port the service runs on
    port: 8000
    
    # Health check endpoints (relative URLs)
    health:
      - /health
      - /api/system/health
    
    # Timeout in seconds for health check
    timeout: 30

  frontend:
    # Build command (run before serve in prod mode)
    build: "cd frontend && npm run build"
    
    # Commands to serve the frontend
    serve:
      dev: "cd frontend && npm run dev -- --port {port}"
      prod: "cd frontend && npm run preview -- --port {port}"
    
    port: 5173
    timeout: 30

# ============================================================
# GATES
# ============================================================
# Quality gates to run at various phases.
# Each gate has: name, cmd, when (condition), timeout_seconds, fatal

gates:
  # Build gates: fast checks run during task loop
  build:
    - name: mypy
      cmd: "uv run mypy src/ --ignore-missing-imports --no-error-summary"
      when: pyproject.toml  # Run if file exists
      timeout_seconds: 120
      fatal: true  # Stop on failure

    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      when: frontend/package.json
      timeout_seconds: 120
      fatal: true

  # Full gates: comprehensive checks run after task completion
  full:
    - name: pytest
      cmd: "uv run pytest -x --tb=short -q"
      when: pyproject.toml
      timeout_seconds: 300
      fatal: true

    - name: lint
      cmd: "cd frontend && npm run lint"
      when: frontend/package.json
      timeout_seconds: 120
      fatal: false  # Warning only

    - name: build
      cmd: "cd frontend && npm run build"
      when: frontend/package.json
      timeout_seconds: 300
      fatal: true

# ============================================================
# TEST PATH GUARDRAILS
# ============================================================
# Glob patterns for allowed test file paths.
# Test-writing agent can only modify files matching these patterns.

test_paths:
  - tests/**
  - test_scripts/**
  - frontend/**/__tests__/**
  - frontend/**/*.test.*
  - frontend/**/*.spec.*
  - frontend/**/cypress/**
  - frontend/**/playwright/**
  - frontend/**/e2e/**

# ============================================================
# UI VERIFICATION (optional)
# ============================================================
# UI testing configuration for post-completion verification.

ui:
  agent_browser:
    enabled: true
    # Path to test script OR inline test definitions
    script: ui_tests/agent-browser/smoke_test.sh
    # Alternative: inline tests
    # tests:
    #   - name: app_loads
    #     action: open
    #     expected: "navigation|header|sidebar"
    #   - name: dashboard
    #     action: click_tab("Dashboard")
    #     expected: "Dashboard heading"

  robot:
    enabled: true
    suite: ui_tests/robot
    variables:
      HEADLESS: "true"
      BROWSER: chromium
      TIMEOUT: 30s

# ============================================================
# AGENT CONFIGURATION
# ============================================================
# Model and tool configuration for each agent role.

agents:
  implementation:
    model: claude-opus-4-5-20251101
    timeout: 1800
    # allowed_tools: []  # Empty = all tools

  test_writing:
    model: claude-sonnet-4-5-20250929
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - Edit
      - Write
      - LS

  review:
    model: haiku
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - LS

  fix:
    model: claude-sonnet-4-5-20250929
    timeout: 1800

  planning:
    model: claude-sonnet-4-5-20250929
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - LS

# ============================================================
# LIMITS
# ============================================================
# Iteration and timeout limits.

limits:
  claude_timeout: 1800          # Default timeout per Claude call (seconds)
  max_iterations: 30            # Max task loop iterations
  post_verify_iterations: 10    # Max runtime fix iterations
  ui_fix_iterations: 10         # Max agent-browser fix iterations
  robot_fix_iterations: 10      # Max Robot Framework fix iterations

# ============================================================
# AUTOPILOT (optional, Compound-style)
# ============================================================
# Settings for automated self-improvement mode.

autopilot:
  enabled: true
  
  # Where to find analysis reports
  reports_dir: ./reports
  
  # Branch naming
  branch_prefix: ralph/
  
  # PR creation (requires gh CLI)
  create_pr: true
  
  # Analysis settings
  analysis:
    provider: anthropic  # anthropic | openai | openrouter | gateway
    model: claude-opus-4-5-20251101
    recent_days: 7  # Exclude items fixed in last N days
  
  # PRD generation settings
  prd:
    mode: autonomous  # autonomous | interactive
    output_dir: ./tasks
  
  # Task generation settings
  tasks:
    output: .ralph/prd.json
    min_count: 8
    max_count: 15
  
  # Memory settings
  memory:
    progress: .ralph/progress.txt
    archive: .ralph/archive

# ============================================================
# GIT / PR SETTINGS
# ============================================================

git:
  base_branch: main
  remote: origin

pr:
  enabled: true
  title_template: "Ralph: {priority_item}"
  body_template: |
    ## Summary
    {description}

    ## Rationale
    {rationale}

    ## Tasks Completed
    {task_summary}
```

### 2.4 Minimal Configuration

For simple projects, only these fields are required:

```yaml
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  full:
    - name: test
      cmd: "npm test"
      when: package.json
      fatal: true

git:
  base_branch: main
```

### 2.5 Stack-Specific Templates

Ralph provides starter templates for common stacks:

| Template | Detected By | Includes |
|----------|-------------|----------|
| `python` | `pyproject.toml` | pytest, mypy gates |
| `node` | `package.json` | npm test, lint, build gates |
| `fullstack` | Both | All gates + services + UI tests |

---

## 3. `.ralph/prd.json` - Task List

### 3.1 Purpose

The canonical, machine-readable task list. Adopted from Compound Product for compatibility and structure.

### 3.2 Location

```
<repo-root>/.ralph/prd.json
```

### 3.3 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Ralph PRD Schema",
  "type": "object",
  "required": ["project", "description", "tasks"],
  "properties": {
    "project": {
      "type": "string",
      "description": "Project or feature name"
    },
    "branchName": {
      "type": "string",
      "pattern": "^[a-z0-9/-]+$",
      "description": "Git branch name (kebab-case)"
    },
    "description": {
      "type": "string",
      "description": "One-line description of the work"
    },
    "tasks": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "#/definitions/Task"
      }
    }
  },
  "definitions": {
    "Task": {
      "type": "object",
      "required": ["id", "title", "description", "acceptanceCriteria", "priority", "passes"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^T-[0-9]{3}$",
          "description": "Stable task identifier (T-001, T-002, etc.)"
        },
        "title": {
          "type": "string",
          "maxLength": 100,
          "description": "Short, action-oriented title"
        },
        "description": {
          "type": "string",
          "description": "What to do and why"
        },
        "acceptanceCriteria": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string"
          },
          "description": "Boolean/verifiable criteria"
        },
        "priority": {
          "type": "integer",
          "minimum": 1,
          "description": "Execution order (lower = earlier)"
        },
        "passes": {
          "type": "boolean",
          "description": "Completion status (script-controlled)"
        },
        "notes": {
          "type": "string",
          "default": "",
          "description": "Evidence, links, or context"
        },
        "subtasks": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/Subtask"
          },
          "description": "Optional subtask breakdown"
        }
      }
    },
    "Subtask": {
      "type": "object",
      "required": ["id", "title", "acceptanceCriteria", "passes"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^T-[0-9]{3}\\.[0-9]+$",
          "description": "Subtask ID (T-001.1, T-001.2, etc.)"
        },
        "title": {
          "type": "string"
        },
        "acceptanceCriteria": {
          "type": "array",
          "items": { "type": "string" }
        },
        "passes": {
          "type": "boolean"
        },
        "notes": {
          "type": "string",
          "default": ""
        }
      }
    }
  }
}
```

### 3.4 Example

```json
{
  "project": "User Authentication",
  "branchName": "ralph/add-user-auth",
  "description": "Implement JWT-based user authentication with login/logout",
  "tasks": [
    {
      "id": "T-001",
      "title": "Add JWT dependency and configuration",
      "description": "Install PyJWT package and add auth configuration to settings",
      "acceptanceCriteria": [
        "PyJWT listed in pyproject.toml dependencies",
        "JWT_SECRET_KEY and JWT_EXPIRATION in config",
        "Run `uv run python -c \"import jwt\"` - exits with code 0"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    },
    {
      "id": "T-002",
      "title": "Create auth service with token generation",
      "description": "Implement AuthService class with create_token and verify_token methods",
      "acceptanceCriteria": [
        "File `src/services/auth.py` exists",
        "AuthService.create_token() returns valid JWT",
        "AuthService.verify_token() validates and decodes JWT",
        "Run `uv run pytest tests/test_auth.py -v` - exits with code 0"
      ],
      "priority": 2,
      "passes": false,
      "notes": "",
      "subtasks": [
        {
          "id": "T-002.1",
          "title": "Implement create_token",
          "acceptanceCriteria": ["Token contains user_id and exp claims"],
          "passes": false,
          "notes": ""
        },
        {
          "id": "T-002.2",
          "title": "Implement verify_token",
          "acceptanceCriteria": ["Returns user_id on valid token", "Raises exception on invalid/expired"],
          "passes": false,
          "notes": ""
        }
      ]
    },
    {
      "id": "T-003",
      "title": "Add login endpoint",
      "description": "Create POST /api/auth/login endpoint that validates credentials and returns JWT",
      "acceptanceCriteria": [
        "POST /api/auth/login accepts {email, password}",
        "Returns 200 with {token} on valid credentials",
        "Returns 401 on invalid credentials",
        "Run `uv run pytest tests/test_auth_api.py -v` - exits with code 0"
      ],
      "priority": 3,
      "passes": false,
      "notes": ""
    }
  ]
}
```

### 3.5 Acceptance Criteria Patterns

Use these verifiable patterns:

| Type | Pattern | Example |
|------|---------|---------|
| **Command** | `Run \`[cmd]\` - exits with code 0` | `Run \`npm test\` - exits with code 0` |
| **File exists** | `File \`[path]\` exists` | `File \`src/auth.py\` exists` |
| **File contains** | `File \`[path]\` contains \`[string]\`` | `File \`config.py\` contains \`JWT_SECRET\`` |
| **API check** | `[METHOD] [url] returns [status]` | `POST /api/login returns 200` |
| **Browser nav** | `agent-browser: open \`[url]\` - [result]` | `agent-browser: open /login - form renders` |
| **Browser action** | `agent-browser: click \`[el]\` - [result]` | `agent-browser: click "Submit" - redirects` |
| **Console check** | `agent-browser: console shows no errors` | - |

### 3.6 Task Status Rules

1. **Initial state**: All tasks start with `passes: false`
2. **Script-only updates**: Only the orchestrator script sets `passes: true`
3. **Subtask aggregation**: If subtasks exist, parent passes only when all subtasks pass
4. **Notes for evidence**: Agents should populate `notes` with verification evidence

### 3.7 CR Markdown Compatibility (Import/Export)

Ralph supports importing tasks from Change Request (CR) markdown files and exporting `prd.json` back to markdown format.

#### Supported Formats

| Format | File Pattern | Use Case |
|--------|--------------|----------|
| **prd.json** | `.ralph/prd.json` | Primary execution format |
| **CR Markdown** | `changes/CR-*.md` | Human authoring, code review |
| **PRD Markdown** | `tasks/prd-*.md` | Documentation, sharing |

#### Import: CR Markdown → prd.json

```bash
ralph import --cr changes/CR-FEATURE.md
```

**Transformation:**

| CR Field | prd.json Field |
|----------|----------------|
| `id` (e.g., CR-FEAT-1) | `id` (normalized to T-001) |
| `description` | `title` + `description` |
| `steps[]` | `acceptanceCriteria[]` |
| `category` | Preserved in `notes` |
| `passes` | `passes` |
| (array position) | `priority` |

#### Export: prd.json → Markdown

```bash
ralph export --format cr --output changes/CR-EXPORT.md
```

> **Full specification:** See [Markdown Import/Export](./markdown-import-export.md) for complete details, examples, and CLI options.

---

## 4. `.ralph-session/` - Session Logs

### 4.1 Purpose

Transient, run-specific state and logs. Created fresh for each `ralph run` invocation.

### 4.2 Location

```
<repo-root>/.ralph-session/
```

### 4.3 Directory Structure

```
.ralph-session/
├── session.json              # Session metadata
├── task-status.json          # Task status with checksum
├── task-status.sha256        # Tamper-detection checksum
├── logs/
│   ├── timeline.jsonl        # Event log (JSON Lines)
│   ├── impl-T-001.log        # Implementation agent output
│   ├── test-T-001.log        # Test-writing agent output
│   ├── review-T-001.log      # Review agent output
│   └── gates-T-001.log       # Gate execution output
├── artifacts/
│   ├── screenshots/          # UI test screenshots
│   │   ├── 001-app-load.png
│   │   └── 002-dashboard.png
│   ├── snapshots/            # Accessibility snapshots
│   │   └── 001-app-load.txt
│   └── robot/                # Robot Framework outputs
│       ├── output.xml
│       ├── log.html
│       └── report.html
└── pids/
    ├── backend.pid           # Backend process ID
    └── frontend.pid          # Frontend process ID
```

### 4.4 `session.json` Schema

```json
{
  "session_id": "20260125-143052-a7b3c9",
  "session_token": "ralph-20260125-143052-a7b3c9f2d1e8",
  "started_at": "2026-01-25T14:30:52Z",
  "task_source": ".ralph/prd.json",
  "task_source_type": "prd_json",
  "config_path": ".ralph/ralph.yml",
  "git_branch": "ralph/add-user-auth",
  "git_commit": "abc123f",
  "status": "running",
  "current_task": "T-002",
  "completed_tasks": ["T-001"],
  "pending_tasks": ["T-002", "T-003"]
}
```

### 4.5 `task-status.json` Schema

```json
{
  "checksum": "sha256:a1b2c3d4e5f6...",
  "last_updated": "2026-01-25T14:45:00Z",
  "tasks": {
    "T-001": {
      "passes": true,
      "completed_at": "2026-01-25T14:40:00Z",
      "iterations": 1
    },
    "T-002": {
      "passes": false,
      "started_at": "2026-01-25T14:42:00Z",
      "iterations": 2,
      "last_failure": "Review rejected: missing error handling"
    },
    "T-003": {
      "passes": false
    }
  }
}
```

### 4.6 `timeline.jsonl` Format

JSON Lines format for event logging:

```jsonl
{"ts":"2026-01-25T14:30:52Z","event":"session_start","session_id":"20260125-143052-a7b3c9"}
{"ts":"2026-01-25T14:31:00Z","event":"task_start","task_id":"T-001"}
{"ts":"2026-01-25T14:35:00Z","event":"agent_complete","role":"implementation","task_id":"T-001","signal":"task-done"}
{"ts":"2026-01-25T14:36:00Z","event":"agent_complete","role":"test_writing","task_id":"T-001","signal":"tests-done"}
{"ts":"2026-01-25T14:37:00Z","event":"gates_run","gate":"pytest","status":"pass","duration_ms":4532}
{"ts":"2026-01-25T14:38:00Z","event":"agent_complete","role":"review","task_id":"T-001","signal":"review-approved"}
{"ts":"2026-01-25T14:38:05Z","event":"task_complete","task_id":"T-001"}
{"ts":"2026-01-25T14:38:10Z","event":"task_start","task_id":"T-002"}
```

### 4.7 Checksum Mechanism

The checksum prevents agents from modifying task status directly:

1. After any task status change, script computes: `sha256(task-status.json)`
2. Stores result in `task-status.sha256`
3. Before reading status, script verifies checksum matches
4. If mismatch detected, abort run with tampering warning

```bash
# Compute checksum
sha256sum .ralph-session/task-status.json | cut -d' ' -f1 > .ralph-session/task-status.sha256

# Verify checksum
expected=$(cat .ralph-session/task-status.sha256)
actual=$(sha256sum .ralph-session/task-status.json | cut -d' ' -f1)
[ "$expected" = "$actual" ] || echo "TAMPERING DETECTED"
```

---

## 5. `AGENTS.md` - Agent Memory

### 5.1 Purpose

Persistent memory file that captures codebase patterns, conventions, and learnings discovered during automation runs. Agents read this at the start of each iteration to benefit from prior context.

### 5.2 Location

```
<repo-root>/AGENTS.md
```

### 5.3 Template

```markdown
# AGENTS.md

> This file captures codebase patterns and conventions discovered during automated development.
> AI agents read this file to understand project-specific context.
> Updates are made by automation runs - do not edit manually.

## Codebase Patterns

### Architecture
- [Pattern description discovered by agents]

### Naming Conventions
- [Convention discovered by agents]

### Testing Patterns
- [Testing pattern discovered by agents]

### Common Gotchas
- [Gotcha or pitfall discovered by agents]

---

## Technology Stack

- **Backend**: [Detected]
- **Frontend**: [Detected]
- **Database**: [Detected]
- **Testing**: [Detected]

---

## File Organization

```
<discovered directory structure summary>
```

---

## Recent Learnings

### [Date] - [Feature/Task]
- Learning 1
- Learning 2

---

*Last updated: [timestamp] by Ralph orchestrator*
```

### 5.4 Update Rules

1. **Append-only for learnings**: New learnings are appended, never overwrite existing
2. **Update sections in place**: Patterns and conventions can be refined
3. **Agent-driven updates**: Implementation agent updates after completing tasks
4. **Timestamp all changes**: Include date/time for traceability

---

## 6. `progress.txt` - Progress Log

### 6.1 Purpose

Append-only log of completed tasks, iterations, and contextual learnings. Provides continuity across autopilot runs and helps agents understand recent work.

### 6.2 Location

```
<repo-root>/.ralph/progress.txt
```

Or configurable via `autopilot.memory.progress` in `ralph.yml`.

### 6.3 Format

```markdown
# Ralph Progress Log

## Codebase Patterns
<!-- Patterns discovered during runs - check this FIRST before each task -->
- Use `@injectable()` decorator for all services
- API routes follow `/api/v1/{resource}` pattern
- Tests use pytest fixtures from `conftest.py`
- Frontend components use shadcn/ui patterns

---

## [2026-01-25 14:38:05] - T-001: Add JWT dependency and configuration

### What was implemented
- Added PyJWT 2.8.0 to pyproject.toml
- Created src/config/auth.py with JWT settings
- Added JWT_SECRET_KEY to .env.example

### Files changed
- pyproject.toml
- src/config/auth.py (new)
- src/config/__init__.py
- .env.example

### Verification
- `uv run python -c "import jwt"` ✓
- `uv run pytest tests/test_config.py` ✓

### Learnings for future iterations
- JWT_SECRET_KEY must be at least 32 characters for HS256
- Config uses pydantic-settings for environment loading
- All new config modules must be imported in __init__.py

---

## [2026-01-25 14:52:00] - T-002: Create auth service with token generation

### What was implemented
- Created AuthService class with create_token and verify_token
- Added token expiration handling
- Created comprehensive unit tests

### Files changed
- src/services/auth.py (new)
- src/services/__init__.py
- tests/test_auth.py (new)

### Verification
- `uv run pytest tests/test_auth.py -v` ✓ (6 tests passed)

### Learnings for future iterations
- Services should raise custom exceptions, not generic ones
- Test fixtures should use freezegun for time-dependent tests
- Type hints required for all public methods

---
```

### 6.4 Structure Rules

1. **Codebase Patterns section at top**: Always read first
2. **Reverse chronological**: Most recent entries first (after patterns)
3. **Separator between entries**: Use `---` horizontal rule
4. **Standard sections per entry**:
   - Timestamp and task ID in heading
   - What was implemented
   - Files changed
   - Verification results
   - Learnings for future iterations
5. **Append-only**: Never delete or modify existing entries

---

## 7. Directory Structure Summary

Complete directory structure for a Ralph-enabled repository:

```
<repo-root>/
├── .ralph/                       # Ralph configuration directory
│   ├── ralph.yml                 # Main configuration file
│   ├── prd.json                  # Current task list
│   ├── progress.txt              # Progress log (autopilot memory)
│   └── archive/                  # Archived runs (autopilot)
│       └── 20260125-add-auth/
│           ├── prd.json
│           └── progress.txt
│
├── .ralph-session/               # Current run state (transient)
│   ├── session.json
│   ├── task-status.json
│   ├── task-status.sha256
│   ├── logs/
│   ├── artifacts/
│   └── pids/
│
├── AGENTS.md                     # Agent memory (persistent)
│
├── tasks/                        # PRD documents (autopilot)
│   └── prd-add-user-auth.md
│
├── reports/                      # Analysis reports (autopilot input)
│   └── weekly-review-20260120.md
│
└── ... (rest of codebase)
```

### Git Ignore Recommendations

Add to `.gitignore`:

```gitignore
# Ralph session (transient, don't commit)
.ralph-session/

# Keep these in git:
# .ralph/ralph.yml       - Configuration (commit)
# .ralph/prd.json        - Active tasks (commit for visibility)
# .ralph/progress.txt    - Progress log (commit)
# AGENTS.md              - Agent memory (commit)
```

---

## 8. Validation Rules

### 8.1 Configuration Validation

On `ralph run` startup:

1. **File exists**: `.ralph/ralph.yml` must exist
2. **Version check**: `version` must be "1"
3. **Required fields**: `task_source`, `gates.full`, `git.base_branch`
4. **Gate conditions**: Each `when` must reference existing file or pattern
5. **Service ports**: No port conflicts between services
6. **Model names**: Must be valid Claude model identifiers

### 8.2 Task List Validation

On task source load:

1. **Schema validation**: Must match prd.json JSON Schema
2. **ID uniqueness**: All task IDs must be unique
3. **ID format**: Must match `T-NNN` pattern
4. **Priority ordering**: Priorities should be sequential (warning if gaps)
5. **Criteria present**: Each task must have at least one acceptance criterion
6. **Subtask consistency**: Subtask IDs must match parent (e.g., T-001.1 under T-001)

### 8.3 Session Validation

During run:

1. **Token format**: Session token must match `ralph-YYYYMMDD-HHMMSS-[a-f0-9]+`
2. **Checksum integrity**: `task-status.sha256` must match actual file hash
3. **Signal validation**: Agent completion signals must contain correct session token
4. **No time travel**: Timestamps must be monotonically increasing

---

## 9. Migration Guide

### 9.1 From MongoDB-RAG-Agent CR Markdown

1. **Extract JSON block** from CR markdown file
2. **Transform task format**:

```javascript
// Old format (CR markdown)
{
  "category": "setup",
  "description": "Task description",
  "steps": ["Step 1", "Step 2"],
  "passes": false
}

// New format (prd.json)
{
  "id": "T-001",
  "title": "Task description",
  "description": "Task description",
  "acceptanceCriteria": ["Step 1", "Step 2"],
  "priority": 1,
  "passes": false,
  "notes": ""
}
```

3. **Create prd.json wrapper**:

```json
{
  "project": "Extracted from CR title",
  "branchName": "feature/from-cr-name",
  "description": "Extracted from CR description",
  "tasks": [/* transformed tasks */]
}
```

### 9.2 From Compound Product

Compound's `prd.json` is already compatible. Just:

1. Copy `prd.json` to `.ralph/prd.json`
2. Create `.ralph/ralph.yml` from `compound.config.json`:

```yaml
# From compound.config.json
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  full:
    # Convert qualityChecks array to gate definitions
    - name: typecheck
      cmd: "npm run typecheck"
      when: package.json
      fatal: true

autopilot:
  enabled: true
  reports_dir: ${reportsDir}
  branch_prefix: ${branchPrefix}
  create_pr: true
```

### 9.3 New Repository Setup

Run `ralph init` to generate starter files:

```bash
$ ralph init

Detected: Python backend (pyproject.toml)
Detected: Node frontend (frontend/package.json)
Template: fullstack

Created:
  .ralph/ralph.yml      - Configuration (review and customize)
  .ralph/prd.json       - Empty task list (populate via ralph autopilot or manually)
  AGENTS.md             - Agent memory (will be populated during runs)

Next steps:
  1. Review .ralph/ralph.yml and adjust commands/ports
  2. Create tasks: ralph autopilot --reports ./reports
     Or manually: edit .ralph/prd.json
  3. Run: ralph run
```

---

## 10. Autopilot Artifacts

### 10.1 Purpose

Autopilot mode generates additional artifacts for report analysis, PRD generation, and run tracking.

### 10.2 Directory Structure

```
.ralph/autopilot/
├── analysis.json           # Latest analysis output
├── runs/                   # Run history
│   ├── 20260125-143052-a7b3c9.json
│   └── ...
└── archive/                # Completed run archives
```

### 10.3 `analysis.json` Schema

The analysis output captures the selected priority item from report analysis:

```json
{
  "priority_item": "Implement user authentication",
  "description": "Add JWT-based authentication with login, logout, and protected routes. This addresses the security gap identified in the report.",
  "rationale": "Authentication is a prerequisite for all user-facing features and has the highest impact on security posture.",
  "acceptance_criteria": [
    "Users can register with email/password",
    "Users can login and receive a JWT",
    "Protected routes require valid JWT",
    "Tests cover happy path and error cases"
  ],
  "branch_name": "ralph/add-user-auth",
  "analysis_timestamp": "2026-01-25T14:30:52Z",
  "source_report": "reports/weekly-review-20260120.md",
  "excluded_items": [
    {
      "item": "Dark mode toggle",
      "reason": "Lower priority - cosmetic only"
    }
  ],
  "model_used": "claude-opus-4-5-20251101",
  "provider": "anthropic"
}
```

### 10.4 Run Record Schema

Each autopilot run is tracked in `.ralph/autopilot/runs/`:

```json
{
  "run_id": "20260125-143052-a7b3c9",
  "started_at": "2026-01-25T14:30:52Z",
  "completed_at": "2026-01-25T16:45:00Z",
  "status": "completed",
  "analysis_path": ".ralph/autopilot/analysis.json",
  "prd_path": "tasks/prd-add-user-auth.md",
  "tasks_path": ".ralph/prd.json",
  "branch_name": "ralph/add-user-auth",
  "session_id": "20260125-150000-b8c4d0",
  "tasks_completed": 10,
  "tasks_total": 10,
  "pr_created": true,
  "pr_url": "https://github.com/org/repo/pull/123"
}
```

### 10.5 PRD Document Format

Generated PRDs are stored in `tasks/` (configurable via `autopilot.prd.output_dir`):

```markdown
---
generated_by: ralph-autopilot
generated_at: 2026-01-25T14:35:00Z
source_analysis: .ralph/autopilot/analysis.json
mode: autonomous
---

# PRD: User Authentication

## Overview
[Generated content...]

## Requirements
[Generated content...]

## Acceptance Criteria
[From analysis.json...]
```

### 10.6 Archiving

Completed runs can be archived to `.ralph/archive/`:

```
.ralph/archive/
└── 20260125-add-user-auth/
    ├── analysis.json       # Copy of analysis
    ├── prd.json           # Final task state
    ├── progress.txt       # Progress log snapshot
    └── run-record.json    # Run metadata
```

Archiving is optional and controlled by `autopilot.memory.archive` setting.

---

## Appendix A: Environment Variables

Configuration can be overridden via environment:

| Variable | Config Path | Description |
|----------|-------------|-------------|
| `RALPH_CONFIG` | - | Path to ralph.yml (default: `.ralph/ralph.yml`) |
| `RALPH_SESSION_DIR` | - | Session directory (default: `.ralph-session`) |
| `RALPH_IMPL_MODEL` | `agents.implementation.model` | Implementation model |
| `RALPH_TEST_MODEL` | `agents.test_writing.model` | Test-writing model |
| `RALPH_REVIEW_MODEL` | `agents.review.model` | Review model |
| `RALPH_CLAUDE_TIMEOUT` | `limits.claude_timeout` | Claude call timeout |
| `RALPH_MAX_ITERATIONS` | `limits.max_iterations` | Max task iterations |
| `RALPH_CLAUDE_CMD` | - | Claude CLI command (for testing/mocking) |

---

## Appendix B: Signal Formats

### Task Done Signal

```xml
<task-done session="ralph-20260125-143052-a7b3c9f2d1e8">
Implementation complete. Changes:
- Created src/auth.py
- Added tests in tests/test_auth.py
</task-done>
```

### Tests Done Signal

```xml
<tests-done session="ralph-20260125-143052-a7b3c9f2d1e8">
Tests written:
- test_create_token_returns_valid_jwt
- test_verify_token_decodes_correctly
- test_verify_token_rejects_expired
</tests-done>
```

### Review Signals

```xml
<review-approved session="ralph-20260125-143052-a7b3c9f2d1e8">
Code review passed. Implementation meets acceptance criteria.
</review-approved>
```

```xml
<review-rejected session="ralph-20260125-143052-a7b3c9f2d1e8">
Issues found:
- Missing error handling for expired tokens
- No logging for failed auth attempts
</review-rejected>
```

---

*End of Canonical Artifacts Specification*
