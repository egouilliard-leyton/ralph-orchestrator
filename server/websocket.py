"""WebSocket manager for real-time updates.

This module provides WebSocket connection management for broadcasting real-time
events to connected clients. It integrates with the event system to forward
events to WebSocket clients subscribed to specific projects.

Features:
- Connection management per project (track active connections)
- Server-to-client event broadcasting
- Client-to-server command handling
- Heartbeat/ping-pong for connection health monitoring
- Graceful disconnect handling
- Integration with EventEmitter for event subscription

Usage:
    from server.websocket import WebSocketManager, websocket_endpoint

    # Create manager (typically done once at app startup)
    manager = WebSocketManager()

    # Add WebSocket route to FastAPI
    @app.websocket("/ws/{project_id}")
    async def websocket_route(websocket: WebSocket, project_id: str):
        await websocket_endpoint(websocket, project_id, manager)

    # Broadcast events through the manager
    manager.broadcast_to_project("my-project", event.to_dict())
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .events import (
    Event,
    EventEmitter,
    EventType,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30.0

# Connection timeout after missed heartbeats
CONNECTION_TIMEOUT = 90.0

# Maximum message size in bytes (1MB)
MAX_MESSAGE_SIZE = 1024 * 1024


# =============================================================================
# Client command types
# =============================================================================


class ClientCommand(str, Enum):
    """Commands that can be sent from client to server.

    These commands allow clients to trigger actions on the server
    through the WebSocket connection.
    """

    # Task execution commands
    START_TASK = "start_task"
    CANCEL_EXECUTION = "cancel_execution"

    # Git commands
    CREATE_BRANCH = "create_branch"

    # Connection management
    PING = "ping"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


class ServerMessageType(str, Enum):
    """Types of messages sent from server to client.

    These message types wrap different kinds of server-side events
    and responses to client commands.
    """

    # Event broadcast
    EVENT = "event"

    # Command responses
    COMMAND_RESPONSE = "command_response"
    COMMAND_ERROR = "command_error"

    # Connection management
    PONG = "pong"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# =============================================================================
# Connection tracking
# =============================================================================


@dataclass
class ConnectionInfo:
    """Information about a single WebSocket connection.

    Tracks connection metadata for monitoring and management.

    Attributes:
        connection_id: Unique identifier for this connection
        websocket: The WebSocket instance
        project_id: Project this connection is subscribed to
        connected_at: Unix timestamp when connection was established
        last_heartbeat: Unix timestamp of last heartbeat (ping/pong)
        subscribed_events: Set of event types the client wants to receive
        metadata: Additional connection metadata
    """

    connection_id: str
    websocket: WebSocket
    project_id: str
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    subscribed_events: Set[EventType] = field(default_factory=lambda: set(EventType))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Check if connection is still healthy based on heartbeat."""
        return (time.time() - self.last_heartbeat) < CONNECTION_TIMEOUT

    def update_heartbeat(self) -> None:
        """Update the last heartbeat timestamp."""
        self.last_heartbeat = time.time()


# =============================================================================
# Command handler type
# =============================================================================

CommandHandler = Callable[[str, Dict[str, Any], ConnectionInfo], Any]


# =============================================================================
# WebSocket Manager
# =============================================================================


