# Architecture Guide

This document describes the architecture of Ralph Orchestrator's web UI system, including the service layer, event system, and API design.

## System Overview

Ralph Orchestrator operates as a dual-interface system:

1. **CLI Interface** - Original command-line interface for direct operation
2. **Web UI Interface** - Modern React-based dashboard with REST API backend

Both interfaces share the same core orchestration engine but provide different user experiences.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ralph Orchestrator                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐           ┌──────────────────────────────┐   │
│  │   CLI        │           │        Web UI                 │   │
│  │   (ralph)    │           │  ┌──────────┐  ┌───────────┐ │   │
│  └──────┬───────┘           │  │ Frontend │  │ FastAPI   │ │   │
│         │                   │  │ (React)  │←→│ Backend   │ │   │
│         │                   │  └──────────┘  └─────┬─────┘ │   │
│         │                   └──────────────────────┼───────┘   │
│         │                                          │            │
│  ┌──────┴──────────────────────────────────────────┴───────┐   │
│  │                    Service Layer                         │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │   │
│  │  │Orchestrat.│ │  Project  │ │  Session  │ │  Config │ │   │
│  │  │  Service  │ │  Service  │ │  Service  │ │ Service │ │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘ │   │
│  │  ┌───────────┐                                          │   │
│  │  │   Git     │                                          │   │
│  │  │  Service  │                                          │   │
│  │  └───────────┘                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Core Components                        │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐  │   │
│  │  │  Claude   │ │   Gates   │ │ Guardrails│ │ Signals │  │   │
│  │  │  Runner   │ │  Runner   │ │           │ │ Parser  │  │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Service Layer

The service layer provides a clean abstraction between the UI/API and the core orchestration logic. Each service follows an event-driven pattern with consistent interfaces.

### OrchestrationService

**Purpose:** Coordinates the verified task loop execution.

**Location:** `ralph_orchestrator/services/orchestration_service.py`

**Key Responsibilities:**
- Manage task execution lifecycle
- Coordinate agent phases (implementation, test, review, fix)
- Execute quality gates
- Emit events for real-time updates

**Event Types:**
```python
class EventType(Enum):
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    AGENT_PHASE_CHANGED = "agent_phase_changed"
    GATE_RUNNING = "gate_running"
    GATE_COMPLETED = "gate_completed"
    SIGNAL_DETECTED = "signal_detected"
    ITERATION_STARTED = "iteration_started"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
```

**Usage:**
```python
from ralph_orchestrator.services.orchestration_service import OrchestrationService

service = OrchestrationService(config, prd, session, ...)

# Subscribe to events
service.on_event(EventType.TASK_STARTED, lambda e: print(f"Task {e.task_id} started"))

# Run orchestration
result = await service.run()
```

### ProjectService

**Purpose:** Discovers and manages multiple Ralph projects.

**Location:** `ralph_orchestrator/services/project_service.py`

**Key Responsibilities:**
- Scan directories for `.ralph/` subdirectories
- Extract project metadata (tasks, git info, status)
- Cache project information
- Emit events for project changes

**Event Types:**
```python
class ProjectEventType(Enum):
    PROJECT_DISCOVERED = "project_discovered"
    PROJECT_REMOVED = "project_removed"
    PROJECT_UPDATED = "project_updated"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
```

**Usage:**
```python
from ralph_orchestrator.services.project_service import ProjectService

service = ProjectService(search_paths=[Path.cwd()], max_depth=3)

# Discover projects
projects = service.discover_projects()

# Get specific project
project = service.get_project("my-project")
```

### SessionService

**Purpose:** Manages session state with tamper detection.

**Location:** `ralph_orchestrator/services/session_service.py`

**Key Responsibilities:**
- Create and manage `.ralph-session/` directory
- Track task status with checksum verification
- Provide session summaries for API
- Emit events for session lifecycle

**Event Types:**
```python
class SessionEventType(Enum):
    SESSION_CREATED = "session_created"
    SESSION_LOADED = "session_loaded"
    SESSION_ENDED = "session_ended"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ITERATION_INCREMENTED = "iteration_incremented"
```

