"""Configuration loader for Ralph orchestrator.

Loads and validates ralph.yml against schemas/ralph-config.schema.json,
resolves paths relative to the repository root.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from jsonschema import Draft7Validator


def _find_project_root() -> Path:
    """Find the project root containing the schemas directory."""
    # First try relative to this file (for installed package)
    module_path = Path(__file__).resolve().parent.parent
    if (module_path / "schemas").exists():
        return module_path
    # Fallback: check current working directory and parents
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "schemas").exists():
            return parent
    # Last resort: return module path anyway
    return module_path


PROJECT_ROOT = _find_project_root()


def _read_schema(schema_name: str) -> Dict[str, Any]:
    """Load a JSON schema from the schemas directory."""
    schema_path = PROJECT_ROOT / "schemas" / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_against_schema(data: Any, schema_name: str) -> Tuple[bool, List[str]]:
    """Validate data against a JSON schema.
    
    Args:
        data: The data to validate
        schema_name: Name of schema file in schemas/ directory
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    schema = _read_schema(schema_name)
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    
    if not errors:
        return True, []
    
    messages: List[str] = []
    for err in errors[:50]:
        location = ".".join([str(p) for p in err.absolute_path]) or "<root>"
        messages.append(f"{location}: {err.message}")
    
    if len(errors) > 50:
        messages.append(f"... and {len(errors) - 50} more errors")
    
    return False, messages


@dataclass
class GateConfig:
    """Configuration for a single quality gate."""
    name: str
    cmd: str
    when: Optional[str] = None
    timeout_seconds: int = 300
    fatal: bool = True


@dataclass
class ServiceConfig:
    """Configuration for a service (backend/frontend)."""
    start_dev: Optional[str] = None
    start_prod: Optional[str] = None
    build: Optional[str] = None
    serve_dev: Optional[str] = None
    serve_prod: Optional[str] = None
    port: int = 8000
    health: List[str] = field(default_factory=list)
    timeout: int = 30


@dataclass
class AgentRoleConfig:
    """Configuration for an agent role."""
    model: Optional[str] = None
    timeout: int = 1800
    allowed_tools: List[str] = field(default_factory=list)


@dataclass
class LimitsConfig:
    """Iteration and timeout limits."""
    claude_timeout: int = 1800
    max_iterations: int = 30
    post_verify_iterations: int = 10
    ui_fix_iterations: int = 10
    robot_fix_iterations: int = 10


@dataclass
class GitConfig:
    """Git configuration."""
    base_branch: str = "main"
    remote: str = "origin"


@dataclass  
class AutopilotConfig:
    """Autopilot pipeline configuration."""
    enabled: bool = False
    reports_dir: str = "./reports"
    branch_prefix: str = "ralph/"
    create_pr: bool = True
    prd_mode: str = "autonomous"
    prd_output_dir: str = "./tasks"
    tasks_output: str = ".ralph/prd.json"
    tasks_min_count: int = 8
    tasks_max_count: int = 15
    analysis_provider: str = "anthropic"
    analysis_model: Optional[str] = None
    recent_days: int = 7
    progress_path: str = ".ralph/progress.txt"
    archive_path: str = ".ralph/archive"


