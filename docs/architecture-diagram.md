# Ralph Orchestrator Architecture Diagrams

Quick visual reference for the orchestrator module structure and data flows.

## Module Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ralph-orchestrator                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                              CLI Layer                               │   │
│  │                                                                      │   │
│  │   ralph init    ralph run    ralph verify    ralph autopilot        │   │
│  │                                                                      │   │
│  └───────────────────────────────────┬─────────────────────────────────┘   │
│                                      │                                      │
│  ┌───────────────────────────────────┴─────────────────────────────────┐   │
│  │                         Orchestration Layer                          │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │    config    │  │   session    │  │        autopilot         │  │   │
│  │  │              │  │              │  │                          │  │   │
│  │  │ • load yml   │  │ • tokens     │  │ • report analysis        │  │   │
│  │  │ • validate   │  │ • checksums  │  │ • PRD generation         │  │   │
│  │  │ • defaults   │  │ • lifecycle  │  │ • task generation        │  │   │
│  │  └──────────────┘  └──────────────┘  │ • PR creation            │  │   │
│  │                                      └──────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           Domain Layer                               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │    tasks     │  │    agents    │  │    gates     │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ • parser     │  │ • roles      │  │ • runner     │               │   │
│  │  │ • status     │  │ • prompts    │  │ • conditions │               │   │
│  │  │ • selector   │  │ • signals    │  │ • results    │               │   │
│  │  │              │  │ • guardrails │  │              │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │   services   │  │      ui      │  │   reports    │               │   │
│  │  │              │  │              │  │              │               │   │
│  │  │ • manager    │  │ • agent_brws │  │ • timeline   │               │   │
│  │  │ • health     │  │ • robot      │  │ • summary    │               │   │
│  │  │ • cleanup    │  │ • loops      │  │ • artifacts  │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Infrastructure Layer                          │   │
│  │                                                                      │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │                           exec                                  │ │   │
│  │  │                                                                 │ │   │
│  │  │  • CommandRunner    • OutputCapture    • TimeoutHandler        │ │   │
│  │  │                                                                 │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Main Task Loop Flow

```
                               ┌─────────────────┐
                               │   START RUN     │
                               └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │  Create Session │
                               │  Generate Token │
                               └────────┬────────┘
                                        │
               ┌────────────────────────▼─────────────────────────┐
               │                  MAIN LOOP                        │
               │                                                   │
               │    ┌────────────────────────────────────────┐    │
               │    │         Per-Iteration Steps             │    │
               │    │                                         │    │
               │    │  1. Verify checksum                     │    │
               │    │  2. Get next pending task               │    │
               │    │  3. Run implementation agent            │    │
               │    │  4. Validate task-done signal           │    │
               │    │  5. Run test-writing agent (guardrailed)│    │
               │    │  6. Run script-enforced gates           │    │
               │    │  7. Run review agent (read-only)        │    │
               │    │  8. Script marks task complete          │    │
               │    │                                         │    │
               │    └────────────────────────────────────────┘    │
               │                                                   │
               └─────────────────────┬─────────────────────────────┘
                                     │
                         ┌───────────▼───────────┐
                         │  All Tasks Complete?  │
                         └───────────┬───────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
               ┌────▼────┐                    ┌───────▼───────┐
               │   YES   │                    │      NO       │
               └────┬────┘                    └───────┬───────┘
                    │                                 │
         ┌──────────▼──────────┐              ┌──────▼──────┐
         │ Post-Verification   │              │ Continue    │
         │ (build/runtime/UI)  │              │ Loop        │
         └──────────┬──────────┘              └─────────────┘
                    │
           ┌────────▼────────┐
           │   SUCCESS/FAIL  │
           └─────────────────┘
```

