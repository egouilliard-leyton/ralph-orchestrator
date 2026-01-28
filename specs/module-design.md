# Ralph Orchestrator: Module Design Specification

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Design Document

This document defines the module boundaries, responsibilities, and interfaces for the Ralph orchestrator Python implementation. The design preserves all anti-gaming mechanisms and verification loops from the original `ralph-verified.sh` implementation.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Dependency Graph](#2-module-dependency-graph)
3. [Module Specifications](#3-module-specifications)
   - [3.1 session](#31-session-module)
   - [3.2 tasks](#32-tasks-module)
   - [3.3 agents](#33-agents-module)
   - [3.4 exec](#34-exec-module)
   - [3.5 gates](#35-gates-module)
   - [3.6 services](#36-services-module)
   - [3.7 ui](#37-ui-module)
   - [3.8 reports](#38-reports-module)
   - [3.9 config](#39-config-module)
   - [3.10 cli](#310-cli-module)
   - [3.11 autopilot](#311-autopilot-module)
4. [Anti-Gaming Mechanisms](#4-anti-gaming-mechanisms)
5. [Verification Loops](#5-verification-loops)
6. [Data Flow Diagrams](#6-data-flow-diagrams)
7. [Interface Contracts](#7-interface-contracts)
8. [Testing Strategy](#8-testing-strategy)

---

## 1. Architecture Overview

### 1.1 Design Principles

1. **Script-controlled state**: Only the orchestrator modifies task status - agents signal completion but never write status
2. **Tokenized signals**: All agent completion signals must contain the valid session token
3. **Checksum verification**: Task status file integrity is verified before every read/write
4. **Role separation**: Clear boundaries between implementation, testing, review, and fix agents
5. **Guardrails**: Test-writing agent can only modify files matching allowed patterns
6. **Structured logging**: All events logged to timeline for audit and replay

### 1.2 Module Overview

```
ralph/
├── __init__.py
├── cli.py              # Command-line interface entry point
├── config.py           # Configuration loading and validation
├── session/            # Session lifecycle and security
│   ├── __init__.py
│   ├── manager.py      # Session creation/destruction
│   ├── token.py        # Token generation and validation
│   └── checksum.py     # Tamper detection
├── tasks/              # Task parsing and status
│   ├── __init__.py
│   ├── parser.py       # PRD JSON / CR markdown parsing
│   ├── status.py       # Task status tracking (script-only writes)
│   └── selector.py     # Next task selection
├── agents/             # Agent roles and prompts
│   ├── __init__.py
│   ├── roles.py        # Role definitions and tool constraints
│   ├── prompts.py      # Prompt template generation
│   ├── signals.py      # Completion signal validation
│   └── guardrails.py   # Path restrictions for test agent
├── exec/               # Command execution
│   ├── __init__.py
│   ├── runner.py       # Shell command execution with timeout
│   ├── capture.py      # Output capture and streaming
│   └── timeout.py      # Timeout handling
├── gates/              # Quality gates
│   ├── __init__.py
│   ├── runner.py       # Gate execution orchestration
│   ├── conditions.py   # When-condition evaluation
│   └── results.py      # Gate result aggregation
├── services/           # Service lifecycle
│   ├── __init__.py
│   ├── manager.py      # Service start/stop orchestration
│   ├── health.py       # Health check polling
│   └── cleanup.py      # Process cleanup and port release
├── ui/                 # UI verification
│   ├── __init__.py
│   ├── agent_browser.py    # Agent-browser test runner
│   ├── robot.py            # Robot Framework test runner
│   └── loops.py            # UI fix loops (plan → impl → retest)
├── reports/            # Logging and reporting
│   ├── __init__.py
│   ├── timeline.py     # JSONL event logging
│   ├── summary.py      # Run summary generation
│   └── artifacts.py    # Artifact management (screenshots, etc.)
├── autopilot/          # Autopilot mode (Compound-style)
│   ├── __init__.py
│   ├── analysis.py     # Report analysis
│   ├── prd_gen.py      # PRD generation
│   ├── tasks_gen.py    # Task list generation
│   └── pr.py           # PR creation
├── research/           # Research sub-agents for PRD enhancement
│   ├── __init__.py
│   ├── coordinator.py  # ResearchCoordinator orchestrates research
│   ├── backend.py      # BackendResearcher scans Python/API code
│   ├── frontend.py     # FrontendResearcher scans React/Vue/CSS
│   └── web.py          # WebResearcher uses web search
└── skills/             # Skill routing for specialized plugins
    ├── __init__.py
    ├── router.py       # SkillRouter detects skills for tasks
    └── defaults.py     # Default skill mappings
```

---

## 2. Module Dependency Graph

```
                                    ┌─────────┐
                                    │   cli   │
                                    └────┬────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
              ┌──────────┐        ┌──────────┐         ┌──────────┐
              │  config  │        │  session │         │ autopilot│
              └────┬─────┘        └────┬─────┘         └────┬─────┘
                   │                   │                    │
         ┌─────────┴─────────┐         │                    │
         │                   │         │                    │
         ▼                   ▼         ▼                    │
    ┌─────────┐         ┌─────────┐   │                    │
    │  gates  │         │ services│◄──┘                    │
    └────┬────┘         └────┬────┘                        │
         │                   │                             │
         │         ┌─────────┴─────────┐                   │
         │         │                   │                   │
         ▼         ▼                   ▼                   │
    ┌─────────┐ ┌─────────┐      ┌─────────┐              │
    │   ui    │ │  exec   │◄─────│ agents  │◄─────────────┘
    └────┬────┘ └────┬────┘      └────┬────┘
         │          │                 │
         │          │                 │
         ▼          ▼                 ▼
    ┌─────────┐ ┌─────────┐      ┌─────────┐
    │ reports │ │ reports │      │  tasks  │
    └─────────┘ └─────────┘      └─────────┘
```

### Dependency Rules

1. **No circular dependencies** - modules only depend on modules below them in the graph
2. **config is read-only** - loaded once, immutable during run
3. **session is write-controlled** - only session module writes session files
4. **tasks is orchestrator-controlled** - only main loop writes task status
5. **reports is append-only** - events and artifacts only added, never deleted

---

## 3. Module Specifications

### 3.1 session Module

**Purpose:** Manage session lifecycle, token generation, and tamper detection.

#### 3.1.1 Files

| File | Responsibility |
|------|----------------|
| `manager.py` | Session creation, persistence, cleanup |
| `token.py` | Cryptographic token generation and validation |
| `checksum.py` | SHA-256 checksum for tamper detection |

#### 3.1.2 Key Classes

```python
# session/manager.py
@dataclass
class Session:
    session_id: str           # Format: YYYYMMDD-HHMMSS-[hex]
    session_token: str        # Format: ralph-YYYYMMDD-HHMMSS-[hex]
    started_at: datetime
    task_source: Path
    task_source_type: Literal["prd_json", "cr_markdown"]
    config_path: Path
    git_branch: Optional[str]
    git_commit: Optional[str]
    status: Literal["running", "completed", "failed", "aborted"]
    current_task: Optional[str]
    completed_tasks: list[str]
    pending_tasks: list[str]

class SessionManager:
    def __init__(self, session_dir: Path):
        """Initialize session manager with session directory."""
    
    def create(self, task_source: Path, config: RalphConfig) -> Session:
        """Create new session with fresh token."""
    
    def load(self) -> Session:
        """Load existing session from disk."""
    
    def save(self, session: Session) -> None:
        """Persist session state to disk."""
    
    def complete(self, session: Session) -> None:
        """Mark session as completed and finalize."""
    
    def abort(self, session: Session, reason: str) -> None:
        """Mark session as aborted with reason."""
```

```python
# session/token.py
class TokenGenerator:
    @staticmethod
    def generate() -> str:
        """Generate cryptographically secure session token.
        
        Format: ralph-YYYYMMDD-HHMMSS-[16-char hex]
        Uses timestamp + 32 bytes random data, SHA-256 hashed.
        """
    
    @staticmethod
    def validate(token: str) -> bool:
        """Validate token format (not authenticity - that's signal validation)."""
```

```python
# session/checksum.py
class ChecksumManager:
    def __init__(self, session_dir: Path):
        """Initialize with session directory."""
    
    def compute(self, filepath: Path) -> str:
        """Compute SHA-256 checksum of file.
        
        Returns: sha256:[64-char hex]
        """
    
    def store(self, filepath: Path) -> None:
        """Compute and store checksum in .sha256 file."""
    
    def verify(self, filepath: Path) -> bool:
        """Verify stored checksum matches current file.
        
        Returns: True if valid, False if tampered
        Raises: ChecksumMissingError if no stored checksum
        """
```

#### 3.1.3 Anti-Gaming: Token and Checksum

The session module implements two critical anti-gaming mechanisms:

1. **Session Token**: Generated at session start, included in all agent prompts, required in all completion signals. Prevents agents from outputting pre-written completion signals.

2. **Task Status Checksum**: SHA-256 checksum of `task-status.json` stored separately. Verified before every read, updated after every write. Detects any tampering by agents.

```
┌──────────────────────────────────────────────────────────────┐
│                    TAMPER DETECTION FLOW                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Script writes task-status.json]                            │
│           │                                                  │
│           ▼                                                  │
│  [Script computes SHA-256 → stores in task-status.sha256]    │
│           │                                                  │
│           ▼                                                  │
│  [Agent runs... (cannot modify task-status.json)]            │
│           │                                                  │
│           ▼                                                  │
│  [Script reads task-status.json]                             │
│           │                                                  │
│           ▼                                                  │
│  [Script verifies SHA-256 matches stored checksum]           │
│           │                                                  │
│      ┌────┴────┐                                            │
│      │         │                                            │
│   MATCH     MISMATCH                                        │
│      │         │                                            │
│      ▼         ▼                                            │
│  Continue   ABORT                                           │
│             "TAMPERING DETECTED"                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### 3.2 tasks Module

**Purpose:** Parse task files, track status, select next task.

#### 3.2.1 Files

| File | Responsibility |
|------|----------------|
| `parser.py` | Parse prd.json and CR markdown formats |
| `status.py` | Task status tracking with checksum |
| `selector.py` | Priority-based next task selection |

#### 3.2.2 Key Classes

```python
# tasks/parser.py
@dataclass
class Task:
    id: str                         # T-001, T-002, etc.
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: int
    passes: bool
    notes: str
    subtasks: list["Subtask"]

@dataclass
class Subtask:
    id: str                         # T-001.1, T-001.2, etc.
    title: str
    acceptance_criteria: list[str]
    passes: bool
    notes: str

@dataclass
class TaskList:
    project: str
    branch_name: Optional[str]
    description: str
    tasks: list[Task]

class TaskParser:
    def parse_prd_json(self, path: Path) -> TaskList:
        """Parse .ralph/prd.json format."""
    
    def parse_cr_markdown(self, path: Path) -> TaskList:
        """Parse CR markdown with embedded JSON block."""
    
    def write_prd_json(self, task_list: TaskList, path: Path) -> None:
        """Write task list to prd.json format."""
```

```python
# tasks/status.py
@dataclass
class TaskStatusEntry:
    passes: bool
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    iterations: int
    last_failure: Optional[str]

class TaskStatusManager:
    """Manages task-status.json with checksum protection.
    
    CRITICAL: This is the ONLY class that writes task status.
    All status changes go through this class to maintain checksum integrity.
    """
    
    def __init__(self, session_dir: Path, checksum_mgr: ChecksumManager):
        """Initialize with session dir and checksum manager."""
    
    def load(self) -> dict[str, TaskStatusEntry]:
        """Load status, verifying checksum first.
        
        Raises: TamperingDetectedError if checksum mismatch
        """
    
    def mark_started(self, task_id: str) -> None:
        """Mark task as started (script-only)."""
    
    def mark_complete(self, task_id: str) -> None:
        """Mark task as complete (script-only).
        
        This is the ONLY way to complete a task.
        Updates file and checksum atomically.
        """
    
    def record_failure(self, task_id: str, reason: str) -> None:
        """Record failure reason for task."""
    
    def increment_iteration(self, task_id: str) -> None:
        """Increment iteration count for task."""
```

```python
# tasks/selector.py
class TaskSelector:
    def get_next_pending(self, task_list: TaskList, status: dict[str, TaskStatusEntry]) -> Optional[Task]:
        """Get next pending task by priority.
        
        A task is pending if:
        1. passes is False in task_list
        2. All subtasks (if any) have passes=False OR at least one does
        
        Returns: Task with lowest priority where passes=False, or None if all complete
        """
    
    def count_tasks(self, task_list: TaskList) -> tuple[int, int]:
        """Count (completed, pending) tasks."""
```

#### 3.2.3 Status Update Ownership

**CRITICAL:** Only the orchestrator script (via `TaskStatusManager`) updates task status. Agents signal completion but never write to the status file.

```
┌──────────────────────────────────────────────────────────────┐
│              TASK COMPLETION FLOW (Script-Only)              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Agent outputs: <task-done session="...">]                  │
│           │                                                  │
│           ▼                                                  │
│  [Script validates signal token matches SESSION_TOKEN]       │
│           │                                                  │
│      ┌────┴────┐                                            │
│      │         │                                            │
│   VALID     INVALID                                         │
│      │         │                                            │
│      ▼         ▼                                            │
│  [Script     Reject,                                        │
│   updates    retry with                                     │
│   task-      feedback]                                      │
│   status.                                                   │
│   json]                                                     │
│      │                                                       │
│      ▼                                                       │
│  [Script updates checksum]                                   │
│      │                                                       │
│      ▼                                                       │
│  [Script updates prd.json (passes: true)]                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### 3.3 agents Module

**Purpose:** Define agent roles, generate prompts, validate signals, enforce guardrails.

#### 3.3.1 Files

| File | Responsibility |
|------|----------------|
| `roles.py` | Role definitions with tool/model constraints |
| `prompts.py` | Prompt template generation |
| `signals.py` | Completion signal parsing and validation |
| `guardrails.py` | Path restrictions and file change monitoring |

#### 3.3.2 Agent Roles

```python
# agents/roles.py
from enum import Enum
from typing import Optional

class AgentRole(Enum):
    IMPLEMENTATION = "implementation"
    TEST_WRITING = "test_writing"
    REVIEW = "review"
    FIX = "fix"
    PLANNING = "planning"
    UI_PLANNING = "ui_planning"
    UI_IMPLEMENTATION = "ui_implementation"
    ROBOT_PLANNING = "robot_planning"
    ROBOT_IMPLEMENTATION = "robot_implementation"

@dataclass
class RoleConfig:
    role: AgentRole
    model: str
    timeout: int
    allowed_tools: Optional[list[str]]  # None = all tools
    read_only: bool                      # Cannot modify files

# Default role configurations
DEFAULT_ROLES = {
    AgentRole.IMPLEMENTATION: RoleConfig(
        role=AgentRole.IMPLEMENTATION,
        model="claude-opus-4-5-20251101",
        timeout=1800,
        allowed_tools=None,  # All tools
        read_only=False,
    ),
    AgentRole.TEST_WRITING: RoleConfig(
        role=AgentRole.TEST_WRITING,
        model="claude-sonnet-4-5-20250929",
        timeout=1800,
        allowed_tools=["Read", "Grep", "Glob", "Edit", "Write", "LS"],
        read_only=False,  # Can write, but path-restricted
    ),
    AgentRole.REVIEW: RoleConfig(
        role=AgentRole.REVIEW,
        model="haiku",
        timeout=1800,
        allowed_tools=["Read", "Grep", "Glob", "LS"],
        read_only=True,
    ),
    AgentRole.FIX: RoleConfig(
        role=AgentRole.FIX,
        model="claude-sonnet-4-5-20250929",
        timeout=1800,
        allowed_tools=None,
        read_only=False,
    ),
    AgentRole.PLANNING: RoleConfig(
        role=AgentRole.PLANNING,
        model="claude-sonnet-4-5-20250929",
        timeout=1800,
        allowed_tools=["Read", "Grep", "Glob", "LS"],
        read_only=True,
    ),
}
```

#### 3.3.3 Prompt Generation

```python
# agents/prompts.py
class PromptGenerator:
    def __init__(self, session_token: str, cr_file: Path):
        """Initialize with session token and CR file path."""
    
    def implementation(self, task: Task, feedback: str = "") -> str:
        """Generate implementation agent prompt.
        
        Includes:
        - Session token (required in completion signal)
        - Task details and acceptance criteria
        - Previous feedback (if any)
        - Security warnings about token
        - Completion signal format
        """
    
    def test_writing(self, task: Task, impl_output: str, feedback: str = "") -> str:
        """Generate test-writing agent prompt.
        
        Includes:
        - Session token
        - Strict path restrictions warning
        - Implementation output for context
        """
    
    def review(self, task: Task, impl_output: str, test_results: dict) -> str:
        """Generate review agent prompt.
        
        Includes:
        - READ-ONLY warning
        - Review checklist
        - Approval/rejection signal formats
        """
    
    def fix_runtime(self, error_type: str, error_output: str, changed_files: list[str]) -> str:
        """Generate runtime fix agent prompt."""
    
    def ui_planning(self, failures: str, snapshots: list[Path]) -> str:
        """Generate UI planning agent prompt (READ-ONLY)."""
    
    def ui_implementation(self, plan: str, failures: str) -> str:
        """Generate UI implementation agent prompt."""
    
    def robot_planning(self, failures: str, robot_output: str) -> str:
        """Generate Robot Framework planning prompt (READ-ONLY)."""
    
    def robot_implementation(self, plan: str, failures: str) -> str:
        """Generate Robot Framework implementation prompt."""
```

#### 3.3.4 Signal Validation

```python
# agents/signals.py
from enum import Enum
from typing import Union

class SignalType(Enum):
    TASK_DONE = "task-done"
    TESTS_DONE = "tests-done"
    REVIEW_APPROVED = "review-approved"
    REVIEW_REJECTED = "review-rejected"
    FIX_DONE = "fix-done"
    UI_PLAN = "ui-plan"
    UI_FIX_DONE = "ui-fix-done"
    ROBOT_PLAN = "robot-plan"
    ROBOT_FIX_DONE = "robot-fix-done"

@dataclass
class ValidatedSignal:
    signal_type: SignalType
    task_id: Optional[str]
    content: str
    valid: bool

class SignalResult(Enum):
    VALID = "valid"
    NO_SIGNAL = "no_signal"
    INVALID_TOKEN = "invalid_token"

class SignalValidator:
    def __init__(self, session_token: str):
        """Initialize with expected session token."""
    
    def validate_task_done(self, output: str) -> tuple[SignalResult, Optional[str]]:
        """Validate task-done signal.
        
        Returns: (result, task_id or None)
        
        Checks:
        1. Signal pattern exists: <task-done session="...">
        2. Session token matches exactly
        3. Task ID can be extracted
        """
    
    def validate_tests_done(self, output: str) -> tuple[SignalResult, Optional[str]]:
        """Validate tests-done signal."""
    
    def validate_review(self, output: str) -> tuple[SignalResult, Optional[str]]:
        """Validate review-approved or review-rejected signal.
        
        Returns: (result, "APPROVED" | "REJECTED: <issues>" | None)
        """
    
    def validate_fix_done(self, output: str) -> tuple[SignalResult, Optional[str]]:
        """Validate fix-done signal."""
```

#### 3.3.5 Test Agent Guardrails

```python
# agents/guardrails.py
import fnmatch
from pathlib import Path

class TestPathGuardrail:
    """Enforces path restrictions for test-writing agent.
    
    The test-writing agent can ONLY create/modify files matching
    the allowed test path patterns. Any other file changes are
    reverted automatically.
    """
    
    DEFAULT_PATTERNS = [
        "tests/**",
        "test_scripts/**",
        "frontend/**/__tests__/**",
        "frontend/**/*.test.*",
        "frontend/**/*.spec.*",
        "frontend/**/cypress/**",
        "frontend/**/playwright/**",
        "frontend/**/e2e/**",
    ]
    
    def __init__(self, patterns: list[str] = None):
        """Initialize with allowed path patterns."""
        self.patterns = patterns or self.DEFAULT_PATTERNS
    
    def is_allowed(self, path: str) -> bool:
        """Check if path matches any allowed pattern."""
        for pattern in self.patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
    
    def snapshot_modified_paths(self, repo_root: Path) -> set[str]:
        """Get set of currently modified/untracked files."""
    
    def find_violations(self, before: set[str], after: set[str]) -> list[str]:
        """Find newly changed files that violate guardrails."""
    
    def revert_violations(self, violations: list[str], repo_root: Path) -> None:
        """Revert files that shouldn't have been changed.
        
        - For tracked files: git checkout
        - For untracked files: delete
        """
```

```
┌──────────────────────────────────────────────────────────────┐
│              TEST AGENT GUARDRAIL FLOW                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Snapshot modified paths BEFORE test agent]                 │
│           │                                                  │
│           ▼                                                  │
│  [Run test-writing agent]                                    │
│           │                                                  │
│           ▼                                                  │
│  [Snapshot modified paths AFTER test agent]                  │
│           │                                                  │
│           ▼                                                  │
│  [Find NEW paths: after - before]                            │
│           │                                                  │
│           ▼                                                  │
│  [For each new path: is_allowed(path)?]                      │
│           │                                                  │
│      ┌────┴────┐                                            │
│      │         │                                            │
│   ALLOWED   VIOLATION                                       │
│      │         │                                            │
│      ▼         ▼                                            │
│   Keep     Revert                                           │
│            (git checkout OR rm)                             │
│                                                              │
│  [If violations: reject iteration, provide feedback]         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### 3.4 exec Module

**Purpose:** Execute shell commands with timeout, output capture, and logging.

#### 3.4.1 Files

| File | Responsibility |
|------|----------------|
| `runner.py` | Main command execution with subprocess |
| `capture.py` | Stdout/stderr capture and streaming |
| `timeout.py` | Timeout handling and process cleanup |

#### 3.4.2 Key Classes

```python
# exec/runner.py
@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool

class CommandRunner:
    def __init__(self, working_dir: Path, timeout_default: int = 300):
        """Initialize with working directory and default timeout."""
    
    def run(
        self,
        cmd: str,
        timeout: int = None,
        env: dict[str, str] = None,
        capture: bool = True,
        stream: bool = False,
    ) -> CommandResult:
        """Execute command with timeout.
        
        Args:
            cmd: Shell command to execute
            timeout: Timeout in seconds (None = use default)
            env: Additional environment variables
            capture: Whether to capture output
            stream: Whether to stream output in real-time
        
        Returns: CommandResult with exit code, output, and timing
        """
    
    def run_claude(
        self,
        prompt: str,
        model: str,
        timeout: int,
        allowed_tools: list[str] = None,
        output_format: str = "text",
    ) -> CommandResult:
        """Execute Claude CLI with prompt.
        
        Supports RALPH_CLAUDE_CMD override for testing.
        """
```

```python
# exec/capture.py
class OutputCapture:
    """Capture and optionally stream command output."""
    
    def __init__(self, log_file: Path = None, stream_to_console: bool = False):
        """Initialize capture with optional log file and streaming."""
    
    def capture(self, process: subprocess.Popen) -> tuple[str, str]:
        """Capture stdout and stderr from process."""
    
    def tee(self, process: subprocess.Popen) -> tuple[str, str]:
        """Capture output while also streaming to console."""
```

```python
# exec/timeout.py
class TimeoutHandler:
    """Handle command timeouts with graceful shutdown."""
    
    @staticmethod
    def with_timeout(func: Callable, timeout: int) -> Any:
        """Execute function with timeout.
        
        Raises: TimeoutError if exceeded
        """
    
    @staticmethod
    def kill_process_tree(pid: int) -> None:
        """Kill process and all children."""
```

---

### 3.5 gates Module

**Purpose:** Execute quality gates (tests, type checks, builds) with conditional execution.

#### 3.5.1 Files

| File | Responsibility |
|------|----------------|
| `runner.py` | Gate execution orchestration |
| `conditions.py` | When-condition evaluation |
| `results.py` | Gate result aggregation |

#### 3.5.2 Key Classes

```python
# gates/runner.py
@dataclass
class GateResult:
    name: str
    passed: bool
    output: str
    duration_ms: int
    skipped: bool
    skipped_reason: Optional[str]

class GateRunner:
    def __init__(self, config: GatesConfig, cmd_runner: CommandRunner):
        """Initialize with gates config and command runner."""
    
    def run_build_gates(self) -> list[GateResult]:
        """Run fast build gates (mypy, tsc).
        
        Used during task loop for quick feedback.
        Stops at first fatal failure.
        """
    
    def run_full_gates(self) -> list[GateResult]:
        """Run comprehensive gates (pytest, lint, build).
        
        Used after task completion.
        Stops at first fatal failure.
        """
    
    def run_single_gate(self, gate: GateConfig) -> GateResult:
        """Run a single gate with condition check."""
```

```python
# gates/conditions.py
class GateCondition:
    """Evaluate when-conditions for gates."""
    
    def __init__(self, repo_root: Path):
        """Initialize with repo root."""
    
    def should_run(self, when: str) -> tuple[bool, Optional[str]]:
        """Check if gate should run based on when condition.
        
        Supported conditions:
        - File path: "pyproject.toml" - runs if file exists
        - Glob: "frontend/**/*.ts" - runs if any match
        - Always: null/omitted - always runs
        
        Returns: (should_run, skip_reason if not)
        """
```

```python
# gates/results.py
@dataclass
class GatesReport:
    timestamp: datetime
    gates: list[GateResult]
    all_passed: bool
    first_failure: Optional[str]

class GatesReporter:
    def aggregate(self, results: list[GateResult]) -> GatesReport:
        """Aggregate gate results into report."""
    
    def format_for_feedback(self, report: GatesReport) -> str:
        """Format report for agent feedback."""
```

---

### 3.6 services Module

**Purpose:** Manage backend/frontend service lifecycle for runtime verification.

#### 3.6.1 Files

| File | Responsibility |
|------|----------------|
| `manager.py` | Service start/stop orchestration |
| `health.py` | Health check polling |
| `cleanup.py` | Process cleanup and port release |

#### 3.6.2 Key Classes

```python
# services/manager.py
@dataclass
class ServiceState:
    name: str
    pid: Optional[int]
    port: int
    status: Literal["stopped", "starting", "healthy", "unhealthy", "failed"]
    started_at: Optional[datetime]
    log_file: Path

class ServiceManager:
    """Manages backend and frontend service lifecycle.
    
    Services are started in prod-like mode for verification,
    with health checks to confirm readiness.
    """
    
    def __init__(self, config: ServicesConfig, session_dir: Path):
        """Initialize with services config and session directory."""
    
    def start_backend(self, mode: Literal["dev", "prod"] = "prod") -> ServiceState:
        """Start backend service.
        
        1. Kill any existing process on port
        2. Start process with configured command
        3. Store PID in session_dir/pids/backend.pid
        4. Log to session_dir/logs/backend.log
        """
    
    def start_frontend(self, mode: Literal["dev", "prod"] = "prod") -> ServiceState:
        """Start frontend service.
        
        In prod mode:
        1. Run build command first
        2. Then start preview server
        """
    
    def stop_all(self) -> None:
        """Stop all managed services."""
    
    def get_status(self, service: str) -> ServiceState:
        """Get current status of a service."""
```

```python
# services/health.py
class HealthChecker:
    """Poll health endpoints with retry."""
    
    def __init__(self, timeout: int = 30, retry_interval: int = 2):
        """Initialize with timeout and retry interval."""
    
    def wait_for_health(
        self,
        url: str,
        max_attempts: int = None,
    ) -> tuple[bool, Optional[str]]:
        """Wait for health endpoint to respond 2xx.
        
        Returns: (healthy, error_message if not)
        """
    
    def check_detailed_health(self, endpoints: list[str]) -> dict[str, bool]:
        """Check multiple health endpoints."""
```

```python
# services/cleanup.py
class ServiceCleanup:
    """Clean up processes and ports."""
    
    @staticmethod
    def kill_process(pid: int) -> bool:
        """Kill process by PID."""
    
    @staticmethod
    def kill_port(port: int) -> bool:
        """Kill any process listening on port."""
    
    @staticmethod
    def cleanup_pid_files(session_dir: Path) -> None:
        """Clean up PID files and their processes."""
```

---

### 3.7 ui Module

**Purpose:** Run UI tests (agent-browser, Robot Framework) with fix loops.

#### 3.7.1 Files

| File | Responsibility |
|------|----------------|
| `agent_browser.py` | Agent-browser test execution |
| `robot.py` | Robot Framework test execution |
| `loops.py` | UI fix loops (plan → implement → retest) |

#### 3.7.2 Key Classes

```python
# ui/agent_browser.py
@dataclass
class UITestResult:
    test_name: str
    passed: bool
    snapshot_path: Optional[Path]
    screenshot_path: Optional[Path]
    error: Optional[str]

class AgentBrowserRunner:
    """Run agent-browser UI smoke tests."""
    
    def __init__(self, config: AgentBrowserConfig, session_dir: Path, frontend_port: int):
        """Initialize with config, session dir, and frontend port."""
    
    def run_smoke_tests(self) -> tuple[bool, list[UITestResult]]:
        """Run all configured smoke tests.
        
        Tests:
        1. App loads (layout elements visible)
        2. Dashboard renders (not blank)
        3. Projects UI functional
        4. Upload UI accessible
        5. History/QA blocks render
        6. QA input functional
        
        Returns: (all_passed, results)
        """
    
    def capture_snapshot(self, name: str) -> Path:
        """Capture accessibility snapshot."""
    
    def capture_screenshot(self, name: str) -> Path:
        """Capture screenshot."""
```

```python
# ui/robot.py
@dataclass
class RobotTestResult:
    name: str
    status: Literal["PASS", "FAIL", "SKIP"]
    message: Optional[str]

@dataclass
class RobotReport:
    passed: int
    failed: int
    failed_tests: list[str]
    output_dir: Path
    report_html: Path
    log_html: Path

class RobotRunner:
    """Run Robot Framework UI tests."""
    
    def __init__(self, config: RobotConfig, session_dir: Path, frontend_port: int):
        """Initialize with config, session dir, and frontend port."""
    
    def run_suite(self) -> RobotReport:
        """Run Robot Framework test suite.
        
        Passes variables:
        - BASE_URL: http://127.0.0.1:{frontend_port}
        - HEADLESS: from config
        - SCREENSHOT_DIR: session output dir
        """
    
    def parse_results(self, output_xml: Path) -> list[RobotTestResult]:
        """Parse Robot output.xml for results."""
```

```python
# ui/loops.py
class UIFixLoop:
    """Orchestrate UI fix iterations.
    
    Each iteration:
    1. Run UI tests
    2. If pass → done
    3. If fail → planning agent (read-only) → implementation agent → rebuild → repeat
    """
    
    def __init__(
        self,
        agent_browser: AgentBrowserRunner,
        robot: RobotRunner,
        service_manager: ServiceManager,
        gate_runner: GateRunner,
        prompt_gen: PromptGenerator,
        cmd_runner: CommandRunner,
        max_iterations: int,
    ):
        """Initialize fix loop with all dependencies."""
    
    def run_agent_browser_fix_loop(self) -> bool:
        """Run agent-browser fix loop.
        
        Returns: True if all tests pass within max_iterations
        """
    
    def run_robot_fix_loop(self) -> bool:
        """Run Robot Framework fix loop.
        
        Returns: True if all tests pass within max_iterations
        """
    
    def run_runtime_fix_loop(self) -> bool:
        """Run build/runtime fix loop.
        
        Focuses on making build gates pass and services healthy.
        """
```

---

### 3.8 reports Module

**Purpose:** Event logging, summary generation, and artifact management.

#### 3.8.1 Files

| File | Responsibility |
|------|----------------|
| `timeline.py` | JSONL event logging |
| `summary.py` | Run summary generation |
| `artifacts.py` | Screenshot/snapshot management |

#### 3.8.2 Key Classes

```python
# reports/timeline.py
from enum import Enum

class EventType(Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_FAILED = "agent_failed"
    GATES_RUN = "gates_run"
    GATE_PASS = "gate_pass"
    GATE_FAIL = "gate_fail"
    SERVICE_START = "service_start"
    SERVICE_READY = "service_ready"
    SERVICE_FAILED = "service_failed"
    UI_TEST_START = "ui_test_start"
    UI_TEST_PASS = "ui_test_pass"
    UI_TEST_FAIL = "ui_test_fail"
    FIX_LOOP_START = "fix_loop_start"
    FIX_LOOP_ITERATION = "fix_loop_iteration"
    FIX_LOOP_END = "fix_loop_end"
    CHECKSUM_VERIFIED = "checksum_verified"
    CHECKSUM_FAILED = "checksum_failed"

@dataclass
class TimelineEvent:
    ts: datetime
    event: EventType
    session_id: str
    task_id: Optional[str] = None
    role: Optional[str] = None
    signal: Optional[str] = None
    gate: Optional[str] = None
    status: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    details: Optional[dict] = None

class TimelineLogger:
    """Append-only JSONL event logger."""
    
    def __init__(self, session_dir: Path, session_id: str):
        """Initialize with session directory and ID."""
    
    def log(self, event: TimelineEvent) -> None:
        """Append event to timeline.jsonl."""
    
    def log_task_start(self, task_id: str) -> None:
        """Log task start event."""
    
    def log_agent_complete(self, role: AgentRole, task_id: str, signal: str, duration_ms: int) -> None:
        """Log agent completion event."""
    
    def log_gate_result(self, gate: str, passed: bool, duration_ms: int) -> None:
        """Log gate execution result."""
```

```python
# reports/summary.py
@dataclass
class RunSummary:
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    status: str
    tasks_completed: int
    tasks_total: int
    iterations: int
    gates_passed: list[str]
    gates_failed: list[str]
    ui_tests_passed: bool
    verification_level: str  # BUILD_RUNTIME_ONLY, AGENT_BROWSER_ONLY, ROBOT_ONLY, FULL

class SummaryGenerator:
    def __init__(self, session: Session, timeline_path: Path):
        """Initialize with session and timeline path."""
    
    def generate(self) -> RunSummary:
        """Generate run summary from timeline events."""
    
    def format_success_banner(self, summary: RunSummary) -> str:
        """Format success banner for console output."""
    
    def format_failure_banner(self, summary: RunSummary, phase: str) -> str:
        """Format failure banner with debug info."""
```

```python
# reports/artifacts.py
class ArtifactManager:
    """Manage session artifacts (screenshots, snapshots, logs)."""
    
    def __init__(self, session_dir: Path):
        """Initialize with session directory."""
    
    def save_screenshot(self, name: str, data: bytes) -> Path:
        """Save screenshot to artifacts/screenshots/."""
    
    def save_snapshot(self, name: str, content: str) -> Path:
        """Save accessibility snapshot to artifacts/snapshots/."""
    
    def save_agent_log(self, role: AgentRole, task_id: str, output: str) -> Path:
        """Save agent output to logs/."""
    
    def save_gate_log(self, gate: str, task_id: str, output: str) -> Path:
        """Save gate output to logs/."""
```

---

### 3.9 config Module

**Purpose:** Load and validate `.ralph/ralph.yml` configuration.

#### 3.9.1 Key Classes

```python
# config.py
from pydantic import BaseModel, Field
from pathlib import Path

class TaskSourceConfig(BaseModel):
    type: Literal["prd_json", "cr_markdown"]
    path: str

class StartCommandsConfig(BaseModel):
    dev: Optional[str] = None
    prod: Optional[str] = None

class BackendServiceConfig(BaseModel):
    start: StartCommandsConfig
    port: int = Field(ge=1, le=65535)
    health: list[str] = ["/health"]
    timeout: int = Field(30, ge=1, le=300)

class FrontendServiceConfig(BaseModel):
    build: Optional[str] = None
    serve: StartCommandsConfig
    port: int = Field(ge=1, le=65535)
    timeout: int = Field(30, ge=1, le=300)

class ServicesConfig(BaseModel):
    backend: Optional[BackendServiceConfig] = None
    frontend: Optional[FrontendServiceConfig] = None

class GateConfig(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_-]+$")
    cmd: str
    when: Optional[str] = None
    timeout_seconds: int = Field(300, ge=1, le=3600)
    fatal: bool = True

class GatesConfig(BaseModel):
    build: list[GateConfig] = []
    full: list[GateConfig]

class AgentRoleConfig(BaseModel):
    model: Optional[str] = None
    timeout: int = Field(1800, ge=60, le=7200)
    allowed_tools: Optional[list[str]] = None

class AgentsConfig(BaseModel):
    implementation: AgentRoleConfig = AgentRoleConfig()
    test_writing: AgentRoleConfig = AgentRoleConfig()
    review: AgentRoleConfig = AgentRoleConfig()
    fix: AgentRoleConfig = AgentRoleConfig()
    planning: AgentRoleConfig = AgentRoleConfig()

class LimitsConfig(BaseModel):
    claude_timeout: int = Field(1800, ge=60, le=7200)
    max_iterations: int = Field(30, ge=1, le=100)
    post_verify_iterations: int = Field(10, ge=1, le=50)
    ui_fix_iterations: int = Field(10, ge=1, le=50)
    robot_fix_iterations: int = Field(10, ge=1, le=50)

class AutopilotConfig(BaseModel):
    enabled: bool = False
    reports_dir: str = "./reports"
    branch_prefix: str = "ralph/"
    create_pr: bool = True
    # ... analysis, prd, tasks, memory sub-configs

class GitConfig(BaseModel):
    base_branch: str = "main"
    remote: str = "origin"

class PRConfig(BaseModel):
    enabled: bool = True
    title_template: str = "Ralph: {priority_item}"
    body_template: Optional[str] = None

class RalphConfig(BaseModel):
    version: Literal["1"]
    task_source: TaskSourceConfig
    services: Optional[ServicesConfig] = None
    gates: GatesConfig
    test_paths: list[str] = ["tests/**", "**/*.test.*", "**/*.spec.*"]
    ui: Optional[UIConfig] = None
    agents: AgentsConfig = AgentsConfig()
    limits: LimitsConfig = LimitsConfig()
    autopilot: Optional[AutopilotConfig] = None
    git: GitConfig
    pr: PRConfig = PRConfig()

class ConfigLoader:
    def __init__(self, repo_root: Path):
        """Initialize with repo root."""
    
    def load(self, config_path: Path = None) -> RalphConfig:
        """Load and validate configuration.
        
        Default path: .ralph/ralph.yml
        
        Raises: ConfigValidationError on invalid config
        """
    
    def detect_stack(self) -> Literal["python", "node", "fullstack", "unknown"]:
        """Detect project stack from files."""
    
    def generate_default(self, stack: str) -> RalphConfig:
        """Generate default config for detected stack."""
```

---

### 3.10 cli Module

**Purpose:** Command-line interface entry point.

#### 3.10.1 Commands

```python
# cli.py
import click
from pathlib import Path

@click.group()
def cli():
    """Ralph Orchestrator - Multi-Agent Verification System"""
    pass

@cli.command()
@click.option("--template", type=click.Choice(["python", "node", "fullstack"]))
def init(template):
    """Initialize Ralph in current repository.
    
    Creates:
    - .ralph/ralph.yml (configuration)
    - .ralph/prd.json (empty task list)
    - AGENTS.md (agent memory)
    """

@cli.command()
@click.option("--prd-json", type=Path, help="Path to prd.json task file")
@click.option("--cr", type=Path, help="Path to CR markdown file")
@click.option("--max-iterations", type=int, default=30)
@click.option("--post-verify/--no-post-verify", default=True)
@click.option("--ui-verify/--no-ui-verify", default=True)
@click.option("--robot-verify/--no-robot-verify", default=True)
def run(prd_json, cr, max_iterations, post_verify, ui_verify, robot_verify):
    """Run verified execution loop on tasks.
    
    Examples:
        ralph run --prd-json .ralph/prd.json
        ralph run --cr changes/CR-FEATURE.md
    """

@cli.command()
def verify():
    """Run post-completion verification only.
    
    Runs build gates, runtime verification, and UI tests
    without executing the task loop.
    """

@cli.command()
@click.option("--reports", type=Path, default="./reports")
@click.option("--dry-run", is_flag=True)
@click.option("--create-pr/--no-create-pr", default=True)
def autopilot(reports, dry_run, create_pr):
    """Run autopilot self-improvement mode.
    
    1. Find latest report in reports directory
    2. Analyze report to pick #1 priority
    3. Generate PRD and tasks
    4. Run verified execution loop
    5. Create PR (optional)
    """

@cli.command()
@click.option("--cr", type=Path, required=True)
def import_cr(cr):
    """Import CR markdown to prd.json format."""

@cli.command()
@click.option("--format", type=click.Choice(["cr", "prd"]), default="cr")
@click.option("--output", type=Path, required=True)
def export(format, output):
    """Export prd.json to markdown format."""

if __name__ == "__main__":
    cli()
```

---

### 3.11 autopilot Module

**Purpose:** Implement Compound Product–style self-improvement pipeline for autonomous operation.

> **📖 Detailed Specification:** See [`autopilot-module-design.md`](./autopilot-module-design.md) for the complete autopilot module design including all phases, data models, prompt templates, and error handling.

#### 3.11.1 Files

| File | Responsibility |
|------|----------------|
| `orchestrator.py` | Main autopilot pipeline coordinator |
| `discovery.py` | Report discovery and selection |
| `analysis.py` | Report analysis with LLM |
| `branch.py` | Git branch management |
| `prd_gen.py` | PRD generation |
| `tasks_gen.py` | Task list generation |
| `pr.py` | Pull request creation |
| `run_state.py` | Run persistence and recovery |
| `memory.py` | Progress tracking and archival |
| `prompts/` | Prompt templates directory |

#### 3.11.2 Pipeline Overview

```
Report Discovery → Analysis → Research (optional) → Branch → PRD → Tasks → Verified Execution → PR
```

1. **Report Discovery**: Find latest report in configured directory
2. **Analysis**: Use LLM to identify #1 priority item
3. **Branch Management**: Create/checkout feature branch
4. **PRD Generation**: Generate PRD markdown from analysis
5. **Task Generation**: Convert PRD to `prd.json` with granular tasks
6. **Verified Execution**: Run main task loop + verification
7. **PR Creation**: Push branch and create pull request

#### 3.11.3 Key Classes

```python
# autopilot/orchestrator.py
class AutopilotOrchestrator:
    """Coordinates the full autopilot pipeline."""
    
    def run(self, dry_run: bool = False) -> AutopilotResult:
        """Run the full autopilot pipeline.
        
        Args:
            dry_run: Stop after analysis, show plan only
        
        Returns: AutopilotResult with success status and PR URL
        """
    
    def resume(self) -> AutopilotResult:
        """Resume an incomplete autopilot run."""
```

```python
# autopilot/analysis.py
class ReportAnalyzer:
    """Analyzes reports to identify actionable priorities."""
    
    def analyze(self, report_path: Path) -> AnalysisOutput:
        """Analyze report and return structured output.
        
        Supports multiple LLM providers:
        - Anthropic (direct API)
        - OpenAI (direct API)
        - OpenRouter
        - AI Gateway (Vercel or compatible)
        """
```

```python
# autopilot/run_state.py
class RunStateManager:
    """Manages autopilot run persistence for recovery."""
    
    def create(self) -> AutopilotRun:
        """Create new run with generated ID."""
    
    def get_latest_incomplete(self) -> Optional[AutopilotRun]:
        """Get latest incomplete run for recovery."""
```

#### 3.11.4 Artifact Locations

| Artifact | Path | Purpose |
|----------|------|---------|
| Analysis output | `.ralph/autopilot/analysis.json` | LLM analysis result |
| Run states | `.ralph/autopilot/runs/*.json` | Run persistence |
| Progress log | `.ralph/progress.txt` | Human-readable progress |
| Archive | `.ralph/autopilot/archive/` | Previous run artifacts |

---

## 4. Anti-Gaming Mechanisms

### 4.1 Summary of Anti-Gaming Features

| Mechanism | Location | Purpose |
|-----------|----------|---------|
| **Session Token** | `session/token.py` | Prevent pre-written completion signals |
| **Task Status Checksum** | `session/checksum.py` | Detect tampering with task status |
| **Script-Only Status Updates** | `tasks/status.py` | Agents cannot mark tasks complete |
| **Signal Validation** | `agents/signals.py` | Verify token in completion signals |
| **Test Path Guardrails** | `agents/guardrails.py` | Restrict test agent file access |
| **Read-Only Roles** | `agents/roles.py` | Review/planning agents cannot modify |
| **Tool Restrictions** | `agents/roles.py` | Limit tools per role |

### 4.2 Attack Prevention

| Attack Vector | Prevention |
|---------------|------------|
| Agent outputs fake completion | Signal validation requires session token |
| Agent modifies task-status.json | Checksum verification detects tampering |
| Agent marks own task complete | Only script writes to task status |
| Test agent modifies prod code | Guardrails revert non-test file changes |
| Review agent approves own code | Review uses read-only tool set |
| Pre-cached completion signals | Token changes every session |

---

## 5. Verification Loops

### 5.1 Main Task Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                      MAIN TASK LOOP                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FOR each iteration (1..max_iterations):                        │
│      │                                                          │
│      ├─► Verify checksum                                        │
│      │                                                          │
│      ├─► Count tasks (completed, pending)                       │
│      │                                                          │
│      ├─► IF pending == 0:                                       │
│      │       └─► Run post-completion verification               │
│      │           └─► EXIT success/failure                       │
│      │                                                          │
│      ├─► Get next pending task                                  │
│      │                                                          │
│      ├─► PHASE 1: Implementation Agent                          │
│      │       ├─► Generate prompt with session token             │
│      │       ├─► Run Claude with full tool access               │
│      │       └─► Validate task-done signal                      │
│      │               ├─► NO_SIGNAL → retry with feedback        │
│      │               ├─► INVALID_TOKEN → security warning       │
│      │               └─► VALID → continue                       │
│      │                                                          │
│      ├─► PHASE 2: Test Writing Agent                            │
│      │       ├─► Snapshot modified paths (BEFORE)               │
│      │       ├─► Run Claude with restricted tools               │
│      │       ├─► Snapshot modified paths (AFTER)                │
│      │       ├─► Find violations (non-test files)               │
│      │       └─► Revert violations, reject if any               │
│      │                                                          │
│      ├─► PHASE 3: Test Gates (Script-Enforced)                  │
│      │       ├─► Run pytest, mypy, tsc, lint, build             │
│      │       └─► IF any fatal fail → retry with feedback        │
│      │                                                          │
│      ├─► PHASE 4: Review Agent                                  │
│      │       ├─► Generate prompt (READ-ONLY)                    │
│      │       ├─► Run Claude with read tools only                │
│      │       └─► Validate review signal                         │
│      │               ├─► APPROVED → mark complete               │
│      │               ├─► REJECTED → retry with feedback         │
│      │               └─► NO_SIGNAL → treat as approved          │
│      │                                                          │
│      └─► PHASE 5: Script Updates Task Status                    │
│              ├─► Verify checksum                                │
│              ├─► Update task-status.json                        │
│              ├─► Update checksum                                │
│              └─► Update prd.json (passes: true)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Post-Completion Verification

```
┌─────────────────────────────────────────────────────────────────┐
│              POST-COMPLETION VERIFICATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PHASE 1: Build & Runtime Verification                          │
│      │                                                          │
│      FOR each iteration (1..post_verify_max):                   │
│          ├─► Run build gates (mypy, tsc, npm build)             │
│          │       IF fail → run fix agent → continue             │
│          │                                                      │
│          ├─► Start backend (prod mode)                          │
│          ├─► Wait for backend health                            │
│          │       IF fail → run fix agent → continue             │
│          │                                                      │
│          ├─► Start frontend (prod mode, build first)            │
│          ├─► Wait for frontend ready                            │
│          │       IF fail → run fix agent → continue             │
│          │                                                      │
│          └─► All pass → proceed to Phase 2                      │
│                                                                 │
│  PHASE 2: Agent-Browser UI Tests (if available)                 │
│      │                                                          │
│      FOR each iteration (1..ui_fix_max):                        │
│          ├─► Run smoke tests                                    │
│          │       IF all pass → proceed to Phase 3               │
│          │                                                      │
│          ├─► Planning agent (READ-ONLY)                         │
│          │       └─► Analyze failures, output plan              │
│          │                                                      │
│          ├─► Implementation agent                               │
│          │       └─► Implement fixes based on plan              │
│          │                                                      │
│          ├─► Build verification                                 │
│          ├─► Restart services                                   │
│          └─► Continue to next iteration                         │
│                                                                 │
│  PHASE 3: Robot Framework Tests (if available)                  │
│      │                                                          │
│      FOR each iteration (1..robot_fix_max):                     │
│          ├─► Run Robot suite                                    │
│          │       IF all pass → SUCCESS                          │
│          │                                                      │
│          ├─► Planning agent (READ-ONLY)                         │
│          ├─► Implementation agent                               │
│          ├─► Build verification                                 │
│          ├─► Restart services                                   │
│          └─► Continue to next iteration                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Flow Diagrams

### 6.1 Configuration Loading

```
.ralph/ralph.yml ──► ConfigLoader ──► RalphConfig (validated)
                          │
                          ├─► Detect stack (python/node/fullstack)
                          │
                          └─► Merge with defaults
```

### 6.2 Task Status Flow

```
.ralph/prd.json ──► TaskParser ──► TaskList
       │                              │
       │                              ▼
       │                        TaskSelector ──► next pending Task
       │                              │
       │                              ▼
       │                        TaskStatusManager
       │                              │
       │                    ┌─────────┼─────────┐
       │                    │         │         │
       │                    ▼         ▼         ▼
       │               load()    mark_*()   verify()
       │                    │         │         │
       │                    │         ▼         │
       │                    │  .ralph-session/  │
       │                    │  task-status.json │
       │                    │  task-status.sha256
       │                    │         │
       │                    └────┬────┘
       │                         │
       │                         ▼
       └──────────────────► sync on complete
```

### 6.3 Agent Execution Flow

```
PromptGenerator ──► prompt string
       │
       ▼
CommandRunner.run_claude() ──► claude CLI
       │
       ▼
agent output string
       │
       ▼
SignalValidator ──► SignalResult + extracted data
       │
       ├─► VALID: proceed
       │
       ├─► INVALID_TOKEN: security warning + retry
       │
       └─► NO_SIGNAL: feedback + retry
```

---

## 7. Interface Contracts

### 7.1 Module Dependencies

| Module | Depends On | Provides To |
|--------|------------|-------------|
| `cli` | config, session, tasks, agents, exec, gates, services, ui, reports, autopilot | Entry point |
| `config` | (none) | RalphConfig to all modules |
| `session` | (none) | Session, TokenGenerator, ChecksumManager |
| `tasks` | session.checksum | TaskList, TaskSelector, TaskStatusManager |
| `agents` | session.token | RoleConfig, PromptGenerator, SignalValidator, TestPathGuardrail |
| `exec` | (none) | CommandRunner, CommandResult |
| `gates` | exec, config | GateRunner, GatesReport |
| `services` | exec, config | ServiceManager, HealthChecker |
| `ui` | exec, services, agents, gates, reports | AgentBrowserRunner, RobotRunner, UIFixLoop |
| `reports` | session | TimelineLogger, SummaryGenerator, ArtifactManager |
| `autopilot` | exec, agents, tasks, config, session, reports | AutopilotOrchestrator, ReportAnalyzer, PRDGenerator, TasksGenerator, PRCreator |

> **Note:** The autopilot module has its own detailed specification at [`autopilot-module-design.md`](./autopilot-module-design.md) which covers all sub-module dependencies, data models, and prompt templates.

### 7.2 Error Handling

| Error | Raised By | Handled By |
|-------|-----------|------------|
| `TamperingDetectedError` | ChecksumManager | Main loop - abort session |
| `InvalidSignalError` | SignalValidator | Main loop - retry with feedback |
| `GateFailedError` | GateRunner | Main loop - retry with feedback |
| `ServiceHealthError` | HealthChecker | Fix loop - run fix agent |
| `TimeoutError` | CommandRunner | Main loop - handle per role |
| `ConfigValidationError` | ConfigLoader | CLI - exit with error |

---

## 8. Testing Strategy

### 8.1 Unit Tests

| Module | Test Focus |
|--------|------------|
| `session/token.py` | Token format, uniqueness, validation |
| `session/checksum.py` | Checksum computation, verification, tampering detection |
| `tasks/parser.py` | prd.json parsing, CR markdown parsing |
| `tasks/selector.py` | Priority ordering, subtask aggregation |
| `agents/signals.py` | Signal extraction, token validation |
| `agents/guardrails.py` | Path matching, violation detection |
| `gates/conditions.py` | When-condition evaluation |

### 8.2 Integration Tests (Mock Claude)

| Test | Validates |
|------|-----------|
| `test_task_advancement` | Tasks advance through valid signals |
| `test_invalid_token_rejected` | Invalid tokens rejected |
| `test_tampering_detected` | Checksum verification works |
| `test_test_guardrails` | Non-test file changes reverted |
| `test_gates_ordering` | Gates run in correct order |
| `test_fix_loop_iteration` | Fix loops iterate correctly |

### 8.3 Fixture Repos

```
fixtures/
├── python_min/           # Minimal Python project
│   ├── pyproject.toml
│   ├── src/
│   └── tests/
├── node_min/             # Minimal Node project
│   ├── package.json
│   └── src/
└── fullstack_min/        # Minimal fullstack project
    ├── pyproject.toml
    ├── frontend/
    └── .ralph/ralph.yml
```

### 8.4 Mock Claude Executable

```python
# tests/mock_claude.py
"""Mock claude CLI for testing.

Returns deterministic outputs with valid/invalid signals
based on environment variables or input patterns.

Usage:
    RALPH_CLAUDE_CMD="python tests/mock_claude.py" ralph run ...
"""

import sys

def main():
    prompt = sys.stdin.read()
    session_token = extract_token_from_prompt(prompt)
    
    if "SIMULATE_INVALID_TOKEN" in prompt:
        print(f'<task-done session="wrong-token">Fake completion</task-done>')
    elif "SIMULATE_NO_SIGNAL" in prompt:
        print("I did some work but forgot the signal")
    else:
        print(f'<task-done session="{session_token}">Task completed</task-done>')

if __name__ == "__main__":
    main()
```

---

## Appendix A: Migration from ralph-verified.sh

| Bash Function | Python Module | Notes |
|---------------|---------------|-------|
| `generate_session_token()` | `session/token.py` | Same algorithm |
| `init_session()` | `session/manager.py` | Creates session + dirs |
| `update_checksum()` | `session/checksum.py` | SHA-256 |
| `verify_checksum()` | `session/checksum.py` | Returns bool |
| `get_next_pending_task()` | `tasks/selector.py` | JSON parsing not grep |
| `mark_task_complete()` | `tasks/status.py` | Atomic update |
| `generate_impl_prompt()` | `agents/prompts.py` | Template method |
| `validate_task_done_signal()` | `agents/signals.py` | Regex → structured |
| `is_allowed_test_path()` | `agents/guardrails.py` | Glob matching |
| `run_test_gates()` | `gates/runner.py` | Configurable gates |
| `start_backend()` | `services/manager.py` | Config-driven |
| `wait_for_backend()` | `services/health.py` | Polling with retry |
| `run_ui_smoke_tests()` | `ui/agent_browser.py` | Structured results |
| `run_robot_tests()` | `ui/robot.py` | XML parsing |
| `run_ui_fix_loop()` | `ui/loops.py` | Orchestrates fix |
| `run_runtime_fix_loop()` | `ui/loops.py` | Build/runtime fixes |

---

*End of Module Design Specification*
