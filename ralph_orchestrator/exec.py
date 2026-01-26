"""Subprocess execution runner for Ralph orchestrator.

Provides subprocess execution with:
- Configurable timeouts
- stdout/stderr capture
- Log file output
- Safe display truncation
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union


# Default timeout for commands (30 minutes)
DEFAULT_TIMEOUT = 1800

# Maximum output to display in console (characters)
MAX_DISPLAY_OUTPUT = 5000

# Maximum output to store in result (characters)
MAX_STORED_OUTPUT = 100000


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ExecResult:
    """Result of a subprocess execution."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    error: Optional[str] = None
    log_path: Optional[Path] = None
    
    @property
    def success(self) -> bool:
        """Check if command succeeded (exit code 0)."""
        return self.exit_code == 0 and not self.timed_out
    
    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)
    
    def truncated_output(self, max_chars: int = MAX_DISPLAY_OUTPUT) -> str:
        """Get output truncated to max characters for display."""
        output = self.output
        if len(output) <= max_chars:
            return output
        
        # Keep first and last portions
        head_size = max_chars // 2
        tail_size = max_chars - head_size - 50  # Leave room for truncation message
        
        return (
            output[:head_size] +
            f"\n\n... [truncated {len(output) - max_chars} characters] ...\n\n" +
            output[-tail_size:]
        )
    
    def truncated_stdout(self, max_chars: int = MAX_DISPLAY_OUTPUT) -> str:
        """Get stdout truncated to max characters."""
        if len(self.stdout) <= max_chars:
            return self.stdout
        
        head_size = max_chars // 2
        tail_size = max_chars - head_size - 50
        
        return (
            self.stdout[:head_size] +
            f"\n\n... [truncated {len(self.stdout) - max_chars} characters] ...\n\n" +
            self.stdout[-tail_size:]
        )


def _truncate_output(output: str, max_chars: int = MAX_STORED_OUTPUT) -> str:
    """Truncate output to maximum size."""
    if len(output) <= max_chars:
        return output
    
    head_size = max_chars // 2
    tail_size = max_chars - head_size - 100
    
    return (
        output[:head_size] +
        f"\n\n... [output truncated: {len(output)} total characters, "
        f"showing first {head_size} and last {tail_size}] ...\n\n" +
        output[-tail_size:]
    )


