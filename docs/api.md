# API Reference

This document provides the full REST API reference for Ralph Orchestrator's web interface.

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently, the API does not require authentication. It is designed for local development use.

## Response Format

All responses return JSON with consistent structure:

**Success Response:**
```json
{
    "data": { ... },
    "total": 10
}
```

**Error Response:**
```json
{
    "detail": "Error message",
    "error_code": "ERROR_CODE"
}
```

---

## Project Endpoints

### List Projects

Retrieve all discovered Ralph projects.

```http
GET /api/projects
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `refresh` | boolean | false | Force rescan of project directories |

**Response:** `200 OK`

```json
{
    "projects": [
        {
            "path": "/path/to/project",
            "name": "my-project",
            "git_branch": "main",
            "git_commit": "abc123",
            "git_remote": "git@github.com:user/repo.git",
            "task_count": 10,
            "tasks_completed": 3,
            "tasks_pending": 7,
            "status": "idle",
            "session_id": "ralph-20260127-abc123",
            "current_task": null,
            "has_config": true,
            "config_version": "1",
            "discovered_at": 1706372400.0,
            "last_updated": 1706372500.0
        }
    ],
    "total": 1
}
```

### Get Project

Retrieve a specific project by ID or path.

```http
GET /api/projects/{project_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | string | Project name or path |

**Response:** `200 OK`

```json
{
    "path": "/path/to/project",
    "name": "my-project",
    "git_branch": "main",
    ...
}
```

**Errors:**
- `404 Not Found` - Project not found

---

## Task Endpoints

### List Tasks

Get tasks from the project's prd.json.

```http
GET /api/projects/{project_id}/tasks
```

**Response:** `200 OK`

```json
{
    "project": "My Project",
    "description": "Project description",
    "tasks": [
        {
            "id": "T-001",
            "title": "Implement feature A",
            "description": "Add feature A to the system",
            "acceptance_criteria": [
                "Criterion 1",
                "Criterion 2"
            ],
            "priority": 1,
            "passes": false,
            "notes": "",
            "requires_tests": true
        }
    ],
    "total": 5,
    "completed": 2,
    "pending": 3
}
```

**Errors:**
- `400 Bad Request` - Failed to parse prd.json
- `404 Not Found` - Project or prd.json not found

### Start Task Execution

Start executing tasks in the verified loop.

```http
POST /api/projects/{project_id}/run
```

**Request Body:**

```json
{
    "task_id": "T-001",          // Optional: specific task to run
    "from_task_id": "T-003",     // Optional: start from this task
    "max_iterations": 200,       // Default: 200, Range: 1-1000
    "gate_type": "full",         // "build" | "full" | "none"
    "dry_run": false             // Preview without executing
}
```

**Response:** `200 OK`

```json
{
    "session_id": "ralph-20260127-abc123",
    "status": "started",
    "message": "Execution started",
    "tasks_pending": 3
}
```

**Response (dry_run=true):** `200 OK`

```json
{
    "session_id": "preview",
    "status": "dry_run",
    "message": "Dry run preview",
    "tasks_pending": 3
}
```

**Errors:**
- `409 Conflict` - Execution already in progress
- `422 Unprocessable Entity` - Invalid parameters

### Stop Execution

Cancel a running task execution.

```http
POST /api/projects/{project_id}/stop
```

**Response:** `200 OK`

```json
{
    "success": true,
    "message": "Execution cancelled"
}
```

**Errors:**
- `400 Bad Request` - No execution in progress

---

## Configuration Endpoints

### Get Configuration

Retrieve the project's ralph.yml configuration.

```http
GET /api/projects/{project_id}/config
```

**Response:** `200 OK`

```json
{
    "config_path": "/path/to/.ralph/ralph.yml",
    "project_path": "/path/to/project",
    "version": "1",
    "task_source_type": "prd_json",
    "task_source_path": ".ralph/prd.json",
    "git_base_branch": "main",
    "git_remote": "origin",
    "gates_build_count": 2,
    "gates_full_count": 2,
    "test_paths": ["tests/**", "**/*.test.*"],
    "has_backend": true,
    "has_frontend": false,
    "autopilot_enabled": false,
    "raw_config": {
        "version": "1",
        "task_source": { ... },
        ...
    }
}
```

**Errors:**
- `404 Not Found` - Configuration not found

### Update Configuration

Update the project's configuration with deep merge.

```http
PUT /api/projects/{project_id}/config
```

**Request Body:**

```json
{
    "updates": {
        "git": {
            "base_branch": "develop"
        },
        "gates": {
            "build": [
                {"name": "lint", "cmd": "ruff check ."},
                {"name": "format", "cmd": "black --check ."}
            ]
        }
    },
    "validate_config": true
}
```

**Response:** `200 OK`

```json
{
    "success": true,
    "message": "Configuration updated",
    "version": "1",
    "changes": {
        "git.base_branch": {
            "old": "main",
            "new": "develop"
        }
    }
}
```

**Errors:**
- `400 Bad Request` - Validation failed
- `422 Unprocessable Entity` - Invalid update structure

---

## Git Endpoints

### List Branches

Get all git branches for the project.

```http
GET /api/projects/{project_id}/branches
```

**Response:** `200 OK`

```json
{
    "branches": [
        {
            "name": "main",
            "is_current": true,
            "is_remote": false,
            "tracking": "origin/main",
            "commit_hash": "abc123def456",
            "commit_message": "Latest commit",
            "ahead": 0,
            "behind": 0
        },
        {
            "name": "feature/new-feature",
            "is_current": false,
            "is_remote": false,
            "tracking": "origin/feature/new-feature",
            "commit_hash": "def456abc789",
            "commit_message": "WIP",
            "ahead": 3,
            "behind": 0
        }
    ],
    "current_branch": "main",
    "total": 2
}
```

### Create Branch

Create a new git branch.

```http
POST /api/projects/{project_id}/branches
```

**Request Body:**

```json
{
    "branch_name": "feature/my-feature",
    "base_branch": "main",    // Optional, defaults to current
    "switch": true            // Switch to new branch after creation
}
```

**Response:** `200 OK`

```json
{
    "success": true,
    "branch_name": "feature/my-feature",
    "base_branch": "main",
    "commit_hash": "abc123"
}
```

**Errors:**
- `400 Bad Request` - Branch already exists
- `422 Unprocessable Entity` - Invalid branch name

### Create Pull Request

Create a pull request on GitHub/GitLab.

```http
POST /api/projects/{project_id}/pr
```

**Request Body:**

```json
{
    "title": "Ralph: T-001 - Implement feature",
    "body": "## Summary\n- Added feature\n- Added tests",
    "base_branch": "main",     // Optional, uses config default
    "draft": false,
    "labels": ["enhancement"]  // Optional
}
```

**Response:** `200 OK`

```json
{
    "success": true,
    "pr_number": 42,
    "pr_url": "https://github.com/user/repo/pull/42",
    "title": "Ralph: T-001 - Implement feature",
    "base_branch": "main",
    "head_branch": "feature/T-001-implement-feature"
}
```

**Errors:**
- `400 Bad Request` - No forge detected (GitHub/GitLab)
- `422 Unprocessable Entity` - Missing required fields

---

## Log Endpoints

### List Log Files

Get available log files from the session.

```http
GET /api/projects/{project_id}/logs
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Maximum files to return |
| `include_content` | boolean | false | Include file content |

**Response:** `200 OK`

```json
{
    "logs": [
        {
            "name": "task-T-001.log",
            "path": "/path/to/.ralph-session/logs/task-T-001.log",
            "size": 15234,
            "modified_at": "2026-01-27T12:30:00Z",
            "content": null
        },
        {
            "name": "gate-build.log",
            "path": "/path/to/.ralph-session/logs/gate-build.log",
            "size": 8192,
            "modified_at": "2026-01-27T12:31:00Z",
            "content": null
        }
    ],
    "total": 2
}
```

### Get Log File

Get a specific log file's content.

```http
GET /api/projects/{project_id}/logs/{log_name}
```

**Response:** `200 OK`

```json
{
    "name": "task-T-001.log",
    "path": "/path/to/.ralph-session/logs/task-T-001.log",
    "size": 15234,
    "modified_at": "2026-01-27T12:30:00Z",
    "content": "Starting task T-001...\n[Implementation Agent]\n..."
}
```

**Errors:**
- `404 Not Found` - Log file not found

---

## Timeline Endpoint

### Get Timeline Events

Get chronological events from the session timeline.

```http
GET /api/projects/{project_id}/timeline
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Maximum events to return |
| `offset` | integer | 0 | Skip N events |

**Response:** `200 OK`

```json
{
    "events": [
        {
            "timestamp": "2026-01-27T12:00:00Z",
            "event_type": "session_started",
            "data": {
                "session_id": "ralph-20260127-abc123"
            }
        },
        {
            "timestamp": "2026-01-27T12:01:00Z",
            "event_type": "task_started",
            "data": {
                "task_id": "T-001",
                "task_title": "Implement feature"
            }
        },
        {
            "timestamp": "2026-01-27T12:05:00Z",
            "event_type": "gate_completed",
            "data": {
                "gate_name": "lint",
                "passed": true
            }
        }
    ],
    "total": 25,
    "session_id": "ralph-20260127-abc123"
}
```

---

## Health Check

### Get Health Status

Check API health and get basic statistics.

```http
GET /api/health
```

**Response:** `200 OK`

```json
{
    "status": "healthy",
    "version": "0.1.0",
    "projects_discovered": 3,
    "active_runs": 1
}
```

---

## WebSocket API

### Connect to Project

Establish a WebSocket connection for real-time updates.

```
ws://localhost:8000/ws/{project_id}
```

**Connection Message (Server → Client):**

```json
{
    "type": "connected",
    "connection_id": "uuid-string",
    "project_id": "my-project"
}
```

### Client Commands

Send commands from client to server:

**Ping:**
```json
{
    "command": "ping",
    "payload": {}
}
```

**Subscribe to Event Types:**
```json
{
    "command": "subscribe",
    "payload": {
        "event_types": ["task_started", "task_completed"]
    }
}
```

**Unsubscribe:**
```json
{
    "command": "unsubscribe",
    "payload": {
        "event_types": ["task_started"]
    }
}
```

**Start Task:**
```json
{
    "command": "start_task",
    "payload": {
        "task_id": "T-001",
        "max_iterations": 200
    }
}
```

**Cancel Execution:**
```json
{
    "command": "cancel_execution",
    "payload": {}
}
```

### Server Messages

**Event Broadcast:**
```json
{
    "type": "event",
    "event_type": "task_started",
    "task_id": "T-001",
    "task_title": "Implement feature",
    "timestamp": 1706372400
}
```

**Command Response:**
```json
{
    "type": "command_response",
    "command": "ping",
    "success": true,
    "result": {
        "timestamp": 1706372400
    }
}
```

**Error:**
```json
{
    "type": "error",
    "error": "Unknown command: invalid"
}
```

### Event Types

Events broadcast via WebSocket:

| Event Type | Description |
|------------|-------------|
| `session_started` | Orchestration session began |
| `session_ended` | Orchestration session completed |
| `task_started` | Task execution started |
| `task_completed` | Task finished successfully |
| `task_failed` | Task failed |
| `agent_phase_changed` | Agent changed (impl → test → review) |
| `gate_running` | Quality gate started |
| `gate_completed` | Quality gate finished |
| `signal_detected` | Agent completion signal detected |
| `iteration_started` | New iteration within task |
| `agent_output` | Live output from agent |

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `PROJECT_NOT_FOUND` | 404 | Project does not exist |
| `CONFIG_NOT_FOUND` | 404 | Configuration file missing |
| `PRD_NOT_FOUND` | 404 | prd.json not found |
| `EXECUTION_IN_PROGRESS` | 409 | Cannot start, already running |
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `PARSE_ERROR` | 400 | Failed to parse file |
| `GIT_ERROR` | 400 | Git operation failed |
| `NO_FORGE` | 400 | No GitHub/GitLab detected |

---

## Rate Limiting

No rate limiting is currently implemented as the API is designed for local development.

## Pagination

Endpoints that return lists support pagination:

```http
GET /api/projects/{id}/timeline?limit=50&offset=100
```

- `limit` - Maximum items to return (default varies by endpoint)
- `offset` - Number of items to skip

Response includes `total` field for calculating page counts.
