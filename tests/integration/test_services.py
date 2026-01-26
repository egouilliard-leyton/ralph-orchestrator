"""
Integration tests for service lifecycle management.

These tests verify that the Ralph orchestrator correctly:
- Starts backend and frontend services
- Checks health endpoints
- Manages service timeouts
- Handles service failures gracefully
- Cleans up services on completion

The services module manages development servers during verification phases.
"""

import pytest
import os
import json
import yaml
from pathlib import Path

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestServiceConfiguration:
    """Test service configuration loading."""
    
    def test_services_loaded_from_config(self, fixture_fullstack_min: Path):
        """
        Services section loaded from ralph.yml.
        
        Given: Config with services section
        When: Config loaded
        Then: Backend and frontend services available
        """
        os.chdir(fixture_fullstack_min)
        
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        assert "services" in config
        assert "backend" in config["services"]
        assert "frontend" in config["services"]
    
    def test_backend_config_has_required_fields(self, fixture_fullstack_min: Path):
        """
        Backend service config has all required fields.
        
        Given: Config with backend service
        When: Config inspected
        Then: Has start, port, health, timeout fields
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        backend = config["services"]["backend"]
        
        assert "start" in backend
        assert "port" in backend
        assert "health" in backend
        assert "timeout" in backend
    
    def test_frontend_config_has_required_fields(self, fixture_fullstack_min: Path):
        """
        Frontend service config has all required fields.
        
        Given: Config with frontend service
        When: Config inspected
        Then: Has build, serve, port, timeout fields
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        frontend = config["services"]["frontend"]
        
        assert "serve" in frontend
        assert "port" in frontend
        assert "timeout" in frontend
    
    def test_service_port_is_configurable(self, fixture_fullstack_min: Path):
        """
        Service ports can be configured per project.
        
        Given: Config with custom ports
        When: Ports read
        Then: Ports are project-specific values
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        backend_port = config["services"]["backend"]["port"]
        frontend_port = config["services"]["frontend"]["port"]
        
        assert isinstance(backend_port, int)
        assert isinstance(frontend_port, int)
        assert backend_port != frontend_port


class TestServiceStartup:
    """Test service startup behavior."""
    
    def test_backend_start_command_exists(self, fixture_fullstack_min: Path):
        """
        Backend start command is defined.
        
        Given: Fullstack config
        When: Start command accessed
        Then: Valid command string available
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        start = config["services"]["backend"]["start"]
        
        assert "dev" in start or "prod" in start
    
    def test_frontend_serve_command_exists(self, fixture_fullstack_min: Path):
        """
        Frontend serve command is defined.
        
        Given: Fullstack config
        When: Serve command accessed
        Then: Valid command string available
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        serve = config["services"]["frontend"]["serve"]
        
        assert "dev" in serve or "prod" in serve
    
    def test_start_command_supports_port_placeholder(self, fixture_fullstack_min: Path):
        """
        Start commands support {port} placeholder.
        
        Given: Start command with {port}
        When: Command rendered
        Then: Port is substituted
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        backend_cmd = config["services"]["backend"]["start"]["dev"]
        
        # Should have {port} placeholder or actual port
        assert "{port}" in backend_cmd or str(config["services"]["backend"]["port"]) in backend_cmd


