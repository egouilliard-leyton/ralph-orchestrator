"""Unit tests for WebSocket manager.

Tests cover:
- WebSocketManager connection management
- Message sending and error handling
- Command handler registration and execution
- Heartbeat health monitoring
- Event subscription filtering
- Connection lifecycle and cleanup
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketState

from server.websocket import (
    ClientCommand,
    ConnectionInfo,
    ServerMessageType,
    WebSocketManager,
    create_websocket_manager,
    HEARTBEAT_INTERVAL,
    CONNECTION_TIMEOUT,
)
from server.events import (
    EventEmitter,
    EventType,
    TaskStartedEvent,
    TaskCompletedEvent,
)


# =============================================================================
# Mock WebSocket
# =============================================================================


class MockWebSocket:
    """Mock WebSocket for unit testing."""

    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.client_state = WebSocketState.CONNECTING

    async def accept(self):
        self.accepted = True
        self.client_state = WebSocketState.CONNECTED

    async def close(self):
        self.closed = True
        self.client_state = WebSocketState.DISCONNECTED

    async def send_json(self, data):
        if self.client_state != WebSocketState.CONNECTED:
            raise RuntimeError("WebSocket not connected")
        self.sent_messages.append(data)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def event_emitter():
    """Create an EventEmitter for testing."""
    return EventEmitter()


@pytest.fixture
def ws_manager():
    """Create a WebSocketManager without emitter."""
    return WebSocketManager()


@pytest.fixture
def ws_manager_with_emitter(event_emitter):
    """Create a WebSocketManager with emitter integration."""
    return WebSocketManager(emitter=event_emitter)


# =============================================================================
# ConnectionInfo tests
# =============================================================================


class TestConnectionInfo:
    """Tests for ConnectionInfo dataclass."""

    def test_is_healthy_returns_true_for_recent_heartbeat(self):
        """is_healthy returns True when heartbeat is recent."""
        websocket = MagicMock()
        connection = ConnectionInfo(
            connection_id="test-1",
            websocket=websocket,
            project_id="project-a",
            last_heartbeat=time.time(),
        )

        assert connection.is_healthy() is True

    def test_is_healthy_returns_false_after_timeout(self):
        """is_healthy returns False when heartbeat exceeds timeout."""
        websocket = MagicMock()
        connection = ConnectionInfo(
            connection_id="test-1",
            websocket=websocket,
            project_id="project-a",
            last_heartbeat=time.time() - CONNECTION_TIMEOUT - 10,
        )

        assert connection.is_healthy() is False

    def test_update_heartbeat_updates_timestamp(self):
        """update_heartbeat updates last_heartbeat timestamp."""
        websocket = MagicMock()
        old_time = time.time() - 100
        connection = ConnectionInfo(
            connection_id="test-1",
            websocket=websocket,
            project_id="project-a",
            last_heartbeat=old_time,
        )

        connection.update_heartbeat()

        assert connection.last_heartbeat > old_time
        assert connection.is_healthy() is True

    def test_default_subscribed_events_includes_all(self):
        """Default subscribed_events includes all event types."""
        websocket = MagicMock()
        connection = ConnectionInfo(
            connection_id="test-1",
            websocket=websocket,
            project_id="project-a",
        )

        assert len(connection.subscribed_events) == len(EventType)
        assert EventType.TASK_STARTED in connection.subscribed_events


# =============================================================================
# WebSocketManager initialization tests
# =============================================================================


class TestWebSocketManagerInitialization:
    """Tests for WebSocketManager initialization."""

    def test_init_without_emitter(self):
        """Manager initializes without emitter."""
        manager = WebSocketManager()

        assert manager._emitter is None
        assert manager._connections == {}
        assert manager._all_connections == {}
        assert manager._running is False
        assert manager._heartbeat_task is None

    def test_init_with_emitter(self, event_emitter):
        """Manager initializes with emitter and sets up integration."""
        manager = WebSocketManager(emitter=event_emitter)

        assert manager._emitter is event_emitter
        # Check that emitter has handlers registered
        assert event_emitter.handler_count() > 0

    def test_default_command_handlers_registered(self):
        """Default command handlers are registered on init."""
        manager = WebSocketManager()

        assert ClientCommand.PING in manager._command_handlers
        assert ClientCommand.SUBSCRIBE in manager._command_handlers
        assert ClientCommand.UNSUBSCRIBE in manager._command_handlers


# =============================================================================
# Connection management tests
# =============================================================================


class TestConnectionManagement:
    """Tests for connection tracking and management."""

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, ws_manager):
        """connect accepts the WebSocket."""
        websocket = MockWebSocket()

        connection = await ws_manager.connect(websocket, "project-a")

        assert websocket.accepted is True
        assert connection.websocket is websocket

    @pytest.mark.asyncio
    async def test_connect_generates_unique_connection_id(self, ws_manager):
        """connect generates unique connection IDs."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        conn1 = await ws_manager.connect(ws1, "project-a")
        conn2 = await ws_manager.connect(ws2, "project-a")

        assert conn1.connection_id != conn2.connection_id

    @pytest.mark.asyncio
    async def test_connect_tracks_connection_in_project(self, ws_manager):
        """connect tracks connection in project-specific dict."""
        websocket = MockWebSocket()

        await ws_manager.connect(websocket, "project-a")

        assert "project-a" in ws_manager._connections
        assert len(ws_manager._connections["project-a"]) == 1

    @pytest.mark.asyncio
    async def test_connect_tracks_connection_globally(self, ws_manager):
        """connect tracks connection in global dict."""
        websocket = MockWebSocket()

        connection = await ws_manager.connect(websocket, "project-a")

        assert connection.connection_id in ws_manager._all_connections

    @pytest.mark.asyncio
    async def test_connect_sends_connected_message(self, ws_manager):
        """connect sends a CONNECTED message to client."""
        websocket = MockWebSocket()

        connection = await ws_manager.connect(websocket, "project-a")

        assert len(websocket.sent_messages) == 1
        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.CONNECTED.value
        assert msg["connection_id"] == connection.connection_id
        assert msg["project_id"] == "project-a"

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_project(self, ws_manager):
        """disconnect removes connection from project dict."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")

        await ws_manager.disconnect(connection)

        assert "project-a" not in ws_manager._connections

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_global(self, ws_manager):
        """disconnect removes connection from global dict."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")

        await ws_manager.disconnect(connection)

        assert connection.connection_id not in ws_manager._all_connections

    @pytest.mark.asyncio
    async def test_disconnect_preserves_other_connections(self, ws_manager):
        """disconnect only removes the specified connection."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        conn1 = await ws_manager.connect(ws1, "project-a")
        conn2 = await ws_manager.connect(ws2, "project-a")

        await ws_manager.disconnect(conn1)

        assert ws_manager.get_connection_count("project-a") == 1
        assert conn2.connection_id in ws_manager._all_connections


# =============================================================================
# Broadcasting tests
# =============================================================================


class TestBroadcasting:
    """Tests for message broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_to_project_sends_to_all_project_clients(self, ws_manager):
        """broadcast_to_project sends to all clients in that project."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-a")
        await ws_manager.connect(ws3, "project-b")

        # Clear connection messages
        ws1.sent_messages.clear()
        ws2.sent_messages.clear()
        ws3.sent_messages.clear()

        sent_count = await ws_manager.broadcast_to_project(
            "project-a",
            {"test": "data"},
        )

        assert sent_count == 2
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert len(ws3.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_project_returns_zero_for_no_connections(self, ws_manager):
        """broadcast_to_project returns 0 when no connections exist."""
        sent_count = await ws_manager.broadcast_to_project(
            "nonexistent-project",
            {"test": "data"},
        )

        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_event_serializes_event_correctly(self, ws_manager):
        """broadcast_event correctly serializes Event objects."""
        websocket = MockWebSocket()
        await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        event = TaskStartedEvent(
            project_id="project-a",
            task_id="T-001",
            task_title="Test task",
            total_tasks=3,
            task_index=1,
        )

        sent_count = await ws_manager.broadcast_event(event)

        assert sent_count == 1
        assert len(websocket.sent_messages) == 1
        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.EVENT.value
        assert msg["event_type"] == EventType.TASK_STARTED.value
        assert msg["task_id"] == "T-001"
        assert msg["task_title"] == "Test task"

    @pytest.mark.asyncio
    async def test_broadcast_to_all_sends_to_every_connection(self, ws_manager):
        """broadcast_to_all sends to all connections regardless of project."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-b")
        await ws_manager.connect(ws3, "project-c")

        ws1.sent_messages.clear()
        ws2.sent_messages.clear()
        ws3.sent_messages.clear()

        sent_count = await ws_manager.broadcast_to_all({"global": "message"})

        assert sent_count == 3
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert len(ws3.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_broadcast_respects_event_type_filter(self, ws_manager):
        """broadcast_to_project respects subscribed_events filter."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")

        # Subscribe only to TASK_STARTED
        connection.subscribed_events = {EventType.TASK_STARTED}
        websocket.sent_messages.clear()

        # Broadcast TASK_STARTED - should be received
        await ws_manager.broadcast_to_project(
            "project-a",
            {"event": "task_started"},
            event_type=EventType.TASK_STARTED,
        )

        # Broadcast TASK_COMPLETED - should be filtered out
        await ws_manager.broadcast_to_project(
            "project-a",
            {"event": "task_completed"},
            event_type=EventType.TASK_COMPLETED,
        )

        assert len(websocket.sent_messages) == 1
        assert websocket.sent_messages[0]["event"] == "task_started"


# =============================================================================
# Message handling tests
# =============================================================================


class TestMessageHandling:
    """Tests for client message handling."""

    @pytest.mark.asyncio
    async def test_handle_message_executes_command_handler(self, ws_manager):
        """handle_message executes the registered command handler."""
        handler_called = False
        handler_args = {}

        def test_handler(project_id, payload, connection):
            nonlocal handler_called, handler_args
            handler_called = True
            handler_args = {"project_id": project_id, "payload": payload}
            return {"result": "success"}

        ws_manager.register_command_handler(ClientCommand.START_TASK, test_handler)

        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.START_TASK.value, "payload": {"task_id": "T-001"}},
        )

        assert handler_called is True
        assert handler_args["project_id"] == "project-a"
        assert handler_args["payload"]["task_id"] == "T-001"

    @pytest.mark.asyncio
    async def test_handle_message_sends_success_response(self, ws_manager):
        """handle_message sends COMMAND_RESPONSE on success."""
        def test_handler(project_id, payload, connection):
            return {"data": "test"}

        ws_manager.register_command_handler(ClientCommand.START_TASK, test_handler)

        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.START_TASK.value, "payload": {}},
        )

        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.COMMAND_RESPONSE.value
        assert msg["success"] is True
        assert msg["result"]["data"] == "test"

    @pytest.mark.asyncio
    async def test_handle_message_sends_error_for_missing_command(self, ws_manager):
        """handle_message sends ERROR when command field is missing."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(connection, {"payload": {}})

        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.ERROR.value
        assert "Missing 'command' field" in msg["error"]

    @pytest.mark.asyncio
    async def test_handle_message_sends_error_for_unknown_command(self, ws_manager):
        """handle_message sends ERROR for unknown command."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {"command": "invalid_command", "payload": {}},
        )

        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.ERROR.value
        assert "Unknown command" in msg["error"]

    @pytest.mark.asyncio
    async def test_handle_message_sends_error_for_unregistered_command(self, ws_manager):
        """handle_message sends ERROR when command has no handler."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        # CREATE_BRANCH is a valid command but has no default handler
        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.CREATE_BRANCH.value, "payload": {}},
        )

        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.ERROR.value
        assert "No handler" in msg["error"]

    @pytest.mark.asyncio
    async def test_handle_message_sends_error_when_handler_raises(self, ws_manager):
        """handle_message sends COMMAND_ERROR when handler raises exception."""
        def failing_handler(project_id, payload, connection):
            raise ValueError("Test error")

        ws_manager.register_command_handler(ClientCommand.START_TASK, failing_handler)

        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.START_TASK.value, "payload": {}},
        )

        msg = websocket.sent_messages[0]
        assert msg["type"] == ServerMessageType.COMMAND_ERROR.value
        assert msg["success"] is False
        assert "Test error" in msg["error"]

    @pytest.mark.asyncio
    async def test_handle_message_supports_async_handlers(self, ws_manager):
        """handle_message correctly awaits async handlers."""
        async def async_handler(project_id, payload, connection):
            await asyncio.sleep(0.01)
            return {"async": "result"}

        ws_manager.register_command_handler(ClientCommand.START_TASK, async_handler)

        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.START_TASK.value, "payload": {}},
        )

        msg = websocket.sent_messages[0]
        assert msg["success"] is True
        assert msg["result"]["async"] == "result"


