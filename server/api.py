"""FastAPI REST API for Ralph Orchestrator.

This module provides the REST API endpoints for the Ralph web UI, enabling:
- Project discovery and management
- Task operations (list, run, stop)
- Configuration management (read, update, validate)
- Git operations (branches, PRs)
- Session logs and timeline access

All endpoints return JSON responses and use Pydantic models for validation.

Usage:
    from server.api import app
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# Import services
from ralph_orchestrator.services.project_service import ProjectService, ProjectMetadata
from ralph_orchestrator.services.config_service import (
    ConfigService,
    ConfigValidationError,
    ConfigSummary,
)
from ralph_orchestrator.services.git_service import GitService, GitError, BranchInfo, PRInfo
from ralph_orchestrator.services.session_service import SessionService, SessionSummary
from ralph_orchestrator.tasks.prd import load_prd, PRDData, Task

# Import WebSocket components
from .websocket import WebSocketManager, websocket_endpoint


# =============================================================================
# Pydantic models for request/response validation
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: Optional[str] = None


class ProjectResponse(BaseModel):
    """Response model for a project."""

    path: str
    name: str
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    git_remote: Optional[str] = None
    task_count: int = 0
    tasks_completed: int = 0
    tasks_pending: int = 0
    status: str = "idle"
    session_id: Optional[str] = None
    current_task: Optional[str] = None
    has_config: bool = False
    config_version: Optional[str] = None
    discovered_at: float = 0.0
    last_updated: float = 0.0

    @classmethod
    def from_metadata(cls, metadata: ProjectMetadata) -> "ProjectResponse":
        """Create from ProjectMetadata."""
        return cls(
            path=str(metadata.path),
            name=metadata.name,
            git_branch=metadata.git_branch,
            git_commit=metadata.git_commit,
            git_remote=metadata.git_remote,
            task_count=metadata.task_count,
            tasks_completed=metadata.tasks_completed,
            tasks_pending=metadata.tasks_pending,
            status=metadata.status,
            session_id=metadata.session_id,
            current_task=metadata.current_task,
            has_config=metadata.has_config,
            config_version=metadata.config_version,
            discovered_at=metadata.discovered_at,
            last_updated=metadata.last_updated,
        )


class ProjectListResponse(BaseModel):
    """Response for list of projects."""

    projects: List[ProjectResponse]
    total: int


class TaskResponse(BaseModel):
    """Response model for a task."""

    id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    priority: int
    passes: bool = False
    notes: str = ""
    requires_tests: bool = True

    @classmethod
    def from_task(cls, task: Task) -> "TaskResponse":
        """Create from Task."""
        return cls(
            id=task.id,
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            priority=task.priority,
            passes=task.passes,
            notes=task.notes,
            requires_tests=task.requires_tests,
        )


class TaskListResponse(BaseModel):
    """Response for list of tasks."""

    project: str
    description: str
    tasks: List[TaskResponse]
    total: int
    completed: int
    pending: int


class RunRequest(BaseModel):
    """Request to start task execution."""

    task_id: Optional[str] = Field(None, description="Specific task ID to run")
    from_task_id: Optional[str] = Field(None, description="Start from this task")
    max_iterations: int = Field(200, ge=1, le=1000, description="Maximum iterations per task")
    gate_type: str = Field("full", description="Gate type: build, full, or none")
    dry_run: bool = Field(False, description="Preview without executing")

    @field_validator("gate_type")
    @classmethod
    def validate_gate_type(cls, v: str) -> str:
        """Validate gate type."""
        valid_types = ["build", "full", "none"]
        if v not in valid_types:
            raise ValueError(f"gate_type must be one of: {', '.join(valid_types)}")
        return v


class RunResponse(BaseModel):
    """Response for run operation."""

    session_id: str
    status: str
    message: str
    tasks_pending: int = 0


class StopResponse(BaseModel):
    """Response for stop operation."""

    success: bool
    message: str


class ConfigResponse(BaseModel):
    """Response model for configuration."""

    config_path: str
    project_path: str
    version: str
    task_source_type: str
    task_source_path: str
    git_base_branch: str
    git_remote: str
    gates_build_count: int
    gates_full_count: int
    test_paths: List[str]
    has_backend: bool
    has_frontend: bool
    autopilot_enabled: bool
    raw_config: Dict[str, Any]

    @classmethod
    def from_summary(cls, summary: ConfigSummary, raw_config: Dict[str, Any]) -> "ConfigResponse":
        """Create from ConfigSummary."""
        return cls(
            config_path=str(summary.config_path),
            project_path=str(summary.project_path),
            version=summary.version,
            task_source_type=summary.task_source_type,
            task_source_path=summary.task_source_path,
            git_base_branch=summary.git_base_branch,
            git_remote=summary.git_remote,
            gates_build_count=summary.gates_build_count,
            gates_full_count=summary.gates_full_count,
            test_paths=summary.test_paths,
            has_backend=summary.has_backend,
            has_frontend=summary.has_frontend,
            autopilot_enabled=summary.autopilot_enabled,
            raw_config=raw_config,
        )


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""

    updates: Dict[str, Any] = Field(..., description="Configuration updates to apply")
    validate_config: bool = Field(True, description="Validate before saving")

    @field_validator("updates")
    @classmethod
    def validate_updates_structure(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the structure of incoming updates before merge.

        This validates that update keys are known config fields and values
        have appropriate types before the deep merge occurs.
        """
        # Known top-level config keys
        allowed_keys = {
            "version", "task_source", "git", "gates", "test_paths",
            "services", "limits", "autopilot", "agents", "ui", "pr"
        }

        # Check for unknown top-level keys
        unknown_keys = set(v.keys()) - allowed_keys
        if unknown_keys:
            raise ValueError(f"Unknown configuration keys: {', '.join(unknown_keys)}")

        # Validate specific field types
        if "version" in v and not isinstance(v["version"], str):
            raise ValueError("version must be a string")

        if "task_source" in v:
            ts = v["task_source"]
            if not isinstance(ts, dict):
                raise ValueError("task_source must be an object")
            if "type" in ts and ts["type"] not in ("prd_json", "cr_markdown"):
                raise ValueError("task_source.type must be 'prd_json' or 'cr_markdown'")

        if "git" in v:
            git = v["git"]
            if not isinstance(git, dict):
                raise ValueError("git must be an object")

        if "gates" in v:
            gates = v["gates"]
            if not isinstance(gates, dict):
                raise ValueError("gates must be an object")
            for gate_type in ("build", "full"):
                if gate_type in gates:
                    if not isinstance(gates[gate_type], list):
                        raise ValueError(f"gates.{gate_type} must be an array")
                    for i, gate in enumerate(gates[gate_type]):
                        if not isinstance(gate, dict):
                            raise ValueError(f"gates.{gate_type}[{i}] must be an object")
                        if "name" in gate and not isinstance(gate["name"], str):
                            raise ValueError(f"gates.{gate_type}[{i}].name must be a string")
                        if "cmd" in gate and not isinstance(gate["cmd"], str):
                            raise ValueError(f"gates.{gate_type}[{i}].cmd must be a string")

        if "test_paths" in v:
            if not isinstance(v["test_paths"], list):
                raise ValueError("test_paths must be an array")
            for i, path in enumerate(v["test_paths"]):
                if not isinstance(path, str):
                    raise ValueError(f"test_paths[{i}] must be a string")

        if "limits" in v:
            limits = v["limits"]
            if not isinstance(limits, dict):
                raise ValueError("limits must be an object")
            int_fields = ["claude_timeout", "max_iterations", "post_verify_iterations",
                          "ui_fix_iterations", "robot_fix_iterations"]
            for field in int_fields:
                if field in limits and not isinstance(limits[field], int):
                    raise ValueError(f"limits.{field} must be an integer")

        if "autopilot" in v:
            autopilot = v["autopilot"]
            if not isinstance(autopilot, dict):
                raise ValueError("autopilot must be an object")
            if "enabled" in autopilot and not isinstance(autopilot["enabled"], bool):
                raise ValueError("autopilot.enabled must be a boolean")
            if "create_pr" in autopilot and not isinstance(autopilot["create_pr"], bool):
                raise ValueError("autopilot.create_pr must be a boolean")

        if "agents" in v:
            agents = v["agents"]
            if not isinstance(agents, dict):
                raise ValueError("agents must be an object")
            allowed_agent_types = {"implementation", "test_writing", "review", "fix", "planning"}
            for agent_type, agent_config in agents.items():
                if agent_type not in allowed_agent_types:
                    raise ValueError(f"Unknown agent type: {agent_type}")
                if not isinstance(agent_config, dict):
                    raise ValueError(f"agents.{agent_type} must be an object")

        return v


