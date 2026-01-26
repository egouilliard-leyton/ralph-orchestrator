# MongoDB-RAG-Agent Workflow Assets Inventory

**Date:** 2026-01-25  
**Last Updated:** 2026-01-25 (inventory-current task)  
**Purpose:** Analyze current workflow assets and classify each element as either **Core Orchestrator Logic** (universal) or **Repo-Specific Configuration**.

---

## Summary

| Category | Core (Universal) | Config (Repo-Specific) |
|----------|------------------|------------------------|
| Session Management | 7 functions | 2 env vars |
| Service Lifecycle | 6 functions | 5+ settings |
| Task Management | 4 functions | 2 formats |
| Agent Roles | 8 agent types | Prompts customizable |
| Test Gates | 1 runner | 5 gate definitions |
| UI Testing | 2 frameworks | Paths, URLs, tests |
| Signal Validation | 3 validators | Token format |

---

## 1. Ralph Scripts

### 1.1 `ralph-verified.sh` (Main Workflow - 2573 lines)

This is the primary workflow script. Below is a breakdown of its sections:

#### SESSION MANAGEMENT (Lines 107-176) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `generate_session_token()` | Creates unique per-run token using timestamp + random data | **Core** |
| `init_session()` | Creates session directory, writes session.json, task-status.json | **Core** |
| `update_checksum()` | SHA-256 checksum of task-status.json for tamper detection | **Core** |
| `verify_checksum()` | Validates checksum hasn't been modified by agent | **Core** |

**Config extracted:**
- `SESSION_DIR` path (default: `.ralph-session`)

#### SERVICE LIFECYCLE (Lines 178-354) → **MIXED**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `init_service_dirs()` | Creates pid/log/ui artifact directories | **Core** |
| `cleanup_services()` | Kills backend/frontend processes, clears ports | **Core** |
| `start_backend()` | Starts backend with uvicorn | **Config** (command) |
| `start_frontend()` | Builds and serves frontend | **Config** (command) |
| `wait_for_backend()` | Polls health endpoint | **Core** (URL = config) |
| `wait_for_frontend()` | Polls frontend URL | **Core** (URL = config) |
| `check_backend_detailed_health()` | Checks `/health` and `/api/system/health` | **Config** (endpoints) |

**Config extracted:**
```yaml
services:
  backend:
    start_cmd: "uv run uvicorn src.api.main:app --host 127.0.0.1 --port {port}"
    health_urls:
      - "/health"
      - "/api/system/health"
    port: 8000
  frontend:
    build_cmd: "cd frontend && npm run build"
    serve_cmd: "cd frontend && npm run preview -- --host 127.0.0.1 --port {port}"
    dev_cmd: "cd frontend && npm run dev -- --host 127.0.0.1 --port {port}"
    port: 5173
```

#### RUNTIME FIX LOOP (Lines 356-566) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `generate_fix_runtime_prompt()` | Creates prompt for fix agent with error context | **Core** (template) |
| `run_build_gates()` | Runs mypy, tsc, npm build in sequence | **Config** (gate list) |
| `run_runtime_verification()` | Start services + health checks | **Core** |
| `run_runtime_fix_loop()` | Iterative fix loop with max iterations | **Core** |

**Config extracted:**
```yaml
gates:
  build:
    - name: mypy
      cmd: "uv run mypy src/ --ignore-missing-imports --no-error-summary"
      condition: "file_exists(pyproject.toml)"
    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      condition: "file_exists(frontend/package.json)"
    - name: npm-build
      cmd: "cd frontend && npm run build"
      condition: "file_exists(frontend/package.json)"
```

#### UI SMOKE TESTING - AGENT-BROWSER (Lines 568-1062) → **MIXED**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `ab()` | Wrapper for agent-browser with session | **Core** |
| `ui_open()` | Opens frontend URL | **Core** (URL = config) |
| `ui_snapshot_and_screenshot()` | Captures accessibility tree + screenshot | **Core** |
| `ui_click_tab()` | Clicks navigation tab by name | **Core** |
| `ui_get_visible_main_text_count()` | JS eval to count visible text in `<main>` | **Core** |
| `ui_assert_dashboard_not_blank()` | Validates dashboard has content | **Config** (assertion) |
| `check_agent_browser()` | Checks if agent-browser CLI installed | **Core** |
| `run_ui_smoke_tests()` | Runs 6 specific UI tests | **Config** (test list) |
| `run_ui_test_*()` | Individual test implementations | **Config** (repo-specific) |

