# Workflow Assets Inventory Summary

**Date:** 2026-01-25  
**Last Updated:** 2026-01-25  
**Status:** Module Design Complete  
**Repositories Analyzed:**
- MongoDB-RAG-Agent (`ralph-verified.sh` + commands + UI tests)
- compound-product (autopilot + skills + loop)

---

## Canonical Artifacts (Finalized)

The canonical artifacts and conventions have been finalized. All schemas, templates, and documentation are complete.

### Specifications

| Document | Description |
|----------|-------------|
| [specs/canonical-artifacts.md](../specs/canonical-artifacts.md) | Complete specification for all artifacts (~1100 lines) |
| [specs/design-decisions.md](../specs/design-decisions.md) | Key design decisions and rationale |
| [specs/module-design.md](../specs/module-design.md) | **NEW** - Python module boundaries and interfaces (~1000 lines) |
| [specs/cli-contract.md](../specs/cli-contract.md) | CLI command reference |
| [specs/markdown-import-export.md](../specs/markdown-import-export.md) | CR/PRD markdown compatibility |

### JSON Schemas

| Schema | Description |
|--------|-------------|
| [schemas/prd.schema.json](../schemas/prd.schema.json) | JSON Schema for `.ralph/prd.json` validation |
| [schemas/session.schema.json](../schemas/session.schema.json) | JSON Schema for session state files |
| [schemas/ralph-config.schema.json](../schemas/ralph-config.schema.json) | JSON Schema for `.ralph/ralph.yml` validation |
| [schemas/autopilot.schema.json](../schemas/autopilot.schema.json) | JSON Schema for autopilot artifacts (analysis.json, run records) |

### Templates

| Template | Description |
|----------|-------------|
| [templates/.ralph/ralph.yml.minimal](../templates/.ralph/ralph.yml.minimal) | Minimal configuration (any stack) |
| [templates/.ralph/ralph.yml.python](../templates/.ralph/ralph.yml.python) | Python-only projects (pytest, mypy, ruff) |
| [templates/.ralph/ralph.yml.node](../templates/.ralph/ralph.yml.node) | Node.js/TypeScript projects (npm, tsc) |
| [templates/.ralph/ralph.yml.fullstack](../templates/.ralph/ralph.yml.fullstack) | Python backend + Node frontend |
| [templates/.ralph/prd.json.template](../templates/.ralph/prd.json.template) | Task list template |
| [templates/.ralph/progress.txt.template](../templates/.ralph/progress.txt.template) | Progress log template |
| [templates/AGENTS.md.template](../templates/AGENTS.md.template) | Agent memory template |

### Examples

| Example | Description |
|---------|-------------|
| [examples/prd-example-authentication.json](../examples/prd-example-authentication.json) | Complete 10-task authentication feature |

### User Documentation

| Document | Description |
|----------|-------------|
| [docs/how-to-setup-repository.md](../docs/how-to-setup-repository.md) | User guide for repository setup |
| [docs/how-to-create-tasks.md](../docs/how-to-create-tasks.md) | User guide for task creation |
| [docs/how-to-use-cli.md](../docs/how-to-use-cli.md) | User guide for CLI commands |
| [docs/artifacts-quick-reference.md](../docs/artifacts-quick-reference.md) | Condensed reference card for all artifacts |
| [docs/architecture-diagram.md](../docs/architecture-diagram.md) | **NEW** - Visual architecture diagrams |

---

## Quick Reference: Core vs Config Classification

### CORE (Universal Engine Logic)

These components will be implemented in the `ralph` Python package:

| Component | Source | Description |
|-----------|--------|-------------|
| **Session Management** | MongoDB-RAG | Token generation, checksum, artifacts |
| **Signal Validation** | MongoDB-RAG | `<task-done>`, `<tests-done>`, `<review-*>` parsing |
| **Task Loop** | Both | Iterate until all tasks pass |
| **Service Lifecycle** | MongoDB-RAG | Start/stop/health check (commands = config) |
| **Gate Runner** | MongoDB-RAG | Execute gates with fail-fast, timeout |
| **Test Path Guardrails** | MongoDB-RAG | Whitelist validation, auto-revert |
| **Agent Role Execution** | MongoDB-RAG | Invoke Claude with role-specific constraints |
| **UI Test Wrappers** | MongoDB-RAG | agent-browser and Robot Framework runners |
| **Fix Loops** | MongoDB-RAG | Plan → Implement → Verify cycle |
| **Report Analysis** | Compound | Multi-provider LLM analysis |
| **PRD Generation** | Compound | Self-clarify → structure → output |
| **Task Generation** | Compound | Explode PRD into granular tasks |
| **Progress Tracking** | Compound | Append-only log, codebase patterns |
| **Autopilot Pipeline** | Compound | Report → Branch → PRD → Tasks → Loop → PR |