class ConfigUpdateResponse(BaseModel):
    """Response for config update operation."""

    success: bool
    message: str
    version: str
    changes: Dict[str, Any]


class BranchResponse(BaseModel):
    """Response model for a git branch."""

    name: str
    is_current: bool = False
    is_remote: bool = False
    tracking: Optional[str] = None
    commit_hash: Optional[str] = None
    commit_message: Optional[str] = None
    ahead: int = 0
    behind: int = 0

    @classmethod
    def from_branch_info(cls, info: BranchInfo) -> "BranchResponse":
        """Create from BranchInfo."""
        return cls(
            name=info.name,
            is_current=info.is_current,
            is_remote=info.is_remote,
            tracking=info.tracking,
            commit_hash=info.commit_hash,
            commit_message=info.commit_message,
            ahead=info.ahead,
            behind=info.behind,
        )


class BranchListResponse(BaseModel):
    """Response for list of branches."""

    branches: List[BranchResponse]
    current_branch: str
    total: int


class CreateBranchRequest(BaseModel):
    """Request to create a new branch."""

    branch_name: str = Field(..., min_length=1, description="Name for the new branch")
    base_branch: Optional[str] = Field(None, description="Base branch to create from")
    switch: bool = Field(True, description="Switch to new branch after creation")


class CreateBranchResponse(BaseModel):
    """Response for branch creation."""

    success: bool
    branch_name: str
    base_branch: str
    commit_hash: Optional[str] = None


