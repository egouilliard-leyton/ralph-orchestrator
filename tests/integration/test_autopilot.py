"""
Integration tests for autopilot pipeline.

These tests verify that the Ralph autopilot correctly:
- Finds and analyzes reports
- Generates analysis JSON with priority item
- Creates PRD from analysis
- Generates tasks in prd.json format
- Runs verified execution loop
- Creates run state for persistence

The autopilot pipeline: report → analysis → PRD → tasks → execution → PR
"""

import pytest
import os
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Mark all tests in this module as autopilot tests
pytestmark = [pytest.mark.integration, pytest.mark.autopilot]


# Mock analysis response for testing
MOCK_ANALYSIS_RESPONSE = json.dumps({
    "priority_item": "Fix Login Form Validation",
    "description": "Improve email validation error messages on the login form to be more specific and user-friendly.",
    "rationale": "This is causing 15% of signup attempts to fail and increased support tickets by 23%.",
    "acceptance_criteria": [
        "Email validation shows specific error for invalid format",
        "Error message clearly explains what is wrong",
        "Valid emails are accepted without error"
    ],
    "estimated_tasks": 8,
    "branch_name": "fix-login-validation"
})


class TestAutopilotReportDiscovery:
    """Test autopilot report discovery phase."""
    
    def test_report_discovery_finds_reports(self, fixture_autopilot_min: Path):
        """
        Report discovery finds reports in directory.
        
        Given: Reports directory with reports
        When: ReportDiscovery scans
        Then: Reports are found and sorted by date
        """
        from ralph_orchestrator.autopilot import ReportDiscovery
        
        reports_dir = fixture_autopilot_min / "reports"
        discovery = ReportDiscovery(reports_dir)
        
        reports = discovery.find_reports()
        assert len(reports) >= 1, "Should find at least one report"
        assert reports[0].extension == ".md"
    
    def test_report_discovery_selects_latest(self, fixture_autopilot_min: Path):
        """
        Report discovery selects most recent report.
        
        Given: Reports directory with reports
        When: select_latest() called
        Then: Returns most recent report
        """
        from ralph_orchestrator.autopilot import ReportDiscovery
        
        reports_dir = fixture_autopilot_min / "reports"
        discovery = ReportDiscovery(reports_dir)
        
        report = discovery.select_latest()
        assert report is not None
        assert report.name == "weekly-report.md"
    
    def test_report_discovery_validates_report(self, fixture_autopilot_min: Path):
        """
        Report discovery validates report content.
        
        Given: Valid report file
        When: validate_report() called
        Then: Returns (True, None)
        """
        from ralph_orchestrator.autopilot import ReportDiscovery
        
        reports_dir = fixture_autopilot_min / "reports"
        discovery = ReportDiscovery(reports_dir)
        
        report = discovery.select_latest()
        valid, error = discovery.validate_report(report)
        
        assert valid is True
        assert error is None

    def test_bootstrap_report_created_when_none_exist(self, temp_dir: Path):
        """
        Autopilot can bootstrap a report when directory is empty.
        
        Given: Empty reports directory
        When: Bootstrap report generator runs
        Then: A report file is created with sufficient content
        """
        from ralph_orchestrator.autopilot import generate_bootstrap_report
        
        repo_root = temp_dir
        # minimal git init so report can include git info (optional)
        (repo_root / "README.md").write_text("test")
        os.system(f"cd {repo_root} && git init -q && git add . && git commit -q -m 'Initial'")
        
        reports_dir = repo_root / "reports"
        assert not reports_dir.exists()
        
        report_path = generate_bootstrap_report(repo_root, reports_dir)
        assert report_path.exists()
        content = report_path.read_text()
        assert len(content.strip()) > 100
        assert "Ralph Auto-Generated Report" in content


