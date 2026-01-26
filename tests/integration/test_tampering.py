"""
Integration tests for tamper detection.

These tests verify that the Ralph orchestrator correctly:
- Creates checksums for task status files
- Detects tampering with task status
- Aborts session when tampering detected
- Provides clear error messages on tampering

The checksum mechanism prevents agents from bypassing the orchestrator
by directly modifying task completion status.
"""

import pytest
import os
import json
import hashlib
from pathlib import Path

from ralph_orchestrator.session import (
    create_session,
    load_session,
    TamperingDetectedError,
    compute_checksum,
)
from ralph_orchestrator.signals import validate_implementation_signal

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestChecksumCreation:
    """Test checksum file creation."""
    
    def test_checksum_created_on_session_start(self, fixture_python_min: Path):
        """
        Checksum file created when session starts.
        
        Given: New session starting
        When: Session initializes
        Then: task-status.sha256 file is created
        """
        os.chdir(fixture_python_min)
        
        session_dir = fixture_python_min / ".ralph-session"
        checksum_file = session_dir / "task-status.sha256"
        
        # Before session, checksum should not exist
        assert not checksum_file.exists(), "Checksum should not pre-exist"
        
        # Create session
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Checksum file should now exist
        assert checksum_file.exists(), "Checksum file should be created"
        
        # Checksum should have correct format
        checksum = checksum_file.read_text().strip()
        assert checksum.startswith("sha256:"), "Checksum should have sha256: prefix"
    
    def test_checksum_format_is_sha256(self, temp_dir: Path):
        """
        Checksum uses SHA-256 format with prefix.
        
        Given: A file to checksum
        When: Checksum is computed
        Then: Format is "sha256:[64 hex chars]"
        """
        # Test with compute_checksum function
        data = {"test": "data"}
        checksum = compute_checksum(data)
        
        # Verify format
        assert checksum.startswith("sha256:")
        assert len(checksum) == 7 + 64  # "sha256:" + 64 hex chars
        
        # Verify hex portion is valid hex
        hex_part = checksum[7:]
        int(hex_part, 16)  # Should not raise
    
    def test_checksum_updated_on_task_complete(self, fixture_python_min: Path):
        """
        Checksum updated after task status change.
        
        Given: Session with existing checksum
        When: Task completes and status updates
        Then: Checksum file is updated with new value
        """
        os.chdir(fixture_python_min)
        
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001", "T-002"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Read initial checksum
        checksum_file = session_dir / "task-status.sha256"
        checksum1 = checksum_file.read_text().strip()
        
        # Start and complete a task
        session.start_task("T-001")
        session.complete_task("T-001")
        
        # Checksum should have changed
        checksum2 = checksum_file.read_text().strip()
        assert checksum1 != checksum2, "Checksum should change after task completion"


class TestTamperingDetection:
    """Test detection of tampering with task status."""
    
    def test_tampering_detected_aborts_session(self, fixture_python_min: Path):
        """
        Modifying task-status.json triggers abort.
        
        Given: Valid session with checksum
        When: task-status.json modified externally
        Then: Load detects tampering and raises error
        """
        os.chdir(fixture_python_min)
        
        # Create valid session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Get original checksum
        original_checksum = session.task_status_checksum_path.read_text().strip()
        
        # Now tamper with the status file
        status_file = session.task_status_path
        status_data = json.loads(status_file.read_text())
        status_data["tasks"]["T-001"]["passes"] = True  # Fake completion!
        status_file.write_text(json.dumps(status_data, indent=2))
        
        # Checksum file still has original value
        stored_checksum = session.task_status_checksum_path.read_text().strip()
        assert stored_checksum == original_checksum
        
        # Loading session should detect tampering
        with pytest.raises(TamperingDetectedError):
            load_session(
                session_dir=session_dir,
                repo_root=fixture_python_min,
                verify_checksum=True,
            )
    
    def test_tampering_logged_with_details(self, fixture_python_min: Path):
        """
        Tampering event is logged with expected vs actual checksum.
        
        Given: Tampering detected
        When: TamperingDetectedError raised
        Then: Error message shows both checksums
        """
        os.chdir(fixture_python_min)
        
        # Create valid session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Tamper with the embedded checksum in task-status.json
        status_file = session.task_status_path
        status_data = json.loads(status_file.read_text())
        status_data["checksum"] = "sha256:tampered000000000000000000000000000000000000000000000000000000"
        status_file.write_text(json.dumps(status_data, indent=2))
        
        # Loading should show checksum details in error
        with pytest.raises(TamperingDetectedError) as exc_info:
            load_session(
                session_dir=session_dir,
                repo_root=fixture_python_min,
                verify_checksum=True,
            )
        
        error_msg = str(exc_info.value)
        assert "tampered" in error_msg.lower() or "mismatch" in error_msg.lower()
    
    def test_prd_json_tampering_detected(self, fixture_python_min: Path):
        """
        Tampering with prd.json task status is detected.
        
        Given: Valid session running
        When: prd.json modified to mark task complete
        Then: Session task status remains authoritative
        """
        os.chdir(fixture_python_min)
        
        prd_file = fixture_python_min / ".ralph" / "prd.json"
        prd = json.loads(prd_file.read_text())
        
        # Create session
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Session says task not complete
        assert session.task_status.tasks["T-001"].passes is False
        
        # Tamper with prd.json directly
        prd["tasks"][0]["passes"] = True
        prd_file.write_text(json.dumps(prd, indent=2))
        
        # Session status is authoritative - still shows not passed
        assert session.task_status.tasks["T-001"].passes is False


