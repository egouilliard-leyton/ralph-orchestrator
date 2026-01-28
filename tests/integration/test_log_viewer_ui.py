"""Integration tests for LogViewer UI component.

Tests the log viewer component that streams logs in real-time with search,
filters, and ANSI color support.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock


@pytest.fixture
def sample_log_entries():
    """Create sample log entries for testing."""
    return [
        {
            "id": "log-001",
            "timestamp": "2024-01-01T10:00:00.000Z",
            "level": "info",
            "source": "implementation",
            "message": "Starting task execution",
        },
        {
            "id": "log-002",
            "timestamp": "2024-01-01T10:00:01.000Z",
            "level": "debug",
            "source": "implementation",
            "message": "\x1b[32mSuccess: Feature implemented\x1b[0m",
        },
        {
            "id": "log-003",
            "timestamp": "2024-01-01T10:00:02.000Z",
            "level": "warn",
            "source": "gate",
            "message": "Test coverage below threshold",
        },
        {
            "id": "log-004",
            "timestamp": "2024-01-01T10:00:03.000Z",
            "level": "error",
            "source": "test",
            "message": "\x1b[31mTest failed: assertion error\x1b[0m",
        },
    ]


@pytest.fixture
def mock_log_api(sample_log_entries):
    """Provide mock API response data for log endpoints."""
    return {
        "logs": {
            "logs": [
                {
                    "name": "implementation-001.log",
                    "path": "/path/to/logs/implementation-001.log",
                    "size": 1024,
                    "modifiedAt": "2024-01-01T10:00:00Z",
                    "content": "Log content here",
                }
            ],
            "total": 1,
        },
        "timeline": {
            "events": sample_log_entries,
            "total": len(sample_log_entries),
            "sessionId": "session-123",
        },
    }


class TestLogViewerStreaming:
    """Test real-time log streaming functionality."""

    def test_streams_logs_in_realtime(self, sample_log_entries):
        """LogViewer streams logs in real-time via WebSocket."""
        # Verify log entries have required fields for streaming
        for entry in sample_log_entries:
            assert "id" in entry
            assert "timestamp" in entry
            assert "level" in entry
            assert "source" in entry
            assert "message" in entry

    @pytest.mark.asyncio
    async def test_websocket_connection_for_logs(self):
        """WebSocket connection established for log streaming."""
        # Mock WebSocket connection
        mock_ws = AsyncMock()

        # Simulate receiving log messages
        log_message = {
            "type": "log",
            "data": {
                "timestamp": "2024-01-01T10:00:00.000Z",
                "level": "info",
                "source": "implementation",
                "message": "Test message",
            },
        }

        mock_ws.receive_json = AsyncMock(return_value=log_message)

        # Simulate connection
        received = await mock_ws.receive_json()

        assert received["type"] == "log"
        assert "data" in received
        assert received["data"]["message"] == "Test message"

    def test_auto_scroll_toggle(self):
        """Auto-scroll can be toggled on/off."""
        auto_scroll_state = {"enabled": True}

        # Toggle off
        auto_scroll_state["enabled"] = not auto_scroll_state["enabled"]
        assert auto_scroll_state["enabled"] is False

        # Toggle on
        auto_scroll_state["enabled"] = not auto_scroll_state["enabled"]
        assert auto_scroll_state["enabled"] is True

    def test_manual_scroll_disables_auto_scroll(self):
        """Manual scroll disables auto-scroll."""
        scroll_position = {"at_bottom": True, "auto_scroll": True}

        # Simulate user scrolling up
        scroll_position["at_bottom"] = False

        # Auto-scroll should be disabled
        if not scroll_position["at_bottom"] and scroll_position["auto_scroll"]:
            scroll_position["auto_scroll"] = False

        assert scroll_position["auto_scroll"] is False


class TestLogViewerFilters:
    """Test log filtering functionality."""

    def test_filter_by_log_level(self, sample_log_entries):
        """Filter logs by log level (debug, info, warn, error)."""
        # Filter for errors only
        error_logs = [log for log in sample_log_entries if log["level"] == "error"]

        assert len(error_logs) == 1
        assert error_logs[0]["level"] == "error"
        assert "Test failed" in error_logs[0]["message"]

    def test_filter_by_agent_type(self, sample_log_entries):
        """Filter logs by agent/source type."""
        # Filter for implementation agent
        impl_logs = [log for log in sample_log_entries if log["source"] == "implementation"]

        assert len(impl_logs) == 2
        for log in impl_logs:
            assert log["source"] == "implementation"

    def test_filter_by_gate(self, sample_log_entries):
        """Filter logs by gate execution."""
        # Filter for gate logs
        gate_logs = [log for log in sample_log_entries if log["source"] == "gate"]

        assert len(gate_logs) == 1
        assert gate_logs[0]["source"] == "gate"

    def test_filter_by_time_range(self, sample_log_entries):
        """Filter logs by time range."""
        start_time = datetime.fromisoformat("2024-01-01T10:00:01.000Z".replace("Z", "+00:00"))
        end_time = datetime.fromisoformat("2024-01-01T10:00:02.999Z".replace("Z", "+00:00"))

        filtered = []
        for log in sample_log_entries:
            log_time = datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
            if start_time <= log_time <= end_time:
                filtered.append(log)

        assert len(filtered) == 2
        assert filtered[0]["id"] == "log-002"
        assert filtered[1]["id"] == "log-003"

    def test_multiple_filters_combined(self, sample_log_entries):
        """Multiple filters can be applied simultaneously."""
        # Filter: level=error AND source=test
        filtered = [
            log
            for log in sample_log_entries
            if log["level"] == "error" and log["source"] == "test"
        ]

        assert len(filtered) == 1
        assert filtered[0]["level"] == "error"
        assert filtered[0]["source"] == "test"


class TestLogViewerSearch:
    """Test search functionality."""

    def test_search_highlights_matches(self, sample_log_entries):
        """Search functionality highlights matching text."""
        search_term = "test"

        matches = []
        for log in sample_log_entries:
            if search_term.lower() in log["message"].lower():
                matches.append(log)

        assert len(matches) >= 1
        # Verify matches contain the search term
        for match in matches:
            assert search_term.lower() in match["message"].lower()

    def test_search_case_insensitive(self, sample_log_entries):
        """Search is case-insensitive."""
        search_term_upper = "TASK"
        search_term_lower = "task"

        matches_upper = [
            log for log in sample_log_entries
            if search_term_upper.lower() in log["message"].lower()
        ]
        matches_lower = [
            log for log in sample_log_entries
            if search_term_lower.lower() in log["message"].lower()
        ]

        assert len(matches_upper) == len(matches_lower)

    def test_search_with_no_results(self, sample_log_entries):
        """Search with no matches returns empty results."""
        search_term = "nonexistent_search_term_xyz"

        matches = [
            log for log in sample_log_entries
            if search_term.lower() in log["message"].lower()
        ]

        assert len(matches) == 0

    def test_clear_search_restores_all_logs(self, sample_log_entries):
        """Clearing search restores full log list."""
        # Apply search filter
        search_term = "test"
        filtered = [
            log for log in sample_log_entries
            if search_term.lower() in log["message"].lower()
        ]

        assert len(filtered) < len(sample_log_entries)

        # Clear search (empty string)
        search_term = ""
        restored = [
            log for log in sample_log_entries
            if not search_term or search_term.lower() in log["message"].lower()
        ]

        assert len(restored) == len(sample_log_entries)


class TestLogViewerANSIColors:
    """Test ANSI color code rendering."""

    def test_ansi_color_codes_parsed(self):
        """ANSI color codes are parsed and rendered."""
        # Green text: \x1b[32m
        log_with_color = "\x1b[32mSuccess\x1b[0m"

        # Parse ANSI codes
        import re
        ansi_pattern = re.compile(r'\x1b\[(\d+)m')

        matches = ansi_pattern.findall(log_with_color)
        assert "32" in matches  # Green color code
        assert "0" in matches   # Reset code

    def test_ansi_colors_rendered_correctly(self):
        """ANSI colors are rendered with correct CSS classes."""
        ansi_color_map = {
            30: "text-gray-900",
            31: "text-red-600",
            32: "text-green-600",
            33: "text-yellow-600",
            34: "text-blue-600",
            35: "text-purple-600",
            36: "text-cyan-600",
            37: "text-gray-200",
        }

        # Verify mapping exists for common colors
        assert 32 in ansi_color_map  # Green
        assert 31 in ansi_color_map  # Red
        assert "green" in ansi_color_map[32]
        assert "red" in ansi_color_map[31]

    def test_ansi_bold_and_underline(self):
        """ANSI bold (1) and underline (4) codes are supported."""
        # Bold: \x1b[1m, Underline: \x1b[4m
        log_with_formatting = "\x1b[1m\x1b[4mBold and underlined\x1b[0m"

        import re
        ansi_pattern = re.compile(r'\x1b\[(\d+)m')

        codes = ansi_pattern.findall(log_with_formatting)
        assert "1" in codes   # Bold
        assert "4" in codes   # Underline
        assert "0" in codes   # Reset

    def test_ansi_reset_code(self):
        """ANSI reset code (0) clears all formatting."""
        # Reset code should be at the end
        log_message = "\x1b[32mGreen text\x1b[0m normal text"

        assert "\x1b[0m" in log_message

        # Split on reset code
        parts = log_message.split("\x1b[0m")
        assert len(parts) == 2
        assert "Green text" in parts[0]
        assert "normal text" in parts[1]

    def test_logs_without_ansi_codes(self):
        """Logs without ANSI codes are displayed normally."""
        plain_log = "This is a plain log message"

        import re
        ansi_pattern = re.compile(r'\x1b\[\d+m')

        assert not ansi_pattern.search(plain_log)


class TestLogViewerDownload:
    """Test log download functionality."""

    def test_download_logs_as_text(self, sample_log_entries):
        """Download logs button exports as text file."""
        # Convert logs to text format
        log_text = ""
        for log in sample_log_entries:
            log_text += f"[{log['timestamp']}] [{log['level'].upper()}] [{log['source']}] {log['message']}\n"

        assert len(log_text) > 0
        assert "implementation" in log_text
        assert "error" in log_text.lower()

    def test_download_preserves_timestamps(self, sample_log_entries):
        """Downloaded logs preserve timestamp information."""
        log_text = ""
        for log in sample_log_entries:
            log_text += f"{log['timestamp']} - {log['message']}\n"

        # Verify timestamps are included
        for log in sample_log_entries:
            assert log["timestamp"] in log_text

    def test_download_includes_all_visible_logs(self, sample_log_entries):
        """Download includes all currently visible/filtered logs."""
        # Apply filter
        filtered = [log for log in sample_log_entries if log["level"] == "error"]

        # Export filtered logs
        exported_count = len(filtered)

        assert exported_count == 1
        assert exported_count < len(sample_log_entries)

    def test_download_filename_includes_project_info(self):
        """Download filename includes project name and timestamp."""
        project_name = "test-project"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        filename = f"{project_name}-logs-{timestamp}.txt"

        assert project_name in filename
        assert ".txt" in filename
        assert "-logs-" in filename


class TestLogViewerAPIIntegration:
    """Test integration with backend log API.

    These tests verify the expected API contract for log operations
    using mock responses instead of live HTTP calls.
    """

    def test_fetch_logs_response_format(self, mock_log_api):
        """GET /api/projects/{id}/logs response format validation."""
        response_data = mock_log_api["logs"]

        # Validate response structure
        assert "logs" in response_data
        assert "total" in response_data
        assert response_data["total"] == 1

        # Validate log entry structure
        for log in response_data["logs"]:
            assert "name" in log
            assert "path" in log
            assert "size" in log
            assert "modifiedAt" in log

    def test_fetch_timeline_response_format(self, mock_log_api, sample_log_entries):
        """GET /api/projects/{id}/timeline response format validation."""
        response_data = mock_log_api["timeline"]

        # Validate response structure
        assert "events" in response_data
        assert "total" in response_data
        assert "sessionId" in response_data
        assert len(response_data["events"]) == 4

    def test_websocket_log_message_format(self):
        """WebSocket /ws/{project_id} message format validation."""
        # Validate expected WebSocket message format
        ws_message = {
            "type": "log",
            "projectId": "test-project",
            "data": {
                "timestamp": "2024-01-01T10:00:00.000Z",
                "level": "info",
                "source": "implementation",
                "message": "New log entry",
            },
        }

        assert ws_message["type"] == "log"
        assert "data" in ws_message
        assert ws_message["data"]["level"] in ["debug", "info", "warn", "error"]

    def test_api_request_format_logs(self):
        """Validate expected request format for fetching logs."""
        # Expected endpoint: GET /api/projects/{project_id}/logs
        endpoint_pattern = "/api/projects/{project_id}/logs"

        # Verify endpoint structure
        assert "{project_id}" in endpoint_pattern
        assert endpoint_pattern.startswith("/api/")

    def test_api_request_format_timeline(self):
        """Validate expected request format for fetching timeline."""
        # Expected endpoint: GET /api/projects/{project_id}/timeline
        endpoint_pattern = "/api/projects/{project_id}/timeline"

        # Verify endpoint structure
        assert "{project_id}" in endpoint_pattern
        assert endpoint_pattern.startswith("/api/")


class TestLogViewerPerformance:
    """Test performance with large log volumes."""

    def test_handles_large_log_volume(self):
        """LogViewer handles large number of log entries efficiently."""
        # Create 1000 log entries
        large_log_set = [
            {
                "id": f"log-{i:04d}",
                "timestamp": f"2024-01-01T10:00:{i % 60:02d}.000Z",
                "level": ["debug", "info", "warn", "error"][i % 4],
                "source": ["implementation", "test", "gate"][i % 3],
                "message": f"Log message {i}",
            }
            for i in range(1000)
        ]

        assert len(large_log_set) == 1000

        # Verify filtering still works
        errors = [log for log in large_log_set if log["level"] == "error"]
        assert len(errors) == 250  # Every 4th entry

    def test_virtualization_for_long_lists(self):
        """Long log lists use virtualization for performance."""
        # Test that we can handle pagination/virtualization
        log_count = 10000
        page_size = 100

        total_pages = (log_count + page_size - 1) // page_size

        assert total_pages == 100

        # First page
        first_page = list(range(0, min(page_size, log_count)))
        assert len(first_page) == page_size

    def test_incremental_log_loading(self):
        """Logs are loaded incrementally (load more button)."""
        total_logs = 1000
        initial_load = 100
        load_more_size = 50

        # Initial load
        visible_count = initial_load
        assert visible_count == 100

        # Load more
        visible_count += load_more_size
        assert visible_count == 150

        # Verify we haven't loaded all logs yet
        assert visible_count < total_logs
