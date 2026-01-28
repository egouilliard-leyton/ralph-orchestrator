"""Run engine for Ralph orchestrator.

Implements the full verified task loop:
1. Load configuration and tasks
2. For each pending task:
   a. Implementation agent
   b. Test-writing agent (guardrailed)
   c. Quality gates
   d. Review agent
   e. Mark task complete
3. Session management and anti-gaming

This module provides the CLI-facing run engine that wraps the CLI-agnostic
OrchestrationService from the services package.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from .config import RalphConfig, load_config
from .session import Session, create_session, load_session, TamperingDetectedError
from .timeline import TimelineLogger, create_timeline_logger, EventType
from .execution_log import ExecutionLogger, create_execution_logger
from .tasks.prd import PRDData, Task, load_prd, save_prd, get_pending_tasks, mark_task_complete
from .signals import (
    SignalType,
    validate_implementation_signal,
    validate_test_writing_signal,
    validate_review_signal,
    validate_fix_signal,
    get_feedback_for_missing_signal,
    get_feedback_for_invalid_token,
)
from .guardrails import FilePathGuardrail, create_guardrail
from .gates import GateRunner, create_gate_runner, format_gate_failure, format_gates_summary
from .agents.prompts import (
    AgentRole,
    TaskContext,
    build_implementation_prompt,
    build_test_writing_prompt,
    build_review_prompt,
    build_fix_prompt,
    get_allowed_tools_for_role,
)
from .agents.claude import ClaudeRunner, create_claude_runner, ClaudeResult

# Re-export ExitCode and result types from services for backward compatibility
from .services.orchestration_service import (
    ExitCode,
    TaskRunResult,
    OrchestrationOptions,
    OrchestrationResult,
    OrchestrationService,
    EventType as ServiceEventType,
    OrchestrationEvent,
    TaskStartedEvent,
    TaskCompletedEvent,
    AgentPhaseChangedEvent,
    GateRunningEvent,
    GateCompletedEvent,
    SignalDetectedEvent,
)


@dataclass
class RunOptions:
    """Options for the run command."""
    prd_json: Optional[str] = None
    task_id: Optional[str] = None
    from_task_id: Optional[str] = None
    max_iterations: int = 200
    gate_type: str = "full"
    dry_run: bool = False
    resume: bool = False
    post_verify: bool = True
    verbose: bool = False
    with_smoke: Optional[bool] = None  # None = use config/task defaults
    with_robot: Optional[bool] = None  # None = use config/task defaults

    def to_orchestration_options(self) -> OrchestrationOptions:
        """Convert to OrchestrationOptions for the service."""
        return OrchestrationOptions(
            prd_json=self.prd_json,
            task_id=self.task_id,
            from_task_id=self.from_task_id,
            max_iterations=self.max_iterations,
            gate_type=self.gate_type,
            dry_run=self.dry_run,
            resume=self.resume,
            post_verify=self.post_verify,
            with_smoke=self.with_smoke,
            with_robot=self.with_robot,
        )


@dataclass
class RunResult:
    """Result of the full run."""
    exit_code: ExitCode
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_pending: int = 0
    total_duration_ms: int = 0
    task_results: List[TaskRunResult] = field(default_factory=list)
    error: Optional[str] = None
    session_id: Optional[str] = None

    @classmethod
    def from_orchestration_result(cls, result: OrchestrationResult) -> "RunResult":
        """Create RunResult from OrchestrationResult."""
        return cls(
            exit_code=result.exit_code,
            tasks_completed=result.tasks_completed,
            tasks_failed=result.tasks_failed,
            tasks_pending=result.tasks_pending,
            total_duration_ms=result.total_duration_ms,
            task_results=result.task_results,
            error=result.error,
            session_id=result.session_id,
        )


class RunEngine:
    """Main execution engine for the verified task loop.

    This class provides the CLI-facing interface to the orchestration service,
    adding CLI-specific output (print statements, progress indicators) on top
    of the service's event-driven architecture.

    For programmatic access without CLI dependencies, use OrchestrationService
    directly from ralph_orchestrator.services.
    """

    def __init__(
        self,
        config: RalphConfig,
        prd: PRDData,
        session: Session,
        timeline: TimelineLogger,
        execution_logger: ExecutionLogger,
        claude_runner: ClaudeRunner,
        gate_runner: GateRunner,
        guardrail: FilePathGuardrail,
        options: RunOptions,
    ):
        """Initialize run engine.

        Args:
            config: Ralph configuration.
            prd: PRD data with tasks.
            session: Session manager.
            timeline: Timeline logger.
            execution_logger: Human-readable execution logger.
            claude_runner: Claude CLI runner.
            gate_runner: Gate execution runner.
            guardrail: Test path guardrail.
            options: Run options.
        """
        self.config = config
        self.prd = prd
        self.session = session
        self.timeline = timeline
        self.exec_log = execution_logger
        self.claude = claude_runner
        self.gates = gate_runner
        self.guardrail = guardrail
        self.options = options

        # Create the underlying orchestration service
        self._service = OrchestrationService(
            config=config,
            prd=prd,
            session=session,
            timeline=timeline,
            execution_logger=execution_logger,
            claude_runner=claude_runner,
            gate_runner=gate_runner,
            guardrail=guardrail,
            options=options.to_orchestration_options(),
        )

        # Register CLI event handlers for printing
        self._register_cli_handlers()

        # Load AGENTS.md if it exists (for backward compat)
        self.agents_md_content = ""
        agents_md_path = config.repo_root / "AGENTS.md"
        if agents_md_path.exists():
            try:
                self.agents_md_content = agents_md_path.read_text(encoding="utf-8")
            except Exception:
                pass

    def _register_cli_handlers(self) -> None:
        """Register event handlers for CLI output."""
        self._service.on_event(ServiceEventType.TASK_STARTED, self._on_task_started)
        self._service.on_event(ServiceEventType.TASK_COMPLETED, self._on_task_completed)
        self._service.on_event(ServiceEventType.AGENT_PHASE_CHANGED, self._on_agent_phase_changed)
        self._service.on_event(ServiceEventType.GATE_COMPLETED, self._on_gate_completed)

    def _on_task_started(self, event: TaskStartedEvent) -> None:
        """Handle task started event for CLI output."""
        self._print(f"\n[{event.task_id}] {event.task_title}")
        self._print("-" * 60)

    def _on_task_completed(self, event: TaskCompletedEvent) -> None:
        """Handle task completed event for CLI output."""
        if event.success:
            self._print(f"  ✓ Task complete")
        else:
            self._print(f"  ✗ Task failed: {event.failure_reason}")

    def _on_agent_phase_changed(self, event: AgentPhaseChangedEvent) -> None:
        """Handle agent phase change event for CLI output."""
        phase_names = {
            "implementation": "Implementation agent",
            "test_writing": "Test-writing agent",
            "review": "Review agent",
            "fix": "Fix agent",
        }
        phase_name = phase_names.get(event.phase, event.phase)
        self._print(f"  ▶ {phase_name} starting...")

    def _on_gate_completed(self, event: GateCompletedEvent) -> None:
        """Handle gate completed event for CLI output."""
        if event.passed:
            self._print(f"    ✓ {event.gate_name} ({event.duration_ms / 1000:.1f}s)")
        else:
            self._print(f"    ✗ {event.gate_name} (failed)")

    @property
    def _session_token(self) -> str:
        """Get session token, raising if not available."""
        token = self.session.session_token
        if not token:
            raise RuntimeError("Session token not available - session not initialized")
        return token

    def _print(self, msg: str, end: str = "\n") -> None:
        """Print message to stdout."""
        print(msg, end=end, file=sys.stdout, flush=True)

    def _print_task_header(self, task: Task) -> None:
        """Print task header."""
        self._print(f"\n[{task.id}] {task.title}")
        self._print("-" * 60)

    def _create_task_context(
        self,
        task: Task,
        previous_feedback: Optional[str] = None,
        gate_output: Optional[str] = None,
        review_feedback: Optional[str] = None,
    ) -> TaskContext:
        """Create task context for prompts."""
        return TaskContext(
            task_id=task.id,
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            notes=task.notes,
            previous_feedback=previous_feedback,
            gate_output=gate_output,
            review_feedback=review_feedback,
        )

    def run(self) -> RunResult:
        """Execute the verified task loop.

        Returns:
            RunResult with overall outcome.
        """
        # Get pending tasks to print header info
        pending_tasks = self._service.get_pending_tasks()

        if not pending_tasks:
            self._print("No pending tasks to execute.")
            return RunResult(
                exit_code=ExitCode.SUCCESS,
                session_id=self.session.session_id,
            )

        # Print header
        self._print("=" * 60)
        self._print("  RALPH VERIFIED EXECUTION")
        self._print(f"  Session: {self.session.session_id}")
        self._print(f"  Tasks: {len(pending_tasks)} pending")
        self._print("=" * 60)

        # Dry run - just show what would run
        if self.options.dry_run:
            self._print("\nDry run mode - tasks that would execute:")
            for task in pending_tasks[:10]:
                self._print(f"  - {task.id}: {task.title} (priority {task.priority})")
            if len(pending_tasks) > 10:
                self._print(f"  ... and {len(pending_tasks) - 10} more")
            return RunResult(
                exit_code=ExitCode.SUCCESS,
                tasks_pending=len(pending_tasks),
                session_id=self.session.session_id,
            )

        # Run the orchestration service
        orchestration_result = self._service.run()

        # Print summary
        self._print_summary(orchestration_result, pending_tasks)

        # Convert to RunResult
        return RunResult.from_orchestration_result(orchestration_result)

    def _print_summary(self, result: OrchestrationResult, pending_tasks: list) -> None:
        """Print execution summary."""
        self._print("\n" + "=" * 60)
        self._print("  SUMMARY")
        self._print("=" * 60)
        self._print(f"  Tasks: {result.tasks_completed}/{len(pending_tasks)} completed")
        self._print(f"  Duration: {result.total_duration_ms // 1000 // 60}m {(result.total_duration_ms // 1000) % 60}s")
        self._print(f"  Session logs: {self.session.logs_dir}")
        self._print("=" * 60)

    # Expose the underlying service for direct access
    @property
    def service(self) -> OrchestrationService:
        """Get the underlying OrchestrationService for event registration."""
        return self._service

    def on_event(self, event_type: ServiceEventType, handler) -> None:
        """Register an event handler (delegates to service)."""
        self._service.on_event(event_type, handler)

    def on_all_events(self, handler) -> None:
        """Register a handler for all events (delegates to service)."""
        self._service.on_all_events(handler)


def run_tasks(
    config_path: Optional[Path] = None,
    prd_path: Optional[Path] = None,
    options: Optional[RunOptions] = None,
) -> RunResult:
    """Main entry point for running tasks.
    
    Args:
        config_path: Path to ralph.yml configuration.
        prd_path: Path to prd.json (overrides config).
        options: Run options.
        
    Returns:
        RunResult with execution outcome.
    """
    options = options or RunOptions()
    
    # Load configuration
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        return RunResult(
            exit_code=ExitCode.CONFIG_ERROR,
            error=str(e),
        )
    
    # Determine PRD path
    if prd_path is None:
        if options.prd_json:
            prd_path = Path(options.prd_json)
        else:
            prd_path = config.task_source_resolved
    
    # Load PRD
    try:
        prd = load_prd(prd_path)
    except (FileNotFoundError, ValueError) as e:
        return RunResult(
            exit_code=ExitCode.TASK_SOURCE_ERROR,
            error=str(e),
        )
    
    # Setup session
    pending_task_ids = [t.id for t in prd.get_pending_tasks()]
    
    if options.resume:
        try:
            session = load_session(repo_root=config.repo_root)
        except FileNotFoundError:
            session = create_session(
                task_source=str(prd_path),
                task_source_type=config.task_source_type,
                config_path=str(config.path),
                pending_tasks=pending_task_ids,
                repo_root=config.repo_root,
            )
    else:
        session = create_session(
            task_source=str(prd_path),
            task_source_type=config.task_source_type,
            config_path=str(config.path),
            pending_tasks=pending_task_ids,
            repo_root=config.repo_root,
        )
    
    # Setup components
    timeline = create_timeline_logger(session.session_dir, session.session_id)
    execution_logger = create_execution_logger(
        session.session_dir,
        session_id=session.session_id,
        prd_path=str(prd_path),
    )
    claude_runner = create_claude_runner(config, session.logs_dir, timeline, config.repo_root)
    gate_runner = create_gate_runner(config, config.repo_root, session.logs_dir, timeline)
    guardrail = create_guardrail(config.test_paths, config.repo_root, timeline)
    
    # Create and run engine
    engine = RunEngine(
        config=config,
        prd=prd,
        session=session,
        timeline=timeline,
        execution_logger=execution_logger,
        claude_runner=claude_runner,
        gate_runner=gate_runner,
        guardrail=guardrail,
        options=options,
    )
    
    return engine.run()
