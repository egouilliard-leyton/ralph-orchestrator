"""Configuration management service.

This module provides the ConfigService class for managing Ralph configuration
files (ralph.yml) with CRUD operations, validation, and event emission.

Features:
- Load and validate ralph.yml against JSON schema
- Update configuration with automatic validation
- Watch for config file changes
- Event emission for config state changes
- CLI-agnostic interface for both CLI and API usage
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from jsonschema import Draft7Validator

from ..config import (
    RalphConfig,
    GateConfig,
    ServiceConfig,
    AgentRoleConfig,
    LimitsConfig,
    GitConfig,
    AutopilotConfig,
    load_config,
    validate_against_schema,
    _parse_gate,
    _parse_service,
    _parse_agent_role,
    _parse_limits,
    _parse_git,
    _parse_autopilot,
    PROJECT_ROOT,
)


class ConfigEventType(str, Enum):
    """Types of events emitted by the config service."""
    CONFIG_LOADED = "config_loaded"
    CONFIG_UPDATED = "config_updated"
    CONFIG_CREATED = "config_created"
    CONFIG_DELETED = "config_deleted"
    CONFIG_VALIDATION_FAILED = "config_validation_failed"
    CONFIG_RELOADED = "config_reloaded"


@dataclass
class ConfigEvent:
    """Base class for config events."""
    event_type: ConfigEventType
    timestamp: float = field(default_factory=time.time)
    project_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "project_path": self.project_path,
        }


@dataclass
class ConfigLoadedEvent(ConfigEvent):
    """Event emitted when a config is loaded."""
    event_type: ConfigEventType = field(init=False, default=ConfigEventType.CONFIG_LOADED)
    config_path: str = ""
    version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
            "version": self.version,
        })
        return d


@dataclass
class ConfigUpdatedEvent(ConfigEvent):
    """Event emitted when a config is updated."""
    event_type: ConfigEventType = field(init=False, default=ConfigEventType.CONFIG_UPDATED)
    config_path: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
            "changes": self.changes,
        })
        return d


@dataclass
class ConfigCreatedEvent(ConfigEvent):
    """Event emitted when a new config is created."""
    event_type: ConfigEventType = field(init=False, default=ConfigEventType.CONFIG_CREATED)
    config_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
        })
        return d


@dataclass
class ConfigDeletedEvent(ConfigEvent):
    """Event emitted when a config is deleted."""
    event_type: ConfigEventType = field(init=False, default=ConfigEventType.CONFIG_DELETED)
    config_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
        })
        return d


@dataclass
class ConfigValidationFailedEvent(ConfigEvent):
    """Event emitted when config validation fails."""
    event_type: ConfigEventType = field(init=False, default=ConfigEventType.CONFIG_VALIDATION_FAILED)
    config_path: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
            "errors": self.errors,
        })
        return d


@dataclass
class ConfigReloadedEvent(ConfigEvent):
    """Event emitted when a config is reloaded from disk."""
    event_type: ConfigEventType = field(init=False, default=ConfigEventType.CONFIG_RELOADED)
    config_path: str = ""
    changed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "config_path": self.config_path,
            "changed": self.changed,
        })
        return d


# Type alias for event handlers
ConfigEventHandler = Callable[[Any], None]


@dataclass
class ConfigSummary:
    """Summary of a Ralph configuration."""
    config_path: Path
    project_path: Path
    version: str
    task_source_type: str
    task_source_path: str
    git_base_branch: str
    git_remote: str
    gates_build_count: int
    gates_full_count: int
    test_paths: List[str]
    has_backend: bool
    has_frontend: bool
    autopilot_enabled: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config_path": str(self.config_path),
            "project_path": str(self.project_path),
            "version": self.version,
            "task_source_type": self.task_source_type,
            "task_source_path": self.task_source_path,
            "git_base_branch": self.git_base_branch,
            "git_remote": self.git_remote,
            "gates_build_count": self.gates_build_count,
            "gates_full_count": self.gates_full_count,
            "test_paths": self.test_paths,
            "has_backend": self.has_backend,
            "has_frontend": self.has_frontend,
            "autopilot_enabled": self.autopilot_enabled,
        }


class ConfigValidationError(Exception):
    """Raised when config validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {'; '.join(errors[:3])}")


