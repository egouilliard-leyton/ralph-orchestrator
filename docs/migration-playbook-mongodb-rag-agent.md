# Migration Playbook: MongoDB-RAG-Agent to Ralph CLI

This guide provides step-by-step instructions for migrating the MongoDB-RAG-Agent repository from its current `ralph-verified.sh` bash-based workflow to the universal Ralph CLI orchestrator with `prd.json` task format and optional autopilot mode.

## Prerequisites

- Ralph CLI installed (`pipx install ralph-orchestrator`)
- Git repository with working `ralph-verified.sh` implementation
- Access to the MongoDB-RAG-Agent codebase
- Claude CLI configured and authenticated
- Node.js and npm installed (for frontend)
- Python and uv installed (for backend)

## Overview

This migration involves three phases:

| Phase | Goal | Time Estimate |
|-------|------|---------------|
| Phase 1 | Generate Ralph configuration | 30 minutes |
| Phase 2 | Convert existing CR to prd.json | 15 minutes |
| Phase 3 | Validate and run first task loop | 1-2 hours |
| Phase 4 (Optional) | Enable autopilot mode | 30 minutes |

---

## Phase 1: Generate Ralph Configuration

### Step 1.1: Install Ralph CLI

Install the Ralph orchestrator CLI globally:

```bash
pipx install ralph-orchestrator
```

Verify installation:

```bash
ralph --version
```

### Step 1.2: Initialize Ralph in Your Repository

Navigate to the MongoDB-RAG-Agent root directory and run the initialization command:

```bash
cd /path/to/MongoDB-RAG-Agent
ralph init
```

Ralph will detect:
- `pyproject.toml` → Python backend
- `frontend/package.json` → Node.js frontend

It will generate `.ralph/ralph.yml` with the fullstack template.

### Step 1.3: Customize the Configuration

Open `.ralph/ralph.yml` and update the following sections to match your current `ralph-verified.sh` settings:

#### Task Source

```yaml
task_source:
  type: prd_json
  path: .ralph/prd.json
```

#### Services

Map your existing start commands from `start_backend.sh` and `start_frontend.sh`:

```yaml
services:
  backend:
    start:
      dev: "uv run uvicorn src.api.main:app --reload --host 127.0.0.1 --port {port}"
      prod: "uv run uvicorn src.api.main:app --host 127.0.0.1 --port {port}"
    port: 8000
    health:
      - /health
      - /api/system/health
    timeout: 30

  frontend:
    build: "cd frontend && npm run build"
    serve:
      dev: "cd frontend && npm run dev -- --host 127.0.0.1 --port {port}"
      prod: "cd frontend && npm run preview -- --host 127.0.0.1 --port {port}"
    port: 5173
    timeout: 30
```

#### Gates

Transfer your quality gate commands from `ralph-verified.sh` (lines 1653-1735):

```yaml
gates:
  build:
    - name: mypy
      cmd: "uv run mypy src/ --ignore-missing-imports --no-error-summary"
      when: pyproject.toml
      timeout_seconds: 120
      fatal: true

    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      when: frontend/tsconfig.json
      timeout_seconds: 120
      fatal: true

  full:
    - name: pytest
      cmd: "uv run pytest -x --tb=short -q"
      when: pyproject.toml
      timeout_seconds: 300
      fatal: true

    - name: mypy
      cmd: "uv run mypy src/ --ignore-missing-imports --no-error-summary"
      when: pyproject.toml
      timeout_seconds: 120
      fatal: true

    - name: tsc
      cmd: "cd frontend && npx tsc --noEmit"
      when: frontend/tsconfig.json
      timeout_seconds: 120
      fatal: true

    - name: lint
      cmd: "cd frontend && npm run lint"
      when: frontend/package.json
      timeout_seconds: 120
      fatal: false

    - name: build
      cmd: "cd frontend && npm run build"
      when: frontend/package.json
      timeout_seconds: 300
      fatal: true
```

#### Test Path Guardrails

Transfer your allowed test paths from `ralph-verified.sh` (lines 1907-1945):

```yaml
test_paths:
  - tests/**
  - test_scripts/**
  - frontend/**/__tests__/**
  - frontend/**/*.test.*
  - frontend/**/*.spec.*
  - frontend/**/cypress/**
  - frontend/**/playwright/**
  - frontend/**/e2e/**
```

#### UI Verification

Configure your existing UI test setup:

```yaml
ui:
  agent_browser:
    enabled: true
    script: ui_tests/agent-browser/smoke_test.sh

  robot:
    enabled: true
    suite: ui_tests/robot
    variables:
      HEADLESS: "true"
      BROWSER: chromium
```

