# Ralph Testing Quick Reference

Quick reference for testing the Ralph orchestrator.

**Test Status:** 180+ tests implemented (unit + integration harness).

## Running Tests

```bash
# All tests
pytest

# Unit tests only (fast, no mocks needed)
pytest -m unit

# Integration tests (uses mock Claude + fixtures)
pytest -m integration

# Specific test file
pytest tests/unit/test_mock_claude.py

# With coverage
pytest --cov=ralph --cov-report=html

# Verbose output
pytest -v --tb=long
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── pytest.ini               # Configuration
├── mock_claude/             # Mock Claude CLI
│   └── mock_claude.py       # Main mock implementation
├── fixtures/                # Fixture repositories
│   ├── python_min/          # Minimal Python project
│   ├── node_min/            # Minimal Node.js project
│   ├── fullstack_min/       # Backend + Frontend
│   └── autopilot_min/       # Autopilot testing
├── unit/                    # Unit tests
│   ├── test_mock_claude.py  # Mock Claude behavior
│   └── test_fixtures.py     # Fixture structure validation
└── integration/             # Integration tests
    ├── test_task_loop.py    # Task advancement workflow
    ├── test_invalid_signals.py # Signal rejection/retry
    ├── test_tampering.py    # Checksum verification
    ├── test_guardrails.py   # Test-agent file restrictions
    ├── test_gates.py        # Gate ordering/behavior
    ├── test_services.py     # Service lifecycle
    ├── test_fix_loops.py    # Runtime fix iterations
    ├── test_autopilot.py    # Autopilot pipeline
    └── test_mock_integration.py # Mock Claude integration
```

## Mock Claude

The mock Claude CLI simulates real Claude responses for testing.

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `RALPH_CLAUDE_CMD` | Override Claude command | `python tests/mock_claude/mock_claude.py` |
| `MOCK_SCENARIO` | Predefined response scenario | `default`, `invalid_token`, `no_signal` |
| `MOCK_RESPONSE_FILE` | Custom response file | `/path/to/response.txt` |
| `MOCK_DELAY` | Artificial delay (seconds) | `5.0` |

### Prompt Directives

Add these to prompts to trigger specific behaviors:

| Directive | Behavior |
|-----------|----------|
| `SIMULATE_INVALID_TOKEN` | Returns response with wrong token |
| `SIMULATE_NO_SIGNAL` | Returns response without completion signal |
| `SIMULATE_TIMEOUT` | Simulates timeout (long delay) |
| `SIMULATE_REVIEW_REJECT` | Returns review rejection |
| `SIMULATE_GUARDRAIL_VIOLATION` | Simulates test agent modifying source files |

### Example Usage

```python
# In test file
def test_invalid_token_rejected(fixture_python_min):
    os.chdir(fixture_python_min)
    
    # Modify task to trigger invalid token
    prd_file = fixture_python_min / ".ralph/prd.json"
    content = prd_file.read_text()
    content = content.replace(
        '"title": "Add multiply"',
        '"title": "Add multiply SIMULATE_INVALID_TOKEN"'
    )
    prd_file.write_text(content)
    
    # Run ralph - should detect invalid token
    result = run_command(["run", "--prd-json", ".ralph/prd.json"])
```

## Fixture Repositories

### python_min
- Minimal Python project with `pyproject.toml`
- 2 tasks: add function, add tests
- Gates: syntax check, pytest

### node_min
- Minimal Node.js project with `package.json`
- 2 tasks: add function, add tests
- Gates: syntax check, npm test

### fullstack_min
- Python backend + TypeScript frontend
- 3 tasks across backend and frontend
- Services configuration for health checks

### autopilot_min
- Includes `reports/` directory with sample report
- Autopilot configuration enabled
- For testing analysis → tasks → execution pipeline

## Common Fixtures

```python
# Available in tests via conftest.py

@pytest.fixture
def fixture_python_min(tmp_path) -> Path:
    """Python fixture with git init."""

@pytest.fixture  
def fixture_node_min(tmp_path) -> Path:
    """Node.js fixture with git init."""

@pytest.fixture
def fixture_fullstack_min(tmp_path) -> Path:
    """Fullstack fixture with git init."""

@pytest.fixture
def fixture_autopilot_min(tmp_path) -> Path:
    """Autopilot fixture with git init."""

@pytest.fixture
def sample_prd_json() -> dict:
    """Sample prd.json structure."""

@pytest.fixture
def sample_session_token() -> str:
    """Sample session token."""
```

## Writing Tests

### Unit Tests

```python
@pytest.mark.unit
class TestTokenGeneration:
    def test_token_format(self):
        token = TokenGenerator.generate()
        assert token.startswith("ralph-")
```

### Integration Tests

```python
@pytest.mark.integration
class TestTaskLoop:
    def test_task_advances(self, fixture_python_min):
        os.chdir(fixture_python_min)
        result = run_command(["run", "--prd-json", ".ralph/prd.json"])
        # Verify task completed
```

## Test Markers

| Marker | Description | Speed |
|--------|-------------|-------|
| `@pytest.mark.unit` | No external deps | < 1s |
| `@pytest.mark.integration` | Mock Claude + fixtures | < 30s |
| `@pytest.mark.slow` | Longer running tests | > 30s |
| `@pytest.mark.autopilot` | Autopilot-specific | < 60s |

## CI/CD

Tests run automatically on:
- Push to `main`
- Pull requests

Unit tests run first (fast feedback), then integration tests.

## Troubleshooting

### Mock Claude not found
```bash
export RALPH_CLAUDE_CMD="python $(pwd)/tests/mock_claude/mock_claude.py"
```

### Fixture not copying
```python
# Ensure fixture exists
assert Path("tests/fixtures/python_min").exists()
```

### Git errors in fixtures
```bash
# Fixtures auto-initialize git, but if issues:
cd fixture_path && git init && git add . && git commit -m "Initial"
```
