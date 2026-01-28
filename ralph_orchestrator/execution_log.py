"""Human-readable execution logger for debugging.

Creates a detailed execution.log file that provides visibility into
each step of the verified task loop including agent outputs, signal
validation, gate results, and feedback being sent on retry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionLogger:
    """Logger for human-readable execution logs.
    
    Writes detailed debug output to .ralph-session/logs/execution.log
    with clear formatting for each phase of task execution.
    """
    
    def __init__(
        self,
        log_path: Path,
        session_id: Optional[str] = None,
        prd_path: Optional[str] = None,
    ):
        """Initialize execution logger.
        
        Args:
            log_path: Path to execution.log file.
            session_id: Session ID for the header.
            prd_path: Path to the PRD file for the header.
        """
        self.log_path = log_path
        self.session_id = session_id
        self.prd_path = prd_path
        
        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write session header
        self._write_session_header()
    
    def _write(self, text: str) -> None:
        """Append text to the log file."""
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(text)
    
    def _write_line(self, line: str = "") -> None:
        """Append a line to the log file."""
        self._write(line + "\n")
    
    def _write_timestamped(self, message: str) -> None:
        """Write a timestamped message."""
        ts = utc_now_iso()
        self._write_line(f"[{ts}] {message}")
    
    def _write_session_header(self) -> None:
        """Write the session header at the start of the log."""
        self._write_line("=" * 80)
        self._write_line(f"SESSION: {self.session_id or 'unknown'}")
        self._write_line(f"PRD: {self.prd_path or 'unknown'}")
        self._write_line(f"Started: {utc_now_iso()}")
        self._write_line("=" * 80)
        self._write_line()
    
    def task_start(self, task_id: str, title: str) -> None:
        """Log the start of a task.
        
        Args:
            task_id: Task ID (e.g., T-001).
            title: Task title.
        """
        self._write_timestamped(f"TASK {task_id}: {title}")
        self._write_line("-" * 80)
        self._write_line()
    
    def iteration_start(
        self,
        task_id: str,
        iteration: int,
        max_iterations: int,
    ) -> None:
        """Log the start of an iteration.
        
        Args:
            task_id: Task ID.
            iteration: Current iteration number.
            max_iterations: Maximum iterations allowed.
        """
        self._write_line(f"=== ITERATION {iteration}/{max_iterations} for {task_id} ===")
        self._write_line()
    
    def agent_start(
        self,
        role: str,
        model: Optional[str] = None,
        previous_feedback: Optional[str] = None,
        allowed_paths: Optional[List[str]] = None,
        command: Optional[List[str]] = None,
    ) -> None:
        """Log the start of an agent phase.
        
        Args:
            role: Agent role (implementation, test_writing, review).
            model: Model name being used.
            previous_feedback: Feedback from previous iteration (if any).
            allowed_paths: Allowed file paths (for test_writing).
            command: The command being executed (for debugging).
        """
        role_upper = role.upper().replace("_", " ")
        self._write_line(f"[{role_upper}] Starting agent...")
        
        if model:
            self._write_line(f"  Model: {model}")
        
        if command:
            # Show command without the prompt (which is long)
            # Find index of -p flag and exclude everything after it
            cmd_parts = []
            for i, part in enumerate(command):
                if part == "-p":
                    break
                cmd_parts.append(part)
            cmd_preview = " ".join(cmd_parts)
            self._write_line(f"  Command: {cmd_preview}")
        
        if allowed_paths:
            paths_str = ", ".join(allowed_paths[:3])
            if len(allowed_paths) > 3:
                paths_str += f" (+{len(allowed_paths) - 3} more)"
            self._write_line(f"  Allowed paths: {paths_str}")
        
        if previous_feedback:
            # Truncate long feedback
            feedback_preview = previous_feedback[:200]
            if len(previous_feedback) > 200:
                feedback_preview += "..."
            self._write_line(f"  Previous feedback: {feedback_preview}")
        else:
            self._write_line("  Previous feedback: None")
        
        self._write_line()
    
    def agent_complete(
        self,
        role: str,
        duration_seconds: int,
        signal_found: bool,
        token_valid: bool,
        guardrail_violations: Optional[int] = None,
    ) -> None:
        """Log the completion of an agent phase.
        
        Args:
            role: Agent role.
            duration_seconds: Duration in seconds.
            signal_found: Whether the completion signal was found.
            token_valid: Whether the session token was valid.
            guardrail_violations: Number of guardrail violations (test_writing only).
        """
        role_upper = role.upper().replace("_", " ")
        self._write_line(f"[{role_upper}] Agent completed ({duration_seconds}s)")
        self._write_line(f"  Signal found: {'YES' if signal_found else 'NO'}")
        self._write_line(f"  Token valid: {'YES' if token_valid else 'NO'}")
        
        if guardrail_violations is not None:
            self._write_line(f"  Guardrail violations: {guardrail_violations}")
        
        self._write_line()
    
    def agent_failed(
        self,
        role: str,
        error: str,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Log agent failure.
        
        Args:
            role: Agent role.
            error: Error message.
            duration_seconds: Duration before failure.
        """
        role_upper = role.upper().replace("_", " ")
        duration_str = f" ({duration_seconds}s)" if duration_seconds else ""
        self._write_line(f"[{role_upper}] Agent FAILED{duration_str}")
        self._write_line(f"  Error: {error}")
        self._write_line()
    
    def signal_validation(
        self,
        role: str,
        signal_found: bool,
        expected_token: str,
        received_token: Optional[str] = None,
    ) -> None:
        """Log signal validation details.
        
        Args:
            role: Agent role.
            signal_found: Whether any signal was found.
            expected_token: Expected session token.
            received_token: Token that was received (if any).
        """
        role_upper = role.upper().replace("_", " ")
        self._write_line(f"[{role_upper}] Signal Validation:")
        self._write_line(f"  Signal found: {'YES' if signal_found else 'NO'}")
        
        if received_token:
            token_match = received_token == expected_token
            self._write_line(f"  Expected token: {expected_token}")
            self._write_line(f"  Received token: {received_token}")
            self._write_line(f"  Token match: {'YES' if token_match else 'NO - MISMATCH'}")
        else:
            self._write_line(f"  Expected token: {expected_token}")
            self._write_line("  Received token: None")
        
        self._write_line()
    
    def gates_start(self, gate_type: str) -> None:
        """Log the start of gate execution.
        
        Args:
            gate_type: Type of gates being run (full, fast, none).
        """
        self._write_line(f"[GATES] Running gates ({gate_type})...")
    
    def gate_result(
        self,
        gate_name: str,
        passed: bool,
        duration_seconds: float,
        output: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        """Log the result of a single gate.
        
        Args:
            gate_name: Name of the gate.
            passed: Whether the gate passed.
            duration_seconds: Duration in seconds.
            output: Gate output (especially for failures).
            exit_code: Exit code (for failed gates).
        """
        status = "PASSED" if passed else "FAILED"
        self._write_line(f"  {gate_name}: {status} ({duration_seconds:.1f}s)")
        
        if not passed:
            if exit_code is not None:
                self._write_line(f"    Exit code: {exit_code}")
            if output:
                # Indent output - show more lines for debugging
                output_lines = output.strip().split("\n")
                # Show first 50 lines of output
                for line in output_lines[:50]:
                    self._write_line(f"    {line}")
                if len(output_lines) > 50:
                    self._write_line(f"    ... ({len(output_lines) - 50} more lines)")
    
    def gates_complete(self, passed: bool, feedback: Optional[str] = None) -> None:
        """Log the completion of all gates.
        
        Args:
            passed: Whether all gates passed.
            feedback: Feedback to be sent on next iteration (if failed).
        """
        self._write_line()
        self._write_line(f"[GATES] Result: {'PASSED' if passed else 'FAILED'}")
        
        if not passed and feedback:
            self._write_line("  Setting feedback for next iteration:")
            # Show first 2000 chars of feedback for better debugging
            feedback_preview = feedback[:2000]
            for line in feedback_preview.split("\n"):
                self._write_line(f"  {line}")
            if len(feedback) > 2000:
                self._write_line("  ...")
        
        self._write_line()
    
    def review_result(
        self,
        approved: bool,
        duration_seconds: int,
        rejection_reason: Optional[str] = None,
    ) -> None:
        """Log review agent result.
        
        Args:
            approved: Whether the review was approved.
            duration_seconds: Duration in seconds.
            rejection_reason: Reason for rejection (if not approved).
        """
        self._write_line(f"[REVIEW] Result: {'APPROVED' if approved else 'REJECTED'} ({duration_seconds}s)")
        
        if not approved and rejection_reason:
            self._write_line("  Rejection reason:")
            for line in rejection_reason.split("\n")[:10]:
                self._write_line(f"    {line}")
        
        self._write_line()
    
    def feedback_set(self, feedback: str, source: str) -> None:
        """Log feedback being set for next iteration.
        
        Args:
            feedback: The feedback content.
            source: Source of the feedback (signal, gates, review).
        """
        self._write_line(f"[FEEDBACK] Setting feedback from {source} for next iteration:")
        # Show first 2000 chars for better debugging
        feedback_preview = feedback[:2000]
        for line in feedback_preview.split("\n"):
            self._write_line(f"  {line}")
        if len(feedback) > 2000:
            self._write_line("  ...")
        self._write_line()
    
    def task_complete(
        self,
        task_id: str,
        iterations: int,
        duration_seconds: int,
    ) -> None:
        """Log task completion.
        
        Args:
            task_id: Task ID.
            iterations: Total iterations used.
            duration_seconds: Total duration in seconds.
        """
        self._write_line(f"[TASK COMPLETE] {task_id}")
        self._write_line(f"  Iterations: {iterations}")
        self._write_line(f"  Duration: {duration_seconds}s")
        self._write_line()
        self._write_line("-" * 80)
        self._write_line()
    
    def task_failed(
        self,
        task_id: str,
        reason: str,
        iterations: int,
        duration_seconds: int,
    ) -> None:
        """Log task failure.
        
        Args:
            task_id: Task ID.
            reason: Failure reason.
            iterations: Total iterations attempted.
            duration_seconds: Total duration in seconds.
        """
        self._write_line(f"[TASK FAILED] {task_id}")
        self._write_line(f"  Reason: {reason}")
        self._write_line(f"  Iterations: {iterations}")
        self._write_line(f"  Duration: {duration_seconds}s")
        self._write_line()
        self._write_line("-" * 80)
        self._write_line()
    
    def session_end(
        self,
        status: str,
        tasks_completed: int,
        tasks_failed: int,
        total_duration_seconds: int,
    ) -> None:
        """Log session end.
        
        Args:
            status: Final session status.
            tasks_completed: Number of completed tasks.
            tasks_failed: Number of failed tasks.
            total_duration_seconds: Total session duration.
        """
        self._write_line()
        self._write_line("=" * 80)
        self._write_line("SESSION END")
        self._write_line("=" * 80)
        self._write_line(f"  Status: {status}")
        self._write_line(f"  Tasks completed: {tasks_completed}")
        self._write_line(f"  Tasks failed: {tasks_failed}")
        self._write_line(f"  Total duration: {total_duration_seconds}s")
        self._write_line(f"  Ended: {utc_now_iso()}")
        self._write_line("=" * 80)
    
    def agent_output(
        self,
        role: str,
        output: str,
        max_lines: int = 30,
    ) -> None:
        """Log agent output/last message.
        
        Args:
            role: Agent role.
            output: Full agent output.
            max_lines: Maximum lines to show.
        """
        role_upper = role.upper().replace("_", " ")
        self._write_line(f"[{role_upper}] Agent Output (last message):")
        
        # Extract last meaningful content (trim trailing whitespace)
        output = output.strip()
        lines = output.split("\n")
        
        # Show last N lines
        display_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        if len(lines) > max_lines:
            self._write_line(f"  ... ({len(lines) - max_lines} lines omitted)")
        
        for line in display_lines:
            self._write_line(f"  {line[:200]}")  # Truncate very long lines
        
        self._write_line()

    def custom(self, message: str, indent: int = 0) -> None:
        """Log a custom message.
        
        Args:
            message: Message to log.
            indent: Number of spaces to indent.
        """
        prefix = " " * indent
        for line in message.split("\n"):
            self._write_line(f"{prefix}{line}")


def create_execution_logger(
    session_dir: Path,
    session_id: Optional[str] = None,
    prd_path: Optional[str] = None,
) -> ExecutionLogger:
    """Create an execution logger for a session.
    
    Args:
        session_dir: Path to session directory.
        session_id: Session ID for the header.
        prd_path: Path to PRD file for the header.
        
    Returns:
        ExecutionLogger instance.
    """
    log_path = session_dir / "logs" / "execution.log"
    return ExecutionLogger(log_path, session_id=session_id, prd_path=prd_path)
