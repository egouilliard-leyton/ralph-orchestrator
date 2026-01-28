"""CLI-agnostic orchestration service for Ralph.

This module provides the core task execution logic extracted from run.py,
designed to be interface-independent (no Click/CLI dependencies) and to
emit events at key execution points for monitoring by CLI or web UI.

Events emitted:
- task_started: When a task begins execution
- task_completed: When a task finishes (success or failure)
- agent_phase_changed: When transitioning between agent phases
- gate_running: When a quality gate starts running
- gate_completed: When a quality gate finishes
- signal_detected: When an agent completion signal is detected
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any, Protocol


class EventType(str, Enum):
    """Types of events emitted by the orchestration service."""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    AGENT_PHASE_CHANGED = "agent_phase_changed"
    GATE_RUNNING = "gate_running"
    GATE_COMPLETED = "gate_completed"
    SIGNAL_DETECTED = "signal_detected"
    ITERATION_STARTED = "iteration_started"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"


@dataclass
class OrchestrationEvent:
    """Base class for orchestration events."""
    event_type: EventType
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
        }


@dataclass
class TaskStartedEvent(OrchestrationEvent):
    """Event emitted when a task begins execution."""
    event_type: EventType = field(init=False, default=EventType.TASK_STARTED)
    task_id: str = ""
    task_title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "task_title": self.task_title,
        })
        return d


@dataclass
class TaskCompletedEvent(OrchestrationEvent):
    """Event emitted when a task finishes execution."""
    event_type: EventType = field(init=False, default=EventType.TASK_COMPLETED)
    task_id: str = ""
    success: bool = False
    iterations: int = 0
    duration_ms: int = 0
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "success": self.success,
            "iterations": self.iterations,
            "duration_ms": self.duration_ms,
            "failure_reason": self.failure_reason,
        })
        return d


@dataclass
class AgentPhaseChangedEvent(OrchestrationEvent):
    """Event emitted when transitioning between agent phases."""
    event_type: EventType = field(init=False, default=EventType.AGENT_PHASE_CHANGED)
    task_id: str = ""
    phase: str = ""  # "implementation", "test_writing", "review", "fix"
    previous_phase: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "phase": self.phase,
            "previous_phase": self.previous_phase,
        })
        return d


@dataclass
class GateRunningEvent(OrchestrationEvent):
    """Event emitted when a quality gate starts running."""
    event_type: EventType = field(init=False, default=EventType.GATE_RUNNING)
    task_id: str = ""
    gate_name: str = ""
    gate_type: str = ""  # "build" or "full"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "gate_name": self.gate_name,
            "gate_type": self.gate_type,
        })
        return d


@dataclass
class GateCompletedEvent(OrchestrationEvent):
    """Event emitted when a quality gate finishes."""
    event_type: EventType = field(init=False, default=EventType.GATE_COMPLETED)
    task_id: str = ""
    gate_name: str = ""
    gate_type: str = ""
    passed: bool = False
    duration_ms: int = 0
    output: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "gate_name": self.gate_name,
            "gate_type": self.gate_type,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "output": self.output,
        })
        return d


@dataclass
class SignalDetectedEvent(OrchestrationEvent):
    """Event emitted when an agent completion signal is detected."""
    event_type: EventType = field(init=False, default=EventType.SIGNAL_DETECTED)
    task_id: str = ""
    signal_type: str = ""  # "task-done", "tests-done", "review-approved", "review-rejected", "fix-done"
    valid: bool = False
    token_valid: bool = False
    agent_role: str = ""
    content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "signal_type": self.signal_type,
            "valid": self.valid,
            "token_valid": self.token_valid,
            "agent_role": self.agent_role,
            "content": self.content,
        })
        return d


@dataclass
class IterationStartedEvent(OrchestrationEvent):
    """Event emitted when a new iteration starts."""
    event_type: EventType = field(init=False, default=EventType.ITERATION_STARTED)
    task_id: str = ""
    iteration: int = 0
    max_iterations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "task_id": self.task_id,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
        })
        return d


@dataclass
class SessionStartedEvent(OrchestrationEvent):
    """Event emitted when a session starts."""
    event_type: EventType = field(init=False, default=EventType.SESSION_STARTED)
    session_id: str = ""
    task_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "session_id": self.session_id,
            "task_count": self.task_count,
        })
        return d


@dataclass
class SessionEndedEvent(OrchestrationEvent):
    """Event emitted when a session ends."""
    event_type: EventType = field(init=False, default=EventType.SESSION_ENDED)
    session_id: str = ""
    status: str = ""  # "completed", "failed", "aborted"
    tasks_completed: int = 0
    tasks_failed: int = 0
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "session_id": self.session_id,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "duration_ms": self.duration_ms,
        })
        return d


# Type alias for event handlers - uses Any to allow handlers for specific event subtypes
# This allows both Callable[[OrchestrationEvent], None] and Callable[[TaskStartedEvent], None]
EventHandler = Callable[[Any], None]


@dataclass
class OrchestrationOptions:
    """Options for the orchestration service."""
    prd_json: Optional[str] = None
    task_id: Optional[str] = None
    from_task_id: Optional[str] = None
    max_iterations: int = 200
    gate_type: str = "full"
    dry_run: bool = False
    resume: bool = False
    post_verify: bool = True
    with_smoke: Optional[bool] = None  # None = use config/task defaults
    with_robot: Optional[bool] = None  # None = use config/task defaults


@dataclass
class TaskRunResult:
    """Result of running a single task."""
    task_id: str
    completed: bool
    iterations: int
    duration_ms: int
    failure_reason: Optional[str] = None


class ExitCode(int, Enum):
    """Exit codes for orchestration."""
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
class OrchestrationResult:
    """Result of the full orchestration run."""
    exit_code: ExitCode
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_pending: int = 0
    total_duration_ms: int = 0
    task_results: List[TaskRunResult] = field(default_factory=list)
    error: Optional[str] = None
    session_id: Optional[str] = None


class OrchestrationService:
    """CLI-agnostic orchestration service for running verified task loops.

    This service encapsulates all the core task execution logic, emitting
    events at key points for monitoring by any interface (CLI, web UI, etc.).

    Usage:
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
        service.on_event(EventType.TASK_STARTED, my_handler)
        service.on_event(EventType.GATE_COMPLETED, my_gate_handler)

        # Run the orchestration
        result = service.run()
    """

    def __init__(
        self,
        config,  # RalphConfig
        prd,  # PRDData
        session,  # Session
        timeline,  # TimelineLogger
        execution_logger,  # ExecutionLogger
        claude_runner,  # ClaudeRunner
        gate_runner,  # GateRunner
        guardrail,  # FilePathGuardrail
        options: OrchestrationOptions,
    ):
        """Initialize orchestration service.

        Args:
            config: Ralph configuration.
            prd: PRD data with tasks.
            session: Session manager.
            timeline: Timeline logger.
            execution_logger: Human-readable execution logger.
            claude_runner: Claude CLI runner.
            gate_runner: Gate execution runner.
            guardrail: Test path guardrail.
            options: Orchestration options.
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

        # Event handlers registry
        self._event_handlers: Dict[EventType, List[EventHandler]] = {
            event_type: [] for event_type in EventType
        }

        # All-events handlers
        self._global_handlers: List[EventHandler] = []

        # Load AGENTS.md if it exists
        self.agents_md_content = ""
        agents_md_path = config.repo_root / "AGENTS.md"
        if agents_md_path.exists():
            try:
                self.agents_md_content = agents_md_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # Current phase tracking for events
        self._current_phase: Optional[str] = None

    def on_event(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an event handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: Callable that receives OrchestrationEvent.
        """
        self._event_handlers[event_type].append(handler)

    def on_all_events(self, handler: EventHandler) -> None:
        """Register a handler for all events.

        Args:
            handler: Callable that receives OrchestrationEvent.
        """
        self._global_handlers.append(handler)

    def remove_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove an event handler.

        Args:
            event_type: The type of event.
            handler: The handler to remove.
        """
        if handler in self._event_handlers[event_type]:
            self._event_handlers[event_type].remove(handler)

    def _emit_event(self, event: OrchestrationEvent) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: The event to emit.
        """
        # Call specific handlers
        for handler in self._event_handlers[event.event_type]:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors break orchestration

        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                pass

    @property
    def _session_token(self) -> str:
        """Get session token, raising if not available."""
        token = self.session.session_token
        if not token:
            raise RuntimeError("Session token not available - session not initialized")
        return token

    def _create_task_context(
        self,
        task,  # Task
        previous_feedback: Optional[str] = None,
        gate_output: Optional[str] = None,
        review_feedback: Optional[str] = None,
    ):
        """Create task context for prompts."""
        from ..agents.prompts import TaskContext

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
        task,  # Task
        feedback: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Run implementation agent.

        Returns:
            Tuple of (success, output, error_feedback).
        """
        from ..agents.prompts import (
            AgentRole,
            build_implementation_prompt,
            get_allowed_tools_for_role,
        )
        from ..signals import (
            validate_implementation_signal,
            get_feedback_for_missing_signal,
            get_feedback_for_invalid_token,
        )
        from ..skills import SkillRouter

        # Emit phase change event
        self._emit_event(AgentPhaseChangedEvent(
            task_id=task.id,
            phase="implementation",
            previous_phase=self._current_phase,
        ))
        self._current_phase = "implementation"

        # Detect skill for this task
        router = SkillRouter.from_config(self.config)
        skill = router.detect_skill(task)

        # Get report path for this agent/task
        report_path = str(self.session.get_report_path("implementation", task.id))

        agent_config = self.config.get_agent_config("implementation")

        # Log agent start with skill info
        self.exec_log.agent_start(
            role="implementation",
            model=agent_config.model,
            previous_feedback=feedback,
        )

        # Log skill detection
        if skill:
            self.exec_log.custom(f"[SKILL] Using /{skill.skill_name} for task {task.id} ({skill.reason})")

        context = self._create_task_context(task, previous_feedback=feedback)
        base_prompt = build_implementation_prompt(
            task=context,
            session_token=self._session_token,
            project_description=self.prd.description,
            agents_md_content=self.agents_md_content,
            report_path=report_path,
        )

        # Add skill prefix if detected
        if skill:
            prompt = router.get_skill_prompt_prefix(skill) + base_prompt
        else:
            prompt = base_prompt

        result = self.claude.invoke(
            prompt=prompt,
            role="implementation",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.IMPLEMENTATION),
            timeout=agent_config.timeout,
        )

        # Log command used (for debugging) - stop at -p to exclude the prompt
        if result.command:
            cmd_parts = []
            for part in result.command:
                if part == "-p":
                    break
                cmd_parts.append(part)
            self.exec_log.custom(f"  Command: {' '.join(cmd_parts)}")

        duration_seconds = result.duration_ms // 1000

        if not result.success:
            self.exec_log.agent_failed(
                role="implementation",
                error=result.error or "Unknown error",
                duration_seconds=duration_seconds,
            )
            return False, result.output, f"Claude CLI error: {result.error}"

        # Validate signal
        validation = validate_implementation_signal(result.output, self._session_token)

        # Emit signal detected event
        self._emit_event(SignalDetectedEvent(
            task_id=task.id,
            signal_type="task-done" if validation.signal else "none",
            valid=validation.valid,
            token_valid=validation.received_token == validation.expected_token if validation.received_token else False,
            agent_role="implementation",
            content=validation.signal.content if validation.signal else None,
        ))

        # Log signal validation details
        self.exec_log.signal_validation(
            role="implementation",
            signal_found=validation.signal is not None,
            expected_token=validation.expected_token or self._session_token or "",
            received_token=validation.received_token,
        )

        if not validation.valid:
            self.exec_log.agent_complete(
                role="implementation",
                duration_seconds=duration_seconds,
                signal_found=validation.signal is not None,
                token_valid=False,
            )

            expected_token = validation.expected_token or self._session_token
            if validation.received_token and validation.received_token != expected_token:
                error_feedback = get_feedback_for_invalid_token(
                    "implementation",
                    expected_token,
                    validation.received_token,
                )
            else:
                error_feedback = get_feedback_for_missing_signal(
                    "implementation",
                    self._session_token,
                )

            self.exec_log.feedback_set(error_feedback, source="signal validation")
            return False, result.output, error_feedback

        # Log successful completion
        self.exec_log.agent_complete(
            role="implementation",
            duration_seconds=duration_seconds,
            signal_found=True,
            token_valid=True,
        )

        # Log agent output
        self.exec_log.agent_output("implementation", result.output, max_lines=20)

        return True, result.output, None

    def _run_test_writing(
        self,
        task,  # Task
    ) -> Tuple[bool, str, Optional[str]]:
        """Run test-writing agent with guardrails.

        Returns:
            Tuple of (success, output, error_feedback).
        """
        from ..agents.prompts import (
            AgentRole,
            build_test_writing_prompt,
            get_allowed_tools_for_role,
        )
        from ..signals import (
            validate_test_writing_signal,
            get_feedback_for_missing_signal,
        )

        # Emit phase change event
        self._emit_event(AgentPhaseChangedEvent(
            task_id=task.id,
            phase="test_writing",
            previous_phase=self._current_phase,
        ))
        self._current_phase = "test_writing"

        # Snapshot git state before
        before_snapshot = self.guardrail.snapshot_state()

        # Get report path for this agent/task
        report_path = str(self.session.get_report_path("test_writing", task.id))

        agent_config = self.config.get_agent_config("test_writing")

        # Log agent start with allowed paths
        self.exec_log.agent_start(
            role="test_writing",
            model=agent_config.model,
            allowed_paths=self.config.test_paths,
        )

        context = self._create_task_context(task)
        prompt = build_test_writing_prompt(
            task=context,
            session_token=self._session_token,
            test_paths=self.config.test_paths,
            project_description=self.prd.description,
            report_path=report_path,
        )

        result = self.claude.invoke(
            prompt=prompt,
            role="test_writing",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.TEST_WRITING),
            timeout=agent_config.timeout,
        )

        duration_seconds = result.duration_ms // 1000

        # Check guardrails
        guardrail_result = self.guardrail.check_and_revert(before_snapshot, task_id=task.id)
        guardrail_violations = len(guardrail_result.violations) if not guardrail_result.passed else 0

        if not result.success:
            self.exec_log.agent_failed(
                role="test_writing",
                error=result.error or "Unknown error",
                duration_seconds=duration_seconds,
            )
            return False, result.output, f"Claude CLI error: {result.error}"

        # Validate signal
        validation = validate_test_writing_signal(result.output, self._session_token)

        # Emit signal detected event
        self._emit_event(SignalDetectedEvent(
            task_id=task.id,
            signal_type="tests-done" if validation.signal else "none",
            valid=validation.valid,
            token_valid=validation.received_token == validation.expected_token if validation.received_token else False,
            agent_role="test_writing",
            content=validation.signal.content if validation.signal else None,
        ))

        # Log signal validation details
        self.exec_log.signal_validation(
            role="test_writing",
            signal_found=validation.signal is not None,
            expected_token=validation.expected_token or self._session_token or "",
            received_token=validation.received_token,
        )

        if not validation.valid:
            self.exec_log.agent_complete(
                role="test_writing",
                duration_seconds=duration_seconds,
                signal_found=validation.signal is not None,
                token_valid=False,
                guardrail_violations=guardrail_violations,
            )

            feedback = get_feedback_for_missing_signal(
                "test_writing",
                self._session_token,
            )
            self.exec_log.feedback_set(feedback, source="signal validation")
            return False, result.output, feedback

        # Log successful completion
        self.exec_log.agent_complete(
            role="test_writing",
            duration_seconds=duration_seconds,
            signal_found=True,
            token_valid=True,
            guardrail_violations=guardrail_violations,
        )

        # Log agent output
        self.exec_log.agent_output("test_writing", result.output, max_lines=20)

        return True, result.output, None

    def _run_gates(
        self,
        task,  # Task
    ) -> Tuple[bool, Optional[str]]:
        """Run quality gates.

        Returns:
            Tuple of (success, failure_output).
        """
        from ..gates import format_gate_failure

        gate_type = self.options.gate_type
        if gate_type == "none":
            self.exec_log.custom("[GATES] Skipped (gate_type=none)")
            return True, None

        self.exec_log.gates_start(gate_type)

        result = self.gates.run_gates(gate_type=gate_type, task_id=task.id)

        for gate_result in result.results:
            # Emit gate running event
            self._emit_event(GateRunningEvent(
                task_id=task.id,
                gate_name=gate_result.name,
                gate_type=gate_type,
            ))

            # Emit gate completed event
            self._emit_event(GateCompletedEvent(
                task_id=task.id,
                gate_name=gate_result.name,
                gate_type=gate_type,
                passed=gate_result.passed,
                duration_ms=gate_result.duration_ms,
                output=gate_result.output if not gate_result.passed else None,
            ))

            if gate_result.skipped:
                continue
            elif gate_result.passed:
                self.exec_log.gate_result(
                    gate_name=gate_result.name,
                    passed=True,
                    duration_seconds=gate_result.duration_ms / 1000,
                )
            else:
                self.exec_log.gate_result(
                    gate_name=gate_result.name,
                    passed=False,
                    duration_seconds=gate_result.duration_ms / 1000,
                    output=gate_result.output,
                    exit_code=gate_result.exit_code,
                )

        if not result.passed:
            fatal_failure = result.fatal_failure
            failure_output = format_gate_failure(fatal_failure) if fatal_failure else "Gates failed"
            self.exec_log.gates_complete(passed=False, feedback=failure_output)
            return False, failure_output

        self.exec_log.gates_complete(passed=True)
        return True, None

    def _run_review(
        self,
        task,  # Task
    ) -> Tuple[bool, bool, str, Optional[str]]:
        """Run review agent.

        Returns:
            Tuple of (signal_valid, is_approved, output, rejection_feedback).
        """
        from ..agents.prompts import (
            AgentRole,
            build_review_prompt,
            get_allowed_tools_for_role,
        )
        from ..signals import (
            validate_review_signal,
            get_feedback_for_missing_signal,
        )

        # Emit phase change event
        self._emit_event(AgentPhaseChangedEvent(
            task_id=task.id,
            phase="review",
            previous_phase=self._current_phase,
        ))
        self._current_phase = "review"

        # Get report path for this agent/task
        report_path = str(self.session.get_report_path("review", task.id))

        agent_config = self.config.get_agent_config("review")

        # Log agent start
        self.exec_log.agent_start(
            role="review",
            model=agent_config.model,
        )

        context = self._create_task_context(task)
        prompt = build_review_prompt(
            task=context,
            session_token=self._session_token,
            project_description=self.prd.description,
            report_path=report_path,
        )

        result = self.claude.invoke(
            prompt=prompt,
            role="review",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.REVIEW),
            timeout=agent_config.timeout,
        )

        duration_seconds = result.duration_ms // 1000

        if not result.success:
            self.exec_log.agent_failed(
                role="review",
                error=result.error or "Unknown error",
                duration_seconds=duration_seconds,
            )
            return False, False, result.output, f"Claude CLI error: {result.error}"

        # Validate review signal
        validation, is_approved = validate_review_signal(result.output, self._session_token)

        # Emit signal detected event
        signal_type = "none"
        if validation.signal:
            signal_type = "review-approved" if is_approved else "review-rejected"

        self._emit_event(SignalDetectedEvent(
            task_id=task.id,
            signal_type=signal_type,
            valid=validation.valid,
            token_valid=validation.received_token == validation.expected_token if validation.received_token else False,
            agent_role="review",
            content=validation.signal.content if validation.signal else None,
        ))

        # Log signal validation details
        self.exec_log.signal_validation(
            role="review",
            signal_found=validation.signal is not None,
            expected_token=validation.expected_token or self._session_token or "",
            received_token=validation.received_token,
        )

        if not validation.valid:
            self.exec_log.agent_complete(
                role="review",
                duration_seconds=duration_seconds,
                signal_found=validation.signal is not None,
                token_valid=False,
            )

            feedback = get_feedback_for_missing_signal(
                "review",
                self._session_token,
            )
            self.exec_log.feedback_set(feedback, source="signal validation")
            return False, False, result.output, feedback

        # Log successful completion
        self.exec_log.agent_complete(
            role="review",
            duration_seconds=duration_seconds,
            signal_found=True,
            token_valid=True,
        )

        # Log agent output
        self.exec_log.agent_output("review", result.output, max_lines=20)

        if is_approved:
            self.exec_log.review_result(approved=True, duration_seconds=duration_seconds)
            return True, True, result.output, None
        else:
            # Extract rejection feedback from signal content
            rejection_feedback = validation.signal.content if validation.signal else "Review rejected"
            self.exec_log.review_result(
                approved=False,
                duration_seconds=duration_seconds,
                rejection_reason=rejection_feedback,
            )
            return True, False, result.output, rejection_feedback

    def _should_run_smoke_tests(self) -> bool:
        """Check if smoke tests (agent-browser) should run with CLI override.

        Returns:
            True if smoke tests should run.
        """
        from ..ui import is_agent_browser_enabled

        # CLI override takes precedence
        if self.options.with_smoke is False:
            return False
        if self.options.with_smoke is True:
            return True
        # Fall back to config
        return is_agent_browser_enabled(self.config)

    def _should_run_robot_tests(self) -> bool:
        """Check if Robot Framework tests should run with CLI override.

        Returns:
            True if Robot tests should run.
        """
        from ..ui import is_robot_enabled

        # CLI override takes precedence
        if self.options.with_robot is False:
            return False
        if self.options.with_robot is True:
            return True
        # Fall back to config
        return is_robot_enabled(self.config)

    def _should_run_ui_testing(self, task) -> bool:
        """Check if UI testing should run for this task.

        UI testing runs when:
        - Task has affects_frontend = True
        - Config has a frontend service configured
        - Smoke tests or Robot Framework tests are enabled (via CLI or config)

        Args:
            task: Task to check.

        Returns:
            True if UI testing should run.
        """
        # Task must affect frontend
        if not task.affects_frontend:
            return False

        # Must have frontend service configured
        if self.config.frontend is None:
            return False

        # Check CLI overrides and config for UI testing
        smoke_enabled = self._should_run_smoke_tests()
        robot_enabled = self._should_run_robot_tests()

        return smoke_enabled or robot_enabled

    def _get_ui_base_url(self) -> Optional[str]:
        """Get base URL for UI testing from config.
        
        Returns:
            Base URL string or None if not configured.
        """
        # Try to get from ui.browser_use.base_url
        ui_config = self.config.raw_data.get("ui", {})
        browser_use_config = ui_config.get("browser_use", {})
        base_url = browser_use_config.get("base_url")
        if base_url:
            return base_url
        
        # Fall back to frontend service port
        if self.config.frontend:
            port = self.config.frontend.port
            return f"http://localhost:{port}"
        
        return None

    def _get_robot_suite_path(self) -> str:
        """Get Robot Framework suite path from config.
        
        Returns:
            Suite path string, defaults to tests/robot.
        """
        ui_config = self.config.raw_data.get("ui", {})
        robot_config = ui_config.get("robot", {})
        return robot_config.get("suite", "tests/robot")

    def _run_ui_testing(
        self,
        task,  # Task
    ) -> Tuple[bool, str, Optional[str]]:
        """Run UI testing agent for browser exploration and Robot test generation.
        
        Args:
            task: Task being tested.
            
        Returns:
            Tuple of (success, output, error_feedback).
        """
        from ..agents.prompts import (
            AgentRole,
            build_ui_testing_prompt,
            get_allowed_tools_for_role,
        )
        from ..signals import (
            validate_ui_testing_signal,
            get_feedback_for_missing_signal,
            get_feedback_for_invalid_token,
        )

        # Emit phase change event
        self._emit_event(AgentPhaseChangedEvent(
            task_id=task.id,
            phase="ui_testing",
            previous_phase=self._current_phase,
        ))
        self._current_phase = "ui_testing"

        # Get base URL and suite path
        base_url = self._get_ui_base_url()
        if not base_url:
            return False, "", "No base URL configured for UI testing"
        
        robot_suite_path = self._get_robot_suite_path()

        # Get report path for this agent/task
        report_path = str(self.session.get_report_path("ui_testing", task.id))

        agent_config = self.config.get_agent_config("ui_testing")

        # Log agent start
        self.exec_log.agent_start(
            role="ui_testing",
            model=agent_config.model,
            allowed_paths=[robot_suite_path],
        )

        context = self._create_task_context(task)
        prompt = build_ui_testing_prompt(
            task=context,
            session_token=self._session_token,
            base_url=base_url,
            robot_suite_path=robot_suite_path,
            project_description=self.prd.description,
            report_path=report_path,
        )

        result = self.claude.invoke(
            prompt=prompt,
            role="ui_testing",
            task_id=task.id,
            model=agent_config.model,
            allowed_tools=agent_config.allowed_tools or get_allowed_tools_for_role(AgentRole.UI_TESTING),
            timeout=agent_config.timeout,
        )

        duration_seconds = result.duration_ms // 1000

        if not result.success:
            self.exec_log.agent_failed(
                role="ui_testing",
                error=result.error or "Unknown error",
                duration_seconds=duration_seconds,
            )
            return False, result.output, f"Claude CLI error: {result.error}"

        # Validate signal
        validation = validate_ui_testing_signal(result.output, self._session_token)

        # Emit signal detected event
        self._emit_event(SignalDetectedEvent(
            task_id=task.id,
            signal_type="ui-tests-done" if validation.signal else "none",
            valid=validation.valid,
            token_valid=validation.received_token == validation.expected_token if validation.received_token else False,
            agent_role="ui_testing",
            content=validation.signal.content if validation.signal else None,
        ))

        # Log signal validation details
        self.exec_log.signal_validation(
            role="ui_testing",
            signal_found=validation.signal is not None,
            expected_token=validation.expected_token or self._session_token or "",
            received_token=validation.received_token,
        )

        if not validation.valid:
            self.exec_log.agent_complete(
                role="ui_testing",
                duration_seconds=duration_seconds,
                signal_found=validation.signal is not None,
                token_valid=False,
            )

            expected_token = validation.expected_token or self._session_token
            if validation.received_token and validation.received_token != expected_token:
                error_feedback = get_feedback_for_invalid_token(
                    "ui_testing",
                    expected_token,
                    validation.received_token,
                )
            else:
                error_feedback = get_feedback_for_missing_signal(
                    "ui_testing",
                    self._session_token,
                )

            self.exec_log.feedback_set(error_feedback, source="signal validation")
            return False, result.output, error_feedback

        # Log successful completion
        self.exec_log.agent_complete(
            role="ui_testing",
            duration_seconds=duration_seconds,
            signal_found=True,
            token_valid=True,
        )

        # Log agent output
        self.exec_log.agent_output("ui_testing", result.output, max_lines=20)

        return True, result.output, None

    def _run_robot_tests(self, task) -> Tuple[bool, Optional[str]]:
        """Run Robot Framework tests after UI testing agent.

        Args:
            task: Task being tested.

        Returns:
            Tuple of (success, failure_output).
        """
        from ..ui import (
            create_robot_runner,
            format_ui_test_summary,
        )

        if not self._should_run_robot_tests():
            self.exec_log.custom("[ROBOT] Skipped (not enabled or disabled via CLI)")
            return True, None
        
        base_url = self._get_ui_base_url()
        if not base_url:
            return True, None  # Skip if no base URL
        
        self.exec_log.custom(f"[ROBOT] Running tests against {base_url}")
        
        runner = create_robot_runner(
            config=self.config,
            base_url=base_url,
            session_dir=self.session.session_dir,
            timeline=self.timeline,
        )
        
        result = runner.run()
        
        # Log summary
        summary = format_ui_test_summary(result)
        self.exec_log.custom(f"[ROBOT]\n{summary}")
        
        if result.passed:
            return True, None
        
        # Format failures for feedback
        failure_lines = ["Robot Framework tests failed:"]
        for test in result.get_failures():
            failure_lines.append(f"  - {test.name}: {test.error or 'Failed'}")
        
        return False, "\n".join(failure_lines)

    def _run_ui_testing_loop(self, task) -> bool:
        """Run UI testing loop with browser exploration and Robot test execution.
        
        This method:
        1. Runs the UI testing agent to explore frontend and generate Robot tests
        2. Executes Robot Framework tests
        3. If tests fail, runs UI fix agent and retries (up to ui_fix_iterations)
        
        Args:
            task: Task being tested.
            
        Returns:
            True if UI testing passed, False otherwise.
        """
        from ..ui import (
            create_robot_runner,
            is_robot_enabled,
            format_failure_description,
        )
        from ..agents.prompts import (
            AgentRole,
            build_ui_planning_prompt,
            build_ui_implementation_prompt,
            get_allowed_tools_for_role,
        )
        from ..signals import validate_ui_plan_signal, validate_ui_fix_signal

        max_iterations = self.config.limits.ui_fix_iterations
        
        self.exec_log.custom(f"[UI TESTING] Starting for task {task.id} (max {max_iterations} fix iterations)")
        
        for iteration in range(1, max_iterations + 1):
            self.exec_log.custom(f"[UI TESTING] Iteration {iteration}/{max_iterations}")
            
            # Step 1: Run UI testing agent for browser exploration and test generation
            ui_success, ui_output, ui_feedback = self._run_ui_testing(task)
            if not ui_success:
                self.exec_log.feedback_set(ui_feedback or "UI testing agent failed", source="ui_testing")
                # On first iteration, this is a fatal error
                if iteration == 1:
                    return False
                continue
            
            # Step 2: Run Robot Framework tests (if enabled)
            robot_success, robot_failure = self._run_robot_tests(task)
            
            if robot_success:
                self.exec_log.custom("[UI TESTING] All UI tests passed!")
                return True
            
            # Robot tests failed - run fix loop
            self.exec_log.custom(f"[UI TESTING] Robot tests failed: {robot_failure}")
            
            if iteration >= max_iterations:
                self.exec_log.custom(f"[UI TESTING] Max iterations reached, UI testing failed")
                break
            
            # Step 3: Run UI fix planning agent
            self.exec_log.custom("[UI TESTING] Running fix planning agent...")
            
            plan_prompt = build_ui_planning_prompt(
                failure_description=robot_failure or "Robot tests failed",
                session_token=self._session_token,
            )
            
            agent_config = self.config.get_agent_config("planning")
            plan_result = self.claude.invoke(
                prompt=plan_prompt,
                role="ui_planning",
                model=agent_config.model,
                allowed_tools=get_allowed_tools_for_role(AgentRole.UI_PLANNING),
                timeout=agent_config.timeout,
            )
            
            if not plan_result.success:
                self.exec_log.custom(f"[UI TESTING] Planning failed: {plan_result.error}")
                continue
            
            plan_validation = validate_ui_plan_signal(plan_result.output, self._session_token)
            if not plan_validation.valid:
                self.exec_log.custom("[UI TESTING] Planning agent did not provide valid signal")
                continue
            
            plan_content = plan_validation.signal.content if plan_validation.signal else plan_result.output
            
            # Step 4: Run UI fix implementation agent
            self.exec_log.custom("[UI TESTING] Running fix implementation agent...")
            
            impl_prompt = build_ui_implementation_prompt(
                plan=plan_content,
                session_token=self._session_token,
            )
            
            impl_config = self.config.get_agent_config("implementation")
            impl_result = self.claude.invoke(
                prompt=impl_prompt,
                role="ui_implementation",
                model=impl_config.model,
                allowed_tools=get_allowed_tools_for_role(AgentRole.UI_IMPLEMENTATION),
                timeout=impl_config.timeout,
            )
            
            if not impl_result.success:
                self.exec_log.custom(f"[UI TESTING] Implementation failed: {impl_result.error}")
                continue
            
            fix_validation = validate_ui_fix_signal(impl_result.output, self._session_token)
            if not fix_validation.valid:
                self.exec_log.custom("[UI TESTING] Implementation agent did not provide valid signal")
                continue
            
            self.exec_log.custom("[UI TESTING] Fix applied, will retest in next iteration")
        
        return False

    def _run_task(self, task) -> TaskRunResult:
        """Run a single task through the verified loop.

        Returns:
            TaskRunResult with completion status.
        """
        from ..tasks.prd import mark_task_complete
        from ..session import TamperingDetectedError

        start_time = time.time()

        # Emit task started event
        self._emit_event(TaskStartedEvent(
            task_id=task.id,
            task_title=task.title,
        ))

        # Start task in session and log
        self.session.start_task(task.id)
        self.timeline.task_start(task.id, task.title)
        self.exec_log.task_start(task.id, task.title)

        iteration = 0
        feedback = None
        gate_output = None
        review_feedback = None

        while iteration < self.options.max_iterations:
            iteration += 1
            self.session.increment_iterations(task.id)

            # Emit iteration started event
            self._emit_event(IterationStartedEvent(
                task_id=task.id,
                iteration=iteration,
                max_iterations=self.options.max_iterations,
            ))

            # Log iteration start
            self.exec_log.iteration_start(task.id, iteration, self.options.max_iterations)

            # Step 1: Implementation
            impl_success, impl_output, impl_feedback = self._run_implementation(
                task,
                feedback=feedback or review_feedback,
            )
            if not impl_success:
                feedback = impl_feedback
                if feedback:
                    self.exec_log.feedback_set(feedback, source="implementation")
                continue

            # Step 2: Test writing (skip if task doesn't require tests)
            if task.requires_tests:
                test_success, test_output, test_feedback = self._run_test_writing(task)
                if not test_success:
                    feedback = test_feedback
                    if feedback:
                        self.exec_log.feedback_set(feedback, source="test_writing")
                    continue
            else:
                self.exec_log.custom("[TEST WRITING] Skipped (requiresTests=false)")

            # Step 3: Gates
            gates_success, gate_failure_output = self._run_gates(task)
            if not gates_success:
                gate_output = gate_failure_output
                feedback = f"Gates failed:\n{gate_failure_output}"
                self.exec_log.feedback_set(feedback, source="gates")
                continue

            # Step 4: Review
            review_valid, is_approved, review_output, rejection_feedback = self._run_review(task)
            if not review_valid:
                feedback = rejection_feedback
                if feedback:
                    self.exec_log.feedback_set(feedback, source="review signal")
                continue

            if not is_approved:
                review_feedback = rejection_feedback
                feedback = None  # Will use review_feedback in next iteration
                if review_feedback:
                    self.exec_log.feedback_set(review_feedback, source="review rejection")
                continue

            # Step 5: UI Testing (only for frontend tasks)
            if self._should_run_ui_testing(task):
                ui_success = self._run_ui_testing_loop(task)
                if not ui_success:
                    feedback = "UI testing failed"
                    self.exec_log.feedback_set(feedback, source="ui_testing")
                    continue
            else:
                self.exec_log.custom("[UI TESTING] Skipped (task doesn't affect frontend or UI testing not configured)")

            # Task complete!
            duration_ms = int((time.time() - start_time) * 1000)
            duration_seconds = duration_ms // 1000

            # Update prd.json and session
            mark_task_complete(self.prd, task.id)
            self.session.complete_task(task.id)
            self.timeline.task_complete(task.id, iterations=iteration, duration_ms=duration_ms)
            self.exec_log.task_complete(task.id, iterations=iteration, duration_seconds=duration_seconds)

            # Emit task completed event
            self._emit_event(TaskCompletedEvent(
                task_id=task.id,
                success=True,
                iterations=iteration,
                duration_ms=duration_ms,
            ))

            return TaskRunResult(
                task_id=task.id,
                completed=True,
                iterations=iteration,
                duration_ms=duration_ms,
            )

        # Max iterations reached
        duration_ms = int((time.time() - start_time) * 1000)
        duration_seconds = duration_ms // 1000
        failure_reason = f"Max iterations ({self.options.max_iterations}) reached"

        self.session.fail_task(task.id, failure_reason)
        self.timeline.task_failed(task.id, failure_reason, iterations=iteration)
        self.exec_log.task_failed(task.id, failure_reason, iterations=iteration, duration_seconds=duration_seconds)

        # Emit task completed event (failure)
        self._emit_event(TaskCompletedEvent(
            task_id=task.id,
            success=False,
            iterations=iteration,
            duration_ms=duration_ms,
            failure_reason=failure_reason,
        ))

        return TaskRunResult(
            task_id=task.id,
            completed=False,
            iterations=iteration,
            duration_ms=duration_ms,
            failure_reason=failure_reason,
        )

    def run(self) -> OrchestrationResult:
        """Execute the verified task loop.

        Returns:
            OrchestrationResult with overall outcome.
        """
        from ..tasks.prd import get_pending_tasks
        from ..session import TamperingDetectedError

        start_time = time.time()

        # Get pending tasks
        try:
            pending_tasks = get_pending_tasks(
                self.prd,
                task_id=self.options.task_id,
                from_task_id=self.options.from_task_id,
            )
        except ValueError as e:
            return OrchestrationResult(
                exit_code=ExitCode.TASK_SOURCE_ERROR,
                error=str(e),
            )

        if not pending_tasks:
            return OrchestrationResult(
                exit_code=ExitCode.SUCCESS,
                session_id=self.session.session_id,
            )

        # Emit session started event
        self._emit_event(SessionStartedEvent(
            session_id=self.session.session_id,
            task_count=len(pending_tasks),
        ))

        # Log session start
        self.timeline.session_start(
            task_count=len(pending_tasks),
            config_path=str(self.config.path),
        )

        # Dry run - just return task info
        if self.options.dry_run:
            return OrchestrationResult(
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
                self.session.end_session("failed", str(e))

                # Emit session ended event
                self._emit_event(SessionEndedEvent(
                    session_id=self.session.session_id,
                    status="failed",
                    tasks_completed=tasks_completed,
                    tasks_failed=tasks_failed + 1,
                    duration_ms=int((time.time() - start_time) * 1000),
                ))

                return OrchestrationResult(
                    exit_code=ExitCode.CHECKSUM_TAMPERING,
                    tasks_completed=tasks_completed,
                    tasks_failed=tasks_failed + 1,
                    task_results=task_results,
                    error=str(e),
                    session_id=self.session.session_id,
                )
            except KeyboardInterrupt:
                self.session.end_session("aborted")

                # Emit session ended event
                self._emit_event(SessionEndedEvent(
                    session_id=self.session.session_id,
                    status="aborted",
                    tasks_completed=tasks_completed,
                    tasks_failed=0,
                    duration_ms=int((time.time() - start_time) * 1000),
                ))

                return OrchestrationResult(
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
            from ..verify import run_post_verify, VerifyOptions

            verify_options = VerifyOptions(
                gate_type=self.options.gate_type,
                env="dev",
                fix=True,
                fix_iterations=self.config.limits.ui_fix_iterations,
            )

            post_verify_result = run_post_verify(
                config=self.config,
                session=self.session,
                timeline=self.timeline,
                options=verify_options,
            )

            if not post_verify_result.all_passed:
                tasks_failed = 1

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
        self.exec_log.session_end(
            status=final_status,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            total_duration_seconds=total_duration_ms // 1000,
        )

        # Emit session ended event
        self._emit_event(SessionEndedEvent(
            session_id=self.session.session_id,
            status=final_status,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            duration_ms=total_duration_ms,
        ))

        # Determine exit code
        if tasks_failed > 0 and not post_verify_result:
            exit_code = ExitCode.TASK_EXECUTION_FAILED
        elif post_verify_result and not post_verify_result.all_passed:
            exit_code = ExitCode.POST_VERIFICATION_FAILED
        else:
            exit_code = ExitCode.SUCCESS

        return OrchestrationResult(
            exit_code=exit_code,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            tasks_pending=tasks_pending,
            total_duration_ms=total_duration_ms,
            task_results=task_results,
            session_id=self.session.session_id,
        )

    def get_pending_tasks(self) -> list:
        """Get list of pending tasks.

        Returns:
            List of pending Task objects.
        """
        from ..tasks.prd import get_pending_tasks

        return get_pending_tasks(
            self.prd,
            task_id=self.options.task_id,
            from_task_id=self.options.from_task_id,
        )
