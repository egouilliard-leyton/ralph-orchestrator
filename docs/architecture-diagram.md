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

---

*See [module-design.md](../specs/module-design.md) for detailed API specifications.*