## Anti-Gaming Mechanisms

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ANTI-GAMING ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      1. SESSION TOKEN                                │   │
│  │                                                                      │   │
│  │   • Generated fresh each session (timestamp + random + SHA-256)     │   │
│  │   • Included in every agent prompt                                   │   │
│  │   • Required in every completion signal                              │   │
│  │   • Prevents pre-written/cached completion signals                   │   │
│  │                                                                      │   │
│  │   Format: ralph-YYYYMMDD-HHMMSS-[16-char-hex]                       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    2. CHECKSUM VERIFICATION                          │   │
│  │                                                                      │   │
│  │   task-status.json ────► SHA-256 ────► task-status.sha256           │   │
│  │                                                                      │   │
│  │   Before ANY read:  computed checksum == stored checksum?           │   │
│  │   After ANY write:  update stored checksum                          │   │
│  │                                                                      │   │
│  │   Mismatch = ABORT with "TAMPERING DETECTED"                        │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   3. SCRIPT-ONLY STATUS UPDATES                      │   │
│  │                                                                      │   │
│  │   Agent signals: <task-done session="...">                          │   │
│  │                          │                                          │   │
│  │                          ▼                                          │   │
│  │   Script validates ──► Script updates ──► Script updates checksum   │   │
│  │                        task-status.json                              │   │
│  │                                                                      │   │
│  │   Agents NEVER write to task-status.json directly                   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    4. TEST PATH GUARDRAILS                           │   │
│  │                                                                      │   │
│  │   BEFORE test agent:  snapshot modified files                       │   │
│  │   AFTER test agent:   snapshot modified files                       │   │
│  │   NEW files = AFTER - BEFORE                                        │   │
│  │                                                                      │   │
│  │   For each NEW file:                                                │   │
│  │     matches(tests/**, **/test_*, *.spec.*, etc.) ?                 │   │
│  │       YES → keep                                                    │   │
│  │       NO  → REVERT (git checkout or rm)                            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    5. ROLE-BASED TOOL RESTRICTIONS                   │   │
│  │                                                                      │   │
│  │   Implementation:  All tools (can modify anything)                  │   │
│  │   Test-writing:    Read, Grep, Glob, Edit, Write (path-restricted)  │   │
│  │   Review:          Read, Grep, Glob only (READ-ONLY)                │   │
│  │   Planning:        Read, Grep, Glob only (READ-ONLY)                │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Post-Completion Verification

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     POST-COMPLETION VERIFICATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 1: Build & Runtime                          │   │
│  │                                                                      │   │
│  │   ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐  │   │
│  │   │  mypy     │───▶│   tsc     │───▶│npm build  │───▶│ backend  │  │   │
│  │   │ (types)   │    │ (types)   │    │           │    │ health   │  │   │
│  │   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘    └────┬─────┘  │   │
│  │         │                │                │               │         │   │
│  │         └────────────────┴────────────────┴───────────────┘         │   │
│  │                                 │                                    │   │
│  │                          FAIL? → Fix Agent → Retry                   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                PHASE 2: Agent-Browser UI Tests                       │   │
│  │                                                                      │   │
│  │   ┌─────────────────┐                                               │   │
│  │   │  Smoke Tests    │─────────────────────────────────────┐         │   │
│  │   │                 │                                     │         │   │
│  │   │ • App loads     │                                     │         │   │
│  │   │ • Dashboard     │      FAIL?                          │         │   │
│  │   │ • Projects UI   │        │                            │         │   │
│  │   │ • Upload UI     │        ▼                            │         │   │
│  │   │ • History       │  ┌───────────────┐                  │         │   │
│  │   │ • Q&A input     │  │ Planning Agent│ (read-only)      │         │   │
│  │   └─────────────────┘  │    ▼          │                  │         │   │
│  │                        │ Impl Agent    │────► Retry ──────┘         │   │
│  │                        └───────────────┘                            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               PHASE 3: Robot Framework Regression                    │   │
│  │                                                                      │   │
│  │   ┌─────────────────┐                                               │   │
│  │   │  Robot Suite    │─────────────────────────────────────┐         │   │
│  │   │                 │                                     │         │   │
│  │   │ • Playwright    │      FAIL?                          │         │   │
│  │   │ • Deterministic │        │                            │         │   │
│  │   │ • Regression    │        ▼                            │         │   │
│  │   │                 │  ┌───────────────┐                  │         │   │
│  │   └─────────────────┘  │ Planning Agent│ (read-only)      │         │   │
│  │                        │    ▼          │                  │         │   │
│  │                        │ Impl Agent    │────► Retry ──────┘         │   │
│  │                        └───────────────┘                            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                            ┌─────────────────┐                             │
│                            │    SUCCESS!     │                             │
│                            └─────────────────┘                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Autopilot Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUTOPILOT PIPELINE                                 │
│                     (Compound Product Integration)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ./reports/                                                                │
│       │                                                                     │
│       ▼                                                                     │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │               STEP 1: Find & Analyze Report                        │    │
│   │                                                                    │    │
│   │   • Find latest report in reports_dir                             │    │
│   │   • Send to Claude for analysis                                    │    │
│   │   • Output: analysis.json                                          │    │
│   │     - priority_item                                                │    │
│   │     - description                                                  │    │
│   │     - rationale                                                    │    │
│   │     - acceptance_criteria                                          │    │
│   │     - branch_name                                                  │    │
│   │                                                                    │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │              STEP 2: Create Branch & Generate PRD                  │    │
│   │                                                                    │    │
│   │   • git checkout -b ralph/{branch_name}                           │    │
│   │   • Generate PRD markdown (autonomous mode)                        │    │
│   │   • Save to tasks/prd-{name}.md                                   │    │
│   │                                                                    │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │               STEP 3: Convert PRD to Tasks                         │    │
│   │                                                                    │    │
│   │   • Parse PRD → extract requirements                               │    │
│   │   • Generate 8-15 granular tasks                                   │    │
│   │   • Write to .ralph/prd.json                                      │    │
│   │                                                                    │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │               STEP 4: Run Verified Execution                       │    │
│   │                                                                    │    │
│   │   • ralph run --prd-json .ralph/prd.json                          │    │
│   │   • Full task loop with anti-gaming                                │    │
│   │   • Post-completion verification                                   │    │
│   │                                                                    │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │               STEP 5: Create Pull Request                          │    │
│   │                                                                    │    │
│   │   • git push -u origin {branch_name}                              │    │
│   │   • gh pr create --title "Ralph: {priority_item}"                 │    │
│   │   • Include task summary and progress log                          │    │
│   │                                                                    │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## File Artifacts

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FILE ARTIFACTS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  .ralph/                         (Permanent - committed to git)             │
│  ├── ralph.yml                   Configuration                              │
│  ├── prd.json                    Current task list                          │
│  ├── progress.txt                Autopilot memory                           │
│  └── archive/                    Completed runs                             │
│                                                                             │
│  .ralph-session/                 (Transient - gitignored)                   │
│  ├── session.json                Session metadata                           │
│  ├── task-status.json            Task completion status                     │
│  ├── task-status.sha256          Tamper detection checksum                  │
│  ├── logs/                                                                  │
│  │   ├── timeline.jsonl          Event log                                  │
│  │   ├── impl-T-001.log          Implementation agent output                │
│  │   ├── test-T-001.log          Test-writing agent output                  │
│  │   └── review-T-001.log        Review agent output                        │
│  ├── artifacts/                                                             │
│  │   ├── screenshots/            UI test screenshots                        │
│  │   ├── snapshots/              Accessibility snapshots                    │
│  │   └── robot/                  Robot Framework outputs                    │
│  └── pids/                                                                  │
│      ├── backend.pid             Backend process ID                         │
│      └── frontend.pid            Frontend process ID                        │
│                                                                             │
│  AGENTS.md                       (Permanent - committed to git)             │
│                                  Agent memory and codebase patterns         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## One-Command Flow Architecture

