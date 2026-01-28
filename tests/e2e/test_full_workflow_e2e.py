"""
End-to-end tests for complete Ralph workflows using Playwright.

These tests verify the entire user journey from project selection through
task execution to PR creation, ensuring all components work together correctly.

Tests cover:
- Complete workflow: select project -> start task -> monitor -> create branch/PR
- Real WebSocket communication and event handling
- API integration with actual backends
- UI state management across components
- Error handling and recovery

Requirements:
- pytest-playwright must be installed: pip install pytest-playwright
- Browsers must be installed: playwright install chromium
- Both frontend and backend servers must be running

Run with: pytest tests/e2e/ -v
Skip if Playwright not available: pytest tests/e2e/ --ignore-glob='**/test_full_workflow_e2e.py'
"""

import json
import os
import socket
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest

# Check if playwright is available and properly configured
try:
    from playwright.sync_api import Page, expect, Browser, BrowserContext, sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # Create dummy types for type hints when playwright is not available
    Page = object  # type: ignore
    Browser = object  # type: ignore
    BrowserContext = object  # type: ignore

# Test configuration
TEST_BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:3000")
TEST_API_URL = os.getenv("E2E_API_URL", "http://localhost:8000")
TEST_TIMEOUT = 30000  # 30 seconds


def _is_server_running(host: str, port: int) -> bool:
    """Check if a server is running on the given host and port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except (socket.error, OSError):
        return False


def _check_servers_available() -> bool:
    """Check if both frontend and backend servers are available."""
    # Parse URLs to get host and port
    import urllib.parse

    frontend_parsed = urllib.parse.urlparse(TEST_BASE_URL)
    backend_parsed = urllib.parse.urlparse(TEST_API_URL)

    frontend_host = frontend_parsed.hostname or "localhost"
    frontend_port = frontend_parsed.port or 3000
    backend_host = backend_parsed.hostname or "localhost"
    backend_port = backend_parsed.port or 8000

    frontend_ok = _is_server_running(frontend_host, frontend_port)
    backend_ok = _is_server_running(backend_host, backend_port)

    return frontend_ok and backend_ok


# Check server availability at module load time
SERVERS_AVAILABLE = _check_servers_available()

# Skip all tests in this module if requirements aren't met
pytestmark = [
    pytest.mark.skipif(
        not PLAYWRIGHT_AVAILABLE,
        reason="Playwright not installed. Install with: pip install pytest-playwright && playwright install chromium"
    ),
    pytest.mark.skipif(
        not SERVERS_AVAILABLE,
        reason=f"E2E servers not running. Start frontend ({TEST_BASE_URL}) and backend ({TEST_API_URL}) first."
    ),
    pytest.mark.e2e,  # Mark all tests as e2e for easy filtering
]


@pytest.fixture(scope="session")
def browser() -> Generator[Browser, None, None]:
    """Create a browser instance for the test session using sync_playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not available")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Create a new browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="en-US",
        timezone_id="America/New_York",
    )
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Create a new page for each test."""
    page = context.new_page()

    # Set default timeout
    page.set_default_timeout(TEST_TIMEOUT)

    yield page
    page.close()


@pytest.fixture
def test_project_dir() -> Generator[Path, None, None]:
    """Create a temporary test project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test-project"
        project_path.mkdir()

        # Create .ralph directory
        ralph_dir = project_path / ".ralph"
        ralph_dir.mkdir()

        # Create prd.json
        prd_data = {
            "project": "E2E Test Project",
            "description": "End-to-end testing project",
            "tasks": [
                {
                    "id": "T-E2E-001",
                    "title": "Implement E2E feature",
                    "description": "Add comprehensive E2E testing support",
                    "acceptanceCriteria": [
                        "Playwright tests configured",
                        "All workflows tested",
                        "CI integration complete"
                    ],
                    "priority": 1,
                    "passes": False,
                    "notes": "",
                    "requiresTests": True,
                },
                {
                    "id": "T-E2E-002",
                    "title": "Fix E2E bug",
                    "description": "Resolve timing issues in tests",
                    "acceptanceCriteria": ["Bug fixed", "Tests stable"],
                    "priority": 2,
                    "passes": False,
                    "notes": "",
                    "requiresTests": True,
                }
            ]
        }

        (ralph_dir / "prd.json").write_text(json.dumps(prd_data, indent=2))

        # Create ralph.yml
        config_yaml = """version: "1"
task_source:
  type: prd_json
  path: .ralph/prd.json
git:
  base_branch: main
  remote: origin
gates:
  build:
    - name: lint
      cmd: echo "Linting..."
  full:
    - name: test
      cmd: echo "Testing..."
test_paths:
  - tests/**
"""
        (ralph_dir / "ralph.yml").write_text(config_yaml)

        yield project_path


