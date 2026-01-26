"""Interactive Claude Code launcher for Ralph.

Goal: open a *real* Claude Code interactive session (one continuous chat)
to help a user think through changes, and have Claude write a markdown
document (PRD or Change Request) to a target file path.

This intentionally does NOT "ping Claude" for each user message — it
launches the Claude CLI in interactive mode.
"""

from __future__ import annotations

import os
import shlex
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import subprocess


class ChatError(Exception):
    pass


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _strip_front_matter(md: str) -> str:
    """Remove YAML front matter if present (--- ... --- at top)."""
    lines = md.splitlines()
    if not lines or lines[0].strip() != "---":
        return md
    # find second ---
    for i in range(1, min(len(lines), 2000)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).lstrip()
    return md


def _load_template(repo_root: Path, template_path: Optional[str], mode: str) -> str:
    """Load a template prompt (repo-local .claude command or built-in fallback)."""
    if template_path:
        p = Path(template_path)
        if not p.is_absolute():
            p = repo_root / p
        if not p.exists():
            raise ChatError(f"Template not found: {p}")
        return _strip_front_matter(p.read_text(encoding="utf-8", errors="replace"))

    # Auto-discover common repo-local templates
    candidates: List[Path] = []
    if mode == "prd":
        candidates.append(repo_root / ".claude/commands/create-prd.md")
    if mode == "change-request":
        candidates.append(repo_root / ".claude/commands/create-change-request.md")

    for c in candidates:
        if c.exists():
            return _strip_front_matter(c.read_text(encoding="utf-8", errors="replace"))

    # Built-in fallbacks (short on purpose)
    if mode == "prd":
        return (
            "You are a supportive product manager. Ask clarifying questions one at a time.\n"
            "Goal: produce a clear PRD in markdown with goals, scope, and acceptance criteria.\n"
        )
    if mode == "change-request":
        return (
            "You are a supportive technical lead. Ask clarifying questions one at a time.\n"
            "Goal: produce a Change Request in markdown describing what to change in an existing codebase,\n"
            "including current vs desired behavior, affected areas, testing plan, and acceptance criteria.\n"
        )
    return "You are a helpful assistant. Ask questions to clarify the user's intent.\n"


def _default_out_path(repo_root: Path, mode: str) -> Path:
    stamp = _utc_stamp()
    if mode == "prd":
        return repo_root / "tasks" / f"prd-chat-{stamp}.md"
    if mode == "change-request":
        return repo_root / "changes" / f"CR-chat-{stamp}.md"
    return repo_root / "notes" / f"chat-{stamp}.md"


def _claude_cmd_base() -> List[str]:
    cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
    argv = shlex.split(cmd) if cmd else ["claude"]
    if not argv:
        argv = ["claude"]
    return argv


def _claude_interactive_cmd_base() -> List[str]:
    """Return a safe base command for interactive Claude Code.

    Users sometimes set RALPH_CLAUDE_CMD to include `--print` (for automation/tests).
    Interactive mode must NOT include `--print` or output-format flags.
    """
    cmd = os.environ.get("RALPH_CLAUDE_INTERACTIVE_CMD") or os.environ.get("RALPH_CLAUDE_CMD") or "claude"
    argv = shlex.split(cmd) if cmd else ["claude"]
    if not argv:
        return ["claude"]

    exe = argv[0]
    flags = set(argv[1:])

    # If the base includes print/structured flags, strip down to just executable.
    if (
        "--print" in flags
        or "-p" in flags
        or "--output-format" in flags
        or "--json-schema" in flags
        or "--input-format" in flags
    ):
        return [exe]

    return argv


def _build_system_prompt(template: str, mode: str, out_path: Path) -> str:
    """Create an appended system prompt for an interactive Claude session."""
    mode_label = "Change Request" if mode == "change-request" else ("PRD" if mode == "prd" else "markdown note")
    rel = out_path.as_posix()
    return (
        template.strip()
        + "\n\n"
        + "IMPORTANT:\n"
        + f"- You are helping the user create a {mode_label}.\n"
        + f"- When you have enough information, write the final document to: {rel}\n"
        + "- Ask questions one at a time until you can write a solid document.\n"
        + "- Do not wait for further confirmation once requirements are clear — write the file.\n"
    )