**Config extracted:**
```yaml
ui_tests:
  agent_browser:
    enabled: true
    tests:
      - name: app_load
        action: open
        assert: "navigation|header|sidebar|button"
      - name: dashboard
        action: click_tab("Dashboard")
        assert: "Dashboard heading + content count > 2"
      - name: projects
        action: click_tab("Q&A")
        assert: "project|create|select"
      # ... more tests
```

#### ROBOT FRAMEWORK TESTING (Lines 665-769) → **MIXED**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `check_robot_browser()` | Checks robotframework-browser installed | **Core** |
| `run_robot_tests()` | Runs Robot Framework with variables | **Core** |

**Config extracted:**
```yaml
ui_tests:
  robot:
    enabled: true
    suite_path: "ui_tests/robot"
    variables:
      BASE_URL: "http://127.0.0.1:{frontend_port}"
      HEADLESS: true
```

#### UI/ROBOT FIX LOOPS (Lines 1064-1441) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `generate_ui_planning_prompt()` | Creates read-only planning prompt | **Core** (template) |
| `generate_ui_impl_prompt()` | Creates implementation prompt with plan | **Core** (template) |
| `run_ui_fix_loop()` | Plan→Implement→Verify loop for agent-browser | **Core** |
| `generate_robot_planning_prompt()` | Robot-specific planning prompt | **Core** (template) |
| `generate_robot_impl_prompt()` | Robot-specific impl prompt | **Core** (template) |
| `run_robot_fix_loop()` | Plan→Implement→Verify loop for Robot | **Core** |

#### POST-COMPLETION VERIFICATION (Lines 1443-1651) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `run_post_completion_verification()` | Orchestrates Phase 1→2→3 verification | **Core** |
| `print_post_verify_success_banner()` | Success output with mode info | **Core** |
| `print_post_verify_failure_banner()` | Failure output with debug paths | **Core** |

#### TEST GATES (Lines 1653-1735) → **MIXED**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `run_test_gates()` | Runs pytest, mypy, tsc, lint, build | **Config** (gate list) |

**Config extracted:**
```yaml
gates:
  full:
    - name: pytest
      cmd: "uv run pytest -x --tb=short -q"
      condition: "file_exists(pyproject.toml)"
    - name: mypy
      cmd: "uv run mypy src/ --ignore-missing-imports --no-error-summary"
      condition: "file_exists(pyproject.toml)"
    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      condition: "file_exists(frontend/package.json)"
    - name: lint
      cmd: "cd frontend && npm run lint"
      condition: "file_exists(frontend/package.json)"
    - name: build
      cmd: "cd frontend && npm run build"
      condition: "file_exists(frontend/package.json)"
```

#### AGENT PROMPTS (Lines 1737-1905) → **CORE (Templates)**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `generate_impl_prompt()` | Implementation agent prompt with session token | **Core** (template) |
| `generate_test_prompt()` | Test-writing agent prompt with path guardrails | **Core** (template) |
| `generate_review_prompt()` | Review agent prompt (read-only) | **Core** (template) |

**Config extracted:**
```yaml
agents:
  implementation:
    model: "${IMPL_MODEL:-claude-opus-4-5-20251101}"
    timeout: 1800
    allowed_tools: [] # all tools
  test_writing:
    model: "${TEST_MODEL:-claude-sonnet-4-5-20250929}"
    timeout: 1800
    allowed_tools: ["Read", "Grep", "Glob", "Edit", "Write"]
  review:
    model: "${REVIEW_MODEL:-haiku}"
    timeout: 1800
    allowed_tools: ["Read", "Grep", "Glob"]
  fix_runtime:
    model: "${FIX_MODEL:-claude-sonnet-4-5-20250929}"
    timeout: 1800
  planning:
    model: "${PLAN_MODEL:-claude-sonnet-4-5-20250929}"
    timeout: 1800
    allowed_tools: ["Read", "Grep", "Glob"]
```

