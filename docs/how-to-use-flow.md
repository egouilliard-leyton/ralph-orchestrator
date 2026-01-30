# How To Use Ralph Flow Commands

This guide explains how to use Ralph's one-command flow pipelines to automate the entire development cycle from conversation to execution.

## Prerequisites

- Ralph CLI installed (`pipx install ralph-orchestrator`)
- Claude CLI installed and authenticated
- Git repository initialized
- Internet connection

## Overview

Ralph provides two one-command flows that combine multiple steps into a single automated pipeline:

| Command | Purpose | Starting Point |
|---------|---------|----------------|
| `ralph flow change` | Modify existing codebase | Existing project with Ralph config |
| `ralph flow new` | Start new project | Empty or minimal repository |

Both flows follow the same core pattern:

```
Chat → Generate Tasks → Validate → Approve → Execute
```

## Steps

### 1. Run the Flow Command

**For an existing codebase** (most common):

```bash
ralph flow change
```

**For a new project:**

```bash
ralph flow new
```

### 2. Interact with Claude

After running the command, Claude Code opens in interactive mode.

1. Describe what you want to build or change.
2. Answer Claude's clarifying questions.
3. Collaborate to define requirements and acceptance criteria.
4. When ready, ask Claude to write the document.

Claude will automatically write the document to the appropriate location:
- **Change flow**: `changes/CR-chat-{timestamp}.md`
- **New project flow**: `tasks/prd-{name}.md`

Once the file is written, Ralph automatically continues to the next step.

### 3. Review the Approval Prompt

After task generation and validation, Ralph shows a review screen:

```
┌──────────────────────────────────────────────────────┐
│             REVIEW BEFORE EXECUTION                  │
├──────────────────────────────────────────────────────┤
│  Source markdown: changes/CR-chat-20260126-143052.md │
│  Task file:       .ralph/prd.json                    │
│  Task count:      12                                 │
├──────────────────────────────────────────────────────┤
│ Tasks preview:                                       │
│  T-001: Investigate existing implementation          │
│  T-002: Add required dependencies                    │
│  T-003: Create configuration module                  │
│  T-004: Implement core service                       │
│  ... and 8 more tasks                                │
└──────────────────────────────────────────────────────┘

Proceed with execution? [y/N]
```

### 4. Approve or Review Manually

You have three options:

- **Type `y`** → Ralph immediately starts executing tasks
- **Type `n`** (or press Enter) → Flow stops, you can review `.ralph/prd.json` and run `ralph run` later
- **Use `--yes` flag** → Skip this prompt entirely (for automation)

### 5. Monitor Execution

If you approved, Ralph runs the verified task loop:

```
[T-001] Investigate existing implementation
------------------------------------------------------------
  ▶ Implementation agent starting...
  ✓ Implementation complete (45s)
  ▶ Test-writing agent starting...
  ✓ Tests written (23s)
  ▶ Running gates (full)...
    ✓ lint (2.1s)
    ✓ test (8.3s)
  ▶ Review agent starting...
  ✓ Review approved (18s)
  ✓ Task complete

[T-002] Add required dependencies
------------------------------------------------------------
...
```

### 6. Check Results

After completion, you'll see a summary:

```
============================================================
  SUMMARY
============================================================
  Tasks: 12/12 completed
  Gates: 2/2 passed
  UI Tests: 3/3 passed
  Duration: 23m 45s
  Session logs: .ralph-session/logs/
============================================================
```

## Expected Results

After successful execution:

- All tasks marked as `passes: true` in `.ralph/prd.json`
- Quality gates passing (lint, tests)
- Change request document saved in `changes/`
- Session logs available in `.ralph-session/logs/`
- Screenshots (if UI tests ran) in `.ralph-session/artifacts/screenshots/`

## Common Options

### Control Task Count

By default, Ralph generates 8-15 tasks. Adjust with:

```bash
ralph flow change --task-count 5-10
ralph flow change --task-count 3-8
```

### Preview Without Executing

Generate tasks but don't run them:

```bash
ralph flow change --dry-run
```

### Skip the Approval Prompt

