# Compound Product Workflow Assets Inventory

**Date:** 2026-01-25  
**Last Updated:** 2026-01-25 (inventory-current task)  
**Purpose:** Analyze Compound Product workflow assets and classify each element as **Core Orchestrator Logic** (universal) or **Repo-Specific Configuration**.

---

## Summary

| Category | Core (Universal) | Config (Repo-Specific) |
|----------|------------------|------------------------|
| Autopilot Pipeline | 3 scripts | 1 config file |
| Task Loop | 1 loop script | 1 prompt template |
| Report Analysis | 1 analysis script | Provider config |
| PRD Generation | 1 skill | Template customizable |
| Task Generation | 1 skill | Schema fields |
| Progress Tracking | File conventions | Paths configurable |

---

## 1. Scripts

### 1.1 `scripts/auto-compound.sh` (Autopilot Pipeline - 242 lines)

**Purpose:** Full autopilot pipeline: report → analysis → branch → PRD → tasks → loop → PR

#### Pipeline Steps → **CORE**

| Step | Function | Classification |
|------|----------|----------------|
| Step 1: Find Report | `ls -t "$REPORTS_DIR"/*.md | head -1` | **Core** (path = config) |
| Step 2: Analyze Report | Call `analyze-report.sh` | **Core** |
| Step 3: Create Branch | `git checkout -b "$BRANCH_NAME"` | **Core** |
| Step 4: Generate PRD | Use PRD skill via amp/claude | **Core** |
| Step 5: Generate Tasks | Use tasks skill to create `prd.json` | **Core** |
| Step 6: Archive Previous | Move old `prd.json` to archive | **Core** |
| Step 7: Run Loop | Execute `loop.sh` | **Core** |
| Step 8: Create PR | `gh pr create` | **Core** |

**Config extracted:**
```yaml
autopilot:
  reports_dir: "./reports"
  output_dir: "./scripts/compound"
  branch_prefix: "compound/"
  max_iterations: 25
  tool: "amp"  # or "claude"
  analyze_command: ""  # custom override
  quality_checks:
    - "npm run typecheck"
    - "npm test"
  create_pr: true
  archive_runs: true
```

---

### 1.2 `scripts/analyze-report.sh` (Report Analysis - 197 lines)

**Purpose:** Analyze a report file and pick the #1 actionable priority item.

#### Provider Support → **CORE**

| Provider | Detection | Model |
|----------|-----------|-------|
| Vercel AI Gateway | `VERCEL_OIDC_TOKEN` or `AI_GATEWAY_API_KEY` | `anthropic/claude-opus-4.5` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-4-5-20251101` |
| OpenAI | `OPENAI_API_KEY` | `gpt-5.2` |
| OpenRouter | `OPENROUTER_API_KEY` | `anthropic/claude-opus-4.5` |

#### Analysis Contract → **CORE**

Output JSON structure:
```json
{
  "priority_item": "Brief title of the item",
  "description": "2-3 sentence description",
  "rationale": "Why this is the #1 priority",
  "acceptance_criteria": ["Specific criteria 1", "..."],
  "estimated_tasks": 3,
  "branch_name": "compound/kebab-case-feature-name"
}
```

#### Deduplication Logic → **CORE**

- Reads recent PRDs (last 7 days) from `$TASKS_DIR`
- Excludes already-fixed items from analysis prompt

**Config extracted:**
```yaml
analysis:
  providers:
    - name: gateway
      url: "${AI_GATEWAY_URL:-https://ai-gateway.vercel.sh/v1}"
      model: "${AI_GATEWAY_MODEL:-anthropic/claude-opus-4.5}"
    - name: anthropic
      url: "https://api.anthropic.com/v1/messages"
      model: "claude-opus-4-5-20251101"
    - name: openai
      url: "https://api.openai.com/v1/chat/completions"
      model: "gpt-5.2"
    - name: openrouter
      url: "https://openrouter.ai/api/v1/chat/completions"
      model: "anthropic/claude-opus-4.5"
  recent_prd_days: 7
  tasks_dir: "./tasks"
```

---

### 1.3 `scripts/loop.sh` (Execution Loop - 98 lines)

**Purpose:** Run AI agent repeatedly until all tasks pass.

#### Loop Logic → **CORE**

| Function | Purpose | Classification |
|----------|---------|----------------|
| Load config | Read `compound.config.json` | **Core** |
| Initialize progress | Create `progress.txt` if missing | **Core** |
| Iteration loop | For 1 to max_iterations | **Core** |
| Run agent | `amp` or `claude` with prompt | **Core** |
| Check completion | Look for `<promise>COMPLETE</promise>` | **Core** |

**Config extracted:**
```yaml
loop:
  max_iterations: 25
  tool: "amp"  # or "claude"
  prompt_path: "scripts/compound/prompt.md"  # for amp
  claude_prompt_path: "scripts/compound/CLAUDE.md"  # for claude
  prd_path: "{output_dir}/prd.json"
  progress_path: "{output_dir}/progress.txt"