class CreatePRRequest(BaseModel):
    """Request to create a pull request."""

    title: str = Field(..., min_length=1, description="PR title")
    body: str = Field("", description="PR body/description")
    base_branch: Optional[str] = Field(None, description="Target branch")
    draft: bool = Field(False, description="Create as draft PR")
    labels: Optional[List[str]] = Field(None, description="Labels to add")


class CreatePRResponse(BaseModel):
    """Response for PR creation."""

    success: bool
    pr_number: int
    pr_url: str
    title: str
    base_branch: str
    head_branch: str


class LogFileResponse(BaseModel):
    """Response model for a log file."""

    name: str
    path: str
    size: int
    modified_at: str
    content: Optional[str] = None


class LogListResponse(BaseModel):
    """Response for list of log files."""

    logs: List[LogFileResponse]
    total: int


class TimelineEvent(BaseModel):
    """A single timeline event."""

    timestamp: str
    event_type: str
    data: Dict[str, Any]


class TimelineResponse(BaseModel):
    """Response for timeline events."""

    events: List[TimelineEvent]
    total: int
    session_id: Optional[str] = None


# =============================================================================
# Service instances (initialized at startup)
# =============================================================================


# Services are initialized globally but can be overridden for testing
_project_service: Optional[ProjectService] = None
_config_service: Optional[ConfigService] = None
_git_service: Optional[GitService] = None
_session_service: Optional[SessionService] = None

# Store for active run tasks (project_path -> asyncio.Task)
_active_runs: Dict[str, asyncio.Task] = {}

# WebSocket manager for real-time updates
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the WebSocket manager."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


def get_project_service() -> ProjectService:
    """Get or create the project service."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService(search_paths=[Path.cwd()])
    return _project_service


def get_config_service() -> ConfigService:
    """Get or create the config service."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


def get_git_service() -> GitService:
    """Get or create the git service."""
    global _git_service
    if _git_service is None:
        _git_service = GitService()
    return _git_service


