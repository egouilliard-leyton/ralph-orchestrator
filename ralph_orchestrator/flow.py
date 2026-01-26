"""Flow coordinator for Ralph one-command pipelines.

Provides two flows:
- Change flow: chat → tasks → validate → approval → run
- New project flow: init → chat → tasks → validate → approval → run
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chat import run_chat, ChatOptions, ChatError
from .cli import (
    eprint,
    generate_tasks_from_markdown,
    load_prd_json,
)
from .run import run_tasks, RunOptions, RunResult


class FlowError(Exception):
    """Error raised during flow execution."""
    pass


@dataclass
class FlowOptions:
    """Options for flow execution."""
    # Mode: "change" or "new"
    mode: str = "change"
    
    # Task generation options
    task_count: str = "auto"
    model: str = "sonnet"
    
    # Output paths
    out_md: Optional[str] = None
    out_json: Optional[str] = None
    
    # Approval options
    skip_approval: bool = False
    
    # New project specific
    template: str = "auto"
    force: bool = False
    
    # Run options
    max_iterations: int = 200
    gate_type: str = "full"
    dry_run: bool = False
    verbose: bool = False


@dataclass
class FlowResult:
    """Result of a flow execution."""
    success: bool
    md_path: Optional[Path] = None
    json_path: Optional[Path] = None
    tasks_count: int = 0
    run_result: Optional[RunResult] = None
    error: Optional[str] = None
    aborted_at: Optional[str] = None  # Stage where flow was aborted


def _print_header(title: str) -> None:
    """Print a formatted header."""
    print()
    print("═" * 60)
    print(f"  {title}")
    print("═" * 60)


def _print_step(step: int, total: int, description: str) -> None:
    """Print a step indicator."""
    print(f"\n[{step}/{total}] {description}")
    print("-" * 60)


def _prompt_approval(
    md_path: Path,
    json_path: Path,
    tasks: List[Dict[str, Any]],
) -> bool:
    """Prompt user for approval before running tasks.
    
    Returns True if approved, False if declined.
    """
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " REVIEW BEFORE EXECUTION".center(58) + "│")
    print("├" + "─" * 58 + "┤")
    print(f"│  Source markdown: {str(md_path)[:38]}".ljust(59) + "│")
    print(f"│  Task file:       {str(json_path)[:38]}".ljust(59) + "│")
    print(f"│  Task count:      {len(tasks)}".ljust(59) + "│")
    print("├" + "─" * 58 + "┤")
    print("│" + " Tasks preview:".ljust(58) + "│")
    
    for t in tasks[:10]:
        task_id = t.get("id", "?")
        title = t.get("title", "Untitled")
        line = f"  {task_id}: {title}"
        if len(line) > 56:
            line = line[:53] + "..."
        print(f"│{line}".ljust(59) + "│")
    
    if len(tasks) > 10:
        print(f"│  ... and {len(tasks) - 10} more tasks".ljust(59) + "│")
    
    print("└" + "─" * 58 + "┘")
    print()
    
    if not sys.stdin.isatty():
        eprint("Cannot prompt for approval in non-interactive mode. Use --yes to skip.")
        return False
    
    try:
        response = input("Proceed with execution? [y/N] ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def _run_init(template: str, force: bool) -> bool:
    """Run ralph init for new project flow.
    
    Returns True on success, False on failure.
    """
    from .cli import command_init
    import argparse
    
    # Create a mock args namespace
    args = argparse.Namespace(
        template=template,
        force=force,
        no_agents_md=False,
        no_prd=True,  # We'll generate PRD from chat
        output_dir=".ralph",
    )
    
    print(f"  Initializing Ralph configuration (template: {template})...")
    rc = command_init(args)
    return rc == 0


def run_flow_change(
    repo_root: Path,
    options: FlowOptions,
) -> FlowResult:
    """Run the change flow: chat → tasks → validate → approval → run.
    
    Args:
        repo_root: Repository root directory.
        options: Flow options.
        
    Returns:
        FlowResult with outcome.
    """
    _print_header("RALPH FLOW: CHANGE REQUEST")
    
    total_steps = 4 if options.dry_run else 5
    
    # Step 1: Interactive chat to create change request
    _print_step(1, total_steps, "Create Change Request (Claude Chat)")
    
    chat_options = ChatOptions(
        mode="change-request",
        template=None,  # Will auto-discover .claude/commands/create-change-request.md
        out=options.out_md,
        model=options.model,
        auto_exit=True,
    )
    
    try:
        md_path = run_chat(repo_root=repo_root, options=chat_options)
        print(f"  ✓ Change request saved: {md_path}")
    except ChatError as e:
        return FlowResult(
            success=False,
            error=str(e),
            aborted_at="chat",
        )
    
    # Step 2: Generate tasks
    _print_step(2, total_steps, "Generate Tasks")
    
    json_path = Path(options.out_json) if options.out_json else Path(".ralph/prd.json")
    if not json_path.is_absolute():
        json_path = repo_root / json_path
    
    try:
        gen_result = generate_tasks_from_markdown(
            src=md_path,
            out=json_path,
            task_count=options.task_count,
            model=options.model,
            verbose=True,
        )
        tasks = gen_result.data.get("tasks", [])
        print(f"  ✓ Generated {gen_result.task_count} tasks: {json_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        return FlowResult(
            success=False,
            md_path=md_path,
            error=str(e),
            aborted_at="tasks",
        )
    
    # Step 3: Validate
    _print_step(3, total_steps, "Validate Tasks")
    
    try:
        validated_prd = load_prd_json(json_path)
        print(f"  ✓ Tasks validated against schema")
    except Exception as e:
        return FlowResult(
            success=False,
            md_path=md_path,
            json_path=json_path,
            tasks_count=len(tasks),
            error=f"Validation failed: {e}",
            aborted_at="validate",
        )
    
    # Step 4: Approval
    _print_step(4, total_steps, "Review & Approval")
    
    if options.skip_approval:
        print("  Skipping approval (--yes flag)")
        approved = True
    else:
        approved = _prompt_approval(md_path, json_path, tasks)
    
    if not approved:
        print("  ⚠ Execution cancelled by user")
        return FlowResult(
            success=True,  # Flow completed, just didn't run
            md_path=md_path,
            json_path=json_path,
            tasks_count=len(tasks),
            aborted_at="approval",
        )
    
    # Step 5: Run tasks
    if options.dry_run:
        print("\n  Dry run mode - skipping execution")
        return FlowResult(
            success=True,
            md_path=md_path,
            json_path=json_path,
            tasks_count=len(tasks),
        )
    
    _print_step(5, total_steps, "Execute Tasks")
    
    run_options = RunOptions(
        prd_json=str(json_path),
        max_iterations=options.max_iterations,
        gate_type=options.gate_type,
        dry_run=False,
        verbose=options.verbose,
    )
    
    run_result = run_tasks(
        config_path=repo_root / ".ralph/ralph.yml",
        prd_path=json_path,
        options=run_options,
    )
    
    success = run_result.exit_code.value == 0
    
    return FlowResult(
        success=success,
        md_path=md_path,
        json_path=json_path,
        tasks_count=len(tasks),
        run_result=run_result,
        error=run_result.error if not success else None,
    )


def run_flow_new(
    repo_root: Path,
    options: FlowOptions,
) -> FlowResult:
    """Run the new project flow: init → chat → tasks → validate → approval → run.
    
    Args:
        repo_root: Repository root directory.
        options: Flow options.
        
    Returns:
        FlowResult with outcome.
    """
    _print_header("RALPH FLOW: NEW PROJECT")
    
    total_steps = 5 if options.dry_run else 6
    
    # Step 1: Initialize Ralph
    _print_step(1, total_steps, "Initialize Ralph Configuration")
    
    if not _run_init(options.template, options.force):
        return FlowResult(
            success=False,
            error="Failed to initialize Ralph configuration",
            aborted_at="init",
        )
    print("  ✓ Ralph initialized")
    
    # Step 2: Interactive chat to create PRD
    _print_step(2, total_steps, "Create PRD (Claude Chat)")
    
    chat_options = ChatOptions(
        mode="prd",
        template=None,  # Will auto-discover .claude/commands/create-prd.md
        out=options.out_md,
        model=options.model,
        auto_exit=True,
    )
    
    try:
        md_path = run_chat(repo_root=repo_root, options=chat_options)
        print(f"  ✓ PRD saved: {md_path}")
    except ChatError as e:
        return FlowResult(
            success=False,
            error=str(e),
            aborted_at="chat",
        )
    
    # Step 3: Generate tasks
    _print_step(3, total_steps, "Generate Tasks")
    
    json_path = Path(options.out_json) if options.out_json else Path(".ralph/prd.json")
    if not json_path.is_absolute():
        json_path = repo_root / json_path
    
    try:
        gen_result = generate_tasks_from_markdown(
            src=md_path,
            out=json_path,
            task_count=options.task_count,
            model=options.model,
            verbose=True,
        )
        tasks = gen_result.data.get("tasks", [])
        print(f"  ✓ Generated {gen_result.task_count} tasks: {json_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        return FlowResult(
            success=False,
            md_path=md_path,
            error=str(e),
            aborted_at="tasks",
        )
    
    # Step 4: Validate
    _print_step(4, total_steps, "Validate Tasks")
    
    try:
        validated_prd = load_prd_json(json_path)
        print(f"  ✓ Tasks validated against schema")
    except Exception as e:
        return FlowResult(
            success=False,
            md_path=md_path,
            json_path=json_path,
            tasks_count=len(tasks),
            error=f"Validation failed: {e}",
            aborted_at="validate",
        )
    
    # Step 5: Approval
    _print_step(5, total_steps, "Review & Approval")
    
    if options.skip_approval:
        print("  Skipping approval (--yes flag)")
        approved = True
    else:
        approved = _prompt_approval(md_path, json_path, tasks)
    
    if not approved:
        print("  ⚠ Execution cancelled by user")
        return FlowResult(
            success=True,  # Flow completed, just didn't run
            md_path=md_path,
            json_path=json_path,
            tasks_count=len(tasks),
            aborted_at="approval",
        )
    
    # Step 6: Run tasks
    if options.dry_run:
        print("\n  Dry run mode - skipping execution")
        return FlowResult(
            success=True,
            md_path=md_path,
            json_path=json_path,
            tasks_count=len(tasks),
        )
    
    _print_step(6, total_steps, "Execute Tasks")
    
    run_options = RunOptions(
        prd_json=str(json_path),
        max_iterations=options.max_iterations,
        gate_type=options.gate_type,
        dry_run=False,
        verbose=options.verbose,
    )
    
    run_result = run_tasks(
        config_path=repo_root / ".ralph/ralph.yml",
        prd_path=json_path,
        options=run_options,
    )
    
    success = run_result.exit_code.value == 0
    
    return FlowResult(
        success=success,
        md_path=md_path,
        json_path=json_path,
        tasks_count=len(tasks),
        run_result=run_result,
        error=run_result.error if not success else None,
    )


def run_flow(
    repo_root: Path,
    options: FlowOptions,
) -> FlowResult:
    """Run the appropriate flow based on mode.
    
    Args:
        repo_root: Repository root directory.
        options: Flow options.
        
    Returns:
        FlowResult with outcome.
    """
    if options.mode == "new":
        return run_flow_new(repo_root, options)
    else:
        return run_flow_change(repo_root, options)
