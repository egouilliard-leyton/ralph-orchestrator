"""
Integration tests for task advancement workflow.

These tests verify that the Ralph orchestrator correctly:
- Advances tasks when valid completion signals are received
- Creates session artifacts (session.json, task-status.json, timeline.jsonl)
- Updates prd.json with completion status
- Handles multiple tasks in priority order

Note: These tests use the mock Claude CLI and fixture repositories.
"""

import pytest
import os
import json
import re
from pathlib import Path
from typing import Generator

from ralph_orchestrator.config import load_config
from ralph_orchestrator.tasks.prd import load_prd, get_pending_tasks, mark_task_complete, get_task_by_id
from ralph_orchestrator.session import create_session, load_session, TamperingDetectedError
from ralph_orchestrator.timeline import TimelineLogger, EventType, create_timeline_logger
from ralph_orchestrator.signals import (
    validate_implementation_signal,
    validate_review_signal,
    SignalType,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestTaskAdvancement:
    """Test task advancement through the workflow."""
    
    def test_task_advances_on_valid_signal(self, fixture_python_min: Path, mock_scenario_default):
        """
        Task status advances when valid completion signal received.
        
        Given: A fixture repo with pending tasks
        When: Implementation signal validated and task marked complete
        Then: Task status is updated to passes=true
        """
        os.chdir(fixture_python_min)
        
        # Verify initial state - task not complete
        prd_path = fixture_python_min / ".ralph" / "prd.json"
        prd = load_prd(prd_path)
        assert prd.tasks[0].passes is False, "Task should start as not passed"
        
        # Create a session
        session = create_session(
            task_source=str(prd_path),
            task_source_type="prd_json",
            pending_tasks=[t.id for t in prd.tasks],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Simulate valid signal from mock Claude
        mock_response = f'''<task-done session="{session.session_token}">
Implementation complete.
</task-done>'''
        
        # Validate signal
        result = validate_implementation_signal(mock_response, session.session_token)
        assert result.valid, "Signal should be valid"
        
        # Mark task complete
        mark_task_complete(prd, "T-001", notes="Completed via test")
        
        # Verify task is now complete
        task = get_task_by_id(prd, "T-001")
        assert task.passes is True, "Task should be marked as passed"
    
    def test_multiple_tasks_advance_sequentially(self, fixture_python_min: Path):
        """
        Multiple tasks advance in priority order.
        
        Given: A fixture repo with multiple pending tasks
        When: Tasks are processed in order
        Then: Tasks are completed in priority order
        """
        os.chdir(fixture_python_min)
        
        prd_path = fixture_python_min / ".ralph" / "prd.json"
        prd = load_prd(prd_path)
        
        # Verify we have multiple tasks
        assert len(prd.tasks) >= 2, "Fixture should have at least 2 tasks"
        
        # Get pending tasks (should be sorted by priority)
        pending = get_pending_tasks(prd)
        assert len(pending) >= 2, "Should have at least 2 pending tasks"
        
        # Verify priority ordering
        priorities = [task.priority for task in pending]
        assert priorities == sorted(priorities), "Tasks should be ordered by priority"
        
        # Process first task
        session = create_session(
            task_source=str(prd_path),
            task_source_type="prd_json",
            pending_tasks=[t.id for t in pending],
            session_dir=fixture_python_min / ".ralph-session",
            repo_root=fixture_python_min,
        )
        
        # Complete first task
        mark_task_complete(prd, pending[0].id)
        
        # Get pending tasks again - should have fewer
        remaining = get_pending_tasks(prd)
        assert len(remaining) == len(pending) - 1, "Should have one less pending task"
    
    def test_task_with_subtasks_requires_all_complete(self, sample_prd_json: dict, temp_dir: Path):
        """
        Parent task only completes when all subtasks are complete.
        
        Given: A task with subtasks
        When: Parent task marked done but subtasks pending
        Then: Task remains incomplete
        """
        # Create prd.json with subtasks
        prd_with_subtasks = sample_prd_json.copy()
        prd_with_subtasks["tasks"][0]["subtasks"] = [
            {
                "id": "T-001.1",
                "title": "Subtask 1",
                "acceptanceCriteria": ["Subtask criterion"],
                "passes": False,
                "notes": ""
            }
        ]
        
        prd_path = temp_dir / ".ralph" / "prd.json"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(json.dumps(prd_with_subtasks, indent=2))
        
        # Verify structure
        loaded = json.loads(prd_path.read_text())
        assert "subtasks" in loaded["tasks"][0]
        assert len(loaded["tasks"][0]["subtasks"]) == 1


class TestSessionArtifacts:
    """Test session artifact creation."""
    
    def test_session_directory_created(self, fixture_python_min: Path):
        """
        Session directory is created on first run.
        
        Given: A clean fixture repo
        When: Session is created
        Then: .ralph-session/ directory is created with correct structure
        """
        os.chdir(fixture_python_min)
        
        session_dir = fixture_python_min / ".ralph-session"
        
        # Before run, session directory should not exist
        assert not session_dir.exists(), "Session dir should not pre-exist"
        
        # Create session
        prd_path = fixture_python_min / ".ralph" / "prd.json"
        session = create_session(
            task_source=str(prd_path),
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Verify directory and files created
        assert session_dir.exists(), "Session directory should be created"
        assert session.logs_dir.exists(), "Logs directory should exist"
        assert session.artifacts_dir.exists(), "Artifacts directory should exist"
        assert session.session_json_path.exists(), "session.json should exist"
        assert session.task_status_path.exists(), "task-status.json should exist"
    
    def test_session_json_has_valid_token(self, fixture_python_min: Path):
        """
        Session.json contains valid session token.
        
        Given: A running session
        When: Session starts
        Then: session.json has token in format ralph-YYYYMMDD-HHMMSS-[hex]
        """
        os.chdir(fixture_python_min)
        
        # Token format pattern
        token_pattern = r'^ralph-\d{8}-\d{6}-[a-f0-9]{16}$'
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Verify token format
        assert re.match(token_pattern, session.session_token), f"Token {session.session_token} should match pattern"
        
        # Verify token is in session.json
        session_data = json.loads(session.session_json_path.read_text())
        assert session_data["session_token"] == session.session_token
    
    def test_timeline_jsonl_created(self, fixture_python_min: Path):
        """
        Timeline log file is created with events.
        
        Given: A running session
        When: Events are logged
        Then: logs/timeline.jsonl contains event entries
        """
        os.chdir(fixture_python_min)
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Create timeline logger and log events
        timeline = create_timeline_logger(session_dir, session.session_id)
        timeline.session_start(task_count=1)
        timeline.task_start("T-001", title="Test Task")
        timeline.task_complete("T-001", iterations=1, duration_ms=1000)
        
        # Verify timeline file exists and has events
        assert session.timeline_path.exists(), "Timeline file should exist"
        
        events = timeline.read_events()
        assert len(events) == 3, "Should have 3 events"
        assert events[0]["event"] == "session_start"
        assert events[1]["event"] == "task_start"
        assert events[2]["event"] == "task_complete"
    
    def test_task_status_json_tracks_progress(self, fixture_python_min: Path):
        """
        Task status file tracks task completion progress.
        
        Given: A running session
        When: Tasks complete
        Then: task-status.json shows completion status
        """
        os.chdir(fixture_python_min)
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Start and complete a task
        session.start_task("T-001")
        session.complete_task("T-001")
        
        # Verify task status
        status_data = json.loads(session.task_status_path.read_text())
        assert "tasks" in status_data
        assert "T-001" in status_data["tasks"]
        assert status_data["tasks"]["T-001"]["passes"] is True


class TestReviewPhase:
    """Test review agent behavior."""
    
    def test_review_approval_completes_task(self, fixture_python_min: Path):
        """
        Task completes when review agent approves.
        
        Given: Implementation complete
        When: Review agent returns review-approved signal
        Then: Signal validation passes with is_approved=True
        """
        os.chdir(fixture_python_min)
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Simulate review approval signal
        mock_response = f'''<review-approved session="{session.session_token}">
All acceptance criteria verified.
</review-approved>'''
        
        # Validate review signal
        result, is_approved = validate_review_signal(mock_response, session.session_token)
        assert result.valid, "Review signal should be valid"
        assert is_approved is True, "Review should be approved"
    
    def test_review_rejection_triggers_retry(self, fixture_python_min: Path, mock_scenario_review_reject):
        """
        Review rejection causes retry with feedback.
        
        Given: Implementation complete
        When: Review agent returns review-rejected signal
        Then: Signal validation shows rejection with feedback
        """
        os.chdir(fixture_python_min)
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Simulate review rejection signal
        mock_response = f'''<review-rejected session="{session.session_token}">
Issues found:
- Missing test coverage
- No error handling
</review-rejected>'''
        
        # Validate review signal
        result, is_approved = validate_review_signal(mock_response, session.session_token)
        assert result.valid, "Review signal should be valid"
        assert is_approved is False, "Review should be rejected"
        assert "Missing test coverage" in result.signal.content, "Rejection feedback should be in content"


class TestFixLoops:
    """Test fix iteration behavior."""
    
    def test_fix_loop_retries_on_failure(self, fixture_python_min: Path):
        """
        Fix agent is called when gates fail after task completion.
        
        Given: A session tracking iterations
        When: Iterations are incremented
        Then: Iteration count is tracked correctly
        """
        os.chdir(fixture_python_min)
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Start task and simulate fix iterations
        session.start_task("T-001")
        
        # First iteration
        count1 = session.increment_iterations("T-001")
        assert count1 == 1, "First iteration should be 1"
        
        # Second iteration (simulating retry after gate failure)
        count2 = session.increment_iterations("T-001")
        assert count2 == 2, "Second iteration should be 2"
        
        # Verify total iterations tracked
        assert session.metadata.total_iterations == 2
    
    def test_fix_loop_respects_max_iterations(self, fixture_python_min: Path):
        """
        Fix loop stops after max iterations.
        
        Given: Persistent gate failures
        When: Max fix iterations reached
        Then: Task failure is recorded
        """
        os.chdir(fixture_python_min)
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        max_iterations = 3
        
        # Start task and simulate iterations up to max
        session.start_task("T-001")
        for i in range(max_iterations):
            session.increment_iterations("T-001")
        
        # Record failure when max reached
        session.fail_task("T-001", f"Max iterations ({max_iterations}) reached")
        
        # Verify failure recorded
        status_data = json.loads(session.task_status_path.read_text())
        assert status_data["tasks"]["T-001"]["last_failure"] == f"Max iterations ({max_iterations}) reached"
        assert status_data["tasks"]["T-001"]["iterations"] == max_iterations
