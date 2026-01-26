"""Unit tests for quality gate execution."""

import pytest
from pathlib import Path

from ralph_orchestrator.gates import (
    GateResult,
    GatesResult,
    GateRunner,
    format_gate_failure,
    format_gates_summary,
)
from ralph_orchestrator.config import GateConfig, RalphConfig


class TestGateResult:
    """Tests for GateResult data class."""
    
    def test_passed_gate(self):
        """Passed gate has correct properties."""
        result = GateResult(
            name="pytest",
            passed=True,
            exit_code=0,
            duration_ms=1234,
            output="All tests passed",
        )
        
        assert result.passed is True
        assert result.exit_code == 0
        assert result.duration_ms == 1234
        assert result.skipped is False
    
    def test_failed_gate(self):
        """Failed gate has correct properties."""
        result = GateResult(
            name="mypy",
            passed=False,
            exit_code=1,
            duration_ms=567,
            output="Type errors found",
            error="mypy failed with errors",
            fatal=True,
        )
        
        assert result.passed is False
        assert result.exit_code == 1
        assert result.fatal is True
    
    def test_skipped_gate(self):
        """Skipped gate has correct properties."""
        result = GateResult(
            name="tsc",
            passed=True,
            exit_code=0,
            duration_ms=0,
            output="",
            skipped=True,
            skip_reason="Condition not met: tsconfig.json does not exist",
        )
        
        assert result.skipped is True
        assert result.skip_reason is not None
    
    def test_timed_out_gate(self):
        """Timed out gate has correct properties."""
        result = GateResult(
            name="slow_test",
            passed=False,
            exit_code=-1,
            duration_ms=60000,
            output="Partial output...",
            timed_out=True,
            error="Command timed out",
        )
        
        assert result.timed_out is True
        assert result.passed is False


class TestGatesResult:
    """Tests for GatesResult aggregate."""
    
    def test_all_gates_passed(self):
        """All gates passing gives passed=True."""
        result = GatesResult(
            gate_type="full",
            passed=True,
            results=[
                GateResult(name="pytest", passed=True, exit_code=0, duration_ms=1000, output=""),
                GateResult(name="mypy", passed=True, exit_code=0, duration_ms=500, output=""),
            ],
        )
        
        assert result.passed is True
        assert result.passed_count == 2
        assert result.failed_count == 0
        assert result.skipped_count == 0
    
    def test_one_gate_failed(self):
        """One gate failing gives passed=False."""
        result = GatesResult(
            gate_type="full",
            passed=False,
            results=[
                GateResult(name="pytest", passed=True, exit_code=0, duration_ms=1000, output=""),
                GateResult(name="mypy", passed=False, exit_code=1, duration_ms=500, output="Errors"),
            ],
            fatal_failure=GateResult(name="mypy", passed=False, exit_code=1, duration_ms=500, output="Errors"),
        )
        
        assert result.passed is False
        assert result.passed_count == 1
        assert result.failed_count == 1
    
    def test_skipped_gates_not_counted_as_failures(self):
        """Skipped gates are not counted as failures."""
        result = GatesResult(
            gate_type="build",
            passed=True,
            results=[
                GateResult(name="pytest", passed=True, exit_code=0, duration_ms=1000, output=""),
                GateResult(name="tsc", passed=True, exit_code=0, duration_ms=0, output="", skipped=True),
            ],
        )
        
        assert result.passed is True
        assert result.passed_count == 1
        assert result.skipped_count == 1
    
    def test_total_duration_calculated(self):
        """Total duration sums all gate durations."""
        result = GatesResult(
            gate_type="full",
            passed=True,
            results=[
                GateResult(name="g1", passed=True, exit_code=0, duration_ms=1000, output=""),
                GateResult(name="g2", passed=True, exit_code=0, duration_ms=2000, output=""),
                GateResult(name="g3", passed=True, exit_code=0, duration_ms=3000, output=""),
            ],
        )
        
        assert result.total_duration_ms == 6000


class TestGateFormatting:
    """Tests for gate output formatting."""
    
    def test_format_gate_failure(self):
        """Gate failure formatted with details."""
        result = GateResult(
            name="pytest",
            passed=False,
            exit_code=1,
            duration_ms=5000,
            output="FAILED test_main.py::test_function - AssertionError",
            error="Exit code 1",
        )
        
        formatted = format_gate_failure(result)
        
        assert "pytest" in formatted
        assert "exit code 1" in formatted.lower()
        assert "FAILED" in formatted
    
    def test_format_gate_failure_with_timeout(self):
        """Timed out gate shows timeout info."""
        result = GateResult(
            name="slow_test",
            passed=False,
            exit_code=-1,
            duration_ms=60000,
            output="",
            timed_out=True,
        )
        
        formatted = format_gate_failure(result)
        
        assert "slow_test" in formatted
        assert "timed out" in formatted.lower()
    
    def test_format_gates_summary(self):
        """Gates summary formatted correctly."""
        result = GatesResult(
            gate_type="full",
            passed=True,
            results=[
                GateResult(name="pytest", passed=True, exit_code=0, duration_ms=1234, output=""),
                GateResult(name="mypy", passed=True, exit_code=0, duration_ms=567, output=""),
                GateResult(name="tsc", passed=True, exit_code=0, duration_ms=0, output="", skipped=True, skip_reason="No tsconfig"),
            ],
        )
        
        summary = format_gates_summary(result)
        
        assert "full" in summary
        assert "2 passed" in summary
        assert "1 skipped" in summary
        assert "pytest" in summary
        assert "mypy" in summary
        assert "tsc" in summary


class TestGateConfig:
    """Tests for gate configuration handling."""
    
    def test_gate_config_defaults(self):
        """Gate config has expected defaults."""
        config = GateConfig(name="test", cmd="pytest")
        
        assert config.timeout_seconds == 300
        assert config.fatal is True
        assert config.when is None
    
    def test_gate_config_custom_values(self):
        """Gate config accepts custom values."""
        config = GateConfig(
            name="slow_test",
            cmd="pytest --slow",
            when="tests/slow/",
            timeout_seconds=600,
            fatal=False,
        )
        
        assert config.timeout_seconds == 600
        assert config.fatal is False
        assert config.when == "tests/slow/"