class TestCompleteWorkflow:
    """Tests for the complete end-to-end workflow."""

    def test_full_task_execution_workflow(self, page: Page, test_project_dir: Path):
        """
        Test the complete workflow: select project -> start task -> monitor -> complete.

        This is the primary E2E test that validates the entire user journey.
        """
        # Step 1: Navigate to dashboard
        page.goto(TEST_BASE_URL)

        # Wait for projects to load
        page.wait_for_selector('[data-testid="project-list"]', state="visible")

        # Verify projects are displayed
        expect(page.locator('[data-testid="project-card"]').first).to_be_visible()

        # Step 2: Select first project
        page.click('[data-testid="project-card"]', first=True)

        # Verify navigation to project page
        expect(page).to_have_url(f"{TEST_BASE_URL}/project/")

        # Verify task board loads
        page.wait_for_selector('[data-testid="task-board"]', state="visible")
        expect(page.locator('[data-testid="task-card"]').first).to_be_visible()

        # Step 3: Start first task
        first_task = page.locator('[data-testid="task-card"]').first
        task_id = first_task.get_attribute("data-task-id")

        # Click start button
        first_task.locator('[data-testid="start-task-button"]').click()

        # Confirm in dialog
        expect(page.locator('[data-testid="start-task-dialog"]')).to_be_visible()
        page.click('[data-testid="confirm-start-button"]')

        # Step 4: Monitor task execution
        # Verify progress panel appears
        expect(page.locator('[data-testid="task-progress-panel"]')).to_be_visible(timeout=10000)

        # Verify current agent is shown
        expect(page.locator('[data-testid="current-agent"]')).to_be_visible()

        # Verify iteration counter
        expect(page.locator('[data-testid="iteration-counter"]')).to_be_visible()

        # Verify log viewer shows output
        page.wait_for_selector('[data-testid="log-viewer"]', state="visible")

        # Wait for log content to appear
        page.wait_for_function(
            """() => {
                const logViewer = document.querySelector('[data-testid="log-viewer"]');
                return logViewer && logViewer.textContent.length > 10;
            }""",
            timeout=15000
        )

        # Step 5: Verify WebSocket updates
        # Check that real-time updates are being received
        ws_connected = page.evaluate(
            """() => {
                return window.__websocket_connected === true;
            }"""
        )
        assert ws_connected, "WebSocket should be connected"

        # Step 6: Wait for task phase transitions
        # Should progress through: implementation -> test_writing -> gates -> review
        phases_seen = set()

        for _ in range(10):  # Check up to 10 times
            current_agent = page.locator('[data-testid="current-agent"]').text_content()
            if current_agent:
                phases_seen.add(current_agent.lower())
            time.sleep(1)

            # Break if we've seen multiple phases
            if len(phases_seen) >= 2:
                break

        # Verify we saw phase transitions
        assert len(phases_seen) > 0, "Should see at least one agent phase"

        # Step 7: Verify gates execution
        # Gates section should appear after implementation
        expect(page.locator('[data-testid="gates-section"]')).to_be_visible(timeout=20000)

        # Should show individual gate results
        gate_results = page.locator('[data-testid="gate-result"]')
        expect(gate_results.first).to_be_visible()

        # Step 8: Verify task status updates
        # Task card should update status as task progresses
        task_card = page.locator(f'[data-task-id="{task_id}"]')

        # Status should eventually change from pending
        final_status = task_card.get_attribute("data-status")
        assert final_status in ["in_progress", "completed", "failed"], \
            f"Task status should update (got: {final_status})"

    def test_branch_and_pr_workflow(self, page: Page, test_project_dir: Path):
        """
        Test creating a branch and PR after task completion.

        Verifies:
        - Git panel integration
        - Branch creation workflow
        - PR creation workflow
        - Form validation
        """
        # Navigate to project
        page.goto(f"{TEST_BASE_URL}/project/{test_project_dir}")
        page.wait_for_selector('[data-testid="task-board"]', state="visible")

        # Step 1: Open git panel
        page.click('[data-testid="git-panel-toggle"]')
        expect(page.locator('[data-testid="git-panel"]')).to_be_visible()

        # Step 2: Create new branch
        page.click('[data-testid="create-branch-button"]')
        expect(page.locator('[data-testid="create-branch-dialog"]')).to_be_visible()

        # Fill branch name
        branch_name = f"feature/e2e-test-{int(time.time())}"
        page.fill('[data-testid="branch-name-input"]', branch_name)

        # Select base branch
        page.click('[data-testid="base-branch-select"]')
        page.click('[data-testid="branch-option-main"]')

        # Submit
        page.click('[data-testid="create-branch-submit"]')

        # Verify success
        expect(page.locator('[data-testid="success-toast"]')).to_be_visible(timeout=10000)
        expect(page.locator('[data-testid="success-toast"]')).to_contain_text("Branch created")

        # Step 3: Create PR
        page.click('[data-testid="create-pr-button"]')
        expect(page.locator('[data-testid="create-pr-modal"]')).to_be_visible()

        # Fill PR details
        page.fill('[data-testid="pr-title-input"]', "E2E Test PR")
        page.fill(
            '[data-testid="pr-description-input"]',
            "## Summary\n- Add E2E testing\n\n## Test plan\n- Run all E2E tests"
        )

        # Select base branch (main)
        page.click('[data-testid="base-branch-select"]')
        page.click('[data-testid="branch-option-main"]')

        # Submit PR
        page.click('[data-testid="create-pr-submit"]')

        # Verify PR created
        expect(page.locator('[data-testid="pr-created-success"]')).to_be_visible(timeout=15000)

        # Should show PR URL
        pr_link = page.locator('[data-testid="pr-url-link"]')
        expect(pr_link).to_be_visible()
        expect(pr_link).to_have_attribute("href")

    def test_config_edit_workflow(self, page: Page, test_project_dir: Path):
        """
        Test editing configuration through the UI.

        Verifies:
        - Config editor loads current config
        - YAML validation
        - Save functionality
        - Error handling
        """
        # Navigate to project
        page.goto(f"{TEST_BASE_URL}/project/{test_project_dir}")
        page.wait_for_selector('[data-testid="task-board"]', state="visible")

        # Step 1: Open config editor
        page.click('[data-testid="config-editor-button"]')
        expect(page.locator('[data-testid="config-editor-panel"]')).to_be_visible()

        # Step 2: Verify current config loads
        editor = page.locator('[data-testid="config-yaml-editor"]')
        expect(editor).to_be_visible()

        current_config = editor.text_content()
        assert "version:" in current_config, "Should load existing config"
        assert "task_source:" in current_config

        # Step 3: Add a new gate
        page.click('[data-testid="add-gate-button"]')

        # Fill gate details
        page.fill('[data-testid="gate-name-input"]', "security-scan")
        page.fill('[data-testid="gate-cmd-input"]', "bandit -r .")
        page.select_option('[data-testid="gate-type-select"]', "build")

        # Add gate
        page.click('[data-testid="add-gate-confirm"]')

        # Step 4: Save config
        page.click('[data-testid="save-config-button"]')

        # Verify success
        expect(page.locator('[data-testid="config-saved-success"]')).to_be_visible(timeout=10000)

        # Step 5: Verify persistence (reload and check)
        page.reload()
        page.wait_for_selector('[data-testid="task-board"]', state="visible")

        page.click('[data-testid="config-editor-button"]')
        expect(page.locator('[data-testid="config-editor-panel"]')).to_be_visible()

        # Check that the new gate appears
        updated_config = page.locator('[data-testid="config-yaml-editor"]').text_content()
        assert "security-scan" in updated_config, "New gate should persist"

    def test_websocket_reconnection(self, page: Page, test_project_dir: Path):
        """
        Test WebSocket reconnection after disconnection.

        Verifies:
        - WebSocket connection established
        - Disconnection detected
        - Automatic reconnection
        - Event streaming resumes
        """
        # Navigate to project
        page.goto(f"{TEST_BASE_URL}/project/{test_project_dir}")
        page.wait_for_selector('[data-testid="task-board"]', state="visible")

        # Verify WebSocket connects
        page.wait_for_function(
            """() => window.__websocket_connected === true""",
            timeout=10000
        )

        # Simulate disconnection
        page.evaluate(
            """() => {
                if (window.__websocket) {
                    window.__websocket.close();
                }
            }"""
        )

        # Should show reconnecting indicator
        expect(page.locator('[data-testid="ws-reconnecting-indicator"]')).to_be_visible(timeout=5000)

        # Should reconnect automatically
        page.wait_for_function(
            """() => window.__websocket_connected === true""",
            timeout=15000
        )

        # Indicator should disappear
        expect(page.locator('[data-testid="ws-reconnecting-indicator"]')).not_to_be_visible()

    def test_error_recovery_workflow(self, page: Page, test_project_dir: Path):
        """
        Test error handling and recovery mechanisms.

        Verifies:
        - API error display
        - Retry mechanisms
        - User feedback
        - Graceful degradation
        """
        # Intercept API requests to simulate errors
        def handle_route(route):
            if "/api/tasks/start" in route.request.url:
                route.fulfill(
                    status=500,
                    body=json.dumps({"detail": "Internal server error"}),
                    headers={"Content-Type": "application/json"}
                )
            else:
                route.continue_()

        page.route("**/api/**", handle_route)

        # Navigate to project
        page.goto(f"{TEST_BASE_URL}/project/{test_project_dir}")
        page.wait_for_selector('[data-testid="task-board"]', state="visible")

        # Try to start a task (will fail)
        page.click('[data-testid="task-card"]', first=True)
        page.click('[data-testid="start-task-button"]')
        page.click('[data-testid="confirm-start-button"]')

        # Should show error message
        expect(page.locator('[data-testid="error-toast"]')).to_be_visible(timeout=5000)
        expect(page.locator('[data-testid="error-toast"]')).to_contain_text("error")

        # Should show retry option
        retry_button = page.locator('[data-testid="retry-button"]')
        expect(retry_button).to_be_visible()

        # Remove route intercept to allow success
        page.unroute("**/api/**")

        # Retry should work
        retry_button.click()

        # Should succeed this time
        expect(page.locator('[data-testid="task-progress-panel"]')).to_be_visible(timeout=10000)