# =============================================================================
# Default command handler tests
# =============================================================================


class TestDefaultCommandHandlers:
    """Tests for built-in command handlers."""

    @pytest.mark.asyncio
    async def test_ping_handler_updates_heartbeat(self, ws_manager):
        """PING handler updates the connection's heartbeat timestamp."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        old_heartbeat = connection.last_heartbeat
        websocket.sent_messages.clear()

        await asyncio.sleep(0.01)

        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.PING.value, "payload": {}},
        )

        assert connection.last_heartbeat > old_heartbeat

    @pytest.mark.asyncio
    async def test_ping_handler_returns_timestamp(self, ws_manager):
        """PING handler returns current timestamp."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {"command": ClientCommand.PING.value, "payload": {}},
        )

        msg = websocket.sent_messages[0]
        assert msg["success"] is True
        assert "timestamp" in msg["result"]

    @pytest.mark.asyncio
    async def test_subscribe_handler_sets_event_types(self, ws_manager):
        """SUBSCRIBE handler sets subscribed_events."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {
                "command": ClientCommand.SUBSCRIBE.value,
                "payload": {"event_types": ["task_started", "gate_running"]},
            },
        )

        assert connection.subscribed_events == {
            EventType.TASK_STARTED,
            EventType.GATE_RUNNING,
        }

    @pytest.mark.asyncio
    async def test_subscribe_handler_with_empty_list_subscribes_to_all(self, ws_manager):
        """SUBSCRIBE handler with empty event_types subscribes to all events."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        connection.subscribed_events = {EventType.TASK_STARTED}  # Start with subset
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {
                "command": ClientCommand.SUBSCRIBE.value,
                "payload": {"event_types": []},
            },
        )

        assert len(connection.subscribed_events) == len(EventType)

    @pytest.mark.asyncio
    async def test_unsubscribe_handler_removes_event_types(self, ws_manager):
        """UNSUBSCRIBE handler removes event types from subscription."""
        websocket = MockWebSocket()
        connection = await ws_manager.connect(websocket, "project-a")
        connection.subscribed_events = {
            EventType.TASK_STARTED,
            EventType.TASK_COMPLETED,
            EventType.GATE_RUNNING,
        }
        websocket.sent_messages.clear()

        await ws_manager.handle_message(
            connection,
            {
                "command": ClientCommand.UNSUBSCRIBE.value,
                "payload": {"event_types": ["task_completed"]},
            },
        )

        assert EventType.TASK_COMPLETED not in connection.subscribed_events
        assert EventType.TASK_STARTED in connection.subscribed_events
        assert EventType.GATE_RUNNING in connection.subscribed_events