def run_command(
    command: Union[str, List[str]],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    env: Optional[dict] = None,
    capture_output: bool = True,
    input_text: Optional[str] = None,
    log_path: Optional[Path] = None,
    shell: bool = False,
) -> ExecResult:
    """Run a command and capture output.
    
    Args:
        command: Command to run (string or list of args).
        cwd: Working directory.
        timeout: Timeout in seconds (default: DEFAULT_TIMEOUT).
        env: Environment variables (merged with current env).
        capture_output: Whether to capture stdout/stderr.
        log_path: Path to write combined output to.
        shell: Whether to run through shell.
        
    Returns:
        ExecResult with command results.
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    
    # Prepare command
    if isinstance(command, str):
        cmd_str = command
        if not shell:
            command = shlex.split(command)
    else:
        cmd_str = " ".join(shlex.quote(arg) for arg in command)
    
    # Prepare environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    
    # Prepare log file
    log_file = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("w", encoding="utf-8")
        log_file.write(f"# Command: {cmd_str}\n")
        log_file.write(f"# Started: {utc_now_iso()}\n")
        log_file.write(f"# CWD: {cwd or Path.cwd()}\n")
        log_file.write(f"# Timeout: {timeout}s\n")
        log_file.write("-" * 60 + "\n")
    
    start_time = time.time()
    stdout_data = ""
    stderr_data = ""
    timed_out = False
    error_msg = None
    exit_code = -1
    
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=run_env,
            capture_output=capture_output,
            text=True,
            input=input_text,
            timeout=timeout,
            shell=shell,
        )
        
        exit_code = result.returncode
        stdout_data = result.stdout or ""
        stderr_data = result.stderr or ""
        
    except subprocess.TimeoutExpired as e:
        timed_out = True
        error_msg = f"Command timed out after {timeout}s"
        exit_code = -1
        
        # Capture any partial output
        if e.stdout:
            stdout_data = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="replace")
        if e.stderr:
            stderr_data = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="replace")
            
    except FileNotFoundError as e:
        error_msg = f"Command not found: {e}"
        exit_code = 127
        
    except PermissionError as e:
        error_msg = f"Permission denied: {e}"
        exit_code = 126
        
    except Exception as e:
        error_msg = f"Execution error: {e}"
        exit_code = -1
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Write to log file
    if log_file:
        if stdout_data:
            log_file.write("# STDOUT:\n")
            log_file.write(stdout_data)
            if not stdout_data.endswith("\n"):
                log_file.write("\n")
        if stderr_data:
            log_file.write("# STDERR:\n")
            log_file.write(stderr_data)
            if not stderr_data.endswith("\n"):
                log_file.write("\n")
        log_file.write("-" * 60 + "\n")
        log_file.write(f"# Ended: {utc_now_iso()}\n")
        log_file.write(f"# Duration: {duration_ms}ms\n")
        log_file.write(f"# Exit code: {exit_code}\n")
        if timed_out:
            log_file.write("# TIMED OUT\n")
        if error_msg:
            log_file.write(f"# Error: {error_msg}\n")
        log_file.close()
    
    # Truncate stored output
    stdout_data = _truncate_output(stdout_data)
    stderr_data = _truncate_output(stderr_data)
    
    return ExecResult(
        command=cmd_str,
        exit_code=exit_code,
        stdout=stdout_data,
        stderr=stderr_data,
        duration_ms=duration_ms,
        timed_out=timed_out,
        error=error_msg,
        log_path=log_path,
    )


def run_command_with_streaming(
    command: Union[str, List[str]],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    env: Optional[dict] = None,
    log_path: Optional[Path] = None,
    prefix: str = "",
    shell: bool = False,
) -> ExecResult:
    """Run a command with streaming output to console.
    
    Output is displayed in real-time while also being captured.
    
    Args:
        command: Command to run.
        cwd: Working directory.
        timeout: Timeout in seconds.
        env: Environment variables.
        log_path: Path to write output to.
        prefix: Prefix for each line of output.
        shell: Whether to run through shell.
        
    Returns:
        ExecResult with command results.
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    
    # Prepare command
    if isinstance(command, str):
        cmd_str = command
        if not shell:
            command = shlex.split(command)
    else:
        cmd_str = " ".join(shlex.quote(arg) for arg in command)
    
    # Prepare environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    
    # Prepare log file
    log_file = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("w", encoding="utf-8")
        log_file.write(f"# Command: {cmd_str}\n")
        log_file.write(f"# Started: {utc_now_iso()}\n")
        log_file.write("-" * 60 + "\n")
    
    start_time = time.time()
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    timed_out = False
    error_msg = None
    exit_code = -1
    
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=shell,
        )
        
        import selectors
        
        sel = selectors.DefaultSelector()
        if process.stdout:
            sel.register(process.stdout, selectors.EVENT_READ)
        if process.stderr:
            sel.register(process.stderr, selectors.EVENT_READ)
        
        deadline = time.time() + timeout
        
        while sel.get_map():
            remaining = deadline - time.time()
            if remaining <= 0:
                process.kill()
                timed_out = True
                error_msg = f"Command timed out after {timeout}s"
                break
            
            events = sel.select(timeout=min(remaining, 0.1))
            
            for key, _ in events:
                line = key.fileobj.readline()
                if not line:
                    sel.unregister(key.fileobj)
                    continue
                
                # Determine if stdout or stderr
                is_stderr = key.fileobj == process.stderr
                
                # Store
                if is_stderr:
                    stderr_lines.append(line)
                else:
                    stdout_lines.append(line)
                
                # Display
                display_line = line.rstrip()
                if prefix:
                    display_line = f"{prefix}{display_line}"
                print(display_line, file=sys.stderr if is_stderr else sys.stdout)
                
                # Log
                if log_file:
                    log_file.write(line)
        
        if not timed_out:
            exit_code = process.wait()
        else:
            exit_code = -1
            
    except FileNotFoundError as e:
        error_msg = f"Command not found: {e}"
        exit_code = 127
        
    except Exception as e:
        error_msg = f"Execution error: {e}"
        exit_code = -1
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Finalize log
    if log_file:
        log_file.write("-" * 60 + "\n")
        log_file.write(f"# Ended: {utc_now_iso()}\n")
        log_file.write(f"# Duration: {duration_ms}ms\n")
        log_file.write(f"# Exit code: {exit_code}\n")
        log_file.close()
    
    stdout_data = _truncate_output("".join(stdout_lines))
    stderr_data = _truncate_output("".join(stderr_lines))
    
    return ExecResult(
        command=cmd_str,
        exit_code=exit_code,
        stdout=stdout_data,
        stderr=stderr_data,
        duration_ms=duration_ms,
        timed_out=timed_out,
        error=error_msg,
        log_path=log_path,
    )


