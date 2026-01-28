"""Services package for Ralph orchestrator.

This package contains CLI-agnostic services that provide core functionality
for orchestration, allowing both CLI and web UI interfaces to share the same
underlying logic.

Services:
- OrchestrationService: Core task execution loop with event hooks
- ProjectService: Project discovery and multi-project management
- SessionService: Session CRUD operations with event emission
- ConfigService: Configuration file management with validation
- GitService: Git operations and PR management
"""

from .orchestration_service import (
    OrchestrationService,
    OrchestrationEvent,
    EventType,
    TaskStartedEvent,
    TaskCompletedEvent,
    AgentPhaseChangedEvent,
    GateRunningEvent,
    GateCompletedEvent,
    SignalDetectedEvent,
    EventHandler,
)

from .project_service import (
    ProjectService,
    ProjectMetadata,
    ProjectEvent,
    ProjectEventType,
    ProjectDiscoveredEvent,
    ProjectRemovedEvent,
    ProjectUpdatedEvent,
    ScanStartedEvent,
    ScanCompletedEvent,
    ProjectEventHandler,
)

from .session_service import (
    SessionService,
    SessionSummary,
    TaskStatusSummary,
    SessionEvent,
    SessionEventType,
    SessionCreatedEvent,
    SessionLoadedEvent,
    SessionEndedEvent,
    SessionDeletedEvent,
    TaskStartedEvent as SessionTaskStartedEvent,
    TaskCompletedEvent as SessionTaskCompletedEvent,
    TaskFailedEvent,
    IterationIncrementedEvent,
    StatusChangedEvent,
    MetadataUpdatedEvent,
    SessionEventHandler,
)

from .config_service import (
    ConfigService,
    ConfigSummary,
    ConfigEvent,
    ConfigEventType,
    ConfigLoadedEvent,
    ConfigUpdatedEvent,
    ConfigCreatedEvent,
    ConfigDeletedEvent,
    ConfigValidationFailedEvent,
    ConfigReloadedEvent,
    ConfigEventHandler,
    ConfigValidationError,
)

from .git_service import (
    GitService,
    GitEvent,
    GitEventType,
    BranchCreatedEvent,
    BranchSwitchedEvent,
    BranchDeletedEvent,
    PRCreatedEvent,
    PRUpdatedEvent,
    CommitCreatedEvent,
    PushCompletedEvent,
    FetchCompletedEvent,
    GitErrorEvent,
    GitEventHandler,
    BranchInfo,
    PRInfo,
    GitStatus,
    GitError,
)

__all__ = [
    # OrchestrationService
    "OrchestrationService",
    "OrchestrationEvent",
    "EventType",
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "AgentPhaseChangedEvent",
    "GateRunningEvent",
    "GateCompletedEvent",
    "SignalDetectedEvent",
    "EventHandler",
    # ProjectService
    "ProjectService",
    "ProjectMetadata",
    "ProjectEvent",
    "ProjectEventType",
    "ProjectDiscoveredEvent",
    "ProjectRemovedEvent",
    "ProjectUpdatedEvent",
    "ScanStartedEvent",
    "ScanCompletedEvent",
    "ProjectEventHandler",
    # SessionService
    "SessionService",
    "SessionSummary",
    "TaskStatusSummary",
    "SessionEvent",
    "SessionEventType",
    "SessionCreatedEvent",
    "SessionLoadedEvent",
    "SessionEndedEvent",
    "SessionDeletedEvent",
    "SessionTaskStartedEvent",
    "SessionTaskCompletedEvent",
    "TaskFailedEvent",
    "IterationIncrementedEvent",
    "StatusChangedEvent",
    "MetadataUpdatedEvent",
    "SessionEventHandler",
    # ConfigService
    "ConfigService",
    "ConfigSummary",
    "ConfigEvent",
    "ConfigEventType",
    "ConfigLoadedEvent",
    "ConfigUpdatedEvent",
    "ConfigCreatedEvent",
    "ConfigDeletedEvent",
    "ConfigValidationFailedEvent",
    "ConfigReloadedEvent",
    "ConfigEventHandler",
    "ConfigValidationError",
    # GitService
    "GitService",
    "GitEvent",
    "GitEventType",
    "BranchCreatedEvent",
    "BranchSwitchedEvent",
    "BranchDeletedEvent",
    "PRCreatedEvent",
    "PRUpdatedEvent",
    "CommitCreatedEvent",
    "PushCompletedEvent",
    "FetchCompletedEvent",
    "GitErrorEvent",
    "GitEventHandler",
    "BranchInfo",
    "PRInfo",
    "GitStatus",
    "GitError",
]