@dataclass
class RalphConfig:
    """Full Ralph configuration with structured access."""
    
    path: Path
    repo_root: Path
    raw_data: Dict[str, Any]
    
    # Required fields
    version: str = "1"
    task_source_type: str = "prd_json"
    task_source_path: str = ".ralph/prd.json"
    
    # Git
    git: GitConfig = field(default_factory=GitConfig)
    
    # Gates
    gates_build: List[GateConfig] = field(default_factory=list)
    gates_full: List[GateConfig] = field(default_factory=list)
    
    # Test paths
    test_paths: List[str] = field(default_factory=lambda: ["tests/**", "**/*.test.*", "**/*.spec.*"])
    
    # Services
    backend: Optional[ServiceConfig] = None
    frontend: Optional[ServiceConfig] = None
    
    # Agent roles
    agents: Dict[str, AgentRoleConfig] = field(default_factory=dict)
    
    # Limits
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    
    # Autopilot
    autopilot: AutopilotConfig = field(default_factory=AutopilotConfig)
    
    # PR config
    pr_enabled: bool = True
    pr_title_template: str = "Ralph: {priority_item}"
    pr_body_template: Optional[str] = None
    
    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a path relative to the repo root."""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return self.repo_root / path
    
    @property
    def task_source_resolved(self) -> Path:
        """Resolved path to the task source file."""
        return self.resolve_path(self.task_source_path)
    
    def get_gates(self, gate_type: str = "full") -> List[GateConfig]:
        """Get gates of the specified type."""
        if gate_type == "build":
            return self.gates_build
        elif gate_type == "full":
            return self.gates_full
        elif gate_type == "none":
            return []
        else:
            raise ValueError(f"Unknown gate type: {gate_type}")
    
    def get_agent_config(self, role: str) -> AgentRoleConfig:
        """Get configuration for an agent role."""
        return self.agents.get(role, AgentRoleConfig())


def _parse_gate(gate_data: Dict[str, Any]) -> GateConfig:
    """Parse a gate configuration dict into a GateConfig."""
    return GateConfig(
        name=gate_data["name"],
        cmd=gate_data["cmd"],
        when=gate_data.get("when"),
        timeout_seconds=gate_data.get("timeout_seconds", 300),
        fatal=gate_data.get("fatal", True),
    )


def _parse_service(service_data: Dict[str, Any]) -> ServiceConfig:
    """Parse a service configuration dict into a ServiceConfig."""
    start = service_data.get("start", {})
    serve = service_data.get("serve", {})
    return ServiceConfig(
        start_dev=start.get("dev"),
        start_prod=start.get("prod"),
        build=service_data.get("build"),
        serve_dev=serve.get("dev"),
        serve_prod=serve.get("prod"),
        port=service_data.get("port", 8000),
        health=service_data.get("health", []),
        timeout=service_data.get("timeout", 30),
    )


def _parse_agent_role(role_data: Dict[str, Any]) -> AgentRoleConfig:
    """Parse an agent role configuration dict."""
    return AgentRoleConfig(
        model=role_data.get("model"),
        timeout=role_data.get("timeout", 1800),
        allowed_tools=role_data.get("allowed_tools", []),
    )


def _parse_limits(limits_data: Dict[str, Any]) -> LimitsConfig:
    """Parse limits configuration dict."""
    return LimitsConfig(
        claude_timeout=limits_data.get("claude_timeout", 1800),
        max_iterations=limits_data.get("max_iterations", 30),
        post_verify_iterations=limits_data.get("post_verify_iterations", 10),
        ui_fix_iterations=limits_data.get("ui_fix_iterations", 10),
        robot_fix_iterations=limits_data.get("robot_fix_iterations", 10),
    )


def _parse_git(git_data: Dict[str, Any]) -> GitConfig:
    """Parse git configuration dict."""
    return GitConfig(
        base_branch=git_data.get("base_branch", "main"),
        remote=git_data.get("remote", "origin"),
    )


def _parse_autopilot(autopilot_data: Dict[str, Any]) -> AutopilotConfig:
    """Parse autopilot configuration dict."""
    analysis = autopilot_data.get("analysis", {})
    prd = autopilot_data.get("prd", {})
    tasks = autopilot_data.get("tasks", {})
    memory = autopilot_data.get("memory", {})
    
    return AutopilotConfig(
        enabled=autopilot_data.get("enabled", False),
        reports_dir=autopilot_data.get("reports_dir", "./reports"),
        branch_prefix=autopilot_data.get("branch_prefix", "ralph/"),
        create_pr=autopilot_data.get("create_pr", True),
        prd_mode=prd.get("mode", "autonomous"),
        prd_output_dir=prd.get("output_dir", "./tasks"),
        tasks_output=tasks.get("output", ".ralph/prd.json"),
        tasks_min_count=tasks.get("min_count", 8),
        tasks_max_count=tasks.get("max_count", 15),
        analysis_provider=analysis.get("provider", "anthropic"),
        analysis_model=analysis.get("model"),
        recent_days=analysis.get("recent_days", 7),
        progress_path=memory.get("progress", ".ralph/progress.txt"),
        archive_path=memory.get("archive", ".ralph/archive"),
    )


def load_config(
    config_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> RalphConfig:
    """Load and validate Ralph configuration from a YAML file.
    
    Args:
        config_path: Path to ralph.yml. Defaults to .ralph/ralph.yml in repo_root.
        repo_root: Repository root directory. Defaults to current working directory.
        
    Returns:
        RalphConfig instance with parsed configuration.
        
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid against schema.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    repo_root = repo_root.resolve()
    
    if config_path is None:
        config_path = repo_root / ".ralph" / "ralph.yml"
    config_path = config_path.resolve()
    
    # Check for environment override
    env_config = os.environ.get("RALPH_CONFIG")
    if env_config:
        config_path = Path(env_config).resolve()
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load YAML
    raw_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    
    # Validate against schema
    valid, errors = validate_against_schema(raw_data, "ralph-config.schema.json")
    if not valid:
        raise ValueError(
            f"Invalid configuration in {config_path}:\n" + 
            "\n".join(f"  - {e}" for e in errors)
        )
    
    # Parse task source
    task_source = raw_data.get("task_source", {})
    
    # Parse gates
    gates_data = raw_data.get("gates", {})
    gates_build = [_parse_gate(g) for g in gates_data.get("build", [])]
    gates_full = [_parse_gate(g) for g in gates_data.get("full", [])]
    
    # Parse services
    services_data = raw_data.get("services", {})
    backend = None
    frontend = None
    if "backend" in services_data:
        backend = _parse_service(services_data["backend"])
    if "frontend" in services_data:
        frontend = _parse_service(services_data["frontend"])
    
    # Parse agents
    agents_data = raw_data.get("agents", {})
    agents = {}
    for role, role_data in agents_data.items():
        agents[role] = _parse_agent_role(role_data)
    
    # Parse limits
    limits = _parse_limits(raw_data.get("limits", {}))
    
    # Parse git
    git = _parse_git(raw_data.get("git", {}))
    
    # Parse autopilot
    autopilot = _parse_autopilot(raw_data.get("autopilot", {}))
    
    # Parse PR config
    pr_data = raw_data.get("pr", {})
    
    return RalphConfig(
        path=config_path,
        repo_root=repo_root,
        raw_data=raw_data,
        version=raw_data.get("version", "1"),
        task_source_type=task_source.get("type", "prd_json"),
        task_source_path=task_source.get("path", ".ralph/prd.json"),
        git=git,
        gates_build=gates_build,
        gates_full=gates_full,
        test_paths=raw_data.get("test_paths", ["tests/**", "**/*.test.*", "**/*.spec.*"]),
        backend=backend,
        frontend=frontend,
        agents=agents,
        limits=limits,
        autopilot=autopilot,
        pr_enabled=pr_data.get("enabled", True),
        pr_title_template=pr_data.get("title_template", "Ralph: {priority_item}"),
        pr_body_template=pr_data.get("body_template"),
    )


def get_default_config_path(repo_root: Optional[Path] = None) -> Path:
    """Get the default configuration file path."""
    if repo_root is None:
        repo_root = Path.cwd()
    return repo_root / ".ralph" / "ralph.yml"
