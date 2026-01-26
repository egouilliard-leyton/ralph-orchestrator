"""UI test runners for Ralph orchestrator.

Provides wrappers for:
- agent-browser: Claude-powered browser automation testing
- Robot Framework: Keyword-driven acceptance testing

Captures artifacts (screenshots, logs) to .ralph-session/artifacts/
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import RalphConfig
from .exec import run_command, ExecResult
from .timeline import TimelineLogger


@dataclass
class UITestResult:
    """Result of a single UI test."""
    name: str
    passed: bool
    duration_ms: int
    error: Optional[str] = None
    screenshot_path: Optional[Path] = None
    log_path: Optional[Path] = None
    output: str = ""


@dataclass
class UITestSuiteResult:
    """Result of running a UI test suite."""
    framework: str  # "agent_browser" or "robot"
    passed: bool
    results: List[UITestResult] = field(default_factory=list)
    total_duration_ms: int = 0
    artifacts_dir: Optional[Path] = None
    
    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    def get_failures(self) -> List[UITestResult]:
        """Get all failed test results."""
        return [r for r in self.results if not r.passed]


class AgentBrowserRunner:
    """Runner for agent-browser UI tests.
    
    agent-browser is a Claude-powered browser automation tool that can
    execute natural language test instructions.
    """
    
    def __init__(
        self,
        config: RalphConfig,
        base_url: str,
        artifacts_dir: Optional[Path] = None,
        logs_dir: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
    ):
        """Initialize agent-browser runner.
        
        Args:
            config: Ralph configuration with agent_browser settings.
            base_url: Base URL for tests.
            artifacts_dir: Directory for test artifacts.
            logs_dir: Directory for test logs.
            timeline: Timeline logger.
        """
        self.config = config
        self.base_url = base_url
        self.artifacts_dir = artifacts_dir or Path(".ralph-session/artifacts/agent-browser")
        self.logs_dir = logs_dir or Path(".ralph-session/logs")
        self.timeline = timeline
        
        # Ensure directories exist
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = self.artifacts_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_tests(self) -> List[Dict[str, str]]:
        """Get test definitions from config.
        
        Returns:
            List of test dicts with name, action, expected.
        """
        ui_config = self.config.raw_data.get("ui", {})
        ab_config = ui_config.get("agent_browser", {})
        
        tests = ab_config.get("tests", [])
        return tests
    
    def _get_script_path(self) -> Optional[Path]:
        """Get path to agent-browser test script if configured."""
        ui_config = self.config.raw_data.get("ui", {})
        ab_config = ui_config.get("agent_browser", {})
        
        script = ab_config.get("script")
        if script:
            return self.config.resolve_path(script)
        return None
    
    def _run_single_test(
        self,
        test: Dict[str, str],
    ) -> UITestResult:
        """Run a single agent-browser test.
        
        Args:
            test: Test definition with name, action, expected.
            
        Returns:
            UITestResult with outcome.
        """
        name = test.get("name", "unnamed_test")
        action = test.get("action", "")
        expected = test.get("expected", "")
        
        start_time = time.time()
        
        # Log start
        if self.timeline:
            self.timeline.ui_test_start(name, "agent_browser")
        
        # Build agent-browser command
        # agent-browser runs a prompt that navigates and verifies
        prompt = f"""Navigate to {self.base_url} and perform this action:
{action}

Expected result: {expected}

