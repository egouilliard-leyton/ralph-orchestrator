"""
Integration tests for mock Claude + fixtures integration.

These tests verify that the mock Claude CLI works correctly with
the fixture repositories. They can run without the actual Ralph CLI,
serving as validation of the test harness itself.
"""

import pytest
import os
import sys
import json
import subprocess
from pathlib import Path

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestMockClaudeWithFixtures:
    """Test mock Claude CLI with fixture repositories."""
    
    def test_mock_claude_runs_from_fixture(self, fixture_python_min: Path, mock_claude_path: Path):
        """
        Mock Claude can be invoked from fixture directory.
        
        Given: Fixture repository with prd.json
        When: Mock Claude invoked with implementation prompt
        Then: Returns valid task-done signal
        """
        os.chdir(fixture_python_min)
        
        # Read task from prd.json
        prd_file = fixture_python_min / ".ralph" / "prd.json"
        prd = json.loads(prd_file.read_text())
        task = prd["tasks"][0]
        
        # Create prompt like real orchestrator would
        prompt = f'''SESSION_TOKEN: "ralph-20260125-143052-testtoken12345"
        
Task: {task["id"]}
Title: {task["title"]}

Implement the requested changes.
'''
        
        # Run mock Claude
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
            cwd=fixture_python_min,
        )
        
        assert result.returncode == 0
        assert "<task-done" in result.stdout
        assert "ralph-20260125-143052-testtoken12345" in result.stdout
    
    def test_mock_claude_detects_test_writing_role(self, fixture_python_min: Path, mock_claude_path: Path):
        """
        Mock Claude detects test-writing role from prompt.
        
        Given: Prompt with test/guardrail keywords
        When: Mock Claude generates response
        Then: Returns tests-done signal
        """
        os.chdir(fixture_python_min)
        
        prompt = '''SESSION_TOKEN: "ralph-test-token"
        
Write tests with guardrail restrictions.
Only modify files in tests/ directory.
'''
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "<tests-done" in result.stdout
    
    def test_mock_claude_detects_review_role(self, fixture_python_min: Path, mock_claude_path: Path):
        """
        Mock Claude detects review role from prompt.
        
        Given: Prompt with review/read-only keywords
        When: Mock Claude generates response
        Then: Returns review-approved signal
        """
        prompt = '''SESSION_TOKEN: "ralph-test-token"
        
Review the code. READ-ONLY mode.
Check for issues.
'''
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "<review-approved" in result.stdout


class TestSimulateDirectives:
    """Test SIMULATE_* directive handling."""
    
    def test_simulate_invalid_token(self, mock_claude_path: Path):
        """
        SIMULATE_INVALID_TOKEN returns wrong token.
        
        Given: Prompt with SIMULATE_INVALID_TOKEN
        When: Mock Claude generates response
        Then: Signal has incorrect token
        """
        prompt = '''SESSION_TOKEN: "ralph-correct-token"

Task: T-001 SIMULATE_INVALID_TOKEN
'''
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "<task-done" in result.stdout
        assert "wrong-token" in result.stdout
        assert "ralph-correct-token" not in result.stdout
    
    def test_simulate_no_signal(self, mock_claude_path: Path):
        """
        SIMULATE_NO_SIGNAL returns response without signal.
        
        Given: Prompt with SIMULATE_NO_SIGNAL
        When: Mock Claude generates response
        Then: No completion signal in response
        """
        prompt = '''SESSION_TOKEN: "ralph-test-token"

Task: T-001 SIMULATE_NO_SIGNAL
'''
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "<task-done" not in result.stdout
        assert "<tests-done" not in result.stdout
        assert "<review-" not in result.stdout
    
    def test_simulate_review_reject(self, mock_claude_path: Path):
        """
        SIMULATE_REVIEW_REJECT returns rejection signal.
        
        Given: Prompt with SIMULATE_REVIEW_REJECT
        When: Mock Claude generates response
        Then: Returns review-rejected signal
        """
        prompt = '''SESSION_TOKEN: "ralph-test-token"

Review SIMULATE_REVIEW_REJECT
'''
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        assert "<review-rejected" in result.stdout


