"""Claude CLI invocation wrapper for Ralph orchestrator.

Provides consistent interface for calling the Claude CLI with:
- Configurable command (via RALPH_CLAUDE_CMD)
- Timeout handling
- Output capture and logging
- Error handling
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..exec import run_command, ExecResult
from ..timeline import TimelineLogger, EventType


# Default Claude CLI command
DEFAULT_CLAUDE_CMD = "claude"

# Maximum output to store
MAX_OUTPUT_SIZE = 100000


@dataclass
class ClaudeResult:
    """Result of a Claude CLI invocation."""
    success: bool
    output: str
    exit_code: int
    duration_ms: int
    error: Optional[str] = None
    timed_out: bool = False
    log_path: Optional[Path] = None
    
    @property
    def truncated_output(self) -> str:
        """Get output truncated for display."""
        if len(self.output) <= 5000:
            return self.output
        return self.output[:2500] + "\n\n... [truncated] ...\n\n" + self.output[-2500:]


class ClaudeRunner:
    """Runner for Claude CLI invocations.
    
    Wraps the Claude CLI with consistent configuration, timeout handling,
    and output capture.
    """
    
    def __init__(
        self,
        claude_cmd: Optional[str] = None,
        default_timeout: int = 1800,
        logs_dir: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
        repo_root: Optional[Path] = None,
    ):
        """Initialize Claude runner.
        
        Args:
            claude_cmd: Claude CLI command. Defaults to RALPH_CLAUDE_CMD env var.
            default_timeout: Default timeout in seconds.
            logs_dir: Directory for Claude output logs.
            timeline: Timeline logger for events.
            repo_root: Repository root for working directory.
        """
        self.claude_cmd = claude_cmd or os.environ.get("RALPH_CLAUDE_CMD", DEFAULT_CLAUDE_CMD)
        self.default_timeout = default_timeout
        self.logs_dir = logs_dir
        self.timeline = timeline
        self.repo_root = repo_root or Path.cwd()
    
    def _get_claude_args(
        self,
        prompt: str,
        model: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        max_turns: Optional[int] = None,
    ) -> List[str]:
        """Build command arguments for Claude CLI.
        
        Args:
            prompt: Prompt text.
            model: Model name (optional).
            allowed_tools: List of allowed tool names.
            max_turns: Maximum conversation turns.
            
        Returns:
            List of command arguments.
        """
        # Parse base command
        args = shlex.split(self.claude_cmd)
        
        # Add print mode flag (non-interactive)
        args.append("--print")
        
        # Add model if specified
        if model:
            args.extend(["-m", model])
        
        # Add allowed tools if specified
        if allowed_tools:
            args.extend(["--allowedTools", ",".join(allowed_tools)])
        
        # Add max turns if specified
        if max_turns:
            args.extend(["--max-turns", str(max_turns)])
        
        # Add prompt
        args.extend(["-p", prompt])
        
        return args
    
    def invoke(
        self,
        prompt: str,
        role: str,
        task_id: Optional[str] = None,
        model: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        max_turns: Optional[int] = None,
    ) -> ClaudeResult:
        """Invoke Claude CLI with a prompt.
        
        Args:
            prompt: Prompt text to send.
            role: Agent role (for logging).
            task_id: Task ID (for logging and log file naming).
            model: Model name override.
            allowed_tools: List of allowed tool names.
            timeout: Timeout in seconds (defaults to default_timeout).
            max_turns: Maximum conversation turns.
            
        Returns:
            ClaudeResult with response and metadata.
        """
        if timeout is None:
            timeout = self.default_timeout
        
        # Build command
        args = self._get_claude_args(
            prompt=prompt,
            model=model,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
        )
        
        # Prepare log path
        log_path = None
        if self.logs_dir:
            timestamp = time.strftime("%H%M%S")
            log_name = f"{task_id}-{role}-{timestamp}.log" if task_id else f"{role}-{timestamp}.log"
            log_path = self.logs_dir / log_name
        
        # Log agent start
        if self.timeline:
            self.timeline.agent_start(
                task_id=task_id or "",
                role=role,
                model=model,
            )
        
        start_time = time.time()
        
        # Run command
        exec_result = run_command(
            command=args,
            cwd=self.repo_root,
            timeout=timeout,
            log_path=log_path,
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = ClaudeResult(
            success=exec_result.success,
            output=exec_result.stdout,
            exit_code=exec_result.exit_code,
            duration_ms=duration_ms,
            error=exec_result.error,
            timed_out=exec_result.timed_out,
            log_path=log_path,
        )
        
        # Log agent completion
        if self.timeline:
            if result.success:
                self.timeline.agent_complete(
                    task_id=task_id or "",
                    role=role,
                    signal="completed",
                    duration_ms=duration_ms,
                )
            else:
                self.timeline.agent_failed(
                    task_id=task_id or "",
                    role=role,
                    error=result.error or f"Exit code {result.exit_code}",
                    duration_ms=duration_ms,
                )
        
        return result


def invoke_claude(
    prompt: str,
    role: str = "default",
    task_id: Optional[str] = None,
    model: Optional[str] = None,
    allowed_tools: Optional[List[str]] = None,
    timeout: Optional[int] = None,
    claude_cmd: Optional[str] = None,
    logs_dir: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
    repo_root: Optional[Path] = None,
) -> ClaudeResult:
    """Convenience function to invoke Claude CLI.
    
    Args:
        prompt: Prompt text.
        role: Agent role for logging.
        task_id: Task ID for logging.
        model: Model name.
        allowed_tools: Allowed tools list.
        timeout: Timeout in seconds.
        claude_cmd: Claude CLI command.
        logs_dir: Directory for logs.
        timeline: Timeline logger.
        repo_root: Repository root.
        
    Returns:
        ClaudeResult with response.
    """
    runner = ClaudeRunner(
        claude_cmd=claude_cmd,
        default_timeout=timeout or 1800,
        logs_dir=logs_dir,
        timeline=timeline,
        repo_root=repo_root,
    )
    
    return runner.invoke(
        prompt=prompt,
        role=role,
        task_id=task_id,
        model=model,
        allowed_tools=allowed_tools,
        timeout=timeout,
    )


def create_claude_runner(
    config: "RalphConfig",
    logs_dir: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
    repo_root: Optional[Path] = None,
) -> ClaudeRunner:
    """Create a Claude runner from configuration.
    
    Args:
        config: Ralph configuration.
        logs_dir: Directory for logs.
        timeline: Timeline logger.
        repo_root: Repository root.
        
    Returns:
        Configured ClaudeRunner instance.
    """
    return ClaudeRunner(
        default_timeout=config.limits.claude_timeout,
        logs_dir=logs_dir,
        timeline=timeline,
        repo_root=repo_root or config.repo_root,
    )
