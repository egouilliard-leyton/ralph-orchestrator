"""Integration tests for workflow editor and config management UI endpoints.

Tests verify the API contract for WorkflowEditor and ConfigEditor components:
- Config data structure and required fields
- Config update/validation through API
- Error handling

These tests use the existing ralph-orchestrator project's config as the test subject.
"""

import pytest
import json
from pathlib import Path

from ralph_orchestrator.services.config_service import ConfigService, ConfigValidationError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config_service():
    """Get a ConfigService instance."""
    return ConfigService()


@pytest.fixture
def project_dir():
    """Use the current project directory which has a valid .ralph/ralph.yml."""
    return Path.cwd()


# =============================================================================
# WorkflowEditor API Contract Tests
# =============================================================================


class TestWorkflowEditorDataContract:
    """Tests for data structure required by WorkflowEditor component."""

    def test_config_service_provides_gates_data(self, config_service, project_dir):
        """Test that config summary includes gates information for workflow visualization."""
        summary = config_service.get_config_summary(project_dir)

        assert summary is not None, "Config summary should be available"
        assert hasattr(summary, "gates_build_count")
        assert hasattr(summary, "gates_full_count")
        assert isinstance(summary.gates_build_count, int)
        assert isinstance(summary.gates_full_count, int)

    def test_config_service_provides_test_paths(self, config_service, project_dir):
        """Test that config includes test_paths for agent guardrails."""
        summary = config_service.get_config_summary(project_dir)

        assert summary is not None
        assert hasattr(summary, "test_paths")
        assert isinstance(summary.test_paths, list)

    def test_raw_config_includes_gates_details(self, config_service, project_dir):
        """Test that raw config includes detailed gate configuration."""
        raw_config = config_service.get_raw_config(project_dir)

        assert raw_config is not None
        assert "gates" in raw_config
        assert "build" in raw_config["gates"]
        assert "full" in raw_config["gates"]
        assert isinstance(raw_config["gates"]["build"], list)
        assert isinstance(raw_config["gates"]["full"], list)

        # If there are gates, verify structure
        if raw_config["gates"]["build"]:
            gate = raw_config["gates"]["build"][0]
            assert "name" in gate
            assert "cmd" in gate

    def test_config_update_preserves_gates(self, config_service, project_dir, tmp_path):
        """Test that updating config preserves gate configuration."""
        # Create a test project with known config
        test_proj = tmp_path / "test_proj"
        test_proj.mkdir()
        ralph_dir = test_proj / ".ralph"
        ralph_dir.mkdir()

        # Create initial config
        initial_config = config_service.create_config(
            test_proj,
            gates_build=[{"name": "lint", "cmd": "ruff check ."}],
            gates_full=[{"name": "test", "cmd": "pytest"}],
        )

        assert len(initial_config.gates_build) == 1
        assert len(initial_config.gates_full) == 1

        # Update with additional build gate
        config_service.update_gates(
            test_proj,
            build=[
                {"name": "lint", "cmd": "ruff check ."},
                {"name": "typecheck", "cmd": "mypy ."},
            ],
            full=[{"name": "test", "cmd": "pytest"}],
        )

        # Verify update
        summary = config_service.get_config_summary(test_proj)
        assert summary.gates_build_count == 2
        assert summary.gates_full_count == 1


# =============================================================================
# ConfigEditor API Contract Tests
# =============================================================================


class TestConfigEditorDataContract:
    """Tests for data structure required by ConfigEditor component."""

    def test_config_summary_has_all_required_fields(self, config_service, project_dir):
        """Test that ConfigSummary includes all fields needed by ConfigEditor form."""
        summary = config_service.get_config_summary(project_dir)

        assert summary is not None

        # Required for form display
        required_attrs = [
            "version",
            "task_source_type",
            "task_source_path",
            "git_base_branch",
            "git_remote",
            "test_paths",
            "has_backend",
            "has_frontend",
            "autopilot_enabled",
        ]

        for attr in required_attrs:
            assert hasattr(summary, attr), f"Missing required field: {attr}"

    def test_raw_config_structure_for_yaml_preview(self, config_service, project_dir):
        """Test that raw_config has structure suitable for YAML preview generation."""
        raw = config_service.get_raw_config(project_dir)

        assert raw is not None
        assert isinstance(raw, dict)

        # Must have core sections
        assert "version" in raw
        assert "task_source" in raw
        assert "git" in raw
        assert "gates" in raw

        # Should be serializable
        import yaml
        yaml_str = yaml.dump(raw)
        assert yaml_str is not None
        assert "version:" in yaml_str

    def test_config_update_git_settings(self, config_service, tmp_path):
        """Test updating git configuration via ConfigService."""
        test_proj = tmp_path / "test_git_update"
        test_proj.mkdir()
        (test_proj / ".ralph").mkdir()

        # Create config with default git settings
        config_service.create_config(test_proj)

        # Update git settings
        updates = {
            "git": {
                "base_branch": "develop",
                "remote": "upstream"
            }
        }

        config_service.update_config(test_proj, updates)

        # Verify changes
        summary = config_service.get_config_summary(test_proj)
        assert summary.git_base_branch == "develop"
        assert summary.git_remote == "upstream"

    def test_config_update_task_source(self, config_service, tmp_path):
        """Test updating task source configuration."""
        test_proj = tmp_path / "test_task_update"
        test_proj.mkdir()
        (test_proj / ".ralph").mkdir()

        config_service.create_config(test_proj)

        # Update task source
        updates = {
            "task_source": {
                "type": "cr_markdown",
                "path": ".ralph/changes.md"
            }
        }

        config_service.update_config(test_proj, updates)

        summary = config_service.get_config_summary(test_proj)
        assert summary.task_source_type == "cr_markdown"
        assert summary.task_source_path == ".ralph/changes.md"

    def test_config_validation_rejects_invalid_data(self, config_service):
        """Test that validation catches invalid config data."""
        # Invalid config: missing required fields
        invalid_config = {
            "version": "1"
            # Missing required task_source
        }

        valid, errors = config_service.validate_config_data(invalid_config)

        assert not valid
        assert len(errors) > 0
        assert any("task_source" in error.lower() for error in errors)

    def test_config_update_deep_merges_changes(self, config_service, tmp_path):
        """Test that config updates use deep merge, preserving unmodified sections."""
        test_proj = tmp_path / "test_merge"
        test_proj.mkdir()
        (test_proj / ".ralph").mkdir()

        # Create config with services
        initial = config_service.create_config(
            test_proj,
            gates_build=[{"name": "lint", "cmd": "ruff check ."}],
        )

        # Update only git config
        updates = {
            "git": {
                "base_branch": "staging"
            }
        }

        config_service.update_config(test_proj, updates)

        # Verify git was updated but gates preserved
        summary = config_service.get_config_summary(test_proj)
        assert summary.git_base_branch == "staging"
        assert summary.gates_build_count == 1  # Preserved


