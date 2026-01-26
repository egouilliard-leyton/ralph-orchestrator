# ralph-orchestrator

A CLI tool for orchestrating verified, autonomous software development workflows using Claude Code.

## Overview

Ralph Orchestrator (`ralph`) automates the software development lifecycle by coordinating Claude Code through a structured, verified task loop. It ensures code quality through multiple agent phases, quality gates, and anti-gaming measures.

### Key Features

- **Verified Task Loop** - Each task passes through implementation, test-writing, quality gates, and review phases
- **Anti-Gaming Protection** - Session tokens and checksum verification prevent agents from bypassing quality checks
- **Quality Gates** - Configurable build, lint, and test commands that must pass before task completion
- **Autopilot Mode** - Fully autonomous pipeline: analyze reports, generate PRDs, create tasks, execute, and open PRs
- **Guardrails** - Test-writing agents are restricted to test directories only
- **Session Management** - Full audit trail with timeline logging and artifact capture

### How It Works

1. Define tasks in `.ralph/prd.json` with acceptance criteria
2. Ralph invokes Claude Code for each task phase:
   - **Implementation Agent** - Makes code changes
   - **Test Writing Agent** - Writes tests (guardrailed)
   - **Quality Gates** - Runs configured checks (lint, build, test)
   - **Review Agent** - Verifies acceptance criteria
3. Each agent must emit a completion signal with the session token
4. Tasks are marked complete only when all phases pass

## Inspiration

This project is inspired by and builds upon ideas from:

- [ralph-claude-code](https://github.com/frankbria/ralph-claude-code) - The original Ralph pattern for verified AI-assisted development
- [compound-product](https://github.com/snarktank/compound-product) - Compound product methodology for incremental, verified improvements

## Quick Start

### Installation

```bash
cd ralph-orchestrator
python -m pip install -e .
ralph --help
```

### Initialize a Project

```bash
ralph init                    # Creates .ralph/ directory with templates
ralph scan                    # Verify environment and tools
```

### Run Tasks

```bash
ralph run --dry-run           # Preview tasks without execution
ralph run                     # Execute verified task loop
```

### Autopilot Mode

```bash
ralph autopilot --dry-run     # Analyze reports and plan
ralph autopilot               # Full autonomous pipeline
```

## Configuration

Configuration is defined in `.ralph/ralph.yml`:

```yaml
version: "1"

task_source:
  type: prd_json
  path: .ralph/prd.json

gates:
  build:
    - name: lint
      cmd: "ruff check ."
  full:
    - name: test
      cmd: "pytest"

test_paths:
  - "tests/**"
  - "**/*.test.*"
```

## Requirements

- Python 3.10+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Git

## Documentation

See the [docs/](docs/) directory for detailed guides:

- [How to Install](docs/how-to-install.md)
- [How to Use CLI](docs/how-to-use-cli.md)
- [How to Create Tasks](docs/how-to-create-tasks.md)
- [How to Use Autopilot](docs/how-to-use-autopilot.md)

## License

MIT