class WebSocketManager:
    """Manager for WebSocket connections and event broadcasting.

    Handles multiple WebSocket connections per project, broadcasting events
    only to clients subscribed to the relevant project. Provides command
    handling for client-to-server communication.

    The manager integrates with EventEmitter to automatically forward
    events to connected clients.

    Usage:
        manager = WebSocketManager()

        # Connect a client
        connection = await manager.connect(websocket, "project-123")

        # Broadcast an event to all clients for a project
        await manager.broadcast_to_project("project-123", {"type": "update", "data": {}})

        # Handle incoming messages
        await manager.handle_message(connection, message_data)

        # Disconnect a client
        await manager.disconnect(connection)

    Thread Safety:
        The manager uses asyncio.Lock for thread-safe operations on
        connection dictionaries. All public methods are async-safe.
    """

    def __init__(self, emitter: Optional[EventEmitter] = None):
        """Initialize the WebSocket manager.

        Args:
            emitter: Optional EventEmitter to integrate with. If provided,
                    events emitted to the emitter will be broadcast to
                    WebSocket clients.
        """
        # Connections indexed by project_id -> {connection_id -> ConnectionInfo}
        self._connections: Dict[str, Dict[str, ConnectionInfo]] = {}

        # All connections indexed by connection_id for quick lookup
        self._all_connections: Dict[str, ConnectionInfo] = {}

        # Lock for thread-safe connection management
        self._lock = asyncio.Lock()

        # Event emitter integration
        self._emitter = emitter
        if emitter:
            self._setup_emitter_integration(emitter)

        # Command handlers
        self._command_handlers: Dict[ClientCommand, CommandHandler] = {}
        self._setup_default_handlers()

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    def _setup_emitter_integration(self, emitter: EventEmitter) -> None:
        """Set up integration with EventEmitter.

        Subscribes to all events and forwards them to WebSocket clients.

        Args:
            emitter: The EventEmitter to integrate with.
        """
        async def event_handler(event: Event) -> None:
            """Forward events to WebSocket clients."""
            await self.broadcast_event(event)

        # Subscribe to all events
        def forward_event(e: Event) -> None:
            asyncio.create_task(event_handler(e))

        emitter.subscribe_all(forward_event)

    def _setup_default_handlers(self) -> None:
        """Set up default command handlers."""
        self.register_command_handler(ClientCommand.PING, self._handle_ping)
        self.register_command_handler(ClientCommand.SUBSCRIBE, self._handle_subscribe)
        self.register_command_handler(ClientCommand.UNSUBSCRIBE, self._handle_unsubscribe)

    async def start(self) -> None:
        """Start the WebSocket manager background tasks.

        Starts the heartbeat monitoring task that checks connection health.
        """
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WebSocket manager started")

    async def stop(self) -> None:
        """Stop the WebSocket manager and close all connections.

        Gracefully disconnects all clients and stops background tasks.
        """
        self._running = False

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Close all connections
        async with self._lock:
            for connection in list(self._all_connections.values()):
                await self._close_connection(connection, "Server shutting down")

        logger.info("WebSocket manager stopped")

    async def connect(
        self,
        websocket: WebSocket,
        project_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConnectionInfo:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket instance from FastAPI.
            project_id: The project ID this connection subscribes to.
            metadata: Optional metadata about the connection.

        Returns:
            ConnectionInfo for the new connection.
        """
        await websocket.accept()

        connection_id = str(uuid.uuid4())
        connection = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket,
            project_id=project_id,
            metadata=metadata or {},
        )

        async with self._lock:
            # Add to project connections
            if project_id not in self._connections:
                self._connections[project_id] = {}
            self._connections[project_id][connection_id] = connection

            # Add to all connections
            self._all_connections[connection_id] = connection

        logger.info(
            f"WebSocket connected: {connection_id} for project {project_id}"
        )

        # Send connected message
        await self._send_message(
            connection,
            ServerMessageType.CONNECTED,
            {
                "connection_id": connection_id,
                "project_id": project_id,
                "subscribed_events": [e.value for e in connection.subscribed_events],
            },
        )

        return connection

    async def disconnect(self, connection: ConnectionInfo) -> None:
        """Disconnect a WebSocket connection.

        Args:
            connection: The connection to disconnect.
        """
        async with self._lock:
            # Remove from project connections
            project_connections = self._connections.get(connection.project_id, {})
            project_connections.pop(connection.connection_id, None)

            # Clean up empty project entries
            if not project_connections:
                self._connections.pop(connection.project_id, None)

            # Remove from all connections
            self._all_connections.pop(connection.connection_id, None)

        logger.info(
            f"WebSocket disconnected: {connection.connection_id} "
            f"for project {connection.project_id}"
        )

    async def _close_connection(
        self,
        connection: ConnectionInfo,
        reason: str = "Connection closed",
    ) -> None:
        """Close a WebSocket connection gracefully.

        Args:
            connection: The connection to close.
            reason: Reason for closing the connection.
        """
        try:
            if connection.websocket.client_state == WebSocketState.CONNECTED:
                await self._send_message(
                    connection,
                    ServerMessageType.DISCONNECTED,
                    {"reason": reason},
                )
                await connection.websocket.close()
        except Exception as e:
            logger.debug(f"Error closing connection {connection.connection_id}: {e}")

    async def broadcast_event(self, event: Event) -> int:
        """Broadcast an event to all clients subscribed to the event's project.

        Args:
            event: The event to broadcast.

        Returns:
            Number of clients the event was sent to.
        """
        return await self.broadcast_to_project(
            event.project_id,
            {
                "event_type": event.event_type.value,
                **event.to_dict(),
            },
            event_type=event.event_type,
        )

    async def broadcast_to_project(
        self,
        project_id: str,
        data: Dict[str, Any],
        event_type: Optional[EventType] = None,
    ) -> int:
        """Broadcast a message to all clients subscribed to a project.

        Args:
            project_id: The project ID to broadcast to.
            data: The data to send.
            event_type: Optional event type for filtering subscribed clients.

        Returns:
            Number of clients the message was sent to.
        """
        async with self._lock:
            connections = list(self._connections.get(project_id, {}).values())

        if not connections:
            return 0

        sent_count = 0
        for connection in connections:
            # Check if client is subscribed to this event type
            if event_type and connection.subscribed_events:
                if event_type not in connection.subscribed_events:
                    continue

            try:
                await self._send_message(connection, ServerMessageType.EVENT, data)
                sent_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to send to {connection.connection_id}: {e}"
                )
                # Schedule disconnect for failed connections
                asyncio.create_task(self.disconnect(connection))

        return sent_count

    async def broadcast_to_all(self, data: Dict[str, Any]) -> int:
        """Broadcast a message to all connected clients.

        Args:
            data: The data to send.

        Returns:
            Number of clients the message was sent to.
        """
        async with self._lock:
            connections = list(self._all_connections.values())

        sent_count = 0
        for connection in connections:
            try:
                await self._send_message(connection, ServerMessageType.EVENT, data)
                sent_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to send to {connection.connection_id}: {e}"
                )
                asyncio.create_task(self.disconnect(connection))

        return sent_count

    async def handle_message(
        self,
        connection: ConnectionInfo,
        message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle an incoming message from a client.

        Parses the message and routes it to the appropriate command handler.

        Args:
            connection: The connection that sent the message.
            message: The parsed message data.

        Returns:
            Response data to send back to the client, or None.
        """
        command_str = message.get("command")
        if not command_str:
            await self._send_error(connection, "Missing 'command' field")
            return None

        try:
            command = ClientCommand(command_str)
        except ValueError:
            await self._send_error(
                connection,
                f"Unknown command: {command_str}",
            )
            return None

        payload = message.get("payload", {})

        # Get handler
        handler = self._command_handlers.get(command)
        if not handler:
            await self._send_error(
                connection,
                f"No handler for command: {command.value}",
            )
            return None

        try:
            result = handler(connection.project_id, payload, connection)
            if asyncio.iscoroutine(result):
                result = await result

            # Send success response
            await self._send_message(
                connection,
                ServerMessageType.COMMAND_RESPONSE,
                {
                    "command": command.value,
                    "success": True,
                    "result": result,
                },
            )
            return result

        except Exception as e:
            logger.exception(f"Error handling command {command.value}")
            await self._send_message(
                connection,
                ServerMessageType.COMMAND_ERROR,
                {
                    "command": command.value,
                    "success": False,
                    "error": str(e),
                },
            )
            return None

    def register_command_handler(
        self,
        command: ClientCommand,
        handler: CommandHandler,
    ) -> None:
        """Register a handler for a client command.

        Args:
            command: The command to handle.
            handler: The handler function. Can be sync or async.
        """
        self._command_handlers[command] = handler

    # =========================================================================
    # Default command handlers
    # =========================================================================

    def _handle_ping(
        self,
        project_id: str,
        payload: Dict[str, Any],
        connection: ConnectionInfo,
    ) -> Dict[str, Any]:
        """Handle ping command for heartbeat."""
        connection.update_heartbeat()
        return {"timestamp": time.time()}

    def _handle_subscribe(
        self,
        project_id: str,
        payload: Dict[str, Any],
        connection: ConnectionInfo,
    ) -> Dict[str, Any]:
        """Handle subscribe command to filter events."""
        event_types = payload.get("event_types", [])
        if event_types:
            connection.subscribed_events = {
                EventType(et) for et in event_types
                if et in [e.value for e in EventType]
            }
        else:
            # Subscribe to all events
            connection.subscribed_events = set(EventType)

        return {
            "subscribed_events": [e.value for e in connection.subscribed_events],
        }

    def _handle_unsubscribe(
        self,
        project_id: str,
        payload: Dict[str, Any],
        connection: ConnectionInfo,
    ) -> Dict[str, Any]:
        """Handle unsubscribe command."""
        event_types = payload.get("event_types", [])
        for et_str in event_types:
            try:
                et = EventType(et_str)
                connection.subscribed_events.discard(et)
            except ValueError:
                pass

        return {
            "subscribed_events": [e.value for e in connection.subscribed_events],
        }

    # =========================================================================
    # Internal helpers
    # =========================================================================

    async def _send_message(
        self,
        connection: ConnectionInfo,
        message_type: ServerMessageType,
        data: Dict[str, Any],
    ) -> None:
        """Send a message to a connection.

        Args:
            connection: The connection to send to.
            message_type: The type of message.
            data: The message data.
        """
        message = {
            "type": message_type.value,
            "timestamp": time.time(),
            **data,
        }
        await connection.websocket.send_json(message)

    async def _send_error(
        self,
        connection: ConnectionInfo,
        error: str,
    ) -> None:
        """Send an error message to a connection.

        Args:
            connection: The connection to send to.
            error: The error message.
        """
        await self._send_message(
            connection,
            ServerMessageType.ERROR,
            {"error": error},
        )

    async def _heartbeat_loop(self) -> None:
        """Background task to check connection health."""
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                async with self._lock:
                    connections = list(self._all_connections.values())

                for connection in connections:
                    if not connection.is_healthy():
                        logger.info(
                            f"Connection {connection.connection_id} timed out"
                        )
                        await self._close_connection(
                            connection,
                            "Heartbeat timeout",
                        )
                        await self.disconnect(connection)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in heartbeat loop: {e}")

    # =========================================================================
    # Status methods
    # =========================================================================

    def get_connection_count(self, project_id: Optional[str] = None) -> int:
        """Get the number of active connections.

        Args:
            project_id: Optional project ID to filter by.

        Returns:
            Number of connections.
        """
        if project_id:
            return len(self._connections.get(project_id, {}))
        return len(self._all_connections)

    def get_connections_for_project(self, project_id: str) -> List[ConnectionInfo]:
        """Get all connections for a project.

        Args:
            project_id: The project ID.

        Returns:
            List of ConnectionInfo objects.
        """
        return list(self._connections.get(project_id, {}).values())

    def get_all_connections(self) -> List[ConnectionInfo]:
        """Get all active connections.

        Returns:
            List of all ConnectionInfo objects.
        """
        return list(self._all_connections.values())

    def get_connected_projects(self) -> List[str]:
        """Get list of projects with active connections.

        Returns:
            List of project IDs.
        """
        return list(self._connections.keys())


# =============================================================================
# WebSocket endpoint function
# =============================================================================


async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    manager: WebSocketManager,
    on_connect: Optional[Callable[[ConnectionInfo], Any]] = None,
    on_disconnect: Optional[Callable[[ConnectionInfo], Any]] = None,
) -> None:
    """WebSocket endpoint handler for use with FastAPI.

    This function handles the complete lifecycle of a WebSocket connection:
    1. Accepts the connection and registers it with the manager
    2. Processes incoming messages in a loop
    3. Handles disconnection gracefully

    Usage:
        @app.websocket("/ws/{project_id}")
        async def ws_route(websocket: WebSocket, project_id: str):
            await websocket_endpoint(websocket, project_id, manager)

    Args:
        websocket: The WebSocket instance from FastAPI.
        project_id: The project ID from the URL path.
        manager: The WebSocketManager instance.
        on_connect: Optional callback when connection is established.
        on_disconnect: Optional callback when connection is closed.
    """
    connection = await manager.connect(websocket, project_id)

    if on_connect:
        result = on_connect(connection)
        if asyncio.iscoroutine(result):
            await result

    try:
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await manager._send_error(connection, "Invalid JSON")
                    continue

                # Handle the message
                await manager.handle_message(connection, message)

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.exception(f"Error processing WebSocket message: {e}")
                try:
                    await manager._send_error(connection, f"Internal error: {e}")
                except Exception:
                    break

    finally:
        await manager.disconnect(connection)

        if on_disconnect:
            result = on_disconnect(connection)
            if asyncio.iscoroutine(result):
                await result


