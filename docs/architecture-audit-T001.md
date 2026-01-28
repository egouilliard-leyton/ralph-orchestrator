# Architecture Audit: Services Layer Refactoring

**Task ID:** T-001
**Date:** 2026-01-27
**Purpose:** Identify refactoring boundaries to enable dual-interface (CLI + Web UI) with real-time updates

---

## 1. Module Dependency Map

### 1.1 Core Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           ENTRY POINTS                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  cli.py (commands)     flow.py (pipelines)     autopilot.py (pipeline)   │
│     │                      │                        │                     │
│     ▼                      ▼                        ▼                     │
├──────────────────────────────────────────────────────────────────────────┤
│                        ORCHESTRATION LAYER                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │   run.py    │    │  verify.py  │    │   chat.py   │                   │
│  │ (RunEngine) │    │(VerifyEngine│    │ (ChatRunner)│                   │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┘                   │
│         │                  │                                              │
├─────────┼──────────────────┼─────────────────────────────────────────────┤
│         │   DOMAIN SERVICES LAYER (business logic)                        │
│         ▼                  ▼                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │ session.py  │    │  gates.py   │    │guardrails.py│                   │
│  │ (Session)   │    │(GateRunner) │    │(Guardrail)  │                   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                   │
│         │                  │                  │                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │ signals.py  │    │ config.py   │    │tasks/prd.py │                   │
│  │ (parsing)   │    │(RalphConfig)│    │ (Task model)│                   │
│  └─────────────┘    └─────────────┘    └─────────────┘                   │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│                        AGENT LAYER                                        │
│  ┌─────────────────────────────────┐    ┌─────────────────────────────┐  │
│  │     agents/claude.py            │    │    agents/prompts.py        │  │
│  │     (ClaudeRunner)              │    │    (prompt templates)       │  │
│  └──────────────┬──────────────────┘    └─────────────────────────────┘  │
│                 │                                                         │
├─────────────────┼────────────────────────────────────────────────────────┤
│                 │         INFRASTRUCTURE LAYER                            │
│                 ▼                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │   exec.py   │    │ timeline.py │    │services.py  │                   │
│  │ (subprocess)│    │(JSONL logs) │    │(start/stop) │                   │
│  └─────────────┘    └─────────────┘    └─────────────┘                   │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Detailed Module Dependencies

| Module | Direct Dependencies | Imported By |
|--------|-------------------|-------------|
| **cli.py** | yaml, jsonschema, run*, verify*, autopilot*, flow*, chat* (*lazy imports) | main entry |
| **run.py** | config, session, timeline, tasks/prd, signals, guardrails, gates, agents/claude, agents/prompts, execution_log | cli, flow, autopilot |
| **session.py** | (stdlib only: hashlib, json, secrets, subprocess) | run, verify |
| **gates.py** | config, exec, timeline | run, verify |
| **guardrails.py** | timeline | run |
| **signals.py** | (stdlib only: re) | run |
| **config.py** | (yaml, jsonschema) | all modules |
| **timeline.py** | (stdlib only: json) | run, gates, guardrails, agents/claude, session |
| **exec.py** | (stdlib only: subprocess) | gates, agents/claude, autopilot |
| **agents/claude.py** | exec, timeline | run, verify, chat, autopilot |
| **agents/prompts.py** | (stdlib only) | run, verify |
| **tasks/prd.py** | config | run, cli, autopilot |
| **flow.py** | chat, cli (generate_tasks), run | cli |
| **autopilot.py** | config, exec, timeline, run | cli |
| **verify.py** | config, session, timeline, gates, services, ui, agents/claude, signals | run, cli |
| **chat.py** | agents/claude | cli, flow |
| **services.py** | config, exec, timeline | verify |
| **ui.py** | config, timeline | verify |
| **execution_log.py** | (stdlib only: json) | run |

### 1.3 Coupling Analysis

**Tightly Coupled Components:**
1. `run.py` ↔ `session.py` - Direct state manipulation
2. `run.py` ↔ `timeline.py` - Event logging throughout execution
3. `cli.py` ↔ `run.py` - Options dataclasses shared
4. `gates.py` ↔ `config.py` - GateConfig parsing
5. `autopilot.py` - Contains many internal classes (LLMProvider, ReportAnalyzer, etc.)

**Loosely Coupled Components:**
1. `signals.py` - Pure functions, no external state
2. `exec.py` - Generic subprocess wrapper
3. `agents/prompts.py` - Pure string templates
4. `execution_log.py` - Isolated logging concern

---

## 2. Logic Extraction: CLI → Services Layer

### 2.1 Current cli.py Responsibilities (to extract)

| Function/Logic | Current Location | Extract To | Priority |
|---------------|------------------|------------|----------|
| `generate_tasks_from_markdown()` | cli.py:~595-~680 | `services/task_generation.py` | HIGH |
| `analyze_complexity_for_task_count()` | cli.py:~495-~595 | `services/task_generation.py` | HIGH |
| `_invoke_claude_structured()` | cli.py:~410-~440 | `services/claude_structured.py` | HIGH |
| `validate_against_schema()` | cli.py (duplicate in config.py) | Already in config.py | MEDIUM |
| `load_prd_json()` | cli.py | `services/prd_service.py` | MEDIUM |
| `detect_template()` | cli.py | `services/project_detection.py` | LOW |
| Command handlers | cli.py | Keep in cli.py (thin wrappers) | N/A |

### 2.2 Current run.py Responsibilities (to extract)

| Function/Logic | Current Location | Extract To | Priority |
|---------------|------------------|------------|----------|
| `RunEngine` class | run.py:102-~620 | `services/execution_engine.py` | HIGH |
| `_run_implementation()` | run.py:177-~284 | `services/agent_executor.py` | HIGH |
| `_run_test_writing()` | run.py:~286-~350 | `services/agent_executor.py` | HIGH |
| `_run_gates()` | run.py:~385-~430 | `services/gate_executor.py` | HIGH |
| `_run_review()` | run.py:~430-~520 | `services/agent_executor.py` | HIGH |
| `_run_task_loop()` | run.py:~530-~620 | `services/task_executor.py` | HIGH |
| `run_tasks()` factory | run.py:~620-~750 | `services/execution_service.py` | HIGH |
| Print/output methods | run.py:149-156 | Abstract to `OutputHandler` protocol | HIGH |

### 2.3 Current autopilot.py Responsibilities (to extract)

| Class/Function | Current Location | Extract To | Priority |
|---------------|------------------|------------|----------|
| `LLMProvider` class | autopilot.py:~596-~686 | `services/llm_service.py` | HIGH |
| `ReportDiscovery` class | autopilot.py:~391-~474 | `services/report_service.py` | MEDIUM |
| `ReportAnalyzer` class | autopilot.py:~760-~940 | `services/analysis_service.py` | MEDIUM |
| `BranchManager` class | autopilot.py:~960-~1100 | `services/git_service.py` | MEDIUM |
| `PRDGenerator` class | autopilot.py:~1110-~1240 | `services/prd_generation.py` | MEDIUM |
| `TasksGenerator` class | autopilot.py:~1242-~1380 | `services/task_generation.py` | MEDIUM |
| `PRCreator` class | autopilot.py:~1380-~1500 | `services/pr_service.py` | MEDIUM |
| `AutopilotOrchestrator` | autopilot.py:~1700-~2340 | `services/autopilot_service.py` | MEDIUM |

### 2.4 Proposed Services Layer Structure

```
ralph_orchestrator/
├── services/
│   ├── __init__.py
│   ├── base.py                     # EventEmitter, BaseService
│   ├── execution_service.py        # Main orchestration (from run.py)
│   │   ├── ExecutionService
│   │   ├── TaskExecutor
│   │   └── AgentExecutor
│   ├── task_generation.py          # PRD/task generation (from cli.py)
│   │   ├── TaskGenerationService
│   │   └── ComplexityAnalyzer
│   ├── gate_service.py             # Quality gates (enhanced gates.py)
│   │   └── GateService
│   ├── session_service.py          # Session management (enhanced session.py)
│   │   └── SessionService
│   ├── llm_service.py              # Multi-provider LLM (from autopilot.py)
│   │   └── LLMService
│   ├── git_service.py              # Git operations (from autopilot.py)
│   │   └── GitService
│   ├── prd_service.py              # PRD management
│   │   └── PRDService
│   └── events/
│       ├── __init__.py
│       ├── event_bus.py            # Event emission/subscription
│       ├── event_types.py          # Event type definitions
│       └── handlers.py             # Default handlers (CLI output)
└── (existing modules refactored to use services)
```

---

## 3. Event Emission Points for WebSocket Broadcasting

### 3.1 Existing Events (in timeline.py EventTypes)

| Event Category | Event Name | Current Location | Data Payload |
|---------------|------------|------------------|--------------|
| **Session** | `SESSION_START` | timeline.py:161-173 | task_count, config_path, session_id |
| **Session** | `SESSION_END` | timeline.py:175-191 | status, completed_count, duration_ms |
| **Task** | `TASK_START` | timeline.py:193-199 | task_id, title |
| **Task** | `TASK_COMPLETE` | timeline.py:201-213 | task_id, iterations, duration_ms |
| **Task** | `TASK_FAILED` | timeline.py:215-227 | task_id, reason, iterations |
| **Agent** | `AGENT_START` | timeline.py:229-241 | task_id, role, model |
| **Agent** | `AGENT_COMPLETE` | timeline.py:243-257 | task_id, role, signal, duration_ms |
| **Agent** | `AGENT_FAILED` | timeline.py:259-273 | task_id, role, error, duration_ms |
| **Gate** | `GATES_RUN` | timeline.py:275-289 | gate_type, gate_count, task_id |
| **Gate** | `GATE_PASS` | timeline.py:291-304 | gate_name, duration_ms |
| **Gate** | `GATE_FAIL` | timeline.py:306-323 | gate_name, error, fatal |
| **Service** | `SERVICE_START` | timeline.py:325-331 | service, port |
| **Service** | `SERVICE_READY` | timeline.py:333-346 | service, url, duration_ms |
| **Service** | `SERVICE_FAILED` | timeline.py:348-361 | service, error, duration_ms |
| **UI Test** | `UI_TEST_START` | timeline.py:363-371 | test_name, framework |
| **UI Test** | `UI_TEST_PASS` | timeline.py:373-384 | test_name, duration_ms |
| **UI Test** | `UI_TEST_FAIL` | timeline.py:386-403 | test_name, error, screenshot |
| **Fix Loop** | `FIX_LOOP_START` | timeline.py:405-417 | loop_type, max_iterations |
| **Fix Loop** | `FIX_LOOP_ITERATION` | timeline.py:419-433 | loop_type, iteration, status |
| **Fix Loop** | `FIX_LOOP_END` | timeline.py:435-450 | loop_type, success, iterations |
| **Checksum** | `CHECKSUM_VERIFIED` | timeline.py:452-454 | (none) |
| **Checksum** | `CHECKSUM_FAILED` | timeline.py:456-458 | error |

### 3.2 New Events Needed for Real-Time UI

| Event Name | Purpose | Emission Point |
|-----------|---------|----------------|
| `ITERATION_START` | Track task loop iterations | run.py at start of each iteration |
| `ITERATION_END` | Iteration completion | After each agent phase completes |
| `SIGNAL_DETECTED` | Signal parsing result | After validate_*_signal() calls |
| `OUTPUT_CHUNK` | Streaming Claude output | agents/claude.py (needs modification) |
| `PROGRESS_UPDATE` | Overall progress percentage | run.py in main loop |
| `LOG_ENTRY` | Real-time log streaming | All modules using timeline |
| `GUARDRAIL_CHECK` | Guardrail results | guardrails.py:277-339 |
| `AUTOPILOT_PHASE` | Autopilot phase transitions | autopilot.py _phase_* methods |

### 3.3 Event Bus Implementation Requirements

```python
# services/events/event_bus.py

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Any

class EventEmitter(ABC):
    """Abstract base for event emission."""

    @abstractmethod
    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to all listeners."""
        pass

    @abstractmethod
    def on(self, event_type: str, callback: Callable) -> None:
        """Register a callback for an event type."""
        pass

class EventBus(EventEmitter):
    """Publish-subscribe event bus for real-time updates."""

    _subscribers: Dict[str, List[Callable]] = {}

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to all subscribers."""
        for callback in self._subscribers.get(event_type, []):
            callback(data)
        # Also emit to wildcard subscribers
        for callback in self._subscribers.get("*", []):
            callback(event_type, data)

    def on(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
```

### 3.4 Integration Points in Existing Code

**run.py modifications needed:**
- Line ~149-156: Replace `_print()` with `event_bus.emit("OUTPUT", ...)`
- Line ~530: Add `event_bus.emit("TASK_START", ...)`
- Line ~580: Add `event_bus.emit("TASK_COMPLETE", ...)`
- Line ~600: Add `event_bus.emit("TASK_FAILED", ...)`

**agents/claude.py modifications needed:**
- Line ~165-210: Add streaming output callback for real-time output
- Consider subprocess streaming instead of bulk output capture

**gates.py modifications needed:**
- Line ~157-171: Already uses timeline, add event_bus parallel publish

**timeline.py modifications needed:**
- Line ~93-157: In `log()` method, add optional event_bus.emit() call

---

## 4. CLI Preservation Strategy

### 4.1 Design Principle: Thin CLI Wrappers

Each CLI command should become a thin wrapper that:
1. Parses arguments (keep in cli.py)
2. Converts args to service options (keep in cli.py)
3. Calls service layer (delegate to services/)
4. Formats output for terminal (use OutputHandler)
5. Returns exit code

### 4.2 Refactoring Pattern Example

**Before (current):**
```python
# cli.py
def command_run(args: argparse.Namespace) -> int:
    from .run import run_tasks, RunOptions
    options = RunOptions(...)
    result = run_tasks(config_path, prd_path, options)
    if result.error:
        eprint(f"Error: {result.error}")
    return result.exit_code.value
```

**After (refactored):**
```python
# cli.py
def command_run(args: argparse.Namespace) -> int:
    from .services import ExecutionService
    from .output import CLIOutputHandler

    service = ExecutionService(
        output_handler=CLIOutputHandler(),  # CLI-specific formatting
        event_bus=NoOpEventBus(),           # No real-time events for CLI
    )
    result = service.run_tasks(
        config_path=config_path,
        prd_path=prd_path,
        options=args_to_options(args),
    )
    return result.exit_code.value

# services/execution_service.py
class ExecutionService:
    def __init__(self, output_handler: OutputHandler, event_bus: EventEmitter = None):
        self.output = output_handler
        self.events = event_bus or NoOpEventBus()

    def run_tasks(self, config_path, prd_path, options) -> RunResult:
        # Business logic here
        self.events.emit("TASK_START", {...})
        self.output.task_header(task)
        # ...
```

### 4.3 Output Handler Protocol

```python
# ralph_orchestrator/output/protocols.py
from typing import Protocol

class OutputHandler(Protocol):
    """Protocol for output handling (CLI, WebSocket, etc.)."""

    def print(self, message: str) -> None: ...
    def task_header(self, task: Task) -> None: ...
    def agent_status(self, role: str, status: str) -> None: ...
    def gate_result(self, name: str, passed: bool, duration_ms: int) -> None: ...
    def summary(self, result: RunResult) -> None: ...

# ralph_orchestrator/output/cli.py
class CLIOutputHandler:
    """CLI-specific output formatting."""

    def print(self, message: str) -> None:
        print(message, file=sys.stdout, flush=True)

    def task_header(self, task: Task) -> None:
        self.print(f"\n[{task.id}] {task.title}")
        self.print("-" * 60)
```

### 4.4 Backward Compatibility Checklist

| Command | Current Interface | Preservation Notes |
|---------|------------------|-------------------|
| `ralph init` | `command_init(args)` | Keep as-is, uses templates |
| `ralph scan` | `command_scan(args)` | Keep as-is, simple checks |
| `ralph run` | `command_run(args)` → `run_tasks()` | Wrap ExecutionService |
| `ralph verify` | `command_verify(args)` → `run_verify()` | Wrap VerifyService |
| `ralph autopilot` | `command_autopilot(args)` | Wrap AutopilotService |
| `ralph flow` | `command_flow(args)` → `run_flow()` | Wrap FlowService |
| `ralph chat` | `command_chat(args)` → `run_chat()` | Wrap ChatService |
| `ralph tasks` | `command_tasks(args)` | Wrap TaskGenerationService |

---

## 5. Breaking Change Analysis

### 5.1 Public API Surface

**Current public interfaces:**
- CLI commands (preserved)
- `run_tasks()` function in run.py
- `RunOptions` dataclass
- `RunResult` dataclass
- `load_config()` function
- Signal format (XML tags with session tokens)
- Session directory structure

### 5.2 Potential Breaking Changes

| Change | Risk Level | Mitigation |
|--------|------------|------------|
| Moving `run_tasks()` | MEDIUM | Keep re-export in run.py |
| Moving dataclasses | LOW | Keep re-export at original location |
| New event system | NONE | Additive, opt-in |
| Output handler abstraction | NONE | Default to CLI handler |

### 5.3 Guaranteed Preserved Behavior

1. All CLI commands maintain same arguments and exit codes
2. Configuration format (ralph.yml) unchanged
3. Task file format (prd.json) unchanged
4. Session directory structure unchanged
5. Timeline JSONL format unchanged
6. Signal XML format unchanged
7. Environment variables (RALPH_CLAUDE_CMD, RALPH_CONFIG, RALPH_SESSION_DIR, ANTHROPIC_API_KEY)

---

## 6. CLI Commands - No Breaking Changes Verification

### 6.1 Command Interface Verification

| Command | Arguments | Exit Codes | Verified |
|---------|-----------|------------|----------|
| `ralph init` | `-t/--template`, `-f/--force`, `--no-agents-md`, `--no-prd`, `-o/--output-dir` | 0, 1, 2, 3 | ✅ Preserved |
| `ralph scan` | `--fix`, `--json` | 0, 2 | ✅ Preserved |
| `ralph run` | `-p/--prd-json`, `-t/--task`, `--from-task`, `--max-iterations`, `--gates`, `--dry-run`, `--resume`, `--post-verify`, `--no-post-verify` | 0-9 | ✅ Preserved |
| `ralph verify` | `--gates`, `--ui`, `--no-ui`, `--robot`, `--no-robot`, `--env`, `--fix`, `--fix-iterations`, `--skip-services`, `--base-url`, `-v/--verbose` | 0-9 | ✅ Preserved |
| `ralph autopilot` | `-r/--reports`, `--report`, `--dry-run`, `--create-pr`, `--no-create-pr`, `-b/--branch`, `--no-prd`, `--prd-mode`, `--task-count`, `--analysis-model`, `--recent-days`, `--resume`, `-v/--verbose` | 0-15 | ✅ Preserved |
| `ralph chat` | `--mode`, `--template`, `--out`, `--model`, `--auto-exit`, `--no-auto-exit` | 0, 2 | ✅ Preserved |
| `ralph flow change` | `--task-count`, `--model`, `--out-md`, `--out-json`, `-y/--yes`, `--max-iterations`, `--gates`, `--dry-run`, `-v/--verbose` | 0, 2 | ✅ Preserved |
| `ralph flow new` | Same as change + `-t/--template`, `-f/--force` | 0, 2 | ✅ Preserved |
| `ralph tasks` | `--from` (required), `--out`, `--branch`, `--task-count`, `--model`, `--dry-run` | 0, 1, 2 | ✅ Preserved |

### 6.2 Environment Variables - Preserved

| Variable | Usage | Verified |
|----------|-------|----------|
| `RALPH_CLAUDE_CMD` | Override Claude CLI command | ✅ |
| `RALPH_CONFIG` | Override config file path | ✅ |
| `RALPH_SESSION_DIR` | Override session directory | ✅ |
| `ANTHROPIC_API_KEY` | API key for Claude | ✅ |

### 6.3 File Formats - Preserved

| File | Format | Verified |
|------|--------|----------|
| `.ralph/ralph.yml` | YAML (schemas/ralph-config.schema.json) | ✅ |
| `.ralph/prd.json` | JSON (schemas/prd.schema.json) | ✅ |
| `.ralph-session/session.json` | JSON (schemas/session.schema.json) | ✅ |
| `.ralph-session/task-status.json` | JSON with embedded checksum | ✅ |
| `.ralph-session/logs/timeline.jsonl` | JSONL | ✅ |

### 6.4 Signal Formats - Preserved

| Signal | Format | Verified |
|--------|--------|----------|
| `<task-done session="TOKEN">` | XML with session token | ✅ |
| `<tests-done session="TOKEN">` | XML with session token | ✅ |
| `<review-approved session="TOKEN">` | XML with session token | ✅ |
| `<review-rejected session="TOKEN">` | XML with session token | ✅ |
| `<fix-done session="TOKEN">` | XML with session token | ✅ |
| `<ui-plan session="TOKEN">` | XML with session token | ✅ |
| `<ui-fix-done session="TOKEN">` | XML with session token | ✅ |

---

## 7. Recommended Refactoring Sequence

### Phase 1: Foundation (No breaking changes)
1. Create `services/events/` with EventBus
2. Create `output/` with OutputHandler protocol
3. Add parallel event publishing to timeline.py

### Phase 2: Extract Services (Backward compatible)
1. Create `services/execution_service.py` (wraps run.py logic)
2. Create `services/task_generation.py` (from cli.py)
3. Create `services/gate_service.py` (wraps gates.py)
4. Keep original modules as re-export facades

### Phase 3: CLI Refactoring (Thin wrappers)
1. Refactor command handlers to use services
2. Add CLIOutputHandler
3. Add WebSocketOutputHandler (for future Web UI)

### Phase 4: Web UI Integration
1. Create FastAPI/WebSocket layer
2. Subscribe WebSocketHandler to EventBus
3. Add REST endpoints calling same services

---

## 8. Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Complete dependency map created showing all modules and their interactions | ✅ DONE | Sections 1.1, 1.2, 1.3 |
| List of logic to extract from cli.py, run.py into services layer documented | ✅ DONE | Sections 2.1, 2.2, 2.3, 2.4 |
| Event emission points identified for WebSocket broadcasting | ✅ DONE | Sections 3.1, 3.2, 3.3, 3.4 |
| CLI preservation strategy documented (keep commands as thin wrappers) | ✅ DONE | Section 4.1, 4.2, 4.3, 4.4 |
| No breaking changes identified for existing CLI commands | ✅ DONE | Sections 5.1, 5.2, 5.3, 6.1-6.4 |

---

## 9. Key Insights for Implementation

### 9.1 TimelineLogger is the Core Integration Point

The existing `TimelineLogger` in `timeline.py` is perfectly structured for WebSocket broadcasting:
- All state changes are logged via atomic JSONL writes
- Event types cover all necessary real-time updates (22 event types)
- Each event includes structured data (task_id, role, status, duration_ms)

**Integration Strategy**: Inject an optional `EventBus` into `TimelineLogger` constructor that broadcasts each event to WebSocket subscribers in parallel to file logging.

### 9.2 Minimal Changes Required for Dual-Interface

The architecture is already well-suited for dual-interface operation:
1. **Session layer** (`session.py`) - Pure state management, no I/O dependencies
2. **Signals layer** (`signals.py`) - Pure parsing functions
3. **Config layer** (`config.py`) - Clean data loading

Only two modules require significant refactoring:
1. **`run.py`** - Replace `_print()` calls with output handler abstraction
2. **`cli.py`** - Extract `generate_tasks_from_markdown()` and `_invoke_claude_structured()` to services

### 9.3 Recommended Implementation Order

1. Create EventBus in `services/events/` and integrate with TimelineLogger
2. Create OutputHandler protocol and implement CLIOutputHandler
3. Extract services from cli.py and run.py (maintaining facades)
4. Add FastAPI/WebSocket layer consuming EventBus

---

*Document completed as part of T-001 architecture audit*
*Last updated: 2026-01-27*
