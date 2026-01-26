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


class ExitCode(int, Enum):
    """Exit codes for ralph run."""
    SUCCESS = 0
    CONFIG_ERROR = 1
    TASK_SOURCE_ERROR = 2
    TASK_EXECUTION_FAILED = 3
    GATE_FAILURE = 4
    POST_VERIFICATION_FAILED = 5
    CHECKSUM_TAMPERING = 6
    USER_ABORT = 7
    CLAUDE_ERROR = 8
    SERVICE_FAILURE = 9


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


@dataclass
class TaskRunResult:
    """Result of running a single task."""
    task_id: str
    completed: bool
    iterations: int
    duration_ms: int
    failure_reason: Optional[str] = None


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


class RunEngine:
    """Main execution engine for the verified task loop."""
    
    def __init__(
        self,
        config: RalphConfig,
        prd: PRDData,
        session: Session,
        timeline: TimelineLogger,
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
            claude_runner: Claude CLI runner.
            gate_runner: Gate execution runner.
            guardrail: Test path guardrail.
            options: Run options.
        """
        self.config = config
        self.prd = prd
        self.session = session
        self.timeline = timeline
        self.claude = claude_runner
        self.gates = gate_runner
        self.guardrail = guardrail
        self.options = options
        
        # Load AGENTS.md if it exists
        self.agents_md_content = ""
        agents_md_path = config.repo_root / "AGENTS.md"
        if agents_md_path.exists():
            try:
                self.agents_md_content = agents_md_path.read_text(encoding="utf-8")
            except Exception:
                pass
    
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
    
    def _run_implementation(
        self,
        task: Task,
        feedback: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Run implementation agent.
        
        Returns:
            Tuple of (success, output, error_feedback).
        """
        self._print("  ▶ Implementation agent starting...")
        
        context = self._create_task_context(task, previous_feedback=feedback)
        prompt = build_implementation_prompt(
            task=context,
            session_token=self.session.session_token,
            project_description=self.prd.description,
            agents_md_content=self.agents_md_content,
        )
        
        agent_config = self.config.get_agent_config("implementation")
        result = self.claude.invoke(
            prompt=prompt,
            role="implementation",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.IMPLEMENTATION),
            timeout=agent_config.timeout,
        )
        
        if not result.success:
            return False, result.output, f"Claude CLI error: {result.error}"
        
        # Validate signal
        validation = validate_implementation_signal(result.output, self.session.session_token)
        
        if not validation.valid:
            if validation.received_token and validation.received_token != validation.expected_token:
                feedback = get_feedback_for_invalid_token(
                    "implementation",
                    validation.expected_token,
                    validation.received_token,
                )
            else:
                feedback = get_feedback_for_missing_signal(
                    "implementation",
                    self.session.session_token,
                )
            return False, result.output, feedback
        
        self._print(f"  ✓ Implementation complete ({result.duration_ms // 1000}s)")
        return True, result.output, None
    
    def _run_test_writing(
        self,
        task: Task,
    ) -> Tuple[bool, str, Optional[str]]:
        """Run test-writing agent with guardrails.
        
        Returns:
            Tuple of (success, output, error_feedback).
        """
        self._print("  ▶ Test-writing agent starting...")
        
        # Snapshot git state before
        before_snapshot = self.guardrail.snapshot_state()
        
        context = self._create_task_context(task)
        prompt = build_test_writing_prompt(
            task=context,
            session_token=self.session.session_token,
            test_paths=self.config.test_paths,
            project_description=self.prd.description,
        )
        
        agent_config = self.config.get_agent_config("test_writing")
        result = self.claude.invoke(
            prompt=prompt,
            role="test_writing",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.TEST_WRITING),
            timeout=agent_config.timeout,
        )
        
        # Check guardrails
        guardrail_result = self.guardrail.check_and_revert(before_snapshot, task_id=task.id)
        if not guardrail_result.passed:
            self._print(f"  ⚠ Guardrail violation: {len(guardrail_result.violations)} files reverted")
        
        if not result.success:
            return False, result.output, f"Claude CLI error: {result.error}"
        
        # Validate signal
        validation = validate_test_writing_signal(result.output, self.session.session_token)
        
        if not validation.valid:
            feedback = get_feedback_for_missing_signal(
                "test_writing",
                self.session.session_token,
            )
            return False, result.output, feedback
        
        self._print(f"  ✓ Tests written ({result.duration_ms // 1000}s)")
        return True, result.output, None
    
    def _run_gates(
        self,
        task: Task,
    ) -> Tuple[bool, Optional[str]]:
        """Run quality gates.
        
        Returns:
            Tuple of (success, failure_output).
        """
        gate_type = self.options.gate_type
        if gate_type == "none":
            return True, None
        
        self._print(f"  ▶ Running gates ({gate_type})...")
        
        result = self.gates.run_gates(gate_type=gate_type, task_id=task.id)
        
        for gate_result in result.results:
            if gate_result.skipped:
                continue
            elif gate_result.passed:
                self._print(f"    ✓ {gate_result.name} ({gate_result.duration_ms / 1000:.1f}s)")
            else:
                self._print(f"    ✗ {gate_result.name} (failed)")
        
        if not result.passed:
            failure_output = format_gate_failure(result.fatal_failure)
            return False, failure_output
        
        return True, None
    
    def _run_review(
        self,
        task: Task,
    ) -> Tuple[bool, bool, str, Optional[str]]:
        """Run review agent.
        
        Returns:
            Tuple of (signal_valid, is_approved, output, rejection_feedback).
        """
        self._print("  ▶ Review agent starting...")
        
        context = self._create_task_context(task)
        prompt = build_review_prompt(
            task=context,
            session_token=self.session.session_token,
            project_description=self.prd.description,
        )
        
        agent_config = self.config.get_agent_config("review")
        result = self.claude.invoke(
            prompt=prompt,
            role="review",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.REVIEW),
            timeout=agent_config.timeout,
        )
        
        if not result.success:
            return False, False, result.output, f"Claude CLI error: {result.error}"
        
        # Validate review signal
        validation, is_approved = validate_review_signal(result.output, self.session.session_token)
        
        if not validation.valid:
            feedback = get_feedback_for_missing_signal(
                "review",
                self.session.session_token,
            )
            return False, False, result.output, feedback
        
        if is_approved:
            self._print(f"  ✓ Review approved ({result.duration_ms // 1000}s)")
            return True, True, result.output, None
        else:
            self._print(f"  ✗ Review rejected ({result.duration_ms // 1000}s)")
            # Extract rejection feedback from signal content
            rejection_feedback = validation.signal.content if validation.signal else "Review rejected"
            return True, False, result.output, rejection_feedback
    
    def _run_task(self, task: Task) -> TaskRunResult:
        """Run a single task through the verified loop.
        
        Returns:
            TaskRunResult with completion status.
        """
        self._print_task_header(task)
        start_time = time.time()
        
        # Start task in session
        self.session.start_task(task.id)
        self.timeline.task_start(task.id, task.title)
        
        iteration = 0
        feedback = None
        gate_output = None
        review_feedback = None
        
        while iteration < self.options.max_iterations:
            iteration += 1
            self.session.increment_iterations(task.id)
            
            # Step 1: Implementation
            impl_success, impl_output, impl_feedback = self._run_implementation(
                task,
                feedback=feedback or review_feedback,
            )
            if not impl_success:
                feedback = impl_feedback
                continue
            
            # Step 2: Test writing
            test_success, test_output, test_feedback = self._run_test_writing(task)
            if not test_success:
                feedback = test_feedback
                continue
            
            # Step 3: Gates
            gates_success, gate_failure_output = self._run_gates(task)
            if not gates_success:
                gate_output = gate_failure_output
                feedback = f"Gates failed:\n{gate_failure_output}"
                continue
            
            # Step 4: Review
            review_valid, is_approved, review_output, rejection_feedback = self._run_review(task)
            if not review_valid:
                feedback = rejection_feedback
                continue
            
            if not is_approved:
                review_feedback = rejection_feedback
                feedback = None  # Will use review_feedback in next iteration
                continue
            
            # Task complete!
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Update prd.json and session
            mark_task_complete(self.prd, task.id)
            self.session.complete_task(task.id)
            self.timeline.task_complete(task.id, iterations=iteration, duration_ms=duration_ms)
            
            self._print(f"  ✓ Task complete")
            
            return TaskRunResult(
                task_id=task.id,
                completed=True,
                iterations=iteration,
                duration_ms=duration_ms,
            )
        
        # Max iterations reached
        duration_ms = int((time.time() - start_time) * 1000)
        failure_reason = f"Max iterations ({self.options.max_iterations}) reached"
        
        self.session.fail_task(task.id, failure_reason)
        self.timeline.task_failed(task.id, failure_reason, iterations=iteration)
        
        self._print(f"  ✗ Task failed: {failure_reason}")
        
        return TaskRunResult(
            task_id=task.id,
            completed=False,
            iterations=iteration,
            duration_ms=duration_ms,
            failure_reason=failure_reason,
        )
    
    def run(self) -> RunResult:
        """Execute the verified task loop.
        
        Returns:
            RunResult with overall outcome.
        """
        start_time = time.time()
        
        # Get pending tasks
        try:
            pending_tasks = get_pending_tasks(
                self.prd,
                task_id=self.options.task_id,
                from_task_id=self.options.from_task_id,
            )
        except ValueError as e:
            return RunResult(
                exit_code=ExitCode.TASK_SOURCE_ERROR,
                error=str(e),
            )
        
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
        
        # Log session start
        self.timeline.session_start(
            task_count=len(pending_tasks),
            config_path=str(self.config.path),
        )
        
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
        
        # Execute tasks
        task_results = []
        tasks_completed = 0
        tasks_failed = 0
        
        for task in pending_tasks:
            try:
                result = self._run_task(task)
                task_results.append(result)
                
                if result.completed:
                    tasks_completed += 1
                else:
                    tasks_failed += 1
                    # Stop on first failure unless configured otherwise
                    break
                    
            except TamperingDetectedError as e:
                self._print(f"\n⚠ CHECKSUM TAMPERING DETECTED: {e}")
                self.session.end_session("failed", str(e))
                return RunResult(
                    exit_code=ExitCode.CHECKSUM_TAMPERING,
                    tasks_completed=tasks_completed,
                    tasks_failed=tasks_failed + 1,
                    task_results=task_results,
                    error=str(e),
                    session_id=self.session.session_id,
                )
            except KeyboardInterrupt:
                self._print("\n\n⚠ Aborted by user")
                self.session.end_session("aborted")
                return RunResult(
                    exit_code=ExitCode.USER_ABORT,
                    tasks_completed=tasks_completed,
                    task_results=task_results,
                    session_id=self.session.session_id,
                )
        
        # Calculate totals
        task_duration_ms = int((time.time() - start_time) * 1000)
        tasks_pending = len(pending_tasks) - tasks_completed - tasks_failed
        
        # Run post-verification if enabled and all tasks completed
        post_verify_result = None
        if self.options.post_verify and tasks_failed == 0 and tasks_completed > 0:
            self._print("\n" + "=" * 60)
            self._print("  POST-COMPLETION VERIFICATION")
            self._print("=" * 60)
            
            from .verify import run_post_verify, VerifyOptions
            
            verify_options = VerifyOptions(
                gate_type=self.options.gate_type,
                env="dev",
                fix=True,  # Enable fix loops in post-verify
                fix_iterations=self.config.limits.ui_fix_iterations,
            )
            
            post_verify_result = run_post_verify(
                config=self.config,
                session=self.session,
                timeline=self.timeline,
                options=verify_options,
            )
            
            if not post_verify_result.all_passed:
                tasks_failed = 1  # Mark as failed
        
        total_duration_ms = int((time.time() - start_time) * 1000)
        
        # End session
        final_status = "completed" if tasks_failed == 0 else "failed"
        self.session.end_session(final_status)
        self.timeline.session_end(
            status=final_status,
            completed_count=tasks_completed,
            total_count=len(pending_tasks),
            duration_ms=total_duration_ms,
        )
        
        # Print summary
        self._print("\n" + "=" * 60)
        self._print("  SUMMARY")
        self._print("=" * 60)
        self._print(f"  Tasks: {tasks_completed}/{len(pending_tasks)} completed")
        if post_verify_result:
            if post_verify_result.gates_result:
                g = post_verify_result.gates_result
                self._print(f"  Gates: {g.passed_count}/{len(g.results)} passed")
            if post_verify_result.agent_browser_result:
                ab = post_verify_result.agent_browser_result
                self._print(f"  UI Tests: {ab.passed_count}/{len(ab.results)} passed")
            if post_verify_result.robot_result:
                r = post_verify_result.robot_result
                self._print(f"  Robot Tests: {r.passed_count}/{len(r.results)} passed")
        self._print(f"  Duration: {total_duration_ms // 1000 // 60}m {(total_duration_ms // 1000) % 60}s")
        self._print(f"  Session logs: {self.session.logs_dir}")
        self._print("=" * 60)
        
        # Determine exit code
        if tasks_failed > 0 and not post_verify_result:
            exit_code = ExitCode.TASK_EXECUTION_FAILED
        elif post_verify_result and not post_verify_result.all_passed:
            exit_code = ExitCode.POST_VERIFICATION_FAILED
        else:
            exit_code = ExitCode.SUCCESS
        
        return RunResult(
            exit_code=exit_code,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            tasks_pending=tasks_pending,
            total_duration_ms=total_duration_ms,
            task_results=task_results,
            session_id=self.session.session_id,
        )


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
    claude_runner = create_claude_runner(config, session.logs_dir, timeline, config.repo_root)
    gate_runner = create_gate_runner(config, config.repo_root, session.logs_dir, timeline)
    guardrail = create_guardrail(config.test_paths, config.repo_root, timeline)
    
    # Create and run engine
    engine = RunEngine(
        config=config,
        prd=prd,
        session=session,
        timeline=timeline,
        claude_runner=claude_runner,
        gate_runner=gate_runner,
        guardrail=guardrail,
        options=options,
    )
    
    return engine.run()
