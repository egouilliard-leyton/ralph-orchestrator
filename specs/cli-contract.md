# Ralph CLI Contract Specification

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Canonical Reference

This document defines the complete CLI contract for the Ralph orchestrator, including all commands, arguments, options, exit codes, and behaviors.

> **Related Documents:**
> - [Canonical Artifacts](./canonical-artifacts.md) - File formats and schemas
> - [Design Decisions](./design-decisions.md) - Rationale behind key decisions
> - [JSON Schemas](../schemas/) - Machine-validatable schemas

---

## Table of Contents

1. [Overview](#1-overview)
2. [Global Options](#2-global-options)
3. [Command: `ralph init`](#3-command-ralph-init)
4. [Command: `ralph run`](#4-command-ralph-run)
5. [Command: `ralph verify`](#5-command-ralph-verify)
6. [Command: `ralph autopilot`](#6-command-ralph-autopilot)
7. [Command: `ralph scan`](#7-command-ralph-scan)
8. [Exit Codes](#8-exit-codes)
9. [Configuration Schema Summary](#9-configuration-schema-summary)
10. [Environment Variables](#10-environment-variables)

---

## 1. Overview

### 1.1 Installation

```bash
# Install from PyPI (recommended)
pipx install ralph-orchestrator

# Install from source
pip install -e ./ralph-orchestrator

# Verify installation
ralph --version
```

### 1.2 Command Summary

| Command | Purpose | Requires Config |
|---------|---------|-----------------|
| `ralph init` | Initialize repo with config and templates | No |
| `ralph run` | Execute verified task loop | Yes |
| `ralph verify` | Run post-completion verification only | Yes |
| `ralph autopilot` | Full pipeline: report → PRD → tasks → run → PR | Yes |
| `ralph scan` | Preflight check for tools and environment | Optional |

### 1.3 Command Structure

```
ralph [global-options] <command> [command-options] [arguments]
```

---

## 2. Global Options

These options apply to all commands.

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--config` | `-c` | PATH | `.ralph/ralph.yml` | Path to configuration file |
| `--session-dir` | | PATH | `.ralph-session` | Session directory location |
| `--verbose` | `-v` | FLAG | false | Enable verbose output |
| `--debug` | | FLAG | false | Enable debug logging |
| `--quiet` | `-q` | FLAG | false | Suppress non-essential output |
| `--version` | `-V` | FLAG | | Show version and exit |
| `--help` | `-h` | FLAG | | Show help and exit |

### 2.1 Examples

```bash
# Use custom config location
ralph -c ./custom/ralph.yml run

# Verbose mode
ralph -v run --prd-json tasks.json

# Debug mode (includes internal state dumps)
ralph --debug autopilot --dry-run
```

---

## 3. Command: `ralph init`

### 3.1 Purpose

Initialize a repository for use with Ralph by generating configuration files and templates.

### 3.2 Synopsis

```bash
ralph init [OPTIONS]
```

### 3.3 Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--template` | `-t` | ENUM | auto | Template to use: `auto`, `minimal`, `python`, `node`, `fullstack` |
| `--force` | `-f` | FLAG | false | Overwrite existing configuration |
| `--no-agents-md` | | FLAG | false | Skip AGENTS.md creation |
| `--no-prd` | | FLAG | false | Skip prd.json template creation |
| `--output-dir` | `-o` | PATH | `.ralph` | Output directory for config |

### 3.4 Behavior

1. **Detection Phase** (when `--template auto`):
   - Check for `pyproject.toml` or `setup.py` → Python stack
   - Check for `package.json` → Node stack
   - Check for both → Fullstack stack
   - Neither → Minimal template

2. **Generation Phase**:
   - Create `.ralph/ralph.yml` from selected template
   - Create `.ralph/prd.json` empty task list (unless `--no-prd`)
   - Create `AGENTS.md` from template (unless `--no-agents-md`)
   - Create `.ralph/progress.txt` placeholder

3. **Validation Phase**:
   - Verify generated config is valid against schema
   - Print summary of created files

4. **Safety**:
   - Refuse to overwrite existing files unless `--force`
   - Create backups of overwritten files (`*.bak`)

### 3.5 Output

```
$ ralph init

Detecting project type...
  ✓ Found pyproject.toml (Python)
  ✓ Found frontend/package.json (Node)
Template: fullstack

Creating configuration files...
  ✓ .ralph/ralph.yml (fullstack template)
  ✓ .ralph/prd.json (empty task list)
  ✓ .ralph/progress.txt (progress log)
  ✓ AGENTS.md (agent memory)

Validating configuration...
  ✓ Configuration valid

Next steps:
  1. Review .ralph/ralph.yml and customize:
     - Service ports and commands
     - Quality gates
     - Test path patterns
  2. Create tasks:
     - Manual: edit .ralph/prd.json
     - Autopilot: ralph autopilot --reports ./reports
  3. Run: ralph run
```

### 3.6 Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Success |
| 1 | File already exists (without `--force`) |
| 2 | Template not found |
| 3 | Validation failed |

---

## 4. Command: `ralph run`

### 4.1 Purpose

Execute the verified task loop: implement → test → gates → review → mark complete.

### 4.2 Synopsis

```bash
ralph run [OPTIONS]
```

### 4.3 Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--prd-json` | `-p` | PATH | (from config) | Path to prd.json task file |
| `--cr` | | PATH | | Path to CR markdown (compat mode) |
| `--latest-cr` | | FLAG | false | Find and use latest CR file |
| `--task` | `-t` | STRING | | Run only specific task ID |
| `--from-task` | | STRING | | Start from specific task ID |
| `--max-iterations` | | INT | 30 | Maximum task loop iterations |
| `--post-verify` | | BOOL | true | Run post-completion verification |
| `--ui-verify` | | BOOL | (from config) | Run UI verification |
| `--robot-verify` | | BOOL | (from config) | Run Robot Framework tests |
| `--gates` | | ENUM | full | Gate level: `build`, `full`, `none` |
| `--model-impl` | | STRING | (from config) | Model for implementation agent |
| `--model-test` | | STRING | (from config) | Model for test-writing agent |
| `--model-review` | | STRING | (from config) | Model for review agent |
| `--timeout` | | INT | 1800 | Timeout per Claude call (seconds) |
| `--env` | | ENUM | dev | Environment mode: `dev`, `prod` |
| `--resume` | | FLAG | false | Resume from existing session |
| `--dry-run` | | FLAG | false | Parse tasks, don't execute |

### 4.4 Behavior

#### Phase 1: Initialization
1. Load and validate configuration
2. Load and validate task source (prd.json or CR markdown)
3. Generate session token
4. Create `.ralph-session/` directory structure
5. Initialize session.json and task-status.json
6. Run preflight checks (tool availability)

#### Phase 2: Task Loop
For each pending task (by priority order):

```
┌─────────────────────────────────────────────────────┐
│ 1. Log task_start event                             │
├─────────────────────────────────────────────────────┤
│ 2. Run Implementation Agent                         │
│    - Prompt includes: task, criteria, session token │
│    - Wait for <task-done> signal                    │
│    - Validate session token in signal              │
├─────────────────────────────────────────────────────┤
│ 3. Run Test-Writing Agent (guardrailed)            │
│    - Snapshot git status before                     │
│    - Allow only test_paths patterns                 │
│    - Revert disallowed file changes                │
│    - Wait for <tests-done> signal                  │
├─────────────────────────────────────────────────────┤
│ 4. Run Quality Gates                                │
│    - Execute gates.build (fast) or gates.full      │
│    - On failure: log, provide feedback, retry      │
├─────────────────────────────────────────────────────┤
│ 5. Run Review Agent (read-only)                    │
│    - Check acceptance criteria                      │
│    - Wait for <review-approved> or <review-rejected>│
│    - On rejection: feed back to impl agent         │
├─────────────────────────────────────────────────────┤
│ 6. Mark Task Complete                               │
│    - Update prd.json passes=true                   │
│    - Update task-status.json                        │
│    - Recompute checksum                            │
│    - Log task_complete event                        │
└─────────────────────────────────────────────────────┘
```

#### Phase 3: Post-Completion Verification (if `--post-verify`)
1. Start services (backend, frontend)
2. Wait for health checks to pass
3. Run agent-browser UI tests (if enabled)
4. Run Robot Framework tests (if enabled)
5. On failure: plan → fix → retest loop

#### Phase 4: Cleanup
1. Stop services
2. Write final summary to timeline.jsonl
3. Update progress.txt (if autopilot)
4. Update AGENTS.md with learnings

### 4.5 Output

```
$ ralph run

═══════════════════════════════════════════════════════════
  RALPH VERIFIED EXECUTION
  Session: ralph-20260125-143052-a7b3c9f2d1e8
  Tasks: 10 pending | 0 completed
═══════════════════════════════════════════════════════════

[T-001] Add JWT dependency and configuration
────────────────────────────────────────────────────────────
  ▶ Implementation agent starting...
  ✓ Implementation complete (2m 34s)
  ▶ Test-writing agent starting...
  ✓ Tests written (1m 12s)
  ▶ Running gates (full)...
    ✓ pytest (4.2s)
    ✓ mypy (8.1s)
    ✓ tsc (12.3s)
  ▶ Review agent starting...
  ✓ Review approved (45s)
  ✓ Task complete

[T-002] Create auth service with token generation
────────────────────────────────────────────────────────────
  ▶ Implementation agent starting...
  ...

═══════════════════════════════════════════════════════════
  POST-COMPLETION VERIFICATION
═══════════════════════════════════════════════════════════

  ▶ Starting backend on port 8000...
  ✓ Backend healthy (3.2s)
  ▶ Building frontend...
  ✓ Frontend built (45s)
  ▶ Serving frontend on port 5173...
  ✓ Frontend ready (2.1s)

  ▶ Running agent-browser smoke tests...
    ✓ app_loads (1.2s)
    ✓ dashboard_navigation (2.3s)
    ✓ login_flow (3.4s)

  ▶ Running Robot Framework tests...
    ✓ smoke_dashboard (5.2s)

═══════════════════════════════════════════════════════════
  SUMMARY
═══════════════════════════════════════════════════════════
  Tasks: 10/10 completed
  Duration: 42m 18s
  Gates: 30 passed, 0 failed
  UI Tests: 4 passed, 0 failed
  
  Session logs: .ralph-session/logs/
  Screenshots: .ralph-session/artifacts/screenshots/
═══════════════════════════════════════════════════════════
```

### 4.6 Exit Codes

| Code | Condition |
|------|-----------|
| 0 | All tasks completed successfully |
| 1 | Configuration error |
| 2 | Task source error (invalid prd.json) |
| 3 | Task execution failed (max iterations) |
| 4 | Gate failure (fatal gate) |
| 5 | Post-verification failed |
| 6 | Checksum tampering detected |
| 7 | User abort (Ctrl+C) |
| 8 | Claude CLI error |
| 9 | Service startup failure |

---

## 5. Command: `ralph verify`

### 5.1 Purpose

Run post-completion verification independently, without executing tasks. Useful for verifying manual changes or re-running verification after `ralph run`.

### 5.2 Synopsis

```bash
ralph verify [OPTIONS]
```

### 5.3 Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--gates` | | ENUM | full | Gate level: `build`, `full`, `none` |
| `--ui` | | BOOL | (from config) | Run UI tests |
| `--robot` | | BOOL | (from config) | Run Robot tests |
| `--env` | | ENUM | dev | Environment: `dev`, `prod` |
| `--fix` | | FLAG | false | Attempt to fix failures |
| `--fix-iterations` | | INT | 10 | Max fix iterations |
| `--skip-services` | | FLAG | false | Skip service startup (use existing) |
| `--base-url` | | URL | | Override base URL for tests |

### 5.4 Behavior

1. **Gate Phase**:
   - Run configured quality gates
   - Report pass/fail for each

2. **Service Phase** (unless `--skip-services`):
   - Start backend service
   - Wait for health check
   - Build and serve frontend
   - Wait for ready

3. **UI Test Phase** (if `--ui`):
   - Run agent-browser tests
   - Capture screenshots on failure
   - If `--fix`: plan → implement fix → retest

4. **Robot Test Phase** (if `--robot`):
   - Run Robot Framework suite
   - Generate report artifacts
   - If `--fix`: plan → implement fix → retest

5. **Cleanup**:
   - Stop services
   - Report summary

### 5.5 Output

```
$ ralph verify --ui --robot

═══════════════════════════════════════════════════════════
  RALPH VERIFICATION
═══════════════════════════════════════════════════════════

▶ Running quality gates (full)...
  ✓ pytest (4.2s)
  ✓ mypy (8.1s)
  ✓ tsc (12.3s)
  ✓ lint (3.2s)
  ✓ build (45.1s)

▶ Starting services...
  ✓ Backend ready on http://localhost:8000 (3.2s)
  ✓ Frontend ready on http://localhost:5173 (2.1s)

▶ Running UI tests (agent-browser)...
  ✓ app_loads
  ✓ dashboard_navigation
  ✗ login_flow
    Expected: "Welcome back" message
    Actual: Error notification visible
    Screenshot: .ralph-session/artifacts/screenshots/login_flow_failure.png

▶ Running Robot Framework...
  ✓ smoke_dashboard

═══════════════════════════════════════════════════════════
  RESULT: 1 FAILURE
═══════════════════════════════════════════════════════════
  Gates: 5/5 passed
  UI Tests: 2/3 passed
  Robot Tests: 1/1 passed

  Run with --fix to attempt automatic repair.
```

### 5.6 Exit Codes

| Code | Condition |
|------|-----------|
| 0 | All verification passed |
| 1 | Configuration error |
| 4 | Gate failure |
| 5 | UI test failure |
| 6 | Robot test failure |
| 9 | Service startup failure |

---

## 6. Command: `ralph autopilot`

### 6.1 Purpose

Automated self-improvement pipeline: analyze reports → select priority → generate PRD → generate tasks → run verified loop → create PR.

### 6.2 Synopsis

```bash
ralph autopilot [OPTIONS]
```

### 6.3 Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--reports` | `-r` | PATH | (from config) | Directory containing reports |
| `--report` | | PATH | | Specific report file to use |
| `--dry-run` | | FLAG | false | Analyze only, don't execute |
| `--create-pr` | | BOOL | (from config) | Create PR on completion |
| `--branch` | `-b` | STRING | (auto) | Branch name to use |
| `--no-prd` | | FLAG | false | Skip PRD generation (use existing tasks) |
| `--prd-mode` | | ENUM | autonomous | PRD mode: `autonomous`, `interactive` |
| `--task-count` | | RANGE | 8-15 | Target task count (e.g., "8-15") |
| `--analysis-model` | | STRING | (from config) | Model for analysis phase |
| `--recent-days` | | INT | 7 | Exclude items fixed in last N days |

### 6.4 Behavior

#### Phase 1: Report Selection
1. Scan `--reports` directory for report files
2. Sort by modification time (newest first)
3. Select newest report (or use `--report`)
4. Validate report is readable

#### Phase 2: Analysis
1. Load report content and progress history
2. Call Claude with analysis prompt:
   - Identify priority items from report
   - Exclude items recently fixed (check progress.txt)
   - Select #1 priority with rationale
3. Generate `analysis.json`:
   - `priority_item`: Selected item
   - `description`: What needs to be done
   - `rationale`: Why this was selected
   - `acceptance_criteria`: High-level criteria
   - `branch_name`: Suggested branch name
4. If `--dry-run`: print analysis and exit

#### Phase 3: Branch Setup
1. Check out base branch (from config)
2. Pull latest changes
3. Create feature branch (`{branch_prefix}{branch_name}`)
4. Push branch to remote

#### Phase 4: PRD Generation (unless `--no-prd`)
1. Call Claude with PRD prompt (autonomous or interactive)
2. Generate PRD markdown document
3. Save to `{prd.output_dir}/prd-{branch_name}.md`

#### Phase 5: Task Generation
1. Call Claude with task generation prompt:
   - Input: PRD document
   - Output: prd.json task list
2. Validate task count is within range
3. Save to `.ralph/prd.json`

#### Phase 6: Verified Execution
1. Invoke `ralph run` internally
2. Execute all generated tasks
3. Run post-completion verification

#### Phase 7: PR Creation (if `--create-pr`)
1. Commit all changes with summary message
2. Push branch to remote
3. Create PR via `gh pr create`:
   - Title: `{title_template}` with placeholders filled
   - Body: Task summary + rationale
4. Output PR URL

#### Phase 8: Cleanup
1. Update progress.txt with completed work
2. Archive run artifacts (if configured)
3. Return to base branch

### 6.5 Output

```
$ ralph autopilot --reports ./reports --create-pr

═══════════════════════════════════════════════════════════
  RALPH AUTOPILOT
═══════════════════════════════════════════════════════════

▶ Scanning reports directory...
  Found 3 reports:
    - weekly-review-20260120.md (latest)
    - weekly-review-20260113.md
    - weekly-review-20260106.md

▶ Analyzing report: weekly-review-20260120.md
  Reading progress history...
  Excluding 2 recently-fixed items
  
  Analysis complete:
  ┌──────────────────────────────────────────────────────┐
  │ Priority Item: User Authentication                   │
  ├──────────────────────────────────────────────────────┤
  │ Description:                                         │
  │   Add JWT-based authentication with login, logout,  │
  │   and protected routes.                             │
  ├──────────────────────────────────────────────────────┤
  │ Rationale:                                          │
  │   Security prerequisite for all user features.      │
  │   Highest impact item in report.                    │
  ├──────────────────────────────────────────────────────┤
  │ Branch: ralph/add-user-auth                         │
  └──────────────────────────────────────────────────────┘

▶ Setting up branch...
  ✓ Checked out main
  ✓ Pulled latest changes
  ✓ Created branch: ralph/add-user-auth

▶ Generating PRD (autonomous mode)...
  ✓ PRD saved to tasks/prd-add-user-auth.md

▶ Generating tasks...
  ✓ Generated 10 tasks
  ✓ Tasks saved to .ralph/prd.json

▶ Starting verified execution...
  [... ralph run output ...]

▶ Creating pull request...
  ✓ Changes committed
  ✓ Pushed to origin/ralph/add-user-auth
  ✓ PR created: https://github.com/org/repo/pull/123

═══════════════════════════════════════════════════════════
  AUTOPILOT COMPLETE
═══════════════════════════════════════════════════════════
  Branch: ralph/add-user-auth
  Tasks: 10/10 completed
  PR: https://github.com/org/repo/pull/123
  
  Run artifacts: .ralph/autopilot/runs/20260125-143052-a7b3c9.json
═══════════════════════════════════════════════════════════
```

### 6.6 Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Autopilot completed successfully |
| 1 | Configuration error |
| 10 | No reports found |
| 11 | Analysis failed |
| 12 | PRD generation failed |
| 13 | Task generation failed |
| 14 | Git operation failed |
| 15 | PR creation failed |
| 3-9 | (inherited from `ralph run`) |

---

## 7. Command: `ralph scan`

### 7.1 Purpose

Preflight check to verify tool availability and environment setup. Useful for diagnosing issues before running automated workflows.

### 7.2 Synopsis

```bash
ralph scan [OPTIONS]
```

### 7.3 Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--fix` | | FLAG | false | Attempt to fix missing tools (print instructions) |
| `--json` | | FLAG | false | Output results as JSON |
| `--check` | | LIST | all | Specific checks: `claude`, `git`, `gh`, `python`, `node`, `robot` |
| `--strict` | | FLAG | false | Fail on warnings (not just errors) |

### 7.4 Checks Performed

| Check | Required For | Severity | Description |
|-------|--------------|----------|-------------|
| `claude` | All | ERROR | Claude CLI installed and authenticated |
| `git` | All | ERROR | Git available and in a repository |
| `gh` | Autopilot PR | WARNING | GitHub CLI for PR creation |
| `python` | Python projects | CONDITIONAL | Python/uv for Python gates |
| `node` | Node projects | CONDITIONAL | Node/npm for Node gates |
| `agent-browser` | UI tests | WARNING | Agent-browser for UI verification |
| `robot` | Robot tests | WARNING | Robot Framework and Browser library |
| `config` | run/verify | ERROR | Valid ralph.yml exists |
| `tasks` | run | WARNING | Valid prd.json exists |

### 7.5 Behavior

1. **Tool Discovery**:
   - Check PATH for each tool
   - Verify tool responds to version command
   - Check minimum version requirements

2. **Configuration Check**:
   - Validate ralph.yml against schema
   - Check referenced files exist
   - Verify port availability

3. **Authentication Check**:
   - Claude CLI: test with simple prompt
   - GitHub CLI: check auth status

4. **Report**:
   - Green check for passed
   - Yellow warning for optional missing
   - Red error for required missing
   - Instructions for fixes if `--fix`

### 7.6 Output

```
$ ralph scan

═══════════════════════════════════════════════════════════
  RALPH ENVIRONMENT SCAN
═══════════════════════════════════════════════════════════

Core Tools
──────────────────────────────────────────────────────────
  ✓ claude         /opt/homebrew/bin/claude (1.2.3)
  ✓ git            /usr/bin/git (2.39.0)
  ⚠ gh             not found (optional for PR creation)

Python Stack
──────────────────────────────────────────────────────────
  ✓ python         /Users/me/.local/bin/python (3.11.4)
  ✓ uv             /opt/homebrew/bin/uv (0.1.24)
  ✓ pytest         available via uv
  ✓ mypy           available via uv

Node Stack
──────────────────────────────────────────────────────────
  ✓ node           /opt/homebrew/bin/node (20.10.0)
  ✓ npm            /opt/homebrew/bin/npm (10.2.3)
  ✓ npx            /opt/homebrew/bin/npx

UI Testing
──────────────────────────────────────────────────────────
  ⚠ agent-browser  not found (optional for UI verification)
  ⚠ robot          not found (optional for Robot tests)

Configuration
──────────────────────────────────────────────────────────
  ✓ ralph.yml      .ralph/ralph.yml (valid)
  ✓ prd.json       .ralph/prd.json (10 tasks)

═══════════════════════════════════════════════════════════
  RESULT: READY (2 warnings)
═══════════════════════════════════════════════════════════

To fix warnings, run: ralph scan --fix
```

### 7.7 Fix Output

```
$ ralph scan --fix

[... scan output ...]

═══════════════════════════════════════════════════════════
  FIX INSTRUCTIONS
═══════════════════════════════════════════════════════════

gh (GitHub CLI)
──────────────────────────────────────────────────────────
  Install:
    brew install gh
  
  Authenticate:
    gh auth login

agent-browser
──────────────────────────────────────────────────────────
  Install:
    npm install -g @anthropic/agent-browser
  
  Note: Requires Chrome/Chromium installed

robot (Robot Framework)
──────────────────────────────────────────────────────────
  Install:
    pip install robotframework robotframework-browser
    rfbrowser init
```

### 7.8 JSON Output

```bash
$ ralph scan --json
```

```json
{
  "status": "ready",
  "errors": [],
  "warnings": ["gh not found", "agent-browser not found"],
  "checks": {
    "claude": {"status": "pass", "path": "/opt/homebrew/bin/claude", "version": "1.2.3"},
    "git": {"status": "pass", "path": "/usr/bin/git", "version": "2.39.0"},
    "gh": {"status": "warning", "message": "not found"},
    "python": {"status": "pass", "path": "/Users/me/.local/bin/python", "version": "3.11.4"},
    "node": {"status": "pass", "path": "/opt/homebrew/bin/node", "version": "20.10.0"},
    "agent-browser": {"status": "warning", "message": "not found"},
    "robot": {"status": "warning", "message": "not found"},
    "config": {"status": "pass", "path": ".ralph/ralph.yml"},
    "tasks": {"status": "pass", "path": ".ralph/prd.json", "task_count": 10}
  }
}
```

### 7.9 Exit Codes

| Code | Condition |
|------|-----------|
| 0 | All checks passed (or warnings only without `--strict`) |
| 1 | One or more required tools missing |
| 2 | Configuration invalid |
| 3 | Warnings present (with `--strict`) |

---

## 8. Exit Codes

### 8.1 Global Exit Codes

| Range | Category |
|-------|----------|
| 0 | Success |
| 1-9 | General/run errors |
| 10-19 | Autopilot-specific errors |
| 20-29 | Reserved for future use |

### 8.2 Complete Exit Code Table

| Code | Command | Condition |
|------|---------|-----------|
| 0 | All | Success |
| 1 | All | Configuration error |
| 2 | run | Task source error |
| 3 | run | Task execution failed (max iterations) |
| 4 | run/verify | Gate failure (fatal) |
| 5 | run/verify | Post-verification failed |
| 6 | run | Checksum tampering detected |
| 7 | All | User abort (Ctrl+C) |
| 8 | run | Claude CLI error |
| 9 | run/verify | Service startup failure |
| 10 | autopilot | No reports found |
| 11 | autopilot | Analysis failed |
| 12 | autopilot | PRD generation failed |
| 13 | autopilot | Task generation failed |
| 14 | autopilot | Git operation failed |
| 15 | autopilot | PR creation failed |

---

## 9. Configuration Schema Summary

The complete schema is defined in `schemas/ralph-config.schema.json`. Here's a summary of the major sections:

### 9.1 Required Fields

```yaml
version: "1"                    # Schema version (must be "1")

task_source:
  type: prd_json               # prd_json | cr_markdown
  path: .ralph/prd.json        # Path to task file

git:
  base_branch: main            # Base branch for features

gates:
  full:                        # At least one gate required
    - name: test
      cmd: "npm test"
      fatal: true
```

### 9.2 Optional Sections

| Section | Purpose | Default |
|---------|---------|---------|
| `services` | Backend/frontend definitions | None (no runtime verification) |
| `gates.build` | Fast gates for task loop | None (use full) |
| `test_paths` | Test file guardrail patterns | `["tests/**", "**/*.test.*"]` |
| `ui` | UI verification settings | Disabled |
| `agents` | Per-role model configuration | Default models |
| `limits` | Iteration/timeout limits | Sensible defaults |
| `autopilot` | Autopilot pipeline settings | Disabled |
| `pr` | PR template settings | Defaults |

### 9.3 Configuration Examples

See templates:
- `templates/.ralph/ralph.yml.minimal` - Bare minimum
- `templates/.ralph/ralph.yml.python` - Python-only project
- `templates/.ralph/ralph.yml.node` - Node.js project
- `templates/.ralph/ralph.yml.fullstack` - Full stack with UI tests

---

## 10. Environment Variables

Environment variables override configuration file settings.

### 10.1 Configuration Overrides

| Variable | Config Path | Description |
|----------|-------------|-------------|
| `RALPH_CONFIG` | - | Path to ralph.yml |
| `RALPH_SESSION_DIR` | - | Session directory path |
| `RALPH_IMPL_MODEL` | `agents.implementation.model` | Implementation model |
| `RALPH_TEST_MODEL` | `agents.test_writing.model` | Test-writing model |
| `RALPH_REVIEW_MODEL` | `agents.review.model` | Review model |
| `RALPH_FIX_MODEL` | `agents.fix.model` | Fix agent model |
| `RALPH_PLANNING_MODEL` | `agents.planning.model` | Planning agent model |
| `RALPH_CLAUDE_TIMEOUT` | `limits.claude_timeout` | Claude call timeout |
| `RALPH_MAX_ITERATIONS` | `limits.max_iterations` | Max task iterations |

### 10.2 Runtime Overrides

| Variable | Description |
|----------|-------------|
| `RALPH_CLAUDE_CMD` | Claude CLI command (default: `claude`) |
| `RALPH_GH_CMD` | GitHub CLI command (default: `gh`) |
| `RALPH_DRY_RUN` | Enable dry-run mode if set to `1` |
| `RALPH_DEBUG` | Enable debug logging if set to `1` |
| `RALPH_NO_COLOR` | Disable colored output if set to `1` |

### 10.3 Precedence

```
Command-line option > Environment variable > Config file > Default
```

---

## Appendix A: Signal Reference

### Task Done
```xml
<task-done session="ralph-YYYYMMDD-HHMMSS-hex">
Implementation complete. Changes:
- [list of changes]
</task-done>
```

### Tests Done
```xml
<tests-done session="ralph-YYYYMMDD-HHMMSS-hex">
Tests written:
- [list of tests]
</tests-done>
```

### Review Approved
```xml
<review-approved session="ralph-YYYYMMDD-HHMMSS-hex">
Code review passed. [optional notes]
</review-approved>
```

### Review Rejected
```xml
<review-rejected session="ralph-YYYYMMDD-HHMMSS-hex">
Issues found:
- [list of issues]
</review-rejected>
```

---

## Appendix B: Quick Reference Card

```
ralph init [-t TEMPLATE] [-f]           # Initialize repo
ralph run [-p PRD] [--cr CR]            # Execute tasks
ralph verify [--ui] [--robot]           # Verify only
ralph autopilot [-r REPORTS] [--create-pr]  # Full pipeline
ralph scan [--fix] [--json]             # Environment check

Common Options:
  -c, --config PATH     Config file (.ralph/ralph.yml)
  -v, --verbose         Verbose output
  -q, --quiet           Quiet mode
  --dry-run             Parse only, don't execute
  --help                Show help

Exit Codes:
  0  Success
  1  Config error
  3  Task failed
  4  Gate failed
  5  Verification failed
  7  User abort
```

---

*End of CLI Contract Specification*