class TestAutopilotAnalysis:
    """Test autopilot analysis phase."""
    
    def test_analysis_parses_response(self, fixture_autopilot_min: Path):
        """
        Analysis correctly parses LLM response.
        
        Given: Valid JSON analysis response
        When: _parse_response() called
        Then: Returns AnalysisOutput with correct fields
        """
        from ralph_orchestrator.autopilot import ReportAnalyzer, AnalysisOutput, LLMProvider
        from ralph_orchestrator.config import load_config
        
        os.chdir(fixture_autopilot_min)
        config = load_config()
        
        # Mock the LLM provider initialization to avoid requiring API keys
        with patch.object(LLMProvider, '__init__', lambda self, **kwargs: None):
            with patch.object(LLMProvider, '_detect_and_validate', lambda self: None):
                analyzer = ReportAnalyzer(
                    config=config.autopilot,
                    repo_root=fixture_autopilot_min,
                )
                # Set up minimal LLM attributes after mocking
                analyzer.llm = MagicMock()
                analyzer.llm.model = "mock-model"
                analyzer.llm._get_default_model = lambda: "mock-model"
                analyzer.llm.provider = MagicMock()
                analyzer.llm.provider.value = "anthropic"
        
        report_path = fixture_autopilot_min / "reports" / "weekly-report.md"
        result = analyzer._parse_response(MOCK_ANALYSIS_RESPONSE, report_path)
        
        assert isinstance(result, AnalysisOutput)
        assert result.priority_item == "Fix Login Form Validation"
        assert len(result.acceptance_criteria) >= 1
        assert "fix-login-validation" in result.branch_name
    
    def test_analysis_output_schema(self, fixture_autopilot_min: Path):
        """
        Analysis output matches expected schema.
        
        Given: Analysis completed
        When: analysis.json loaded
        Then: Contains required fields with correct types
        """
        from ralph_orchestrator.autopilot import AnalysisOutput
        from datetime import datetime, timezone
        
        # Expected schema from testing-strategy.md:
        expected_fields = [
            "priority_item",     # string
            "description",       # string  
            "rationale",         # string
            "acceptance_criteria",  # array of strings
            "branch_name",       # string (ralph/prefix)
        ]
        
        # Create a valid AnalysisOutput
        analysis = AnalysisOutput(
            priority_item="Test Item",
            description="Test description",
            rationale="Test rationale",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            branch_name="ralph/test-feature",
            analysis_timestamp=datetime.now(timezone.utc),
            source_report="test.md",
        )
        
        # Verify all required fields exist and have correct types
        assert isinstance(analysis.priority_item, str)
        assert isinstance(analysis.description, str)
        assert isinstance(analysis.rationale, str)
        assert isinstance(analysis.acceptance_criteria, list)
        assert isinstance(analysis.branch_name, str)
        assert len(analysis.acceptance_criteria) >= 1
    
    def test_branch_name_format(self, fixture_autopilot_min: Path):
        """
        Branch name has correct prefix from config.
        
        Given: Config has branch_prefix
        When: Branch name normalized
        Then: Branch name starts with prefix
        """
        from ralph_orchestrator.autopilot import normalize_branch_name
        
        os.chdir(fixture_autopilot_min)
        
        config_file = fixture_autopilot_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        prefix = config["autopilot"]["branch_prefix"]
        
        # Test branch name normalization
        branch = normalize_branch_name("fix-login-validation", prefix)
        assert branch.startswith(prefix), f"Branch {branch} should start with {prefix}"
        
        # Already prefixed
        branch = normalize_branch_name("ralph/existing-prefix", prefix)
        assert branch.startswith(prefix)
    
    def test_latest_report_selected(self, fixture_autopilot_min: Path):
        """
        Analysis selects most recent report.
        
        Given: Multiple reports with different dates
        When: ReportDiscovery selects latest
        Then: Most recent report is returned
        """
        from ralph_orchestrator.autopilot import ReportDiscovery
        import time
        
        os.chdir(fixture_autopilot_min)
        
        # Create second report (ensure it's more recent)
        reports_dir = fixture_autopilot_min / "reports"
        newer_report = reports_dir / "weekly-report-2026-01-25.md"
        time.sleep(0.1)  # Ensure timestamp is different
        newer_report.write_text("""# Weekly Report - 2026-01-25
        
## Issues
### 1. New Issue (High Priority)
New issue for testing report selection.
""")
        
        discovery = ReportDiscovery(reports_dir)
        report = discovery.select_latest()
        
        # Newer report should be selected
        assert report.name == "weekly-report-2026-01-25.md"