**Anti-Tampering:**
- `task-status.json` is protected by `task-status.sha256` checksum
- Changes without valid checksum updates are detected as tampering
- Session tokens must match for signal validation

### ConfigService

**Purpose:** Manages `ralph.yml` configuration with validation.

**Location:** `ralph_orchestrator/services/config_service.py`

**Key Responsibilities:**
- Load and parse YAML configuration
- Validate against JSON schema
- Deep merge configuration updates
- Emit events for configuration changes

**Event Types:**
```python
class ConfigEventType(Enum):
    CONFIG_LOADED = "config_loaded"
    CONFIG_UPDATED = "config_updated"
    CONFIG_CREATED = "config_created"
    CONFIG_VALIDATION_FAILED = "config_validation_failed"
```

### GitService

**Purpose:** Provides git operations and PR management.

**Location:** `ralph_orchestrator/services/git_service.py`

**Key Responsibilities:**
- Branch operations (list, create, switch, delete)
- Commit and push operations
- PR creation via `gh` or `glab` CLI
- Status tracking (ahead/behind, staged, unstaged)

**Event Types:**
```python
class GitEventType(Enum):
    BRANCH_CREATED = "branch_created"
    BRANCH_SWITCHED = "branch_switched"
    BRANCH_DELETED = "branch_deleted"
    PR_CREATED = "pr_created"
    COMMIT_CREATED = "commit_created"
    PUSH_COMPLETED = "push_completed"
    GIT_ERROR = "git_error"
```

## Event System

All services use a consistent event-driven architecture:

```python
class BaseEvent:
    event_type: EventType
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for WebSocket broadcasting."""
        pass

class EventEmitter:
    def on_event(self, event_type: EventType, handler: Callable):
        """Subscribe to specific event type."""
        pass

    def on_all_events(self, handler: Callable):
        """Subscribe to all events."""
        pass

    def emit(self, event: BaseEvent):
        """Emit event to all subscribers."""
        pass
```

**Benefits:**
- Decouples UI from business logic
- Enables real-time updates via WebSocket
- Supports multiple subscribers
- Events are serializable for logging

## API Layer

### FastAPI Backend

**Location:** `server/api.py`

The REST API provides CRUD operations for all resources:

```
GET    /api/projects                    List projects
GET    /api/projects/{id}               Get project details
GET    /api/projects/{id}/tasks         Get tasks
POST   /api/projects/{id}/run           Start execution
POST   /api/projects/{id}/stop          Stop execution
GET    /api/projects/{id}/config        Get configuration
PUT    /api/projects/{id}/config        Update configuration
GET    /api/projects/{id}/branches      List branches
POST   /api/projects/{id}/branches      Create branch
POST   /api/projects/{id}/pr            Create PR
GET    /api/projects/{id}/logs          List log files
GET    /api/projects/{id}/logs/{name}   Get log content
GET    /api/projects/{id}/timeline      Get timeline events
GET    /api/health                      Health check
```

### WebSocket Manager

**Location:** `server/websocket.py`

Provides real-time updates to connected clients:

```python
class WebSocketManager:
    async def connect(self, websocket: WebSocket, project_id: str):
        """Accept connection and track by project."""
        pass

    async def broadcast_to_project(self, project_id: str, data: dict):
        """Send update to all clients watching a project."""
        pass

    async def handle_message(self, connection: ConnectionInfo, data: dict):
        """Process client commands (ping, subscribe, start_task, etc.)."""
        pass
```

**Client Commands:**
```python
class ClientCommand(Enum):
    PING = "ping"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    START_TASK = "start_task"
    CANCEL_EXECUTION = "cancel_execution"
    CREATE_BRANCH = "create_branch"
```

**Message Protocol:**
```json
// Client -> Server
{
    "command": "start_task",
    "payload": {"task_id": "T-001"}
}

// Server -> Client
{
    "type": "event",
    "event_type": "task_started",
    "task_id": "T-001",
    "timestamp": 1706372400
}
```