#### Agent Configuration

Map your environment variables to agent settings:

```yaml
agents:
  implementation:
    model: claude-opus-4-5-20251101    # Was: $IMPL_MODEL
    timeout: 1800

  test_writing:
    model: claude-sonnet-4-5-20250929  # Was: $TEST_MODEL
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - Edit
      - Write
      - LS

  review:
    model: haiku                       # Was: $REVIEW_MODEL
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - LS

  fix:
    model: claude-sonnet-4-5-20250929  # Was: $FIX_MODEL
    timeout: 1800

  planning:
    model: claude-sonnet-4-5-20250929  # Was: $PLAN_MODEL
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - LS
```

#### Limits

```yaml
limits:
  claude_timeout: 1800                 # Was: $CLAUDE_TIMEOUT
  max_iterations: 30
  post_verify_iterations: 10           # Was: $POST_VERIFY_MAX_ITERATIONS
  ui_fix_iterations: 10                # Was: $UI_VERIFY_MAX_ITERATIONS
  robot_fix_iterations: 10             # Was: $ROBOT_VERIFY_MAX_ITERATIONS
```

### Step 1.4: Update .gitignore

Add the session directory to `.gitignore`:

```gitignore
# Ralph session (transient)
.ralph-session/
```

Keep these files in version control:
- `.ralph/ralph.yml`
- `.ralph/prd.json`
- `AGENTS.md`

---

## Phase 2: Convert Existing CR to prd.json

### Step 2.1: Identify Your Current Change Request

Locate your active Change Request file:

```bash
ls -la changes/CR-*.md
```

For example: `changes/CR-DOCUMENT-INGESTION-DASHBOARD.md`

### Step 2.2: Import Using Ralph

Use the import command to convert your CR markdown to prd.json:

```bash
ralph import --cr changes/CR-DOCUMENT-INGESTION-DASHBOARD.md
```

This will:
1. Parse the JSON task block from your CR file
2. Normalize task IDs to `T-NNN` format
3. Map `steps` to `acceptanceCriteria`
4. Generate `.ralph/prd.json`

### Step 2.3: Verify the Generated prd.json

Review the generated `.ralph/prd.json`:

```bash
cat .ralph/prd.json | jq .
```

Verify that:
- All tasks are present with `"passes": false`
- Acceptance criteria are clear and verifiable
- Priorities match your intended order

### Step 2.4: Manual prd.json Creation (Alternative)

If you prefer to create tasks manually or start fresh, create `.ralph/prd.json` with this structure:

```json
{
  "$schema": "https://ralph-orchestrator.dev/schemas/prd.schema.json",
  "project": "MongoDB RAG Agent - Feature Name",
  "branchName": "ralph/feature-name",
  "description": "Brief description of the feature or change",
  "tasks": [
    {
      "id": "T-001",
      "title": "First task title (action-oriented)",
      "description": "What to do and why. Include context.",
      "acceptanceCriteria": [
        "File `path/to/file.py` exists",
        "Run `uv run pytest tests/test_file.py -v` - exits with code 0",
        "API endpoint returns expected response"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

### Step 2.5: Task Formatting Best Practices

When writing tasks, follow these acceptance criteria patterns:

| Type | Pattern | Example |
|------|---------|---------|
| Command | `Run \`cmd\` - exits with code 0` | `Run \`uv run pytest\` - exits with code 0` |
| File exists | `File \`path\` exists` | `File \`src/config/auth.py\` exists` |
| File contains | `File \`path\` contains \`string\`` | `File \`main.py\` contains \`import jwt\`` |
| Browser nav | `agent-browser: open \`url\` - result` | `agent-browser: open /login - form renders` |
| Browser action | `agent-browser: click \`el\` - result` | `agent-browser: click 'Submit' - redirects` |
| API check | `GET/POST \`url\` returns \`status\`` | `POST /api/login returns 200` |

---

## Phase 3: Validate and Run First Task Loop

### Step 3.1: Validate Configuration

Run the configuration validator:

```bash
ralph validate
```

This checks:
- Configuration file syntax
- Required tools are available (claude, uv, npm)
- Gate commands are valid
- Service commands parse correctly

### Step 3.2: Run a Dry-Run

Execute a dry-run to see what Ralph will do:

```bash
ralph run --dry-run
```

This shows:
- Which tasks will be executed
- Which gates will run
- Which services will start (if any)

### Step 3.3: Run the Task Loop

Start the verified execution engine:

```bash
ralph run
```

Or, if you want to use a specific prd.json:

```bash
ralph run --prd-json .ralph/prd.json
```

For compatibility with your existing CR files:

