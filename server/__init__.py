"""Server package for Ralph orchestrator web UI.

This package contains modules for the web server backend that provides:
- Real-time event broadcasting via WebSocket
- REST API endpoints for project management
- Integration with existing Ralph services
"""

from .events import (
    # Event type enum
    EventType,
    # Base event class
    Event,
    # Specific event classes
    TaskStartedEvent,
    TaskCompletedEvent,
    AgentOutputEvent,
    AgentPhaseChangedEvent,
    GateRunningEvent,
    GateCompletedEvent,
    SignalDetectedEvent,
    SessionChangedEvent,
    ConfigChangedEvent,
    # Handler type aliases
    EventHandler,
    AsyncEventHandler,
    # Core classes
    EventEmitter,
    EventQueue,
    # Service bridge
    create_service_bridge,
)

from .api import (
    # FastAPI application
    app,
    # Response models
    ProjectResponse,
    TaskResponse,
    ConfigResponse,
    BranchResponse,
    TimelineEvent,
)

from .websocket import (
    # Constants
    HEARTBEAT_INTERVAL,
    CONNECTION_TIMEOUT,
    MAX_MESSAGE_SIZE,
    # Enums
    ClientCommand,
    ServerMessageType,
    # Classes
    ConnectionInfo,
    WebSocketManager,
    # Functions
    websocket_endpoint,
    create_websocket_manager,
    # Types
    CommandHandler,
)

__all__ = [
    # FastAPI application
    "app",
    # Event type enum
    "EventType",
    # Base event class
    "Event",
    # Specific event classes
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "AgentOutputEvent",
    "AgentPhaseChangedEvent",
    "GateRunningEvent",
    "GateCompletedEvent",
    "SignalDetectedEvent",
    "SessionChangedEvent",
    "ConfigChangedEvent",
    # Handler type aliases
    "EventHandler",
    "AsyncEventHandler",
    # Core classes
    "EventEmitter",
    "EventQueue",
    # Service bridge
    "create_service_bridge",
    # Response models
    "ProjectResponse",
    "TaskResponse",
    "ConfigResponse",
    "BranchResponse",
    "TimelineEvent",
    # WebSocket - Constants
    "HEARTBEAT_INTERVAL",
    "CONNECTION_TIMEOUT",
    "MAX_MESSAGE_SIZE",
    # WebSocket - Enums
    "ClientCommand",
    "ServerMessageType",
    # WebSocket - Classes
    "ConnectionInfo",
    "WebSocketManager",
    # WebSocket - Functions
    "websocket_endpoint",
    "create_websocket_manager",
    # WebSocket - Types
    "CommandHandler",
]