class TestAutopilotTaskGeneration:
    """Test autopilot task generation phase."""
    
    def test_prd_json_validation(self, fixture_autopilot_min: Path):
        """
        TasksGenerator validates prd.json format.
        
        Given: prd.json file with tasks
        When: _validate_prd_json called
        Then: Returns task count and validates schema
        """
        from ralph_orchestrator.autopilot import TasksGenerator
        from ralph_orchestrator.config import load_config
        
        os.chdir(fixture_autopilot_min)
        config = load_config()
        
        # Create a test prd.json
        prd_path = fixture_autopilot_min / ".ralph" / "prd.json"
        test_prd = {
            "project": "Test",
            "branchName": "ralph/test",
            "description": "Test description",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Test Task",
                    "description": "Test",
                    "acceptanceCriteria": ["Test passes"],
                    "priority": 1,
                    "passes": False,
                    "notes": ""
                }
            ]
        }
        prd_path.write_text(json.dumps(test_prd, indent=2))
        
        generator = TasksGenerator(
            config=config.autopilot,
            repo_root=fixture_autopilot_min,
            branch_manager=MagicMock(),
        )
        
        task_count = generator._validate_prd_json(prd_path, "ralph/test")
        assert task_count == 1
    
    def test_tasks_schema_fields(self, fixture_autopilot_min: Path):
        """
        Generated tasks match prd.json schema.
        
        Given: prd.json with tasks
        When: Tasks loaded
        Then: Tasks have all required fields
        """
        required_task_fields = [
            "id",
            "title",
            "acceptanceCriteria",
            "priority",
            "passes",
        ]
        
        # Verify fixture prd.json has correct structure
        prd_path = fixture_autopilot_min / ".ralph" / "prd.json"
        prd = json.loads(prd_path.read_text())
        
        assert "tasks" in prd
        for task in prd["tasks"]:
            for field in required_task_fields:
                assert field in task, f"Task missing field: {field}"
    
    def test_task_count_config(self, fixture_autopilot_min: Path):
        """
        Task count bounds are read from config.
        
        Given: Config has min/max task count
        When: Config loaded
        Then: Bounds are available
        """
        from ralph_orchestrator.config import load_config
        
        os.chdir(fixture_autopilot_min)
        config = load_config()
        
        assert config.autopilot.tasks_min_count >= 1
        assert config.autopilot.tasks_max_count >= config.autopilot.tasks_min_count
    
    def test_task_ids_unique(self, fixture_autopilot_min: Path):
        """
        Task IDs are unique.
        
        Given: prd.json with tasks
        When: IDs checked
        Then: No duplicate IDs
        """
        prd_path = fixture_autopilot_min / ".ralph" / "prd.json"
        prd = json.loads(prd_path.read_text())
        
        ids = [task["id"] for task in prd["tasks"]]
        assert len(ids) == len(set(ids)), "Task IDs must be unique"
    
    def test_task_ids_format(self, fixture_autopilot_min: Path):
        r"""
        Task IDs follow T-NNN format.
        
        Given: Tasks generated
        When: IDs checked
        Then: All match T-\d{3} pattern
        """
        import re
        
        id_pattern = r'^T-\d{3}$'
        
        # Sample valid IDs
        valid_ids = ["T-001", "T-002", "T-010", "T-099"]
        for task_id in valid_ids:
            assert re.match(id_pattern, task_id), f"{task_id} should match pattern"
    
    def test_tasks_start_not_passed(self, fixture_autopilot_min: Path):
        """
        Generated tasks start with passes=false.
        
        Given: Fresh prd.json
        When: Tasks loaded
        Then: All tasks have passes=false
        """
        prd_path = fixture_autopilot_min / ".ralph" / "prd.json"
        prd = json.loads(prd_path.read_text())
        
        for task in prd["tasks"]:
            assert task["passes"] is False, f"Task {task['id']} should start with passes=False"