```bash
ralph run --cr changes/CR-DOCUMENT-INGESTION-DASHBOARD.md
```

### Step 3.4: Monitor Progress

During execution, you can monitor:

**Session artifacts:**
```bash
ls -la .ralph-session/
```

**Task status:**
```bash
cat .ralph/prd.json | jq '.tasks[] | {id, title, passes}'
```

**Gate results:**
```bash
cat .ralph-session/gates.log
```

### Step 3.5: Run Post-Completion Verification Only

If you want to run verification without task execution:

```bash
ralph verify
```

This runs:
1. Build gates (mypy, tsc)
2. Full gates (pytest, lint, build)
3. Service health checks
4. UI smoke tests (agent-browser)
5. Robot Framework tests

---

## Phase 4: Enable Autopilot Mode (Optional)

Autopilot automates the improvement cycle: report → analysis → PRD → tasks → execution → PR.

### Step 4.1: Create Reports Directory

Create a directory for analysis reports:

```bash
mkdir -p reports
```

Add report files containing information for Ralph to analyze:
- Daily error logs
- User feedback summaries
- Performance metrics
- Feature requests

Example report (`reports/weekly-analytics.md`):

```markdown
# Weekly Analytics - January 25, 2026

## Error Summary
- 45 "Connection timeout" errors in Q&A endpoint
- 12 users reported slow document uploads

## User Feedback
- "Search results are not relevant"
- "Need bulk document upload"

## Performance Metrics
- Average response time: 2.3s (target: <1s)
- Document indexing: 5 docs/minute
```

### Step 4.2: Configure Autopilot Settings

Add the autopilot section to your `.ralph/ralph.yml`:

```yaml
autopilot:
  enabled: true
  reports_dir: ./reports
  branch_prefix: ralph/
  create_pr: true

  analysis:
    provider: anthropic
    model: claude-opus-4-5-20251101
    recent_days: 7  # Avoid re-picking recent fixes

  prd:
    mode: autonomous  # Don't ask questions
    output_dir: ./tasks

  tasks:
    output: .ralph/prd.json
    min_count: 8
    max_count: 15

  memory:
    progress: .ralph/progress.txt
    archive: .ralph/archive
```

### Step 4.3: Set API Key

Configure your LLM provider:

```bash
# Anthropic (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Or OpenAI
export OPENAI_API_KEY="sk-..."

# Or OpenRouter
export OPENROUTER_API_KEY="sk-or-..."
```

### Step 4.4: Test Autopilot (Dry Run)

Preview what autopilot would do:

```bash
ralph autopilot --dry-run
```

This shows:
- Which report was selected
- Analysis output (priority item, rationale)
- Proposed branch name
- Generated PRD summary

### Step 4.5: Run Full Autopilot

Execute the complete autopilot pipeline:

```bash
ralph autopilot
```

This will:
1. Find the latest report in `./reports`
2. Analyze and pick the #1 priority item
3. Create branch `ralph/[feature-name]`
4. Generate PRD and tasks
5. Run the verified execution loop
6. Create a pull request

### Step 4.6: Schedule Nightly Autopilot (macOS launchd)

Create a launchd plist for scheduled execution:

**File:** `~/Library/LaunchAgents/com.ralph.autopilot.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ralph.autopilot</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-c</string>
        <string>cd /path/to/MongoDB-RAG-Agent && /usr/local/bin/ralph autopilot --reports ./reports --create-pr 2>&amp;1 | tee -a /tmp/ralph-autopilot.log</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>ANTHROPIC_API_KEY</key>
        <string>YOUR_API_KEY</string>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/tmp/ralph-autopilot-stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/ralph-autopilot-stderr.log</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

Load the schedule:

```bash
launchctl load ~/Library/LaunchAgents/com.ralph.autopilot.plist
```

Verify it's scheduled:

```bash
launchctl list | grep ralph
```

### Step 4.7: Schedule Nightly Autopilot (Linux cron)

Add to your crontab:

```bash
crontab -e
```

Add this line (runs at 3 AM daily):

```cron
0 3 * * * cd /path/to/MongoDB-RAG-Agent && ANTHROPIC_API_KEY="your-key" /usr/local/bin/ralph autopilot --reports ./reports --create-pr >> /var/log/ralph-autopilot.log 2>&1
```

---

## Phase 5: Cleanup Legacy Files (Optional)

After confirming the new workflow works correctly, you can remove the legacy scripts.

### Step 5.1: Files to Remove

```bash
# Legacy Ralph scripts
rm ralph-verified.sh
rm ralph-cr.sh
rm ralph.sh

# Legacy prompt file (replaced by Ralph prompts)
rm PROMPT.md