Ralph provides two one-command flows that automate the entire pipeline from ideation to execution:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ONE-COMMAND FLOW OVERVIEW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ralph flow change              ralph flow new                             │
│         │                              │                                    │
│         ▼                              ▼                                    │
│   ┌───────────┐                  ┌───────────┐                             │
│   │   Chat    │                  │   Init    │ (bootstrap config)          │
│   │  (Claude) │                  └─────┬─────┘                             │
│   └─────┬─────┘                        │                                    │
│         │                              ▼                                    │
│         │                        ┌───────────┐                             │
│         │                        │   Chat    │                             │
│         │                        │  (Claude) │                             │
│         │                        └─────┬─────┘                             │
│         │                              │                                    │
│         └──────────────┬───────────────┘                                    │
│                        │                                                    │
│                        ▼                                                    │
│                  ┌───────────┐                                             │
│                  │   Tasks   │ (generate from markdown)                    │
│                  │ Generator │                                             │
│                  └─────┬─────┘                                             │
│                        │                                                    │
│                        ▼                                                    │
│                  ┌───────────┐                                             │
│                  │ Validate  │ (schema validation)                         │
│                  └─────┬─────┘                                             │
│                        │                                                    │
│                        ▼                                                    │
│                  ┌───────────┐                                             │
│                  │  Approval │ ◀── User reviews tasks                      │
│                  │  Prompt   │                                             │
│                  └─────┬─────┘                                             │
│                        │                                                    │
│                   (y/N)?                                                    │
│                        │                                                    │
│             ┌──────────┴──────────┐                                        │
│             │                     │                                        │
│          [ y ]                 [ n ]                                       │
│             │                     │                                        │
│             ▼                     ▼                                        │
│       ┌───────────┐        ┌───────────┐                                  │
│       │ralph run  │        │  Manual   │                                  │
│       │(verified) │        │  Review   │                                  │
│       └───────────┘        └───────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Change Flow: `ralph flow change`

