# ralph-orchestrator

A CLI tool for orchestrating verified, autonomous software development workflows using Claude Code. Now with a modern web UI for real-time monitoring and multi-project management.

## Overview

Ralph Orchestrator (`ralph`) automates the software development lifecycle by coordinating Claude Code through a structured, verified task loop. It ensures code quality through multiple agent phases, quality gates, and anti-gaming measures.

### Key Features

- **Verified Task Loop** - Each task passes through implementation, test-writing, quality gates, and review phases
- **Anti-Gaming Protection** - Session tokens and checksum verification prevent agents from bypassing quality checks
- **Quality Gates** - Configurable build, lint, and test commands that must pass before task completion
- **Parallel Task Execution** - Run independent tasks concurrently with `--parallel` flag using file-set pre-allocation
- **Enhanced Subtasks** - Checkpoint mode for progress tracking, independent mode for separate verification loops
- **Autopilot Mode** - Fully autonomous pipeline: analyze reports, research codebase, generate PRDs, create tasks, execute, and open PRs
- **Research Sub-agents** - Backend, frontend, and web researchers gather context before PRD generation
- **Guardrails** - Test-writing agents are restricted to test directories only
- **Session Management** - Full audit trail with timeline logging and artifact capture
- **Web UI Dashboard** - Modern React-based interface for real-time monitoring (via `ralph serve`)
- **Multi-Project Management** - Discover and manage multiple Ralph projects from a single dashboard
- **Kanban Task Board** - Visual task management with drag-and-drop support
- **Git Integration** - Create branches and PRs directly from the UI

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
ralph run --parallel          # Run tasks in parallel when possible
ralph run --parallel --max-parallel 5   # Limit to 5 concurrent groups
```

### One-Command Flows

```bash
ralph flow change             # Chat → tasks → validate → approve → run
ralph flow new                # Init → chat → tasks → validate → approve → run
```

These flows open an interactive Claude session to discuss your requirements, then automatically generate tasks, validate them, show a preview for approval, and execute the verified loop.

### Autopilot Mode

```bash
ralph autopilot --dry-run     # Analyze reports and plan
ralph autopilot               # Full autonomous pipeline
```

### Web UI (ralph serve)

Start the web UI for real-time monitoring and visual task management:

```bash
ralph serve                   # Start backend API on port 8000
ralph serve --port 9000       # Use custom port
ralph serve --host 0.0.0.0    # Allow external connections
```

Then open http://localhost:3001 in your browser to access the dashboard.

**Features:**
- **Dashboard** - Overview of all Ralph projects with aggregate statistics
- **Task Board** - Kanban-style board with drag-and-drop task reordering
- **Real-time Updates** - WebSocket-based live updates during task execution
- **Log Viewer** - Browse and search execution logs with filtering
- **Timeline** - Chronological view of all orchestration events
- **Git Panel** - Create branches and pull requests from completed tasks
- **Config Editor** - Visual editor for `ralph.yml` configuration

**Starting the Frontend (Development):**

```bash
cd frontend
npm install
npm run dev                   # Start frontend on port 3001
```

**API Endpoints:**

The `ralph serve` command exposes a REST API at `http://localhost:8000/api/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all discovered Ralph projects |
| `/api/projects/{id}/tasks` | GET | Get tasks from project's prd.json |
| `/api/projects/{id}/run` | POST | Start task execution |
| `/api/projects/{id}/stop` | POST | Cancel running execution |
| `/api/projects/{id}/config` | GET/PUT | Read/update configuration |
| `/api/projects/{id}/branches` | GET/POST | List/create git branches |
| `/api/projects/{id}/pr` | POST | Create pull request |
| `/api/projects/{id}/logs` | GET | List/retrieve log files |
| `/api/projects/{id}/timeline` | GET | Get timeline events |
| `/ws/{project_id}` | WS | WebSocket for real-time updates |
| `/api/health` | GET | Health check endpoint |

See [API Documentation](docs/api.md) for full endpoint reference.

## UI Testing (Browser Automation)

Ralph includes integrated UI testing capabilities using two frameworks:

### Agent-Browser (Claude-Powered)

Agent-browser is an AI-powered browser automation tool that executes natural language test instructions. Claude controls the browser to perform actions and verify expected outcomes.

**Configuration in `.ralph/ralph.yml`:**

```yaml
ui:
  agent_browser:
    enabled: true
    tests:
      - name: login_test
        action: "Click the login button and enter username 'test@example.com'"
        expected: "User should see the dashboard with welcome message"
      - name: navigation_test
        action: "Navigate to the settings page using the sidebar menu"
        expected: "Settings page should display user preferences"
```

Or use a script for more complex scenarios:

```yaml
ui:
  agent_browser:
    enabled: true
    script: ".ralph/ui-tests.sh"
```

**Features:**
- Natural language test definitions
- Automatic screenshot capture on failure
- Test artifacts saved to `.ralph-session/artifacts/agent-browser/`

### Robot Framework

For keyword-driven acceptance testing, Ralph integrates with Robot Framework using the Browser library (Chromium).

```yaml
ui:
  robot:
    enabled: true
    suite: "tests/acceptance"
    variables:
      TIMEOUT: "10s"
```

**Running UI tests:**

```bash
ralph verify --ui              # Run agent-browser tests
ralph verify --robot           # Run Robot Framework tests
ralph verify --ui --robot      # Run both
ralph verify --base-url http://localhost:3000  # Override base URL
```

**Controlling UI tests in `ralph run`:**

```bash
ralph run --with-smoke         # Enable smoke tests (agent-browser)
ralph run --no-smoke           # Disable smoke tests
ralph run --with-robot         # Enable Robot Framework tests
ralph run --no-robot           # Disable Robot Framework tests
```

UI tests run after quality gates pass and services are started. Failed tests trigger automatic fix loops when `--fix` is enabled.

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
- [Architecture Guide](docs/architecture.md) - Service layer and API design
- [API Reference](docs/api.md) - Full REST API documentation

## License

MIT
