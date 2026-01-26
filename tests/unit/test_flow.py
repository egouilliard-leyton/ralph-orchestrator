"""Unit tests for flow module non-interactive pieces.

Tests for:
- Approval gate behavior (stops without --yes, blocks in non-TTY)
- Tasks structured output handling and schema validation
- Task count parsing
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ralph_orchestrator.flow import (
    _prompt_approval,
    FlowOptions,
    FlowResult,
)
from ralph_orchestrator.cli import (
    _invoke_claude_structured,
    _parse_task_count,
    generate_tasks_from_markdown,
    TaskGenerationResult,
    validate_against_schema,
)


# ============================================================================
# Approval Gate Tests
# ============================================================================

class TestPromptApproval:
    """Test the approval gate functionality."""
    
    def _make_sample_tasks(self, count: int = 3) -> list:
        """Create sample tasks for testing."""
        return [
            {
                "id": f"T-{i+1:03d}",
                "title": f"Test Task {i+1}",
                "description": f"Description for task {i+1}",
                "acceptanceCriteria": ["Criterion 1"],
                "priority": i + 1,
                "passes": False,
                "notes": "",
            }
            for i in range(count)
        ]
    
    def test_approval_blocks_in_non_tty(self, tmp_path: Path, capsys):
        """Test that approval returns False in non-interactive mode."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        # Mock stdin.isatty() to return False (non-interactive)
        with patch.object(sys.stdin, 'isatty', return_value=False):
            result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is False
        captured = capsys.readouterr()
        assert "non-interactive" in captured.err.lower() or "Cannot prompt" in captured.err
    
    def test_approval_accepts_y(self, tmp_path: Path):
        """Test that approval returns True when user enters 'y'."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='y'):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is True
    
    def test_approval_accepts_yes(self, tmp_path: Path):
        """Test that approval returns True when user enters 'yes'."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='yes'):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is True
    
    def test_approval_accepts_Y_uppercase(self, tmp_path: Path):
        """Test that approval returns True when user enters 'Y' (uppercase)."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='Y'):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is True
    
    def test_approval_rejects_n(self, tmp_path: Path):
        """Test that approval returns False when user enters 'n'."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='n'):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is False
    
    def test_approval_rejects_empty_input(self, tmp_path: Path):
        """Test that approval returns False when user enters empty input."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value=''):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is False
    
    def test_approval_rejects_arbitrary_input(self, tmp_path: Path):
        """Test that approval returns False for arbitrary input."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='maybe'):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is False
    
    def test_approval_handles_eof_error(self, tmp_path: Path):
        """Test that approval returns False on EOFError."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', side_effect=EOFError()):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is False
    
    def test_approval_handles_keyboard_interrupt(self, tmp_path: Path):
        """Test that approval returns False on KeyboardInterrupt."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks()
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', side_effect=KeyboardInterrupt()):
                result = _prompt_approval(md_path, json_path, tasks)
        
        assert result is False
    
    def test_approval_displays_task_preview(self, tmp_path: Path, capsys):
        """Test that approval displays task preview correctly."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks(5)
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='n'):
                _prompt_approval(md_path, json_path, tasks)
        
        captured = capsys.readouterr()
        # Check that task IDs are displayed
        assert "T-001" in captured.out
        assert "T-002" in captured.out
        assert "Task count:" in captured.out
        assert "5" in captured.out
    
    def test_approval_truncates_many_tasks(self, tmp_path: Path, capsys):
        """Test that approval truncates display when many tasks."""
        md_path = tmp_path / "test.md"
        json_path = tmp_path / "prd.json"
        md_path.touch()
        json_path.touch()
        
        tasks = self._make_sample_tasks(15)
        
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('builtins.input', return_value='n'):
                _prompt_approval(md_path, json_path, tasks)
        
        captured = capsys.readouterr()
        # Should show first 10 tasks and indicate more
        assert "T-010" in captured.out
        assert "5 more" in captured.out  # 15 - 10 = 5 more


# ============================================================================
# Task Count Parsing Tests
# ============================================================================

class TestTaskCountParsing:
    """Test task count range parsing."""
    
    def test_parse_range_format(self):
        """Test parsing range format like '8-15'."""
        min_count, max_count = _parse_task_count("8-15")
        assert min_count == 8
        assert max_count == 15
    
    def test_parse_single_number(self):
        """Test parsing single number like '10'."""
        min_count, max_count = _parse_task_count("10")
        assert min_count == 10
        assert max_count == 10
    
    def test_parse_with_spaces(self):
        """Test parsing with spaces around numbers."""
        min_count, max_count = _parse_task_count("  5 - 12  ")
        assert min_count == 5
        assert max_count == 12
    
    def test_parse_empty_returns_none(self):
        """Test parsing empty string returns None."""
        min_count, max_count = _parse_task_count("")
        assert min_count is None
        assert max_count is None
    
    def test_parse_none_returns_none(self):
        """Test parsing None returns None."""
        min_count, max_count = _parse_task_count(None)
        assert min_count is None
        assert max_count is None


# ============================================================================
# Structured Output Handling Tests
# ============================================================================

class TestInvokeClaudeStructured:
    """Test Claude structured output extraction."""
    
    def test_extracts_structured_output_field(self):
        """Test that structured_output field is correctly extracted."""
        mock_response = {
            "structured_output": {
                "project": "Test",
                "tasks": []
            },
            "other_field": "ignored"
        }
        
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )
            
            result = _invoke_claude_structured(
                prompt="test",
                schema={"type": "object"},
                model="sonnet"
            )
        
        assert result == {"project": "Test", "tasks": []}
    
    def test_handles_direct_json_response(self):
        """Test handling when Claude returns JSON directly without structured_output wrapper."""
        mock_response = {
            "project": "Direct Test",
            "tasks": [{"id": "T-001"}]
        }
        
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )
            
            result = _invoke_claude_structured(
                prompt="test",
                schema={"type": "object"},
                model="sonnet"
            )
        
        assert result == mock_response
    
    def test_raises_on_non_zero_exit(self):
        """Test that RuntimeError is raised on non-zero exit code."""
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Claude error message"
            )
            
            with pytest.raises(RuntimeError, match="Claude error message"):
                _invoke_claude_structured(
                    prompt="test",
                    schema={"type": "object"},
                    model="sonnet"
                )
    
    def test_raises_on_empty_output(self):
        """Test that RuntimeError is raised when output is not valid structured output."""
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([1, 2, 3]),  # Array, not object
                stderr=""
            )
            
            with pytest.raises(RuntimeError, match="structured output"):
                _invoke_claude_structured(
                    prompt="test",
                    schema={"type": "object"},
                    model="sonnet"
                )


# ============================================================================
# Schema Validation Tests
# ============================================================================

class TestSchemaValidation:
    """Test PRD schema validation for generated tasks."""
    
    def test_valid_prd_passes_validation(self):
        """Test that valid PRD data passes schema validation."""
        valid_prd = {
            "project": "Test Project",
            "branchName": "ralph/test",
            "description": "Test description",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "First task",
                    "description": "Do something",
                    "acceptanceCriteria": ["Criterion 1"],
                    "priority": 1,
                    "passes": False,
                    "notes": ""
                }
            ]
        }
        
        ok, errors = validate_against_schema(valid_prd, "schemas/prd.schema.json")
        assert ok is True
        assert len(errors) == 0
    
    def test_missing_required_field_fails(self):
        """Test that missing required field fails validation."""
        invalid_prd = {
            "project": "Test Project",
            # Missing description
            "tasks": []
        }
        
        ok, errors = validate_against_schema(invalid_prd, "schemas/prd.schema.json")
        assert ok is False
        assert len(errors) > 0
    
    def test_empty_tasks_fails(self):
        """Test that empty tasks array fails validation."""
        invalid_prd = {
            "project": "Test Project",
            "description": "Test",
            "tasks": []  # Empty - should fail minItems
        }
        
        ok, errors = validate_against_schema(invalid_prd, "schemas/prd.schema.json")
        assert ok is False
    
    def test_task_missing_acceptance_criteria_fails(self):
        """Test that task without acceptanceCriteria fails."""
        invalid_prd = {
            "project": "Test Project",
            "description": "Test",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task",
                    "description": "Desc",
                    # Missing acceptanceCriteria
                    "priority": 1,
                    "passes": False,
                }
            ]
        }
        
        ok, errors = validate_against_schema(invalid_prd, "schemas/prd.schema.json")
        assert ok is False
    
    def test_empty_acceptance_criteria_fails(self):
        """Test that empty acceptanceCriteria array fails."""
        invalid_prd = {
            "project": "Test Project",
            "description": "Test",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task",
                    "description": "Desc",
                    "acceptanceCriteria": [],  # Empty - should fail minItems
                    "priority": 1,
                    "passes": False,
                }
            ]
        }
        
        ok, errors = validate_against_schema(invalid_prd, "schemas/prd.schema.json")
        assert ok is False


# ============================================================================
# Generate Tasks From Markdown Tests
# ============================================================================

class TestGenerateTasksFromMarkdown:
    """Test the generate_tasks_from_markdown helper."""
    
    def test_source_not_found_raises(self, tmp_path: Path):
        """Test that FileNotFoundError is raised when source doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            generate_tasks_from_markdown(
                src=tmp_path / "nonexistent.md",
                out=tmp_path / "prd.json",
            )
    
    def test_creates_output_directory(self, tmp_path: Path):
        """Test that output directory is created if needed."""
        src = tmp_path / "source.md"
        src.write_text("# Test PRD\n\nThis is a test.")
        
        out = tmp_path / "subdir" / "nested" / "prd.json"
        
        # Mock the Claude call to return valid data
        mock_response = {
            "structured_output": {
                "project": "Test",
                "description": "Test desc",
                "branchName": "ralph/test",
                "tasks": [
                    {
                        "id": "T-001",
                        "title": "Task",
                        "description": "Desc",
                        "acceptanceCriteria": ["AC1"],
                        "priority": 1,
                        "passes": False,
                        "notes": ""
                    }
                ]
            }
        }
        
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )
            
            result = generate_tasks_from_markdown(
                src=src,
                out=out,
                verbose=False,
            )
        
        assert out.parent.exists()
        assert result.path == out
    
    def test_returns_task_count(self, tmp_path: Path):
        """Test that correct task count is returned."""
        src = tmp_path / "source.md"
        src.write_text("# Test\n\nContent")
        out = tmp_path / "prd.json"
        
        mock_response = {
            "structured_output": {
                "project": "Test",
                "description": "Test",
                "branchName": "ralph/test",
                "tasks": [
                    {"id": "T-001", "title": "T1", "description": "D1", "acceptanceCriteria": ["AC1"], "priority": 1, "passes": False, "notes": ""},
                    {"id": "T-002", "title": "T2", "description": "D2", "acceptanceCriteria": ["AC2"], "priority": 2, "passes": False, "notes": ""},
                    {"id": "T-003", "title": "T3", "description": "D3", "acceptanceCriteria": ["AC3"], "priority": 3, "passes": False, "notes": ""},
                ]
            }
        }
        
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )
            
            result = generate_tasks_from_markdown(
                src=src,
                out=out,
                verbose=False,
            )
        
        assert result.task_count == 3
    
    def test_invalid_schema_raises_value_error(self, tmp_path: Path):
        """Test that invalid schema raises ValueError."""
        src = tmp_path / "source.md"
        src.write_text("# Test\n\nContent")
        out = tmp_path / "prd.json"
        
        # Response missing required fields
        mock_response = {
            "structured_output": {
                "project": "Test",
                # Missing description and tasks
            }
        }
        
        with patch('ralph_orchestrator.cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )
            
            with pytest.raises(ValueError, match="Invalid"):
                generate_tasks_from_markdown(
                    src=src,
                    out=out,
                    verbose=False,
                )
    
    def test_generates_branch_name_from_source(self, tmp_path: Path):
        """Test that branch name is auto-generated from source filename."""
        src = tmp_path / "CR-add-feature.md"
        src.write_text("# Test\n\nContent")
        out = tmp_path / "prd.json"
        
        captured_prompt = None
        
        def capture_call(*args, **kwargs):
            nonlocal captured_prompt
            captured_prompt = kwargs.get('input', '')
            return MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "structured_output": {
                        "project": "Test",
                        "description": "Test",
                        "branchName": "ralph/test",
                        "tasks": [
                            {"id": "T-001", "title": "T", "description": "D", "acceptanceCriteria": ["AC"], "priority": 1, "passes": False, "notes": ""}
                        ]
                    }
                }),
                stderr=""
            )
        
        with patch('ralph_orchestrator.cli.subprocess.run', side_effect=capture_call):
            generate_tasks_from_markdown(
                src=src,
                out=out,
                verbose=False,
            )
        
        # Check that the prompt includes auto-generated branch name
        assert captured_prompt is not None
        assert "cr-add-feature" in captured_prompt.lower()