```

---

### 1.4 `scripts/prompt.md` / `scripts/CLAUDE.md` (Agent Instructions)

**Purpose:** Instructions for the execution agent per iteration.

#### Instruction Flow → **CORE (Template)**

1. Read config (`compound.config.json`)
2. Read PRD (`prd.json`)
3. Read progress log (`progress.txt`) - check Codebase Patterns first
4. Check branch matches PRD `branchName`
5. Pick highest priority task with `passes: false`
6. Implement single task
7. Run quality checks
8. Update `AGENTS.md` with discovered patterns
9. Commit changes: `feat: [Task ID] - [Task Title]`
10. Update PRD: set `passes: true`
11. Append progress to `progress.txt`

#### Progress Report Format → **CORE**

```markdown
## [Date/Time] - [Task ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered
  - Gotchas encountered
  - Useful context
---
```

#### Stop Condition → **CORE**

Signal: `<promise>COMPLETE</promise>` when ALL tasks have `passes: true`

---

## 2. Skills

### 2.1 `skills/prd/SKILL.md` (PRD Generator)

**Purpose:** Generate Product Requirements Documents autonomously.

#### Self-Clarification Questions → **CORE (Template)**

1. **Problem/Goal:** What problem does this solve?
2. **Core Functionality:** What are the 2-3 key actions?
3. **Scope/Boundaries:** What should this NOT do?
4. **Success Criteria:** How do we verify it's working?
5. **Constraints:** Technical/time constraints?

#### PRD Structure → **CORE (Template)**

| Section | Purpose |
|---------|---------|
| Introduction | Brief description |
| Goals | Measurable objectives |
| Tasks | T-001, T-002, etc. with acceptance criteria |
| Functional Requirements | FR-1, FR-2, etc. |
| Non-Goals | Out of scope items |
| Technical Considerations | Constraints, dependencies |
| Success Metrics | How to measure success |
| Open Questions | Remaining clarifications |

**Key rule:** Each task acceptance criteria must be verifiable, not vague.

---

### 2.2 `skills/tasks/SKILL.md` (Task Generator)

**Purpose:** Convert PRD markdown to `prd.json` for execution.

#### Task Schema → **CORE**

```json
{
  "project": "Project Name",
  "branchName": "compound/[feature-name]",
  "description": "One-line description",
  "tasks": [
    {
      "id": "T-001",
      "title": "Specific action verb + target",
      "description": "What to do and why",
      "acceptanceCriteria": [
        "Machine-verifiable criterion 1",
        "Run `npm run typecheck` - exits with code 0"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

#### Acceptance Criteria Patterns → **CORE (Rules)**

| Type | Pattern | Example |
|------|---------|---------|
| Command | "Run `[cmd]` - exits with code 0" | "Run `npm test` - exits with code 0" |
| File check | "File `[path]` contains `[string]`" | "File `middleware.ts` contains `clerkMiddleware`" |
| Browser nav | "agent-browser: open `[url]` - [result]" | "agent-browser: open /login - SignIn renders" |
| Browser action | "agent-browser: click `[el]` - [result]" | "agent-browser: click 'Submit' - redirects" |
| Console check | "agent-browser: console shows no errors" | |
| API check | "GET/POST `[url]` returns `[status]`" | "POST /api/signup returns 200" |

#### Task Granularity Rules → **CORE (Rules)**

- **Target: 8-15 tasks per PRD**
- **One concern per task** (navigate → check → test → implement → verify)
- **Never combine investigation with implementation**
- **Each task completable in one iteration**

#### Priority Ordering → **CORE (Rules)**

1. Investigation tasks (priority 1-3)
2. Schema/database changes (priority 4-5)
3. Backend logic changes (priority 6-7)
4. UI component changes (priority 8-9)
5. Verification tasks (priority 10+)

---

## 3. Configuration Files

### 3.1 `compound.config.json`

**Location:** Project root

```json
{
  "tool": "amp",
  "reportsDir": "./reports",
  "outputDir": "./scripts/compound",
  "qualityChecks": ["npm run typecheck", "npm test"],
  "maxIterations": 25,
  "branchPrefix": "compound/",
  "analyzeCommand": ""
}
```

**Classification:** **Config** (repo-specific)

**Mapping to ralph.yml:**
```yaml
autopilot:
  tool: "claude"  # ralph uses claude only
  reports_dir: "${reportsDir}"
  output_dir: "${outputDir}"
  branch_prefix: "${branchPrefix}"
  max_iterations: ${maxIterations}

gates:
  autopilot: ${qualityChecks}
```

---

### 3.2 `examples/sample-tasks.json`

**Purpose:** Example `prd.json` format

**Classification:** **Core** (schema definition)

This becomes the canonical task format for ralph.

---

## 4. Memory/Progress Files

### 4.1 `progress.txt`

**Purpose:** Append-only log of completed tasks and learnings.

**Structure:**
```markdown
## Codebase Patterns
- Pattern 1
- Pattern 2

---

## [Date/Time] - T-001
- What was implemented
- Files changed
- **Learnings:**
  - ...
---
```

**Classification:** **Core** (convention)

---

### 4.2 Archive Structure

**Location:** `{output_dir}/archive/{date}-{branch-name}/`

Contains:
- `prd.json` - Snapshot of tasks
- `progress.txt` - Progress at completion time

**Classification:** **Core** (convention)

---

## 5. Core vs Config Summary

### CORE ORCHESTRATOR (Universal)

Components to integrate into ralph:

```
ralph/
├── autopilot/
│   ├── analyzer.py         # Report analysis (multi-provider)
│   ├── pipeline.py         # Full autopilot flow
│   └── memory.py           # Progress file management
├── skills/
│   ├── prd_generator.py    # PRD generation logic
│   └── task_generator.py   # prd.json generation
└── tasks/
    └── schema.py           # prd.json schema validation
```

#### Analysis Contract

```python
class AnalysisResult:
    priority_item: str
    description: str
    rationale: str
    acceptance_criteria: list[str]
    estimated_tasks: int
    branch_name: str
```

#### Task Schema

```python
class Task:
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: int
    passes: bool
    notes: str = ""

class PRD:
    project: str
    branch_name: str
    description: str
    tasks: list[Task]
```

---

### REPO-SPECIFIC CONFIG

Additions to `.ralph/ralph.yml`:

```yaml
autopilot:
  enabled: true
  reports_dir: "./reports"
  branch_prefix: "compound/"
  create_pr: true
  
  analysis:
    provider: "anthropic"  # or gateway, openai, openrouter
    model: "claude-opus-4-5-20251101"
    max_tokens: 1024
    recent_days: 7  # Exclude items fixed in last N days
  
  prd:
    mode: autonomous  # or interactive
    output_dir: "./tasks"
    filename_pattern: "prd-{feature-name}.md"
  
  tasks:
    output_path: ".ralph/prd.json"
    min_tasks: 8
    max_tasks: 15
  
  memory:
    progress_file: ".ralph/progress.txt"
    archive_dir: ".ralph/archive"
```

---

## 6. Differences from MongoDB-RAG-Agent Approach

| Aspect | MongoDB-RAG-Agent | Compound Product |
|--------|-------------------|------------------|
| **Entry Point** | CR markdown file | Report analysis |
| **Task Source** | JSON in markdown | Standalone prd.json |
| **Verification** | Multi-phase (build, runtime, UI) | Quality checks only |
| **Anti-Gaming** | Session tokens, checksums | Simple completion signal |
| **Agent Roles** | Separate impl/test/review | Single agent per iteration |
| **Memory** | Session artifacts | progress.txt + AGENTS.md |
| **Branch Strategy** | Manual | Auto-created from analysis |
| **PR Creation** | Manual | Automated |

---

## 7. Integration Plan

### What Ralph Should Adopt from Compound

1. **Autopilot mode** (`ralph autopilot`)
   - Report analysis
   - Branch creation
   - PRD + tasks generation
   - Loop execution
   - PR creation

2. **prd.json as canonical format**
   - Structured, machine-readable
   - Clear schema
   - Priority ordering
   - Notes field for logging

3. **Progress tracking**
   - Append-only progress file
   - Codebase Patterns section
   - AGENTS.md updates

4. **Task granularity rules**
   - 8-15 tasks per PRD
   - Boolean acceptance criteria
   - agent-browser verification patterns

### What Compound Should Adopt from MongoDB-RAG

1. **Anti-gaming mechanisms**
   - Session tokens
   - Signal validation
   - Checksum verification

2. **Multi-agent verification**
   - Separate test-writing agent
   - Independent review agent
   - Read-only permissions

3. **Post-completion verification**
   - Build gates
   - Runtime health checks
   - UI smoke tests (agent-browser + Robot)

4. **Test path guardrails**
   - Whitelist of allowed test paths
   - Automatic revert of unauthorized changes

---

## 8. Files to Extract

### Move to ralph package

| File | New Location | Purpose |
|------|--------------|---------|
| `analyze-report.sh` | `ralph/autopilot/analyzer.py` | Report analysis |
| `auto-compound.sh` | `ralph/autopilot/pipeline.py` | Autopilot flow |
| `loop.sh` | (merged with ralph run) | Task loop |
| `skills/prd/SKILL.md` | `ralph/skills/prd.py` | PRD generation |
| `skills/tasks/SKILL.md` | `ralph/skills/tasks.py` | Task generation |
| `prompt.md` / `CLAUDE.md` | `ralph/agents/templates/` | Agent instructions |
| `sample-tasks.json` | `ralph/schemas/prd.json` | Schema reference |

### Keep as examples

| File | Purpose |
|------|---------|
| `examples/sample-prd.md` | PRD format example |
| `examples/sample-report.md` | Report format example |
| `examples/sample-tasks.json` | prd.json schema example |
| `examples/com.compound.plist.example` | launchd scheduling example |
