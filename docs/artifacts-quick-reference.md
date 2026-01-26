# Ralph Artifacts Quick Reference

A condensed reference for all Ralph orchestrator artifacts, their locations, and purposes.

## File Locations Summary

```
<repo-root>/
├── .ralph/                      # Permanent configuration & tasks
│   ├── ralph.yml               # Main configuration (REQUIRED)
│   ├── prd.json                # Current task list
│   ├── progress.txt            # Progress log (autopilot memory)
│   ├── autopilot/              # Autopilot artifacts
│   │   ├── analysis.json       # Latest analysis output
│   │   └── runs/               # Run history
│   └── archive/                # Archived runs
│
├── .ralph-session/             # Transient session state
│   ├── session.json            # Session metadata
│   ├── task-status.json        # Task completion status
│   ├── task-status.sha256      # Tamper detection checksum
│   ├── logs/                   # Agent and gate logs
│   │   ├── timeline.jsonl      # Event timeline
│   │   ├── impl-T-XXX.log      # Implementation agent logs
│   │   ├── test-T-XXX.log      # Test agent logs
│   │   └── gates-T-XXX.log     # Gate execution logs
│   ├── artifacts/              # Generated artifacts
│   │   ├── screenshots/        # UI test screenshots
│   │   └── robot/              # Robot Framework outputs
│   └── pids/                   # Service process IDs
│
├── AGENTS.md                   # Agent memory (committed)
├── tasks/                      # PRD documents (autopilot)
└── reports/                    # Analysis reports (autopilot input)
```

## Artifact Reference Table

| Artifact | Location | Committed | Purpose | Lifetime |
|----------|----------|-----------|---------|----------|
| Configuration | `.ralph/ralph.yml` | Yes | Repo-specific settings | Permanent |
| Task List | `.ralph/prd.json` | Yes | Executable tasks | Per feature |
| Progress Log | `.ralph/progress.txt` | Yes | Append-only learnings | Persistent |
| Agent Memory | `AGENTS.md` | Yes | Codebase patterns | Persistent |
| Session Metadata | `.ralph-session/session.json` | No | Run state | Per run |
| Task Status | `.ralph-session/task-status.json` | No | Completion tracking | Per run |
| Checksum | `.ralph-session/task-status.sha256` | No | Tamper detection | Per run |
| Timeline | `.ralph-session/logs/timeline.jsonl` | No | Event log | Per run |
| Analysis Output | `.ralph/autopilot/analysis.json` | Optional | Priority selection | Per autopilot run |

## Schema References

| Schema | URL | Validates |
|--------|-----|-----------|
| Configuration | `schemas/ralph-config.schema.json` | `.ralph/ralph.yml` |
| Tasks (canonical) | `schemas/prd.schema.json` | `.ralph/prd.json` |
| CR Markdown | `schemas/cr-markdown.schema.json` | JSON blocks in CR markdown |
| Session | `schemas/session.schema.json` | `.ralph-session/*.json` |
| Autopilot | `schemas/autopilot.schema.json` | `.ralph/autopilot/*.json` |

## Required vs Optional Artifacts

### Always Required
- `.ralph/ralph.yml` - Configuration file
- `.ralph/prd.json` - Task list (or `--cr` flag for markdown)

### Optional (Recommended)
- `AGENTS.md` - Agent memory for pattern accumulation
- `.ralph/progress.txt` - Progress tracking for autopilot

### Auto-Generated (Don't Commit)
- `.ralph-session/` - Entire directory

## Session Token Format

```
ralph-YYYYMMDD-HHMMSS-[12-char-hex]
```

Example: `ralph-20260125-143052-a7b3c9f2d1e8`

## Signal Formats

### Task Done
```xml
<task-done session="ralph-YYYYMMDD-HHMMSS-hex">
  Implementation complete. Changes: ...
</task-done>
```

### Tests Done
```xml
<tests-done session="ralph-YYYYMMDD-HHMMSS-hex">
  Tests written: ...
</tests-done>
```

### Review Approved
```xml
<review-approved session="ralph-YYYYMMDD-HHMMSS-hex">
  Code review passed.
</review-approved>
```

### Review Rejected
```xml
<review-rejected session="ralph-YYYYMMDD-HHMMSS-hex">
  Issues found: ...
</review-rejected>
```

## Task ID Formats

| Type | Pattern | Example |
|------|---------|---------|
| Task (prd.json) | `T-NNN` | T-001, T-002 |
| Subtask | `T-NNN.N` | T-001.1, T-001.2 |
| CR Markdown | Flexible | CR-FEAT-1, TASK-003 |