For making changes to an **existing codebase**. Creates a Change Request document.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CHANGE FLOW (ralph flow change)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Interactive Chat                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Claude Code Session                               │   │
│  │                                                                      │   │
│  │  • Uses .claude/commands/create-change-request.md as template       │   │
│  │  • User discusses the change with Claude                            │   │
│  │  • Claude writes final document to changes/CR-chat-{timestamp}.md   │   │
│  │  • Auto-exits when file is written (--no-auto-exit to keep open)    │   │
│  │                                                                      │   │
│  │  Output: changes/CR-chat-20260126-143052.md                         │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  STEP 2: Task Generation                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Claude Structured Output                         │   │
│  │                                                                      │   │
│  │  • Reads the CR markdown file                                       │   │
│  │  • Sends to Claude with PRD schema constraints                      │   │
│  │  • Generates 8-15 granular tasks (configurable)                     │   │
│  │  • Each task has: id, title, description, acceptanceCriteria        │   │
│  │                                                                      │   │
│  │  Output: .ralph/prd.json                                            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  STEP 3: Schema Validation                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     JSON Schema Validation                           │   │
│  │                                                                      │   │
│  │  • Validates against schemas/prd.schema.json                        │   │
│  │  • Checks required fields: id, title, acceptanceCriteria            │   │
│  │  • Verifies ID format (T-NNN pattern)                               │   │
│  │  • Ensures acceptance criteria is non-empty array                   │   │
│  │                                                                      │   │
│  │  ✓ If valid: proceed to approval                                    │   │
│  │  ✗ If invalid: abort with error details                             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  STEP 4: Review & Approval                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      User Review Prompt                              │   │
│  │                                                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │             REVIEW BEFORE EXECUTION                           │   │   │
│  │  ├──────────────────────────────────────────────────────────────┤   │   │
│  │  │  Source markdown: changes/CR-chat-20260126-143052.md         │   │   │
│  │  │  Task file:       .ralph/prd.json                            │   │   │
│  │  │  Task count:      12                                         │   │   │
│  │  ├──────────────────────────────────────────────────────────────┤   │   │
│  │  │ Tasks preview:                                                │   │   │
│  │  │  T-001: Investigate existing implementation                  │   │   │
│  │  │  T-002: Add required dependencies                            │   │   │
│  │  │  T-003: Create configuration module                          │   │   │
│  │  │  ... and 9 more tasks                                        │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Proceed with execution? [y/N]                                      │   │
│  │                                                                      │   │
│  │  • [y] → Continue to execution                                      │   │
│  │  • [n] → Stop, user reviews .ralph/prd.json manually                │   │
│  │  • --yes flag skips this prompt                                     │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  STEP 5: Verified Execution                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     ralph run (Verified Loop)                        │   │
│  │                                                                      │   │
│  │  For each task in .ralph/prd.json:                                  │   │
│  │    ├── Implementation Agent (makes changes)                         │   │
│  │    ├── Test-Writing Agent (writes tests, guardrailed)               │   │
│  │    ├── Quality Gates (lint, build, test)                            │   │
│  │    └── Review Agent (verifies acceptance criteria)                   │   │
│  │                                                                      │   │
│  │  Anti-Gaming: Session tokens + checksum verification                │   │
│  │  Post-Verification: UI tests, Robot Framework (if configured)       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New Project Flow: `ralph flow new`

