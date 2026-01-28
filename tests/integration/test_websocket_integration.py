"""Integration tests for WebSocket functionality."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock
from server.websocket import (
    WebSocketManager,
    ClientCommand,
    ServerMessageType,
    ConnectionInfo,
    websocket_endpoint,
)
from server.events import EventEmitter, EventType, TaskStartedEvent


@pytest.fixture
def event_emitter():
    """Create an EventEmitter for testing."""
    return EventEmitter()


@pytest.fixture
def ws_manager(event_emitter):
    """Create a WebSocketManager for testing."""
    return WebSocketManager(emitter=event_emitter)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = Mock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.client_state = "CONNECTED"
    return ws


class TestWebSocketManager:
    """Test WebSocketManager class."""

    @pytest.mark.asyncio
    async def test_connect(self, ws_manager, mock_websocket):
        """Test connecting a WebSocket client."""
        connection = await ws_manager.connect(mock_websocket, "test-project")
        
        assert connection.project_id == "test-project"
        assert connection.websocket == mock_websocket
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, ws_manager, mock_websocket):
        """Test disconnecting a WebSocket client."""
        connection = await ws_manager.connect(mock_websocket, "test-project")
        
        await ws_manager.disconnect(connection)
        
        # Connection should be removed
        assert ws_manager.get_connection_count("test-project") == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_project(self, ws_manager, mock_websocket):
        """Test broadcasting message to project subscribers."""
        await ws_manager.connect(mock_websocket, "test-project")

        # Reset mock after connect (which sends a connected message)
        mock_websocket.send_json.reset_mock()

        message_data = {"type": "test", "data": "Hello"}
        sent_count = await ws_manager.broadcast_to_project("test-project", message_data)

        assert sent_count == 1
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_project(self, ws_manager):
        """Test broadcasting to project with no connections."""
        message_data = {"type": "test", "data": "Hello"}
        sent_count = await ws_manager.broadcast_to_project("nonexistent", message_data)
        
        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_handle_ping_command(self, ws_manager, mock_websocket):
        """Test handling ping command from client."""
        connection = await ws_manager.connect(mock_websocket, "test-project")
        
        message = {
            "command": "ping",
            "payload": {}
        }
        
        await ws_manager.handle_message(connection, message)
        
        # Should send command response
        assert mock_websocket.send_json.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_subscribe_command(self, ws_manager, mock_websocket):
        """Test handling subscribe command."""
        connection = await ws_manager.connect(mock_websocket, "test-project")
        
        message = {
            "command": "subscribe",
            "payload": {
                "event_types": ["task_started", "task_completed"]
            }
        }
        
        await ws_manager.handle_message(connection, message)
        
        # Connection should now filter events
        assert EventType.TASK_STARTED in connection.subscribed_events
        assert EventType.TASK_COMPLETED in connection.subscribed_events

    @pytest.mark.asyncio
    async def test_handle_invalid_command(self, ws_manager, mock_websocket):
        """Test handling invalid command from client."""
        connection = await ws_manager.connect(mock_websocket, "test-project")
        
        message = {
            "command": "invalid_command",
            "payload": {}
        }
        
        await ws_manager.handle_message(connection, message)
        
        # Should send error response
        assert mock_websocket.send_json.call_count >= 1

    @pytest.mark.asyncio
    async def test_broadcast_event(self, ws_manager, mock_websocket):
        """Test broadcasting event through manager."""
        await ws_manager.connect(mock_websocket, "test-project")
        
        event = TaskStartedEvent(
            project_id="test-project",
            task_id="T-001",
            task_title="Test Task"
        )
        
        sent_count = await ws_manager.broadcast_event(event)
        
        assert sent_count == 1
        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_get_connection_count(self, ws_manager, mock_websocket):
        """Test getting connection count."""
        assert ws_manager.get_connection_count() == 0
        
        await ws_manager.connect(mock_websocket, "test-project")
        
        assert ws_manager.get_connection_count() == 1
        assert ws_manager.get_connection_count("test-project") == 1

    @pytest.mark.asyncio
    async def test_get_connections_for_project(self, ws_manager, mock_websocket):
        """Test getting connections for specific project."""
        connection = await ws_manager.connect(mock_websocket, "test-project")
        
        connections = ws_manager.get_connections_for_project("test-project")
        
        assert len(connections) == 1
        assert connections[0].connection_id == connection.connection_id

    @pytest.mark.asyncio
    async def test_get_connected_projects(self, ws_manager, mock_websocket):
        """Test getting list of connected projects."""
        await ws_manager.connect(mock_websocket, "test-project-1")
        
        projects = ws_manager.get_connected_projects()
        
        assert "test-project-1" in projects


class TestConnectionInfo:
    """Test ConnectionInfo dataclass."""

    def test_connection_info_is_healthy(self, mock_websocket):
        """Test connection health check."""
        connection = ConnectionInfo(
            connection_id="test-123",
            websocket=mock_websocket,
            project_id="test-project"
        )
        
        assert connection.is_healthy() is True

    def test_connection_info_update_heartbeat(self, mock_websocket):
        """Test updating connection heartbeat."""
        connection = ConnectionInfo(
            connection_id="test-123",
            websocket=mock_websocket,
            project_id="test-project"
        )
        
        initial_heartbeat = connection.last_heartbeat
        connection.update_heartbeat()
        
        assert connection.last_heartbeat >= initial_heartbeat


class TestEventIntegration:
    """Test integration between EventEmitter and WebSocketManager."""

    @pytest.mark.asyncio
    async def test_event_emitter_broadcasts_to_websocket(
        self, event_emitter, mock_websocket
    ):
        """Test that events emitted to EventEmitter reach WebSocket clients."""
        # Create manager with emitter integration
        manager = WebSocketManager(emitter=event_emitter)
        await manager.connect(mock_websocket, "test-project")
        
        # Emit an event through the emitter
        event = TaskStartedEvent(
            project_id="test-project",
            task_id="T-001",
            task_title="Test Task"
        )
        event_emitter.emit(event)
        
        # Give async tasks time to process
        await asyncio.sleep(0.1)
        
        # WebSocket should have received the event
        assert mock_websocket.send_json.call_count >= 1


class TestClientCommand:
    """Test ClientCommand enum."""

    def test_client_command_values(self):
        """Test that all expected commands are defined."""
        assert ClientCommand.PING.value == "ping"
        assert ClientCommand.SUBSCRIBE.value == "subscribe"
        assert ClientCommand.UNSUBSCRIBE.value == "unsubscribe"


class TestServerMessageType:
    """Test ServerMessageType enum."""

    def test_server_message_type_values(self):
        """Test that all expected message types are defined."""
        assert ServerMessageType.EVENT.value == "event"
        assert ServerMessageType.COMMAND_RESPONSE.value == "command_response"
        assert ServerMessageType.COMMAND_ERROR.value == "command_error"
        assert ServerMessageType.PONG.value == "pong"
        assert ServerMessageType.CONNECTED.value == "connected"
        assert ServerMessageType.ERROR.value == "error"