## Import/Export Quick Reference

| Operation | Command | Description |
|-----------|---------|-------------|
| Import CR | `ralph import --cr FILE.md` | CR markdown → prd.json |
| Export to MD | `ralph export --format markdown` | prd.json → readable markdown |
| Export to CR | `ralph export --format cr` | prd.json → CR-compatible format |
| Update CR | `ralph export --update FILE.md` | Update CR file in-place |
| Validate | `ralph validate --tasks FILE` | Validate against schema |

### CR → prd.json Field Mapping

| CR Field | prd.json Field |
|----------|----------------|
| `id` | `id` (normalized to T-NNN) |
| `description` | `title` + `description` |
| `steps[]` | `acceptanceCriteria[]` |
| `category` | `notes` (preserved) |
| `passes` | `passes` |
| (order) | `priority` |

## Acceptance Criteria Patterns

| Type | Pattern | Example |
|------|---------|---------|
| Command | `Run \`cmd\` - exits with code 0` | `Run \`npm test\` - exits with code 0` |
| File exists | `File \`path\` exists` | `File \`src/auth.py\` exists` |
| File contains | `File \`path\` contains \`str\`` | `File \`config.py\` contains \`SECRET\`` |
| API | `METHOD /url returns status` | `POST /api/login returns 200` |
| Browser | `agent-browser: action - result` | `agent-browser: click "Submit" - redirects` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RALPH_CONFIG` | `.ralph/ralph.yml` | Config file path |
| `RALPH_SESSION_DIR` | `.ralph-session` | Session directory |
| `RALPH_IMPL_MODEL` | (from config) | Implementation model |
| `RALPH_TEST_MODEL` | (from config) | Test-writing model |
| `RALPH_REVIEW_MODEL` | (from config) | Review model |
| `RALPH_CLAUDE_TIMEOUT` | 1800 | Claude call timeout |
| `RALPH_MAX_ITERATIONS` | 30 | Max task iterations |
| `RALPH_CLAUDE_CMD` | `claude` | Claude CLI command |

## Git Ignore Template

```gitignore
# Ralph session (transient - do not commit)
.ralph-session/

# Keep in version control:
# .ralph/ralph.yml
# .ralph/prd.json
# .ralph/progress.txt
# AGENTS.md
```

## CLI Commands Reference

```bash
# Initialize a new repo
ralph init                              # Auto-detect project type
ralph init -t python                    # Use Python template
ralph init -t fullstack -f              # Force overwrite existing

# Run task execution
ralph run                               # Use config defaults
ralph run -p .ralph/prd.json            # Explicit task file
ralph run --cr changes/CR-feature.md    # CR markdown compat mode
ralph run --task T-003                  # Run specific task only
ralph run --gates build                 # Fast gates only
ralph run --post-verify off             # Skip post-verification

# Run verification only
ralph verify                            # Full verification
ralph verify --ui --robot               # UI and Robot tests
ralph verify --fix                      # Auto-fix failures
ralph verify --skip-services            # Use running services

# Run autopilot mode
ralph autopilot                         # Use config defaults
ralph autopilot -r ./reports            # Specify reports dir
ralph autopilot --create-pr             # Create PR on completion
ralph autopilot --dry-run               # Analyze only, don't execute

# Import/Export tasks
ralph import --cr changes/CR-feature.md           # Import CR to prd.json
ralph import --cr changes/CR-feature.md --dry-run # Preview import
ralph export --format markdown --output tasks/    # Export to markdown
ralph export --format cr --update changes/CR.md   # Update CR in-place
ralph validate --tasks .ralph/prd.json            # Validate task list
ralph validate --cr changes/CR-feature.md         # Validate CR format

# Preflight environment check
ralph scan                              # Check all tools
ralph scan --fix                        # Show fix instructions
ralph scan --json                       # JSON output
ralph scan --strict                     # Fail on warnings
```

See [CLI Contract Specification](../specs/cli-contract.md) for complete command documentation.

## Template Files

| Template | Use Case |
|----------|----------|
| `ralph.yml.minimal` | Any project, bare minimum |
| `ralph.yml.python` | Python-only (pytest, mypy, ruff) |
| `ralph.yml.node` | Node.js/TypeScript (npm, tsc) |
| `ralph.yml.fullstack` | Python backend + Node frontend |
| `prd.json.template` | Task list starter |
| `progress.txt.template` | Progress log starter |
| `AGENTS.md.template` | Agent memory starter |

---

*See [Canonical Artifacts Specification](../specs/canonical-artifacts.md) for complete documentation.*