def which(cmd: str) -> Optional[str]:
    """Find executable in PATH.
    
    Args:
        cmd: Command name to find.
        
    Returns:
        Full path to executable or None.
    """
    import shutil
    return shutil.which(cmd)


def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH.
    
    Args:
        cmd: Command name to check.
        
    Returns:
        True if command exists.
    """
    return which(cmd) is not None


def get_command_version(cmd: str, version_arg: str = "--version") -> Optional[str]:
    """Get version string from a command.
    
    Args:
        cmd: Command to check.
        version_arg: Argument to get version (default: --version).
        
    Returns:
        Version string or None.
    """
    try:
        result = run_command([cmd, version_arg], timeout=5)
        if result.success:
            return result.stdout.strip() or result.stderr.strip()
    except Exception:
        pass
    return None


class CommandRunner:
    """Stateful command runner for a session.
    
    Tracks all commands run and their results.
    """
    
    def __init__(
        self,
        logs_dir: Optional[Path] = None,
        default_cwd: Optional[Path] = None,
        default_timeout: int = DEFAULT_TIMEOUT,
    ):
        """Initialize command runner.
        
        Args:
            logs_dir: Directory to write command logs.
            default_cwd: Default working directory.
            default_timeout: Default timeout for commands.
        """
        self.logs_dir = logs_dir
        self.default_cwd = default_cwd
        self.default_timeout = default_timeout
        self.history: List[ExecResult] = []
    
    def run(
        self,
        command: Union[str, List[str]],
        name: Optional[str] = None,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        env: Optional[dict] = None,
        log: bool = True,
        stream: bool = False,
        shell: bool = False,
    ) -> ExecResult:
        """Run a command.
        
        Args:
            command: Command to run.
            name: Name for log file.
            cwd: Working directory (uses default if not specified).
            timeout: Timeout in seconds.
            env: Environment variables.
            log: Whether to write to log file.
            stream: Whether to stream output.
            shell: Whether to run through shell.
            
        Returns:
            ExecResult with command results.
        """
        if cwd is None:
            cwd = self.default_cwd
        if timeout is None:
            timeout = self.default_timeout
        
        log_path = None
        if log and self.logs_dir and name:
            timestamp = datetime.now().strftime("%H%M%S")
            log_path = self.logs_dir / f"{name}-{timestamp}.log"
        
        if stream:
            result = run_command_with_streaming(
                command,
                cwd=cwd,
                timeout=timeout,
                env=env,
                log_path=log_path,
                shell=shell,
            )
        else:
            result = run_command(
                command,
                cwd=cwd,
                timeout=timeout,
                env=env,
                log_path=log_path,
                shell=shell,
            )
        
        self.history.append(result)
        return result
    
    def get_failed_commands(self) -> List[ExecResult]:
        """Get all failed commands."""
        return [r for r in self.history if not r.success]
    
    def get_timed_out_commands(self) -> List[ExecResult]:
        """Get all timed out commands."""
        return [r for r in self.history if r.timed_out]
    
    def clear_history(self) -> None:
        """Clear command history."""
        self.history.clear()