### CONFIG (Repo-Specific)

These go into `.ralph/ralph.yml` per repository:

| Configuration | Source | Example Values |
|---------------|--------|----------------|
| **Service Commands** | MongoDB-RAG | `uv run uvicorn...`, `npm run dev` |
| **Health Endpoints** | MongoDB-RAG | `/health`, `/api/system/health` |
| **Ports** | MongoDB-RAG | 8000, 5173 |
| **Gate Definitions** | MongoDB-RAG | pytest, mypy, tsc, lint, build |
| **Test Path Patterns** | MongoDB-RAG | `tests/**`, `frontend/**/*.test.*` |
| **UI Test Scripts** | MongoDB-RAG | `smoke_test.sh`, `smoke_dashboard.robot` |
| **Agent Models** | Both | `claude-opus-4-5`, `haiku` |
| **Iteration Limits** | Both | 30, 10, 25 |
| **Reports Directory** | Compound | `./reports` |
| **Branch Prefix** | Compound | `compound/` |
| **Quality Checks** | Compound | `npm run typecheck`, `npm test` |
| **Analysis Provider** | Compound | `anthropic`, `openai`, `gateway` |

---

## Component Inventory Matrix

### 1. Orchestration Engine

| Feature | MongoDB-RAG-Agent | Compound Product | Universal Ralph |
|---------|-------------------|------------------|-----------------|
| Entry point | `ralph-verified.sh` | `auto-compound.sh` | `ralph run` / `ralph autopilot` |
| Task source | CR markdown (JSON block) | `prd.json` file | Both (config selects) |
| Task format | `passes: true/false` | `passes: true/false` | Unified schema |
| Status updates | Script-only (checksum) | Agent updates file | Script-only (safer) |
| Completion signal | `<task-done session="...">` | `<promise>COMPLETE</promise>` | Tokenized signals |

### 2. Agent Roles

| Role | MongoDB-RAG-Agent | Compound Product | Universal Ralph |
|------|-------------------|------------------|-----------------|
| Implementation | Yes (full tools) | Yes (single agent) | Yes |
| Test Writing | Yes (guardrailed paths) | No (combined) | Yes |
| Review | Yes (read-only) | No | Yes |
| Runtime Fix | Yes | No | Yes |
| UI Planning | Yes (read-only) | No | Yes |
| UI Implementation | Yes | No | Yes |

### 3. Verification Gates

| Gate Type | MongoDB-RAG-Agent | Compound Product | Universal Ralph |
|-----------|-------------------|------------------|-----------------|
| Build gates | mypy, tsc, npm build | From `qualityChecks` | Configurable list |
| Test gates | pytest, lint | From `qualityChecks` | Configurable list |
| Runtime health | Backend + Frontend | No | Optional |
| UI smoke tests | agent-browser | Browser via agent | Optional |
| UI regression | Robot Framework | No | Optional |

### 4. Anti-Gaming Mechanisms

| Mechanism | MongoDB-RAG-Agent | Compound Product | Universal Ralph |
|-----------|-------------------|------------------|-----------------|
| Session tokens | Yes | No | Yes |
| Signal validation | 3 validators | Simple grep | Yes |
| Checksum verification | Yes | No | Yes |
| Script-only updates | Yes | No (agent updates) | Yes |
| Test path guardrails | Yes | No | Yes |
| Read-only review | Yes | No | Yes |

### 5. Autopilot Features

| Feature | MongoDB-RAG-Agent | Compound Product | Universal Ralph |
|---------|-------------------|------------------|-----------------|
| Report analysis | No | Yes (multi-provider) | Yes |
| Branch creation | No | Yes | Yes |
| PRD generation | Via command (interactive) | Via skill (autonomous) | Both modes |
| Task generation | Via command | Via skill | Unified |
| PR creation | No | Yes (gh CLI) | Yes |
| Run archiving | No | Yes | Yes |
| Progress memory | Session artifacts | progress.txt | Both |

---

## Prompt Templates Inventory

### From MongoDB-RAG-Agent