If the expected result is verified, respond with: TEST_PASSED
If the expected result is NOT verified, respond with: TEST_FAILED: <reason>
"""
        
        log_path = self.logs_dir / f"agent-browser-{name}.log"
        screenshot_path = self.screenshots_dir / f"{name}.png"
        
        # Run agent-browser
        result = run_command(
            ["agent-browser", "-p", prompt, "--screenshot", str(screenshot_path)],
            cwd=self.config.repo_root,
            timeout=120,
            log_path=log_path,
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Parse result
        output = result.output
        passed = "TEST_PASSED" in output and "TEST_FAILED" not in output
        
        error = None
        if not passed:
            # Extract failure reason
            match = re.search(r"TEST_FAILED:\s*(.+)", output)
            if match:
                error = match.group(1).strip()
            elif result.error:
                error = result.error
            else:
                error = "Test did not pass verification"
        
        # Log result
        if self.timeline:
            if passed:
                self.timeline.ui_test_pass(name, duration_ms)
            else:
                self.timeline.ui_test_fail(
                    name,
                    error or "Unknown failure",
                    screenshot=str(screenshot_path) if screenshot_path.exists() else None,
                    duration_ms=duration_ms,
                )
        
        return UITestResult(
            name=name,
            passed=passed,
            duration_ms=duration_ms,
            error=error,
            screenshot_path=screenshot_path if screenshot_path.exists() else None,
            log_path=log_path,
            output=output,
        )
    
    def _run_script(self) -> UITestSuiteResult:
        """Run agent-browser test script.
        
        Returns:
            UITestSuiteResult with all test outcomes.
        """
        script_path = self._get_script_path()
        if not script_path or not script_path.exists():
            return UITestSuiteResult(
                framework="agent_browser",
                passed=False,
                results=[UITestResult(
                    name="script",
                    passed=False,
                    duration_ms=0,
                    error=f"Script not found: {script_path}",
                )],
            )
        
        start_time = time.time()
        log_path = self.logs_dir / "agent-browser-script.log"
        
        # Run the script
        result = run_command(
            ["bash", str(script_path)],
            cwd=self.config.repo_root,
            timeout=600,
            log_path=log_path,
            env={"BASE_URL": self.base_url},
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Script exit code determines pass/fail
        passed = result.success
        
        return UITestSuiteResult(
            framework="agent_browser",
            passed=passed,
            results=[UITestResult(
                name="script",
                passed=passed,
                duration_ms=duration_ms,
                error=result.error if not passed else None,
                log_path=log_path,
                output=result.output,
            )],
            total_duration_ms=duration_ms,
            artifacts_dir=self.artifacts_dir,
        )
    
    def run(self) -> UITestSuiteResult:
        """Run all agent-browser tests.
        
        Returns:
            UITestSuiteResult with all test outcomes.
        """
        start_time = time.time()
        
        # Check if script mode
        if self._get_script_path():
            return self._run_script()
        
        # Run inline tests
        tests = self._get_tests()
        if not tests:
            return UITestSuiteResult(
                framework="agent_browser",
                passed=True,
                results=[],
                artifacts_dir=self.artifacts_dir,
            )
        
        results = []
        all_passed = True
        
        for test in tests:
            result = self._run_single_test(test)
            results.append(result)
            if not result.passed:
                all_passed = False
        
        total_duration_ms = int((time.time() - start_time) * 1000)
        
        return UITestSuiteResult(
            framework="agent_browser",
            passed=all_passed,
            results=results,
            total_duration_ms=total_duration_ms,
            artifacts_dir=self.artifacts_dir,
        )


class RobotRunner:
    """Runner for Robot Framework tests.
    
    Robot Framework is a keyword-driven testing framework that can be
    used for acceptance testing and UI testing with Browser library.
    """
    
    def __init__(
        self,
        config: RalphConfig,
        base_url: str,
        artifacts_dir: Optional[Path] = None,
        logs_dir: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
    ):
        """Initialize Robot Framework runner.
        
        Args:
            config: Ralph configuration with robot settings.
            base_url: Base URL for tests.
            artifacts_dir: Directory for test artifacts.
            logs_dir: Directory for test logs.
            timeline: Timeline logger.
        """
        self.config = config
        self.base_url = base_url
        self.artifacts_dir = artifacts_dir or Path(".ralph-session/artifacts/robot")
        self.logs_dir = logs_dir or Path(".ralph-session/logs")
        self.timeline = timeline
        
        # Ensure directories exist
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_suite_path(self) -> Optional[Path]:
        """Get path to Robot test suite."""
        ui_config = self.config.raw_data.get("ui", {})
        robot_config = ui_config.get("robot", {})
        
        suite = robot_config.get("suite")
        if suite:
            return self.config.resolve_path(suite)
        
        # Default locations
        for default in ["robot", "tests/robot", "tests/acceptance"]:
            path = self.config.repo_root / default
            if path.exists():
                return path
        
        return None
    
    def _get_variables(self) -> Dict[str, str]:
        """Get Robot variables from config."""
        ui_config = self.config.raw_data.get("ui", {})
        robot_config = ui_config.get("robot", {})
        
        variables = robot_config.get("variables", {})
        # Always include base URL
        variables["BASE_URL"] = self.base_url
        variables["BROWSER"] = "chromium"
        
        return variables
    
    def _parse_robot_output(self, output_xml: Path) -> List[UITestResult]:
        """Parse Robot Framework output.xml for test results.
        
        Args:
            output_xml: Path to output.xml file.
            
        Returns:
            List of test results.
        """
        results = []
        
        if not output_xml.exists():
            return results
        
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(output_xml)
            root = tree.getroot()
            
            # Find all test elements
            for test in root.iter("test"):
                name = test.get("name", "unknown")
                
                # Find status element
                status_elem = test.find("status")
                if status_elem is not None:
                    status = status_elem.get("status", "FAIL")
                    passed = status == "PASS"
                    
                    # Calculate duration from starttime/endtime if available
                    starttime = status_elem.get("starttime", "")
                    endtime = status_elem.get("endtime", "")
                    duration_ms = 0
                    if starttime and endtime:
                        try:
                            from datetime import datetime
                            start = datetime.strptime(starttime, "%Y%m%d %H:%M:%S.%f")
                            end = datetime.strptime(endtime, "%Y%m%d %H:%M:%S.%f")
                            duration_ms = int((end - start).total_seconds() * 1000)
                        except ValueError:
                            pass
                    
                    error = None
                    if not passed:
                        # Get error message
                        for msg in test.iter("msg"):
                            if msg.get("level") in ("FAIL", "ERROR"):
                                error = msg.text
                                break
                    
                    results.append(UITestResult(
                        name=name,
                        passed=passed,
                        duration_ms=duration_ms,
                        error=error,
                    ))
        except Exception as e:
            results.append(UITestResult(
                name="parse_error",
                passed=False,
                duration_ms=0,
                error=f"Failed to parse output.xml: {e}",
            ))
        
        return results
    
    def run(self) -> UITestSuiteResult:
        """Run Robot Framework tests.
        
        Returns:
            UITestSuiteResult with all test outcomes.
        """
        start_time = time.time()
        
        suite_path = self._get_suite_path()
        if not suite_path:
            return UITestSuiteResult(
                framework="robot",
                passed=False,
                results=[UITestResult(
                    name="suite",
                    passed=False,
                    duration_ms=0,
                    error="No Robot Framework test suite configured or found",
                )],
            )
        
        # Build command
        cmd = ["robot"]
        
        # Add variables
        for name, value in self._get_variables().items():
            cmd.extend(["--variable", f"{name}:{value}"])
        
        # Output settings
        output_dir = self.artifacts_dir
        cmd.extend([
            "--outputdir", str(output_dir),
            "--output", "output.xml",
            "--log", "log.html",
            "--report", "report.html",
        ])
        
        # Add suite path
        cmd.append(str(suite_path))
        
        # Log start
        if self.timeline:
            self.timeline.ui_test_start("robot_suite", "robot")
        
        # Run Robot Framework
        log_path = self.logs_dir / "robot.log"
        result = run_command(
            cmd,
            cwd=self.config.repo_root,
            timeout=600,
            log_path=log_path,
        )
        
        total_duration_ms = int((time.time() - start_time) * 1000)
        
        # Parse results from output.xml
        output_xml = output_dir / "output.xml"
        test_results = self._parse_robot_output(output_xml)
        
        # If no results parsed, create one from exit code
        if not test_results:
            test_results = [UITestResult(
                name="robot_suite",
                passed=result.success,
                duration_ms=total_duration_ms,
                error=result.error if not result.success else None,
                log_path=log_path,
                output=result.output,
            )]
        
        # Log results
        all_passed = all(r.passed for r in test_results)
        for test_result in test_results:
            if self.timeline:
                if test_result.passed:
                    self.timeline.ui_test_pass(test_result.name, test_result.duration_ms)
                else:
                    self.timeline.ui_test_fail(
                        test_result.name,
                        test_result.error or "Test failed",
                        duration_ms=test_result.duration_ms,
                    )
        
        return UITestSuiteResult(
            framework="robot",
            passed=all_passed,
            results=test_results,
            total_duration_ms=total_duration_ms,
            artifacts_dir=output_dir,
        )


def is_agent_browser_enabled(config: RalphConfig) -> bool:
    """Check if agent-browser testing is enabled.
    
    Args:
        config: Ralph configuration.
        
    Returns:
        True if agent-browser is enabled.
    """
    ui_config = config.raw_data.get("ui", {})
    ab_config = ui_config.get("agent_browser", {})
    return ab_config.get("enabled", False)


def is_robot_enabled(config: RalphConfig) -> bool:
    """Check if Robot Framework testing is enabled.
    
    Args:
        config: Ralph configuration.
        
    Returns:
        True if Robot is enabled.
    """
    ui_config = config.raw_data.get("ui", {})
    robot_config = ui_config.get("robot", {})
    return robot_config.get("enabled", False)


def create_agent_browser_runner(
    config: RalphConfig,
    base_url: str,
    session_dir: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
) -> AgentBrowserRunner:
    """Create an agent-browser test runner.
    
    Args:
        config: Ralph configuration.
        base_url: Base URL for tests.
        session_dir: Session directory.
        timeline: Timeline logger.
        
    Returns:
        AgentBrowserRunner instance.
    """
    if session_dir is None:
        session_dir = config.repo_root / ".ralph-session"
    
    return AgentBrowserRunner(
        config=config,
        base_url=base_url,
        artifacts_dir=session_dir / "artifacts" / "agent-browser",
        logs_dir=session_dir / "logs",
        timeline=timeline,
    )


def create_robot_runner(
    config: RalphConfig,
    base_url: str,
    session_dir: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
) -> RobotRunner:
    """Create a Robot Framework test runner.
    
    Args:
        config: Ralph configuration.
        base_url: Base URL for tests.
        session_dir: Session directory.
        timeline: Timeline logger.
        
    Returns:
        RobotRunner instance.
    """
    if session_dir is None:
        session_dir = config.repo_root / ".ralph-session"
    
    return RobotRunner(
        config=config,
        base_url=base_url,
        artifacts_dir=session_dir / "artifacts" / "robot",
        logs_dir=session_dir / "logs",
        timeline=timeline,
    )


def format_ui_test_summary(result: UITestSuiteResult) -> str:
    """Format UI test results for display.
    
    Args:
        result: Test suite result.
        
    Returns:
        Formatted summary string.
    """
    framework_name = "Agent-Browser" if result.framework == "agent_browser" else "Robot Framework"
    
    lines = [
        f"  {framework_name}: {result.passed_count}/{len(result.results)} passed "
        f"({result.total_duration_ms}ms)"
    ]
    
    for test in result.results:
        if test.passed:
            status = "✓"
            suffix = f"({test.duration_ms}ms)"
        else:
            status = "✗"
            suffix = f"- {test.error}" if test.error else "(failed)"
        
        lines.append(f"    {status} {test.name} {suffix}")
    
    return "\n".join(lines)


def format_failure_description(result: UITestResult, framework: str) -> str:
    """Format a UI test failure for fix planning.
    
    Args:
        result: Failed test result.
        framework: Test framework name.
        
    Returns:
        Formatted failure description.
    """
    lines = [
        f"## {framework} Test Failure: {result.name}",
        "",
    ]
    
    if result.error:
        lines.extend([
            "### Error",
            result.error,
            "",
        ])
    
    if result.screenshot_path and result.screenshot_path.exists():
        lines.extend([
            "### Screenshot",
            f"Failure screenshot available at: {result.screenshot_path}",
            "",
        ])
    
    if result.output:
        lines.extend([
            "### Test Output",
            "```",
            result.output[:2000] if len(result.output) > 2000 else result.output,
            "```" if len(result.output) <= 2000 else "```\n... (truncated)",
            "",
        ])
    
    if result.log_path and result.log_path.exists():
        lines.extend([
            "### Log File",
            f"Full log available at: {result.log_path}",
        ])
    
    return "\n".join(lines)
