"""Unit tests for ConfigService.

Tests the configuration management service including:
- Config CRUD operations
- Validation against JSON schema
- Event emission
- Cache management
"""

import json
import pytest
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

import yaml

from ralph_orchestrator.services.config_service import (
    ConfigService,
    ConfigSummary,
    ConfigEventType,
    ConfigLoadedEvent,
    ConfigUpdatedEvent,
    ConfigCreatedEvent,
    ConfigDeletedEvent,
    ConfigValidationFailedEvent,
    ConfigReloadedEvent,
    ConfigValidationError,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a minimal Ralph project structure with config."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    # Create .ralph directory
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir()

    # Create ralph.yml
    config_data = {
        "version": "1",
        "task_source": {
            "type": "prd_json",
            "path": ".ralph/prd.json",
        },
        "git": {
            "base_branch": "main",
            "remote": "origin",
        },
        "gates": {
            "build": [
                {"name": "lint", "cmd": "ruff check ."},
            ],
            "full": [
                {"name": "test", "cmd": "pytest"},
            ],
        },
        "test_paths": ["tests/**", "**/*.test.*"],
    }

    config_path = ralph_dir / "ralph.yml"
    config_path.write_text(yaml.dump(config_data))

    return project_path


@pytest.fixture
def temp_project_no_config(tmp_path: Path) -> Path:
    """Create a project structure without config."""
    project_path = tmp_path / "no_config_project"
    project_path.mkdir()
    (project_path / ".ralph").mkdir()
    return project_path


class TestConfigServiceCreate:
    """Tests for config creation."""

    def test_create_config(self, temp_project_no_config: Path):
        """Test creating a new config file."""
        service = ConfigService()

        config = service.create_config(
            temp_project_no_config,
            task_source_type="prd_json",
            task_source_path=".ralph/prd.json",
            git_base_branch="main",
        )

        assert config is not None
        assert config.version == "1"
        assert config.task_source_type == "prd_json"

        # Verify file was created
        config_path = temp_project_no_config / ".ralph" / "ralph.yml"
        assert config_path.exists()

    def test_create_config_already_exists(self, temp_project: Path):
        """Test that creating config when one exists raises error."""
        service = ConfigService()

        with pytest.raises(FileExistsError):
            service.create_config(temp_project)

    def test_create_config_with_custom_gates(self, temp_project_no_config: Path):
        """Test creating config with custom gates."""
        service = ConfigService()

        config = service.create_config(
            temp_project_no_config,
            gates_build=[{"name": "lint", "cmd": "eslint ."}],
            gates_full=[
                {"name": "test", "cmd": "jest"},
                {"name": "build", "cmd": "npm run build"},
            ],
        )

        assert len(config.gates_build) == 1
        assert len(config.gates_full) == 2
        assert config.gates_build[0].name == "lint"

    def test_create_config_emits_event(self, temp_project_no_config: Path):
        """Test that creating config emits event."""
        events: List[ConfigCreatedEvent] = []

        def handler(event):
            if isinstance(event, ConfigCreatedEvent):
                events.append(event)

        service = ConfigService()
        service.on_event(ConfigEventType.CONFIG_CREATED, handler)
        service.create_config(temp_project_no_config)

        assert len(events) == 1
        assert str(temp_project_no_config) in events[0].project_path

    def test_create_config_validates(self, temp_project_no_config: Path):
        """Test that invalid config data raises validation error."""
        service = ConfigService()

        # Missing required git field causes validation to fail
        # We need to mock validate_against_schema to force failure
        with patch(
            "ralph_orchestrator.services.config_service.validate_against_schema"
        ) as mock_validate:
            mock_validate.return_value = (False, ["version: 'invalid' is not valid"])

            with pytest.raises(ConfigValidationError) as exc_info:
                service.create_config(temp_project_no_config)

            assert "validation failed" in str(exc_info.value).lower()


class TestConfigServiceRead:
    """Tests for config reading."""

    def test_load_config(self, temp_project: Path):
        """Test loading a config file."""
        service = ConfigService()

        config = service.load_config(temp_project)

        assert config is not None
        assert config.version == "1"
        assert config.task_source_type == "prd_json"
        assert config.git.base_branch == "main"

    def test_load_config_not_found(self, temp_project_no_config: Path):
        """Test loading non-existent config raises error."""
        service = ConfigService()

        with pytest.raises(FileNotFoundError):
            service.load_config(temp_project_no_config)

    def test_load_config_caches(self, temp_project: Path):
        """Test that loaded config is cached."""
        service = ConfigService()

        config1 = service.load_config(temp_project)
        config2 = service.load_config(temp_project)

        # Should return same cached instance
        assert config1 is config2

    def test_load_config_force_reload(self, temp_project: Path):
        """Test force reload ignores cache."""
        service = ConfigService()

        config1 = service.load_config(temp_project)

        # Modify config file
        config_path = temp_project / ".ralph" / "ralph.yml"
        data = yaml.safe_load(config_path.read_text())
        data["git"]["base_branch"] = "develop"
        config_path.write_text(yaml.dump(data))

        # Without force_reload, returns cached version
        config2 = service.load_config(temp_project)
        assert config2.git.base_branch == "main"

        # With force_reload, returns updated version
        config3 = service.load_config(temp_project, force_reload=True)
        assert config3.git.base_branch == "develop"

    def test_load_config_emits_event(self, temp_project: Path):
        """Test that loading config emits event."""
        events: List[ConfigLoadedEvent] = []

        def handler(event):
            if isinstance(event, ConfigLoadedEvent):
                events.append(event)

        service = ConfigService()
        service.on_event(ConfigEventType.CONFIG_LOADED, handler)
        service.load_config(temp_project)

        assert len(events) == 1
        assert events[0].version == "1"

    def test_get_config_no_load(self, temp_project: Path):
        """Test get_config returns None if not loaded."""
        service = ConfigService()

        config = service.get_config(temp_project)
        assert config is None

        # Load it first
        service.load_config(temp_project)

        # Now it should return the cached config
        config = service.get_config(temp_project)
        assert config is not None

    def test_config_exists(self, temp_project: Path, temp_project_no_config: Path):
        """Test checking if config exists."""
        service = ConfigService()

        assert service.config_exists(temp_project) is True
        assert service.config_exists(temp_project_no_config) is False

    def test_get_config_summary(self, temp_project: Path):
        """Test getting config summary."""
        service = ConfigService()

        summary = service.get_config_summary(temp_project)

        assert summary is not None
        assert summary.version == "1"
        assert summary.task_source_type == "prd_json"
        assert summary.git_base_branch == "main"
        assert summary.gates_build_count == 1
        assert summary.gates_full_count == 1

    def test_get_config_summary_not_found(self, temp_project_no_config: Path):
        """Test getting summary for missing config returns None."""
        service = ConfigService()

        summary = service.get_config_summary(temp_project_no_config)
        assert summary is None

    def test_get_raw_config(self, temp_project: Path):
        """Test getting raw config data."""
        service = ConfigService()

        raw = service.get_raw_config(temp_project)

        assert raw is not None
        assert raw["version"] == "1"
        assert raw["git"]["base_branch"] == "main"


class TestConfigServiceUpdate:
    """Tests for config updates."""

    def test_update_config(self, temp_project: Path):
        """Test updating config."""
        service = ConfigService()

        config = service.update_config(temp_project, {
            "git": {"base_branch": "develop"},
        })

        assert config.git.base_branch == "develop"

        # Verify file was updated
        config_path = temp_project / ".ralph" / "ralph.yml"
        data = yaml.safe_load(config_path.read_text())
        assert data["git"]["base_branch"] == "develop"

    def test_update_config_deep_merge(self, temp_project: Path):
        """Test that updates are deep merged."""
        service = ConfigService()

        # Update only one field in git
        config = service.update_config(temp_project, {
            "git": {"remote": "upstream"},
        })

        # base_branch should be preserved
        assert config.git.base_branch == "main"
        assert config.git.remote == "upstream"

    def test_update_config_emits_event(self, temp_project: Path):
        """Test that updating config emits event."""
        events: List[ConfigUpdatedEvent] = []

        def handler(event):
            if isinstance(event, ConfigUpdatedEvent):
                events.append(event)

        service = ConfigService()
        service.on_event(ConfigEventType.CONFIG_UPDATED, handler)
        service.update_config(temp_project, {"git": {"base_branch": "develop"}})

        assert len(events) == 1
        assert "git.base_branch" in events[0].changes
        assert events[0].changes["git.base_branch"]["old"] == "main"
        assert events[0].changes["git.base_branch"]["new"] == "develop"

    def test_update_task_source(self, temp_project: Path):
        """Test updating task source."""
        service = ConfigService()

        config = service.update_task_source(
            temp_project,
            source_type="cr_markdown",
            source_path="./tasks/*.md",
        )

        assert config.task_source_type == "cr_markdown"
        assert config.task_source_path == "./tasks/*.md"

    def test_update_git(self, temp_project: Path):
        """Test updating git config."""
        service = ConfigService()

        config = service.update_git(
            temp_project,
            base_branch="develop",
            remote="upstream",
        )

        assert config.git.base_branch == "develop"
        assert config.git.remote == "upstream"

    def test_update_gates(self, temp_project: Path):
        """Test updating gates."""
        service = ConfigService()

        config = service.update_gates(
            temp_project,
            full=[
                {"name": "test", "cmd": "pytest -v"},
                {"name": "typecheck", "cmd": "mypy ."},
            ],
        )

        assert len(config.gates_full) == 2
        assert config.gates_full[0].cmd == "pytest -v"
        assert config.gates_full[1].name == "typecheck"

    def test_add_gate(self, temp_project: Path):
        """Test adding a gate."""
        service = ConfigService()

        config = service.add_gate(
            temp_project,
            gate_type="build",
            name="typecheck",
            cmd="mypy .",
        )

        assert len(config.gates_build) == 2
        gate_names = [g.name for g in config.gates_build]
        assert "lint" in gate_names
        assert "typecheck" in gate_names

    def test_remove_gate(self, temp_project: Path):
        """Test removing a gate."""
        service = ConfigService()

        config = service.remove_gate(
            temp_project,
            gate_type="build",
            name="lint",
        )

        assert len(config.gates_build) == 0

    def test_update_test_paths(self, temp_project: Path):
        """Test updating test paths."""
        service = ConfigService()

        config = service.update_test_paths(
            temp_project,
            test_paths=["tests/**", "src/**/*.spec.ts"],
        )

        assert len(config.test_paths) == 2
        assert "src/**/*.spec.ts" in config.test_paths

    def test_update_limits(self, temp_project: Path):
        """Test updating limits."""
        service = ConfigService()

        config = service.update_limits(
            temp_project,
            claude_timeout=3600,
            max_iterations=100,
        )

        assert config.limits.claude_timeout == 3600
        assert config.limits.max_iterations == 100

    def test_update_autopilot(self, temp_project: Path):
        """Test updating autopilot config."""
        service = ConfigService()

        config = service.update_autopilot(
            temp_project,
            enabled=True,
            branch_prefix="feature/",
        )

        assert config.autopilot.enabled is True
        assert config.autopilot.branch_prefix == "feature/"

    def test_reload_config(self, temp_project: Path):
        """Test reloading config from disk."""
        service = ConfigService()

        # Load initial config
        service.load_config(temp_project)

        # Modify file directly
        config_path = temp_project / ".ralph" / "ralph.yml"
        data = yaml.safe_load(config_path.read_text())
        data["git"]["base_branch"] = "develop"
        config_path.write_text(yaml.dump(data))

        # Reload
        config = service.reload_config(temp_project)

        assert config.git.base_branch == "develop"

    def test_reload_config_emits_event(self, temp_project: Path):
        """Test that reloading emits event."""
        events: List[ConfigReloadedEvent] = []

        def handler(event):
            if isinstance(event, ConfigReloadedEvent):
                events.append(event)

        service = ConfigService()
        service.load_config(temp_project)
        service.on_event(ConfigEventType.CONFIG_RELOADED, handler)

        # Modify and reload
        config_path = temp_project / ".ralph" / "ralph.yml"
        data = yaml.safe_load(config_path.read_text())
        data["git"]["base_branch"] = "develop"
        config_path.write_text(yaml.dump(data))

        service.reload_config(temp_project)

        assert len(events) == 1
        assert events[0].changed is True


class TestConfigServiceDelete:
    """Tests for config deletion."""

    def test_delete_config(self, temp_project: Path):
        """Test deleting config."""
        service = ConfigService()

        # Load first
        service.load_config(temp_project)

        result = service.delete_config(temp_project)

        assert result is True
        assert not (temp_project / ".ralph" / "ralph.yml").exists()

    def test_delete_config_clears_cache(self, temp_project: Path):
        """Test that deletion clears cache."""
        service = ConfigService()

        service.load_config(temp_project)
        assert service.get_config(temp_project) is not None

        service.delete_config(temp_project)

        assert service.get_config(temp_project) is None

    def test_delete_config_emits_event(self, temp_project: Path):
        """Test that deletion emits event."""
        events: List[ConfigDeletedEvent] = []

        def handler(event):
            if isinstance(event, ConfigDeletedEvent):
                events.append(event)

        service = ConfigService()
        service.on_event(ConfigEventType.CONFIG_DELETED, handler)
        service.delete_config(temp_project)

        assert len(events) == 1

    def test_delete_config_not_found(self, temp_project_no_config: Path):
        """Test deleting non-existent config returns False."""
        service = ConfigService()

        result = service.delete_config(temp_project_no_config)

        assert result is False


class TestConfigServiceValidation:
    """Tests for config validation."""

    def test_validate_config(self, temp_project: Path):
        """Test validating config file."""
        service = ConfigService()

        valid, errors = service.validate_config(temp_project)

        assert valid is True
        assert len(errors) == 0

    def test_validate_config_not_found(self, temp_project_no_config: Path):
        """Test validating non-existent config."""
        service = ConfigService()

        valid, errors = service.validate_config(temp_project_no_config)

        assert valid is False
        assert len(errors) > 0
        assert "not found" in errors[0].lower()

    def test_validate_config_invalid_yaml(self, tmp_path: Path):
        """Test validating invalid YAML."""
        project = tmp_path / "invalid_yaml"
        project.mkdir()
        ralph_dir = project / ".ralph"
        ralph_dir.mkdir()

        config_path = ralph_dir / "ralph.yml"
        config_path.write_text("invalid: yaml: content:")

        service = ConfigService()
        valid, errors = service.validate_config(project)

        assert valid is False
        assert "yaml" in errors[0].lower() or "parse" in errors[0].lower()

    def test_validate_config_data(self):
        """Test validating config data directly."""
        service = ConfigService()

        valid_data = {
            "version": "1",
            "task_source": {"type": "prd_json", "path": ".ralph/prd.json"},
            "git": {"base_branch": "main"},
            "gates": {"full": []},
        }

        valid, errors = service.validate_config_data(valid_data)
        assert valid is True

        invalid_data = {"version": "2"}  # Invalid version
        valid, errors = service.validate_config_data(invalid_data)
        assert valid is False


class TestConfigServiceEvents:
    """Tests for event handling."""

    def test_on_all_events(self, temp_project: Path):
        """Test global event handler."""
        events = []

        def handler(event):
            events.append(event)

        service = ConfigService()
        service.on_all_events(handler)
        service.load_config(temp_project)

        assert len(events) >= 1
        event_types = {e.event_type for e in events}
        assert ConfigEventType.CONFIG_LOADED in event_types

    def test_remove_handler(self, temp_project: Path):
        """Test removing event handler."""
        events = []

        def handler(event):
            events.append(event)

        service = ConfigService()
        service.on_event(ConfigEventType.CONFIG_LOADED, handler)
        service.remove_handler(ConfigEventType.CONFIG_LOADED, handler)
        service.load_config(temp_project)

        # Handler should not be called
        loaded_events = [e for e in events if e.event_type == ConfigEventType.CONFIG_LOADED]
        assert len(loaded_events) == 0

    def test_validation_failed_event(self, temp_project: Path):
        """Test that validation failure emits event."""
        events: List[ConfigValidationFailedEvent] = []

        def handler(event):
            if isinstance(event, ConfigValidationFailedEvent):
                events.append(event)

        service = ConfigService()
        service.on_event(ConfigEventType.CONFIG_VALIDATION_FAILED, handler)

        # Mock validation to fail
        with patch(
            "ralph_orchestrator.services.config_service.validate_against_schema"
        ) as mock_validate:
            mock_validate.return_value = (False, ["Invalid config"])

            try:
                service.update_config(temp_project, {"invalid": "data"})
            except ConfigValidationError:
                pass

        assert len(events) == 1
        assert "Invalid config" in events[0].errors


class TestConfigServiceCache:
    """Tests for cache management."""

    def test_clear_cache(self, temp_project: Path):
        """Test clearing cache."""
        service = ConfigService()

        service.load_config(temp_project)
        assert service.get_config(temp_project) is not None

        service.clear_cache()

        assert service.get_config(temp_project) is None

    def test_list_cached_configs(self, tmp_path: Path):
        """Test listing cached configs."""
        service = ConfigService()

        # Create two projects
        projects = []
        for name in ["proj1", "proj2"]:
            proj = tmp_path / name
            proj.mkdir()
            ralph_dir = proj / ".ralph"
            ralph_dir.mkdir()
            config_path = ralph_dir / "ralph.yml"
            config_path.write_text(yaml.dump({
                "version": "1",
                "task_source": {"type": "prd_json", "path": ".ralph/prd.json"},
                "git": {"base_branch": "main"},
                "gates": {"full": []},
            }))
            projects.append(proj)

        # Load both
        for proj in projects:
            service.load_config(proj)

        cached = service.list_cached_configs()
        assert len(cached) == 2


class TestConfigSummary:
    """Tests for ConfigSummary dataclass."""

    def test_to_dict(self, temp_project: Path):
        """Test ConfigSummary serialization."""
        service = ConfigService()
        summary = service.get_config_summary(temp_project)

        d = summary.to_dict()

        assert d["version"] == "1"
        assert d["task_source_type"] == "prd_json"
        assert d["git_base_branch"] == "main"
        assert isinstance(d["test_paths"], list)


class TestConfigEventDataclasses:
    """Tests for event dataclass serialization."""

    def test_config_loaded_event_to_dict(self):
        """Test ConfigLoadedEvent serialization."""
        event = ConfigLoadedEvent(
            project_path="/path/to/project",
            config_path="/path/to/project/.ralph/ralph.yml",
            version="1",
        )

        d = event.to_dict()

        assert d["event_type"] == "config_loaded"
        assert d["config_path"] == "/path/to/project/.ralph/ralph.yml"
        assert d["version"] == "1"
        assert "timestamp" in d

    def test_config_updated_event_to_dict(self):
        """Test ConfigUpdatedEvent serialization."""
        event = ConfigUpdatedEvent(
            project_path="/path",
            config_path="/path/.ralph/ralph.yml",
            changes={"git.base_branch": {"old": "main", "new": "develop"}},
        )

        d = event.to_dict()

        assert d["event_type"] == "config_updated"
        assert "git.base_branch" in d["changes"]

    def test_config_validation_failed_event_to_dict(self):
        """Test ConfigValidationFailedEvent serialization."""
        event = ConfigValidationFailedEvent(
            project_path="/path",
            config_path="/path/.ralph/ralph.yml",
            errors=["Error 1", "Error 2"],
        )

        d = event.to_dict()

        assert d["event_type"] == "config_validation_failed"
        assert len(d["errors"]) == 2


class TestConfigServiceEdgeCases:
    """Tests for edge cases."""

    def test_update_config_not_found(self, temp_project_no_config: Path):
        """Test updating non-existent config."""
        service = ConfigService()

        with pytest.raises(FileNotFoundError):
            service.update_config(temp_project_no_config, {})

    def test_deep_merge_nested_dicts(self):
        """Test deep merge with nested dictionaries."""
        service = ConfigService()

        base = {
            "level1": {
                "level2": {
                    "a": 1,
                    "b": 2,
                },
                "keep": "this",
            },
        }

        updates = {
            "level1": {
                "level2": {
                    "b": 3,
                    "c": 4,
                },
            },
        }

        result = service._deep_merge(base, updates)

        assert result["level1"]["level2"]["a"] == 1  # Preserved
        assert result["level1"]["level2"]["b"] == 3  # Updated
        assert result["level1"]["level2"]["c"] == 4  # Added
        assert result["level1"]["keep"] == "this"  # Preserved

    def test_detect_changes(self):
        """Test change detection."""
        service = ConfigService()

        old = {"a": 1, "b": {"c": 2, "d": 3}}
        new = {"a": 1, "b": {"c": 2, "d": 4}, "e": 5}

        changes = service._detect_changes(old, new)

        assert "b.d" in changes
        assert changes["b.d"]["old"] == 3
        assert changes["b.d"]["new"] == 4
        assert "e" in changes

    def test_load_config_with_string_path(self, temp_project: Path):
        """Test loading config with string path."""
        service = ConfigService()

        config = service.load_config(str(temp_project))

        assert config is not None
        assert config.version == "1"
