"""
Integration tests for Ralph orchestrator.

These tests verify the complete workflow behavior using:
- Mock Claude CLI for deterministic agent responses
- Fixture repositories for realistic project structures
- Scenario-based testing for various execution paths

Test modules:
- test_task_loop.py: Task advancement, session artifacts, review phase
- test_invalid_signals.py: Signal rejection, retry behavior, timeouts
- test_tampering.py: Checksum verification, anti-gaming measures
- test_guardrails.py: Test-agent file restrictions
- test_gates.py: Gate ordering, fatal/non-fatal behavior
- test_autopilot.py: Full autopilot pipeline

Running integration tests:
    pytest -m integration
    pytest tests/integration/ -v

Mock Claude control:
    - Environment: MOCK_SCENARIO=invalid_token pytest ...
    - Directives: Add SIMULATE_* in task titles

These tests are designed to run without real Claude API calls.
The actual Ralph CLI modules must be implemented for full test execution.
Until then, tests verify infrastructure and contracts.
"""