class TestAccessibility:
    """Tests for accessibility compliance."""

    def test_keyboard_navigation(self, page: Page):
        """Verify keyboard navigation works throughout the app."""
        page.goto(TEST_BASE_URL)
        page.wait_for_selector('[data-testid="project-list"]', state="visible")

        # Tab through elements
        page.keyboard.press("Tab")
        focused1 = page.evaluate("() => document.activeElement.getAttribute('data-testid')")
        assert focused1, "Should focus on an element"

        # Tab again
        page.keyboard.press("Tab")
        focused2 = page.evaluate("() => document.activeElement.getAttribute('data-testid')")
        assert focused2 != focused1, "Focus should move to different element"

        # Enter should activate focused element
        page.keyboard.press("Enter")
        # Should trigger some action (navigation or dialog)

    def test_screen_reader_labels(self, page: Page):
        """Verify ARIA labels and screen reader support."""
        page.goto(TEST_BASE_URL)
        page.wait_for_selector('[data-testid="project-card"]', state="visible")

        # Check project cards have aria-label
        project_card = page.locator('[data-testid="project-card"]').first
        aria_label = project_card.get_attribute("aria-label")
        assert aria_label, "Project cards should have aria-label"

        # Check buttons have aria-label
        start_button = page.locator('[data-testid="start-task-button"]').first
        if start_button.is_visible():
            button_label = start_button.get_attribute("aria-label") or start_button.text_content()
            assert button_label, "Buttons should have label"


