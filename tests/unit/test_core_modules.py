"""Unit tests for core infrastructure modules.

Tests for:
- config.py: Configuration loader
- tasks/prd.py: Task loader/updater
- session.py: Session artifacts + checksum
- timeline.py: Timeline logger
- exec.py: Subprocess runner
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ralph_orchestrator.config import (
    RalphConfig,
    load_config,
    validate_against_schema,
    GateConfig,
    LimitsConfig,
)
from ralph_orchestrator.tasks.prd import (
    PRDData,
    Task,
    Subtask,
    load_prd,
    save_prd,
    get_pending_tasks,
    get_task_by_id,
    mark_task_complete,
    update_task_notes,
    generate_next_task_id,
)
from ralph_orchestrator.session import (
    Session,
    create_session,
    load_session,
    TamperingDetectedError,
    compute_checksum,
    generate_session_id,
    generate_session_token,
)
from ralph_orchestrator.timeline import (
    TimelineLogger,
    EventType,
    create_timeline_logger,
)
from ralph_orchestrator.exec import (
    ExecResult,
    run_command,
    CommandRunner,
    which,
)


# ============================================================================
# Config Module Tests
# ============================================================================

class TestConfigValidation:
    """Test schema validation functionality."""
    
    def test_validate_valid_config(self, fixture_python_min: Path):
        """Test validation passes for valid config."""
        config_path = fixture_python_min / ".ralph" / "ralph.yml"
        config = load_config(config_path, repo_root=fixture_python_min)
        assert config.version == "1"
        assert config.task_source_type == "prd_json"
    
    def test_validate_invalid_config_raises(self, tmp_path: Path):
        """Test validation fails for invalid config."""
        config_path = tmp_path / ".ralph" / "ralph.yml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("version: 2\n")  # Invalid version
        
        with pytest.raises(ValueError, match="Invalid configuration"):
            load_config(config_path, repo_root=tmp_path)
    
    def test_config_file_not_found_raises(self, tmp_path: Path):
        """Test appropriate error when config doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yml")


class TestConfigLoading:
    """Test configuration loading and parsing."""
    
    def test_load_python_config(self, fixture_python_min: Path):
        """Test loading Python fixture config."""
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        assert config.task_source_path == ".ralph/prd.json"
        assert len(config.gates_full) >= 1
        assert config.gates_full[0].name == "pytest"
    
    def test_load_fullstack_config(self, fixture_fullstack_min: Path):
        """Test loading fullstack fixture config."""
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        assert config.backend is not None
        assert config.frontend is not None
        assert config.backend.port > 0
    
    def test_config_path_resolution(self, fixture_python_min: Path):
        """Test path resolution relative to repo root."""
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        resolved = config.resolve_path(".ralph/prd.json")
        assert resolved.is_absolute()
        assert resolved.name == "prd.json"
    
    def test_config_gates_accessor(self, fixture_python_min: Path):
        """Test gate accessor methods."""
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        full_gates = config.get_gates("full")
        assert len(full_gates) >= 1
        
        no_gates = config.get_gates("none")
        assert len(no_gates) == 0


# ============================================================================
# PRD/Tasks Module Tests
# ============================================================================