For **starting a new project** from scratch. Bootstraps Ralph config first.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NEW PROJECT FLOW (ralph flow new)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Initialize Ralph Configuration                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ralph init                                    │   │
│  │                                                                      │   │
│  │  • Detects project type (--template auto|python|node|fullstack)     │   │
│  │  • Creates .ralph/ directory structure                              │   │
│  │  • Generates ralph.yml with appropriate defaults                    │   │
│  │  • Creates AGENTS.md template                                       │   │
│  │  • --force overwrites existing config                               │   │
│  │                                                                      │   │
│  │  Output:                                                            │   │
│  │    .ralph/                                                          │   │
│  │    ├── ralph.yml    (service ports, gates, test paths)              │   │
│  │    ├── prd.json     (empty, will be generated)                      │   │
│  │    └── progress.txt (autopilot memory)                              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  STEP 2: Interactive Chat (PRD Creation)                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Claude Code Session                               │   │
│  │                                                                      │   │
│  │  • Uses .claude/commands/create-prd.md as template                  │   │
│  │  • User describes the project requirements                          │   │
│  │  • Claude helps structure the PRD                                   │   │
│  │  • Writes document to tasks/prd-{name}.md                           │   │
│  │                                                                      │   │
│  │  Output: tasks/prd-my-feature.md                                    │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  STEPS 3-5: Same as Change Flow                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  3. Task Generation   → Claude generates tasks from PRD markdown    │   │
│  │  4. Schema Validation → Validates against prd.schema.json           │   │
│  │  5. Review & Approval → Shows task preview, waits for [y/N]         │   │
│  │  6. Verified Execution → Runs ralph run with anti-gaming            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Verified Task Loop: Deep Dive

