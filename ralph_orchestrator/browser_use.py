"""Browser automation wrapper using agent-browser CLI.

Provides a programmatic interface to Vercel's agent-browser CLI for
browser exploration and UI testing. Used by the UI testing agent to
verify frontend changes and capture artifacts.

Commands supported:
- open: Navigate to a URL
- snapshot: Capture accessibility snapshot of the current page
- click: Click on an element
- type: Type text into an element
- screenshot: Capture a screenshot of the page

Artifacts are captured to .ralph-session/artifacts/browser-use/
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import RalphConfig
from .exec import run_command, ExecResult, check_command_exists
from .timeline import TimelineLogger


class BrowserActionType(str, Enum):
    """Browser action types."""
    OPEN = "open"
    SNAPSHOT = "snapshot"
    CLICK = "click"
    TYPE = "type"
    SCREENSHOT = "screenshot"
    HOVER = "hover"
    SCROLL = "scroll"
    WAIT = "wait"
    EVALUATE = "evaluate"


@dataclass
class BrowserActionResult:
    """Result of a browser action."""
    action: BrowserActionType
    success: bool
    duration_ms: int
    output: str = ""
    error: Optional[str] = None
    screenshot_path: Optional[Path] = None
    snapshot_path: Optional[Path] = None
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        result: Dict[str, Any] = {
            "action": self.action.value,
            "success": self.success,
            "duration_ms": self.duration_ms,
        }
        if self.output:
            result["output"] = self.output[:500] if len(self.output) > 500 else self.output
        if self.error:
            result["error"] = self.error
        if self.screenshot_path:
            result["screenshot"] = str(self.screenshot_path)
        if self.snapshot_path:
            result["snapshot"] = str(self.snapshot_path)
        if self.data:
            result["data"] = self.data
        return result


@dataclass
class BrowserSession:
    """Represents an active browser session."""
    session_id: str
    base_url: str
    current_url: Optional[str] = None
    started_at: Optional[datetime] = None
    actions: List[BrowserActionResult] = field(default_factory=list)
    artifacts_dir: Optional[Path] = None
    
    @property
    def action_count(self) -> int:
        return len(self.actions)
    
    @property
    def success_count(self) -> int:
        return sum(1 for a in self.actions if a.success)
    
    @property
    def failure_count(self) -> int:
        return sum(1 for a in self.actions if not a.success)
    
    def get_latest_screenshot(self) -> Optional[Path]:
        """Get the most recent screenshot path."""
        for action in reversed(self.actions):
            if action.screenshot_path and action.screenshot_path.exists():
                return action.screenshot_path
        return None
    
    def get_latest_snapshot(self) -> Optional[Path]:
        """Get the most recent snapshot path."""
        for action in reversed(self.actions):
            if action.snapshot_path and action.snapshot_path.exists():
                return action.snapshot_path
        return None


class BrowserUseRunner:
    """Runner for browser automation using agent-browser CLI.
    
    Wraps Vercel's agent-browser CLI to provide programmatic browser
    control for UI testing and exploration.
    
    Example usage:
        runner = BrowserUseRunner(config, "http://localhost:3000")
        session = runner.start_session()
        
        # Navigate and verify
        runner.open("/dashboard")
        runner.click("button", "Login")
        runner.type("input[name='email']", "test@example.com")
        screenshot = runner.screenshot("after-login")
        
        runner.end_session()
    """
    
    def __init__(
        self,
        config: RalphConfig,
        base_url: str,
        artifacts_dir: Optional[Path] = None,
        logs_dir: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
        timeout: int = 120,
        screenshot_on_failure: bool = True,
    ):
        """Initialize browser-use runner.
        
        Args:
            config: Ralph configuration with browser_use settings.
            base_url: Base URL for the frontend application.
            artifacts_dir: Directory for browser artifacts (screenshots, snapshots).
            logs_dir: Directory for browser logs.
            timeline: Timeline logger for events.
            timeout: Default timeout for browser actions in seconds.
            screenshot_on_failure: Whether to capture screenshots on action failures.
        """
        self.config = config
        self.base_url = base_url.rstrip("/")
        self.artifacts_dir = artifacts_dir or Path(".ralph-session/artifacts/browser-use")
        self.logs_dir = logs_dir or Path(".ralph-session/logs")
        self.timeline = timeline
        self.timeout = timeout
        self.screenshot_on_failure = screenshot_on_failure
        
        # Ensure directories exist
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = self.artifacts_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir = self.artifacts_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session
        self._session: Optional[BrowserSession] = None
        
        # Load config settings
        ui_config = config.raw_data.get("ui", {})
        browser_use_config = ui_config.get("browser_use", {})
        
        # Override defaults from config
        if "timeout" in browser_use_config:
            self.timeout = browser_use_config["timeout"]
        if "screenshot_on_failure" in browser_use_config:
            self.screenshot_on_failure = browser_use_config["screenshot_on_failure"]
    
    @property
    def session(self) -> Optional[BrowserSession]:
        """Get the current browser session."""
        return self._session
    
    @property
    def is_available(self) -> bool:
        """Check if agent-browser CLI is available."""
        return check_command_exists("agent-browser")
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"browser-{timestamp}-{short_uuid}"
    
    def _generate_artifact_name(self, prefix: str, extension: str) -> str:
        """Generate a unique artifact filename."""
        timestamp = datetime.now().strftime("%H%M%S")
        action_num = len(self._session.actions) if self._session else 0
        return f"{prefix}-{action_num:03d}-{timestamp}.{extension}"
    
    def _run_agent_browser(
        self,
        prompt: str,
        screenshot_path: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> ExecResult:
        """Run agent-browser CLI with a prompt.
        
        Args:
            prompt: The instruction prompt for agent-browser.
            screenshot_path: Optional path to save a screenshot.
            timeout: Timeout in seconds (uses default if not specified).
            
        Returns:
            ExecResult with command output.
        """
        if timeout is None:
            timeout = self.timeout
        
        cmd = ["agent-browser", "-p", prompt]
        
        if screenshot_path:
            cmd.extend(["--screenshot", str(screenshot_path)])
        
        # Create a log file for this command
        log_name = f"agent-browser-{datetime.now().strftime('%H%M%S')}.log"
        log_path = self.logs_dir / log_name
        
        return run_command(
            cmd,
            cwd=self.config.repo_root,
            timeout=timeout,
            log_path=log_path,
        )
    
    def _record_action(self, result: BrowserActionResult) -> None:
        """Record an action in the current session."""
        if self._session:
            self._session.actions.append(result)
    
    def start_session(self) -> BrowserSession:
        """Start a new browser session.
        
        Returns:
            BrowserSession instance.
        """
        session_id = self._generate_session_id()
        session_artifacts = self.artifacts_dir / session_id
        session_artifacts.mkdir(parents=True, exist_ok=True)
        
        self._session = BrowserSession(
            session_id=session_id,
            base_url=self.base_url,
            started_at=datetime.now(),
            artifacts_dir=session_artifacts,
        )
        
        # Update artifact directories for this session
        self.screenshots_dir = session_artifacts / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir = session_artifacts / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        return self._session
    
    def end_session(self) -> Optional[BrowserSession]:
        """End the current browser session.
        
        Returns:
            The completed BrowserSession or None if no session was active.
        """
        if not self._session:
            return None
        
        session = self._session
        self._session = None
        
        # Write session summary
        summary_path = session.artifacts_dir / "session-summary.json" if session.artifacts_dir else None
        if summary_path:
            summary = {
                "session_id": session.session_id,
                "base_url": session.base_url,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": datetime.now().isoformat(),
                "action_count": session.action_count,
                "success_count": session.success_count,
                "failure_count": session.failure_count,
                "actions": [a.to_dict() for a in session.actions],
            }
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        
        return session
    
    def open(
        self,
        url_or_path: str,
        wait_for: Optional[str] = None,
    ) -> BrowserActionResult:
        """Navigate to a URL.
        
        Args:
            url_or_path: Full URL or path (will be joined with base_url).
            wait_for: Optional text/element to wait for after navigation.
            
        Returns:
            BrowserActionResult with navigation outcome.
        """
        start_time = time.time()
        
        # Build full URL
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            full_url = url_or_path
        else:
            path = url_or_path.lstrip("/")
            full_url = f"{self.base_url}/{path}"
        
        # Build prompt
        prompt = f"Navigate to {full_url}"
        if wait_for:
            prompt += f" and wait for '{wait_for}' to appear"
        
        # Screenshot on open
        screenshot_path = self.screenshots_dir / self._generate_artifact_name("open", "png")
        
        exec_result = self._run_agent_browser(prompt, screenshot_path=screenshot_path)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None
        
        if not success:
            error = exec_result.error or "Navigation failed"
            if self.screenshot_on_failure and not screenshot_path.exists():
                # Try to capture failure screenshot
                self._capture_failure_screenshot("open-failed")
        
        # Update session URL
        if self._session:
            self._session.current_url = full_url
        
        result = BrowserActionResult(
            action=BrowserActionType.OPEN,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
        )
        
        self._record_action(result)
        return result
    
    def snapshot(
        self,
        name: Optional[str] = None,
    ) -> BrowserActionResult:
        """Capture an accessibility snapshot of the current page.
        
        Args:
            name: Optional name for the snapshot file.
            
        Returns:
            BrowserActionResult with snapshot path.
        """
        start_time = time.time()
        
        snapshot_name = name or self._generate_artifact_name("snapshot", "json")
        if not snapshot_name.endswith(".json"):
            snapshot_name += ".json"
        snapshot_path = self.snapshots_dir / snapshot_name
        
        prompt = "Capture an accessibility snapshot of the current page and output the page structure as JSON"
        
        exec_result = self._run_agent_browser(prompt)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None
        snapshot_data = None
        
        if success:
            # Try to extract JSON from output
            try:
                # Look for JSON in the output
                output = exec_result.output
                json_match = re.search(r'\{[\s\S]*\}', output)
                if json_match:
                    snapshot_data = json.loads(json_match.group())
                    snapshot_path.write_text(json.dumps(snapshot_data, indent=2), encoding="utf-8")
                else:
                    # Save raw output as snapshot
                    snapshot_path.write_text(output, encoding="utf-8")
            except (json.JSONDecodeError, Exception) as e:
                error = f"Failed to parse snapshot: {e}"
                success = False
        else:
            error = exec_result.error or "Snapshot capture failed"
        
        result = BrowserActionResult(
            action=BrowserActionType.SNAPSHOT,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            snapshot_path=snapshot_path if snapshot_path.exists() else None,
            data=snapshot_data,
        )
        
        self._record_action(result)
        return result
    
    def click(
        self,
        selector_or_description: str,
        text: Optional[str] = None,
    ) -> BrowserActionResult:
        """Click on an element.
        
        Args:
            selector_or_description: CSS selector or element description.
            text: Optional text content to match within the element.
            
        Returns:
            BrowserActionResult with click outcome.
        """
        start_time = time.time()
        
        # Build prompt
        if text:
            prompt = f"Click on the element matching '{selector_or_description}' with text '{text}'"
        else:
            prompt = f"Click on the element: {selector_or_description}"
        
        screenshot_path = self.screenshots_dir / self._generate_artifact_name("click", "png")
        
        exec_result = self._run_agent_browser(prompt, screenshot_path=screenshot_path)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None
        
        if not success:
            error = exec_result.error or f"Click failed: {selector_or_description}"
            if self.screenshot_on_failure:
                self._capture_failure_screenshot("click-failed")
        
        result = BrowserActionResult(
            action=BrowserActionType.CLICK,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
        )
        
        self._record_action(result)
        return result
    
    def type(
        self,
        selector_or_description: str,
        text: str,
        clear_first: bool = True,
        submit: bool = False,
    ) -> BrowserActionResult:
        """Type text into an input element.
        
        Args:
            selector_or_description: CSS selector or element description.
            text: Text to type.
            clear_first: Whether to clear the field before typing.
            submit: Whether to press Enter after typing.
            
        Returns:
            BrowserActionResult with type outcome.
        """
        start_time = time.time()
        
        # Build prompt
        action_desc = []
        if clear_first:
            action_desc.append("clear")
        action_desc.append(f"type '{text}'")
        if submit:
            action_desc.append("press Enter")
        
        prompt = f"In the field '{selector_or_description}', {', then '.join(action_desc)}"
        
        screenshot_path = self.screenshots_dir / self._generate_artifact_name("type", "png")
        
        exec_result = self._run_agent_browser(prompt, screenshot_path=screenshot_path)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None
        
        if not success:
            error = exec_result.error or f"Type failed: {selector_or_description}"
            if self.screenshot_on_failure:
                self._capture_failure_screenshot("type-failed")
        
        result = BrowserActionResult(
            action=BrowserActionType.TYPE,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
        )
        
        self._record_action(result)
        return result
    
    def screenshot(
        self,
        name: Optional[str] = None,
        full_page: bool = False,
    ) -> BrowserActionResult:
        """Capture a screenshot of the current page.
        
        Args:
            name: Optional name for the screenshot file.
            full_page: Whether to capture the full scrollable page.
            
        Returns:
            BrowserActionResult with screenshot path.
        """
        start_time = time.time()
        
        screenshot_name = name or self._generate_artifact_name("screenshot", "png")
        if not screenshot_name.endswith(".png"):
            screenshot_name += ".png"
        screenshot_path = self.screenshots_dir / screenshot_name
        
        prompt = "Take a screenshot of the current page"
        if full_page:
            prompt += " (full page, including scrollable content)"
        
        exec_result = self._run_agent_browser(prompt, screenshot_path=screenshot_path)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = screenshot_path.exists()
        error = None if success else (exec_result.error or "Screenshot capture failed")
        
        result = BrowserActionResult(
            action=BrowserActionType.SCREENSHOT,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
        )
        
        self._record_action(result)
        return result
    
    def hover(
        self,
        selector_or_description: str,
    ) -> BrowserActionResult:
        """Hover over an element.
        
        Args:
            selector_or_description: CSS selector or element description.
            
        Returns:
            BrowserActionResult with hover outcome.
        """
        start_time = time.time()
        
        prompt = f"Hover over the element: {selector_or_description}"
        
        screenshot_path = self.screenshots_dir / self._generate_artifact_name("hover", "png")
        
        exec_result = self._run_agent_browser(prompt, screenshot_path=screenshot_path)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None if success else (exec_result.error or f"Hover failed: {selector_or_description}")
        
        result = BrowserActionResult(
            action=BrowserActionType.HOVER,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
        )
        
        self._record_action(result)
        return result
    
    def wait(
        self,
        text_or_selector: Optional[str] = None,
        timeout_seconds: int = 30,
    ) -> BrowserActionResult:
        """Wait for an element or text to appear.
        
        Args:
            text_or_selector: Text or CSS selector to wait for.
            timeout_seconds: Maximum time to wait.
            
        Returns:
            BrowserActionResult with wait outcome.
        """
        start_time = time.time()
        
        if text_or_selector:
            prompt = f"Wait up to {timeout_seconds} seconds for '{text_or_selector}' to appear on the page"
        else:
            prompt = f"Wait {timeout_seconds} seconds"
        
        exec_result = self._run_agent_browser(prompt, timeout=timeout_seconds + 10)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None if success else (exec_result.error or "Wait timed out")
        
        result = BrowserActionResult(
            action=BrowserActionType.WAIT,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
        )
        
        self._record_action(result)
        return result
    
    def evaluate(
        self,
        prompt: str,
    ) -> BrowserActionResult:
        """Evaluate a custom prompt/question about the page.
        
        This is useful for verification steps where you want to ask
        agent-browser to verify something specific about the UI.
        
        Args:
            prompt: The prompt/question to evaluate.
            
        Returns:
            BrowserActionResult with evaluation output.
        """
        start_time = time.time()
        
        screenshot_path = self.screenshots_dir / self._generate_artifact_name("eval", "png")
        
        exec_result = self._run_agent_browser(prompt, screenshot_path=screenshot_path)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        success = exec_result.success
        error = None if success else exec_result.error
        
        result = BrowserActionResult(
            action=BrowserActionType.EVALUATE,
            success=success,
            duration_ms=duration_ms,
            output=exec_result.output,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
        )
        
        self._record_action(result)
        return result
    
    def _capture_failure_screenshot(self, prefix: str) -> Optional[Path]:
        """Capture a screenshot on failure.
        
        Args:
            prefix: Prefix for the screenshot filename.
            
        Returns:
            Path to screenshot or None if capture failed.
        """
        try:
            screenshot_name = self._generate_artifact_name(f"failure-{prefix}", "png")
            screenshot_path = self.screenshots_dir / screenshot_name
            
            self._run_agent_browser(
                "Take a screenshot of the current page state",
                screenshot_path=screenshot_path,
                timeout=30,
            )
            
            if screenshot_path.exists():
                return screenshot_path
        except Exception:
            pass
        return None
    
    def verify_element_exists(
        self,
        selector_or_description: str,
        text: Optional[str] = None,
    ) -> BrowserActionResult:
        """Verify that an element exists on the page.
        
        Args:
            selector_or_description: CSS selector or element description.
            text: Optional text content to match.
            
        Returns:
            BrowserActionResult with verification outcome.
        """
        if text:
            prompt = f"Verify that an element matching '{selector_or_description}' with text '{text}' exists on the page. Respond with 'VERIFIED' if found, 'NOT_FOUND' if not found."
        else:
            prompt = f"Verify that an element matching '{selector_or_description}' exists on the page. Respond with 'VERIFIED' if found, 'NOT_FOUND' if not found."
        
        result = self.evaluate(prompt)
        
        # Check for verification in output
        output_lower = result.output.lower()
        if "verified" in output_lower and "not_found" not in output_lower:
            result.success = True
        elif "not_found" in output_lower or "not found" in output_lower:
            result.success = False
            result.error = f"Element not found: {selector_or_description}"
        
        return result
    
    def verify_text_visible(
        self,
        text: str,
    ) -> BrowserActionResult:
        """Verify that specific text is visible on the page.
        
        Args:
            text: Text to look for.
            
        Returns:
            BrowserActionResult with verification outcome.
        """
        prompt = f"Verify that the text '{text}' is visible on the page. Respond with 'VERIFIED' if found, 'NOT_FOUND' if not visible."
        
        result = self.evaluate(prompt)
        
        output_lower = result.output.lower()
        if "verified" in output_lower and "not_found" not in output_lower:
            result.success = True
        elif "not_found" in output_lower or "not found" in output_lower:
            result.success = False
            result.error = f"Text not visible: {text}"
        
        return result


def is_browser_use_enabled(config: RalphConfig) -> bool:
    """Check if browser-use is enabled in configuration.
    
    Args:
        config: Ralph configuration.
        
    Returns:
        True if browser-use is enabled.
    """
    ui_config = config.raw_data.get("ui", {})
    browser_use_config = ui_config.get("browser_use", {})
    return browser_use_config.get("enabled", False)


def get_browser_use_base_url(config: RalphConfig) -> Optional[str]:
    """Get the base URL for browser-use from configuration.
    
    Args:
        config: Ralph configuration.
        
    Returns:
        Base URL string or None.
    """
    ui_config = config.raw_data.get("ui", {})
    browser_use_config = ui_config.get("browser_use", {})
    return browser_use_config.get("base_url")


def create_browser_use_runner(
    config: RalphConfig,
    base_url: Optional[str] = None,
    session_dir: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
) -> BrowserUseRunner:
    """Create a BrowserUseRunner from configuration.
    
    Args:
        config: Ralph configuration.
        base_url: Override base URL (uses config value if not specified).
        session_dir: Session directory for artifacts.
        timeline: Timeline logger.
        
    Returns:
        BrowserUseRunner instance.
    """
    if base_url is None:
        base_url = get_browser_use_base_url(config) or "http://localhost:3000"
    
    if session_dir is None:
        session_dir = config.repo_root / ".ralph-session"
    
    return BrowserUseRunner(
        config=config,
        base_url=base_url,
        artifacts_dir=session_dir / "artifacts" / "browser-use",
        logs_dir=session_dir / "logs",
        timeline=timeline,
    )


def format_browser_session_summary(session: BrowserSession) -> str:
    """Format a browser session summary for display.
    
    Args:
        session: Browser session.
        
    Returns:
        Formatted summary string.
    """
    lines = [
        f"Browser Session: {session.session_id}",
        f"  Base URL: {session.base_url}",
        f"  Current URL: {session.current_url or 'N/A'}",
        f"  Actions: {session.action_count} ({session.success_count} passed, {session.failure_count} failed)",
    ]
    
    if session.actions:
        lines.append("  Recent actions:")
        for action in session.actions[-5:]:
            status = "✓" if action.success else "✗"
            suffix = f"({action.duration_ms}ms)"
            if action.error:
                suffix = f"- {action.error[:50]}..."
            lines.append(f"    {status} {action.action.value} {suffix}")
    
    latest_screenshot = session.get_latest_screenshot()
    if latest_screenshot:
        lines.append(f"  Latest screenshot: {latest_screenshot}")
    
    return "\n".join(lines)