class TestPRDLoading:
    """Test PRD file loading and validation."""
    
    def test_load_valid_prd(self, fixture_python_min: Path):
        """Test loading valid PRD file."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        
        assert prd.project == "Python Minimal Fixture"
        assert len(prd.tasks) == 2
    
    def test_prd_task_structure(self, fixture_python_min: Path):
        """Test task structure is properly parsed."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        
        task = prd.tasks[0]
        assert task.id == "T-001"
        assert task.title
        assert task.description
        assert len(task.acceptance_criteria) >= 1
        assert task.priority == 1
        assert task.passes is False
    
    def test_prd_file_not_found(self, tmp_path: Path):
        """Test error when PRD file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_prd(tmp_path / "nonexistent.json")
    
    def test_prd_invalid_json(self, tmp_path: Path):
        """Test error for invalid JSON."""
        prd_path = tmp_path / "prd.json"
        prd_path.write_text("not valid json")
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_prd(prd_path)


class TestPRDOperations:
    """Test PRD manipulation operations."""
    
    def test_get_pending_tasks(self, fixture_python_min: Path):
        """Test getting pending tasks."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        
        pending = get_pending_tasks(prd)
        assert len(pending) == 2
        # Should be sorted by priority
        assert pending[0].priority <= pending[1].priority
    
    def test_get_task_by_id(self, fixture_python_min: Path):
        """Test finding task by ID."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        
        task = get_task_by_id(prd, "T-001")
        assert task is not None
        assert task.id == "T-001"
        
        missing = get_task_by_id(prd, "T-999")
        assert missing is None
    
    def test_mark_task_complete(self, tmp_path: Path, fixture_python_min: Path):
        """Test marking a task complete."""
        # Copy PRD to temp location
        prd_path = tmp_path / "prd.json"
        original = (fixture_python_min / ".ralph" / "prd.json").read_text()
        prd_path.write_text(original)
        
        prd = load_prd(prd_path)
        mark_task_complete(prd, "T-001", notes="Test complete", save=True)
        
        # Verify in memory
        task = get_task_by_id(prd, "T-001")
        assert task.passes is True
        assert "Test complete" in task.notes
        
        # Verify on disk
        reloaded = load_prd(prd_path)
        assert get_task_by_id(reloaded, "T-001").passes is True
    
    def test_filter_specific_task(self, fixture_python_min: Path):
        """Test filtering to specific task."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        
        tasks = get_pending_tasks(prd, task_id="T-002")
        assert len(tasks) == 1
        assert tasks[0].id == "T-002"
    
    def test_generate_next_task_id(self, fixture_python_min: Path):
        """Test task ID generation."""
        prd = load_prd(fixture_python_min / ".ralph" / "prd.json")
        
        next_id = generate_next_task_id(prd)
        assert next_id == "T-003"


class TestPRDSerialization:
    """Test PRD serialization."""
    
    def test_task_to_dict(self):
        """Test task serialization."""
        task = Task(
            id="T-001",
            title="Test Task",
            description="Description",
            acceptance_criteria=["Criterion 1"],
            priority=1,
        )
        
        data = task.to_dict()
        assert data["id"] == "T-001"
        assert data["acceptanceCriteria"] == ["Criterion 1"]
    
    def test_task_roundtrip(self):
        """Test task serialize/deserialize roundtrip."""
        task = Task(
            id="T-001",
            title="Test Task",
            description="Description",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            priority=5,
            passes=True,
            notes="Some notes",
        )
        
        data = task.to_dict()
        restored = Task.from_dict(data)
        
        assert restored.id == task.id
        assert restored.priority == task.priority
        assert restored.passes == task.passes


# ============================================================================
# Session Module Tests
# ============================================================================

class TestSessionCreation:
    """Test session creation."""
    
    def test_create_session(self, tmp_path: Path):
        """Test creating a new session."""
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            config_path=".ralph/ralph.yml",
            pending_tasks=["T-001", "T-002"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )
        
        assert session.session_id is not None
        assert session.session_token.startswith("ralph-")
        assert session.session_dir.exists()
    
    def test_session_directory_structure(self, tmp_path: Path):
        """Test session creates proper directory structure."""
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )
        
        assert session.logs_dir.exists()
        assert session.artifacts_dir.exists()
        assert session.pids_dir.exists()
        assert session.screenshots_dir.exists()
        assert session.session_json_path.exists()
        assert session.task_status_path.exists()
    
    def test_session_id_format(self):
        """Test session ID format."""
        session_id = generate_session_id()
        # Format: YYYYMMDD-HHMMSS-hex
        parts = session_id.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # Date
        assert len(parts[1]) == 6  # Time
        assert len(parts[2]) == 16  # Hex


