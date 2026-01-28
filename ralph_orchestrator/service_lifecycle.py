"""Service lifecycle management for Ralph orchestrator.

Handles starting, stopping, and health checking of backend and frontend
services for runtime verification.

Provides:
- Service startup with configurable dev/prod modes
- PID file management in .ralph-session/pids/
- Health check endpoints with retries
- Graceful shutdown and cleanup (including Ctrl+C)
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import urlopen

from .config import RalphConfig, ServiceConfig
from .exec import run_command
from .timeline import TimelineLogger


# Default health check settings
DEFAULT_HEALTH_TIMEOUT = 30
DEFAULT_HEALTH_INTERVAL = 1.0
DEFAULT_HEALTH_RETRIES = 30


@dataclass
class ServiceProcess:
    """Represents a running service process."""
    name: str
    process: subprocess.Popen
    port: int
    pid: int
    pid_file: Path
    url: str
    started_at: float = field(default_factory=time.time)
    
    @property
    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process.poll() is None


@dataclass
class ServiceResult:
    """Result of a service operation."""
    name: str
    success: bool
    port: int = 0
    url: str = ""
    pid: Optional[int] = None
    error: Optional[str] = None
    duration_ms: int = 0


class ServiceManager:
    """Manages service lifecycle for runtime verification.
    
    Handles starting/stopping backend and frontend services,
    with PID file management and health checks.
    """
    
    def __init__(
        self,
        config: RalphConfig,
        session_dir: Optional[Path] = None,
        env: str = "dev",
        timeline: Optional[TimelineLogger] = None,
    ):
        """Initialize service manager.
        
        Args:
            config: Ralph configuration with service definitions.
            session_dir: Session directory for PID files.
            env: Environment mode ("dev" or "prod").
            timeline: Timeline logger for events.
        """
        self.config = config
        self.env = env
        self.timeline = timeline
        
        # Setup directories
        if session_dir is None:
            session_dir = config.repo_root / ".ralph-session"
        self.session_dir = session_dir
        self.pids_dir = session_dir / "pids"
        self.pids_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = session_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Active services
        self._services: Dict[str, ServiceProcess] = {}
        self._cleanup_registered = False
        
    def _get_start_command(
        self,
        service_config: ServiceConfig,
        service_type: str,
    ) -> Optional[str]:
        """Get the start command for a service.
        
        Args:
            service_config: Service configuration.
            service_type: "backend" or "frontend".
            
        Returns:
            Command string with {port} placeholder replaced.
        """
        if service_type == "frontend":
            # Frontend uses serve commands
            cmd = service_config.serve_dev if self.env == "dev" else service_config.serve_prod
        else:
            # Backend uses start commands
            cmd = service_config.start_dev if self.env == "dev" else service_config.start_prod
        
        if cmd:
            # Replace port placeholder
            cmd = cmd.replace("{port}", str(service_config.port))
        
        return cmd
    
    def _write_pid_file(self, name: str, pid: int) -> Path:
        """Write PID file for a service.
        
        Args:
            name: Service name.
            pid: Process ID.
            
        Returns:
            Path to PID file.
        """
        pid_file = self.pids_dir / f"{name}.pid"
        pid_file.write_text(str(pid), encoding="utf-8")
        return pid_file
    
    def _remove_pid_file(self, name: str) -> None:
        """Remove PID file for a service."""
        pid_file = self.pids_dir / f"{name}.pid"
        if pid_file.exists():
            pid_file.unlink()
    
    def _check_health(
        self,
        url: str,
        endpoints: List[str],
        timeout: int = DEFAULT_HEALTH_TIMEOUT,
    ) -> bool:
        """Check service health via HTTP endpoints.
        
        Args:
            url: Base URL of the service.
            endpoints: List of health check endpoints to try.
            timeout: Request timeout in seconds.
            
        Returns:
            True if any health endpoint responds with 2xx.
        """
        if not endpoints:
            # Default: try root endpoint
            endpoints = ["/"]
        
        for endpoint in endpoints:
            check_url = url.rstrip("/") + "/" + endpoint.lstrip("/")
            try:
                response = urlopen(check_url, timeout=5)
                if 200 <= response.status < 300:
                    return True
            except (URLError, OSError, Exception):
                continue
        
        return False
    
    def _wait_for_health(
        self,
        name: str,
        service: ServiceProcess,
        endpoints: List[str],
        timeout: int,
        interval: float = DEFAULT_HEALTH_INTERVAL,
    ) -> bool:
        """Wait for service to become healthy.
        
        Args:
            name: Service name.
            service: Running service process.
            endpoints: Health check endpoints.
            timeout: Maximum wait time in seconds.
            interval: Time between checks in seconds.
            
        Returns:
            True if service became healthy within timeout.
        """
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Check if process died
            if not service.is_running:
                return False
            
            # Check health endpoint
            if self._check_health(service.url, endpoints, timeout=5):
                return True
            
            time.sleep(interval)
        
        return False
    
    def _register_cleanup(self) -> None:
        """Register cleanup handlers for graceful shutdown."""
        if self._cleanup_registered:
            return
        
        # Register atexit handler
        atexit.register(self.stop_all)
        
        # Register signal handlers
        original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
        original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Store original handlers for potential restoration
        self._original_sigint = original_sigint
        self._original_sigterm = original_sigterm
        
        self._cleanup_registered = True
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle termination signals gracefully."""
        print(f"\n⚠ Received signal {signum}, cleaning up services...", file=sys.stderr)
        self.stop_all()
        sys.exit(128 + signum)
    
    def start_service(
        self,
        name: str,
        service_config: ServiceConfig,
    ) -> ServiceResult:
        """Start a single service.
        
        Args:
            name: Service name (e.g., "backend", "frontend").
            service_config: Service configuration.
            
        Returns:
            ServiceResult with startup outcome.
        """
        start_time = time.time()
        port = service_config.port
        
        # Log start
        if self.timeline:
            self.timeline.service_start(name, port)
        
        # Get start command
        cmd = self._get_start_command(service_config, name)
        if not cmd:
            error = f"No {self.env} start command configured for {name}"
            if self.timeline:
                self.timeline.service_failed(name, error)
            return ServiceResult(
                name=name,
                success=False,
                port=port,
                error=error,
            )
        
        # Start process
        try:
            log_path = self.logs_dir / f"{name}.log"
            log_file = log_path.open("w", encoding="utf-8")
            
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(self.config.repo_root),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                preexec_fn=os.setsid if sys.platform != "win32" else None,
            )
        except Exception as e:
            error = f"Failed to start {name}: {e}"
            if self.timeline:
                self.timeline.service_failed(name, error)
            return ServiceResult(
                name=name,
                success=False,
                port=port,
                error=error,
            )
        
        # Write PID file
        pid_file = self._write_pid_file(name, process.pid)
        
        # Create service object
        url = f"http://localhost:{port}"
        service = ServiceProcess(
            name=name,
            process=process,
            port=port,
            pid=process.pid,
            pid_file=pid_file,
            url=url,
        )
        
        # Register cleanup handlers
        self._register_cleanup()
        
        # Wait for health check
        timeout = service_config.timeout or DEFAULT_HEALTH_TIMEOUT
        health_endpoints = service_config.health or ["/"]
        
        if self._wait_for_health(name, service, health_endpoints, timeout):
            # Store active service
            self._services[name] = service
            
            duration_ms = int((time.time() - start_time) * 1000)
            if self.timeline:
                self.timeline.service_ready(name, url, duration_ms)
            
            return ServiceResult(
                name=name,
                success=True,
                port=port,
                url=url,
                pid=process.pid,
                duration_ms=duration_ms,
            )
        else:
            # Health check failed - stop and cleanup
            self._stop_process(process, name)
            self._remove_pid_file(name)
            
            duration_ms = int((time.time() - start_time) * 1000)
            error = f"Health check failed after {timeout}s"
            
            if self.timeline:
                self.timeline.service_failed(name, error, duration_ms)
            
            return ServiceResult(
                name=name,
                success=False,
                port=port,
                error=error,
                duration_ms=duration_ms,
            )
    
    def _stop_process(
        self,
        process: subprocess.Popen,
        name: str,
        timeout: int = 10,
    ) -> None:
        """Stop a process gracefully, then forcefully if needed.
        
        Args:
            process: Process to stop.
            name: Service name for logging.
            timeout: Timeout for graceful shutdown.
        """
        if process.poll() is not None:
            return  # Already dead
        
        try:
            # Try graceful shutdown
            if sys.platform != "win32":
                # Kill process group on Unix
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Force kill
                if sys.platform != "win32":
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                process.wait(timeout=5)
        except (ProcessLookupError, OSError):
            pass  # Process already gone
    
    def stop_service(self, name: str) -> bool:
        """Stop a single service.
        
        Args:
            name: Service name to stop.
            
        Returns:
            True if service was stopped successfully.
        """
        if name not in self._services:
            return True
        
        service = self._services[name]
        self._stop_process(service.process, name)
        self._remove_pid_file(name)
        
        del self._services[name]
        return True
    
    def stop_all(self) -> None:
        """Stop all running services."""
        for name in list(self._services.keys()):
            self.stop_service(name)
    
    def start_backend(self) -> ServiceResult:
        """Start the backend service.
        
        Returns:
            ServiceResult with startup outcome.
        """
        if not self.config.backend:
            return ServiceResult(
                name="backend",
                success=False,
                error="No backend service configured",
            )
        
        return self.start_service("backend", self.config.backend)
    
    def start_frontend(self, build_first: bool = True) -> ServiceResult:
        """Start the frontend service.
        
        Args:
            build_first: Run build command first (for prod mode).
            
        Returns:
            ServiceResult with startup outcome.
        """
        if not self.config.frontend:
            return ServiceResult(
                name="frontend",
                success=False,
                error="No frontend service configured",
            )
        
        # Build first if in prod mode and build command exists
        if build_first and self.env == "prod" and self.config.frontend.build:
            build_result = run_command(
                self.config.frontend.build,
                cwd=self.config.repo_root,
                timeout=300,
                shell=True,
            )
            if not build_result.success:
                return ServiceResult(
                    name="frontend",
                    success=False,
                    error=f"Build failed: {build_result.error or build_result.stderr}",
                )
        
        return self.start_service("frontend", self.config.frontend)
    
    def start_all(self, build_frontend: bool = True) -> Dict[str, ServiceResult]:
        """Start all configured services.
        
        Args:
            build_frontend: Build frontend before starting.
            
        Returns:
            Dict mapping service names to their results.
        """
        results = {}
        
        # Start backend first
        if self.config.backend:
            results["backend"] = self.start_backend()
            if not results["backend"].success:
                return results
        
        # Start frontend
        if self.config.frontend:
            results["frontend"] = self.start_frontend(build_first=build_frontend)
        
        return results
    
    def get_service(self, name: str) -> Optional[ServiceProcess]:
        """Get a running service by name."""
        return self._services.get(name)
    
    def get_base_url(self, prefer_frontend: bool = True) -> Optional[str]:
        """Get the base URL for tests.
        
        Args:
            prefer_frontend: Prefer frontend URL if both are running.
            
        Returns:
            Base URL or None if no services running.
        """
        if prefer_frontend and "frontend" in self._services:
            return self._services["frontend"].url
        if "backend" in self._services:
            return self._services["backend"].url
        return None
    
    def is_healthy(self, name: str) -> bool:
        """Check if a service is healthy.
        
        Args:
            name: Service name.
            
        Returns:
            True if service is running and healthy.
        """
        if name not in self._services:
            return False
        
        service = self._services[name]
        if not service.is_running:
            return False
        
        # Get health endpoints
        if name == "backend" and self.config.backend:
            endpoints = self.config.backend.health or ["/"]
        elif name == "frontend" and self.config.frontend:
            endpoints = ["/"]  # Frontend typically just needs root
        else:
            endpoints = ["/"]
        
        return self._check_health(service.url, endpoints)
    
    @property
    def running_services(self) -> List[str]:
        """Get list of running service names."""
        return list(self._services.keys())


def create_service_manager(
    config: RalphConfig,
    session_dir: Optional[Path] = None,
    env: str = "dev",
    timeline: Optional[TimelineLogger] = None,
) -> ServiceManager:
    """Create a service manager.
    
    Args:
        config: Ralph configuration.
        session_dir: Session directory.
        env: Environment mode.
        timeline: Timeline logger.
        
    Returns:
        ServiceManager instance.
    """
    return ServiceManager(
        config=config,
        session_dir=session_dir,
        env=env,
        timeline=timeline,
    )


def format_service_status(results: Dict[str, ServiceResult]) -> str:
    """Format service startup results for display.
    
    Args:
        results: Dict of service results.
        
    Returns:
        Formatted status string.
    """
    lines = []
    for name, result in results.items():
        if result.success:
            lines.append(f"  ✓ {name.capitalize()} ready on {result.url} ({result.duration_ms}ms)")
        else:
            lines.append(f"  ✗ {name.capitalize()} failed: {result.error}")
    return "\n".join(lines)
