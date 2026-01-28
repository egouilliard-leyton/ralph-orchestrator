"""Unit tests for UI testing components.

Tests for:
- BrowserUseRunner: Browser automation wrapper using agent-browser CLI
- RobotTestGenerator: Smart Robot Framework test generation
- UI testing orchestration: Integration with OrchestrationService
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest


# ============================================================================
# BrowserUseRunner Tests
# ============================================================================


class TestBrowserActionResult:
    """Tests for BrowserActionResult data class."""

    def test_basic_action_result(self):
        """BrowserActionResult has correct fields."""
        from ralph_orchestrator.browser_use import BrowserActionResult, BrowserActionType

        result = BrowserActionResult(
            action=BrowserActionType.CLICK,
            success=True,
            duration_ms=150,
            output="Clicked button successfully",
        )

        assert result.action == BrowserActionType.CLICK
        assert result.success is True
        assert result.duration_ms == 150
        assert result.output == "Clicked button successfully"
        assert result.error is None
        assert result.screenshot_path is None

    def test_failed_action_result(self):
        """Failed action result includes error."""
        from ralph_orchestrator.browser_use import BrowserActionResult, BrowserActionType

        result = BrowserActionResult(
            action=BrowserActionType.TYPE,
            success=False,
            duration_ms=200,
            output="",
            error="Element not found: input[name='email']",
        )

        assert result.success is False
        assert result.error == "Element not found: input[name='email']"

    def test_action_result_with_screenshot(self, tmp_path):
        """Action result includes screenshot path when available."""
        from ralph_orchestrator.browser_use import BrowserActionResult, BrowserActionType

        screenshot = tmp_path / "screenshot.png"
        screenshot.write_bytes(b"PNG data")

        result = BrowserActionResult(
            action=BrowserActionType.SCREENSHOT,
            success=True,
            duration_ms=50,
            output="",
            screenshot_path=screenshot,
        )

        assert result.screenshot_path == screenshot

    def test_action_result_to_dict(self):
        """to_dict serializes correctly."""
        from ralph_orchestrator.browser_use import BrowserActionResult, BrowserActionType

        result = BrowserActionResult(
            action=BrowserActionType.OPEN,
            success=True,
            duration_ms=1000,
            output="Navigated to page",
        )

        data = result.to_dict()

        assert data["action"] == "open"
        assert data["success"] is True
        assert data["duration_ms"] == 1000
        assert data["output"] == "Navigated to page"

    def test_action_result_truncates_long_output(self):
        """to_dict truncates very long output."""
        from ralph_orchestrator.browser_use import BrowserActionResult, BrowserActionType

        long_output = "x" * 1000
        result = BrowserActionResult(
            action=BrowserActionType.EVALUATE,
            success=True,
            duration_ms=100,
            output=long_output,
        )

        data = result.to_dict()
        assert len(data["output"]) <= 500


class TestBrowserSession:
    """Tests for BrowserSession data class."""

    def test_session_creation(self):
        """BrowserSession initializes correctly."""
        from ralph_orchestrator.browser_use import BrowserSession

        session = BrowserSession(
            session_id="browser-20260127-120000-abcd1234",
            base_url="http://localhost:3000",
        )

        assert session.session_id == "browser-20260127-120000-abcd1234"
        assert session.base_url == "http://localhost:3000"
        assert session.current_url is None
        assert session.action_count == 0
        assert session.actions == []

    def test_session_action_counts(self):
        """Session tracks action counts correctly."""
        from ralph_orchestrator.browser_use import (
            BrowserSession,
            BrowserActionResult,
            BrowserActionType,
        )

        session = BrowserSession(
            session_id="test-session",
            base_url="http://localhost:3000",
        )

        # Add some actions
        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.OPEN,
                success=True,
                duration_ms=100,
            )
        )
        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.CLICK,
                success=False,
                duration_ms=50,
                error="Not found",
            )
        )
        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.TYPE,
                success=True,
                duration_ms=75,
            )
        )

        assert session.action_count == 3
        assert session.success_count == 2
        assert session.failure_count == 1

    def test_session_get_latest_screenshot(self, tmp_path):
        """get_latest_screenshot returns most recent screenshot."""
        from ralph_orchestrator.browser_use import (
            BrowserSession,
            BrowserActionResult,
            BrowserActionType,
        )

        session = BrowserSession(
            session_id="test-session",
            base_url="http://localhost:3000",
        )

        # Create screenshots
        old_screenshot = tmp_path / "old.png"
        old_screenshot.write_bytes(b"old")
        new_screenshot = tmp_path / "new.png"
        new_screenshot.write_bytes(b"new")

        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.SCREENSHOT,
                success=True,
                duration_ms=50,
                screenshot_path=old_screenshot,
            )
        )
        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.CLICK,
                success=True,
                duration_ms=25,
            )
        )
        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.SCREENSHOT,
                success=True,
                duration_ms=50,
                screenshot_path=new_screenshot,
            )
        )

        assert session.get_latest_screenshot() == new_screenshot

    def test_session_get_latest_screenshot_none_when_no_screenshots(self):
        """get_latest_screenshot returns None when no screenshots exist."""
        from ralph_orchestrator.browser_use import BrowserSession

        session = BrowserSession(
            session_id="test-session",
            base_url="http://localhost:3000",
        )

        assert session.get_latest_screenshot() is None


class TestBrowserUseRunner:
    """Tests for BrowserUseRunner class."""

    def _create_mock_config(self, tmp_path, browser_use_config=None):
        """Create a mock RalphConfig for testing."""
        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {
            "ui": {
                "browser_use": browser_use_config or {
                    "enabled": True,
                    "base_url": "http://localhost:3000",
                    "timeout": 120,
                    "screenshot_on_failure": True,
                }
            }
        }
        return config

    def test_runner_initialization(self, tmp_path):
        """Runner initializes with correct defaults."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
            logs_dir=tmp_path / "logs",
        )

        assert runner.base_url == "http://localhost:3000"
        assert runner.timeout == 120
        assert runner.screenshot_on_failure is True
        assert runner.session is None

    def test_runner_strips_trailing_slash_from_url(self, tmp_path):
        """Runner strips trailing slash from base URL."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000/",
        )

        assert runner.base_url == "http://localhost:3000"

    def test_runner_creates_directories(self, tmp_path):
        """Runner creates artifact directories on init."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        artifacts = tmp_path / "new_artifacts"
        logs = tmp_path / "new_logs"

        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=artifacts,
            logs_dir=logs,
        )

        assert artifacts.exists()
        assert logs.exists()
        assert (artifacts / "screenshots").exists()
        assert (artifacts / "snapshots").exists()

    def test_start_session(self, tmp_path):
        """start_session creates new BrowserSession."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )

        session = runner.start_session()

        assert session is not None
        assert session.base_url == "http://localhost:3000"
        assert session.session_id.startswith("browser-")
        assert session.started_at is not None
        assert runner.session == session

    def test_end_session(self, tmp_path):
        """end_session writes summary and clears session."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )

        session = runner.start_session()
        session_id = session.session_id

        ended_session = runner.end_session()

        assert ended_session.session_id == session_id
        assert runner.session is None
        
        # Check summary file was created
        summary_path = ended_session.artifacts_dir / "session-summary.json"
        assert summary_path.exists()
        
        summary = json.loads(summary_path.read_text())
        assert summary["session_id"] == session_id
        assert summary["base_url"] == "http://localhost:3000"

    def test_end_session_when_no_session(self, tmp_path):
        """end_session returns None when no active session."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
        )

        result = runner.end_session()

        assert result is None

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_open_navigates_to_url(self, mock_run, tmp_path):
        """open() navigates to specified URL."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Navigation successful",
            stderr="",
            duration_ms=500,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.open("/dashboard")

        assert result.success is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        prompt = call_args[0][0][2]  # Third arg of command list is prompt
        assert "http://localhost:3000/dashboard" in prompt

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_open_handles_full_url(self, mock_run, tmp_path):
        """open() handles full URLs correctly."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Navigation successful",
            stderr="",
            duration_ms=500,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.open("https://example.com/page")

        assert result.success is True
        call_args = mock_run.call_args
        prompt = call_args[0][0][2]
        assert "https://example.com/page" in prompt

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_click_action(self, mock_run, tmp_path):
        """click() performs click action."""
        from ralph_orchestrator.browser_use import BrowserUseRunner, BrowserActionType
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Clicked successfully",
            stderr="",
            duration_ms=100,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.click("button.submit")

        assert result.action == BrowserActionType.CLICK
        assert result.success is True

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_click_with_text(self, mock_run, tmp_path):
        """click() includes text in prompt when specified."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Clicked",
            stderr="",
            duration_ms=100,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        runner.click("button", text="Submit")

        call_args = mock_run.call_args
        prompt = call_args[0][0][2]
        assert "Submit" in prompt

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_type_action(self, mock_run, tmp_path):
        """type() types text into element."""
        from ralph_orchestrator.browser_use import BrowserUseRunner, BrowserActionType
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Typed text",
            stderr="",
            duration_ms=150,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.type("input[name='email']", "test@example.com")

        assert result.action == BrowserActionType.TYPE
        assert result.success is True

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_screenshot_action(self, mock_run, tmp_path):
        """screenshot() captures page screenshot."""
        from ralph_orchestrator.browser_use import BrowserUseRunner, BrowserActionType
        from ralph_orchestrator.exec import ExecResult

        # Create a mock screenshot file
        def create_screenshot(*args, **kwargs):
            screenshot_arg = next(
                (args[0][i+1] for i, arg in enumerate(args[0]) if arg == "--screenshot"),
                None
            )
            if screenshot_arg:
                Path(screenshot_arg).write_bytes(b"PNG data")
            return ExecResult(
                command="agent-browser",
                exit_code=0,
                stdout="Screenshot taken",
                stderr="",
                duration_ms=50,
            )

        mock_run.side_effect = create_screenshot

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.screenshot("test-screenshot")

        assert result.action == BrowserActionType.SCREENSHOT
        assert result.success is True
        assert result.screenshot_path is not None

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_verify_element_exists_success(self, mock_run, tmp_path):
        """verify_element_exists() returns success when element found."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Element found. VERIFIED",
            stderr="",
            duration_ms=100,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.verify_element_exists("button.submit")

        assert result.success is True

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_verify_element_exists_failure(self, mock_run, tmp_path):
        """verify_element_exists() returns failure when element not found."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Element NOT_FOUND on the page",
            stderr="",
            duration_ms=100,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.verify_element_exists("button.nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_verify_text_visible(self, mock_run, tmp_path):
        """verify_text_visible() checks for visible text."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Text is visible. VERIFIED",
            stderr="",
            duration_ms=100,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        result = runner.verify_text_visible("Welcome to Dashboard")

        assert result.success is True

    def test_is_available_checks_command(self, tmp_path):
        """is_available checks if agent-browser CLI exists."""
        from ralph_orchestrator.browser_use import BrowserUseRunner

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
        )

        with patch("ralph_orchestrator.browser_use.check_command_exists") as mock_check:
            mock_check.return_value = True
            assert runner.is_available is True

            mock_check.return_value = False
            assert runner.is_available is False

    @patch("ralph_orchestrator.browser_use.run_command")
    def test_actions_recorded_in_session(self, mock_run, tmp_path):
        """Actions are recorded in the session."""
        from ralph_orchestrator.browser_use import BrowserUseRunner
        from ralph_orchestrator.exec import ExecResult

        mock_run.return_value = ExecResult(
            command="agent-browser",
            exit_code=0,
            stdout="Success",
            stderr="",
            duration_ms=100,
        )

        config = self._create_mock_config(tmp_path)
        runner = BrowserUseRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )
        runner.start_session()

        runner.open("/page1")
        runner.click("button")
        runner.type("input", "text")

        assert runner.session.action_count == 3
        assert runner.session.success_count == 3


class TestBrowserUseHelperFunctions:
    """Tests for browser_use module helper functions."""

    def test_is_browser_use_enabled_true(self):
        """is_browser_use_enabled returns True when enabled."""
        from ralph_orchestrator.browser_use import is_browser_use_enabled

        config = Mock()
        config.raw_data = {
            "ui": {
                "browser_use": {
                    "enabled": True,
                }
            }
        }

        assert is_browser_use_enabled(config) is True

    def test_is_browser_use_enabled_false(self):
        """is_browser_use_enabled returns False when disabled."""
        from ralph_orchestrator.browser_use import is_browser_use_enabled

        config = Mock()
        config.raw_data = {"ui": {"browser_use": {"enabled": False}}}

        assert is_browser_use_enabled(config) is False

    def test_is_browser_use_enabled_missing(self):
        """is_browser_use_enabled returns False when not configured."""
        from ralph_orchestrator.browser_use import is_browser_use_enabled

        config = Mock()
        config.raw_data = {}

        assert is_browser_use_enabled(config) is False

    def test_get_browser_use_base_url(self):
        """get_browser_use_base_url returns configured URL."""
        from ralph_orchestrator.browser_use import get_browser_use_base_url

        config = Mock()
        config.raw_data = {
            "ui": {
                "browser_use": {
                    "base_url": "http://localhost:8080",
                }
            }
        }

        assert get_browser_use_base_url(config) == "http://localhost:8080"

    def test_create_browser_use_runner(self, tmp_path):
        """create_browser_use_runner creates properly configured runner."""
        from ralph_orchestrator.browser_use import create_browser_use_runner

        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {
            "ui": {
                "browser_use": {
                    "enabled": True,
                    "base_url": "http://localhost:3000",
                    "timeout": 60,
                }
            }
        }

        runner = create_browser_use_runner(config, session_dir=tmp_path / "session")

        assert runner.base_url == "http://localhost:3000"
        assert runner.timeout == 60

    def test_format_browser_session_summary(self):
        """format_browser_session_summary formats session correctly."""
        from ralph_orchestrator.browser_use import (
            format_browser_session_summary,
            BrowserSession,
            BrowserActionResult,
            BrowserActionType,
        )

        session = BrowserSession(
            session_id="browser-test-123",
            base_url="http://localhost:3000",
            current_url="http://localhost:3000/dashboard",
        )
        session.actions.append(
            BrowserActionResult(
                action=BrowserActionType.OPEN,
                success=True,
                duration_ms=500,
            )
        )

        summary = format_browser_session_summary(session)

        assert "browser-test-123" in summary
        assert "localhost:3000" in summary
        assert "1 passed" in summary


# ============================================================================
# RobotTestGenerator Tests
# ============================================================================


class TestRobotTestInfo:
    """Tests for RobotTestInfo data class."""

    def test_robot_test_info_creation(self, tmp_path):
        """RobotTestInfo holds test file information."""
        from ralph_orchestrator.ui import RobotTestInfo

        info = RobotTestInfo(
            path=tmp_path / "test_login.robot",
            name="test_login",
            test_cases=["Login With Valid Credentials", "Login With Invalid Credentials"],
            keywords=["Login To System", "Verify Dashboard"],
            pages=["${BASE_URL}/login", "${BASE_URL}/dashboard"],
            last_modified=datetime.now(),
            content_hash="abc123",
        )

        assert info.name == "test_login"
        assert len(info.test_cases) == 2
        assert len(info.keywords) == 2
        assert len(info.pages) == 2


class TestGeneratedTest:
    """Tests for GeneratedTest data class."""

    def test_generated_test_creation(self, tmp_path):
        """GeneratedTest holds generated test data."""
        from ralph_orchestrator.ui import GeneratedTest

        test = GeneratedTest(
            path=tmp_path / "new_test.robot",
            content="*** Test Cases ***\nTest 1\n    Log    Hello",
            is_new=True,
            test_cases=["Test 1"],
            description="A new test file",
        )

        assert test.is_new is True
        assert len(test.test_cases) == 1
        assert "Hello" in test.content


class TestRobotTestGenerator:
    """Tests for RobotTestGenerator class."""

    def _create_mock_config(self, tmp_path, auto_generate=True):
        """Create a mock RalphConfig for testing."""
        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {
            "ui": {
                "robot": {
                    "enabled": True,
                    "suite": "tests/robot",
                    "auto_generate": auto_generate,
                }
            }
        }
        config.resolve_path = lambda p: tmp_path / p
        return config

    def test_generator_initialization(self, tmp_path):
        """Generator initializes with correct defaults."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)

        assert generator.suite_path == tmp_path / "tests" / "robot"
        assert generator.auto_generate_enabled is True

    def test_generator_with_custom_suite_path(self, tmp_path):
        """Generator uses custom suite path when provided."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        custom_path = tmp_path / "custom_tests"

        generator = RobotTestGenerator(config=config, suite_path=custom_path)

        assert generator.suite_path == custom_path

    def test_is_enabled(self, tmp_path):
        """is_enabled reflects auto_generate setting."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config_enabled = self._create_mock_config(tmp_path, auto_generate=True)
        config_disabled = self._create_mock_config(tmp_path, auto_generate=False)

        gen_enabled = RobotTestGenerator(config=config_enabled)
        gen_disabled = RobotTestGenerator(config=config_disabled)

        assert gen_enabled.is_enabled() is True
        assert gen_disabled.is_enabled() is False

    def test_ensure_suite_structure(self, tmp_path):
        """ensure_suite_structure creates directory and common.resource."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)

        suite_path = generator.ensure_suite_structure()

        assert suite_path.exists()
        assert (suite_path / "common.resource").exists()
        
        # Check common.resource has expected content
        content = (suite_path / "common.resource").read_text()
        assert "Library" in content
        assert "Browser" in content

    def test_scan_existing_tests_empty(self, tmp_path):
        """scan_existing_tests returns empty list when no tests exist."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)

        tests = generator.scan_existing_tests()

        assert tests == []

    def test_scan_existing_tests_finds_robot_files(self, tmp_path):
        """scan_existing_tests finds all .robot files."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)
        
        # Create test suite directory and files
        generator.ensure_suite_structure()
        
        test_file = generator.suite_path / "test_login.robot"
        test_file.write_text("""*** Settings ***
Documentation    Login tests

*** Test Cases ***
Login With Valid Credentials
    Log    Test step

*** Keywords ***
Custom Keyword
    Log    Keyword step
""")

        tests = generator.scan_existing_tests()

        assert len(tests) == 1
        assert tests[0].name == "test_login"
        assert "Login With Valid Credentials" in tests[0].test_cases
        assert "Custom Keyword" in tests[0].keywords

    def test_find_tests_for_page(self, tmp_path):
        """find_tests_for_page returns tests covering a specific page."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)
        generator.ensure_suite_structure()

        # Create test file with page reference
        test_file = generator.suite_path / "test_dashboard.robot"
        test_file.write_text("""*** Test Cases ***
Dashboard Loads
    New Page    ${BASE_URL}/dashboard
    Log    Test
""")

        tests = generator.find_tests_for_page("/dashboard")

        assert len(tests) == 1
        assert tests[0].name == "test_dashboard"

    def test_find_tests_for_component(self, tmp_path):
        """find_tests_for_component returns tests related to a component."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)
        generator.ensure_suite_structure()

        # Create test file with component name
        test_file = generator.suite_path / "test_login_form.robot"
        test_file.write_text("""*** Test Cases ***
Login Form Displays Correctly
    Log    Test
""")

        tests = generator.find_tests_for_component("login-form")

        assert len(tests) == 1

    def test_generate_test_file(self, tmp_path):
        """generate_test_file creates Robot test file content."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)

        test = generator.generate_test_file(
            name="login_tests",
            description="Login page tests",
            test_cases=[
                {
                    "name": "Login With Valid Credentials",
                    "steps": [
                        "New Page    ${BASE_URL}/login",
                        "Fill Text    id=username    testuser",
                        "Click    button[type='submit']",
                    ],
                    "tags": ["smoke", "login"],
                }
            ],
        )

        assert test.path == generator.suite_path / "login_tests.robot"
        assert "Login With Valid Credentials" in test.content
        assert "[Tags]" in test.content
        assert "smoke" in test.content
        assert "Fill Text" in test.content

    def test_generate_smoke_test(self, tmp_path):
        """generate_smoke_test creates smoke test for a page."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)

        test = generator.generate_smoke_test(
            page_name="Dashboard",
            page_url="${BASE_URL}/dashboard",
            verifications=[
                {"type": "text_visible", "value": "Welcome"},
                {"type": "element_visible", "value": "button.logout"},
            ],
        )

        assert "Dashboard Smoke Test" in test.content
        assert "smoke" in test.content
        assert "Welcome" in test.content
        assert "button.logout" in test.content

    def test_generate_acceptance_test(self, tmp_path):
        """generate_acceptance_test creates tests from acceptance criteria."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)

        test = generator.generate_acceptance_test(
            task_id="T-001",
            task_title="User Login Feature",
            acceptance_criteria=[
                "User can enter username and password",
                "System validates credentials",
                "Successful login redirects to dashboard",
            ],
        )

        # Filename uses lowercase task ID
        assert "t-001" in test.path.name.lower()
        assert len(test.test_cases) == 3
        assert "AC1:" in test.content or "AC 1:" in test.content.replace("AC1", "AC 1")
        assert "acceptance" in test.content
        assert "t-001" in test.content.lower()

    def test_update_test_from_findings(self, tmp_path):
        """update_test_from_findings updates test based on exploration."""
        from ralph_orchestrator.ui import RobotTestGenerator, RobotTestInfo

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)
        generator.ensure_suite_structure()

        # Create existing test file
        test_file = generator.suite_path / "test_existing.robot"
        test_file.write_text("""*** Test Cases ***
Test Login
    Click    button.old-class
    Get Text    body    contains    Old Welcome Text
""")

        test_info = RobotTestInfo(
            path=test_file,
            name="test_existing",
            test_cases=["Test Login"],
            keywords=[],
            pages=[],
            last_modified=datetime.now(),
            content_hash="hash123",
        )

        findings = {
            "selectors": {"button.old-class": "button.new-class"},
            "updated_text": {"Old Welcome Text": "New Welcome Text"},
        }

        updated = generator.update_test_from_findings(test_info, findings)

        assert updated is not None
        assert "button.new-class" in updated.content
        assert "New Welcome Text" in updated.content
        assert updated.is_new is False

    def test_update_test_from_findings_no_changes(self, tmp_path):
        """update_test_from_findings returns None when no changes needed."""
        from ralph_orchestrator.ui import RobotTestGenerator, RobotTestInfo

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)
        generator.ensure_suite_structure()

        test_file = generator.suite_path / "test_existing.robot"
        test_file.write_text("*** Test Cases ***\nTest 1\n    Log    Hello")

        test_info = RobotTestInfo(
            path=test_file,
            name="test_existing",
            test_cases=["Test 1"],
            keywords=[],
            pages=[],
            last_modified=datetime.now(),
            content_hash="hash123",
        )

        findings = {
            "selectors": {"nonexistent": "new"},
        }

        updated = generator.update_test_from_findings(test_info, findings)

        assert updated is None

    def test_save_test_success(self, tmp_path):
        """save_test writes test file when auto_generate enabled."""
        from ralph_orchestrator.ui import RobotTestGenerator, GeneratedTest

        config = self._create_mock_config(tmp_path, auto_generate=True)
        generator = RobotTestGenerator(config=config)

        test = GeneratedTest(
            path=tmp_path / "tests" / "robot" / "new_test.robot",
            content="*** Test Cases ***\nTest 1\n    Log    Hello",
            is_new=True,
            test_cases=["Test 1"],
            description="New test",
        )

        saved_path = generator.save_test(test)

        assert saved_path.exists()
        assert saved_path.read_text() == test.content

    def test_save_test_permission_error(self, tmp_path):
        """save_test raises error when auto_generate disabled."""
        from ralph_orchestrator.ui import RobotTestGenerator, GeneratedTest

        config = self._create_mock_config(tmp_path, auto_generate=False)
        generator = RobotTestGenerator(config=config)

        test = GeneratedTest(
            path=tmp_path / "tests" / "robot" / "new_test.robot",
            content="*** Test Cases ***\nTest 1",
            is_new=True,
            test_cases=["Test 1"],
            description="New test",
        )

        with pytest.raises(PermissionError, match="auto-generation is not enabled"):
            generator.save_test(test)

    def test_get_coverage_summary(self, tmp_path):
        """get_coverage_summary returns test coverage info."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = self._create_mock_config(tmp_path)
        generator = RobotTestGenerator(config=config)
        generator.ensure_suite_structure()

        # Create test files
        (generator.suite_path / "test_1.robot").write_text("""*** Test Cases ***