def get_session_service() -> SessionService:
    """Get or create the session service."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


def get_project_path(project_id: str) -> Path:
    """Resolve project_id to a Path.

    project_id can be:
    - An absolute path
    - A relative path
    - A project name (looked up in discovered projects)
    """
    # Try as absolute path first
    if project_id.startswith("/"):
        return Path(project_id)

    # Try as relative path
    path = Path(project_id)
    if path.exists() and (path / ".ralph").exists():
        return path.resolve()

    # Look up in discovered projects
    project_service = get_project_service()
    for project in project_service.list_projects():
        if project.name == project_id:
            return project.path

    # Default: treat as relative path from cwd
    return Path.cwd() / project_id


# =============================================================================
# Application lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup: discover projects
    project_service = get_project_service()
    project_service.discover_projects()

    yield

    # Shutdown: stop any active runs
    for project_path, task in _active_runs.items():
        if not task.done():
            task.cancel()
    _active_runs.clear()


# =============================================================================
# FastAPI application
# =============================================================================


app = FastAPI(
    title="Ralph Orchestrator API",
    description="REST API for Ralph verified task orchestration",
    version="0.1.0",
    lifespan=lifespan,
)


# Configure CORS for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Project endpoints
# =============================================================================


@app.get("/api/projects", response_model=ProjectListResponse)
async def list_projects(
    refresh: bool = Query(False, description="Force refresh project scan"),
) -> ProjectListResponse:
    """List all discovered Ralph projects.

    Scans configured search paths for directories containing .ralph/ subdirectory.
    Returns project metadata including task counts, git info, and session status.
    """
    project_service = get_project_service()

    if refresh:
        projects = project_service.discover_projects(refresh=True)
    else:
        projects = project_service.list_projects()
        if not projects:
            projects = project_service.discover_projects()

    return ProjectListResponse(
        projects=[ProjectResponse.from_metadata(p) for p in projects],
        total=len(projects),
    )


@app.get("/api/projects/{project_id:path}/tasks", response_model=TaskListResponse)
async def get_tasks(project_id: str) -> TaskListResponse:
    """Get tasks from project's prd.json.

    Args:
        project_id: Project path or name.

    Returns:
        List of tasks with metadata.
    """
    project_path = get_project_path(project_id)
    prd_path = project_path / ".ralph" / "prd.json"

    if not prd_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"PRD file not found: {prd_path}",
        )

    try:
        prd = load_prd(prd_path)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load PRD: {e}",
        )

    tasks = [TaskResponse.from_task(t) for t in prd.tasks]
    completed = sum(1 for t in prd.tasks if t.passes)
    pending = len(prd.tasks) - completed

    return TaskListResponse(
        project=prd.project,
        description=prd.description,
        tasks=tasks,
        total=len(tasks),
        completed=completed,
        pending=pending,
    )


@app.post("/api/projects/{project_id:path}/run", response_model=RunResponse)
async def run_project(
    project_id: str,
    request: RunRequest,
    background_tasks: BackgroundTasks,
) -> RunResponse:
    """Start task execution for a project.

    This endpoint starts the verified task loop in the background.
    Use the /stop endpoint to cancel execution.

    Args:
        project_id: Project path or name.
        request: Run configuration.

    Returns:
        Session info and status.
    """
    project_path = get_project_path(project_id)
    path_key = str(project_path.resolve())

    # Check if already running
    if path_key in _active_runs and not _active_runs[path_key].done():
        raise HTTPException(
            status_code=409,
            detail="Task execution already in progress for this project",
        )

    # Validate project exists
    if not (project_path / ".ralph").exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project not found or not initialized: {project_id}",
        )

    # Load PRD to get task info
    prd_path = project_path / ".ralph" / "prd.json"
    if not prd_path.exists():
        raise HTTPException(
            status_code=404,
            detail="PRD file not found. Run 'ralph init' first.",
        )

    try:
        prd = load_prd(prd_path)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid PRD file: {e}",
        )

    # Count pending tasks
    pending_tasks = [t for t in prd.tasks if not t.passes]
    if request.task_id:
        pending_tasks = [t for t in pending_tasks if t.id == request.task_id]
    elif request.from_task_id:
        found = False
        filtered = []
        for t in pending_tasks:
            if t.id == request.from_task_id:
                found = True
            if found:
                filtered.append(t)
        pending_tasks = filtered

    if not pending_tasks and not request.dry_run:
        return RunResponse(
            session_id="",
            status="completed",
            message="No pending tasks to execute",
            tasks_pending=0,
        )

    # For dry run, just return what would be executed
    if request.dry_run:
        return RunResponse(
            session_id="dry-run",
            status="dry_run",
            message=f"Would execute {len(pending_tasks)} task(s)",
            tasks_pending=len(pending_tasks),
        )

    # Generate session ID
    from ralph_orchestrator.session import generate_session_id

    session_id = generate_session_id()

    # Start background execution
    async def run_tasks():
        """Background task to run the orchestration."""
        import subprocess
        import sys

        cmd = [
            sys.executable,
            "-m",
            "ralph_orchestrator.cli",
            "run",
            "--prd-json",
            str(prd_path),
            "--max-iterations",
            str(request.max_iterations),
            "--gate-type",
            request.gate_type,
        ]

        if request.task_id:
            cmd.extend(["--task", request.task_id])
        elif request.from_task_id:
            cmd.extend(["--from-task", request.from_task_id])

        try:
            subprocess.run(
                cmd,
                cwd=project_path,
                check=True,
            )
        except subprocess.CalledProcessError:
            pass  # Error is logged in the session
        except asyncio.CancelledError:
            pass  # Cancelled by stop endpoint
        finally:
            # Clean up from active runs
            if path_key in _active_runs:
                del _active_runs[path_key]

    # Store the task
    task = asyncio.create_task(run_tasks())
    _active_runs[path_key] = task

    return RunResponse(
        session_id=session_id,
        status="started",
        message=f"Started execution of {len(pending_tasks)} task(s)",
        tasks_pending=len(pending_tasks),
    )


@app.post("/api/projects/{project_id:path}/stop", response_model=StopResponse)
async def stop_project(project_id: str) -> StopResponse:
    """Stop task execution for a project.

    Cancels any running orchestration for this project.

    Args:
        project_id: Project path or name.

    Returns:
        Stop operation result.
    """
    project_path = get_project_path(project_id)
    path_key = str(project_path.resolve())

    if path_key not in _active_runs:
        return StopResponse(
            success=False,
            message="No active execution for this project",
        )

    task = _active_runs[path_key]
    if task.done():
        del _active_runs[path_key]
        return StopResponse(
            success=False,
            message="Execution already completed",
        )

    task.cancel()
    del _active_runs[path_key]

    return StopResponse(
        success=True,
        message="Execution cancelled",
    )


# =============================================================================
# Configuration endpoints
# =============================================================================


@app.get("/api/projects/{project_id:path}/config", response_model=ConfigResponse)
async def get_config(project_id: str) -> ConfigResponse:
    """Get ralph.yml configuration for a project.

    Args:
        project_id: Project path or name.

    Returns:
        Configuration summary and raw config data.
    """
    project_path = get_project_path(project_id)
    config_service = get_config_service()

    try:
        summary = config_service.get_config_summary(project_path)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration not found for project: {project_id}",
            )

        raw_config = config_service.get_raw_config(project_path) or {}

        return ConfigResponse.from_summary(summary, raw_config)

    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration: {'; '.join(e.errors[:3])}",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration not found for project: {project_id}",
        )


@app.put("/api/projects/{project_id:path}/config", response_model=ConfigUpdateResponse)
async def update_config(
    project_id: str,
    request: ConfigUpdateRequest,
) -> ConfigUpdateResponse:
    """Update ralph.yml configuration for a project.

    Updates are merged with existing configuration.

    Args:
        project_id: Project path or name.
        request: Configuration updates.

    Returns:
        Update result with applied changes.
    """
    project_path = get_project_path(project_id)
    config_service = get_config_service()

    try:
        # Validate updates first if requested
        if request.validate_config:
            current_config = config_service.get_raw_config(project_path)
            if current_config is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Configuration not found for project: {project_id}",
                )

            # Deep merge for validation
            merged = _deep_merge(current_config.copy(), request.updates)
            valid, errors = config_service.validate_config_data(merged)
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Validation failed: {'; '.join(errors[:3])}",
                )

        # Apply updates
        new_config = config_service.update_config(
            project_path,
            request.updates,
            validate=request.validate_config,
        )

        return ConfigUpdateResponse(
            success=True,
            message="Configuration updated successfully",
            version=new_config.version,
            changes=request.updates,
        )

    except ConfigValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {'; '.join(e.errors[:3])}",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration not found for project: {project_id}",
        )


# =============================================================================
# Git endpoints
# =============================================================================


@app.get("/api/projects/{project_id:path}/branches", response_model=BranchListResponse)
async def list_branches(
    project_id: str,
    include_remote: bool = Query(False, description="Include remote branches"),
) -> BranchListResponse:
    """List git branches for a project.

    Args:
        project_id: Project path or name.
        include_remote: Whether to include remote branches.

    Returns:
        List of branches with status.
    """
    project_path = get_project_path(project_id)
    git_service = get_git_service()

    try:
        branches = git_service.list_branches(project_path, include_remote=include_remote)
        current_branch = git_service.get_current_branch(project_path)

        return BranchListResponse(
            branches=[BranchResponse.from_branch_info(b) for b in branches],
            current_branch=current_branch,
            total=len(branches),
        )

    except GitError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Git error: {e}",
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Git error: Project path not found - {e}",
        )


@app.post("/api/projects/{project_id:path}/branches", response_model=CreateBranchResponse)
async def create_branch(
    project_id: str,
    request: CreateBranchRequest,
) -> CreateBranchResponse:
    """Create a new git branch.

    Args:
        project_id: Project path or name.
        request: Branch creation parameters.

    Returns:
        Created branch info.
    """
    project_path = get_project_path(project_id)
    git_service = get_git_service()

    try:
        current_branch = git_service.get_current_branch(project_path)
        base_branch = request.base_branch or current_branch

        branch_info = git_service.create_branch(
            project_path,
            request.branch_name,
            base_branch=request.base_branch,
            switch=request.switch,
        )

        return CreateBranchResponse(
            success=True,
            branch_name=branch_info.name,
            base_branch=base_branch,
            commit_hash=branch_info.commit_hash,
        )

    except GitError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Git error: {e}",
        )


@app.post("/api/projects/{project_id:path}/pr", response_model=CreatePRResponse)
async def create_pr(
    project_id: str,
    request: CreatePRRequest,
) -> CreatePRResponse:
    """Create a pull request.

    Uses gh CLI for GitHub or glab CLI for GitLab.

    Args:
        project_id: Project path or name.
        request: PR creation parameters.

    Returns:
        Created PR info.
    """
    project_path = get_project_path(project_id)
    git_service = get_git_service()

    try:
        pr_info = git_service.create_pr(
            project_path,
            title=request.title,
            body=request.body,
            base_branch=request.base_branch,
            draft=request.draft,
            labels=request.labels,
        )

        return CreatePRResponse(
            success=True,
            pr_number=pr_info.number,
            pr_url=pr_info.url,
            title=pr_info.title,
            base_branch=pr_info.base_branch,
            head_branch=pr_info.head_branch,
        )

    except GitError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Git error: {e}",
        )


# =============================================================================
# Logs endpoints
# =============================================================================


@app.get("/api/projects/{project_id:path}/logs", response_model=LogListResponse)
async def list_logs(
    project_id: str,
    include_content: bool = Query(False, description="Include file content"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum files to return"),
) -> LogListResponse:
    """List log files for a project.

    Args:
        project_id: Project path or name.
        include_content: Whether to include file content.
        limit: Maximum number of files to return.

    Returns:
        List of log files.
    """
    project_path = get_project_path(project_id)
    logs_dir = project_path / ".ralph-session" / "logs"

    if not logs_dir.exists():
        return LogListResponse(logs=[], total=0)

    logs = []
    for log_file in sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        stat = log_file.stat()
        content = None
        if include_content:
            try:
                content = log_file.read_text(encoding="utf-8")
            except Exception:
                content = "[Error reading file]"

        logs.append(LogFileResponse(
            name=log_file.name,
            path=str(log_file),
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            content=content,
        ))

    return LogListResponse(logs=logs, total=len(logs))


@app.get("/api/projects/{project_id:path}/logs/{log_name}")
async def get_log(
    project_id: str,
    log_name: str,
) -> LogFileResponse:
    """Get a specific log file.

    Args:
        project_id: Project path or name.
        log_name: Name of the log file.

    Returns:
        Log file with content.
    """
    project_path = get_project_path(project_id)
    log_path = project_path / ".ralph-session" / "logs" / log_name

    if not log_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file not found: {log_name}",
        )

    try:
        stat = log_path.stat()
        content = log_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading log file: {e}",
        )

    return LogFileResponse(
        name=log_path.name,
        path=str(log_path),
        size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        content=content,
    )


# =============================================================================
# Timeline endpoints
# =============================================================================


@app.get("/api/projects/{project_id:path}/timeline", response_model=TimelineResponse)
async def get_timeline(
    project_id: str,
    limit: int = Query(100, ge=1, le=10000, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
) -> TimelineResponse:
    """Get timeline.jsonl events for a project.

    Args:
        project_id: Project path or name.
        limit: Maximum number of events to return.
        offset: Number of events to skip from the start.

    Returns:
        List of timeline events.
    """
    project_path = get_project_path(project_id)
    timeline_path = project_path / ".ralph-session" / "logs" / "timeline.jsonl"

    if not timeline_path.exists():
        return TimelineResponse(events=[], total=0, session_id=None)

    # Get session ID from session.json
    session_id = None
    session_path = project_path / ".ralph-session" / "session.json"
    if session_path.exists():
        try:
            session_data = json.loads(session_path.read_text(encoding="utf-8"))
            session_id = session_data.get("session_id")
        except Exception:
            pass

    events: List[TimelineEvent] = []
    total = 0

    try:
        with open(timeline_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                total += 1
                if i < offset:
                    continue
                if len(events) >= limit:
                    continue  # Keep counting total

                try:
                    data = json.loads(line)
                    events.append(TimelineEvent(
                        timestamp=data.get("timestamp", ""),
                        event_type=data.get("event_type", data.get("type", "unknown")),
                        data=data,
                    ))
                except json.JSONDecodeError:
                    continue

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading timeline: {e}",
        )

    return TimelineResponse(
        events=events,
        total=total,
        session_id=session_id,
    )


# =============================================================================
# Single project endpoint (catch-all, must be AFTER specific routes)
# =============================================================================


@app.get("/api/projects/{project_id:path}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    """Get details for a specific project.

    Args:
        project_id: Project path or name.

    Returns:
        Project metadata including task counts, git info, and session status.
    """
    project_path = get_project_path(project_id)
    project_service = get_project_service()

    # Try to get from cache or refresh
    metadata = project_service.get_project(project_path)
    if metadata is None:
        metadata = project_service.refresh_project(project_path)

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project not found: {project_id}",
        )

    return ProjectResponse.from_metadata(metadata)


# =============================================================================
# Utility functions
# =============================================================================


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in updates.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# =============================================================================
# Health check
# =============================================================================


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint.

    Returns:
        Service status and version.
    """
    project_service = get_project_service()

    return {
        "status": "healthy",
        "version": "0.1.0",
        "projects_discovered": len(project_service.list_projects()),
        "active_runs": len(_active_runs),
    }


# =============================================================================
# WebSocket endpoint
# =============================================================================


@app.websocket("/ws/{project_id:path}")
async def ws_route(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time updates.

    Clients connect to receive real-time events for a specific project,
    including task progress, log streaming, and git events.

    Args:
        websocket: The WebSocket connection.
        project_id: The project ID to subscribe to.
    """
    manager = get_websocket_manager()
    await websocket_endpoint(websocket, project_id, manager)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "app",
    "ProjectResponse",
    "TaskResponse",
    "ConfigResponse",
    "BranchResponse",
    "TimelineEvent",
    "get_websocket_manager",
]