#### TEST AGENT GUARDRAILS (Lines 1907-1945) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `is_allowed_test_path()` | Validates path matches test patterns | **Core** (patterns = config) |
| `snapshot_modified_paths()` | Gets git diff + untracked files | **Core** |
| `revert_path_if_untracked_or_tracked()` | Reverts unauthorized changes | **Core** |

**Config extracted:**
```yaml
test_paths:
  allowed:
    - "tests/**"
    - "test_scripts/**"
    - "frontend/**/__tests__/**"
    - "frontend/**/*.test.*"
    - "frontend/**/*.spec.*"
    - "frontend/**/cypress/**"
    - "frontend/**/playwright/**"
    - "frontend/**/e2e/**"
```

#### TASK MANAGEMENT (Lines 1947-2122) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `get_next_pending_task()` | Parses CR to find next `passes: false` task | **Core** |
| `count_tasks()` | Counts completed/pending tasks | **Core** |
| `mark_task_complete()` | Updates CR file, session status, checksum | **Core** |

**Task Format Support:**
- `"passes": false/true` (create-prd.md format)
- `"status": "pending"/"completed"` (alternative format)
- Task ID from `"id"` field or `"description"` fallback

#### SIGNAL VALIDATION (Lines 2124-2202) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `validate_task_done_signal()` | Validates `<task-done session="...">` | **Core** |
| `validate_tests_done_signal()` | Validates `<tests-done session="...">` | **Core** |
| `validate_review_signal()` | Validates `<review-approved/rejected>` | **Core** |

#### MAIN LOOP (Lines 2204-2569) → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| `main()` | Orchestrates the full workflow | **Core** |
| `print_success_banner()` | Success output | **Core** |
| `print_max_iterations_banner()` | Max iterations output | **Core** |

---

### 1.2 `ralph-cr.sh` (Simpler CR Loop - 340 lines)

A simpler variant without multi-agent verification. Uses:
- Single prompt template (inline)
- `<promise>CR_COMPLETE</promise>` completion signal
- Task counting via grep

**Classification:** Legacy/simpler mode. Core loop logic is similar but without:
- Session tokens
- Separate test/review agents
- Post-completion verification

---

### 1.3 `ralph.sh` (Original PRD Loop - 135 lines)

The original PRD-based loop. Uses:
- `PROMPT.md` as the prompt source
- `<promise>COMPLETE</promise>` completion signal
- No verification gates

**Classification:** Legacy. Superseded by `ralph-verified.sh`.

---

### 1.4 `start_backend.sh` / `start_frontend.sh`

Simple convenience scripts:

