# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ralph Orchestrator is a CLI tool that automates verified software development workflows. It orchestrates Claude Code (the AI assistant) through a structured task loop with quality gates, anti-gaming measures, and session management.

## Common Commands

```bash
# Install for development
pip install -e .

# Run tests
pytest                              # All tests
pytest tests/unit                   # Unit tests only
pytest tests/integration            # Integration tests only
pytest -k "test_signals"            # Run specific test pattern
pytest --tb=long -v                 # Verbose output with full tracebacks

# CLI commands
ralph init                          # Initialize .ralph/ directory with templates
ralph scan                          # Check environment (tools, config, task source)
ralph run --dry-run                 # Preview tasks without executing
ralph run --prd-json .ralph/prd.json  # Execute verified task loop
ralph verify                        # Run post-completion verification
ralph autopilot --dry-run           # Analyze reports and plan (no execution)

# Run with UI test control
ralph run --with-smoke --prd-json .ralph/prd.json   # Enable smoke tests
ralph run --no-smoke --prd-json .ralph/prd.json     # Disable smoke tests
ralph run --with-robot --prd-json .ralph/prd.json   # Enable Robot Framework
ralph run --no-robot --prd-json .ralph/prd.json     # Disable Robot Framework

# Autopilot with research control
ralph autopilot --with-research --dry-run    # Enable research phase (default)
ralph autopilot --no-research                # Skip research phase
ralph autopilot --research-backend           # Backend research only
ralph autopilot --research-frontend          # Frontend research only
ralph autopilot --research-web               # Web search research only
```

## Architecture

### Core Execution Flow

The verified task loop in `run.py` executes tasks through multiple agent phases:

1. **Implementation Agent** - Makes code changes, must emit `<task-done session="TOKEN">` signal
2. **Test Writing Agent** - Writes tests (guardrailed to test paths only), emits `<tests-done session="TOKEN">`
3. **Quality Gates** - Runs configured build/test commands from `ralph.yml`
4. **Review Agent** - Verifies acceptance criteria, emits `<review-approved>` or `<review-rejected>`

Each agent must include the session token in their completion signal for anti-gaming verification.

### Key Modules

- **`cli.py`** - Entry point, argument parsing, subcommand dispatch
- **`run.py`** - `RunEngine` class orchestrates the verified task loop
- **`autopilot.py`** - `AutopilotOrchestrator` runs the full report→research→PRD→tasks→execute pipeline
- **`config.py`** - Loads and validates `ralph.yml` against JSON schema
- **`session.py`** - Session management with checksum-based tamper detection (`.ralph-session/`)
- **`signals.py`** - Parses XML completion signals from Claude responses
- **`gates.py`** - `GateRunner` executes quality gates (build, lint, test)
- **`guardrails.py`** - `FilePathGuardrail` restricts test-writing agent to test directories
- **`agents/claude.py`** - `ClaudeRunner` wraps Claude CLI invocation
- **`agents/prompts.py`** - Prompt templates for each agent role
- **`tasks/prd.py`** - PRD data model and task management
- **`research/`** - Research sub-agents for PRD enhancement
  - `coordinator.py` - `ResearchCoordinator` orchestrates research phases
  - `backend.py` - `BackendResearcher` scans Python/API code patterns
  - `frontend.py` - `FrontendResearcher` scans React/Vue/CSS components
  - `web.py` - `WebResearcher` uses web search for docs/best practices
- **`skills/`** - Skill routing for specialized Claude plugins
  - `router.py` - `SkillRouter` detects and applies skills for tasks
  - `defaults.py` - Default skill mappings (frontend-design, docx, xlsx, etc.)

### Configuration

Configuration lives in `.ralph/ralph.yml` (validated against `schemas/ralph-config.schema.json`):

```yaml
task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  build:
    - name: lint
      cmd: "ruff check ."
  full:
    - name: test
      cmd: "pytest"

services:
  backend:
    start:
      dev: "uvicorn app:main --reload"
```

### Signal Format

Agents communicate completion via XML signals with session tokens:

```xml
<task-done session="ralph-20260125-143052-abc123">
Implementation complete. Changes made: ...
</task-done>
```

Signal types: `task-done`, `tests-done`, `review-approved`, `review-rejected`, `fix-done`

### Session Directory Structure

```
.ralph-session/
├── session.json          # Session metadata
├── task-status.json      # Task completion status
├── task-status.sha256    # Checksum for tamper detection
├── logs/
│   ├── timeline.jsonl    # Event timeline
│   └── *.log             # Agent and gate outputs
└── artifacts/            # Screenshots, reports
```

## Testing

Tests use a mock Claude CLI (`tests/mock_claude/mock_claude.py`) controlled via `MOCK_SCENARIO` environment variable:

- `default` - Returns success signals with correct tokens
- `invalid_token` - Returns signals with wrong session token
- `no_signal` - Returns response without completion signal
- `review_reject` - Returns review rejection

Fixtures in `tests/fixtures/` provide minimal project setups (python_min, node_min, fullstack_min, autopilot_min).

## Environment Variables

- `RALPH_CLAUDE_CMD` - Override Claude CLI command (default: `claude`)
- `RALPH_CONFIG` - Override config file path
- `RALPH_SESSION_DIR` - Override session directory
- `ANTHROPIC_API_KEY` - For autopilot analysis (or use Claude CLI auth)
