"""UI test runners for Ralph orchestrator.

Provides wrappers for:
- agent-browser: Claude-powered browser automation testing
- Robot Framework: Keyword-driven acceptance testing
- Robot test generation: Smart test creation and updates

Captures artifacts (screenshots, logs) to .ralph-session/artifacts/
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
        results: List[UITestResult] = []
        
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


@dataclass
class RobotTestInfo:
    """Information about an existing Robot test file."""
    path: Path
    name: str
    test_cases: List[str]
    keywords: List[str]
    pages: List[str]  # URLs or page references found in tests
    last_modified: datetime
    content_hash: str


@dataclass
class GeneratedTest:
    """A generated or updated Robot test."""
    path: Path
    content: str
    is_new: bool
    test_cases: List[str]
    description: str


class RobotTestGenerator:
    """Smart Robot Framework test generator.
    
    Scans existing Robot tests, generates new tests based on task context
    and browser exploration findings, and updates failing tests.
    
    Features:
    - Scans existing tests for affected pages/components
    - Generates new .robot files with proper structure
    - Updates failing tests based on UI exploration findings
    - Persists tests to configured robot.suite path
    """
    
    # Standard Robot Framework Browser library keywords
    BROWSER_KEYWORDS = {
        "New Page": "Open a new page with URL",
        "New Browser": "Create a new browser instance",
        "New Context": "Create a new browser context",
        "Click": "Click an element",
        "Fill Text": "Fill text into an input field",
        "Type Text": "Type text character by character",
        "Get Text": "Get text content of an element",
        "Get Title": "Get page title",
        "Get Url": "Get current page URL",
        "Wait For Elements State": "Wait for element to reach state",
        "Take Screenshot": "Capture a screenshot",
        "Get Element States": "Get all states of an element",
        "Get Element Count": "Count matching elements",
        "Get Attribute": "Get element attribute value",
        "Scroll To Element": "Scroll element into view",
        "Press Keys": "Press keyboard keys",
        "Select Options By": "Select dropdown options",
        "Check Checkbox": "Check a checkbox",
        "Uncheck Checkbox": "Uncheck a checkbox",
    }
    
    # Test file template
    TEST_FILE_TEMPLATE = '''*** Settings ***
Documentation     {documentation}
Library           Browser
Resource          common.resource
Suite Setup       Open Browser To Base URL
Suite Teardown    Close Browser

*** Variables ***
${{BASE_URL}}      {base_url}

*** Test Cases ***
{test_cases}

*** Keywords ***
Open Browser To Base URL
    New Browser    chromium    headless=true
    New Context
    New Page    ${{BASE_URL}}
'''
    
    # Common resource file template
    COMMON_RESOURCE_TEMPLATE = '''*** Settings ***
Documentation     Common keywords and variables for UI tests
Library           Browser

*** Variables ***
${BROWSER}        chromium
${HEADLESS}       true
${TIMEOUT}        30s

*** Keywords ***
Setup Browser
    New Browser    ${BROWSER}    headless=${HEADLESS}
    New Context    viewport={'width': 1280, 'height': 720}
    Set Browser Timeout    ${TIMEOUT}

Teardown Browser
    Close Browser

Navigate To
    [Arguments]    ${url}
    New Page    ${url}
    Wait For Load State    networkidle

Click Element
    [Arguments]    ${selector}
    Wait For Elements State    ${selector}    visible    timeout=10s
    Click    ${selector}

Fill Input
    [Arguments]    ${selector}    ${value}
    Wait For Elements State    ${selector}    visible    timeout=10s
    Fill Text    ${selector}    ${value}

Verify Text Visible
    [Arguments]    ${text}
    Get Text    body    contains    ${text}

Verify Element Visible
    [Arguments]    ${selector}
    Wait For Elements State    ${selector}    visible    timeout=10s

Verify Element Not Visible
    [Arguments]    ${selector}
    Wait For Elements State    ${selector}    hidden    timeout=10s

Take Failure Screenshot
    [Arguments]    ${name}=failure
    Take Screenshot    filename=${name}-{timestamp}.png
'''
    
    def __init__(
        self,
        config: RalphConfig,
        suite_path: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
    ):
        """Initialize Robot test generator.
        
        Args:
            config: Ralph configuration with robot settings.
            suite_path: Path to Robot test suite directory. 
                       Defaults to config's robot.suite or tests/robot.
            timeline: Timeline logger for tracking operations.
        """
        self.config = config
        self.timeline = timeline
        
        # Determine suite path
        if suite_path:
            self.suite_path = suite_path
        else:
            ui_config = config.raw_data.get("ui", {})
            robot_config = ui_config.get("robot", {})
            suite = robot_config.get("suite", "tests/robot")
            self.suite_path = config.resolve_path(suite)
        
        # Check if auto_generate is enabled
        ui_config = config.raw_data.get("ui", {})
        robot_config = ui_config.get("robot", {})
        self.auto_generate_enabled = robot_config.get("auto_generate", False)
        
        # Cache for scanned tests
        self._test_cache: Dict[Path, RobotTestInfo] = {}
        self._cache_valid = False
    
    def is_enabled(self) -> bool:
        """Check if auto-generation is enabled in config."""
        return self.auto_generate_enabled
    
    def ensure_suite_structure(self) -> Path:
        """Ensure the test suite directory structure exists.
        
        Creates the suite directory and common.resource if they don't exist.
        
        Returns:
            Path to the suite directory.
        """
        self.suite_path.mkdir(parents=True, exist_ok=True)
        
        # Create common.resource if it doesn't exist
        common_resource = self.suite_path / "common.resource"
        if not common_resource.exists():
            common_resource.write_text(self.COMMON_RESOURCE_TEMPLATE, encoding="utf-8")
            if self.timeline:
                self.timeline.log_info(f"Created common.resource at {common_resource}")
        
        return self.suite_path
    
    def scan_existing_tests(self, force_refresh: bool = False) -> List[RobotTestInfo]:
        """Scan the test suite for existing Robot tests.
        
        Args:
            force_refresh: Force rescan even if cache is valid.
            
        Returns:
            List of RobotTestInfo for all found test files.
        """
        if self._cache_valid and not force_refresh:
            return list(self._test_cache.values())
        
        self._test_cache.clear()
        
        if not self.suite_path.exists():
            self._cache_valid = True
            return []
        
        # Find all .robot files
        robot_files = list(self.suite_path.glob("**/*.robot"))
        
        for robot_file in robot_files:
            try:
                info = self._parse_robot_file(robot_file)
                self._test_cache[robot_file] = info
            except Exception as e:
                if self.timeline:
                    self.timeline.log_warning(f"Failed to parse {robot_file}: {e}")
        
        self._cache_valid = True
        return list(self._test_cache.values())
    
    def _parse_robot_file(self, path: Path) -> RobotTestInfo:
        """Parse a Robot Framework file to extract test information.
        
        Args:
            path: Path to the .robot file.
            
        Returns:
            RobotTestInfo with parsed information.
        """
        content = path.read_text(encoding="utf-8")
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        test_cases: List[str] = []
        keywords: List[str] = []
        pages: List[str] = []
        
        current_section = None
        
        for line in content.split("\n"):
            line_stripped = line.strip()
            
            # Detect sections
            if line_stripped.startswith("*** "):
                section_match = re.match(r"\*\*\*\s*(\w+)", line_stripped)
                if section_match:
                    current_section = section_match.group(1).lower()
                continue
            
            # Skip empty lines and comments
            if not line_stripped or line_stripped.startswith("#"):
                continue
            
            # Parse test cases section
            if current_section == "test":
                # Test case names start at column 0 (no leading whitespace)
                if not line.startswith(" ") and not line.startswith("\t"):
                    test_cases.append(line_stripped)
            
            # Parse keywords section  
            elif current_section == "keywords":
                if not line.startswith(" ") and not line.startswith("\t"):
                    # Keyword names (exclude arguments)
                    keyword_name = line_stripped.split("[")[0].strip()
                    if keyword_name:
                        keywords.append(keyword_name)
            
            # Extract URLs/pages from any section
            url_patterns = [
                r'https?://[^\s"\'<>]+',
                r'\$\{BASE_URL\}[^\s]*',
                r'New Page\s+([^\s]+)',
                r'Navigate To\s+([^\s]+)',
            ]
            for pattern in url_patterns:
                matches = re.findall(pattern, line)
                pages.extend(matches)
        
        return RobotTestInfo(
            path=path,
            name=path.stem,
            test_cases=test_cases,
            keywords=keywords,
            pages=list(set(pages)),  # Deduplicate
            last_modified=datetime.fromtimestamp(path.stat().st_mtime),
            content_hash=content_hash,
        )
    
    def find_tests_for_page(self, page_path: str) -> List[RobotTestInfo]:
        """Find existing tests that cover a specific page.
        
        Args:
            page_path: URL path or page identifier to search for.
            
        Returns:
            List of RobotTestInfo for tests covering the page.
        """
        tests = self.scan_existing_tests()
        matching = []
        
        # Normalize the page path
        page_path_normalized = page_path.strip("/").lower()
        
        for test in tests:
            for page in test.pages:
                page_normalized = page.strip("/").lower()
                # Match if the page path is contained in the test's pages
                if page_path_normalized in page_normalized or page_normalized in page_path_normalized:
                    matching.append(test)
                    break
        
        return matching
    
    def find_tests_for_component(self, component_name: str) -> List[RobotTestInfo]:
        """Find existing tests related to a component.
        
        Args:
            component_name: Component name to search for.
            
        Returns:
            List of RobotTestInfo for tests related to the component.
        """
        tests = self.scan_existing_tests()
        matching = []
        
        # Normalize component name
        component_normalized = component_name.lower().replace("-", "_").replace(" ", "_")
        
        for test in tests:
            # Check file name
            if component_normalized in test.name.lower():
                matching.append(test)
                continue
            
            # Check test case names
            for tc in test.test_cases:
                if component_normalized in tc.lower().replace(" ", "_"):
                    matching.append(test)
                    break
        
        return matching
    
    def generate_test_file(
        self,
        name: str,
        description: str,
        test_cases: List[Dict[str, Any]],
        base_url: str = "${BASE_URL}",
    ) -> GeneratedTest:
        """Generate a new Robot Framework test file.
        
        Args:
            name: Test file name (without .robot extension).
            description: Documentation for the test suite.
            test_cases: List of test case definitions, each with:
                - name: Test case name
                - steps: List of step strings (Robot keywords)
                - tags: Optional list of tags
            base_url: Base URL variable or literal.
            
        Returns:
            GeneratedTest with the generated content.
        """
        self.ensure_suite_structure()
        
        # Format test cases
        test_cases_content = []
        for tc in test_cases:
            tc_name = tc.get("name", "Unnamed Test")
            tc_steps = tc.get("steps", [])
            tc_tags = tc.get("tags", [])
            
            tc_lines = [tc_name]
            if tc_tags:
                tc_lines.append(f"    [Tags]    {' '.join(tc_tags)}")
            for step in tc_steps:
                tc_lines.append(f"    {step}")
            tc_lines.append("")  # Empty line between test cases
            
            test_cases_content.append("\n".join(tc_lines))
        
        # Generate content
        content = self.TEST_FILE_TEMPLATE.format(
            documentation=description,
            base_url=base_url,
            test_cases="\n".join(test_cases_content),
        )
        
        # Determine file path
        file_name = self._sanitize_filename(name)
        file_path = self.suite_path / f"{file_name}.robot"
        is_new = not file_path.exists()
        
        return GeneratedTest(
            path=file_path,
            content=content,
            is_new=is_new,
            test_cases=[tc.get("name", "Unnamed") for tc in test_cases],
            description=description,
        )
    
    def generate_smoke_test(
        self,
        page_name: str,
        page_url: str,
        verifications: List[Dict[str, str]],
    ) -> GeneratedTest:
        """Generate a smoke test for a page.
        
        Args:
            page_name: Human-readable page name.
            page_url: URL or path to the page.
            verifications: List of verification dicts with:
                - type: "text_visible", "element_visible", "title_contains", etc.
                - value: The value to verify
                - description: Optional description
                
        Returns:
            GeneratedTest with smoke test content.
        """
        # Generate test steps from verifications
        steps = [f"New Page    {page_url}"]
        
        for v in verifications:
            v_type = v.get("type", "text_visible")
            v_value = v.get("value", "")
            
            if v_type == "text_visible":
                steps.append(f"Get Text    body    contains    {v_value}")
            elif v_type == "element_visible":
                steps.append(f"Wait For Elements State    {v_value}    visible")
            elif v_type == "title_contains":
                steps.append(f"Get Title    contains    {v_value}")
            elif v_type == "url_contains":
                steps.append(f"Get Url    contains    {v_value}")
            elif v_type == "element_count":
                selector, count = v_value.split(":", 1) if ":" in v_value else (v_value, "1")
                steps.append(f"Get Element Count    {selector}    >=    {count}")
        
        test_case = {
            "name": f"{page_name} Smoke Test",
            "steps": steps,
            "tags": ["smoke", self._sanitize_tag(page_name)],
        }
        
        return self.generate_test_file(
            name=f"smoke_{self._sanitize_filename(page_name)}",
            description=f"Smoke tests for {page_name} page",
            test_cases=[test_case],
            base_url="${BASE_URL}",
        )
    
    def generate_acceptance_test(
        self,
        task_id: str,
        task_title: str,
        acceptance_criteria: List[str],
        page_context: Optional[Dict[str, str]] = None,
    ) -> GeneratedTest:
        """Generate acceptance tests from task acceptance criteria.
        
        Args:
            task_id: Task identifier (e.g., "T-001").
            task_title: Task title for documentation.
            acceptance_criteria: List of acceptance criteria strings.
            page_context: Optional dict with page info:
                - url: Page URL
                - selectors: Dict of named selectors
                
        Returns:
            GeneratedTest with acceptance test content.
        """
        test_cases = []
        
        for i, criterion in enumerate(acceptance_criteria, 1):
            # Generate test case name from criterion
            tc_name = self._criterion_to_test_name(criterion, i)
            
            # Generate placeholder steps
            steps = [
                "# TODO: Implement test steps for:",
                f"# {criterion}",
                "Log    Test implementation pending",
            ]
            
            # Add page context if available
            if page_context and page_context.get("url"):
                steps.insert(0, f"New Page    {page_context['url']}")
            
            test_cases.append({
                "name": tc_name,
                "steps": steps,
                "tags": ["acceptance", task_id.lower()],
            })
        
        return self.generate_test_file(
            name=f"acceptance_{task_id.lower()}",
            description=f"Acceptance tests for {task_id}: {task_title}",
            test_cases=test_cases,
        )
    
    def update_test_from_findings(
        self,
        test_info: RobotTestInfo,
        findings: Dict[str, Any],
    ) -> Optional[GeneratedTest]:
        """Update an existing test based on browser exploration findings.
        
        Args:
            test_info: Existing test information.
            findings: Dict with exploration findings:
                - selectors: Updated selectors found
                - new_elements: New elements to verify
                - removed_elements: Elements that no longer exist
                - updated_text: Text content changes
                
        Returns:
            GeneratedTest with updated content, or None if no changes needed.
        """
        content = test_info.path.read_text(encoding="utf-8")
        updated_content = content
        changes_made = False
        
        # Update selectors
        selectors = findings.get("selectors", {})
        for old_selector, new_selector in selectors.items():
            if old_selector in updated_content:
                updated_content = updated_content.replace(old_selector, new_selector)
                changes_made = True
        
        # Update text values
        updated_text = findings.get("updated_text", {})
        for old_text, new_text in updated_text.items():
            if old_text in updated_content:
                updated_content = updated_content.replace(old_text, new_text)
                changes_made = True
        
        if not changes_made:
            return None
        
        # Add comment about the update
        update_comment = f"# Updated by RobotTestGenerator on {datetime.now().isoformat()}\n"
        if not updated_content.startswith("# Updated"):
            updated_content = update_comment + updated_content
        
        return GeneratedTest(
            path=test_info.path,
            content=updated_content,
            is_new=False,
            test_cases=test_info.test_cases,
            description=f"Updated test based on UI findings",
        )
    
    def save_test(self, test: GeneratedTest) -> Path:
        """Save a generated or updated test to disk.
        
        Args:
            test: GeneratedTest to save.
            
        Returns:
            Path to the saved file.
            
        Raises:
            PermissionError: If auto_generate is not enabled.
        """
        if not self.auto_generate_enabled:
            raise PermissionError(
                "Robot test auto-generation is not enabled. "
                "Set ui.robot.auto_generate: true in ralph.yml to enable."
            )
        
        # Ensure directory exists
        test.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        test.path.write_text(test.content, encoding="utf-8")
        
        # Invalidate cache
        self._cache_valid = False
        
        if self.timeline:
            action = "Created" if test.is_new else "Updated"
            self.timeline.log_info(f"{action} Robot test: {test.path}")
        
        return test.path
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Replace spaces and special chars with underscores
        sanitized = re.sub(r"[^\w\-]", "_", name.lower())
        # Collapse multiple underscores
        sanitized = re.sub(r"_+", "_", sanitized)
        # Remove leading/trailing underscores
        return sanitized.strip("_")
    
    def _sanitize_tag(self, name: str) -> str:
        """Sanitize a string for use as a Robot tag."""
        return self._sanitize_filename(name).replace("_", "-")
    
    def _criterion_to_test_name(self, criterion: str, index: int) -> str:
        """Convert an acceptance criterion to a test case name."""
        # Extract first few meaningful words
        words = re.findall(r"\b\w+\b", criterion)[:6]
        if words:
            name = " ".join(w.capitalize() for w in words)
            return f"AC{index}: {name}"
        return f"Acceptance Criterion {index}"
    
    def get_coverage_summary(self) -> Dict[str, Any]:
        """Get a summary of test coverage.
        
        Returns:
            Dict with coverage information:
                - total_tests: Total number of test files
                - total_cases: Total number of test cases
                - pages_covered: List of pages with tests
                - last_scan: Timestamp of last scan
        """
        tests = self.scan_existing_tests()
        
        total_cases = sum(len(t.test_cases) for t in tests)
        all_pages: Set[str] = set()
        for t in tests:
            all_pages.update(t.pages)
        
        return {
            "total_tests": len(tests),
            "total_cases": total_cases,
            "pages_covered": sorted(all_pages),
            "suite_path": str(self.suite_path),
            "auto_generate_enabled": self.auto_generate_enabled,
        }


def create_robot_generator(
    config: RalphConfig,
    suite_path: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
) -> RobotTestGenerator:
    """Create a Robot Framework test generator.
    
    Args:
        config: Ralph configuration.
        suite_path: Optional override for suite path.
        timeline: Timeline logger.
        
    Returns:
        RobotTestGenerator instance.
    """
    return RobotTestGenerator(
        config=config,
        suite_path=suite_path,
        timeline=timeline,
    )


def is_robot_auto_generate_enabled(config: RalphConfig) -> bool:
    """Check if Robot Framework test auto-generation is enabled.
    
    Args:
        config: Ralph configuration.
        
    Returns:
        True if auto_generate is enabled.
    """
    ui_config = config.raw_data.get("ui", {})
    robot_config = ui_config.get("robot", {})
    return robot_config.get("auto_generate", False)


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