class TestSessionChecksum:
    """Test session checksum/anti-tampering."""
    
    def test_checksum_computation(self):
        """Test checksum computation is deterministic."""
        data = {"key": "value", "nested": {"a": 1}}
        
        checksum1 = compute_checksum(data)
        checksum2 = compute_checksum(data)
        
        assert checksum1 == checksum2
        assert checksum1.startswith("sha256:")
    
    def test_checksum_changes_with_data(self):
        """Test checksum changes when data changes."""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}
        
        assert compute_checksum(data1) != compute_checksum(data2)
    
    def test_checksum_verification_passes(self, tmp_path: Path):
        """Test checksum verification passes for valid data."""
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )
        
        # Should not raise
        assert session.verify_checksum() is True
    
    def test_tampering_detection(self, tmp_path: Path):
        """Test tampering is detected."""
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )
        
        # Tamper with the task status file
        status_content = session.task_status_path.read_text()
        tampered = status_content.replace('"passes": false', '"passes": true')
        session.task_status_path.write_text(tampered)
        
        # Should detect tampering
        with pytest.raises(TamperingDetectedError):
            load_session(
                session_dir=tmp_path / ".ralph-session",
                repo_root=tmp_path,
                verify_checksum=True,
            )


class TestSessionOperations:
    """Test session state operations."""
    
    def test_task_lifecycle(self, tmp_path: Path):
        """Test task start/complete lifecycle."""
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )
        
        # Start task
        session.start_task("T-001")
        assert session.metadata.current_task == "T-001"
        assert session.task_status.tasks["T-001"].started_at is not None
        
        # Complete task
        session.complete_task("T-001")
        assert session.task_status.tasks["T-001"].passes is True
        assert "T-001" in session.metadata.completed_tasks
    
    def test_iteration_tracking(self, tmp_path: Path):
        """Test iteration counting."""
        session = create_session(
            task_source="test.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=tmp_path / ".ralph-session",
            repo_root=tmp_path,
        )
        
        session.start_task("T-001")
        count1 = session.increment_iterations("T-001")
        count2 = session.increment_iterations("T-001")
        
        assert count1 == 1
        assert count2 == 2
        assert session.metadata.total_iterations == 2


# ============================================================================
# Timeline Module Tests
# ============================================================================

class TestTimelineLogger:
    """Test timeline event logging."""
    
    def test_log_event(self, tmp_path: Path):
        """Test basic event logging."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl", session_id="test-session")
        
        event = timeline.log(EventType.SESSION_START, details={"test": True})
        
        assert event["event"] == "session_start"
        assert event["session_id"] == "test-session"
        assert "ts" in event
    
    def test_read_events(self, tmp_path: Path):
        """Test reading logged events."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")
        
        timeline.session_start(task_count=5)
        timeline.task_start("T-001", title="Test")
        timeline.task_complete("T-001", iterations=1, duration_ms=1000)
        
        events = timeline.read_events()
        assert len(events) == 3
        assert events[0]["event"] == "session_start"
        assert events[1]["event"] == "task_start"
        assert events[2]["event"] == "task_complete"
    
    def test_filter_events_by_type(self, tmp_path: Path):
        """Test filtering events by type."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")
        
        timeline.session_start(task_count=2)
        timeline.task_start("T-001")
        timeline.task_start("T-002")
        timeline.task_complete("T-001", iterations=1)
        
        task_starts = timeline.get_events_by_type(EventType.TASK_START)
        assert len(task_starts) == 2
    
    def test_filter_events_by_task(self, tmp_path: Path):
        """Test filtering events by task ID."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")
        
        timeline.task_start("T-001")
        timeline.agent_start("T-001", "implementation")
        timeline.task_start("T-002")
        timeline.agent_start("T-002", "implementation")
        timeline.task_complete("T-001", iterations=1)
        
        t001_events = timeline.get_events_for_task("T-001")
        assert len(t001_events) == 3
        assert all(e.get("task_id") == "T-001" for e in t001_events)