| Template | Purpose | Parameterized |
|----------|---------|---------------|
| Implementation | Task implementation with session token | `{{SESSION_TOKEN}}`, `{{TASK_INFO}}`, `{{PREVIOUS_FEEDBACK}}` |
| Test Writing | Write tests with path constraints | `{{SESSION_TOKEN}}`, `{{TASK_INFO}}`, `{{IMPL_OUTPUT}}` |
| Review | Read-only code review | `{{SESSION_TOKEN}}`, `{{TASK_INFO}}`, `{{IMPL_OUTPUT}}`, `{{TEST_RESULTS}}` |
| Fix Runtime | Fix build/runtime errors | `{{SESSION_TOKEN}}`, `{{ERROR_TYPE}}`, `{{ERROR_OUTPUT}}` |
| UI Planning | Plan UI fixes (read-only) | `{{SESSION_TOKEN}}`, `{{FAILURES}}`, `{{SNAPSHOTS}}` |
| UI Implementation | Implement UI fixes | `{{SESSION_TOKEN}}`, `{{PLAN}}`, `{{FAILURES}}` |
| Robot Planning | Plan Robot test fixes | `{{SESSION_TOKEN}}`, `{{FAILURES}}`, `{{ROBOT_LOG}}` |
| Robot Implementation | Fix Robot test failures | `{{SESSION_TOKEN}}`, `{{PLAN}}`, `{{FAILURES}}` |

### From Compound Product

| Template | Purpose | Parameterized |
|----------|---------|---------------|
| Analysis | Pick #1 priority from report | `{{REPORT_CONTENT}}`, `{{RECENT_FIXES}}` |
| PRD Generation | Create PRD from requirements | `{{PRIORITY_ITEM}}`, `{{DESCRIPTION}}`, `{{ACCEPTANCE_CRITERIA}}` |
| Task Generation | Convert PRD to prd.json | `{{PRD_PATH}}`, `{{BRANCH_NAME}}` |
| Iteration | Execute single task | `{{CONFIG}}`, `{{PRD}}`, `{{PROGRESS}}` |

### Skills (Claude/Agent Skills)

| Skill | Source | Purpose |
|-------|--------|---------|
| agent-browser | MongoDB-RAG-Agent | Browser automation for UI testing (50+ commands documented) |
| prd | Compound Product | Autonomous PRD generation with self-clarification |
| tasks | Compound Product | Convert PRD to granular prd.json tasks |

---

## Task Schema Comparison

### MongoDB-RAG-Agent (CR Markdown)

```json
{
  "category": "setup",
  "description": "Task description here",
  "steps": ["Step 1", "Step 2"],
  "passes": false
}
```

**Note:** No explicit `id` field; uses `description` as identifier.

### Compound Product (prd.json)

```json
{
  "id": "T-001",
  "title": "Short title",
  "description": "What to do and why",
  "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
  "priority": 1,
  "passes": false,
  "notes": ""
}
```

### Universal Ralph (Unified)

```json
{
  "id": "T-001",
  "title": "Short title",
  "description": "What to do and why",
  "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
  "priority": 1,
  "passes": false,
  "notes": "",
  "subtasks": []  // Optional extension
}
```

**Compatibility:** Ralph will support both formats:
- `prd.json` as primary (Compound style)
- Markdown JSON blocks as compatibility layer (MongoDB-RAG style)

---

## Configuration Schema

### Proposed `.ralph/ralph.yml`

