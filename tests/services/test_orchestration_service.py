"""Unit tests for OrchestrationService."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from ralph_orchestrator.services.orchestration_service import (
    EventType,
    TaskStartedEvent,
    TaskCompletedEvent,
    AgentPhaseChangedEvent,
    GateRunningEvent,
    GateCompletedEvent,
    SignalDetectedEvent,
)


class TestOrchestrationEvents:
    """Test orchestration event classes."""

    def test_task_started_event_to_dict(self):
        """Test TaskStartedEvent serialization."""
        event = TaskStartedEvent(task_id="T-001", task_title="Test Task")
        data = event.to_dict()
        
        assert data["event_type"] == "task_started"
        assert data["task_id"] == "T-001"
        assert data["task_title"] == "Test Task"
        assert "timestamp" in data

    def test_task_completed_event_to_dict(self):
        """Test TaskCompletedEvent serialization."""
        event = TaskCompletedEvent(
            task_id="T-001",
            success=True,
            iterations=3,
            duration_ms=5000
        )
        data = event.to_dict()
        
        assert data["event_type"] == "task_completed"
        assert data["task_id"] == "T-001"
        assert data["success"] is True
        assert data["iterations"] == 3
        assert data["duration_ms"] == 5000
        assert data["failure_reason"] is None

    def test_task_completed_event_with_failure(self):
        """Test TaskCompletedEvent with failure reason."""
        event = TaskCompletedEvent(
            task_id="T-002",
            success=False,
            iterations=5,
            duration_ms=10000,
            failure_reason="Max iterations exceeded"
        )
        data = event.to_dict()
        
        assert data["success"] is False
        assert data["failure_reason"] == "Max iterations exceeded"

    def test_agent_phase_changed_event(self):
        """Test AgentPhaseChangedEvent serialization."""
        event = AgentPhaseChangedEvent(
            task_id="T-001",
            phase="test_writing",
            previous_phase="implementation"
        )
        data = event.to_dict()
        
        assert data["event_type"] == "agent_phase_changed"
        assert data["task_id"] == "T-001"
        assert data["phase"] == "test_writing"
        assert data["previous_phase"] == "implementation"

    def test_gate_running_event(self):
        """Test GateRunningEvent serialization."""
        event = GateRunningEvent(
            task_id="T-001",
            gate_name="lint",
            gate_type="build"
        )
        data = event.to_dict()
        
        assert data["event_type"] == "gate_running"
        assert data["gate_name"] == "lint"
        assert data["gate_type"] == "build"

    def test_gate_completed_event(self):
        """Test GateCompletedEvent serialization."""
        event = GateCompletedEvent(
            task_id="T-001",
            gate_name="test",
            gate_type="full",
            passed=True,
            duration_ms=2500
        )
        data = event.to_dict()
        
        assert data["event_type"] == "gate_completed"
        assert data["passed"] is True
        assert data["duration_ms"] == 2500

    def test_gate_completed_event_with_output(self):
        """Test GateCompletedEvent with command output."""
        output = "ERROR: test_foo.py failed"
        event = GateCompletedEvent(
            task_id="T-001",
            gate_name="pytest",
            gate_type="full",
            passed=False,
            duration_ms=1200,
            output=output
        )
        data = event.to_dict()
        
        assert data["passed"] is False
        assert data["output"] == output

    def test_signal_detected_event(self):
        """Test SignalDetectedEvent serialization."""
        event = SignalDetectedEvent(
            task_id="T-001",
            signal_type="task-done",
            valid=True,
            token_valid=True,
            agent_role="implementation",
            content="Implementation complete"
        )
        data = event.to_dict()
        
        assert data["event_type"] == "signal_detected"
        assert data["signal_type"] == "task-done"
        assert data["valid"] is True
        assert data["token_valid"] is True
        assert data["agent_role"] == "implementation"
        assert data["content"] == "Implementation complete"

    def test_signal_detected_invalid_token(self):
        """Test SignalDetectedEvent with invalid token."""
        event = SignalDetectedEvent(
            task_id="T-001",
            signal_type="tests-done",
            valid=True,
            token_valid=False,
            agent_role="test_writing"
        )
        data = event.to_dict()
        
        assert data["valid"] is True
        assert data["token_valid"] is False


class TestEventType:
    """Test EventType enum."""

    def test_event_type_values(self):
        """Test that all expected event types are defined."""
        assert EventType.TASK_STARTED.value == "task_started"
        assert EventType.TASK_COMPLETED.value == "task_completed"
        assert EventType.AGENT_PHASE_CHANGED.value == "agent_phase_changed"
        assert EventType.GATE_RUNNING.value == "gate_running"
        assert EventType.GATE_COMPLETED.value == "gate_completed"
        assert EventType.SIGNAL_DETECTED.value == "signal_detected"
