# Ralph Orchestrator: Design Decisions

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Canonical Reference

This document captures the key design decisions and rationale for the Ralph orchestrator's canonical artifacts and conventions.

---

## Table of Contents

1. [Task Format: Why prd.json](#1-task-format-why-prdjson)
2. [Session Token Anti-Gaming](#2-session-token-anti-gaming)
3. [Script-Controlled State](#3-script-controlled-state)
4. [Checksum Tamper Detection](#4-checksum-tamper-detection)
5. [Test Path Guardrails](#5-test-path-guardrails)
6. [Agent Role Separation](#6-agent-role-separation)
7. [Memory: AGENTS.md vs progress.txt](#7-memory-agentsmd-vs-progresstxt)
8. [Configuration Over Convention](#8-configuration-over-convention)
9. [Acceptance Criteria Patterns](#9-acceptance-criteria-patterns)
10. [Session vs Permanent Artifacts](#10-session-vs-permanent-artifacts)

---

## 1. Task Format: Why prd.json

### Decision
Use JSON (`prd.json`) as the canonical task format instead of markdown.

### Alternatives Considered
- **Markdown with embedded JSON**: Used by MongoDB-RAG-Agent CR files
- **Pure markdown checklist**: Human-readable but fragile parsing
- **YAML**: Human-readable but less precise for nested structures

### Rationale
1. **Machine-readable**: No regex/grep heuristics needed for parsing
2. **Schema-validatable**: JSON Schema catches errors before execution
3. **Stable IDs**: Each task has a unique `id` field for reliable status tracking
4. **Subtask support**: Nested structure naturally supports task decomposition
5. **Compound compatibility**: Aligns with existing Compound Product format

### Compatibility
Markdown JSON blocks remain supported as an import/export layer for existing CR workflows.

---

## 2. Session Token Anti-Gaming

### Decision
Each run generates a unique session token that agents must include in completion signals.

### Format
```
ralph-YYYYMMDD-HHMMSS-[hex-suffix]
```

Example: `ralph-20260125-143052-a7b3c9f2d1e8`

### Rationale
Prevents agents from:
1. **Copying signals** from previous runs or examples
2. **Pre-generating signals** before completing work
3. **Gaming completion detection** by outputting expected patterns

### Implementation
- Token generated at session start, stored in `session.json`
- Passed to agents as a parameter in prompts
- Validated by script when parsing agent output
- Invalid tokens cause signal rejection, not task completion

---

## 3. Script-Controlled State

### Decision
Only the orchestrator script can modify task `passes` status. Agents cannot directly update task files.

### Alternatives Considered
- **Agent updates file directly**: Simpler but gameable
- **Agent proposes, human approves**: Too slow for automation

### Rationale
1. **Anti-gaming**: Agents can't mark tasks complete without verification
2. **Audit trail**: All status changes logged by script with timestamps
3. **Verification**: Script runs gates BEFORE updating status
4. **Rollback**: Script can revert status if post-completion verification fails

### Signal Flow
```
Agent outputs <task-done session="...">
    ↓
Script validates session token
    ↓
Script runs quality gates
    ↓
Script updates prd.json passes=true
    ↓
Script updates checksum
```

---

## 4. Checksum Tamper Detection

### Decision
Use SHA-256 checksum to detect unauthorized modifications to task status.

### Implementation
```bash
# After any status change:
sha256sum .ralph-session/task-status.json > .ralph-session/task-status.sha256

# Before reading status:
expected=$(cat .ralph-session/task-status.sha256)
actual=$(sha256sum .ralph-session/task-status.json)
[ "$expected" = "$actual" ] || abort
```

### Rationale
1. **Detects tampering**: Any edit changes the hash
2. **Cheap verification**: SHA-256 is fast
3. **Transparent**: Human-readable JSON, checksum in separate file
4. **Session-scoped**: Resets each run, no accumulation issues

### Behavior on Mismatch
Abort run with clear error message. Assume either:
- Agent modified status file (violation)
- Concurrent modification (race condition)

---

## 5. Test Path Guardrails

### Decision
Test-writing agent is restricted to modifying files matching configured glob patterns.

### Default Patterns
```yaml
test_paths:
  - tests/**
  - **/*.test.*
  - **/*.spec.*
  - **/__tests__/**
```

### Rationale
1. **Scope control**: Test agent shouldn't modify production code
2. **Role separation**: Implementation and test roles have clear boundaries
3. **Revertable**: If test agent modifies disallowed files, script reverts them
4. **Configurable**: Projects can add paths (e.g., `cypress/**`, `e2e/**`)

### Enforcement
Script captures `git status` before test agent runs, reverts any files outside allowed patterns.

---

## 6. Agent Role Separation

### Decision
Define distinct agent roles with different tool permissions and prompts.

### Roles

| Role | Purpose | Tools |
|------|---------|-------|
| **Implementation** | Implement task requirements | All |
| **Test Writing** | Write tests for implementation | Read, Write, Edit (guardrailed paths) |
| **Review** | Code review, acceptance check | Read-only |
| **Fix** | Fix runtime/build errors | All |
| **Planning** | Plan UI/test fixes | Read-only |

### Rationale
1. **Least privilege**: Review agent can't modify code
2. **Focused prompts**: Each role has optimized instructions
3. **Auditability**: Logs show which role made which changes
4. **Specialization**: Different models can be used per role (e.g., cheaper model for review)

---

## 7. Memory: AGENTS.md vs progress.txt

### Decision
Maintain two separate memory files with different purposes.

### AGENTS.md
- **Location**: Project root (committed)
- **Purpose**: Codebase patterns, conventions, architecture
- **Update style**: Sections updated in place
- **Audience**: All agents, all runs

### progress.txt
- **Location**: `.ralph/progress.txt` (committed)
- **Purpose**: What was done, verification results, learnings
- **Update style**: Append-only, reverse chronological
- **Audience**: Primarily autopilot continuity

### Rationale
1. **Separation of concerns**: Patterns vs history
2. **Different lifecycles**: Patterns evolve, history accumulates
3. **Different audiences**: General context vs task-specific learnings
4. **Git-friendly**: Both are committed, AGENTS.md for team, progress.txt for automation

---

## 8. Configuration Over Convention

### Decision
Use explicit configuration (`.ralph/ralph.yml`) rather than convention-based discovery.

### Alternatives Considered
- **Convention only**: Detect `pyproject.toml` → assume pytest, etc.
- **Plugin architecture**: Extensible but complex

### Rationale
1. **Explicit > implicit**: No surprises from auto-detection
2. **Override-friendly**: Any setting can be customized
3. **Portable**: Same config format across all project types
4. **Documented**: Config file serves as documentation of project setup
5. **Validatable**: JSON Schema validates configuration at startup

### Defaults
Templates provide sensible defaults; `ralph init` detects project type and generates appropriate config.

---

## 9. Acceptance Criteria Patterns

### Decision
Define standard patterns for verifiable acceptance criteria.

### Patterns

| Type | Pattern | Example |
|------|---------|---------|
| Command | `Run \`cmd\` - exits with code 0` | `Run \`npm test\` - exits with code 0` |
| File exists | `File \`path\` exists` | `File \`src/auth.py\` exists` |
| File contains | `File \`path\` contains \`string\`` | `File \`config.py\` contains \`JWT_SECRET\`` |
| API | `METHOD /url returns status` | `POST /api/login returns 200` |
| Browser | `agent-browser: action - result` | `agent-browser: click "Submit" - redirects` |

### Rationale
1. **Machine-verifiable**: Script can check each criterion
2. **Consistent**: Standard patterns across all projects
3. **Actionable**: Agents know exactly what to verify
4. **Boolean**: Each criterion is pass/fail, no ambiguity

### Anti-patterns
Avoid subjective criteria like "code is clean" or "works correctly" that can't be machine-verified.

---

## 10. Session vs Permanent Artifacts

### Decision
Separate transient session state from permanent project artifacts.

### Session (`.ralph-session/`)
- Created fresh each run
- Contains: token, status checksum, logs, screenshots, PIDs
- **Not committed** to git
- Deleted or archived after run

### Permanent (`.ralph/`)
- Persists across runs
- Contains: config, tasks, progress
- **Committed** to git
- Represents project state

### Rationale
1. **Clean runs**: Each session starts fresh, no stale state
2. **Debugging**: Session artifacts available for post-mortem
3. **No bloat**: Transient files don't accumulate in git
4. **Team visibility**: Config and tasks visible in version control

### .gitignore
```gitignore
# Session (transient)
.ralph-session/

# Keep permanent artifacts
# .ralph/ralph.yml
# .ralph/prd.json
# .ralph/progress.txt
# AGENTS.md
```

---

## Summary: Design Principles

1. **Anti-gaming by design**: Tokens, checksums, script-controlled state
2. **Machine-verifiable**: JSON schemas, verifiable acceptance criteria
3. **Role separation**: Distinct agent roles with appropriate permissions
4. **Configuration over convention**: Explicit settings, validatable schemas
5. **Append-only memory**: Progress accumulates, never overwrites
6. **Session isolation**: Clean state each run, permanent artifacts persist

---

*End of Design Decisions Document*