The core of Ralph is the verified task loop. Here's how each task progresses through the system:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VERIFIED TASK LOOP (ralph run)                       │
│                        Per-Task Execution Detail                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        SESSION INITIALIZATION                        │   │
│  │                                                                      │   │
│  │  1. Generate unique session token: ralph-YYYYMMDD-HHMMSS-{hex}      │   │
│  │  2. Create .ralph-session/ directory                                │   │
│  │  3. Initialize task-status.json with all tasks                      │   │
│  │  4. Compute and store checksum (task-status.sha256)                 │   │
│  │  5. Load AGENTS.md for codebase context                             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    FOR EACH PENDING TASK                             │   │
│  │                                                                      │   │
│  │  Task Queue: T-001 → T-002 → T-003 → ... → T-NNN                   │   │
│  │  (Ordered by priority field, lower numbers first)                   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                                                                     │  │
│   │  ┌────────────────────────────────────────────────────────────┐    │  │
│   │  │               PHASE 1: IMPLEMENTATION AGENT                 │    │  │
│   │  │                                                             │    │  │
│   │  │  Input:                                                     │    │  │
│   │  │    • Task description + acceptance criteria                 │    │  │
│   │  │    • Session token (must be in completion signal)           │    │  │
│   │  │    • Previous feedback (if retry)                           │    │  │
│   │  │    • AGENTS.md context                                      │    │  │
│   │  │                                                             │    │  │
│   │  │  Tools: All (Read, Write, Edit, Shell, Browser, etc.)       │    │  │
│   │  │                                                             │    │  │
│   │  │  Must emit: <task-done session="{token}">completion</task>  │    │  │
│   │  │                                                             │    │  │
│   │  │  ✓ Valid signal → Continue to test writing                  │    │  │
│   │  │  ✗ Invalid/missing → Retry with feedback (up to N times)    │    │  │
│   │  │                                                             │    │  │
│   │  └──────────────────────────┬─────────────────────────────────┘    │  │
│   │                             │                                       │  │
│   │                             ▼                                       │  │
│   │  ┌────────────────────────────────────────────────────────────┐    │  │
│   │  │               PHASE 2: TEST-WRITING AGENT                   │    │  │
│   │  │                        (Guardrailed)                        │    │  │
│   │  │                                                             │    │  │
│   │  │  Before Agent:                                              │    │  │
│   │  │    └── Snapshot current git state                           │    │  │
│   │  │                                                             │    │  │
│   │  │  Input:                                                     │    │  │
│   │  │    • Task context (what was implemented)                    │    │  │
│   │  │    • Allowed test paths from ralph.yml                      │    │  │
│   │  │    • Session token                                          │    │  │
│   │  │                                                             │    │  │
│   │  │  Tools: Read, Grep, Glob, Edit, Write (path-restricted)     │    │  │
│   │  │                                                             │    │  │
│   │  │  After Agent:                                               │    │  │
│   │  │    └── Check all new/modified files                         │    │  │
│   │  │    └── Files NOT in test paths → REVERT                     │    │  │
│   │  │                                                             │    │  │
│   │  │  Must emit: <tests-done session="{token}">summary</tests>   │    │  │
│   │  │                                                             │    │  │
│   │  │  ✓ Valid signal → Continue to gates                         │    │  │
│   │  │  ✗ Invalid/missing → Retry with feedback                    │    │  │
│   │  │                                                             │    │  │
│   │  └──────────────────────────┬─────────────────────────────────┘    │  │
│   │                             │                                       │  │
│   │                             ▼                                       │  │
│   │  ┌────────────────────────────────────────────────────────────┐    │  │
│   │  │                PHASE 3: QUALITY GATES                       │    │  │
│   │  │                   (Script-Enforced)                         │    │  │
│   │  │                                                             │    │  │
│   │  │  Gate Types (from ralph.yml):                               │    │  │
│   │  │                                                             │    │  │
│   │  │  build gates (fast):          full gates (comprehensive):   │    │  │
│   │  │    • ruff check .              • ruff check .               │    │  │
│   │  │    • mypy --strict             • mypy --strict              │    │  │
│   │  │    • tsc --noEmit              • tsc --noEmit               │    │  │
│   │  │                                • pytest                     │    │  │
│   │  │                                • npm test                   │    │  │
│   │  │                                                             │    │  │
│   │  │  Execution:                                                 │    │  │
│   │  │    • Run each command sequentially                          │    │  │
│   │  │    • Capture stdout/stderr to gate logs                     │    │  │
│   │  │    • First failure stops the gate sequence                  │    │  │
│   │  │                                                             │    │  │
│   │  │  ✓ All pass → Continue to review                            │    │  │
│   │  │  ✗ Any fail → Feed error output back to implementation      │    │  │
│   │  │                                                             │    │  │
│   │  └──────────────────────────┬─────────────────────────────────┘    │  │
│   │                             │                                       │  │
│   │                             ▼                                       │  │
│   │  ┌────────────────────────────────────────────────────────────┐    │  │
│   │  │                 PHASE 4: REVIEW AGENT                       │    │  │
│   │  │                    (Read-Only)                              │    │  │
│   │  │                                                             │    │  │
│   │  │  Input:                                                     │    │  │
│   │  │    • Task acceptance criteria                               │    │  │
│   │  │    • Current codebase state                                 │    │  │
│   │  │    • Session token                                          │    │  │
│   │  │                                                             │    │  │
│   │  │  Tools: Read, Grep, Glob ONLY (no writes allowed)           │    │  │
│   │  │                                                             │    │  │
│   │  │  Reviews each acceptance criterion:                         │    │  │
│   │  │    ✓ File exists: Check file path                           │    │  │
│   │  │    ✓ Contains code: Grep for expected content               │    │  │
│   │  │    ✓ Tests pass: Verified by gates already                  │    │  │
│   │  │    ✓ API works: Check route definitions                     │    │  │
│   │  │                                                             │    │  │
│   │  │  Must emit one of:                                          │    │  │
│   │  │    <review-approved session="{token}">✓ all criteria</...>  │    │  │
│   │  │    <review-rejected session="{token}">missing: X</...>      │    │  │
│   │  │                                                             │    │  │
│   │  │  ✓ Approved → Mark task complete, move to next              │    │  │
│   │  │  ✗ Rejected → Feed rejection back to implementation         │    │  │
│   │  │                                                             │    │  │
│   │  └──────────────────────────┬─────────────────────────────────┘    │  │
│   │                             │                                       │  │
│   │                             ▼                                       │  │
│   │  ┌────────────────────────────────────────────────────────────┐    │  │
│   │  │                 TASK COMPLETION                             │    │  │
│   │  │                                                             │    │  │
│   │  │  1. Script marks task.passes = true in prd.json             │    │  │
│   │  │     (Agents NEVER write to prd.json directly)               │    │  │
│   │  │                                                             │    │  │
│   │  │  2. Update task-status.json with completion                 │    │  │
│   │  │                                                             │    │  │
│   │  │  3. Recompute checksum for tamper detection                 │    │  │
│   │  │                                                             │    │  │
│   │  │  4. Log to timeline.jsonl                                   │    │  │
│   │  │                                                             │    │  │
│   │  │  5. Move to next pending task                               │    │  │
│   │  │                                                             │    │  │
│   │  └────────────────────────────────────────────────────────────┘    │  │
│   │                                                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│                        (repeat for each task)                               │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST-COMPLETION VERIFICATION                      │   │
│  │                     (After All Tasks Complete)                       │   │
│  │                                                                      │   │
│  │  Phase 1: Build/Runtime Checks                                      │   │
│  │    • Re-run all quality gates                                       │   │
│  │    • Start backend/frontend services                                │   │
│  │    • Health check endpoints                                         │   │
│  │                                                                      │   │
│  │  Phase 2: Agent-Browser UI Tests (if configured)                    │   │
│  │    • Navigate to key pages                                          │   │
│  │    • Verify UI elements render                                      │   │
│  │    • Take accessibility snapshots                                   │   │
│  │    • On failure: Planning Agent → Fix Agent → Retry                 │   │
│  │                                                                      │   │
│  │  Phase 3: Robot Framework Tests (if configured)                     │   │
│  │    • Run Playwright-based regression tests                          │   │
│  │    • Deterministic, repeatable assertions                           │   │
│  │    • On failure: Planning Agent → Fix Agent → Retry                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Task Iteration & Retry Flow