class TestTimelineConvenienceMethods:
    """Test timeline convenience logging methods."""
    
    def test_agent_lifecycle(self, tmp_path: Path):
        """Test agent start/complete logging."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")
        
        timeline.agent_start("T-001", "implementation", model="claude-sonnet")
        timeline.agent_complete("T-001", "implementation", signal="task-done", duration_ms=5000)
        
        events = timeline.read_events()
        assert events[0]["role"] == "implementation"
        assert events[1]["signal"] == "task-done"
    
    def test_gate_events(self, tmp_path: Path):
        """Test gate pass/fail logging."""
        timeline = TimelineLogger(tmp_path / "timeline.jsonl")
        
        timeline.gates_run("full", gate_count=3)
        timeline.gate_pass("pytest", duration_ms=1000)
        timeline.gate_fail("mypy", "Type errors", duration_ms=500, fatal=True)
        
        events = timeline.read_events()
        assert events[1]["gate"] == "pytest"
        assert events[2]["gate"] == "mypy"
        assert events[2]["details"]["fatal"] is True


# ============================================================================
# Exec Module Tests
# ============================================================================

class TestCommandExecution:
    """Test command execution."""
    
    def test_run_simple_command(self):
        """Test running a simple command."""
        result = run_command("echo hello")
        
        assert result.success
        assert result.exit_code == 0
        assert "hello" in result.stdout
    
    def test_run_command_list_form(self):
        """Test running command in list form."""
        result = run_command(["echo", "hello", "world"])
        
        assert result.success
        assert "hello world" in result.stdout
    
    def test_command_failure(self):
        """Test command that fails."""
        result = run_command("exit 1", shell=True)
        
        assert not result.success
        assert result.exit_code == 1
    
    def test_command_not_found(self):
        """Test command that doesn't exist."""
        result = run_command("nonexistent_command_xyz123")
        
        assert not result.success
        assert result.exit_code in (127, -1)
    
    def test_command_timeout(self):
        """Test command timeout."""
        result = run_command("sleep 10", timeout=1)
        
        assert result.timed_out
        assert not result.success


class TestExecResult:
    """Test ExecResult dataclass."""
    
    def test_success_property(self):
        """Test success property."""
        result = ExecResult(
            command="test",
            exit_code=0,
            stdout="out",
            stderr="",
            duration_ms=100,
        )
        assert result.success
        
        result2 = ExecResult(
            command="test",
            exit_code=1,
            stdout="",
            stderr="error",
            duration_ms=100,
        )
        assert not result2.success
    
    def test_output_combined(self):
        """Test combined output property."""
        result = ExecResult(
            command="test",
            exit_code=0,
            stdout="stdout content",
            stderr="stderr content",
            duration_ms=100,
        )
        
        assert "stdout content" in result.output
        assert "stderr content" in result.output
    
    def test_truncated_output(self):
        """Test output truncation."""
        long_output = "x" * 10000
        result = ExecResult(
            command="test",
            exit_code=0,
            stdout=long_output,
            stderr="",
            duration_ms=100,
        )
        
        truncated = result.truncated_output(max_chars=1000)
        assert len(truncated) < len(long_output)
        assert "truncated" in truncated


class TestCommandRunner:
    """Test CommandRunner class."""
    
    def test_runner_tracks_history(self, tmp_path: Path):
        """Test runner tracks command history."""
        runner = CommandRunner(logs_dir=tmp_path / "logs")
        
        runner.run("echo one", name="test1")
        runner.run("echo two", name="test2")
        
        assert len(runner.history) == 2
        assert runner.history[0].stdout.strip() == "one"
    
    def test_runner_creates_logs(self, tmp_path: Path):
        """Test runner creates log files."""
        logs_dir = tmp_path / "logs"
        runner = CommandRunner(logs_dir=logs_dir)
        
        result = runner.run("echo test", name="echo")
        
        assert result.log_path is not None
        assert result.log_path.exists()
        content = result.log_path.read_text()
        assert "echo test" in content
    
    def test_runner_tracks_failures(self, tmp_path: Path):
        """Test runner tracks failed commands."""
        runner = CommandRunner(logs_dir=tmp_path / "logs")
        
        runner.run("echo success")
        runner.run("exit 1", shell=True)
        runner.run("echo also success")
        
        failed = runner.get_failed_commands()
        assert len(failed) == 1