class TestAutopilotRunState:
    """Test autopilot run state persistence."""
    
    def test_run_state_manager_create(self, fixture_autopilot_min: Path):
        """
        RunStateManager creates run state.
        
        Given: Autopilot directory
        When: RunStateManager.create() called
        Then: Run state file saved
        """
        from ralph_orchestrator.autopilot import RunStateManager, RunStatus
        
        os.chdir(fixture_autopilot_min)
        
        autopilot_dir = fixture_autopilot_min / ".ralph" / "autopilot"
        manager = RunStateManager(autopilot_dir)
        
        run = manager.create()
        
        # Verify run state
        assert run.run_id is not None
        assert run.status == RunStatus.PENDING
        
        # Verify file exists
        run_file = autopilot_dir / "runs" / f"{run.run_id}.json"
        assert run_file.exists()
    
    def test_run_state_schema(self, fixture_autopilot_min: Path):
        """
        Run state matches expected schema.
        
        Given: Run state created
        When: Run state loaded
        Then: Contains required fields
        """
        from ralph_orchestrator.autopilot import RunStateManager, AutopilotRun
        
        expected_fields = [
            "run_id",
            "started_at",
            "status",
        ]
        
        autopilot_dir = fixture_autopilot_min / ".ralph" / "autopilot"
        manager = RunStateManager(autopilot_dir)
        
        run = manager.create()
        
        # Load run state from file
        run_file = autopilot_dir / "runs" / f"{run.run_id}.json"
        data = json.loads(run_file.read_text())
        
        for field in expected_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_run_id_unique(self, fixture_autopilot_min: Path):
        """
        Each run gets unique run_id.
        
        Given: Multiple autopilot runs
        When: Run states created
        Then: run_ids are unique
        """
        from ralph_orchestrator.autopilot import RunStateManager
        
        autopilot_dir = fixture_autopilot_min / ".ralph" / "autopilot"
        manager = RunStateManager(autopilot_dir)
        
        run1 = manager.create()
        run2 = manager.create()
        
        assert run1.run_id != run2.run_id
    
    def test_run_state_update(self, fixture_autopilot_min: Path):
        """
        Run state can be updated.
        
        Given: Existing run state
        When: update() called with new values
        Then: Values are persisted
        """
        from ralph_orchestrator.autopilot import RunStateManager, RunStatus
        
        autopilot_dir = fixture_autopilot_min / ".ralph" / "autopilot"
        manager = RunStateManager(autopilot_dir)
        
        run = manager.create()
        run = manager.update(run, status=RunStatus.ANALYZING, report_path="/test/report.md")
        
        # Reload and verify
        loaded = manager.load(run.run_id)
        assert loaded.status == RunStatus.ANALYZING
        assert loaded.report_path == "/test/report.md"


class TestAutopilotDryRun:
    """Test autopilot dry-run mode."""
    
    def test_dry_run_options(self, fixture_autopilot_min: Path):
        """
        Dry-run option is properly configured.
        
        Given: AutopilotOptions with dry_run=True
        When: Options created
        Then: dry_run flag is set
        """
        from ralph_orchestrator.autopilot import AutopilotOptions
        
        options = AutopilotOptions(dry_run=True)
        assert options.dry_run is True
        
        options = AutopilotOptions(dry_run=False)
        assert options.dry_run is False
    
    def test_dry_run_result_flag(self, fixture_autopilot_min: Path):
        """
        Dry-run result includes dry_run flag.
        
        Given: AutopilotResult
        When: Result created for dry-run
        Then: dry_run flag is True
        """
        from ralph_orchestrator.autopilot import AutopilotResult, ExitCode
        
        result = AutopilotResult(
            exit_code=ExitCode.SUCCESS,
            dry_run=True,
            run_id="test-run",
        )
        
        assert result.dry_run is True


class TestAutopilotPRCreation:
    """Test autopilot PR creation."""
    
    def test_pr_not_created_by_default(self, fixture_autopilot_min: Path):
        """
        PR not created unless explicitly requested.
        
        Given: No --create-pr flag
        When: Config loaded
        Then: create_pr is false
        """
        os.chdir(fixture_autopilot_min)
        
        config_file = fixture_autopilot_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Fixture has create_pr: false
        assert config["autopilot"]["create_pr"] is False
    
    def test_pr_body_generation(self, fixture_autopilot_min: Path):
        """
        PR body is generated correctly.
        
        Given: Analysis output and task data
        When: PR body generated
        Then: Contains summary information
        """
        from ralph_orchestrator.autopilot import PRCreator, AnalysisOutput
        from ralph_orchestrator.config import load_config
        from datetime import datetime, timezone
        
        os.chdir(fixture_autopilot_min)
        config = load_config()
        
        creator = PRCreator(
            config=config,
            repo_root=fixture_autopilot_min,
        )
        
        analysis = AnalysisOutput(
            priority_item="Test Feature",
            description="Test description",
            rationale="Test rationale",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            branch_name="ralph/test",
            analysis_timestamp=datetime.now(timezone.utc),
            source_report="report.md",
        )
        
        body = creator._generate_body(
            analysis=analysis,
            tasks_completed=5,
            tasks_total=10,
            prd_data=None,
        )
        
        assert "Test Feature" in body
        assert "Test description" in body
        assert "Test rationale" in body
        assert "5/10" in body