When a task fails at any phase, it loops back with feedback:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TASK ITERATION & RETRY FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  iteration = 0                                                              │
│  max_iterations = 30 (configurable)                                         │
│  feedback = None                                                            │
│                                                                             │
│  while iteration < max_iterations:                                          │
│      │                                                                      │
│      │  ┌──────────────────────────────────────────────────────────────┐   │
│      ├─▶│ Implementation Agent (with feedback from previous iteration) │   │
│      │  └─────────────────┬────────────────────────────────────────────┘   │
│      │                    │                                                 │
│      │         ┌──────────┴──────────┐                                      │
│      │         │  Signal Valid?      │                                      │
│      │         └──────────┬──────────┘                                      │
│      │              │           │                                           │
│      │           [YES]        [NO]                                          │
│      │              │           │                                           │
│      │              │           └──▶ feedback = "Missing/invalid signal"    │
│      │              │                         │                             │
│      │              │                         └──▶ iteration++ ─────┐       │
│      │              ▼                                               │       │
│      │  ┌──────────────────────────────────────────────────────┐   │       │
│      │  │ Test-Writing Agent                                    │   │       │
│      │  └─────────────────┬────────────────────────────────────┘   │       │
│      │                    │                                         │       │
│      │         ┌──────────┴──────────┐                              │       │
│      │         │  Signal Valid?      │                              │       │
│      │         └──────────┬──────────┘                              │       │
│      │              │           │                                   │       │
│      │           [YES]        [NO]                                  │       │
│      │              │           │                                   │       │
│      │              │           └──▶ feedback = "Missing signal"    │       │
│      │              │                         │                     │       │
│      │              │                         └──▶ iteration++ ─────┤       │
│      │              ▼                                               │       │
│      │  ┌──────────────────────────────────────────────────────┐   │       │
│      │  │ Quality Gates                                         │   │       │
│      │  └─────────────────┬────────────────────────────────────┘   │       │
│      │                    │                                         │       │
│      │         ┌──────────┴──────────┐                              │       │
│      │         │   All Passed?       │                              │       │
│      │         └──────────┬──────────┘                              │       │
│      │              │           │                                   │       │
│      │           [YES]        [NO]                                  │       │
│      │              │           │                                   │       │
│      │              │           └──▶ feedback = gate_error_output   │       │
│      │              │                         │                     │       │
│      │              │                         └──▶ iteration++ ─────┤       │
│      │              ▼                                               │       │
│      │  ┌──────────────────────────────────────────────────────┐   │       │
│      │  │ Review Agent                                          │   │       │
│      │  └─────────────────┬────────────────────────────────────┘   │       │
│      │                    │                                         │       │
│      │         ┌──────────┴──────────┐                              │       │
│      │         │    Approved?        │                              │       │
│      │         └──────────┬──────────┘                              │       │
│      │              │           │                                   │       │
│      │           [YES]        [NO]                                  │       │
│      │              │           │                                   │       │
│      │              │           └──▶ feedback = rejection_reason    │       │
│      │              │                         │                     │       │
│      │              │                         └──▶ iteration++ ─────┘       │
│      │              │                                                       │
│      │              ▼                                                       │
│      │     ╔═══════════════════════════╗                                   │
│      │     ║   TASK COMPLETE! ✓        ║                                   │
│      │     ║   Mark passes = true      ║                                   │
│      │     ║   Move to next task       ║                                   │
│      │     ╚═══════════════════════════╝                                   │
│      │                                                                      │
│      └──────────────────────────────────────────────────────────────────────┘
│                                                                             │
│  If iteration >= max_iterations:                                            │
│     ╔═══════════════════════════════════════════════════════╗              │
│     ║   TASK FAILED ✗                                        ║              │
│     ║   Log failure reason                                   ║              │
│     ║   Stop execution (fail-fast)                           ║              │
│     ╚═══════════════════════════════════════════════════════╝              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Signal Validation Protocol

