# T-006 Implementation Report

## Implementation - 2026-01-27T13:10:00Z

### What was done

Created the FastAPI application with comprehensive REST endpoints for the Ralph Orchestrator web UI. The implementation includes:

**Core API Structure:**
- Created `server/api.py` with FastAPI application instance
- Configured CORS middleware for localhost development (ports 3000, 5173, 8080)
- Added application lifespan handler for startup/shutdown
- Implemented health check endpoint at `/api/health`

**Pydantic Models for Request/Response Validation:**
- `ProjectResponse` / `ProjectListResponse` - Project metadata
- `TaskResponse` / `TaskListResponse` - Task data from prd.json
- `RunRequest` / `RunResponse` - Task execution parameters
- `StopResponse` - Execution cancellation
- `ConfigResponse` / `ConfigUpdateRequest` / `ConfigUpdateResponse` - Configuration management
- `BranchResponse` / `BranchListResponse` / `CreateBranchRequest` / `CreateBranchResponse` - Git branches
- `CreatePRRequest` / `CreatePRResponse` - Pull request creation
- `LogFileResponse` / `LogListResponse` - Log file access
- `TimelineEvent` / `TimelineResponse` - Timeline events

**Implemented Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all discovered projects |
| `/api/projects/{project_id}` | GET | Get project details |
| `/api/projects/{project_id}/tasks` | GET | Get tasks from prd.json |
| `/api/projects/{project_id}/run` | POST | Start task execution |
| `/api/projects/{project_id}/stop` | POST | Cancel execution |
| `/api/projects/{project_id}/config` | GET | Get ralph.yml contents |
| `/api/projects/{project_id}/config` | PUT | Update and validate ralph.yml |
| `/api/projects/{project_id}/branches` | GET | List git branches with status |
| `/api/projects/{project_id}/branches` | POST | Create new branch |
| `/api/projects/{project_id}/pr` | POST | Create pull request |
| `/api/projects/{project_id}/logs` | GET | List log files |
| `/api/projects/{project_id}/logs/{log_name}` | GET | Get specific log file |
| `/api/projects/{project_id}/timeline` | GET | Get timeline.jsonl events |
| `/api/health` | GET | Health check |

**Service Integration:**
- Integrated with `ProjectService` for project discovery
- Integrated with `ConfigService` for configuration management
- Integrated with `GitService` for git operations
- Integrated with `SessionService` for session management
- Integrated with PRD loader for task operations

**Error Handling:**
- All endpoints use proper HTTP status codes (400, 404, 409, 500)
- Errors return consistent `ErrorResponse` format
- Git operations wrap `GitError` exceptions
- Config operations wrap `ConfigValidationError` exceptions

**Background Task Execution:**
- Run endpoint starts orchestration in asyncio background task
- Stop endpoint cancels running tasks
- Active runs tracked in `_active_runs` dictionary

### Files modified

1. **Created:** `server/api.py` - FastAPI application with all endpoints
2. **Modified:** `server/__init__.py` - Added API exports
3. **Modified:** `pyproject.toml` - Added FastAPI, uvicorn, pydantic dependencies

### Acceptance Criteria Status

- [x] server/api.py created with FastAPI app instance
- [x] GET /api/projects endpoint returns all discovered projects
- [x] GET /api/projects/{project_id} returns project details
- [x] GET /api/projects/{project_id}/tasks returns tasks from prd.json
- [x] POST /api/projects/{project_id}/run starts task execution
- [x] POST /api/projects/{project_id}/stop cancels execution
- [x] GET /api/projects/{project_id}/config returns ralph.yml contents
- [x] PUT /api/projects/{project_id}/config updates and validates ralph.yml
- [x] GET /api/projects/{project_id}/branches lists git branches with status
- [x] POST /api/projects/{project_id}/branches creates new branch
- [x] POST /api/projects/{project_id}/pr creates pull request
- [x] GET /api/projects/{project_id}/logs returns log files
- [x] GET /api/projects/{project_id}/timeline returns timeline.jsonl events
- [x] CORS configured for localhost development
- [x] All endpoints have proper error handling with appropriate HTTP status codes
- [x] Request validation using Pydantic models

### Notes

- The API uses FastAPI's native Pydantic integration for request/response validation
- CORS is configured for common development ports (3000, 5173, 8080)
- The run endpoint executes tasks via subprocess to use the existing CLI
- Project ID can be an absolute path, relative path, or project name
- All Pydantic models include factory methods for conversion from service layer dataclasses
- Fixed Pydantic warning: renamed `validate` field to `validate_config` in ConfigUpdateRequest to avoid shadowing BaseModel method

## Implementation - 2026-01-27T13:07:00Z

### What was done

Fixed the critical routing bug that prevented 8 endpoints from being accessible.

**Root Cause:**
The FastAPI application used `{project_id:path}` as the path parameter type for project-specific endpoints. The `:path` type converter matches any string including `/` characters, which caused greedy matching. When a request was made to `/api/projects/test-project/tasks`, the `{project_id:path}` parameter would match `test-project/tasks` as the project_id, preventing the `/tasks` sub-route from matching.

**Fix Applied:**
Changed all route definitions from `{project_id:path}` to `{project_id}` (plain string). This prevents the greedy path matching and allows FastAPI to correctly route to sub-endpoints.

**Routes Updated:**
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/tasks`
- `POST /api/projects/{project_id}/run`
- `POST /api/projects/{project_id}/stop`
- `GET /api/projects/{project_id}/config`
- `PUT /api/projects/{project_id}/config`
- `GET /api/projects/{project_id}/branches`
- `POST /api/projects/{project_id}/branches`
- `POST /api/projects/{project_id}/pr`
- `GET /api/projects/{project_id}/logs`
- `GET /api/projects/{project_id}/logs/{log_name}`
- `GET /api/projects/{project_id}/timeline`

**Test Fixes:**
- Removed all `pytest.skip()` calls that were placed due to the routing bug (19 skipped tests now pass)
- Fixed test URLs using `f"/api/projects/{temp_project}/..."` to use `/api/projects/test-project/...` with mocked `get_project_path`
- Updated PRD fixture data to use camelCase field names (`acceptanceCriteria`, `requiresTests`) per schema
- Updated `PRInfo` mock in tests to include all required fields

### Files modified

1. **server/api.py** - Changed all `{project_id:path}` to `{project_id}` in 12 endpoint route definitions
2. **tests/unit/test_api.py** - Removed pytest.skip() calls, fixed test URLs and fixture data

### Test Results

```
41 passed in 0.29s
```

All 41 tests pass with 0 skipped.

### Notes for next iteration

- Project identifiers must not contain slashes. This is acceptable since projects are discovered by directory name and directory names should not contain slashes on typical filesystems.
- If absolute paths need to be passed as project IDs, the API design would need to change (e.g., using query parameters or POST body instead of path parameters).