# ============================================================================
# FlowOptions Tests
# ============================================================================

class TestFlowOptions:
    """Test FlowOptions dataclass defaults."""
    
    def test_default_values(self):
        """Test default option values."""
        options = FlowOptions()
        
        assert options.mode == "change"
        assert options.task_count == "8-15"
        assert options.model == "sonnet"
        assert options.skip_approval is False
        assert options.template == "auto"
        assert options.force is False
        assert options.max_iterations == 30
        assert options.gate_type == "full"
        assert options.dry_run is False
        assert options.verbose is False
    
    def test_custom_values(self):
        """Test setting custom option values."""
        options = FlowOptions(
            mode="new",
            task_count="5-10",
            model="opus",
            skip_approval=True,
            template="python",
            force=True,
            max_iterations=50,
        )
        
        assert options.mode == "new"
        assert options.task_count == "5-10"
        assert options.model == "opus"
        assert options.skip_approval is True
        assert options.template == "python"
        assert options.force is True
        assert options.max_iterations == 50


# ============================================================================
# FlowResult Tests
# ============================================================================

class TestFlowResult:
    """Test FlowResult dataclass."""
    
    def test_success_result(self, tmp_path: Path):
        """Test successful flow result."""
        result = FlowResult(
            success=True,
            md_path=tmp_path / "cr.md",
            json_path=tmp_path / "prd.json",
            tasks_count=10,
        )
        
        assert result.success is True
        assert result.error is None
        assert result.aborted_at is None
    
    def test_failure_result(self):
        """Test failed flow result."""
        result = FlowResult(
            success=False,
            error="Test error message",
            aborted_at="tasks",
        )
        
        assert result.success is False
        assert result.error == "Test error message"
        assert result.aborted_at == "tasks"
    
    def test_aborted_at_approval(self, tmp_path: Path):
        """Test result when aborted at approval stage."""
        result = FlowResult(
            success=True,  # Flow completed, just didn't run
            md_path=tmp_path / "cr.md",
            json_path=tmp_path / "prd.json",
            tasks_count=5,
            aborted_at="approval",
        )
        
        assert result.success is True
        assert result.aborted_at == "approval"
        assert result.run_result is None