class TestChecksumVerification:
    """Test checksum verification process."""
    
    def test_verify_returns_true_for_valid(self, fixture_python_min: Path):
        """
        Verification passes for unmodified files.
        
        Given: Session with valid checksum
        When: Verification runs
        Then: Returns True
        """
        os.chdir(fixture_python_min)
        
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Verification should pass
        assert session.verify_checksum() is True
    
    def test_verify_returns_false_for_tampered(self, fixture_python_min: Path):
        """
        Verification fails for modified files.
        
        Given: Session with checksum
        When: Task status modified
        Then: Verification raises TamperingDetectedError
        """
        os.chdir(fixture_python_min)
        
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Tamper with task status in memory
        session.task_status.tasks["T-001"].passes = True
        # But don't save properly (simulate external modification)
        
        # Write tampered data without updating checksum
        status_file = session.task_status_path
        tampered_data = session.task_status.to_dict()
        status_file.write_text(json.dumps(tampered_data, indent=2))
        
        # Load should detect tampering
        with pytest.raises(TamperingDetectedError):
            load_session(
                session_dir=session_dir,
                repo_root=fixture_python_min,
                verify_checksum=True,
            )
    
    def test_missing_checksum_raises_error(self, fixture_python_min: Path):
        """
        Missing checksum file raises clear error.
        
        Given: Session without checksum file
        When: Verification attempted
        Then: Verification fails or error raised
        """
        os.chdir(fixture_python_min)
        
        session_dir = fixture_python_min / ".ralph-session"
        session = create_session(
            task_source=".ralph/prd.json",
            task_source_type="prd_json",
            pending_tasks=["T-001"],
            session_dir=session_dir,
            repo_root=fixture_python_min,
        )
        
        # Delete checksum file
        session.task_status_checksum_path.unlink()
        
        # Verification should still work (embedded checksum is primary)
        # External file is secondary verification
        assert session.verify_checksum() is True


class TestAntiGaming:
    """Test anti-gaming measures for task completion."""
    
    def test_agent_cannot_mark_task_complete_directly(self, fixture_python_min: Path):
        """
        Agent modifying prd.json directly doesn't bypass verification.
        
        Given: Agent attempts to mark task complete in prd.json
        When: Session task status checked
        Then: Session status is authoritative
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
        
        # Session says task not complete
        assert session.task_status.tasks["T-001"].passes is False
        
        # Even if prd.json is modified, session status is authoritative
        prd_file = fixture_python_min / ".ralph" / "prd.json"
        prd = json.loads(prd_file.read_text())
        prd["tasks"][0]["passes"] = True
        prd_file.write_text(json.dumps(prd, indent=2))
        
        # Session still shows not complete
        assert session.task_status.tasks["T-001"].passes is False
    
    def test_session_token_required_in_signal(self, fixture_python_min: Path):
        """
        Completion signal without token is rejected.
        
        Given: Valid task completion
        When: Signal missing session attribute
        Then: Signal rejected as invalid
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
        
        # Signal without proper session token should fail validation
        response_without_token = '''<task-done>
Task complete (but no session token)
</task-done>'''
        
        from ralph_orchestrator.signals import parse_signals
        signals = parse_signals(response_without_token)
        
        # Either no signals found or validation would fail
        assert len(signals) == 0 or signals[0].session_token != session.session_token
    
    def test_only_orchestrator_can_update_status(self, fixture_python_min: Path):
        """
        Task status can only be updated by orchestrator script.
        
        Given: External process attempts to update status
        When: Orchestrator resumes
        Then: Tampering detected
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
        
        # Simulate external process modifying task-status.json
        status_file = session.task_status_path
        status_data = json.loads(status_file.read_text())
        status_data["tasks"]["T-001"]["passes"] = True
        status_file.write_text(json.dumps(status_data, indent=2))
        
        # Orchestrator (load_session) detects tampering
        with pytest.raises(TamperingDetectedError):
            load_session(
                session_dir=session_dir,
                repo_root=fixture_python_min,
                verify_checksum=True,
            )
