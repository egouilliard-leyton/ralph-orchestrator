"""Unit tests for ConfigService."""

import pytest
import yaml
from pathlib import Path
from ralph_orchestrator.services.config_service import (
    ConfigService,
    ConfigSummary,
    ConfigValidationError,
)


@pytest.fixture
def temp_project_with_config(tmp_path):
    """Create a temporary project with config."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create .ralph directory
    ralph_dir = project_dir / ".ralph"
    ralph_dir.mkdir()
    
    # Create ralph.yml
    config_file = ralph_dir / "ralph.yml"
    config_data = {
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
            "build": [
                {"name": "lint", "cmd": "ruff check ."}
            ],
            "full": [
                {"name": "test", "cmd": "pytest"}
            ]
        },
        "test_paths": ["tests/"]
    }
    config_file.write_text(yaml.dump(config_data))
    
    return project_dir


@pytest.fixture
def config_service():
    """Create a ConfigService instance."""
    return ConfigService()


class TestConfigService:
    """Test ConfigService class."""

    def test_get_config_summary(self, config_service, temp_project_with_config):
        """Test getting config summary."""
        summary = config_service.get_config_summary(temp_project_with_config)
        
        assert summary is not None
        assert summary.version == "1"
        assert summary.task_source_type == "prd_json"
        assert summary.git_base_branch == "main"
        assert summary.gates_build_count == 1
        assert summary.gates_full_count == 1
        assert "tests/" in summary.test_paths

    def test_get_raw_config(self, config_service, temp_project_with_config):
        """Test getting raw config data."""
        config = config_service.get_raw_config(temp_project_with_config)
        
        assert config is not None
        assert config["version"] == "1"
        assert config["task_source"]["type"] == "prd_json"

    def test_validate_config_data_valid(self, config_service):
        """Test validating valid config data."""
        config_data = {
            "version": "1",
            "task_source": {
                "type": "prd_json",
                "path": ".ralph/prd.json"
            },
            "git": {
                "base_branch": "main"
            }
        }

        valid, errors = config_service.validate_config_data(config_data)
        
        assert valid is True
        assert len(errors) == 0

    def test_validate_config_data_invalid(self, config_service):
        """Test validating invalid config data."""
        config_data = {
            "version": "1.0",
            "task_source": {
                "type": "invalid_type",  # Invalid type
                "path": ".ralph/prd.json"
            }
        }
        
        valid, errors = config_service.validate_config_data(config_data)
        
        assert valid is False
        assert len(errors) > 0

    def test_update_config(self, config_service, temp_project_with_config):
        """Test updating config."""
        updates = {
            "git": {
                "base_branch": "develop"
            }
        }
        
        new_config = config_service.update_config(
            temp_project_with_config,
            updates,
            validate=True
        )
        
        assert new_config is not None
        # Config should be updated in file
        updated_summary = config_service.get_config_summary(temp_project_with_config)
        assert updated_summary.git_base_branch == "develop"

    def test_config_not_found(self, config_service, tmp_path):
        """Test getting config when file doesn't exist."""
        empty_project = tmp_path / "empty_project"
        empty_project.mkdir()
        
        summary = config_service.get_config_summary(empty_project)
        
        assert summary is None


class TestConfigSummary:
    """Test ConfigSummary dataclass."""

    def test_config_summary_creation(self):
        """Test creating ConfigSummary."""
        summary = ConfigSummary(
            config_path=Path("/test/.ralph/ralph.yml"),
            project_path=Path("/test"),
            version="1.0",
            task_source_type="prd_json",
            task_source_path=".ralph/prd.json",
            git_base_branch="main",
            git_remote="origin",
            gates_build_count=1,
            gates_full_count=2,
            test_paths=["tests/"],
            has_backend=False,
            has_frontend=False,
            autopilot_enabled=False
        )
        
        assert summary.version == "1.0"
        assert summary.task_source_type == "prd_json"
        assert summary.gates_build_count == 1
        assert summary.gates_full_count == 2