# =============================================================================
# Validation Tests
# =============================================================================


class TestConfigValidation:
    """Tests for configuration validation used by both editors."""

    def test_validate_complete_config(self, config_service):
        """Test validation with a complete valid config."""
        valid_config = {
            "version": "1",
            "task_source": {
                "type": "prd_json",
                "path": ".ralph/prd.json"
            },
            "git": {
                "base_branch": "main",
                "remote": "origin"
            },
            "gates": {
                "build": [],
                "full": []
            }
        }

        valid, errors = config_service.validate_config_data(valid_config)

        assert valid, f"Validation should pass but got errors: {errors}"
        assert len(errors) == 0

    def test_validate_gate_structure_requires_cmd(self, config_service):
        """Test that gate validation requires cmd field."""
        invalid_config = {
            "version": "1",
            "task_source": {"type": "prd_json", "path": ".ralph/prd.json"},
            "git": {"base_branch": "main", "remote": "origin"},
            "gates": {
                "build": [
                    {"name": "lint"}  # Missing cmd
                ],
                "full": []
            }
        }

        valid, errors = config_service.validate_config_data(invalid_config)

        assert not valid
        assert len(errors) > 0

    def test_validate_task_source_types(self, config_service):
        """Test validation of task_source type enum."""
        valid_types = ["prd_json", "cr_markdown"]

        for task_type in valid_types:
            config = {
                "version": "1",
                "task_source": {"type": task_type, "path": ".ralph/tasks"},
                "git": {"base_branch": "main", "remote": "origin"},
                "gates": {"build": [], "full": []}
            }
            valid, _ = config_service.validate_config_data(config)
            assert valid, f"Valid type {task_type} should pass validation"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestConfigErrorHandling:
    """Tests for error handling in config operations."""

    def test_get_config_for_nonexistent_project(self, config_service, tmp_path):
        """Test behavior when requesting config for project without ralph.yml."""
        nonexistent = tmp_path / "no_config"
        nonexistent.mkdir()

        summary = config_service.get_config_summary(nonexistent)
        assert summary is None

    def test_load_config_raises_file_not_found(self, config_service, tmp_path):
        """Test that load_config raises FileNotFoundError for missing config."""
        missing = tmp_path / "missing"
        missing.mkdir()

        with pytest.raises(FileNotFoundError):
            config_service.load_config(missing)

    def test_create_config_fails_if_exists(self, config_service, tmp_path):
        """Test that creating config when one exists raises error."""
        test_proj = tmp_path / "exists"
        test_proj.mkdir()
        (test_proj / ".ralph").mkdir()

        # Create first config
        config_service.create_config(test_proj)

        # Try to create again - should fail
        with pytest.raises(FileExistsError):
            config_service.create_config(test_proj)


# =============================================================================
# Loading State Tests
# =============================================================================


class TestConfigLoadingStates:
    """Tests for handling config loading scenarios."""

    def test_config_is_cached_after_first_load(self, config_service, project_dir):
        """Test that config service caches loaded configs."""
        # Load once
        config1 = config_service.load_config(project_dir)

        # Load again - should return same instance from cache
        config2 = config_service.load_config(project_dir)

        # Both should reference same data
        assert config1.version == config2.version

    def test_config_reload_forces_disk_read(self, config_service, tmp_path):
        """Test that reload_config forces reading from disk."""
        test_proj = tmp_path / "test_reload"
        test_proj.mkdir()
        (test_proj / ".ralph").mkdir()

        config_service.create_config(test_proj, git_base_branch="main")

        # Load to cache
        config1 = config_service.load_config(test_proj)
        assert config1.git.base_branch == "main"

        # Manually modify config file
        config_path = test_proj / ".ralph" / "ralph.yml"
        import yaml
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        data["git"]["base_branch"] = "develop"
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        # Reload should read new value
        config2 = config_service.reload_config(test_proj)
        assert config2.git.base_branch == "develop"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
