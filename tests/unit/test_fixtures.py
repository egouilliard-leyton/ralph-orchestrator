"""
Unit tests for test fixtures.

These tests verify that the fixture repositories are correctly
structured and can be used for integration testing.
"""

import pytest
import json
import yaml
from pathlib import Path


class TestPythonMinFixture:
    """Tests for python_min fixture structure."""
    
    @pytest.fixture
    def fixture_path(self, fixtures_dir: Path) -> Path:
        """Get path to python_min fixture."""
        return fixtures_dir / "python_min"
    
    def test_pyproject_exists(self, fixture_path: Path):
        """pyproject.toml exists in fixture."""
        assert (fixture_path / "pyproject.toml").exists()
    
    def test_src_module_exists(self, fixture_path: Path):
        """src/main.py exists in fixture."""
        assert (fixture_path / "src" / "main.py").exists()
    
    def test_tests_exist(self, fixture_path: Path):
        """tests/test_main.py exists in fixture."""
        assert (fixture_path / "tests" / "test_main.py").exists()
    
    def test_ralph_config_exists(self, fixture_path: Path):
        """Ralph configuration exists."""
        assert (fixture_path / ".ralph" / "ralph.yml").exists()
    
    def test_prd_json_valid(self, fixture_path: Path):
        """prd.json is valid JSON with required fields."""
        prd_path = fixture_path / ".ralph" / "prd.json"
        assert prd_path.exists()
        
        prd = json.loads(prd_path.read_text())
        
        assert "project" in prd
        assert "tasks" in prd
        assert len(prd["tasks"]) >= 1
        
        for task in prd["tasks"]:
            assert "id" in task
            assert "title" in task
            assert "acceptanceCriteria" in task
            assert "passes" in task
    
    def test_ralph_config_valid(self, fixture_path: Path):
        """ralph.yml is valid YAML with required fields."""
        config_path = fixture_path / ".ralph" / "ralph.yml"
        
        config = yaml.safe_load(config_path.read_text())
        
        assert config["version"] == "1"
        assert "task_source" in config
        assert "gates" in config
        assert "git" in config


class TestNodeMinFixture:
    """Tests for node_min fixture structure."""
    
    @pytest.fixture
    def fixture_path(self, fixtures_dir: Path) -> Path:
        """Get path to node_min fixture."""
        return fixtures_dir / "node_min"
    
    def test_package_json_exists(self, fixture_path: Path):
        """package.json exists in fixture."""
        assert (fixture_path / "package.json").exists()
    
    def test_src_module_exists(self, fixture_path: Path):
        """src/index.js exists in fixture."""
        assert (fixture_path / "src" / "index.js").exists()
    
    def test_tests_exist(self, fixture_path: Path):
        """Test file exists in fixture."""
        assert (fixture_path / "src" / "index.test.js").exists()
    
    def test_package_json_valid(self, fixture_path: Path):
        """package.json is valid with required scripts."""
        pkg_path = fixture_path / "package.json"
        
        pkg = json.loads(pkg_path.read_text())
        
        assert "name" in pkg
        assert "scripts" in pkg
        assert "test" in pkg["scripts"]


class TestFullstackMinFixture:
    """Tests for fullstack_min fixture structure."""
    
    @pytest.fixture
    def fixture_path(self, fixtures_dir: Path) -> Path:
        """Get path to fullstack_min fixture."""
        return fixtures_dir / "fullstack_min"
    
    def test_backend_exists(self, fixture_path: Path):
        """Backend structure exists."""
        assert (fixture_path / "pyproject.toml").exists()
        assert (fixture_path / "src" / "api" / "main.py").exists()
    
    def test_frontend_exists(self, fixture_path: Path):
        """Frontend structure exists."""
        assert (fixture_path / "frontend" / "package.json").exists()
        assert (fixture_path / "frontend" / "src" / "App.tsx").exists()
    
    def test_config_has_services(self, fixture_path: Path):
        """Config has services section for backend/frontend."""
        config_path = fixture_path / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_path.read_text())
        
        assert "services" in config
        assert "backend" in config["services"]
        assert "frontend" in config["services"]


class TestAutopilotMinFixture:
    """Tests for autopilot_min fixture structure."""
    
    @pytest.fixture
    def fixture_path(self, fixtures_dir: Path) -> Path:
        """Get path to autopilot_min fixture."""
        return fixtures_dir / "autopilot_min"
    
    def test_reports_directory_exists(self, fixture_path: Path):
        """Reports directory exists with sample report."""
        reports_dir = fixture_path / "reports"
        assert reports_dir.exists()
        
        reports = list(reports_dir.glob("*.md"))
        assert len(reports) >= 1
    
    def test_config_has_autopilot(self, fixture_path: Path):
        """Config has autopilot section."""
        config_path = fixture_path / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_path.read_text())
        
        assert "autopilot" in config
        assert config["autopilot"]["enabled"] is True
        assert "reports_dir" in config["autopilot"]
    
    def test_report_has_issues(self, fixture_path: Path):
        """Sample report contains parseable issues."""
        report_path = fixture_path / "reports" / "weekly-report.md"
        content = report_path.read_text()
        
        # Should have issues section
        assert "Issue" in content or "issue" in content
        # Should have priority indicators
        assert "Priority" in content or "priority" in content