# =============================================================================
# Factory function for creating manager with command handlers
# =============================================================================


def create_websocket_manager(
    emitter: Optional[EventEmitter] = None,
    command_handlers: Optional[Dict[ClientCommand, CommandHandler]] = None,
) -> WebSocketManager:
    """Create a WebSocketManager with optional configuration.

    Factory function to create a configured WebSocketManager instance.

    Args:
        emitter: Optional EventEmitter for automatic event broadcasting.
        command_handlers: Optional dict of command handlers to register.

    Returns:
        Configured WebSocketManager instance.

    Usage:
        manager = create_websocket_manager(
            emitter=my_emitter,
            command_handlers={
                ClientCommand.START_TASK: handle_start_task,
                ClientCommand.CANCEL_EXECUTION: handle_cancel,
            },
        )
    """
    manager = WebSocketManager(emitter=emitter)

    if command_handlers:
        for command, handler in command_handlers.items():
            manager.register_command_handler(command, handler)

    return manager


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "HEARTBEAT_INTERVAL",
    "CONNECTION_TIMEOUT",
    "MAX_MESSAGE_SIZE",
    # Enums
    "ClientCommand",
    "ServerMessageType",
    # Classes
    "ConnectionInfo",
    "WebSocketManager",
    # Functions
    "websocket_endpoint",
    "create_websocket_manager",
    # Types
    "CommandHandler",
]