# =============================================================================
# EventEmitter integration tests
# =============================================================================


class TestEmitterIntegration:
    """Tests for EventEmitter integration."""

    @pytest.mark.asyncio
    async def test_emitter_events_broadcast_to_connections(
        self, ws_manager_with_emitter, event_emitter
    ):
        """Events emitted through EventEmitter are broadcast to WebSockets."""
        websocket = MockWebSocket()
        await ws_manager_with_emitter.connect(websocket, "project-a")
        websocket.sent_messages.clear()

        event = TaskStartedEvent(
            project_id="project-a",
            task_id="T-001",
            task_title="Test",
        )

        event_emitter.emit(event)
        await asyncio.sleep(0.1)  # Allow async broadcast to complete

        # Find event messages (filter out any other messages)
        event_msgs = [
            m for m in websocket.sent_messages
            if m.get("type") == ServerMessageType.EVENT.value
        ]

        assert len(event_msgs) == 1
        assert event_msgs[0]["task_id"] == "T-001"

    @pytest.mark.asyncio
    async def test_emitter_integration_respects_project_isolation(
        self, ws_manager_with_emitter, event_emitter
    ):
        """Emitter integration only sends events to correct project."""
        ws_a = MockWebSocket()
        ws_b = MockWebSocket()

        await ws_manager_with_emitter.connect(ws_a, "project-a")
        await ws_manager_with_emitter.connect(ws_b, "project-b")
        ws_a.sent_messages.clear()
        ws_b.sent_messages.clear()

        event = TaskStartedEvent(project_id="project-a", task_id="T-001")
        event_emitter.emit(event)
        await asyncio.sleep(0.1)

        # Only project-a should receive the event
        event_msgs_a = [m for m in ws_a.sent_messages if m.get("event_type")]
        event_msgs_b = [m for m in ws_b.sent_messages if m.get("event_type")]

        assert len(event_msgs_a) >= 1
        assert len(event_msgs_b) == 0