## Frontend Architecture

### Technology Stack

- **Framework:** Next.js 16 (React 19)
- **UI Components:** shadcn/ui + Radix UI
- **Styling:** Tailwind CSS 4
- **State Management:** React hooks + Context
- **Testing:** Vitest + React Testing Library
- **E2E Testing:** Playwright

### Component Structure

```
frontend/src/
├── app/                    # Next.js pages
│   ├── page.tsx           # Dashboard
│   ├── projects/          # Project pages
│   ├── tasks/             # Task board
│   ├── workflow/          # Config editor
│   └── settings/          # Settings
├── components/
│   ├── ui/                # shadcn/ui primitives
│   ├── layout/            # App layout components
│   ├── projects/          # Project list/card
│   ├── tasks/             # Task board/card
│   ├── git/               # Git panel, PR modal
│   ├── logs/              # Log viewer
│   ├── timeline/          # Timeline view
│   └── workflow/          # Config editor
├── hooks/                  # Custom React hooks
│   ├── use-projects.ts
│   ├── use-tasks.ts
│   ├── use-websocket.ts
│   └── ...
└── services/
    └── api.ts             # API client
```

### Custom Hooks

```typescript
// Project data fetching with WebSocket updates
const { projects, loading, error, refresh } = useProjects();

// Task management
const { tasks, startTask, skipTask, updateStatus } = useTasks(projectId);

// WebSocket connection
const { connected, send, subscribe } = useWebSocket(projectId);

// Configuration management
const { config, updateConfig, validationErrors } = useConfig(projectId);

// Git operations
const { branches, createBranch, createPR, status } = useGit(projectId);
```

## Data Flow

### Task Execution Flow

```
1. User clicks "Start Task" in UI
   │
2. Frontend sends POST /api/projects/{id}/run
   │
3. API creates OrchestrationService
   │
4. OrchestrationService emits TASK_STARTED event
   │
5. Event broadcasted to WebSocket clients
   │
6. Frontend updates task card status
   │
7. Agent phases execute (implementation → test → review)
   │
8. Gate results emitted as events
   │
9. TASK_COMPLETED event when done
   │
10. Frontend moves task to "Done" column
```

### Configuration Update Flow

```
1. User edits config in UI
   │
2. Frontend sends PUT /api/projects/{id}/config
   │
3. API calls ConfigService.update_config()
   │
4. ConfigService validates against JSON schema
   │
5. Deep merge applied to existing config
   │
6. ralph.yml written to disk
   │
7. CONFIG_UPDATED event emitted
   │
8. Response returns updated config
   │
9. Frontend shows success toast
```

## Testing Strategy

### Unit Tests

- **Location:** `tests/unit/`, `tests/services/`
- **Coverage:** Service methods, event emission, data models
- **Tools:** pytest, pytest-asyncio

### Integration Tests

- **Location:** `tests/integration/`
- **Coverage:** API endpoints, WebSocket, CLI commands
- **Tools:** pytest, TestClient (FastAPI)

### Frontend Tests

- **Location:** `frontend/src/__tests__/`
- **Coverage:** Component rendering, interactions
- **Tools:** Vitest, React Testing Library

### E2E Tests

- **Location:** `frontend/e2e/`
- **Coverage:** Full user workflows
- **Tools:** Playwright

## Security Considerations

1. **Session Tokens** - All completion signals must include valid session token
2. **Checksum Verification** - Task status protected by SHA256 checksum
3. **Guardrails** - Test-writing agent restricted to test paths
4. **CORS** - API restricted to localhost origins
5. **No Credentials in Commits** - .env and credential files excluded

## Performance Considerations

1. **Project Caching** - ProjectService caches metadata to avoid repeated scans
2. **WebSocket Pooling** - Connections managed per project
3. **Log Pagination** - Large logs loaded with offset/limit
4. **Timeline Streaming** - Events streamed incrementally
5. **Virtual List** - Large lists use virtualization in UI