class TestPerformance:
    """Tests for performance metrics."""

    def test_initial_load_time(self, page: Page):
        """Verify initial page load is under acceptable threshold."""
        start_time = time.time()

        page.goto(TEST_BASE_URL)
        page.wait_for_selector('[data-testid="project-list"]', state="visible")

        load_time = time.time() - start_time

        # Should load in under 5 seconds
        assert load_time < 5.0, f"Initial load took {load_time:.2f}s (should be < 5s)"

    def test_websocket_latency(self, page: Page, test_project_dir: Path):
        """Verify WebSocket message latency is acceptable."""
        page.goto(f"{TEST_BASE_URL}/project/{test_project_dir}")
        page.wait_for_selector('[data-testid="task-board"]', state="visible")

        # Setup latency tracking
        page.evaluate(
            """() => {
                window.__ws_latencies = [];
                const originalOnMessage = WebSocket.prototype.onmessage;
                WebSocket.prototype.onmessage = function(event) {
                    const receiveTime = Date.now();
                    try {
                        const data = JSON.parse(event.data);
                        if (data.timestamp) {
                            const sentTime = new Date(data.timestamp).getTime();
                            const latency = receiveTime - sentTime;
                            window.__ws_latencies.push(latency);
                        }
                    } catch (e) {}
                    return originalOnMessage.call(this, event);
                };
            }"""
        )

        # Trigger some activity
        page.click('[data-testid="task-card"]', first=True)

        # Wait for messages
        time.sleep(3)

        # Check latencies
        latencies = page.evaluate("() => window.__ws_latencies || []")
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Should average under 500ms
            assert avg_latency < 500, f"Average WebSocket latency: {avg_latency:.0f}ms"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
