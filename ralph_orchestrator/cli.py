"""Ralph Orchestrator CLI.

This module defines the `ralph` command-line interface, including:
- Argument parsing and command dispatch
- Helpers used by CLI flows (e.g., task generation from markdown)

The core execution loop lives in `run.py`; the CLI should stay a thin wrapper
around reusable orchestration logic.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from jsonschema import Draft7Validator

from . import __version__


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_schema(schema_rel: str) -> Dict[str, Any]:
    schema_path = PROJECT_ROOT / schema_rel
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_against_schema(data: Any, schema_rel: str) -> Tuple[bool, List[str]]:
    schema = _read_schema(schema_rel)
    v = Draft7Validator(schema)
    errors = sorted(v.iter_errors(data), key=lambda e: e.path)
    if not errors:
        return True, []
    msgs: List[str] = []
    for err in errors[:50]:
        loc = ".".join([str(p) for p in err.absolute_path]) or "<root>"
        msgs.append(f"{loc}: {err.message}")
    if len(errors) > 50:
        msgs.append(f"... and {len(errors) - 50} more")
    return False, msgs


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def ralph_dir() -> Path:
    return Path(".ralph")


def default_config_path() -> Path:
    return ralph_dir() / "ralph.yml"


@dataclass
class RalphConfig:
    path: Path
    data: Dict[str, Any]

    @property
    def task_source(self) -> Dict[str, Any]:
        return self.data["task_source"]


def load_config(path: Path) -> RalphConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ok, errs = validate_against_schema(data, "schemas/ralph-config.schema.json")
    if not ok:
        raise ValueError("Invalid config:\n" + "\n".join(f"- {e}" for e in errs))
    return RalphConfig(path=path, data=data)


def load_prd_json(path: Path) -> Dict[str, Any]:
    prd = load_json(path)
    ok, errs = validate_against_schema(prd, "schemas/prd.schema.json")
    if not ok:
        raise ValueError("Invalid prd.json:\n" + "\n".join(f"- {e}" for e in errs))
    return prd


def detect_template() -> str:
    # Minimal heuristic: python if pyproject.toml, node if package.json, fullstack if both or frontend/package.json
    has_py = Path("pyproject.toml").exists()
    has_node = Path("package.json").exists()
    has_frontend = Path("frontend/package.json").exists()
    if has_py and (has_node or has_frontend):
        return "fullstack"
    if has_py:
        return "python"
    if has_node:
        return "node"
    return "minimal"


def copy_template_file(src: Path, dst: Path, force: bool) -> None:
    if dst.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {dst} (use --force)")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and force:
        backup = dst.with_suffix(dst.suffix + ".bak")
        shutil.copy2(dst, backup)
    shutil.copy2(src, dst)


def command_init(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    template = args.template
    if template == "auto":
        template = detect_template()

    template_map = {
        "minimal": PROJECT_ROOT / "templates/.ralph/ralph.yml.minimal",
        "python": PROJECT_ROOT / "templates/.ralph/ralph.yml.python",
        "node": PROJECT_ROOT / "templates/.ralph/ralph.yml.node",
        "fullstack": PROJECT_ROOT / "templates/.ralph/ralph.yml.fullstack",
    }
    if template not in template_map:
        eprint(f"Unknown template: {template}")
        return 2

    try:
        copy_template_file(template_map[template], out_dir / "ralph.yml", force=args.force)
        if not args.no_prd:
            copy_template_file(PROJECT_ROOT / "templates/.ralph/prd.json.template", out_dir / "prd.json", force=args.force)
        copy_template_file(PROJECT_ROOT / "templates/.ralph/progress.txt.template", out_dir / "progress.txt", force=args.force)
        if not args.no_agents_md:
            copy_template_file(PROJECT_ROOT / "templates/AGENTS.md.template", Path("AGENTS.md"), force=args.force)
    except FileExistsError as e:
        eprint(str(e))
        return 1

    # For Python template, auto-create pyproject.toml if missing
    pyproject_created = False
    if template == "python" and not Path("pyproject.toml").exists():
        pyproject_starter = PROJECT_ROOT / "templates/pyproject.toml.starter"
        if pyproject_starter.exists():
            try:
                copy_template_file(pyproject_starter, Path("pyproject.toml"), force=args.force)
                pyproject_created = True
            except FileExistsError:
                pass  # Already exists, skip

    # Validate generated config
    try:
        cfg = load_config(out_dir / "ralph.yml")
    except Exception as e:
        eprint(f"Generated config failed validation: {e}")
        return 3

    print("Created:")
    print(f"- {out_dir / 'ralph.yml'} (template: {template})")
    if not args.no_prd:
        print(f"- {out_dir / 'prd.json'}")
    print(f"- {out_dir / 'progress.txt'}")
    if not args.no_agents_md:
        print("- AGENTS.md")
    if pyproject_created:
        print("- pyproject.toml (starter file for pytest/mypy/ruff)")
    print("")
    print("Next:")
    print("- Review `.ralph/ralph.yml` and customize gates/services if needed")
    print("- Add tasks to `.ralph/prd.json` (or run `ralph autopilot`)")
    print("- Run: `ralph scan` then `ralph run`")
    _ = cfg
    return 0


def _tool_check(name: str, cmd: str) -> Dict[str, Any]:
    path = which(cmd)
    if not path:
        return {"name": name, "status": "missing", "cmd": cmd}
    # best-effort version
    ver = None
    try:
        out = run_cmd([cmd, "--version"], timeout=5)
        if out.returncode == 0:
            ver = out.stdout.strip() or out.stderr.strip()
    except Exception:
        ver = None
    return {"name": name, "status": "ok", "cmd": cmd, "path": path, "version": ver}


def command_scan(args: argparse.Namespace) -> int:
    checks: List[Dict[str, Any]] = []

    # Core tools
    claude_cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
    claude_argv0 = shlex.split(claude_cmd)[0]
    checks.append(_tool_check("claude", claude_argv0))
    checks.append(_tool_check("git", "git"))
    checks.append(_tool_check("gh", "gh"))

    # Optional
    checks.append(_tool_check("node", "node"))
    checks.append(_tool_check("npm", "npm"))
    checks.append(_tool_check("uv", "uv"))
    checks.append(_tool_check("agent-browser", "agent-browser"))
    checks.append(_tool_check("robot", "robot"))

    config_path = Path(args.config) if args.config else default_config_path()
    config_ok = config_path.exists()
    tasks_ok = False
    tasks_path: Optional[Path] = None
    config_err: Optional[str] = None

    if config_ok:
        try:
            cfg = load_config(config_path)
            task_src = cfg.task_source
            if task_src["type"] == "prd_json":
                tasks_path = Path(task_src["path"])
                tasks_ok = tasks_path.exists()
            else:
                # compat mode not implemented in scan v0.1 beyond existence check
                tasks_path = Path(task_src["path"])
                tasks_ok = True
        except Exception as e:
            config_ok = False
            config_err = str(e)

    report: Dict[str, Any] = {
        "status": "ready",
        "checks": checks,
        "config": {"path": str(config_path), "ok": config_ok, "error": config_err},
        "tasks": {"path": str(tasks_path) if tasks_path else None, "ok": tasks_ok},
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if config_ok else 2

    print("RALPH ENVIRONMENT SCAN")
    print("----------------------")
    for c in checks:
        status = c["status"]
        if status == "ok":
            print(f"✓ {c['name']}: {c.get('path')}")
        else:
            print(f"⚠ {c['name']}: not found")
    if config_ok:
        print(f"✓ config: {config_path}")
    else:
        print(f"✗ config: {config_path}")
        if config_err:
            print(f"  {config_err}")
    if tasks_path:
        print(f"{'✓' if tasks_ok else '⚠'} tasks: {tasks_path}")

    # Check for skippable fatal gates
    if config_ok:
        try:
            from .config import load_config as load_full_config
            from .gates import check_skippable_fatal_gates

            full_cfg = load_full_config(config_path)
            skippable = check_skippable_fatal_gates(full_cfg, Path.cwd())
            if skippable:
                print("")
                print("⚠ WARNING: The following fatal gates will be SKIPPED:")
                for gate_name, missing_file in skippable:
                    print(f"  - {gate_name}: '{missing_file}' not found")
                print("  Tests may be written but never executed!")
                print("  Fix: Create the missing file(s) or remove 'when:' conditions from .ralph/ralph.yml")
        except Exception:
            pass  # Don't fail scan if gate check fails

    return 0 if config_ok else 2


def command_run(args: argparse.Namespace) -> int:
    """Execute the verified task loop."""
    from .run import run_tasks, RunOptions, ExitCode

    config_path = Path(args.config) if args.config else None
    prd_path = Path(args.prd_json) if args.prd_json else None

    options = RunOptions(
        prd_json=args.prd_json,
        task_id=getattr(args, 'task', None),
        from_task_id=getattr(args, 'from_task', None),
        max_iterations=args.max_iterations,
        gate_type=getattr(args, 'gates', 'full'),
        dry_run=args.dry_run,
        resume=getattr(args, 'resume', False),
        post_verify=getattr(args, 'post_verify', True),
        verbose=getattr(args, 'verbose', False),
        with_smoke=getattr(args, 'with_smoke', None),
        with_robot=getattr(args, 'with_robot', None),
        parallel=getattr(args, 'parallel', False),
        max_parallel=getattr(args, 'max_parallel', 3),
    )

    result = run_tasks(
        config_path=config_path,
        prd_path=prd_path,
        options=options,
    )

    if result.error:
        eprint(f"Error: {result.error}")

    return result.exit_code.value


def command_verify(args: argparse.Namespace) -> int:
    """Run post-completion verification."""
    from .verify import run_verify, VerifyOptions
    
    config_path = Path(args.config) if args.config else None
    
    options = VerifyOptions(
        gate_type=getattr(args, 'gates', 'full'),
        run_ui=getattr(args, 'ui', None),
        run_robot=getattr(args, 'robot', None),
        env=getattr(args, 'env', 'dev'),
        fix=getattr(args, 'fix', False),
        fix_iterations=getattr(args, 'fix_iterations', 10),
        skip_services=getattr(args, 'skip_services', False),
        base_url=getattr(args, 'base_url', None),
        verbose=getattr(args, 'verbose', False),
    )
    
    result = run_verify(
        config_path=config_path,
        options=options,
    )
    
    if result.error:
        eprint(f"Error: {result.error}")
    
    return result.exit_code.value


def command_autopilot(args: argparse.Namespace) -> int:
    """Run the autopilot self-improvement pipeline."""
    from .autopilot import run_autopilot, AutopilotOptions

    config_path = Path(args.config) if args.config else None

    options = AutopilotOptions(
        reports_dir=getattr(args, 'reports', None),
        report_path=getattr(args, 'report', None),
        dry_run=getattr(args, 'dry_run', False),
        create_pr=getattr(args, 'create_pr', None),
        branch_name=getattr(args, 'branch', None),
        skip_prd=getattr(args, 'no_prd', False),
        prd_mode=getattr(args, 'prd_mode', None),
        task_count_min=None,  # From task_count range
        task_count_max=None,
        analysis_model=getattr(args, 'analysis_model', None),
        recent_days=getattr(args, 'recent_days', None),
        resume=getattr(args, 'resume', False),
        verbose=getattr(args, 'verbose', False),
        with_research=getattr(args, 'with_research', None),
        research_backend=getattr(args, 'research_backend', False),
        research_frontend=getattr(args, 'research_frontend', False),
        research_web=getattr(args, 'research_web', False),
    )
    
    # Parse task count range if provided
    task_count = getattr(args, 'task_count', None)
    if task_count:
        try:
            if '-' in task_count:
                min_count, max_count = task_count.split('-')
                options.task_count_min = int(min_count)
                options.task_count_max = int(max_count)
            else:
                count = int(task_count)
                options.task_count_min = count
                options.task_count_max = count
        except ValueError:
            eprint(f"Invalid task count format: {task_count} (expected: 8-15 or 10)")
            return 2
    
    result = run_autopilot(
        config_path=config_path,
        options=options,
    )
    
    if result.error:
        eprint(f"Error: {result.error}")
    
    return result.exit_code.value


def command_chat(args: argparse.Namespace) -> int:
    """Launch an interactive Claude Code session to produce a markdown doc."""
    from .chat import run_chat, ChatOptions, ChatError

    repo_root = Path.cwd()
    options = ChatOptions(
        mode=getattr(args, "mode", "change-request"),
        template=getattr(args, "template", None),
        out=getattr(args, "out", None),
        model=getattr(args, "model", "sonnet"),
        auto_exit=getattr(args, "auto_exit", True),
    )

    try:
        saved = run_chat(repo_root=repo_root, options=options)
        print(f"\nDone. File created: {saved}")
        return 0
    except ChatError as e:
        eprint(f"Error: {e}")
        return 2


def _claude_argv0() -> str:
    claude_cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
    argv0 = shlex.split(claude_cmd)[0] if claude_cmd else "claude"
    return argv0


def _invoke_claude_structured(prompt: str, schema: Dict[str, Any], model: str = "sonnet", timeout: int = 1800) -> Dict[str, Any]:
    """Call Claude CLI in --print mode and return structured output."""
    argv0 = _claude_argv0()
    cmd = [
        argv0,
        "--print",
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
        "--model",
        model,
    ]
    proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"Claude failed with exit code {proc.returncode}")
    data = json.loads(proc.stdout.strip() or "{}")
    if isinstance(data, dict) and "structured_output" in data:
        return data["structured_output"]
    # Fallback: some configurations might emit the JSON directly
    if isinstance(data, dict):
        return data
    raise RuntimeError("Claude did not return structured output")


def _parse_task_count(task_count: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if not task_count:
        return None, None
    task_count = task_count.strip()
    if "-" in task_count:
        a, b = task_count.split("-", 1)
        return int(a.strip()), int(b.strip())
    n = int(task_count)
    return n, n


@dataclass
class TaskGenerationResult:
    """Result of task generation from markdown."""
    data: Dict[str, Any]
    path: Path
    task_count: int


@dataclass
class ComplexityAnalysisResult:
    """Result of complexity analysis for task count recommendation."""
    min_tasks: int
    max_tasks: int
    complexity: str  # "simple", "moderate", "complex", "very_complex"
    rationale: str


def analyze_complexity_for_task_count(
    md_content: str,
    model: str = "sonnet",
    timeout: int = 300,
    verbose: bool = False,
) -> ComplexityAnalysisResult:
    """Analyze the complexity of a change request and recommend task count range.
    
    Uses Claude to analyze the markdown content and determine an appropriate
    number of tasks based on:
    - Scope of changes (single file vs multi-file vs multi-system)
    - Number of distinct features/requirements
    - Technical complexity indicators
    - Dependencies between components
    
    Args:
        md_content: The markdown content to analyze.
        model: Claude model to use for analysis.
        timeout: Timeout in seconds.
        verbose: Whether to print progress.
        
    Returns:
        ComplexityAnalysisResult with recommended task range.
    """
    complexity_schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["min_tasks", "max_tasks", "complexity", "rationale"],
        "properties": {
            "min_tasks": {"type": "integer", "minimum": 3, "maximum": 50},
            "max_tasks": {"type": "integer", "minimum": 3, "maximum": 100},
            "complexity": {
                "type": "string",
                "enum": ["simple", "moderate", "complex", "very_complex"]
            },
            "rationale": {"type": "string", "maxLength": 500}
        }
    }
    
    prompt = (
        "Analyze the following change request/PRD and determine the appropriate number of tasks.\n\n"
        "ANALYSIS CRITERIA:\n"
        "- simple (3-8 tasks): Single file changes, minor features, bug fixes\n"
        "- moderate (8-15 tasks): Multi-file changes, new features with clear scope\n"
        "- complex (15-25 tasks): Multi-system changes, new services/APIs, significant refactoring\n"
        "- very_complex (25-50 tasks): Architecture changes, new frameworks, multiple integrations\n\n"
        "FACTORS TO CONSIDER:\n"
        "- Number of distinct features or requirements mentioned\n"
        "- Number of systems/components affected\n"
        "- Whether it involves UI, backend, database, or infrastructure changes\n"
        "- Dependencies and integration points\n"
        "- Testing and verification requirements\n\n"
        "Respond with min_tasks and max_tasks that form a reasonable range for this work.\n"
        "The range should typically span 3-5 tasks (e.g., 8-12, not 5-20).\n\n"
        "DOCUMENT TO ANALYZE:\n"
        "-------------------\n"
        f"{md_content[:8000]}\n"  # Truncate to avoid token limits
    )
    
    if verbose:
        print("  Analyzing complexity to determine task count...")
    
    try:
        data = _invoke_claude_structured(prompt=prompt, schema=complexity_schema, model=model, timeout=timeout)
        
        # Validate the response
        min_tasks = max(3, min(50, data.get("min_tasks", 8)))
        max_tasks = max(min_tasks, min(100, data.get("max_tasks", 15)))
        
        # Ensure max >= min with reasonable spread
        if max_tasks < min_tasks + 2:
            max_tasks = min_tasks + 5
        
        return ComplexityAnalysisResult(
            min_tasks=min_tasks,
            max_tasks=max_tasks,
            complexity=data.get("complexity", "moderate"),
            rationale=data.get("rationale", "Default analysis")
        )
    except Exception as e:
        # Fallback to moderate complexity on error
        if verbose:
            print(f"  Warning: Complexity analysis failed ({e}), using default range 8-15")
        return ComplexityAnalysisResult(
            min_tasks=8,
            max_tasks=15,
            complexity="moderate",
            rationale=f"Default fallback (analysis error: {str(e)[:100]})"
        )


def generate_tasks_from_markdown(
    src: Path,
    out: Path,
    task_count: str = "auto",
    branch: Optional[str] = None,
    model: str = "sonnet",
    timeout: int = 1800,
    verbose: bool = False,
) -> TaskGenerationResult:
    """Generate .ralph/prd.json tasks from a PRD/CR markdown file.
    
    This is the shared helper used by both `ralph tasks` and `ralph flow`.
    
    Args:
        src: Source markdown file path.
        out: Output prd.json path.
        task_count: Task count range (e.g., "8-15" or "10").
        branch: Branch name for branchName field. Auto-generated from src if None.
        model: Claude model alias (e.g., "sonnet", "opus").
        timeout: Timeout in seconds for Claude call.
        verbose: Whether to print progress messages.
        
    Returns:
        TaskGenerationResult with generated data, path, and task count.
        
    Raises:
        FileNotFoundError: If source markdown not found.
        ValueError: If generated data fails schema validation.
        RuntimeError: If Claude call fails.
    """
    if not src.exists():
        raise FileNotFoundError(f"Source markdown not found: {src}")
    
    out.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate branch name if not provided
    if branch is None:
        branch = f"ralph/{src.stem.lower().replace(' ', '-').replace('_', '-')}"
    
    md = src.read_text(encoding="utf-8", errors="replace")
    
    # Determine task count range
    min_count: int
    max_count: int
    if task_count == "auto" or task_count is None:
        # Use AI to analyze complexity and determine task count
        complexity = analyze_complexity_for_task_count(md, model=model, verbose=verbose)
        min_count = complexity.min_tasks
        max_count = complexity.max_tasks
        if verbose:
            print(f"  Complexity: {complexity.complexity} → {min_count}-{max_count} tasks")
            print(f"  Rationale: {complexity.rationale[:100]}...")
    else:
        parsed_min, parsed_max = _parse_task_count(task_count)
        min_count = parsed_min if parsed_min is not None else 8
        max_count = parsed_max if parsed_max is not None else 15
    
    # Use a relaxed schema for generation (easier for the model),
    # then validate against the canonical prd.schema.json after.
    prd_schema_relaxed: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["project", "description", "tasks"],
        "properties": {
            "project": {"type": "string"},
            "branchName": {"type": "string"},
            "description": {"type": "string"},
            "version": {"type": "string"},
            "metadata": {"type": "object"},
            "tasks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["id", "title", "description", "acceptanceCriteria", "priority", "passes"],
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "acceptanceCriteria": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "priority": {"type": "integer"},
                        "passes": {"type": "boolean"},
                        "notes": {"type": "string"},
                        "subtasks": {"type": "array"},
                    },
                },
            },
        },
    }
    
    prompt = (
        "You are generating a task list for Ralph orchestrator.\n\n"
        "INPUT: a markdown document describing a desired change.\n"
        "OUTPUT: a JSON object that STRICTLY matches the provided JSON Schema.\n\n"
        "TASK RULES:\n"
        f"- Produce between {min_count} and {max_count} tasks.\n"
        "- Each task does ONE thing only.\n"
        "- Use IDs T-001, T-002, ... sequential.\n"
        "- Every acceptanceCriteria item must be boolean/verifiable.\n"
        "- All tasks must start with passes=false and notes=\"\".\n"
        "- Prefer investigation tasks first, then implementation, then verification.\n\n"
        "Set top-level fields:\n"
        f"- branchName: {branch}\n"
        "- version: \"1\" (or omit version)\n"
        "- metadata.source: imported-cr OR imported-prd (choose best fit)\n"
        f"- metadata.sourceFile: {src.as_posix()}\n\n"
        "MARKDOWN SOURCE:\n"
        "----------------\n"
        f"{md}\n"
    )
    
    if verbose:
        print(f"  Generating tasks from {src.name}...")
        print(f"  Target: {min_count}-{max_count} tasks using {model}")
    
    data = _invoke_claude_structured(prompt=prompt, schema=prd_schema_relaxed, model=model, timeout=timeout)
    ok, errs = validate_against_schema(data, "schemas/prd.schema.json")
    if not ok:
        raise ValueError("Invalid prd.json:\n" + "\n".join(f"- {e}" for e in errs))
    
    dump_json(out, data)
    
    tasks = data.get("tasks", [])
    return TaskGenerationResult(data=data, path=out, task_count=len(tasks))


def command_validate_tasks(args: argparse.Namespace) -> int:
    """Validate a prd.json file against schema."""
    path = Path(args.path) if args.path else Path(".ralph/prd.json")
    if not path.exists():
        eprint(f"Task file not found: {path}")
        return 2
    try:
        _ = load_prd_json(path)
    except Exception as e:
        eprint(str(e))
        return 1
    print(f"✓ Valid: {path}")
    return 0


def command_serve(args: argparse.Namespace) -> int:
    """Start the Ralph web UI server."""
    import webbrowser

    try:
        import uvicorn
    except ImportError:
        eprint("Error: uvicorn is not installed. Install with: pip install uvicorn")
        return 1

    # Determine host - remote flag overrides host
    host = args.host
    if args.remote:
        host = "0.0.0.0"
        print("WARNING: Remote access enabled. The server will be accessible from your network.")
        print("         Ensure you understand the security implications.")
        print()

    port = args.port

    # Determine projects root
    projects_root = Path(args.projects_root).resolve() if args.projects_root else Path.cwd()
    if not projects_root.exists():
        eprint(f"Projects root directory does not exist: {projects_root}")
        return 2

    # Add the project root to sys.path so the server module can be imported
    # This is needed because server/ is not part of the ralph_orchestrator package
    server_parent = PROJECT_ROOT
    if str(server_parent) not in sys.path:
        sys.path.insert(0, str(server_parent))

    # Initialize the ProjectService with the specified projects root
    # We need to set this before importing the app so it uses our paths
    from ralph_orchestrator.services.project_service import ProjectService
    from server import api

    # Configure the project service with our search paths
    api._project_service = ProjectService(search_paths=[projects_root])

    # Build the URL
    display_host = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    url = f"http://{display_host}:{port}"

    # Print startup message
    print("Ralph Orchestrator Web UI")
    print("=" * 40)
    print(f"  Server:       {url}")
    print(f"  API docs:     {url}/docs")
    print(f"  Projects root: {projects_root}")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    sys.stdout.flush()

    # Auto-open browser if requested
    if args.open:
        # Use a small delay to let the server start
        import threading
        def open_browser():
            import time
            time.sleep(1.0)  # Wait for server to start
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    # Start the uvicorn server
    try:
        uvicorn.run(
            "server.api:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        eprint(f"Server error: {e}")
        return 1

    return 0


def command_flow(args: argparse.Namespace) -> int:
    """Run one-command flow (change or new project)."""
    from .flow import run_flow, FlowOptions, FlowResult
    
    repo_root = Path.cwd()
    
    # Determine mode from subcommand
    mode = getattr(args, "flow_mode", "change")
    
    options = FlowOptions(
        mode=mode,
        task_count=getattr(args, "task_count", "auto"),
        model=getattr(args, "model", "sonnet"),
        out_md=getattr(args, "out_md", None),
        out_json=getattr(args, "out_json", None),
        skip_approval=getattr(args, "yes", False),
        template=getattr(args, "template", "auto"),
        force=getattr(args, "force", False),
        max_iterations=getattr(args, "max_iterations", 200),
        gate_type=getattr(args, "gates", "full"),
        dry_run=getattr(args, "dry_run", False),
        verbose=getattr(args, "verbose", False),
    )
    
    result = run_flow(repo_root=repo_root, options=options)
    
    # Print final summary
    print()
    if result.success:
        if result.aborted_at == "approval":
            print("Flow completed (execution skipped)")
            print(f"  - Markdown: {result.md_path}")
            print(f"  - Tasks: {result.json_path} ({result.tasks_count} tasks)")
            print("\nTo run later: ralph run --prd-json .ralph/prd.json")
            return 0
        elif result.run_result:
            print("Flow completed successfully")
            return result.run_result.exit_code.value
        else:
            print("Flow completed")
            return 0
    else:
        eprint(f"Flow failed at stage: {result.aborted_at}")
        if result.error:
            eprint(f"Error: {result.error}")
        return 2


def command_tasks(args: argparse.Namespace) -> int:
    """Generate .ralph/prd.json tasks from a PRD/CR markdown file."""
    src = Path(args.from_markdown)
    out = Path(args.out) if args.out else Path(".ralph/prd.json")
    branch = args.branch  # None is fine, helper will auto-generate

    try:
        result = generate_tasks_from_markdown(
            src=src,
            out=out,
            task_count=args.task_count,
            branch=branch,
            model=args.model,
            verbose=True,
        )
    except FileNotFoundError as e:
        eprint(str(e))
        return 2
    except (ValueError, RuntimeError) as e:
        eprint(f"Error: {e}")
        return 1

    if args.dry_run:
        # Print a short preview for review without implying execution
        tasks = result.data.get("tasks", [])
        print(f"Generated {result.task_count} tasks in {result.path}:")
        for t in tasks[:10]:
            print(f"- {t.get('id')}: {t.get('title')}")
        if len(tasks) > 10:
            print(f"... and {len(tasks) - 10} more")
        return 0

    print(f"✓ Wrote tasks: {result.path}")
    print("Next: review it, then run `ralph run --prd-json .ralph/prd.json --dry-run`")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ralph", description="Ralph Orchestrator CLI")
    p.add_argument("-V", "--version", action="version", version=f"ralph {__version__}")
    p.add_argument("-c", "--config", default=None, help="Path to .ralph/ralph.yml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Initialize repo (.ralph templates)")
    sp.add_argument("-t", "--template", default="auto", choices=["auto", "minimal", "python", "node", "fullstack"])
    sp.add_argument("-f", "--force", action="store_true")
    sp.add_argument("--no-agents-md", action="store_true")
    sp.add_argument("--no-prd", action="store_true")
    sp.add_argument("-o", "--output-dir", default=".ralph")
    sp.set_defaults(func=command_init)

    sp = sub.add_parser("scan", help="Check environment/tools/config")
    sp.add_argument("--fix", action="store_true", help="(not implemented) print install instructions")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=command_scan)

    sp = sub.add_parser("run", help="Run verified task loop")
    sp.add_argument("-p", "--prd-json", default=None, help="Path to prd.json task file")
    sp.add_argument("-t", "--task", default=None, help="Run only specific task ID")
    sp.add_argument("--from-task", default=None, help="Start from specific task ID")
    sp.add_argument("--max-iterations", type=int, default=200, help="Maximum task loop iterations")
    sp.add_argument("--gates", default="full", choices=["build", "full", "none"], help="Gate level to run")
    sp.add_argument("--dry-run", action="store_true", help="Parse tasks, don't execute")
    sp.add_argument("--resume", action="store_true", help="Resume from existing session")
    sp.add_argument("--post-verify", action="store_true", default=True, help="Run post-completion verification")
    sp.add_argument("--no-post-verify", action="store_false", dest="post_verify", help="Skip post-completion verification")
    # UI test control flags
    sp.add_argument("--with-smoke", action="store_true", default=None, dest="with_smoke",
        help="Run smoke tests (agent-browser) for frontend tasks")
    sp.add_argument("--no-smoke", action="store_false", dest="with_smoke",
        help="Skip smoke tests even for frontend tasks")
    sp.add_argument("--with-robot", action="store_true", default=None, dest="with_robot",
        help="Run Robot Framework tests for frontend tasks")
    sp.add_argument("--no-robot", action="store_false", dest="with_robot",
        help="Skip Robot Framework tests")
    # Parallel execution flags
    sp.add_argument("--parallel", action="store_true", default=False,
        help="Run tasks in parallel when possible (using file-set pre-allocation)")
    sp.add_argument("--max-parallel", type=int, default=3,
        help="Maximum number of parallel task groups (default: 3)")
    sp.set_defaults(func=command_run)

    sp = sub.add_parser("verify", help="Run post-completion verification")
    sp.add_argument("--gates", default="full", choices=["build", "full", "none"], help="Gate level to run")
    sp.add_argument("--ui", action="store_true", default=None, dest="ui", help="Run UI tests")
    sp.add_argument("--no-ui", action="store_false", dest="ui", help="Skip UI tests")
    sp.add_argument("--robot", action="store_true", default=None, dest="robot", help="Run Robot tests")
    sp.add_argument("--no-robot", action="store_false", dest="robot", help="Skip Robot tests")
    sp.add_argument("--env", default="dev", choices=["dev", "prod"], help="Environment mode")
    sp.add_argument("--fix", action="store_true", help="Attempt to fix failures")
    sp.add_argument("--fix-iterations", type=int, default=10, help="Max fix iterations")
    sp.add_argument("--skip-services", action="store_true", help="Skip service startup (use existing)")
    sp.add_argument("--base-url", default=None, help="Override base URL for tests")
    sp.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    sp.set_defaults(func=command_verify)

    sp = sub.add_parser("autopilot", help="Report→PRD→tasks→run pipeline")
    sp.add_argument("-r", "--reports", default=None, help="Directory containing reports")
    sp.add_argument("--report", default=None, help="Specific report file to use")
    sp.add_argument("--dry-run", action="store_true", help="Analyze only, don't execute")
    sp.add_argument("--create-pr", action="store_true", default=None, dest="create_pr", help="Create PR on completion")
    sp.add_argument("--no-create-pr", action="store_false", dest="create_pr", help="Skip PR creation")
    sp.add_argument("-b", "--branch", default=None, help="Branch name to use")
    sp.add_argument("--no-prd", action="store_true", help="Skip PRD generation (use existing tasks)")
    sp.add_argument("--prd-mode", default=None, choices=["autonomous", "interactive"], help="PRD generation mode")
    sp.add_argument("--task-count", default=None, help="Target task count (e.g., '8-15' or '10')")
    sp.add_argument("--analysis-model", default=None, help="Model for analysis phase")
    sp.add_argument("--recent-days", type=int, default=None, help="Exclude items fixed in last N days")
    sp.add_argument("--resume", action="store_true", help="Resume last incomplete run")
    sp.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    # Research control flags
    sp.add_argument("--with-research", action="store_true", default=None, dest="with_research",
        help="Enable research phase for PRD generation (default: on)")
    sp.add_argument("--no-research", action="store_false", dest="with_research",
        help="Skip research phase")
    sp.add_argument("--research-backend", action="store_true", dest="research_backend",
        help="Enable backend research only")
    sp.add_argument("--research-frontend", action="store_true", dest="research_frontend",
        help="Enable frontend research only")
    sp.add_argument("--research-web", action="store_true", dest="research_web",
        help="Enable web research only")
    sp.set_defaults(func=command_autopilot)

    sp = sub.add_parser("chat", help="Open Claude Code chat and save a markdown doc")
    sp.add_argument(
        "--mode",
        default="change-request",
        choices=["change-request", "prd", "free"],
        help="Which kind of document Claude should produce",
    )
    sp.add_argument(
        "--template",
        default=None,
        help="Optional path to a .claude command markdown file to use as guidance",
    )
    sp.add_argument(
        "--out",
        default=None,
        help="Output markdown file to write (default: changes/ or tasks/ with timestamp)",
    )
    sp.add_argument(
        "--model",
        default="sonnet",
        help="Claude model alias/name passed to Claude CLI (e.g. sonnet, opus)",
    )
    sp.add_argument(
        "--auto-exit",
        action="store_true",
        default=True,
        help="Automatically exit chat once the output file is written (default: on)",
    )
    sp.add_argument(
        "--no-auto-exit",
        action="store_false",
        dest="auto_exit",
        help="Do not auto-exit after writing the output file",
    )
    sp.set_defaults(func=command_chat)

    sp = sub.add_parser("tasks", help="Generate prd.json tasks from a markdown doc")
    sp.add_argument("--from", dest="from_markdown", required=True, help="Source markdown (CR/PRD) file")
    sp.add_argument("--out", default=None, help="Output prd.json path (default: .ralph/prd.json)")
    sp.add_argument("--branch", default=None, help="branchName to write into prd.json")
    sp.add_argument("--task-count", default="auto", help="Target task count: 'auto' (AI analyzes complexity), or explicit range (e.g., '8-15' or '10')")
    sp.add_argument("--model", default="sonnet", help="Claude model (e.g. sonnet, opus)")
    sp.add_argument("--dry-run", action="store_true", help="Write file then print a short preview")
    sp.set_defaults(func=command_tasks)

    sp = sub.add_parser("validate-tasks", help="Validate prd.json against schema")
    sp.add_argument("--path", default=None, help="Path to prd.json (default: .ralph/prd.json)")
    sp.set_defaults(func=command_validate_tasks)

    # Serve command - starts the FastAPI web server
    sp = sub.add_parser("serve", help="Start the Ralph web UI server")
    sp.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port to run the server on (default: 3000)",
    )
    sp.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    sp.add_argument(
        "--projects-root",
        default=None,
        help="Root directory to scan for projects (default: current directory)",
    )
    sp.add_argument(
        "--open",
        action="store_true",
        help="Auto-open browser to the web UI",
    )
    sp.add_argument(
        "--remote",
        action="store_true",
        help="Allow remote connections (binds to 0.0.0.0). WARNING: This exposes the server to your network.",
    )
    sp.set_defaults(func=command_serve)

    # Flow command with subcommands
    sp_flow = sub.add_parser("flow", help="One-command flows (chat→tasks→validate→run)")
    flow_sub = sp_flow.add_subparsers(dest="flow_mode", required=True)
    
    # Common flow arguments (added to both subcommands)
    def add_common_flow_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--task-count",
            default="auto",
            help="Target task count: 'auto' (AI analyzes complexity), or explicit range (e.g., '8-15' or '10')",
        )
        parser.add_argument(
            "--model",
            default="sonnet",
            help="Claude model for chat and task generation (e.g., sonnet, opus)",
        )
        parser.add_argument(
            "--out-md",
            default=None,
            help="Override markdown output path",
        )
        parser.add_argument(
            "--out-json",
            default=None,
            help="Override prd.json output path (default: .ralph/prd.json)",
        )
        parser.add_argument(
            "-y", "--yes",
            action="store_true",
            help="Skip approval prompt (auto-approve)",
        )
        parser.add_argument(
            "--max-iterations",
            type=int,
            default=30,
            help="Maximum task loop iterations",
        )
        parser.add_argument(
            "--gates",
            default="full",
            choices=["build", "full", "none"],
            help="Gate level to run",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Generate tasks but don't execute",
        )
        parser.add_argument(
            "-v", "--verbose",
            action="store_true",
            help="Verbose output",
        )
    
    # Flow change subcommand
    sp_flow_change = flow_sub.add_parser(
        "change",
        help="Change request flow: chat→tasks→validate→approval→run",
    )
    add_common_flow_args(sp_flow_change)
    sp_flow_change.set_defaults(func=command_flow)
    
    # Flow new subcommand
    sp_flow_new = flow_sub.add_parser(
        "new",
        help="New project flow: init→chat→tasks→validate→approval→run",
    )
    add_common_flow_args(sp_flow_new)
    sp_flow_new.add_argument(
        "-t", "--template",
        default="auto",
        choices=["auto", "minimal", "python", "node", "fullstack"],
        help="Project template for init (default: auto-detect)",
    )
    sp_flow_new.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite existing files during init",
    )
    sp_flow_new.set_defaults(func=command_flow)

    return p


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    rc = int(args.func(args))
    raise SystemExit(rc)