**start_backend.sh:**
```bash
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**start_frontend.sh:**
```bash
cd frontend && npm install --legacy-peer-deps && npm run dev
```

**Classification:** **Config** - These become entries in `.ralph/ralph.yml`.

---

## 2. Claude Commands

### 2.1 `.claude/commands/create-prd.md`

**Purpose:** Interactive PRD creation with discovery questions.

**Key Features:**
- 11-question discovery flow using `AskUserQuestion`
- Tech stack research via `WebSearch`/`WebFetch`
- Generates `prd.md` with JSON task list
- Updates `PROMPT.md` and `.claude/settings.json`

**Classification:** **Core** (generic)  
This command is already repo-agnostic. It discovers project requirements and generates:
- `prd.md` - PRD with task list
- `activity.md` - Activity log
- Updated `.claude/settings.json` permissions

---

### 2.2 `.claude/commands/create-change-request.md`

**Purpose:** Interactive Change Request creation for existing codebases.

**Key Features:**
- 10-question discovery flow
- Codebase exploration via `Task` tool
- Generates `changes/CR-[NAME].md` with task list
- Supports bug fixes, features, refactoring, performance, security

**Classification:** **Core** (generic)  
This command is already repo-agnostic. It works with any codebase.

---

## 3. UI Test Assets

### 3.1 Agent-Browser Tests

**Location:** `ui_tests/agent-browser/`

| File | Purpose | Classification |
|------|---------|----------------|
| `smoke_test.sh` | Main test script with 5 UI tests | **Config** (repo-specific tests) |
| `run_tests.sh` | Wrapper to check agent-browser installed | **Core** |

**Tests in `smoke_test.sh`:**
1. `test_app_loads()` - Verifies app loads, looks for "Q&A System"
2. `test_tab("Q&A", ...)` - Clicks Q&A tab
3. `test_tab("Documents", ...)` - Clicks Documents tab
4. `test_tab("Ingestion", ...)` - Clicks Ingestion tab
5. `test_dashboard_not_blank()` - Critical assertion for Dashboard

**Config extracted:**
```yaml
ui_tests:
  agent_browser:
    enabled: true
    base_url: "http://127.0.0.1:5173"
    tests:
      - name: app_loads
        expected: "Q&A System"
      - name: qa_tab
        click: "Q&A"
        expected: "QuestionInput|Ask a question"
      - name: documents_tab
        click: "Documents"
        expected: "Upload|Document List"
      - name: ingestion_tab
        click: "Ingestion"
        expected: "History|Dashboard"
      - name: dashboard_not_blank
        click: "Dashboard"
        assert: "main_content_count >= 2"
```

---

### 3.2 Robot Framework Tests

**Location:** `ui_tests/robot/smoke_dashboard.robot`

**Tests:**
1. `App Loads And Main Layout Renders` - Verifies Q&A System heading, nav tabs
2. `Dashboard Tab Is Clickable` - Navigation test
3. `Dashboard Page Is Not Blank` - Critical content assertion
4. `Dashboard Shows Summary Cards Or Loading State` - Data validation

**Keywords:**
- `Open Browser To App` - Browser setup
- `Evaluate Dashboard Content Visibility` - JS eval for content count
- `Check For Dashboard Elements` - Checks for cards, charts, loading

**Classification:** **Config** (repo-specific test definitions)

**Config extracted:**
```yaml
ui_tests:
  robot:
    enabled: true
    suite_path: "ui_tests/robot"
    browser: chromium
    headless: true
    timeout: 30s
    viewport:
      width: 1280
      height: 720