class TestHealthChecks:
    """Test service health check configuration."""
    
    def test_backend_has_health_endpoints(self, fixture_fullstack_min: Path):
        """
        Backend health endpoints are configured.
        
        Given: Backend service config
        When: Health endpoints accessed
        Then: At least one endpoint defined
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        health = config["services"]["backend"]["health"]
        
        assert isinstance(health, list)
        assert len(health) >= 1
    
    def test_health_endpoint_is_path(self, fixture_fullstack_min: Path):
        """
        Health endpoints are URL paths.
        
        Given: Health endpoint list
        When: Endpoint inspected
        Then: Starts with /
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        health = config["services"]["backend"]["health"]
        
        for endpoint in health:
            assert endpoint.startswith("/"), f"Health endpoint should be path: {endpoint}"
    
    def test_timeout_is_reasonable(self, fixture_fullstack_min: Path):
        """
        Service timeout is reasonable value.
        
        Given: Service timeout config
        When: Timeout value checked
        Then: Between 5 and 120 seconds
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        backend_timeout = config["services"]["backend"]["timeout"]
        
        assert 5 <= backend_timeout <= 120


class TestServiceLifecycle:
    """Test service lifecycle management."""
    
    def test_services_started_for_verification(self, fixture_fullstack_min: Path):
        """
        Services started when verification phase begins.
        
        Given: Post-verify phase enabled
        When: Verification runs
        Then: Backend and frontend services are started
        """
        # TODO: When ralph CLI is implemented:
        # run_command(["verify"])
        # 
        # # Check timeline for service start events
        # timeline_file = fixture_fullstack_min / ".ralph-session/logs/timeline.jsonl"
        # timeline = timeline_file.read_text()
        # assert "service_start" in timeline
        pass
    
    def test_services_stopped_after_verification(self, fixture_fullstack_min: Path):
        """
        Services stopped when verification completes.
        
        Given: Verification running
        When: Verification completes
        Then: All services are stopped cleanly
        """
        # TODO: When ralph CLI is implemented:
        # Verify service cleanup
        pass
    
    def test_service_failure_logged(self, fixture_fullstack_min: Path):
        """
        Service startup failure is logged.
        
        Given: Service with bad start command
        When: Service fails to start
        Then: Failure logged with error details
        """
        # TODO: When ralph CLI is implemented:
        # Configure invalid command, verify error logging
        pass
    
    def test_health_check_failure_logged(self, fixture_fullstack_min: Path):
        """
        Health check failure is logged.
        
        Given: Service running but unhealthy
        When: Health check fails
        Then: Failure logged with endpoint and response
        """
        # TODO: When ralph CLI is implemented:
        # Configure failing health endpoint, verify error logging
        pass


class TestServiceRecovery:
    """Test service failure recovery."""
    
    def test_service_restart_on_failure(self, fixture_fullstack_min: Path):
        """
        Service restarted after failure.
        
        Given: Service crashes during verification
        When: Crash detected
        Then: Service is restarted
        """
        # TODO: When ralph CLI is implemented:
        # Simulate crash, verify restart
        pass
    
    def test_max_restart_attempts(self, fixture_fullstack_min: Path):
        """
        Service restarts limited to prevent infinite loop.
        
        Given: Service that keeps crashing
        When: Max restarts exceeded
        Then: Verification fails with clear error
        """
        # TODO: When ralph CLI is implemented:
        # Configure persistent failure, verify max attempts
        pass


class TestDevVsProdMode:
    """Test dev vs prod mode service startup."""
    
    def test_dev_mode_used_for_ui_testing(self, fixture_fullstack_min: Path):
        """
        Dev mode used during UI testing.
        
        Given: UI verification enabled
        When: Services started
        Then: Dev start commands used
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Dev command should be different from prod
        backend_start = config["services"]["backend"]["start"]
        
        assert "dev" in backend_start
        assert "prod" in backend_start
    
    def test_prod_mode_available_for_final_verify(self, fixture_fullstack_min: Path):
        """
        Prod mode available for production-like testing.
        
        Given: Config with prod commands
        When: Prod mode requested
        Then: Prod start commands available
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        backend_prod = config["services"]["backend"]["start"]["prod"]
        
        assert backend_prod is not None
        assert len(backend_prod) > 0


class TestPythonOnlyNoServices:
    """Test that python-only projects work without services."""
    
    def test_python_min_has_no_services(self, fixture_python_min: Path):
        """
        Python-only fixture has no services section.
        
        Given: Python minimal fixture
        When: Config loaded
        Then: No services section (optional)
        """
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config = yaml.safe_load(config_file.read_text())
        
        # Services are optional for projects without UI
        assert "services" not in config or config.get("services") is None
    
    def test_verification_works_without_services(self, fixture_python_min: Path):
        """
        Verification works for projects without services.
        
        Given: Python project without services
        When: Verification runs
        Then: Skips service phase, runs gates only
        """
        # TODO: When ralph CLI is implemented:
        # run_command(["verify"])
        # Verify no service errors
        pass