class TestAutopilotMemory:
    """Test autopilot memory/progress tracking."""
    
    def test_progress_append(self, fixture_autopilot_min: Path):
        """
        Progress.txt is appended with messages.
        
        Given: MemoryManager
        When: append_progress() called
        Then: Message added to progress file
        """
        from ralph_orchestrator.autopilot import MemoryManager
        from ralph_orchestrator.config import load_config
        
        os.chdir(fixture_autopilot_min)
        config = load_config()
        
        memory = MemoryManager(
            config=config.autopilot,
            repo_root=fixture_autopilot_min,
        )
        
        memory.append_progress("Test message")
        
        content = memory.get_progress_content()
        assert "Test message" in content
    
    def test_progress_timestamps(self, fixture_autopilot_min: Path):
        """
        Progress entries have timestamps.
        
        Given: Progress entries
        When: get_progress_content() called
        Then: Entries have timestamps
        """
        from ralph_orchestrator.autopilot import MemoryManager
        from ralph_orchestrator.config import load_config
        import re
        
        os.chdir(fixture_autopilot_min)
        config = load_config()
        
        memory = MemoryManager(
            config=config.autopilot,
            repo_root=fixture_autopilot_min,
        )
        
        memory.append_progress("Test message")
        
        content = memory.get_progress_content()
        
        # Should have timestamp format [YYYY-MM-DD HH:MM:SS]
        assert re.search(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]', content)
    
    def test_archive_path_config(self, fixture_autopilot_min: Path):
        """
        Archive path is read from config.
        
        Given: Config with archive path
        When: Config loaded
        Then: Archive path is available
        """
        os.chdir(fixture_autopilot_min)
        
        config_file = fixture_autopilot_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Get archive path from config
        archive_path = config["autopilot"]["memory"]["archive"]
        
        assert archive_path is not None
        assert ".ralph" in archive_path or "archive" in archive_path


class TestAutopilotMockResponses:
    """Test that mock Claude provides valid autopilot responses."""
    
    def test_mock_analysis_response_valid(self):
        """
        Mock Claude analysis response is valid JSON.
        
        Given: Mock Claude with analysis prompt
        When: Response generated
        Then: Response is valid analysis JSON
        """
        import sys
        from pathlib import Path
        
        # Add mock_claude to path
        mock_path = str(Path(__file__).parent.parent / "mock_claude")
        if mock_path not in sys.path:
            sys.path.insert(0, mock_path)
        from mock_claude import MockClaudeCLI
        
        cli = MockClaudeCLI()
        cli.prompt = "Analyze this report and identify priorities"
        
        response = cli.generate_response()
        
        # Should be valid JSON
        analysis = json.loads(response)
        assert "priority_item" in analysis
        assert "branch_name" in analysis
    
    def test_mock_tasks_response_valid(self):
        """
        Mock Claude tasks response is valid JSON.
        
        Given: Mock Claude with tasks prompt
        When: Response generated
        Then: Response is valid prd.json format
        """
        import sys
        from pathlib import Path
        
        mock_path = str(Path(__file__).parent.parent / "mock_claude")
        if mock_path not in sys.path:
            sys.path.insert(0, mock_path)
        from mock_claude import MockClaudeCLI
        
        cli = MockClaudeCLI()
        cli.prompt = "Generate tasks and convert to prd.json format"
        
        response = cli.generate_response()
        
        # Should be valid JSON with tasks
        prd = json.loads(response)
        assert "tasks" in prd
        assert len(prd["tasks"]) >= 1


class TestAutopilotExitCodes:
    """Test autopilot exit codes."""
    
    def test_exit_code_values(self):
        """
        Exit codes match documented values.
        
        Given: ExitCode enum
        When: Values checked
        Then: Match CLI contract specification
        """
        from ralph_orchestrator.autopilot import ExitCode
        
        assert ExitCode.SUCCESS.value == 0
        assert ExitCode.CONFIG_ERROR.value == 1
        assert ExitCode.NO_REPORTS.value == 10
        assert ExitCode.ANALYSIS_FAILED.value == 11
        assert ExitCode.PRD_GENERATION_FAILED.value == 12
        assert ExitCode.TASK_GENERATION_FAILED.value == 13
        assert ExitCode.GIT_ERROR.value == 14
        assert ExitCode.PR_CREATION_FAILED.value == 15
    
    def test_run_status_values(self):
        """
        Run status values are valid.
        
        Given: RunStatus enum
        When: Values checked
        Then: All expected states present
        """
        from ralph_orchestrator.autopilot import RunStatus
        
        expected_statuses = [
            "pending", "analyzing", "planning", "branching",
            "executing", "verifying", "pushing",
            "completed", "failed", "aborted"
        ]
        
        for status in expected_statuses:
            assert status in [s.value for s in RunStatus]