# =============================================================================
# Manager lifecycle tests
# =============================================================================


class TestManagerLifecycle:
    """Tests for WebSocketManager lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, ws_manager):
        """start() sets the _running flag."""
        await ws_manager.start()

        assert ws_manager._running is True

        await ws_manager.stop()

    @pytest.mark.asyncio
    async def test_start_creates_heartbeat_task(self, ws_manager):
        """start() creates the heartbeat monitoring task."""
        await ws_manager.start()

        assert ws_manager._heartbeat_task is not None
        assert not ws_manager._heartbeat_task.done()

        await ws_manager.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, ws_manager):
        """start() can be called multiple times safely."""
        await ws_manager.start()
        first_task = ws_manager._heartbeat_task

        await ws_manager.start()
        second_task = ws_manager._heartbeat_task

        assert first_task is second_task

        await ws_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, ws_manager):
        """stop() clears the _running flag."""
        await ws_manager.start()
        await ws_manager.stop()

        assert ws_manager._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_heartbeat_task(self, ws_manager):
        """stop() cancels the heartbeat task."""
        await ws_manager.start()
        await ws_manager.stop()

        assert ws_manager._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_stop_closes_all_websockets(self, ws_manager):
        """stop() closes all WebSocket connections."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-b")

        await ws_manager.stop()

        # WebSockets should be closed
        assert ws1.closed is True
        assert ws2.closed is True