```

---

### 3.3 Runner Scripts

| Script | Purpose | Classification |
|--------|---------|----------------|
| `scripts/run_ui_smoke_tests.sh` | Entry point for agent-browser tests | **Core** |
| `scripts/run_ui_robot_tests.sh` | Entry point for Robot Framework tests | **Core** |

---

## 4. Skills

### 4.1 `.claude/skills/agent-browser-skill/SKILL.md`

**Purpose:** Browser automation skill for UI testing and verification.

**Commands Documented:**

| Category | Commands |
|----------|----------|
| **Navigation** | `open`, `back`, `forward`, `reload`, `close` |
| **Snapshot** | `snapshot`, `snapshot -i` (interactive), `snapshot -c` (compact) |
| **Interactions** | `click`, `dblclick`, `fill`, `type`, `press`, `hover`, `check`, `select`, `drag` |
| **Get Info** | `get text`, `get html`, `get value`, `get attr`, `get title`, `get url`, `get count` |
| **State Checks** | `is visible`, `is enabled`, `is checked` |
| **Screenshots** | `screenshot`, `screenshot --full`, `pdf` |
| **Video** | `record start`, `record stop`, `record restart` |
| **Wait** | `wait @ref`, `wait 2000`, `wait --text`, `wait --url`, `wait --load` |
| **Semantic** | `find role button click`, `find text "..." click`, `find label "..." fill` |
| **Settings** | `set viewport`, `set device`, `set geo`, `set offline`, `set headers` |
| **Storage** | `cookies`, `cookies set`, `storage local`, `storage local set` |
| **Network** | `network route`, `network route --abort`, `network requests` |
| **Tabs** | `tab`, `tab new`, `tab close` |
| **Frames** | `frame "#iframe"`, `frame main` |
| **Debug** | `console`, `errors`, `highlight`, `trace` |

**Classification:** **Core** (skill documentation, usable in any repo)

---

## 5. Prompt Templates

### 5.1 `prompts/implementation.md`

Documents the implementation agent prompt structure with:
- Variable substitution: `{{SESSION_TOKEN}}`, `{{CR_FILE}}`, `{{TASK_INFO}}`
- Security requirements
- Completion signal format
- Anti-gaming notes

**Classification:** **Core** (template documentation)

---

### 5.2 `prompts/review.md`

Documents the review agent prompt structure with:
- READ-ONLY permissions
- Review checklist
- Approval/rejection signal formats
- Model selection guidance

**Classification:** **Core** (template documentation)

---

## 6. Configuration Files

### 6.1 `.claude/settings.json`

```json
{
  "permissions": {
    "allow": [
      "Bash(agent-browser:*)",
      "Bash(npm run:*)",
      "Bash(uv run:*)",
      ...
    ],
    "deny": ["Bash(sudo:*)", ...],
    "ask": ["Bash(git push:*)"]
  }
}
```

**Classification:** **Config** (repo-specific permissions)

---

### 6.2 `PROMPT.md`

The prompt template for the basic `ralph.sh` loop. Contains:
- Start commands for backend/frontend
- Task workflow instructions
- Browser verification steps

**Classification:** **Config** (repo-specific instructions)

---

## 7. Core vs Config Summary

### CORE ORCHESTRATOR (Universal)

These components go into the `ralph` Python package:

```
ralph/
├── cli.py                 # Command parsing (init, run, verify)
├── config.py              # Load/validate .ralph/ralph.yml
├── session.py             # Token, checksum, artifacts
├── tasks/
│   ├── parser.py          # Extract tasks from CR/PRD
│   └── updater.py         # Mark task complete (JSON-aware)
├── agents/
│   ├── templates/         # Prompt templates
│   │   ├── implementation.md
│   │   ├── test_writing.md
│   │   ├── review.md
│   │   ├── fix_runtime.md
│   │   └── planning.md
│   └── roles.py           # Agent role definitions + allowed tools
├── exec/
│   ├── runner.py          # Shell command execution with timeout
│   └── claude.py          # Claude CLI invocation wrapper
├── services/
│   ├── lifecycle.py       # Start/stop/health check
│   └── ports.py           # Port management
├── gates/
│   └── runner.py          # Gate execution with fail-fast
├── ui/
│   ├── agent_browser.py   # Agent-browser wrapper
│   └── robot.py           # Robot Framework wrapper
├── signals/
│   └── validators.py      # Signal validation (task-done, review, etc.)
└── reports/
    └── renderer.py        # JSON logs + summary output
```

### REPO-SPECIFIC CONFIG (`.ralph/ralph.yml`)

This is what the user creates per-repo:

```yaml
# .ralph/ralph.yml
version: "1"

# Task source (CR or PRD)
task_source:
  type: cr  # or "prd"
  path: "changes/CR-*.md"  # or "prd.md"
  format: json_block  # JSON embedded in markdown
  status_field: passes  # or "status"

# Services
services:
  backend:
    start:
      dev: "uv run uvicorn src.api.main:app --reload --host 127.0.0.1 --port {port}"
      prod: "uv run uvicorn src.api.main:app --host 127.0.0.1 --port {port}"
    port: 8000
    health_urls:
      - "/health"
      - "/api/system/health"
    
  frontend:
    build: "cd frontend && npm run build"
    serve:
      dev: "cd frontend && npm run dev -- --host 127.0.0.1 --port {port}"
      prod: "cd frontend && npm run preview -- --host 127.0.0.1 --port {port}"
    port: 5173

# Test gates
gates:
  build:
    - name: mypy
      cmd: "uv run mypy src/ --ignore-missing-imports"
      when: "pyproject.toml"
    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      when: "frontend/package.json"
    - name: frontend-build
      cmd: "cd frontend && npm run build"
      when: "frontend/package.json"
  
  full:
    - name: pytest
      cmd: "uv run pytest -x --tb=short"
      when: "pyproject.toml"
    - name: lint
      cmd: "cd frontend && npm run lint"
      when: "frontend/package.json"