# Legacy start scripts (now in ralph.yml)
rm start_backend.sh
rm start_frontend.sh
```

### Step 5.2: Files to Keep

Keep these repo-specific assets:

- `.claude/commands/create-prd.md` - Generic PRD command
- `.claude/commands/create-change-request.md` - Generic CR command
- `.claude/skills/agent-browser-skill/` - Browser skill
- `ui_tests/robot/` - Robot Framework tests
- `ui_tests/agent-browser/` - Agent-browser tests
- `changes/` - Historical Change Requests

### Step 5.3: Update Documentation

Update your README to reference the new workflow:

```markdown
## Development Workflow

This project uses [Ralph Orchestrator](https://github.com/your-org/ralph-orchestrator) for automated development.

### Running Tasks

```bash
# Initialize Ralph (first time only)
ralph init

# Run verified task loop
ralph run

# Run verification only
ralph verify
```

### Autopilot Mode

```bash
# Run autopilot self-improvement
ralph autopilot --reports ./reports

# Preview autopilot decisions
ralph autopilot --dry-run
```
```

---

## Troubleshooting

### Configuration Not Found

**Error:** "Configuration file not found"

**Solution:** Ensure you're in the project root and `.ralph/ralph.yml` exists:

```bash
ralph init
```

### Claude CLI Not Found

**Error:** "claude: command not found"

**Solution:** Install and authenticate the Claude CLI:

```bash
npm install -g @anthropic-ai/claude-cli
claude auth login
```

### Gate Command Fails

**Error:** "Gate 'pytest' failed with exit code 1"

**Solution:**
1. Run the gate command manually to see the error
2. Fix the failing tests
3. Run `ralph run` again

### Service Health Check Timeout

**Error:** "Backend health check timed out after 30s"

**Solution:**
1. Verify the start command works manually
2. Check the health endpoint URL is correct
3. Increase the timeout in configuration:

```yaml
services:
  backend:
    timeout: 60  # Increase from 30
```

### Tasks Not Advancing

**Error:** Tasks stuck at `passes: false`

**Solution:**
1. Check `.ralph-session/` for agent output logs
2. Verify acceptance criteria are achievable
3. Check signal validation in session logs

### Autopilot No Reports Found

**Error:** "No reports found in ./reports"

**Solution:** Add at least one `.md`, `.txt`, or `.json` file to your reports directory.

### GitHub CLI Not Authenticated

**Error:** "gh: not logged in"

**Solution:**

```bash
gh auth login
```

---

## Configuration Reference

### Environment Variable to Config Mapping

| Environment Variable | Config Path | Default |
|---------------------|-------------|---------|
| `IMPL_MODEL` | `agents.implementation.model` | `claude-opus-4-5-20251101` |
| `TEST_MODEL` | `agents.test_writing.model` | `claude-sonnet-4-5-20250929` |
| `REVIEW_MODEL` | `agents.review.model` | `haiku` |
| `FIX_MODEL` | `agents.fix.model` | `claude-sonnet-4-5-20250929` |
| `PLAN_MODEL` | `agents.planning.model` | `claude-sonnet-4-5-20250929` |
| `CLAUDE_TIMEOUT` | `limits.claude_timeout` | `1800` |
| `POST_VERIFY_MAX_ITERATIONS` | `limits.post_verify_iterations` | `10` |
| `UI_VERIFY_MAX_ITERATIONS` | `limits.ui_fix_iterations` | `10` |
| `ROBOT_VERIFY_MAX_ITERATIONS` | `limits.robot_fix_iterations` | `10` |
| `BACKEND_PORT` | `services.backend.port` | `8000` |
| `FRONTEND_PORT` | `services.frontend.port` | `5173` |

### Artifact Locations

| Purpose | Old Location | New Location |
|---------|--------------|--------------|
| Session artifacts | `.ralph-session/` | `.ralph-session/` (unchanged) |
| Task status | `changes/CR-*.md` JSON block | `.ralph/prd.json` |
| Progress log | N/A | `.ralph/progress.txt` |
| Autopilot analysis | N/A | `.ralph/autopilot/analysis.json` |
| Archived runs | N/A | `.ralph/archive/` |

---

## Related Documentation

- [How To Set Up a Repository](./how-to-setup-repository.md) - General Ralph setup
- [How To Create Tasks](./how-to-create-tasks.md) - Task creation guide
- [How To Use Autopilot](./how-to-use-autopilot.md) - Autopilot mode reference
- [How To Use the CLI](./how-to-use-cli.md) - CLI command reference
- [Canonical Artifacts](../specs/canonical-artifacts.md) - Schema documentation