# =============================================================================
# Status method tests
# =============================================================================


class TestStatusMethods:
    """Tests for manager status query methods."""

    @pytest.mark.asyncio
    async def test_get_connection_count_all(self, ws_manager):
        """get_connection_count() returns total connections."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-b")

        assert ws_manager.get_connection_count() == 2

    @pytest.mark.asyncio
    async def test_get_connection_count_by_project(self, ws_manager):
        """get_connection_count(project_id) returns project-specific count."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-a")
        await ws_manager.connect(ws3, "project-b")

        assert ws_manager.get_connection_count("project-a") == 2
        assert ws_manager.get_connection_count("project-b") == 1

    @pytest.mark.asyncio
    async def test_get_connections_for_project(self, ws_manager):
        """get_connections_for_project returns list of connections."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        conn1 = await ws_manager.connect(ws1, "project-a")
        conn2 = await ws_manager.connect(ws2, "project-a")

        connections = ws_manager.get_connections_for_project("project-a")

        assert len(connections) == 2
        assert conn1 in connections
        assert conn2 in connections

    @pytest.mark.asyncio
    async def test_get_all_connections(self, ws_manager):
        """get_all_connections returns all connections."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-b")

        connections = ws_manager.get_all_connections()

        assert len(connections) == 2

    @pytest.mark.asyncio
    async def test_get_connected_projects(self, ws_manager):
        """get_connected_projects returns list of project IDs."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await ws_manager.connect(ws1, "project-a")
        await ws_manager.connect(ws2, "project-b")

        projects = ws_manager.get_connected_projects()

        assert set(projects) == {"project-a", "project-b"}


# =============================================================================
# Factory function tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_websocket_manager factory."""

    def test_create_websocket_manager_without_args(self):
        """Factory creates manager with defaults."""
        manager = create_websocket_manager()

        assert manager is not None
        assert manager._emitter is None

    def test_create_websocket_manager_with_emitter(self, event_emitter):
        """Factory creates manager with emitter."""
        manager = create_websocket_manager(emitter=event_emitter)

        assert manager._emitter is event_emitter

    def test_create_websocket_manager_with_command_handlers(self):
        """Factory registers custom command handlers."""
        def custom_handler(project_id, payload, connection):
            return {"custom": True}

        handlers = {
            ClientCommand.START_TASK: custom_handler,
            ClientCommand.CANCEL_EXECUTION: custom_handler,
        }

        manager = create_websocket_manager(command_handlers=handlers)

        assert ClientCommand.START_TASK in manager._command_handlers
        assert ClientCommand.CANCEL_EXECUTION in manager._command_handlers
        assert manager._command_handlers[ClientCommand.START_TASK] is custom_handler


# =============================================================================
# Command handler registration tests
# =============================================================================


class TestCommandHandlerRegistration:
    """Tests for command handler registration."""

    def test_register_command_handler(self, ws_manager):
        """register_command_handler adds handler to registry."""
        def test_handler(project_id, payload, connection):
            return {}

        ws_manager.register_command_handler(ClientCommand.START_TASK, test_handler)

        assert ClientCommand.START_TASK in ws_manager._command_handlers
        assert ws_manager._command_handlers[ClientCommand.START_TASK] is test_handler

    def test_register_command_handler_overwrites_existing(self, ws_manager):
        """register_command_handler overwrites existing handler."""
        def handler1(project_id, payload, connection):
            return {"version": 1}

        def handler2(project_id, payload, connection):
            return {"version": 2}

        ws_manager.register_command_handler(ClientCommand.START_TASK, handler1)
        ws_manager.register_command_handler(ClientCommand.START_TASK, handler2)

        assert ws_manager._command_handlers[ClientCommand.START_TASK] is handler2