```yaml
version: "1"

# ============================================================
# TASK SOURCE
# ============================================================
task_source:
  type: prd_json          # prd_json | cr_markdown
  path: .ralph/prd.json   # or changes/CR-*.md

# ============================================================
# SERVICES (for runtime verification)
# ============================================================
services:
  backend:
    start:
      dev: "uv run uvicorn src.api.main:app --reload --port {port}"
      prod: "uv run uvicorn src.api.main:app --port {port}"
    port: 8000
    health:
      - /health
      - /api/system/health
    timeout: 30

  frontend:
    build: "cd frontend && npm run build"
    serve:
      dev: "cd frontend && npm run dev -- --port {port}"
      prod: "cd frontend && npm run preview -- --port {port}"
    port: 5173
    timeout: 30

# ============================================================
# GATES
# ============================================================
gates:
  build:
    - name: mypy
      cmd: "uv run mypy src/"
      when: pyproject.toml
    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      when: frontend/package.json

  full:
    - name: pytest
      cmd: "uv run pytest -x"
      when: pyproject.toml
    - name: lint
      cmd: "cd frontend && npm run lint"
      when: frontend/package.json
    - name: build
      cmd: "cd frontend && npm run build"
      when: frontend/package.json

# ============================================================
# TEST PATH GUARDRAILS
# ============================================================
test_paths:
  - tests/**
  - test_scripts/**
  - frontend/**/__tests__/**
  - frontend/**/*.test.*
  - frontend/**/*.spec.*

# ============================================================
# UI VERIFICATION
# ============================================================
ui:
  agent_browser:
    enabled: true
    script: ui_tests/agent-browser/smoke_test.sh

  robot:
    enabled: true
    suite: ui_tests/robot
    variables:
      HEADLESS: true

# ============================================================
# AGENT CONFIGURATION
# ============================================================
agents:
  implementation:
    model: claude-opus-4-5-20251101
  test_writing:
    model: claude-sonnet-4-5-20250929
  review:
    model: haiku
  fix:
    model: claude-sonnet-4-5-20250929
  planning:
    model: claude-sonnet-4-5-20250929

# ============================================================
# LIMITS
# ============================================================
limits:
  claude_timeout: 1800
  max_iterations: 30
  post_verify_iterations: 10
  ui_fix_iterations: 10
  robot_fix_iterations: 10

# ============================================================
# AUTOPILOT (Compound-style self-improve)
# ============================================================
autopilot:
  enabled: true
  reports_dir: ./reports
  branch_prefix: ralph/
  create_pr: true

  analysis:
    provider: anthropic  # anthropic | openai | openrouter | gateway
    model: claude-opus-4-5-20251101
    recent_days: 7

  prd:
    mode: autonomous  # autonomous | interactive
    output_dir: ./tasks

  tasks:
    output: .ralph/prd.json
    min_count: 8
    max_count: 15

  memory:
    progress: .ralph/progress.txt
    archive: .ralph/archive

# ============================================================
# GIT / PR
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

---

## File Migration Plan

### Files to Move to Ralph Package

| Source File | Destination | Classification |
|-------------|-------------|----------------|
| `ralph-verified.sh` (session mgmt) | `ralph/session.py` | Core |
| `ralph-verified.sh` (signals) | `ralph/signals/validators.py` | Core |
| `ralph-verified.sh` (services) | `ralph/services/lifecycle.py` | Core |
| `ralph-verified.sh` (gates) | `ralph/gates/runner.py` | Core |
| `ralph-verified.sh` (UI loops) | `ralph/ui/fix_loop.py` | Core |
| `prompts/*.md` | `ralph/agents/templates/` | Core |
| `analyze-report.sh` | `ralph/autopilot/analyzer.py` | Core |
| `auto-compound.sh` | `ralph/autopilot/pipeline.py` | Core |
| `loop.sh` | (merged into run command) | Core |
| `skills/prd/SKILL.md` | `ralph/skills/prd.py` | Core |
| `skills/tasks/SKILL.md` | `ralph/skills/tasks.py` | Core |

### Files to Keep as Examples

| File | Purpose |
|------|---------|
| `.claude/commands/create-prd.md` | Interactive PRD creation |
| `.claude/commands/create-change-request.md` | Interactive CR creation |
| `ui_tests/robot/smoke_dashboard.robot` | Robot test example |
| `examples/sample-tasks.json` | prd.json schema example |

### Files to Remove After Migration

| File | Reason |
|------|--------|
| `ralph-verified.sh` | Replaced by `ralph run` |
| `ralph-cr.sh` | Replaced by `ralph run --cr` |
| `ralph.sh` | Superseded |
| `PROMPT.md` | Replaced by ralph templates |

---

## Next Steps

### Completed
- [x] Design orchestrator module boundaries → [specs/module-design.md](../specs/module-design.md)
- [x] Create architecture diagrams → [docs/architecture-diagram.md](../docs/architecture-diagram.md)

### In Progress / Upcoming
1. **Create ralph package structure** with module stubs
2. **Implement session management** (token, checksum, artifacts)
   - See: [module-design.md#31-session-module](../specs/module-design.md#31-session-module)
3. **Implement signal validators** (task-done, tests-done, review)
   - See: [module-design.md#334-signal-validation](../specs/module-design.md#334-signal-validation)
4. **Implement config loader** (parse ralph.yml)
   - See: [module-design.md#39-config-module](../specs/module-design.md#39-config-module)
5. **Implement task parser** (prd.json + markdown compat)
   - See: [module-design.md#32-tasks-module](../specs/module-design.md#32-tasks-module)
6. **Implement gate runner** (with conditions, timeout)
   - See: [module-design.md#35-gates-module](../specs/module-design.md#35-gates-module)
7. **Implement service lifecycle** (start, health, stop)
   - See: [module-design.md#36-services-module](../specs/module-design.md#36-services-module)
8. **Implement agent executor** (Claude CLI wrapper)
   - See: [module-design.md#34-exec-module](../specs/module-design.md#34-exec-module)
9. **Implement UI test wrappers** (agent-browser, Robot)
   - See: [module-design.md#37-ui-module](../specs/module-design.md#37-ui-module)
10. **Implement autopilot pipeline** (analysis → PRD → tasks → loop)
11. **Create CLI commands** (init, run, verify, autopilot)
    - See: [module-design.md#310-cli-module](../specs/module-design.md#310-cli-module)
12. **Add unit tests** with mock Claude
    - See: [module-design.md#8-testing-strategy](../specs/module-design.md#8-testing-strategy)
13. **Create fixture repos** for integration tests
14. **Migrate MongoDB-RAG-Agent** as first consumer
