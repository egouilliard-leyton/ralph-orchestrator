"""Quality gate execution for Ralph orchestrator.

Runs configured quality gates (build, lint, test, type-check) and
handles fatal/non-fatal failures, timeouts, and conditional execution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .config import GateConfig, RalphConfig
from .exec import run_command, ExecResult
from .timeline import TimelineLogger, EventType


@dataclass
class GateResult:
    """Result of a single gate execution."""
    name: str
    passed: bool
    exit_code: int
    duration_ms: int
    output: str
    error: Optional[str] = None
    timed_out: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None
    fatal: bool = True
    log_path: Optional[Path] = None


@dataclass
class GatesResult:
    """Result of running all gates in a category."""
    gate_type: str  # "build" or "full"
    passed: bool
    results: List[GateResult] = field(default_factory=list)
    fatal_failure: Optional[GateResult] = None
    
    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed and not r.skipped)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and not r.skipped)
    
    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.skipped)
    
    @property
    def total_duration_ms(self) -> int:
        return sum(r.duration_ms for r in self.results)


class GateRunner:
    """Executes quality gates defined in configuration."""
    
    def __init__(
        self,
        config: RalphConfig,
        repo_root: Optional[Path] = None,
        logs_dir: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
    ):
        """Initialize gate runner.
        
        Args:
            config: Ralph configuration with gate definitions.
            repo_root: Repository root directory. Defaults to cwd.
            logs_dir: Directory for gate output logs.
            timeline: Timeline logger for events.
        """
        self.config = config
        self.repo_root = repo_root or Path.cwd()
        self.logs_dir = logs_dir
        self.timeline = timeline
    
    def _check_condition(self, gate: GateConfig) -> tuple[bool, Optional[str]]:
        """Check if gate condition is met.
        
        Args:
            gate: Gate configuration with optional 'when' condition.
            
        Returns:
            Tuple of (should_run, skip_reason).
        """
        if gate.when is None:
            return True, None
        
        # Check if file/directory exists
        condition_path = self.repo_root / gate.when
        if condition_path.exists():
            return True, None
        
        return False, f"Condition not met: {gate.when} does not exist"
    
    def _run_gate(
        self,
        gate: GateConfig,
        task_id: Optional[str] = None,
    ) -> GateResult:
        """Run a single gate.
        
        Args:
            gate: Gate configuration.
            task_id: Current task ID for logging.
            
        Returns:
            GateResult with execution outcome.
        """
        # Check condition
        should_run, skip_reason = self._check_condition(gate)
        if not should_run:
            return GateResult(
                name=gate.name,
                passed=True,  # Skipped gates count as passed
                exit_code=0,
                duration_ms=0,
                output="",
                skipped=True,
                skip_reason=skip_reason,
                fatal=gate.fatal,
            )
        
        # Prepare log path
        log_path = None
        if self.logs_dir:
            log_path = self.logs_dir / f"gate-{gate.name}.log"
        
        # Run the gate command
        exec_result = run_command(
            command=gate.cmd,
            cwd=self.repo_root,
            timeout=gate.timeout_seconds,
            log_path=log_path,
            shell=True,  # Gates are shell commands
        )
        
        result = GateResult(
            name=gate.name,
            passed=exec_result.success,
            exit_code=exec_result.exit_code,
            duration_ms=exec_result.duration_ms,
            output=exec_result.truncated_output(),
            error=exec_result.error,
            timed_out=exec_result.timed_out,
            fatal=gate.fatal,
            log_path=log_path,
        )
        
        # Log to timeline
        if self.timeline:
            if result.passed:
                self.timeline.gate_pass(
                    gate_name=gate.name,
                    duration_ms=result.duration_ms,
                    task_id=task_id,
                )
            else:
                self.timeline.gate_fail(
                    gate_name=gate.name,
                    error=result.error or f"Exit code {result.exit_code}",
                    duration_ms=result.duration_ms,
                    task_id=task_id,
                    fatal=gate.fatal,
                )
        
        return result
    
    def run_gates(
        self,
        gate_type: str = "full",
        task_id: Optional[str] = None,
        stop_on_fatal: bool = True,
    ) -> GatesResult:
        """Run all gates of a specific type.
        
        Args:
            gate_type: Type of gates to run ("build", "full", or "none").
            task_id: Current task ID for logging.
            stop_on_fatal: Stop execution on fatal gate failure.
            
        Returns:
            GatesResult with all gate outcomes.
        """
        gates = self.config.get_gates(gate_type)
        
        if not gates:
            return GatesResult(
                gate_type=gate_type,
                passed=True,
                results=[],
            )
        
        # Log gates run start
        if self.timeline:
            self.timeline.gates_run(
                gate_type=gate_type,
                gate_count=len(gates),
                task_id=task_id,
            )
        
        results = []
        fatal_failure = None
        
        for gate in gates:
            result = self._run_gate(gate, task_id=task_id)
            results.append(result)
            
            # Check for fatal failure
            if not result.passed and result.fatal and not result.skipped:
                fatal_failure = result
                if stop_on_fatal:
                    break
        
        return GatesResult(
            gate_type=gate_type,
            passed=fatal_failure is None,
            results=results,
            fatal_failure=fatal_failure,
        )
    
    def run_build_gates(
        self,
        task_id: Optional[str] = None,
    ) -> GatesResult:
        """Run build gates (fast checks during task loop)."""
        return self.run_gates("build", task_id=task_id)
    
    def run_full_gates(
        self,
        task_id: Optional[str] = None,
    ) -> GatesResult:
        """Run full gates (complete verification)."""
        return self.run_gates("full", task_id=task_id)


def create_gate_runner(
    config: RalphConfig,
    repo_root: Optional[Path] = None,
    logs_dir: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
) -> GateRunner:
    """Create a gate runner from configuration.
    
    Args:
        config: Ralph configuration.
        repo_root: Repository root directory.
        logs_dir: Directory for gate output logs.
        timeline: Timeline logger for events.
        
    Returns:
        Configured GateRunner instance.
    """
    return GateRunner(
        config=config,
        repo_root=repo_root,
        logs_dir=logs_dir,
        timeline=timeline,
    )


def format_gate_failure(result: GateResult) -> str:
    """Format a gate failure for display and feedback.
    
    Args:
        result: Failed gate result.
        
    Returns:
        Formatted failure message.
    """
    lines = [
        f"Gate '{result.name}' failed (exit code {result.exit_code})",
    ]
    
    if result.timed_out:
        lines.append(f"  Timed out after timeout limit")
    
    if result.error:
        lines.append(f"  Error: {result.error}")
    
    if result.output:
        # Truncate output for display
        output_lines = result.output.split("\n")
        if len(output_lines) > 20:
            output_preview = "\n".join(output_lines[:10] + ["..."] + output_lines[-10:])
        else:
            output_preview = result.output
        lines.append(f"  Output:\n{output_preview}")
    
    return "\n".join(lines)


def format_gates_summary(result: GatesResult) -> str:
    """Format gates result summary for display.
    
    Args:
        result: Gates execution result.
        
    Returns:
        Formatted summary string.
    """
    lines = [
        f"Gates ({result.gate_type}): {result.passed_count} passed, "
        f"{result.failed_count} failed, {result.skipped_count} skipped"
    ]
    
    for gate_result in result.results:
        if gate_result.skipped:
            status = "⊘"  # Skipped
            suffix = f" (skipped: {gate_result.skip_reason})"
        elif gate_result.passed:
            status = "✓"
            suffix = f" ({gate_result.duration_ms}ms)"
        else:
            status = "✗"
            suffix = f" (failed, exit {gate_result.exit_code})"
        
        lines.append(f"  {status} {gate_result.name}{suffix}")
    
    return "\n".join(lines)