For fully automated pipelines:

```bash
ralph flow change --yes
```

### Use a Different Model

```bash
ralph flow change --model opus
ralph flow change --model sonnet
```

### New Project with Specific Template

```bash
ralph flow new --template python
ralph flow new --template node
ralph flow new --template fullstack
ralph flow new --template minimal
```

### Force Overwrite Existing Config

```bash
ralph flow new --force
```

### Custom Output Paths

```bash
ralph flow change --out-md changes/my-feature.md --out-json .ralph/my-feature.json
```

### Run Tasks in Parallel

Enable parallel execution for non-overlapping tasks:

```bash
ralph flow change --parallel
ralph flow change --parallel --max-parallel 5
```

Parallel mode analyzes tasks to estimate file dependencies and runs non-overlapping tasks concurrently.

## Troubleshooting

### Chat exits without writing file

The chat auto-exits when it detects the output file has been written. If Claude didn't write the file:

1. Run with `--no-auto-exit` to keep the chat open:
   ```bash
   ralph chat --mode change-request --no-auto-exit
   ```
2. Explicitly ask Claude to write the document.
3. Once written, exit manually with `Ctrl+C`.

### Task generation fails

If task generation returns an error:

1. Check the markdown file was written correctly.
2. Ensure the file contains structured content Claude can parse.
3. Run task generation separately for debugging:
   ```bash
   ralph tasks --from changes/CR-chat-YYYYMMDD-HHMMSS.md --dry-run
   ```

### Approval prompt doesn't appear

If you're running in a non-interactive environment (CI/CD, scripts):

- Use `--yes` to skip the prompt, or
- Run `ralph run` separately after generating tasks

### Task execution fails

If a task fails during execution:

1. Check logs in `.ralph-session/logs/impl-T-XXX.log`
2. Review the task's acceptance criteria in `.ralph/prd.json`
3. Fix issues and resume with:
   ```bash
   ralph run --from-task T-XXX
   ```

## Additional Information

### How the Flow Works Internally

```
ralph flow change
      │
      ├─1─▶ Claude Chat Session
      │     └── Writes: changes/CR-chat-{timestamp}.md
      │
      ├─2─▶ Task Generation (Claude structured output)
      │     └── Writes: .ralph/prd.json
      │
      ├─3─▶ Schema Validation
      │     └── Checks against schemas/prd.schema.json
      │
      ├─4─▶ Approval Prompt (interactive)
      │     └── Shows task preview, waits for [y/N]
      │
      └─5─▶ Verified Execution (ralph run)
            ├── Implementation Agent
            ├── Test-Writing Agent (guardrailed)
            ├── Quality Gates
            └── Review Agent
```

### Difference from Manual Steps

Using `ralph flow change` is equivalent to:

```bash
# Manual approach (4 commands):
ralph chat --mode change-request
ralph tasks --from changes/CR-....md --out .ralph/prd.json
ralph validate-tasks
ralph run

# One-command approach (1 command):
ralph flow change
```

### When to Use Each Command

| Situation | Recommended Command |
|-----------|---------------------|
| Adding a feature to existing code | `ralph flow change` |
| Fixing a bug in existing code | `ralph flow change` |
| Refactoring existing code | `ralph flow change` |
| Starting a brand new project | `ralph flow new` |
| Project has no `.ralph/` directory | `ralph flow new` |

### Customizing the Chat Templates

Ralph uses templates from your repo to guide the Claude conversation:

- **Change requests**: `.claude/commands/create-change-request.md`
- **PRDs**: `.claude/commands/create-prd.md`

If these files exist, Claude uses them for context. You can customize them to match your team's requirements format.

## Related Guides

- [How To Use the CLI](./how-to-use-cli.md) - Full CLI reference
- [How To Create Tasks](./how-to-create-tasks.md) - Manual task creation
- [How To Use Autopilot](./how-to-use-autopilot.md) - Fully automated pipeline
- [Architecture Diagram](./architecture-diagram.md) - Visual system overview
- [How To Troubleshoot](./how-to-troubleshoot.md) - Common issues and solutions