# Test path guardrails
test_paths:
  - "tests/**"
  - "test_scripts/**"
  - "frontend/**/__tests__/**"
  - "frontend/**/*.test.*"
  - "frontend/**/*.spec.*"

# UI verification
ui_tests:
  agent_browser:
    enabled: true
    script: "ui_tests/agent-browser/smoke_test.sh"
  
  robot:
    enabled: true
    suite: "ui_tests/robot"
    variables:
      HEADLESS: true

# Agent configuration
agents:
  implementation:
    model: "claude-opus-4-5-20251101"
  test_writing:
    model: "claude-sonnet-4-5-20250929"
  review:
    model: "haiku"
  fix:
    model: "claude-sonnet-4-5-20250929"
  planning:
    model: "claude-sonnet-4-5-20250929"

# Timeouts and limits
limits:
  claude_timeout: 1800
  max_iterations: 30
  post_verify_iterations: 10
  ui_fix_iterations: 10
  robot_fix_iterations: 10
```

---

## 8. Migration Path

To migrate MongoDB-RAG-Agent to use the universal orchestrator:

1. **Install ralph CLI:**
   ```bash
   pipx install ralph-orchestrator
   ```

2. **Run `ralph init`** in the repo:
   - Detects pyproject.toml → Python backend
   - Detects frontend/package.json → Node frontend
   - Generates `.ralph/ralph.yml` with detected settings

3. **Review and customize** the generated config:
   - Verify service commands
   - Verify health endpoints
   - Verify gate commands
   - Add any custom UI tests

4. **Remove** the repo-specific scripts:
   - `ralph-verified.sh`
   - `ralph-cr.sh`
   - `ralph.sh`
   - Keep or migrate `start_backend.sh`, `start_frontend.sh`

5. **Run** the universal orchestrator:
   ```bash
   ralph run --cr changes/CR-DOCUMENT-INGESTION-DASHBOARD.md
   ```

---

## 9. Files to Keep vs Remove

### Keep (move to ralph package)
- Agent prompt templates (generalized)
- Signal validation logic
- Session management
- Service lifecycle management
- Gate execution framework
- UI test runners (wrappers)

### Keep (repo-specific, reference for .ralph.yml)
- `.claude/commands/` (already generic)
- `ui_tests/robot/smoke_dashboard.robot` (example)
- `ui_tests/agent-browser/smoke_test.sh` (example)

### Remove (after migration)
- `ralph-verified.sh`
- `ralph-cr.sh`
- `ralph.sh`
- `PROMPT.md` (replaced by ralph prompts)
- `prompts/` directory (moved to package)

---

## Appendix: Environment Variables

Current environment variables that become config:

| Variable | Default | Config Location |
|----------|---------|-----------------|
| `IMPL_MODEL` | `claude-opus-4-5-20251101` | `agents.implementation.model` |
| `TEST_MODEL` | `claude-sonnet-4-5-20250929` | `agents.test_writing.model` |
| `REVIEW_MODEL` | `haiku` | `agents.review.model` |
| `FIX_MODEL` | `claude-sonnet-4-5-20250929` | `agents.fix.model` |
| `PLAN_MODEL` | `claude-sonnet-4-5-20250929` | `agents.planning.model` |
| `CLAUDE_TIMEOUT` | `1800` | `limits.claude_timeout` |
| `SESSION_DIR` | `.ralph-session` | Hardcoded (convention) |
| `POST_VERIFY` | `1` | `post_verify.enabled` |
| `POST_VERIFY_MAX_ITERATIONS` | `10` | `limits.post_verify_iterations` |
| `UI_VERIFY_MAX_ITERATIONS` | `10` | `limits.ui_fix_iterations` |
| `ROBOT_VERIFY_MAX_ITERATIONS` | `10` | `limits.robot_fix_iterations` |
| `BACKEND_PORT` | `8000` | `services.backend.port` |
| `FRONTEND_PORT` | `5173` | `services.frontend.port` |