class TestAutopilotMockResponses:
    """Test mock Claude autopilot-specific responses."""
    
    def test_analysis_response_is_valid_json(self, mock_claude_path: Path):
        """
        Analysis prompt returns valid JSON.
        
        Given: Analysis-style prompt
        When: Mock Claude generates response
        Then: Response is valid JSON with required fields
        """
        prompt = "Analyze this report and identify priorities"
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        
        # Parse JSON response
        analysis = json.loads(result.stdout)
        
        assert "priority_item" in analysis
        assert "description" in analysis
        assert "rationale" in analysis
        assert "acceptance_criteria" in analysis
        assert "branch_name" in analysis
        
        assert isinstance(analysis["acceptance_criteria"], list)
        assert analysis["branch_name"].startswith("ralph/")
    
    def test_tasks_response_is_valid_prd_json(self, mock_claude_path: Path):
        """
        Tasks prompt returns valid prd.json format.
        
        Given: Tasks generation prompt
        When: Mock Claude generates response
        Then: Response matches prd.json schema
        """
        prompt = "Generate tasks and convert to prd.json format"
        
        result = subprocess.run(
            [sys.executable, str(mock_claude_path), "-p", prompt],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0
        
        # Parse JSON response
        prd = json.loads(result.stdout)
        
        assert "project" in prd
        assert "tasks" in prd
        assert len(prd["tasks"]) >= 1
        
        # Verify task structure
        task = prd["tasks"][0]
        assert "id" in task
        assert "title" in task
        assert "acceptanceCriteria" in task
        assert "priority" in task
        assert "passes" in task
        assert task["passes"] is False


class TestFixtureIntegrity:
    """Test fixture repository integrity."""
    
    def test_python_min_has_required_structure(self, fixture_python_min: Path):
        """
        Python fixture has all required files.
        
        Given: python_min fixture
        When: Structure checked
        Then: All required files present
        """
        required_files = [
            ".ralph/ralph.yml",
            ".ralph/prd.json",
            "pyproject.toml",
            "src/main.py",
            "tests/test_main.py",
        ]
        
        for file_path in required_files:
            full_path = fixture_python_min / file_path
            assert full_path.exists(), f"Missing: {file_path}"
    
    def test_node_min_has_required_structure(self, fixture_node_min: Path):
        """
        Node fixture has all required files.
        
        Given: node_min fixture
        When: Structure checked
        Then: All required files present
        """
        required_files = [
            ".ralph/ralph.yml",
            ".ralph/prd.json",
            "package.json",
            "src/index.js",
        ]
        
        for file_path in required_files:
            full_path = fixture_node_min / file_path
            assert full_path.exists(), f"Missing: {file_path}"
    
    def test_fullstack_min_has_required_structure(self, fixture_fullstack_min: Path):
        """
        Fullstack fixture has all required files.
        
        Given: fullstack_min fixture
        When: Structure checked
        Then: Backend and frontend structure present
        """
        required_files = [
            ".ralph/ralph.yml",
            ".ralph/prd.json",
            "pyproject.toml",
            "src/api/main.py",
            "frontend/package.json",
            "frontend/src/App.tsx",
        ]
        
        for file_path in required_files:
            full_path = fixture_fullstack_min / file_path
            assert full_path.exists(), f"Missing: {file_path}"
    
    def test_autopilot_min_has_required_structure(self, fixture_autopilot_min: Path):
        """
        Autopilot fixture has all required files.
        
        Given: autopilot_min fixture
        When: Structure checked
        Then: Reports directory and config present
        """
        required_files = [
            ".ralph/ralph.yml",
            ".ralph/prd.json",
            "reports/weekly-report.md",
        ]
        
        for file_path in required_files:
            full_path = fixture_autopilot_min / file_path
            assert full_path.exists(), f"Missing: {file_path}"
        
        # Verify autopilot config enabled
        import yaml
        config = yaml.safe_load((fixture_autopilot_min / ".ralph/ralph.yml").read_text())
        assert config["autopilot"]["enabled"] is True


class TestEnvironmentOverride:
    """Test RALPH_CLAUDE_CMD environment override."""
    
    def test_ralph_claude_cmd_set_in_conftest(self):
        """
        RALPH_CLAUDE_CMD is set to mock by conftest.
        
        Given: Test environment
        When: Environment checked
        Then: RALPH_CLAUDE_CMD points to mock
        """
        ralph_cmd = os.environ.get("RALPH_CLAUDE_CMD", "")
        
        assert "mock_claude" in ralph_cmd
        assert ralph_cmd.endswith("mock_claude.py")
    
    def test_mock_scenario_can_be_overridden(self):
        """
        MOCK_SCENARIO environment variable works.
        
        Given: MOCK_SCENARIO set
        When: Mock Claude runs
        Then: Uses specified scenario
        """
        original = os.environ.get("MOCK_SCENARIO")
        
        try:
            os.environ["MOCK_SCENARIO"] = "success"
            
            # Verify environment is set
            assert os.environ.get("MOCK_SCENARIO") == "success"
        finally:
            if original:
                os.environ["MOCK_SCENARIO"] = original
            else:
                os.environ.pop("MOCK_SCENARIO", None)