Test A
    New Page    ${BASE_URL}/page1

Test B
    Log    Hello
""")
        (generator.suite_path / "test_2.robot").write_text("""*** Test Cases ***
Test C
    New Page    ${BASE_URL}/page2
""")

        summary = generator.get_coverage_summary()

        assert summary["total_tests"] == 2
        assert summary["total_cases"] == 3
        assert summary["auto_generate_enabled"] is True


class TestRobotTestGeneratorHelpers:
    """Tests for RobotTestGenerator helper methods."""

    def test_sanitize_filename(self, tmp_path):
        """_sanitize_filename creates safe filenames."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {"ui": {"robot": {"suite": "tests/robot"}}}
        config.resolve_path = lambda p: tmp_path / p

        generator = RobotTestGenerator(config=config)

        # Replaces spaces and special chars (except hyphen) with underscores
        assert generator._sanitize_filename("Hello World!") == "hello_world"
        # Hyphens are allowed in filenames (not special chars)
        assert generator._sanitize_filename("test-file") == "test-file"
        assert generator._sanitize_filename("  spaces  ") == "spaces"
        assert generator._sanitize_filename("UPPER_case") == "upper_case"

    def test_sanitize_tag(self, tmp_path):
        """_sanitize_tag creates safe Robot tags."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {"ui": {"robot": {"suite": "tests/robot"}}}
        config.resolve_path = lambda p: tmp_path / p

        generator = RobotTestGenerator(config=config)

        assert generator._sanitize_tag("Hello World") == "hello-world"
        assert generator._sanitize_tag("test_tag") == "test-tag"

    def test_criterion_to_test_name(self, tmp_path):
        """_criterion_to_test_name creates test names from criteria."""
        from ralph_orchestrator.ui import RobotTestGenerator

        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {"ui": {"robot": {"suite": "tests/robot"}}}
        config.resolve_path = lambda p: tmp_path / p

        generator = RobotTestGenerator(config=config)

        name = generator._criterion_to_test_name(
            "User can login with valid credentials and see dashboard", 1
        )

        assert "AC1:" in name
        assert len(name.split()) <= 8  # Not too long


class TestUITestingHelperFunctions:
    """Tests for ui.py module helper functions."""

    def test_is_robot_enabled(self):
        """is_robot_enabled checks config correctly."""
        from ralph_orchestrator.ui import is_robot_enabled

        config_enabled = Mock()
        config_enabled.raw_data = {"ui": {"robot": {"enabled": True}}}

        config_disabled = Mock()
        config_disabled.raw_data = {"ui": {"robot": {"enabled": False}}}

        assert is_robot_enabled(config_enabled) is True
        assert is_robot_enabled(config_disabled) is False

    def test_is_robot_auto_generate_enabled(self):
        """is_robot_auto_generate_enabled checks config correctly."""
        from ralph_orchestrator.ui import is_robot_auto_generate_enabled

        config = Mock()
        config.raw_data = {"ui": {"robot": {"auto_generate": True}}}

        assert is_robot_auto_generate_enabled(config) is True

    def test_is_agent_browser_enabled(self):
        """is_agent_browser_enabled checks config correctly."""
        from ralph_orchestrator.ui import is_agent_browser_enabled

        config = Mock()
        config.raw_data = {"ui": {"agent_browser": {"enabled": True}}}

        assert is_agent_browser_enabled(config) is True

    def test_format_ui_test_summary(self):
        """format_ui_test_summary formats results correctly."""
        from ralph_orchestrator.ui import (
            format_ui_test_summary,
            UITestSuiteResult,
            UITestResult,
        )

        result = UITestSuiteResult(
            framework="robot",
            passed=True,
            results=[
                UITestResult(name="Test 1", passed=True, duration_ms=100),
                UITestResult(name="Test 2", passed=True, duration_ms=200),
            ],
            total_duration_ms=300,
        )

        summary = format_ui_test_summary(result)

        assert "Robot Framework" in summary
        assert "2/2 passed" in summary
        assert "Test 1" in summary
        assert "Test 2" in summary

    def test_format_failure_description(self):
        """format_failure_description formats failure correctly."""
        from ralph_orchestrator.ui import format_failure_description, UITestResult

        result = UITestResult(
            name="Login Test",
            passed=False,
            duration_ms=500,
            error="Element not found: button.submit",
            output="Test output...",
        )

        description = format_failure_description(result, "Robot Framework")

        assert "Login Test" in description
        assert "Element not found" in description
        assert "Test output" in description


# ============================================================================
# UI Testing Orchestration Tests
# ============================================================================


class TestUITestingOrchestration:
    """Tests for UI testing integration in OrchestrationService."""

    def _create_mock_service(self, tmp_path, frontend=True, browser_use_enabled=True):
        """Create a minimal mock orchestration service for testing."""
        from ralph_orchestrator.services.orchestration_service import (
            OrchestrationService,
            OrchestrationOptions,
        )
        from ralph_orchestrator.config import ServiceConfig

        config = Mock()
        config.repo_root = tmp_path
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(
            return_value=Mock(model="sonnet", allowed_tools=None, timeout=None)
        )
        
        if frontend:
            config.frontend = ServiceConfig(port=3000)
        else:
            config.frontend = None
        
        config.raw_data = {
            "ui": {
                "browser_use": {
                    "enabled": browser_use_enabled,
                    "base_url": "http://localhost:3000",
                },
                "robot": {
                    "enabled": True,
                    "suite": "tests/robot",
                },
            },
            "limits": {
                "ui_fix_iterations": 3,
            },
        }

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        session.get_report_path = Mock(return_value=tmp_path / "report.md")
        timeline = Mock()
        exec_logger = Mock()
        exec_logger.custom = Mock()
        exec_logger.agent_start = Mock()
        exec_logger.agent_failed = Mock()
        exec_logger.agent_complete = Mock()
        exec_logger.signal_validation = Mock()
        exec_logger.agent_output = Mock()
        exec_logger.feedback_set = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()

        options = OrchestrationOptions()

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

        return service

    def test_should_run_ui_testing_with_frontend_task(self, tmp_path):
        """_should_run_ui_testing returns True for frontend tasks."""
        service = self._create_mock_service(tmp_path, frontend=True, browser_use_enabled=True)

        task = Mock()
        task.affects_frontend = True

        result = service._should_run_ui_testing(task)

        assert result is True

    def test_should_run_ui_testing_no_frontend_task(self, tmp_path):
        """_should_run_ui_testing returns False for non-frontend tasks."""
        service = self._create_mock_service(tmp_path, frontend=True, browser_use_enabled=True)

        task = Mock()
        task.affects_frontend = False

        result = service._should_run_ui_testing(task)

        assert result is False

    def test_should_run_ui_testing_no_frontend_service(self, tmp_path):
        """_should_run_ui_testing returns False without frontend service."""
        service = self._create_mock_service(tmp_path, frontend=False, browser_use_enabled=True)

        task = Mock()
        task.affects_frontend = True

        result = service._should_run_ui_testing(task)

        assert result is False

    def test_should_run_ui_testing_browser_use_disabled(self, tmp_path):
        """_should_run_ui_testing returns False when both browser-use and robot disabled."""
        from ralph_orchestrator.services.orchestration_service import (
            OrchestrationService,
            OrchestrationOptions,
        )
        from ralph_orchestrator.config import ServiceConfig

        # Create config with both browser-use and robot disabled
        config = Mock()
        config.repo_root = tmp_path
        config.test_paths = ["tests/"]
        config.get_agent_config = Mock(
            return_value=Mock(model="sonnet", allowed_tools=None, timeout=None)
        )
        config.frontend = ServiceConfig(port=3000)
        config.raw_data = {
            "ui": {
                "browser_use": {
                    "enabled": False,  # Disabled
                    "base_url": "http://localhost:3000",
                },
                "robot": {
                    "enabled": False,  # Also disabled
                    "suite": "tests/robot",
                },
            },
            "limits": {
                "ui_fix_iterations": 3,
            },
        }

        prd = Mock()
        session = Mock()
        session.session_token = "test-token"
        session.get_report_path = Mock(return_value=tmp_path / "report.md")
        timeline = Mock()
        exec_logger = Mock()
        exec_logger.custom = Mock()
        exec_logger.agent_start = Mock()
        exec_logger.agent_failed = Mock()
        exec_logger.agent_complete = Mock()
        exec_logger.signal_validation = Mock()
        exec_logger.agent_output = Mock()
        exec_logger.feedback_set = Mock()
        claude_runner = Mock()
        gate_runner = Mock()
        guardrail = Mock()

        options = OrchestrationOptions()

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

        task = Mock()
        task.affects_frontend = True

        result = service._should_run_ui_testing(task)

        assert result is False

    def test_get_ui_base_url(self, tmp_path):
        """_get_ui_base_url returns configured base URL."""
        service = self._create_mock_service(tmp_path)

        url = service._get_ui_base_url()

        assert url == "http://localhost:3000"

    def test_get_robot_suite_path(self, tmp_path):
        """_get_robot_suite_path returns configured suite path."""
        service = self._create_mock_service(tmp_path)

        path = service._get_robot_suite_path()

        assert path == "tests/robot"


class TestUITestResult:
    """Tests for UITestResult data class."""

    def test_ui_test_result_creation(self):
        """UITestResult holds test result data."""
        from ralph_orchestrator.ui import UITestResult

        result = UITestResult(
            name="Login Test",
            passed=True,
            duration_ms=1500,
            output="Test passed successfully",
        )

        assert result.name == "Login Test"
        assert result.passed is True
        assert result.duration_ms == 1500
        assert result.error is None

    def test_ui_test_result_with_error(self, tmp_path):
        """UITestResult includes error and artifacts."""
        from ralph_orchestrator.ui import UITestResult

        screenshot = tmp_path / "failure.png"

        result = UITestResult(
            name="Failed Test",
            passed=False,
            duration_ms=2000,
            error="Assertion failed: expected 'Welcome' but got 'Error'",
            screenshot_path=screenshot,
            output="Test output...",
        )

        assert result.passed is False
        assert "Assertion failed" in result.error


class TestUITestSuiteResult:
    """Tests for UITestSuiteResult data class."""

    def test_suite_result_counts(self):
        """UITestSuiteResult calculates counts correctly."""
        from ralph_orchestrator.ui import UITestSuiteResult, UITestResult

        result = UITestSuiteResult(
            framework="robot",
            passed=False,
            results=[
                UITestResult(name="Test 1", passed=True, duration_ms=100),
                UITestResult(name="Test 2", passed=False, duration_ms=200, error="Failed"),
                UITestResult(name="Test 3", passed=True, duration_ms=150),
            ],
            total_duration_ms=450,
        )

        assert result.passed_count == 2
        assert result.failed_count == 1

    def test_get_failures(self):
        """get_failures returns only failed tests."""
        from ralph_orchestrator.ui import UITestSuiteResult, UITestResult

        result = UITestSuiteResult(
            framework="agent_browser",
            passed=False,
            results=[
                UITestResult(name="Pass 1", passed=True, duration_ms=100),
                UITestResult(name="Fail 1", passed=False, duration_ms=200, error="Error 1"),
                UITestResult(name="Fail 2", passed=False, duration_ms=150, error="Error 2"),
            ],
        )

        failures = result.get_failures()

        assert len(failures) == 2
        assert failures[0].name == "Fail 1"
        assert failures[1].name == "Fail 2"


class TestRobotRunner:
    """Tests for RobotRunner class."""

    def _create_mock_config(self, tmp_path, robot_enabled=True):
        """Create mock config for RobotRunner tests."""
        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {
            "ui": {
                "robot": {
                    "enabled": robot_enabled,
                    "suite": "tests/robot",
                    "variables": {"EXTRA_VAR": "value"},
                }
            }
        }
        config.resolve_path = lambda p: tmp_path / p
        return config

    def test_robot_runner_initialization(self, tmp_path):
        """RobotRunner initializes correctly."""
        from ralph_orchestrator.ui import RobotRunner

        config = self._create_mock_config(tmp_path)
        runner = RobotRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
            logs_dir=tmp_path / "logs",
        )

        assert runner.base_url == "http://localhost:3000"
        assert runner.artifacts_dir.exists()
        assert runner.logs_dir.exists()

    def test_get_variables(self, tmp_path):
        """_get_variables returns configured variables plus defaults."""
        from ralph_orchestrator.ui import RobotRunner

        config = self._create_mock_config(tmp_path)
        runner = RobotRunner(
            config=config,
            base_url="http://localhost:3000",
        )

        variables = runner._get_variables()

        assert variables["BASE_URL"] == "http://localhost:3000"
        assert variables["BROWSER"] == "chromium"
        assert variables["EXTRA_VAR"] == "value"

    def test_get_suite_path_from_config(self, tmp_path):
        """_get_suite_path returns configured suite path."""
        from ralph_orchestrator.ui import RobotRunner

        config = self._create_mock_config(tmp_path)
        
        # Create the suite directory
        suite_dir = tmp_path / "tests" / "robot"
        suite_dir.mkdir(parents=True)

        runner = RobotRunner(
            config=config,
            base_url="http://localhost:3000",
        )

        path = runner._get_suite_path()

        assert path == suite_dir

    def test_run_no_suite_configured(self, tmp_path):
        """run() returns failure when no suite found."""
        from ralph_orchestrator.ui import RobotRunner

        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {"ui": {"robot": {}}}
        config.resolve_path = lambda p: tmp_path / p

        runner = RobotRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )

        result = runner.run()

        assert result.passed is False
        assert "No Robot Framework test suite" in result.results[0].error


class TestAgentBrowserRunner:
    """Tests for AgentBrowserRunner class."""

    def _create_mock_config(self, tmp_path, tests=None, script=None):
        """Create mock config for AgentBrowserRunner tests."""
        config = Mock()
        config.repo_root = tmp_path
        config.raw_data = {
            "ui": {
                "agent_browser": {
                    "enabled": True,
                    "tests": tests or [],
                    "script": script,
                }
            }
        }
        config.resolve_path = lambda p: tmp_path / p
        return config

    def test_agent_browser_runner_initialization(self, tmp_path):
        """AgentBrowserRunner initializes correctly."""
        from ralph_orchestrator.ui import AgentBrowserRunner

        config = self._create_mock_config(tmp_path)
        runner = AgentBrowserRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
            logs_dir=tmp_path / "logs",
        )

        assert runner.base_url == "http://localhost:3000"
        assert runner.artifacts_dir.exists()

    def test_run_no_tests_configured(self, tmp_path):
        """run() returns success with empty results when no tests configured."""
        from ralph_orchestrator.ui import AgentBrowserRunner

        config = self._create_mock_config(tmp_path, tests=[])
        runner = AgentBrowserRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )

        result = runner.run()

        assert result.passed is True
        assert len(result.results) == 0

    def test_run_script_not_found(self, tmp_path):
        """run() returns failure when script doesn't exist."""
        from ralph_orchestrator.ui import AgentBrowserRunner

        config = self._create_mock_config(tmp_path, script="nonexistent.sh")
        runner = AgentBrowserRunner(
            config=config,
            base_url="http://localhost:3000",
            artifacts_dir=tmp_path / "artifacts",
        )

        result = runner.run()

        assert result.passed is False
        assert "not found" in result.results[0].error.lower()
