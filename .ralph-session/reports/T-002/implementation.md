# T-002 Implementation Report

## Implementation - 2026-01-27T13:15:00Z

### What was done

Created the `ralph_orchestrator/services/` package with a CLI-agnostic `OrchestrationService` that extracts core task execution logic from `run.py`. The service emits events at key execution points, enabling both CLI and web UI interfaces to monitor orchestration progress.

### Files created

1. **ralph_orchestrator/services/__init__.py**
   - Package initialization with all public exports
   - Exports: `OrchestrationService`, event types, and event classes

2. **ralph_orchestrator/services/orchestration_service.py**
   - `OrchestrationService` class: CLI-agnostic orchestration service
   - Event types enum: `EventType` with values for all orchestration events
   - Event dataclasses:
     - `TaskStartedEvent`: Emitted when a task begins
     - `TaskCompletedEvent`: Emitted when a task finishes (success/failure)
     - `AgentPhaseChangedEvent`: Emitted on agent phase transitions
     - `GateRunningEvent`: Emitted when a gate starts
     - `GateCompletedEvent`: Emitted when a gate finishes
     - `SignalDetectedEvent`: Emitted when a completion signal is detected
     - `IterationStartedEvent`: Emitted at start of each iteration
     - `SessionStartedEvent`: Emitted when session begins
     - `SessionEndedEvent`: Emitted when session ends
   - `OrchestrationOptions` and `OrchestrationResult` dataclasses
   - Event handler registration: `on_event()`, `on_all_events()`, `remove_handler()`
   - Full task execution loop with event emission at all key points

### Files modified

1. **ralph_orchestrator/run.py**
   - Updated `RunEngine` to delegate to `OrchestrationService`
   - Added CLI-specific event handlers for terminal output
   - `RunOptions.to_orchestration_options()` method for conversion
   - `RunResult.from_orchestration_result()` class method for conversion
   - Re-exports from services package for backward compatibility
   - Exposed `service` property and event registration methods

### Architecture

The new architecture follows a layered approach:

```
┌─────────────────────────────────────┐
│           CLI (cli.py)              │
│    User-facing argument parsing     │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│         RunEngine (run.py)          │
│   CLI-specific output (printing)    │
│   Registers CLI event handlers      │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│   OrchestrationService (services/)  │
│   CLI-agnostic task execution       │
│   Emits events at key points        │
│   No Click/CLI dependencies         │
└─────────────────────────────────────┘
```

### Event hooks implemented

| Event Type | Description | Payload |
|------------|-------------|---------|
| `task_started` | Task begins execution | task_id, task_title |
| `task_completed` | Task finishes | task_id, success, iterations, duration_ms, failure_reason |
| `agent_phase_changed` | Agent phase transition | task_id, phase, previous_phase |
| `gate_running` | Quality gate starts | task_id, gate_name, gate_type |
| `gate_completed` | Quality gate finishes | task_id, gate_name, passed, duration_ms, output |
| `signal_detected` | Completion signal detected | task_id, signal_type, valid, token_valid, agent_role, content |
| `iteration_started` | New iteration begins | task_id, iteration, max_iterations |
| `session_started` | Session begins | session_id, task_count |
| `session_ended` | Session ends | session_id, status, tasks_completed, tasks_failed, duration_ms |

### Verification

- All 345 existing unit and integration tests pass
- CLI `ralph run --help` works correctly
- Imports work for both old (`run.py`) and new (`services/`) modules
- Backward compatibility maintained through re-exports

### Usage example (programmatic access)

```python
from ralph_orchestrator.services import (
    OrchestrationService,
    EventType,
    TaskStartedEvent,
)

# Create service (after setting up dependencies)
service = OrchestrationService(
    config=config,
    prd=prd,
    session=session,
    timeline=timeline,
    execution_logger=exec_logger,
    claude_runner=claude_runner,
    gate_runner=gate_runner,
    guardrail=guardrail,
    options=options,
)

# Register event handlers
def on_task_started(event: TaskStartedEvent):
    print(f"Task {event.task_id} started: {event.task_title}")

service.on_event(EventType.TASK_STARTED, on_task_started)

# Run orchestration
result = service.run()
```

### Notes for next iteration

- The web UI can now subscribe to events via websockets by wrapping event handlers
- Consider adding async event emission for non-blocking UI updates
- Post-verification result details not yet included in session_ended event

## Implementation - 2026-01-27T13:20:00Z

### What was done

Fixed dataclass inheritance issue with event classes. The `event_type` field in the base `OrchestrationEvent` class was declared without a default value, but child classes had fields with default values, which is invalid in Python dataclass inheritance.

### Fix applied

Changed all event subclasses to use `field(init=False, default=...)` for `event_type`, which:
1. Removes `event_type` from constructor parameters (no longer needs to be passed)
2. Automatically sets the correct event type as a default value
3. Avoids the dataclass field ordering issue

### Files modified

1. **ralph_orchestrator/services/orchestration_service.py**
   - `TaskStartedEvent`: Changed to `event_type: EventType = field(init=False, default=EventType.TASK_STARTED)`
   - `TaskCompletedEvent`: Same pattern
   - `AgentPhaseChangedEvent`: Same pattern
   - `GateRunningEvent`: Same pattern
   - `GateCompletedEvent`: Same pattern
   - `SignalDetectedEvent`: Same pattern
   - `IterationStartedEvent`: Same pattern
   - `SessionStartedEvent`: Same pattern
   - `SessionEndedEvent`: Same pattern
   - Removed all `__post_init__` methods that were setting `event_type`

2. **tests/unit/test_orchestration_service.py**
   - Updated all event creation calls to not pass `event_type` as argument
   - Removed 13 instances of `event_type=EventType.*` from test code

3. **tests/unit/test_orchestration_events.py**
   - Updated 3 event creation calls to not pass `event_type` as argument

### Verification

- All 442 tests pass
- `pytest` completes successfully with no failures

## Implementation - 2026-01-27T13:30:00Z

### What was done

Fixed mypy errors from the previous iteration:

1. **Import naming conflict**: The new `services/` package was shadowing the existing `services.py` module containing `ServiceManager`, `create_service_manager`, `ServiceResult`, and `format_service_status`.

2. **Event handler type compatibility**: The `on_event()` method signature expected `Callable[[OrchestrationEvent], None]` but handlers were being passed with specific event subtypes like `Callable[[TaskStartedEvent], None]`.

### Files modified

1. **ralph_orchestrator/services.py** → **ralph_orchestrator/service_lifecycle.py**
   - Renamed file to avoid naming conflict with `services/` package
   - No code changes, just the file rename

2. **ralph_orchestrator/verify.py**
   - Updated import from `.services` to `.service_lifecycle` for `ServiceManager`, `create_service_manager`, `ServiceResult`, `format_service_status`

3. **ralph_orchestrator/services/orchestration_service.py**
   - Changed `EventHandler` type alias from `Callable[[OrchestrationEvent], None]` to `Callable[[Any], None]`
   - This allows handlers with specific event subtypes to be registered without mypy errors

### Verification

- mypy: `Success: no issues found in 24 source files`
- Unit tests: 260 passed
- Integration tests: 191 passed
- Total: 451 tests pass