class ConfigService:
    """Service for managing Ralph configuration files.

    This service provides CRUD operations for ralph.yml configuration files,
    with automatic validation against the JSON schema and event emission
    for state changes.

    Usage:
        service = ConfigService()

        # Register event handlers
        service.on_event(ConfigEventType.CONFIG_UPDATED, my_handler)

        # Load a config
        config = service.load_config(Path("/path/to/project"))

        # Get config summary
        summary = service.get_config_summary(Path("/path/to/project"))

        # Update a specific section
        service.update_gates(
            Path("/path/to/project"),
            build=[{"name": "lint", "cmd": "ruff check ."}],
        )

        # Reload from disk
        service.reload_config(Path("/path/to/project"))
    """

    def __init__(self):
        """Initialize the config service."""
        # Cache of loaded configs keyed by project path
        self._configs: Dict[str, RalphConfig] = {}

        # Cache of raw config data for change detection
        self._raw_configs: Dict[str, Dict[str, Any]] = {}

        # Event handlers
        self._event_handlers: Dict[ConfigEventType, List[ConfigEventHandler]] = {
            event_type: [] for event_type in ConfigEventType
        }
        self._global_handlers: List[ConfigEventHandler] = []

    def on_event(self, event_type: ConfigEventType, handler: ConfigEventHandler) -> None:
        """Register an event handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: Callable that receives the event.
        """
        self._event_handlers[event_type].append(handler)

    def on_all_events(self, handler: ConfigEventHandler) -> None:
        """Register a handler for all events.

        Args:
            handler: Callable that receives any event.
        """
        self._global_handlers.append(handler)

    def remove_handler(self, event_type: ConfigEventType, handler: ConfigEventHandler) -> None:
        """Remove an event handler.

        Args:
            event_type: The type of event.
            handler: The handler to remove.
        """
        if handler in self._event_handlers[event_type]:
            self._event_handlers[event_type].remove(handler)

    def _emit_event(self, event: ConfigEvent) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: The event to emit.
        """
        # Call specific handlers
        for handler in self._event_handlers[event.event_type]:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors break the service

        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                pass

    def _get_path_key(self, project_path: Path | str) -> str:
        """Get normalized path key for caching."""
        return str(Path(project_path).resolve())

    def _get_config_path(self, project_path: Path | str) -> Path:
        """Get the config file path for a project."""
        return Path(project_path).resolve() / ".ralph" / "ralph.yml"

    # =========================================================================
    # CREATE operations
    # =========================================================================

    def create_config(
        self,
        project_path: Path | str,
        task_source_type: str = "prd_json",
        task_source_path: str = ".ralph/prd.json",
        git_base_branch: str = "main",
        git_remote: str = "origin",
        gates_build: Optional[List[Dict[str, Any]]] = None,
        gates_full: Optional[List[Dict[str, Any]]] = None,
        test_paths: Optional[List[str]] = None,
    ) -> RalphConfig:
        """Create a new ralph.yml configuration file.

        Args:
            project_path: Path to the project directory.
            task_source_type: Type of task source (prd_json, cr_markdown).
            task_source_path: Path to task source file.
            git_base_branch: Base branch for feature branches.
            git_remote: Git remote name.
            gates_build: Build gates configuration.
            gates_full: Full gates configuration.
            test_paths: Glob patterns for test file paths.

        Returns:
            Created RalphConfig instance.

        Raises:
            FileExistsError: If config already exists.
            ConfigValidationError: If config data is invalid.
        """
        path_key = self._get_path_key(project_path)
        project_path_obj = Path(project_path).resolve()
        config_path = self._get_config_path(project_path)

        # Check if config already exists
        if config_path.exists():
            raise FileExistsError(f"Config already exists: {config_path}")

        # Build config data
        config_data: Dict[str, Any] = {
            "version": "1",
            "task_source": {
                "type": task_source_type,
                "path": task_source_path,
            },
            "git": {
                "base_branch": git_base_branch,
                "remote": git_remote,
            },
            "gates": {
                "build": gates_build or [],
                "full": gates_full or [{"name": "test", "cmd": "pytest"}],
            },
        }

        if test_paths:
            config_data["test_paths"] = test_paths

        # Validate before writing
        valid, errors = validate_against_schema(config_data, "ralph-config.schema.json")
        if not valid:
            self._emit_event(ConfigValidationFailedEvent(
                project_path=path_key,
                config_path=str(config_path),
                errors=errors,
            ))
            raise ConfigValidationError(errors)

        # Ensure .ralph directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config file
        config_path.write_text(
            yaml.dump(config_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        # Load and cache the config
        config = load_config(config_path=config_path, repo_root=project_path_obj)
        self._configs[path_key] = config
        self._raw_configs[path_key] = config_data

        # Emit event
        self._emit_event(ConfigCreatedEvent(
            project_path=path_key,
            config_path=str(config_path),
        ))

        return config

    # =========================================================================
    # READ operations
    # =========================================================================

    def load_config(
        self,
        project_path: Path | str,
        force_reload: bool = False,
    ) -> RalphConfig:
        """Load a Ralph configuration from a project.

        Args:
            project_path: Path to the project directory.
            force_reload: If True, reload from disk even if cached.

        Returns:
            Loaded RalphConfig instance.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ConfigValidationError: If config is invalid.
        """
        path_key = self._get_path_key(project_path)
        config_path = self._get_config_path(project_path)

        # Check cache first (unless force_reload)
        if not force_reload and path_key in self._configs:
            return self._configs[path_key]

        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        try:
            config = load_config(
                config_path=config_path,
                repo_root=Path(project_path).resolve(),
            )

            # Cache the config and raw data
            self._configs[path_key] = config
            self._raw_configs[path_key] = config.raw_data.copy()

            # Emit event
            self._emit_event(ConfigLoadedEvent(
                project_path=path_key,
                config_path=str(config_path),
                version=config.version,
            ))

            return config

        except ValueError as e:
            # Validation failed
            error_str = str(e)
            errors = [error_str] if error_str else ["Unknown validation error"]
            self._emit_event(ConfigValidationFailedEvent(
                project_path=path_key,
                config_path=str(config_path),
                errors=errors,
            ))
            raise ConfigValidationError(errors) from e

    def get_config(self, project_path: Path | str) -> Optional[RalphConfig]:
        """Get a cached config without loading from disk.

        Args:
            project_path: Path to the project directory.

        Returns:
            Cached RalphConfig if available, None otherwise.
        """
        path_key = self._get_path_key(project_path)
        return self._configs.get(path_key)

    def config_exists(self, project_path: Path | str) -> bool:
        """Check if a config file exists for a project.

        Args:
            project_path: Path to the project directory.

        Returns:
            True if config exists.
        """
        config_path = self._get_config_path(project_path)
        return config_path.exists()

    def get_config_summary(self, project_path: Path | str) -> Optional[ConfigSummary]:
        """Get a summary of a project's configuration.

        Args:
            project_path: Path to the project directory.

        Returns:
            ConfigSummary if config exists, None otherwise.
        """
        try:
            config = self.load_config(project_path)
        except (FileNotFoundError, ConfigValidationError):
            return None

        return ConfigSummary(
            config_path=config.path,
            project_path=config.repo_root,
            version=config.version,
            task_source_type=config.task_source_type,
            task_source_path=config.task_source_path,
            git_base_branch=config.git.base_branch,
            git_remote=config.git.remote,
            gates_build_count=len(config.gates_build),
            gates_full_count=len(config.gates_full),
            test_paths=config.test_paths,
            has_backend=config.backend is not None,
            has_frontend=config.frontend is not None,
            autopilot_enabled=config.autopilot.enabled,
        )

    def get_raw_config(self, project_path: Path | str) -> Optional[Dict[str, Any]]:
        """Get the raw config data as a dictionary.

        Args:
            project_path: Path to the project directory.

        Returns:
            Raw config dict if available, None otherwise.
        """
        path_key = self._get_path_key(project_path)
        if path_key not in self._raw_configs:
            try:
                self.load_config(project_path)
            except (FileNotFoundError, ConfigValidationError):
                return None
        return self._raw_configs.get(path_key)

    # =========================================================================
    # UPDATE operations
    # =========================================================================

    def update_config(
        self,
        project_path: Path | str,
        updates: Dict[str, Any],
        validate: bool = True,
    ) -> RalphConfig:
        """Update configuration with new values.

        Args:
            project_path: Path to the project directory.
            updates: Dictionary of updates to apply (merged with existing).
            validate: If True, validate before saving.

        Returns:
            Updated RalphConfig instance.

        Raises:
            FileNotFoundError: If config doesn't exist.
            ConfigValidationError: If validation fails.
        """
        path_key = self._get_path_key(project_path)
        config_path = self._get_config_path(project_path)

        # Load current config
        config = self.load_config(project_path)
        current_data = config.raw_data.copy()

        # Deep merge updates
        new_data = self._deep_merge(current_data, updates)

        # Validate if requested
        if validate:
            valid, errors = validate_against_schema(new_data, "ralph-config.schema.json")
            if not valid:
                self._emit_event(ConfigValidationFailedEvent(
                    project_path=path_key,
                    config_path=str(config_path),
                    errors=errors,
                ))
                raise ConfigValidationError(errors)

        # Write updated config
        config_path.write_text(
            yaml.dump(new_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        # Detect changes
        changes = self._detect_changes(current_data, new_data)

        # Reload and cache
        new_config = load_config(
            config_path=config_path,
            repo_root=Path(project_path).resolve(),
        )
        self._configs[path_key] = new_config
        self._raw_configs[path_key] = new_data

        # Emit event
        self._emit_event(ConfigUpdatedEvent(
            project_path=path_key,
            config_path=str(config_path),
            changes=changes,
        ))

        return new_config

    def update_task_source(
        self,
        project_path: Path | str,
        source_type: str,
        source_path: str,
    ) -> RalphConfig:
        """Update the task source configuration.

        Args:
            project_path: Path to the project directory.
            source_type: Task source type (prd_json, cr_markdown).
            source_path: Path to task source file.

        Returns:
            Updated RalphConfig instance.
        """
        return self.update_config(project_path, {
            "task_source": {
                "type": source_type,
                "path": source_path,
            },
        })

    def update_git(
        self,
        project_path: Path | str,
        base_branch: Optional[str] = None,
        remote: Optional[str] = None,
    ) -> RalphConfig:
        """Update git configuration.

        Args:
            project_path: Path to the project directory.
            base_branch: Base branch for feature branches.
            remote: Git remote name.

        Returns:
            Updated RalphConfig instance.
        """
        updates: Dict[str, Any] = {"git": {}}
        if base_branch is not None:
            updates["git"]["base_branch"] = base_branch
        if remote is not None:
            updates["git"]["remote"] = remote

        return self.update_config(project_path, updates)

    def update_gates(
        self,
        project_path: Path | str,
        build: Optional[List[Dict[str, Any]]] = None,
        full: Optional[List[Dict[str, Any]]] = None,
    ) -> RalphConfig:
        """Update quality gates configuration.

        Args:
            project_path: Path to the project directory.
            build: Build gates list.
            full: Full gates list.

        Returns:
            Updated RalphConfig instance.
        """
        updates: Dict[str, Any] = {"gates": {}}
        if build is not None:
            updates["gates"]["build"] = build
        if full is not None:
            updates["gates"]["full"] = full

        return self.update_config(project_path, updates)

    def add_gate(
        self,
        project_path: Path | str,
        gate_type: str,
        name: str,
        cmd: str,
        when: Optional[str] = None,
        timeout_seconds: int = 300,
        fatal: bool = True,
    ) -> RalphConfig:
        """Add a quality gate.

        Args:
            project_path: Path to the project directory.
            gate_type: Type of gate (build or full).
            name: Gate name.
            cmd: Command to run.
            when: Condition for when to run.
            timeout_seconds: Timeout for gate.
            fatal: Whether failure stops execution.

        Returns:
            Updated RalphConfig instance.
        """
        config = self.load_config(project_path)
        gates = config.raw_data.get("gates", {})

        gate_list = list(gates.get(gate_type, []))
        gate_list.append({
            "name": name,
            "cmd": cmd,
            **({"when": when} if when else {}),
            "timeout_seconds": timeout_seconds,
            "fatal": fatal,
        })

        return self.update_gates(
            project_path,
            build=gate_list if gate_type == "build" else None,
            full=gate_list if gate_type == "full" else None,
        )

    def remove_gate(
        self,
        project_path: Path | str,
        gate_type: str,
        name: str,
    ) -> RalphConfig:
        """Remove a quality gate by name.

        Args:
            project_path: Path to the project directory.
            gate_type: Type of gate (build or full).
            name: Gate name to remove.

        Returns:
            Updated RalphConfig instance.
        """
        config = self.load_config(project_path)
        gates = config.raw_data.get("gates", {})

        gate_list = [g for g in gates.get(gate_type, []) if g.get("name") != name]

        return self.update_gates(
            project_path,
            build=gate_list if gate_type == "build" else None,
            full=gate_list if gate_type == "full" else None,
        )

    def update_test_paths(
        self,
        project_path: Path | str,
        test_paths: List[str],
    ) -> RalphConfig:
        """Update test paths configuration.

        Args:
            project_path: Path to the project directory.
            test_paths: List of glob patterns for test files.

        Returns:
            Updated RalphConfig instance.
        """
        return self.update_config(project_path, {"test_paths": test_paths})

    def update_limits(
        self,
        project_path: Path | str,
        claude_timeout: Optional[int] = None,
        max_iterations: Optional[int] = None,
        post_verify_iterations: Optional[int] = None,
        ui_fix_iterations: Optional[int] = None,
        robot_fix_iterations: Optional[int] = None,
    ) -> RalphConfig:
        """Update iteration and timeout limits.

        Args:
            project_path: Path to the project directory.
            claude_timeout: Timeout per Claude call in seconds.
            max_iterations: Max task loop iterations.
            post_verify_iterations: Max runtime fix iterations.
            ui_fix_iterations: Max agent-browser fix iterations.
            robot_fix_iterations: Max Robot Framework fix iterations.

        Returns:
            Updated RalphConfig instance.
        """
        updates: Dict[str, Any] = {"limits": {}}
        if claude_timeout is not None:
            updates["limits"]["claude_timeout"] = claude_timeout
        if max_iterations is not None:
            updates["limits"]["max_iterations"] = max_iterations
        if post_verify_iterations is not None:
            updates["limits"]["post_verify_iterations"] = post_verify_iterations
        if ui_fix_iterations is not None:
            updates["limits"]["ui_fix_iterations"] = ui_fix_iterations
        if robot_fix_iterations is not None:
            updates["limits"]["robot_fix_iterations"] = robot_fix_iterations

        return self.update_config(project_path, updates)

    def update_autopilot(
        self,
        project_path: Path | str,
        enabled: Optional[bool] = None,
        reports_dir: Optional[str] = None,
        branch_prefix: Optional[str] = None,
        create_pr: Optional[bool] = None,
    ) -> RalphConfig:
        """Update autopilot configuration.

        Args:
            project_path: Path to the project directory.
            enabled: Whether autopilot is enabled.
            reports_dir: Directory for reports.
            branch_prefix: Prefix for created branches.
            create_pr: Whether to create PRs.

        Returns:
            Updated RalphConfig instance.
        """
        updates: Dict[str, Any] = {"autopilot": {}}
        if enabled is not None:
            updates["autopilot"]["enabled"] = enabled
        if reports_dir is not None:
            updates["autopilot"]["reports_dir"] = reports_dir
        if branch_prefix is not None:
            updates["autopilot"]["branch_prefix"] = branch_prefix
        if create_pr is not None:
            updates["autopilot"]["create_pr"] = create_pr

        return self.update_config(project_path, updates)

    def reload_config(self, project_path: Path | str) -> RalphConfig:
        """Reload configuration from disk.

        Args:
            project_path: Path to the project directory.

        Returns:
            Reloaded RalphConfig instance.
        """
        path_key = self._get_path_key(project_path)
        config_path = self._get_config_path(project_path)

        # Get old data for change detection
        old_data = self._raw_configs.get(path_key, {})

        # Force reload
        config = self.load_config(project_path, force_reload=True)

        # Detect if changed
        changed = old_data != config.raw_data

        # Emit event
        self._emit_event(ConfigReloadedEvent(
            project_path=path_key,
            config_path=str(config_path),
            changed=changed,
        ))

        return config

    # =========================================================================
    # DELETE operations
    # =========================================================================

    def delete_config(self, project_path: Path | str) -> bool:
        """Delete a configuration file.

        Args:
            project_path: Path to the project directory.

        Returns:
            True if config was deleted, False if it didn't exist.
        """
        path_key = self._get_path_key(project_path)
        config_path = self._get_config_path(project_path)

        # Remove from cache
        if path_key in self._configs:
            del self._configs[path_key]
        if path_key in self._raw_configs:
            del self._raw_configs[path_key]

        # Delete file
        if config_path.exists():
            config_path.unlink()

            self._emit_event(ConfigDeletedEvent(
                project_path=path_key,
                config_path=str(config_path),
            ))

            return True

        return False

    def clear_cache(self) -> None:
        """Clear the config cache."""
        self._configs.clear()
        self._raw_configs.clear()

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_config(
        self,
        project_path: Path | str,
    ) -> tuple[bool, List[str]]:
        """Validate a configuration file.

        Args:
            project_path: Path to the project directory.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        config_path = self._get_config_path(project_path)

        if not config_path.exists():
            return False, [f"Config file not found: {config_path}"]

        try:
            raw_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            return False, [f"YAML parse error: {e}"]

        return validate_against_schema(raw_data, "ralph-config.schema.json")

    def validate_config_data(
        self,
        data: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """Validate configuration data without a file.

        Args:
            data: Configuration data dictionary.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        return validate_against_schema(data, "ralph-config.schema.json")

    # =========================================================================
    # Utility methods
    # =========================================================================

    def _deep_merge(
        self,
        base: Dict[str, Any],
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary.
            updates: Updates to apply.

        Returns:
            Merged dictionary.
        """
        result = base.copy()
        for key, value in updates.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _detect_changes(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        prefix: str = "",
    ) -> Dict[str, Any]:
        """Detect changes between two config dictionaries.

        Args:
            old_data: Old configuration.
            new_data: New configuration.
            prefix: Key prefix for nested detection.

        Returns:
            Dictionary of changes with old/new values.
        """
        changes: Dict[str, Any] = {}

        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val != new_val:
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    nested_changes = self._detect_changes(old_val, new_val, full_key)
                    changes.update(nested_changes)
                else:
                    changes[full_key] = {"old": old_val, "new": new_val}

        return changes

    def list_cached_configs(self) -> List[str]:
        """List all cached config paths.

        Returns:
            List of project paths with cached configs.
        """
        return list(self._configs.keys())