@dataclass
class ChatOptions:
    mode: str = "change-request"  # prd | change-request | free
    template: Optional[str] = None
    out: Optional[str] = None
    model: str = "sonnet"
    auto_exit: bool = True
    auto_exit_stable_seconds: float = 2.0
    auto_exit_min_chars: int = 80


def run_chat(repo_root: Path, options: ChatOptions) -> Path:
    """Launch Claude Code interactive session and return saved file path.

    This launches `claude` *without* `--print`, so the user gets a normal
    Claude Code experience (single continuous conversation).
    """
    mode = options.mode
    template = _load_template(repo_root, options.template, mode)
    out_path = Path(options.out) if options.out else _default_out_path(repo_root, mode)
    if not out_path.is_absolute():
        out_path = repo_root / out_path

    if not sys.stdin.isatty():
        raise ChatError(
            "ralph chat needs an interactive terminal (TTY).\n"
            "Run it from your terminal (not from a non-interactive runner)."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    system_prompt = _build_system_prompt(template, mode, out_path)
    cmd = _claude_interactive_cmd_base() + [
        "--append-system-prompt",
        system_prompt,
        "--model",
        options.model,
        "--add-dir",
        str(repo_root),
    ]

    print("════════════════════════════════════════════════════════════")
    print("  RALPH CHAT (Claude Code)")
    print("════════════════════════════════════════════════════════════")
    print(f"Mode: {mode}")
    print(f"Output file: {out_path}")
    print("")
    print("Claude will open in interactive mode.")
    if options.auto_exit:
        print("When Claude writes the output file, Ralph will auto-exit the chat.")
        print("If you prefer to keep chatting after the file is written, run with: --no-auto-exit")
    else:
        print("When you're done, ask Claude to write the document to the output file above, then exit Claude.")
    print("────────────────────────────────────────────────────────────")

    start_ts = time.time()
    initial_exists = out_path.exists()
    initial_stat = out_path.stat() if initial_exists else None

    try:
        # Start Claude in its own process group so we can terminate it cleanly.
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            preexec_fn=os.setsid,
        )
    except FileNotFoundError as e:
        raise ChatError(f"Claude CLI not found: {e}")

    def _file_ready() -> bool:
        if not out_path.exists():
            return False
        try:
            st = out_path.stat()
            # If the file existed before launch, require it to be modified during this session.
            if initial_stat and st.st_mtime <= initial_stat.st_mtime:
                return False
            if st.st_mtime < start_ts:
                return False
            txt = out_path.read_text(encoding="utf-8", errors="replace").strip()
            return len(txt) >= options.auto_exit_min_chars
        except Exception:
            return False

    def _file_stable_for(seconds: float) -> bool:
        """Check file has stopped changing for N seconds."""
        if not out_path.exists():
            return False
        try:
            st1 = out_path.stat()
        except Exception:
            return False
        t_end = time.time() + seconds
        while time.time() < t_end:
            time.sleep(0.25)
            try:
                st2 = out_path.stat()
            except Exception:
                return False
            if st2.st_mtime != st1.st_mtime or st2.st_size != st1.st_size:
                return False
        return True

    # Watcher loop: auto-exit when file is created and stable.
    auto_exit_triggered = False
    while True:
        rc = proc.poll()
        if rc is not None:
            break

        if options.auto_exit and (not auto_exit_triggered):
            if _file_ready() and _file_stable_for(options.auto_exit_stable_seconds):
                auto_exit_triggered = True
                print("\n✓ Detected output file written. Closing Claude session...")
                try:
                    os.killpg(proc.pid, signal.SIGINT)
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                # Give Claude a moment to exit gracefully
                for _ in range(20):
                    time.sleep(0.25)
                    if proc.poll() is not None:
                        break
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except Exception:
                        pass
        else:
            time.sleep(0.25)

    if rc != 0 and not (options.auto_exit and auto_exit_triggered):
        raise ChatError(f"Claude session exited with code {rc}")

    if not out_path.exists() or len(out_path.read_text(encoding='utf-8', errors='replace').strip()) < 50:
        raise ChatError(
            f"Claude session ended but the output file wasn't created (or is empty): {out_path}\n"
            "In Claude, explicitly ask it to write the final markdown file to that path before exiting."
        )

    return out_path