Every agent must emit a completion signal with the correct session token:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SIGNAL VALIDATION PROTOCOL                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SIGNAL TYPES:                                                              │
│                                                                             │
│  Implementation:   <task-done session="{token}">summary</task-done>         │
│  Test-writing:     <tests-done session="{token}">files</tests-done>         │
│  Review (pass):    <review-approved session="{token}">✓</review-approved>   │
│  Review (fail):    <review-rejected session="{token}">why</review-rejected> │
│  Fix:              <fix-done session="{token}">changes</fix-done>           │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  VALIDATION FLOW:                                                           │
│                                                                             │
│  Agent Output                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌────────────────────────────┐                                            │
│  │ Parse output for signal    │                                            │
│  │ using regex pattern        │                                            │
│  └─────────────┬──────────────┘                                            │
│                │                                                            │
│       ┌────────┴────────┐                                                   │
│       │ Signal Found?   │                                                   │
│       └────────┬────────┘                                                   │
│           │         │                                                       │
│        [YES]      [NO] ─────────────────────┐                              │
│           │                                  │                              │
│           ▼                                  ▼                              │
│  ┌─────────────────────────┐      ┌──────────────────────────┐             │
│  │ Extract session attr    │      │ Return: Invalid          │             │
│  └─────────────┬───────────┘      │ Feedback: "Emit signal   │             │
│                │                   │ with token {expected}"   │             │
│       ┌────────┴────────┐         └──────────────────────────┘             │
│       │ Token matches?  │                                                   │
│       │ expected token  │                                                   │
│       └────────┬────────┘                                                   │
│           │         │                                                       │
│        [YES]      [NO] ─────────────────────┐                              │
│           │                                  │                              │
│           ▼                                  ▼                              │
│  ┌─────────────────────────┐      ┌──────────────────────────┐             │
│  │ Return: Valid ✓         │      │ Return: Invalid          │             │
│  │ Signal content usable   │      │ Feedback: "Token         │             │
│  └─────────────────────────┘      │ mismatch: got {got},     │             │
│                                    │ expected {expected}"     │             │
│                                    └──────────────────────────┘             │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  ANTI-GAMING PURPOSE:                                                       │
│                                                                             │
│  • Token is unique per session (timestamp + random hex)                    │
│  • Prevents agents from using pre-written signals                          │
│  • Forces agents to actually complete the work to emit signal              │
│  • Combined with checksum verification prevents status tampering           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*See [module-design.md](../specs/module-design.md) for detailed API specifications.*
