"""Autopilot pipeline for Ralph orchestrator.

Implements the full autopilot self-improvement pipeline:
1. Report discovery - find and select reports
2. Report analysis - LLM-based priority selection
3. Branch management - create feature branches
4. PRD generation - generate product requirements
5. Task generation - convert PRD to tasks
6. Verified execution - run task loop
7. PR creation - create pull request

Usage:
    from ralph_orchestrator.autopilot import run_autopilot, AutopilotOptions
    
    result = run_autopilot(
        config_path=Path(".ralph/ralph.yml"),
        options=AutopilotOptions(dry_run=True),
    )
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import RalphConfig, AutopilotConfig, load_config
from .exec import run_command, ExecResult, CommandRunner
from .timeline import TimelineLogger, create_timeline_logger


# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_REPORTS_DIR = "./reports"
DEFAULT_BRANCH_PREFIX = "ralph/"
SUPPORTED_REPORT_EXTENSIONS = [".md", ".txt", ".json", ".html"]
MAX_REPORT_SIZE_BYTES = 1_000_000  # 1MB


# ============================================================
# ERROR CLASSES
# ============================================================

class AutopilotError(Exception):
    """Base exception for autopilot errors."""
    pass


class ReportDiscoveryError(AutopilotError):
    """Error during report discovery."""
    pass


class AnalysisError(AutopilotError):
    """Error during report analysis."""
    pass


class BranchError(AutopilotError):
    """Error during branch operations."""
    pass


class PRDGenerationError(AutopilotError):
    """Error during PRD generation."""
    pass


class TasksGenerationError(AutopilotError):
    """Error during task generation."""
    pass


class PRCreationError(AutopilotError):
    """Error during PR creation."""
    pass


# ============================================================
# ENUMS
# ============================================================

class RunStatus(str, Enum):
    """Status of an autopilot run."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    BRANCHING = "branching"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    PUSHING = "pushing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class AnalysisProvider(str, Enum):
    """LLM provider for analysis."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    GATEWAY = "gateway"
    CLAUDE_CLI = "claude_cli"


class ExitCode(int, Enum):
    """Exit codes for autopilot command."""
    SUCCESS = 0
    CONFIG_ERROR = 1
    NO_REPORTS = 10
    ANALYSIS_FAILED = 11
    PRD_GENERATION_FAILED = 12
    TASK_GENERATION_FAILED = 13
    GIT_ERROR = 14
    PR_CREATION_FAILED = 15
    EXECUTION_FAILED = 3
    USER_ABORT = 7


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class ReportInfo:
    """Information about a discovered report."""
    path: Path
    name: str
    modified_at: datetime
    size_bytes: int
    extension: str


@dataclass
class AnalysisOutput:
    """Output from report analysis phase."""
    priority_item: str
    description: str
    rationale: str
    acceptance_criteria: List[str]
    branch_name: str
    analysis_timestamp: datetime
    source_report: str
    excluded_items: List[Dict[str, str]] = field(default_factory=list)
    model_used: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class AutopilotRun:
    """State of an autopilot run."""
    run_id: str
    started_at: datetime
    status: RunStatus
    completed_at: Optional[datetime] = None
    
    # Phase outputs
    report_path: Optional[str] = None
    analysis_path: Optional[str] = None
    prd_path: Optional[str] = None
    tasks_path: Optional[str] = None
    
    # Git state
    branch_name: Optional[str] = None
    base_commit: Optional[str] = None
    
    # Execution state
    session_id: Optional[str] = None
    tasks_completed: int = 0
    tasks_total: int = 0
    
    # PR state
    pr_created: bool = False
    pr_url: Optional[str] = None
    
    # Error state
    failure_reason: Optional[str] = None
    failure_phase: Optional[str] = None


@dataclass
class AutopilotOptions:
    """Options for autopilot command."""
    reports_dir: Optional[str] = None
    report_path: Optional[str] = None
    dry_run: bool = False
    create_pr: Optional[bool] = None  # None means use config
    branch_name: Optional[str] = None
    skip_prd: bool = False
    prd_mode: Optional[str] = None  # autonomous | interactive
    task_count_min: Optional[int] = None
    task_count_max: Optional[int] = None
    analysis_model: Optional[str] = None
    recent_days: Optional[int] = None
    resume: bool = False
    verbose: bool = False


@dataclass
class AutopilotResult:
    """Result of autopilot execution."""
    exit_code: ExitCode
    run_id: Optional[str] = None
    dry_run: bool = False
    analysis: Optional[AnalysisOutput] = None
    branch_name: Optional[str] = None
    prd_path: Optional[str] = None
    tasks_path: Optional[str] = None
    tasks_completed: int = 0
    tasks_total: int = 0
    pr_url: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# PROMPT TEMPLATES
# ============================================================

ANALYSIS_PROMPT_TEMPLATE = """You are analyzing a daily report for a software product.

Read this report and identify the #1 most actionable item that should be worked on TODAY.

CONSTRAINTS:
- Must NOT require database migrations (no schema changes)
- Must be completable in a few hours of focused work
- Must be a clear, specific task (not vague like 'improve conversion')
- Prefer fixes over new features
- Prefer high-impact, low-effort items
- Focus on UI/UX improvements, copy changes, bug fixes, or configuration changes
- IMPORTANT: Do NOT pick items that appear in the 'Recently Fixed' section below
{recent_fixes}

REPORT:
{report_content}

Respond with ONLY a JSON object (no markdown, no code fences, no explanation):
{{
  "priority_item": "Brief title of the item (max 100 chars)",
  "description": "2-3 sentence description of what needs to be done",
  "rationale": "Why this is the #1 priority based on the report",
  "acceptance_criteria": ["List of 3-5 specific, verifiable criteria"],
  "estimated_tasks": 8,
  "branch_name": "kebab-case-feature-name"
}}"""

PRD_PROMPT_TEMPLATE = """Create a PRD for: {priority_item}

Description: {description}

Rationale from report analysis: {rationale}

Acceptance criteria from analysis:
{acceptance_criteria}

IMPORTANT CONSTRAINTS:
- NO database migrations or schema changes
- Keep scope small - this should be completable in 2-4 hours
- Break into 8-12 small tasks maximum
- Each task must be verifiable with quality checks and/or browser testing
- DO NOT ask clarifying questions - you have enough context to proceed
- Generate the PRD immediately without waiting for user input

PRD STRUCTURE:
1. Introduction/Overview - Brief description of the feature
2. Goals - Specific, measurable objectives (bullet list)
3. Tasks - Each task needs:
   - Title (T-001, T-002, etc.)
   - Description
   - Acceptance Criteria (verifiable checklist)
4. Functional Requirements - Numbered list (FR-1, FR-2, etc.)
5. Non-Goals - What this will NOT include
6. Success Metrics - How success is measured

TASK GUIDELINES:
- Each task must be completable in one focused session
- Acceptance criteria must be boolean pass/fail (not vague)
- For UI tasks, always include browser verification criteria
- Use action verbs: "Add", "Update", "Fix", "Configure"

Save the PRD to: {output_path}"""

TASKS_PROMPT_TEMPLATE = """Convert the PRD at {prd_path} to {output_path}

Use branch name: {branch_name}

TARGET: {min_tasks}-{max_tasks} granular tasks

CRITICAL RULES:
1. Each task does ONE thing only
2. Investigation tasks separated from implementation tasks
3. Every acceptance criterion is boolean pass/fail
4. No vague words: "review", "identify", "document", "verify it works"
5. Commands must specify expected exit code (e.g., "exits with code 0")
6. Browser actions must specify expected result
7. All tasks start with passes: false
8. Priority order reflects dependencies (lower = earlier)

TASK GRANULARITY:
- Check one configuration file → 1 task
- Test one user interaction → 1 task  
- Make one code change → 1 task
- Verify on one viewport → 1 task

ACCEPTANCE CRITERIA PATTERNS:
- Command: "Run `npm test` - exits with code 0"
- File check: "File `src/auth/config.ts` contains `redirectUrl: '/onboarding'`"
- Browser: "agent-browser: open /login - SignIn component renders"
- Browser action: "agent-browser: click 'Submit' button - redirects to /dashboard"

PRIORITY ORDERING:
1-3: Investigation tasks
4-5: Schema/database changes
6-7: Backend logic changes  
8-9: UI component changes
10+: Verification tasks

OUTPUT FORMAT (write to {output_path}):
```json
{{
  "project": "Project Name",
  "branchName": "{branch_name}",
  "description": "One-line description",
  "tasks": [
    {{
      "id": "T-001",
      "title": "Specific action verb + target",
      "description": "1-2 sentences",
      "acceptanceCriteria": ["Boolean criterion 1", "Boolean criterion 2"],
      "priority": 1,
      "passes": false,
      "notes": ""
    }}
  ]
}}
```

Read the PRD and generate prd.json immediately. Do not ask questions."""


# ============================================================
# UTILITIES
# ============================================================

def utc_now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_run_id() -> str:
    """Generate unique run identifier."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand = secrets.token_hex(4)
    return f"{ts}-{rand}"


def normalize_branch_name(name: str, prefix: str) -> str:
    """Ensure branch name has correct prefix and format."""
    # Remove any existing prefix
    cleaned = re.sub(r'^[a-zA-Z]+/', '', name)
    # Convert to kebab case
    cleaned = re.sub(r'[^a-zA-Z0-9/-]', '-', cleaned.lower())
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    # Add prefix
    if not cleaned.startswith(prefix):
        return f"{prefix}{cleaned}"
    return cleaned


def extract_feature_name(branch_name: str) -> str:
    """Extract feature name from branch (remove prefix)."""
    return re.sub(r'^[a-zA-Z]+/', '', branch_name)


# ============================================================
# REPORT DISCOVERY
# ============================================================

class ReportDiscovery:
    """Discovers and selects reports for analysis."""
    
    def __init__(
        self,
        reports_dir: Path,
        processed_reports: Optional[List[str]] = None,
    ):
        """Initialize with reports directory.
        
        Args:
            reports_dir: Directory containing reports.
            processed_reports: List of already processed report names.
        """
        self.reports_dir = reports_dir
        self.processed = set(processed_reports or [])
    
    def find_reports(self) -> List[ReportInfo]:
        """Find all reports in directory.
        
        Returns:
            List of ReportInfo sorted by modified_at (newest first).
        """
        reports = []
        
        if not self.reports_dir.exists():
            return reports
        
        for ext in SUPPORTED_REPORT_EXTENSIONS:
            for path in self.reports_dir.glob(f"*{ext}"):
                if path.is_file():
                    stat = path.stat()
                    reports.append(ReportInfo(
                        path=path,
                        name=path.name,
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                        size_bytes=stat.st_size,
                        extension=ext,
                    ))
        
        return sorted(reports, key=lambda r: r.modified_at, reverse=True)
    
    def select_latest(self, exclude_processed: bool = True) -> Optional[ReportInfo]:
        """Select the latest unprocessed report.
        
        Args:
            exclude_processed: Skip reports already processed.
        
        Returns:
            ReportInfo or None if no reports available.
        """
        for report in self.find_reports():
            if exclude_processed and report.name in self.processed:
                continue
            return report
        return None
    
    def validate_report(self, report: ReportInfo) -> Tuple[bool, Optional[str]]:
        """Validate report is suitable for analysis.
        
        Args:
            report: Report to validate.
        
        Returns:
            Tuple of (valid, error_message).
        """
        if not report.path.exists():
            return False, f"Report file does not exist: {report.path}"
        
        if report.size_bytes == 0:
            return False, "Report file is empty"
        
        if report.size_bytes > MAX_REPORT_SIZE_BYTES:
            return False, f"Report file too large: {report.size_bytes} bytes"
        
        try:
            content = report.path.read_text()
            if len(content.strip()) < 50:
                return False, "Report content too short"
        except Exception as e:
            return False, f"Cannot read report: {e}"
        
        return True, None


# ============================================================
# REPORT GENERATION (fallback when no reports exist)
# ============================================================

def _safe_run_output(args: List[str], cwd: Path) -> str:
    """Run a command and return trimmed output for embedding in reports."""
    try:
        proc = run_command(args, cwd=cwd, timeout=10)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        combined = out if out else err
        combined = combined.strip()
        if proc.exit_code != 0 and not combined:
            combined = f"(command failed with exit code {proc.exit_code})"
        # keep it short in the report
        lines = combined.splitlines()
        return "\n".join(lines[:60])
    except Exception as e:
        return f"(command error: {e})"


def generate_bootstrap_report(repo_root: Path, reports_dir: Path) -> Path:
    """Create a bootstrap report when none exist.

    This makes autopilot usable out-of-the-box: if there are no reports,
    we generate a repo snapshot report that the analysis phase can use.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"ralph-auto-report-{ts}.md"
    path = reports_dir / filename

    # Avoid overwriting an existing auto report; add a suffix if needed.
    if path.exists():
        i = 2
        while True:
            candidate = reports_dir / f"ralph-auto-report-{ts}-{i}.md"
            if not candidate.exists():
                path = candidate
                break
            i += 1

    git_branch = _safe_run_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    git_status = _safe_run_output(["git", "status", "--porcelain=v1"], cwd=repo_root)
    git_log = _safe_run_output(["git", "log", "-5", "--oneline"], cwd=repo_root)

    # Include recent Ralph artifacts if present (helpful for self-improvement loops)
    session_dir = repo_root / ".ralph-session"
    runtime_err = ""
    build_err = ""
    ui_fail = ""
    if session_dir.exists():
        runtime_path = session_dir / "logs" / "runtime-errors.txt"
        build_path = session_dir / "logs" / "build-errors.txt"
        ui_fail_path = session_dir / "ui" / "failures.txt"
        if runtime_path.exists():
            runtime_err = "\n".join(runtime_path.read_text(errors="ignore").splitlines()[-80:])
        if build_path.exists():
            build_err = "\n".join(build_path.read_text(errors="ignore").splitlines()[-80:])
        if ui_fail_path.exists():
            ui_fail = "\n".join(ui_fail_path.read_text(errors="ignore").splitlines()[-80:])

    content = f"""# Ralph Auto-Generated Report - {ts}

This report was auto-generated because no reports were found in `{reports_dir.relative_to(repo_root) if reports_dir.is_relative_to(repo_root) else str(reports_dir)}`.

## Repository Snapshot

- Repo: `{repo_root}`
- Branch: `{git_branch.strip() or 'unknown'}`
- Generated at (UTC): {utc_now_iso()}

## Recent Git Activity

```text
{git_log or '(no git history found)'}
```

## Working Tree Status

```text
{git_status or '(clean)'}
```

## Recent Ralph Failures (if any)

### Build Errors
```text
{build_err or '(none found)'}
```

### Runtime Errors
```text
{runtime_err or '(none found)'}
```

### UI Failures
```text
{ui_fail or '(none found)'}
```

## Observations / Notes

- If you have monitoring/analytics, paste a quick snapshot here (errors, drop-offs, feedback).
- If you have a known pain point, add it here in plain language.

## Recommendations (placeholder)

1. Fix the most frequent runtime/build/UI failure (if any above).
2. Improve the most-visible user-facing workflow that’s currently flaky.
3. Reduce friction in onboarding / first-run experience.
"""
    path.write_text(content, encoding="utf-8")
    return path


# ============================================================
# LLM PROVIDER SUPPORT
# ============================================================

class LLMProvider:
    """Multi-provider LLM client for analysis."""
    
    def __init__(
        self,
        provider: str = "anthropic",
        model: Optional[str] = None,
    ):
        """Initialize LLM provider.
        
        Args:
            provider: Provider name (anthropic, openai, openrouter, gateway).
            model: Model override (uses provider default if not specified).
        """
        self.provider = AnalysisProvider(provider)
        self.model = model
        self._detect_and_validate()
    
    def _detect_and_validate(self) -> None:
        """Detect and validate provider credentials."""
        # Check for gateway first (can use Vercel OIDC)
        if self.provider == AnalysisProvider.GATEWAY:
            if not (os.environ.get("VERCEL_OIDC_TOKEN") or os.environ.get("AI_GATEWAY_API_KEY")):
                raise AnalysisError("AI Gateway requires VERCEL_OIDC_TOKEN or AI_GATEWAY_API_KEY")
        elif self.provider == AnalysisProvider.ANTHROPIC:
            # Prefer direct API key, but fall back to Claude CLI if available.
            if os.environ.get("ANTHROPIC_API_KEY"):
                return
            claude_cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
            exe = shlex.split(claude_cmd)[0] if claude_cmd else "claude"
            if shutil.which(exe):
                self.provider = AnalysisProvider.CLAUDE_CLI
                return
            raise AnalysisError("Anthropic requires ANTHROPIC_API_KEY environment variable")
        elif self.provider == AnalysisProvider.OPENAI:
            if not os.environ.get("OPENAI_API_KEY"):
                raise AnalysisError("OpenAI requires OPENAI_API_KEY environment variable")
        elif self.provider == AnalysisProvider.OPENROUTER:
            if not os.environ.get("OPENROUTER_API_KEY"):
                raise AnalysisError("OpenRouter requires OPENROUTER_API_KEY environment variable")
        elif self.provider == AnalysisProvider.CLAUDE_CLI:
            claude_cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
            exe = shlex.split(claude_cmd)[0] if claude_cmd else "claude"
            if not shutil.which(exe):
                raise AnalysisError(
                    f"claude_cli requires '{exe}' on PATH (or set RALPH_CLAUDE_CMD)"
                )
    
    def _get_default_model(self) -> str:
        """Get default model for provider."""
        defaults = {
            AnalysisProvider.ANTHROPIC: "claude-sonnet-4-20250514",
            AnalysisProvider.OPENAI: "gpt-4o",
            AnalysisProvider.OPENROUTER: "anthropic/claude-sonnet-4",
            AnalysisProvider.GATEWAY: "anthropic/claude-sonnet-4",
            AnalysisProvider.CLAUDE_CLI: "claude-sonnet-4-20250514",
        }
        return defaults.get(self.provider, "claude-sonnet-4-20250514")
    
    def call(self, prompt: str) -> str:
        """Call LLM with prompt.
        
        Args:
            prompt: Prompt text.
        
        Returns:
            Response text.
        
        Raises:
            AnalysisError: If call fails.
        """
        model = self.model or self._get_default_model()
        
        try:
            if self.provider == AnalysisProvider.ANTHROPIC:
                return self._call_anthropic(prompt, model)
            elif self.provider == AnalysisProvider.OPENAI:
                return self._call_openai(prompt, model)
            elif self.provider == AnalysisProvider.OPENROUTER:
                return self._call_openrouter(prompt, model)
            elif self.provider == AnalysisProvider.GATEWAY:
                return self._call_gateway(prompt, model)
            elif self.provider == AnalysisProvider.CLAUDE_CLI:
                return self._call_claude_cli(prompt, model)
            else:
                raise AnalysisError(f"Unknown provider: {self.provider}")
        except urllib.error.HTTPError as e:
            raise AnalysisError(f"LLM API error: {e.code} {e.reason}")
        except Exception as e:
            raise AnalysisError(f"LLM call failed: {e}")
    
    def _call_anthropic(self, prompt: str, model: str) -> str:
        """Call Anthropic API."""
        api_key = os.environ["ANTHROPIC_API_KEY"]
        
        request_data = json.dumps({
            "model": model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    
    def _call_openai(self, prompt: str, model: str) -> str:
        """Call OpenAI API."""
        api_key = os.environ["OPENAI_API_KEY"]
        
        request_data = json.dumps({
            "model": model,
            "max_completion_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    
    def _call_openrouter(self, prompt: str, model: str) -> str:
        """Call OpenRouter API."""
        api_key = os.environ["OPENROUTER_API_KEY"]
        
        request_data = json.dumps({
            "model": model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    
    def _call_gateway(self, prompt: str, model: str) -> str:
        """Call AI Gateway."""
        gateway_url = os.environ.get("AI_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1")
        auth_token = os.environ.get("VERCEL_OIDC_TOKEN") or os.environ.get("AI_GATEWAY_API_KEY")
        
        request_data = json.dumps({
            "model": model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        
        req = urllib.request.Request(
            f"{gateway_url}/chat/completions",
            data=request_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            },
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]

    def _call_claude_cli(self, prompt: str, model: str) -> str:
        """Call Claude CLI (or mock) using stdin for prompt."""
        claude_cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
        base = shlex.split(claude_cmd) if claude_cmd else ["claude"]

        # Keep args short; pass prompt via stdin (avoids argv length limits).
        #
        # Use Claude Code structured output to force valid JSON.
        schema = json.dumps({
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "priority_item": {"type": "string"},
                "description": {"type": "string"},
                "rationale": {"type": "string"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "estimated_tasks": {"type": "integer"},
                "branch_name": {"type": "string"},
            },
            "required": [
                "priority_item",
                "description",
                "rationale",
                "acceptance_criteria",
                "estimated_tasks",
                "branch_name",
            ],
        })

        cmd = base + [
            "--print",
            "--output-format",
            "json",
            "--json-schema",
            schema,
            "--model",
            model,
        ]
        res = run_command(cmd, timeout=1800, input_text=prompt)
        if res.exit_code != 0:
            raise AnalysisError(f"Claude CLI failed (exit {res.exit_code}): {res.truncated_output()}")
        raw = (res.stdout or res.stderr or "").strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "structured_output" in data and data["structured_output"]:
                return json.dumps(data["structured_output"])
            if isinstance(data, dict) and "result" in data and data["result"]:
                return data["result"]
        except Exception:
            # Fall back to raw (ReportAnalyzer will attempt parsing and raise a clear error)
            return raw
        return raw


# ============================================================
# REPORT ANALYSIS
# ============================================================

class ReportAnalyzer:
    """Analyzes reports to identify actionable priorities."""
    
    def __init__(
        self,
        config: AutopilotConfig,
        repo_root: Path,
    ):
        """Initialize analyzer.
        
        Args:
            config: Autopilot configuration.
            repo_root: Repository root path.
        """
        self.config = config
        self.repo_root = repo_root
        self.llm = LLMProvider(
            provider=config.analysis_provider,
            model=config.analysis_model,
        )
    
    def _load_recent_prds(self, days: int) -> str:
        """Load recent PRD titles to exclude from consideration.
        
        Args:
            days: Number of days to look back.
        
        Returns:
            Formatted string of recent PRDs.
        """
        tasks_dir = self.repo_root / self.config.prd_output_dir
        if not tasks_dir.exists():
            # Also check ./tasks directory
            tasks_dir = self.repo_root / "tasks"
            if not tasks_dir.exists():
                return ""
        
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        
        for prd in tasks_dir.glob("prd-*.md"):
            stat = prd.stat()
            if datetime.fromtimestamp(stat.st_mtime) > cutoff:
                try:
                    content = prd.read_text()
                    for line in content.split("\n"):
                        if line.startswith("# "):
                            title = line[2:].strip()
                            date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                            recent.append(f"- {date}: {title}")
                            break
                except Exception:
                    pass
        
        # Also check progress.txt for recent items
        progress_path = self.repo_root / self.config.progress_path
        if progress_path.exists():
            try:
                content = progress_path.read_text()
                for line in content.split("\n")[-50:]:  # Last 50 lines
                    if "completed" in line.lower() or "done" in line.lower():
                        recent.append(f"- {line.strip()}")
            except Exception:
                pass
        
        if not recent:
            return ""
        
        return "\n\n## Recently Fixed (Last 7 Days) - DO NOT PICK THESE AGAIN\n" + "\n".join(recent[:20])
    
    def analyze(self, report_path: Path) -> AnalysisOutput:
        """Analyze report and return structured output.
        
        Args:
            report_path: Path to report file.
        
        Returns:
            AnalysisOutput with priority item details.
        
        Raises:
            AnalysisError: If analysis fails.
        """
        # Load report content
        report_content = report_path.read_text()
        
        # Get recent PRDs to exclude
        recent_fixes = self._load_recent_prds(self.config.recent_days)
        
        # Generate prompt
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            report_content=report_content,
            recent_fixes=recent_fixes,
        )
        
        # Call LLM
        response = self.llm.call(prompt)
        
        # Parse response
        return self._parse_response(response, report_path)
    
    def _parse_response(self, response: str, report_path: Path) -> AnalysisOutput:
        """Parse LLM response into AnalysisOutput.
        
        Args:
            response: Raw LLM response.
            report_path: Source report path.
        
        Returns:
            Parsed AnalysisOutput.
        
        Raises:
            AnalysisError: If parsing fails.
        """
        # Try direct JSON parse
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*"priority_item"[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Try extracting from code block
            code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if code_match:
                try:
                    data = json.loads(code_match.group(1))
                except json.JSONDecodeError:
                    raise AnalysisError(f"Could not parse analysis response: {response[:500]}")
            else:
                raise AnalysisError(f"Could not parse analysis response: {response[:500]}")
        
        # Validate required fields
        required = ["priority_item", "description", "rationale", "acceptance_criteria", "branch_name"]
        for field in required:
            if field not in data:
                raise AnalysisError(f"Missing required field in analysis: {field}")
        
        return AnalysisOutput(
            priority_item=data["priority_item"][:200],  # Truncate
            description=data["description"][:2000],
            rationale=data["rationale"][:1000],
            acceptance_criteria=data["acceptance_criteria"][:10],  # Max 10 criteria
            branch_name=data["branch_name"],
            analysis_timestamp=datetime.now(timezone.utc),
            source_report=str(report_path),
            excluded_items=data.get("excluded_items", []),
            model_used=self.llm.model or self.llm._get_default_model(),
            provider=self.llm.provider.value,
        )


# ============================================================
# BRANCH MANAGEMENT
# ============================================================

class BranchManager:
    """Manages git branches for autopilot runs."""
    
    def __init__(
        self,
        repo_root: Path,
        base_branch: str,
        remote: str,
        branch_prefix: str,
    ):
        """Initialize branch manager.
        
        Args:
            repo_root: Repository root path.
            base_branch: Base branch name (e.g., "main").
            remote: Git remote name (e.g., "origin").
            branch_prefix: Prefix for feature branches.
        """
        self.repo_root = repo_root
        self.base_branch = base_branch
        self.remote = remote
        self.branch_prefix = branch_prefix
    
    def _run_git(self, *args: str, check: bool = True) -> ExecResult:
        """Run a git command.
        
        Args:
            *args: Git command arguments.
            check: Raise on failure.
        
        Returns:
            ExecResult from command.
        
        Raises:
            BranchError: If check=True and command fails.
        """
        result = run_command(
            ["git"] + list(args),
            cwd=self.repo_root,
            timeout=60,
        )
        
        if check and not result.success:
            raise BranchError(f"Git command failed: git {' '.join(args)}\n{result.stderr}")
        
        return result
    
    def is_clean(self) -> bool:
        """Check if working directory is clean."""
        result = self._run_git("status", "--porcelain", check=False)
        return result.success and len(result.stdout.strip()) == 0
    
    def get_current_branch(self) -> str:
        """Get current branch name."""
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()
    
    def get_current_commit(self) -> str:
        """Get current commit SHA."""
        result = self._run_git("rev-parse", "HEAD")
        return result.stdout.strip()
    
    def pull_latest(self) -> None:
        """Pull latest from base branch."""
        self._run_git("fetch", self.remote, self.base_branch)
        self._run_git("checkout", self.base_branch)
        self._run_git("pull", self.remote, self.base_branch)
    
    def create_branch(self, branch_name: str) -> bool:
        """Create and checkout a new branch.
        
        Args:
            branch_name: Branch name.
        
        Returns:
            True if new branch created, False if existing checked out.
        """
        # Normalize branch name
        branch_name = normalize_branch_name(branch_name, self.branch_prefix)
        
        # Check if branch exists
        result = self._run_git("rev-parse", "--verify", branch_name, check=False)
        
        if result.success:
            # Branch exists - checkout
            self._run_git("checkout", branch_name)
            return False
        else:
            # Create new branch
            self._run_git("checkout", "-b", branch_name)
            return True
    
    def commit_file(self, path: Path, message: str) -> str:
        """Stage and commit a file.
        
        Args:
            path: File to commit.
            message: Commit message.
        
        Returns:
            Commit SHA.
        """
        # Use relative path
        rel_path = path.relative_to(self.repo_root) if path.is_absolute() else path
        self._run_git("add", str(rel_path))
        self._run_git("commit", "-m", message)
        return self.get_current_commit()
    
    def commit_all(self, message: str) -> str:
        """Commit all changes.
        
        Args:
            message: Commit message.
        
        Returns:
            Commit SHA.
        """
        self._run_git("add", "-A")
        self._run_git("commit", "-m", message)
        return self.get_current_commit()
    
    def push_branch(self, branch_name: str, force: bool = False) -> None:
        """Push branch to remote.
        
        Args:
            branch_name: Branch to push.
            force: Force push (not recommended).
        """
        args = ["push", "-u", self.remote, branch_name]
        if force:
            args.insert(1, "--force")
        self._run_git(*args)


# ============================================================
# PRD GENERATION
# ============================================================

class PRDGenerator:
    """Generates PRD documents from analysis output."""
    
    def __init__(
        self,
        config: AutopilotConfig,
        repo_root: Path,
        branch_manager: BranchManager,
    ):
        """Initialize PRD generator.
        
        Args:
            config: Autopilot configuration.
            repo_root: Repository root.
            branch_manager: Branch manager for commits.
        """
        self.config = config
        self.repo_root = repo_root
        self.branch_manager = branch_manager
    
    def generate(self, analysis: AnalysisOutput) -> Path:
        """Generate PRD from analysis.
        
        Args:
            analysis: Analysis output.
        
        Returns:
            Path to generated PRD.
        
        Raises:
            PRDGenerationError: If generation fails.
        """
        from .agents.claude import invoke_claude
        
        # Determine output path
        feature_name = extract_feature_name(analysis.branch_name)
        prd_filename = f"prd-{feature_name}.md"
        output_dir = self.repo_root / self.config.prd_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        prd_path = output_dir / prd_filename
        
        # Format acceptance criteria
        criteria_text = "\n".join(f"- {c}" for c in analysis.acceptance_criteria)
        
        # Generate prompt
        prompt = PRD_PROMPT_TEMPLATE.format(
            priority_item=analysis.priority_item,
            description=analysis.description,
            rationale=analysis.rationale,
            acceptance_criteria=criteria_text,
            output_path=prd_path,
        )
        
        # Call Claude CLI
        result = invoke_claude(
            prompt=prompt,
            role="prd_generation",
            timeout=600,  # 10 minutes
            repo_root=self.repo_root,
        )
        
        if not result.success:
            raise PRDGenerationError(f"Claude CLI failed: {result.error}")
        
        # Verify PRD was created
        if not prd_path.exists():
            # Try to create from response if it contains markdown
            if "# " in result.output:
                prd_content = self._extract_markdown(result.output)
                if prd_content:
                    prd_path.write_text(prd_content)
        
        if not prd_path.exists():
            raise PRDGenerationError(f"PRD was not created at {prd_path}")
        
        # Commit PRD
        try:
            self.branch_manager.commit_file(
                prd_path,
                f"docs: add PRD for {analysis.priority_item}",
            )
        except BranchError:
            pass  # May fail if nothing to commit
        
        return prd_path
    
    def _extract_markdown(self, response: str) -> Optional[str]:
        """Extract markdown content from response."""
        # Look for markdown code block
        match = re.search(r'```markdown\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            return match.group(1)
        
        # Look for content starting with #
        match = re.search(r'(#\s+.*)', response, re.DOTALL)
        if match:
            return match.group(1)
        
        return None


# ============================================================
# TASK GENERATION
# ============================================================

class TasksGenerator:
    """Generates prd.json from PRD markdown."""
    
    def __init__(
        self,
        config: AutopilotConfig,
        repo_root: Path,
        branch_manager: BranchManager,
    ):
        """Initialize tasks generator.
        
        Args:
            config: Autopilot configuration.
            repo_root: Repository root.
            branch_manager: Branch manager for commits.
        """
        self.config = config
        self.repo_root = repo_root
        self.branch_manager = branch_manager
    
    def generate(self, prd_path: Path, branch_name: str) -> Tuple[Path, int]:
        """Generate prd.json from PRD.
        
        Args:
            prd_path: Path to PRD markdown.
            branch_name: Git branch name.
        
        Returns:
            Tuple of (path to prd.json, task count).
        
        Raises:
            TasksGenerationError: If generation fails.
        """
        from .agents.claude import invoke_claude
        
        output_path = self.repo_root / self.config.tasks_output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate prompt
        prompt = TASKS_PROMPT_TEMPLATE.format(
            prd_path=prd_path,
            output_path=output_path,
            branch_name=branch_name,
            min_tasks=self.config.tasks_min_count,
            max_tasks=self.config.tasks_max_count,
        )
        
        # Call Claude CLI
        result = invoke_claude(
            prompt=prompt,
            role="task_generation",
            timeout=600,
            allowed_tools=["Read", "Write", "Glob", "LS"],
            repo_root=self.repo_root,
        )
        
        if not result.success:
            raise TasksGenerationError(f"Claude CLI failed: {result.error}")
        
        # Verify prd.json was created
        if not output_path.exists():
            # Try to extract JSON from response
            json_content = self._extract_json(result.output)
            if json_content:
                output_path.write_text(json_content)
        
        if not output_path.exists():
            raise TasksGenerationError(f"prd.json was not created at {output_path}")
        
        # Validate and count tasks
        task_count = self._validate_prd_json(output_path, branch_name)
        
        # Check task count bounds
        if task_count < self.config.tasks_min_count:
            raise TasksGenerationError(
                f"Generated {task_count} tasks, minimum is {self.config.tasks_min_count}"
            )
        if task_count > self.config.tasks_max_count:
            raise TasksGenerationError(
                f"Generated {task_count} tasks, maximum is {self.config.tasks_max_count}"
            )
        
        # Commit tasks
        try:
            self.branch_manager.commit_file(
                output_path,
                f"chore: add tasks for {branch_name}",
            )
        except BranchError:
            pass
        
        return output_path, task_count
    
    def _extract_json(self, response: str) -> Optional[str]:
        """Extract JSON content from response."""
        # Look for JSON code block
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return json.dumps(data, indent=2)
            except json.JSONDecodeError:
                pass
        
        # Look for raw JSON
        match = re.search(r'(\{[^{}]*"tasks"\s*:\s*\[.*?\]\s*\})', response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return json.dumps(data, indent=2)
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _validate_prd_json(self, path: Path, branch_name: str) -> int:
        """Validate prd.json and return task count.
        
        Args:
            path: Path to prd.json.
            branch_name: Expected branch name.
        
        Returns:
            Number of tasks.
        
        Raises:
            TasksGenerationError: If validation fails.
        """
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise TasksGenerationError(f"Invalid JSON in prd.json: {e}")
        
        # Required fields
        required = ["project", "branchName", "description", "tasks"]
        for field in required:
            if field not in data:
                # Try to add missing fields
                if field == "project":
                    data["project"] = "Ralph Autopilot"
                elif field == "branchName":
                    data["branchName"] = branch_name
                elif field == "description":
                    data["description"] = "Autopilot-generated tasks"
                else:
                    raise TasksGenerationError(f"Missing required field: {field}")
        
        # Validate each task
        for i, task in enumerate(data.get("tasks", [])):
            task_required = ["id", "title", "acceptanceCriteria", "priority"]
            for field in task_required:
                if field not in task:
                    # Try to fix
                    if field == "id":
                        task["id"] = f"T-{i+1:03d}"
                    elif field == "priority":
                        task["priority"] = i + 1
                    else:
                        raise TasksGenerationError(f"Task {i} missing required field: {field}")
            
            # Ensure passes is False
            task["passes"] = False
            
            # Ensure notes exists
            if "notes" not in task:
                task["notes"] = ""
        
        # Write back sanitized version
        path.write_text(json.dumps(data, indent=2) + "\n")
        
        return len(data.get("tasks", []))


# ============================================================
# PR CREATION
# ============================================================

class PRCreator:
    """Creates pull requests via gh CLI."""
    
    def __init__(
        self,
        config: RalphConfig,
        repo_root: Path,
    ):
        """Initialize PR creator.
        
        Args:
            config: Ralph configuration.
            repo_root: Repository root.
        """
        self.config = config
        self.repo_root = repo_root
    
    def create(
        self,
        branch_name: str,
        analysis: AnalysisOutput,
        tasks_completed: int,
        tasks_total: int,
        prd_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a pull request.
        
        Args:
            branch_name: Feature branch name.
            analysis: Analysis output.
            tasks_completed: Number of completed tasks.
            tasks_total: Total tasks.
            prd_data: Parsed prd.json data.
        
        Returns:
            PR URL.
        
        Raises:
            PRCreationError: If PR creation fails.
        """
        # Check gh is available
        from .exec import check_command_exists
        if not check_command_exists("gh"):
            raise PRCreationError("gh CLI not found. Install with: brew install gh")
        
        # Generate PR title
        title = self.config.pr_title_template.format(
            priority_item=analysis.priority_item[:80],
        )
        
        # Generate PR body
        body = self._generate_body(
            analysis=analysis,
            tasks_completed=tasks_completed,
            tasks_total=tasks_total,
            prd_data=prd_data,
        )
        
        # Create PR
        result = run_command(
            [
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--base", self.config.git.base_branch,
                "--head", branch_name,
            ],
            cwd=self.repo_root,
            timeout=60,
        )
        
        if not result.success:
            raise PRCreationError(f"Failed to create PR: {result.stderr}")
        
        # Parse PR URL from output
        pr_url = result.stdout.strip()
        
        return pr_url
    
    def _generate_body(
        self,
        analysis: AnalysisOutput,
        tasks_completed: int,
        tasks_total: int,
        prd_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate PR body."""
        # Format task summary
        task_summary = f"{tasks_completed}/{tasks_total} tasks completed"
        if prd_data and "tasks" in prd_data:
            task_lines = []
            for t in prd_data["tasks"]:
                status = "✅" if t.get("passes") else "⬜"
                task_lines.append(f"- {status} {t.get('id', '?')}: {t.get('title', 'Unknown')}")
            task_summary = "\n".join(task_lines)
        
        # Use template if provided
        if self.config.pr_body_template:
            return self.config.pr_body_template.format(
                description=analysis.description,
                rationale=analysis.rationale,
                task_summary=task_summary,
            )
        
        # Default body
        criteria = "\n".join(f"- [ ] {c}" for c in analysis.acceptance_criteria)
        
        return f"""## Ralph Autopilot: {analysis.priority_item}

**Generated from report:** {analysis.source_report}

### Description
{analysis.description}

### Rationale
{analysis.rationale}

### Acceptance Criteria
{criteria}

### Tasks ({tasks_completed}/{tasks_total})
{task_summary}

---
*This PR was automatically generated by Ralph Autopilot.*
"""


# ============================================================
# RUN STATE MANAGEMENT
# ============================================================

class RunStateManager:
    """Manages autopilot run persistence."""
    
    def __init__(self, autopilot_dir: Path):
        """Initialize run state manager.
        
        Args:
            autopilot_dir: Directory for autopilot artifacts.
        """
        self.autopilot_dir = autopilot_dir
        self.runs_dir = autopilot_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
    
    def create(self) -> AutopilotRun:
        """Create a new run."""
        run = AutopilotRun(
            run_id=generate_run_id(),
            started_at=datetime.now(timezone.utc),
            status=RunStatus.PENDING,
        )
        self._save(run)
        return run
    
    def load(self, run_id: str) -> AutopilotRun:
        """Load run state from disk."""
        path = self.runs_dir / f"{run_id}.json"
        data = json.loads(path.read_text())
        return self._from_dict(data)
    
    def update(self, run: AutopilotRun, **kwargs) -> AutopilotRun:
        """Update run state."""
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)
        self._save(run)
        return run
    
    def get_latest_incomplete(self) -> Optional[AutopilotRun]:
        """Get latest incomplete run for recovery."""
        runs = sorted(self.runs_dir.glob("*.json"), reverse=True)
        for run_path in runs:
            try:
                run = self.load(run_path.stem)
                if run.status not in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABORTED]:
                    return run
            except Exception:
                continue
        return None
    
    def _save(self, run: AutopilotRun) -> None:
        """Save run state to disk."""
        path = self.runs_dir / f"{run.run_id}.json"
        path.write_text(json.dumps(self._to_dict(run), indent=2) + "\n")
    
    def _to_dict(self, run: AutopilotRun) -> Dict[str, Any]:
        """Convert run to dictionary."""
        return {
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "status": run.status.value,
            "report_path": run.report_path,
            "analysis_path": run.analysis_path,
            "prd_path": run.prd_path,
            "tasks_path": run.tasks_path,
            "branch_name": run.branch_name,
            "base_commit": run.base_commit,
            "session_id": run.session_id,
            "tasks_completed": run.tasks_completed,
            "tasks_total": run.tasks_total,
            "pr_created": run.pr_created,
            "pr_url": run.pr_url,
            "failure_reason": run.failure_reason,
            "failure_phase": run.failure_phase,
        }
    
    def _from_dict(self, data: Dict[str, Any]) -> AutopilotRun:
        """Create run from dictionary."""
        return AutopilotRun(
            run_id=data["run_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            status=RunStatus(data["status"]),
            report_path=data.get("report_path"),
            analysis_path=data.get("analysis_path"),
            prd_path=data.get("prd_path"),
            tasks_path=data.get("tasks_path"),
            branch_name=data.get("branch_name"),
            base_commit=data.get("base_commit"),
            session_id=data.get("session_id"),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_total=data.get("tasks_total", 0),
            pr_created=data.get("pr_created", False),
            pr_url=data.get("pr_url"),
            failure_reason=data.get("failure_reason"),
            failure_phase=data.get("failure_phase"),
        )


# ============================================================
# MEMORY MANAGEMENT
# ============================================================

class MemoryManager:
    """Manages progress tracking and archival."""
    
    def __init__(self, config: AutopilotConfig, repo_root: Path):
        """Initialize memory manager.
        
        Args:
            config: Autopilot configuration.
            repo_root: Repository root.
        """
        self.config = config
        self.repo_root = repo_root
        self.progress_path = repo_root / config.progress_path
        self.archive_dir = repo_root / config.archive_path
    
    def archive_previous_run(self, current_branch: str) -> Optional[Path]:
        """Archive previous run if branch changed.
        
        Args:
            current_branch: Current branch name.
        
        Returns:
            Path to archive folder, or None if no archive.
        """
        prd_path = self.repo_root / self.config.tasks_output
        if not prd_path.exists():
            return None
        
        try:
            prd_data = json.loads(prd_path.read_text())
            previous_branch = prd_data.get("branchName", "")
        except Exception:
            return None
        
        if previous_branch == current_branch:
            return None  # Same branch, no archive
        
        # Create archive folder
        date = datetime.now().strftime("%Y-%m-%d")
        folder_name = extract_feature_name(previous_branch) or "unknown"
        archive_path = self.archive_dir / f"{date}-{folder_name}"
        archive_path.mkdir(parents=True, exist_ok=True)
        
        # Copy files
        import shutil
        if prd_path.exists():
            shutil.copy(prd_path, archive_path / "prd.json")
        if self.progress_path.exists():
            shutil.copy(self.progress_path, archive_path / "progress.txt")
        
        analysis_path = self.repo_root / ".ralph/autopilot/analysis.json"
        if analysis_path.exists():
            shutil.copy(analysis_path, archive_path / "analysis.json")
        
        return archive_path
    
    def append_progress(self, message: str) -> None:
        """Append message to progress log.
        
        Args:
            message: Progress message.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_path, "a") as f:
            f.write(line)
    
    def get_progress_content(self, max_lines: int = 100) -> str:
        """Get progress log content.
        
        Args:
            max_lines: Maximum lines to return.
        
        Returns:
            Progress content.
        """
        if not self.progress_path.exists():
            return ""
        
        lines = self.progress_path.read_text().strip().split("\n")
        return "\n".join(lines[-max_lines:])


# ============================================================
# AUTOPILOT ORCHESTRATOR
# ============================================================

class AutopilotOrchestrator:
    """Main orchestrator for the autopilot pipeline."""
    
    def __init__(
        self,
        config: RalphConfig,
        options: AutopilotOptions,
    ):
        """Initialize orchestrator.
        
        Args:
            config: Ralph configuration.
            options: Autopilot options.
        """
        self.config = config
        self.options = options
        self.repo_root = config.repo_root
        
        # Setup directories
        self.autopilot_dir = config.repo_root / ".ralph" / "autopilot"
        self.autopilot_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.run_state = RunStateManager(self.autopilot_dir)
        self.memory = MemoryManager(config.autopilot, config.repo_root)
        
        # Branch manager
        self.branch_manager = BranchManager(
            repo_root=config.repo_root,
            base_branch=config.git.base_branch,
            remote=config.git.remote,
            branch_prefix=config.autopilot.branch_prefix,
        )
    
    def _print(self, msg: str, end: str = "\n") -> None:
        """Print message."""
        print(msg, end=end, file=sys.stdout, flush=True)
    
    def _print_header(self, title: str) -> None:
        """Print section header."""
        self._print("")
        self._print("═" * 60)
        self._print(f"  {title}")
        self._print("═" * 60)
    
    def run(self) -> AutopilotResult:
        """Run the full autopilot pipeline.
        
        Returns:
            AutopilotResult with outcome.
        """
        self._print_header("RALPH AUTOPILOT")
        
        # Check for incomplete run to resume
        run: Optional[AutopilotRun] = None
        if self.options.resume:
            run = self.run_state.get_latest_incomplete()
            if run:
                self._print(f"Resuming incomplete run: {run.run_id}")
        
        if run is None:
            run = self.run_state.create()
        
        try:
            return self._execute_pipeline(run)
        except AutopilotError as e:
            self.run_state.update(
                run,
                status=RunStatus.FAILED,
                failure_reason=str(e),
                failure_phase=run.status.value,
                completed_at=datetime.now(timezone.utc),
            )
            return AutopilotResult(
                exit_code=self._error_to_exit_code(e),
                run_id=run.run_id,
                error=str(e),
            )
        except KeyboardInterrupt:
            self.run_state.update(
                run,
                status=RunStatus.ABORTED,
                failure_reason="User abort",
                completed_at=datetime.now(timezone.utc),
            )
            self._print("\n⚠ Aborted by user")
            return AutopilotResult(
                exit_code=ExitCode.USER_ABORT,
                run_id=run.run_id,
                error="User abort",
            )
    
    def _execute_pipeline(self, run: AutopilotRun) -> AutopilotResult:
        """Execute the autopilot pipeline phases.
        
        Args:
            run: Autopilot run state.
        
        Returns:
            AutopilotResult.
        """
        analysis: Optional[AnalysisOutput] = None
        
        # Phase 1: Report Discovery
        if run.status == RunStatus.PENDING:
            run = self._phase_discovery(run)
        
        # Phase 2: Analysis
        if run.status == RunStatus.ANALYZING:
            run, analysis = self._phase_analysis(run)
        
        # Load analysis if resuming
        if analysis is None and run.analysis_path:
            analysis = self._load_analysis(run.analysis_path)
        
        # Stop at dry run
        if self.options.dry_run:
            self._print("\n✓ Dry run complete - stopping after analysis")
            return AutopilotResult(
                exit_code=ExitCode.SUCCESS,
                run_id=run.run_id,
                dry_run=True,
                analysis=analysis,
            )
        
        # Phase 3: Branch Setup
        if run.status == RunStatus.BRANCHING:
            run = self._phase_branch(run, analysis)
        
        # Phase 4: PRD Generation
        if run.status == RunStatus.PLANNING and not self.options.skip_prd:
            run = self._phase_prd(run, analysis)
        
        # Phase 5: Task Generation
        if run.tasks_path is None:
            run = self._phase_tasks(run, analysis)
        
        # Phase 6: Verified Execution
        if run.status == RunStatus.EXECUTING:
            run = self._phase_execution(run)
        
        # Phase 7: PR Creation
        should_create_pr = (
            self.options.create_pr if self.options.create_pr is not None
            else self.config.autopilot.create_pr
        )
        
        if run.status == RunStatus.PUSHING and should_create_pr:
            run = self._phase_pr(run, analysis)
        
        # Complete
        run = self.run_state.update(
            run,
            status=RunStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        
        # Update progress
        self.memory.append_progress(
            f"Autopilot complete: {analysis.priority_item if analysis else 'unknown'} "
            f"({run.tasks_completed}/{run.tasks_total} tasks)"
        )
        
        # Print summary
        self._print_header("AUTOPILOT COMPLETE")
        self._print(f"  Run ID: {run.run_id}")
        if run.branch_name:
            self._print(f"  Branch: {run.branch_name}")
        self._print(f"  Tasks: {run.tasks_completed}/{run.tasks_total} completed")
        if run.pr_url:
            self._print(f"  PR: {run.pr_url}")
        self._print("═" * 60)
        
        return AutopilotResult(
            exit_code=ExitCode.SUCCESS,
            run_id=run.run_id,
            analysis=analysis,
            branch_name=run.branch_name,
            prd_path=run.prd_path,
            tasks_path=run.tasks_path,
            tasks_completed=run.tasks_completed,
            tasks_total=run.tasks_total,
            pr_url=run.pr_url,
        )
    
    def _phase_discovery(self, run: AutopilotRun) -> AutopilotRun:
        """Phase 1: Discover and select report.
        
        Args:
            run: Current run state.
        
        Returns:
            Updated run state.
        
        Raises:
            ReportDiscoveryError: If no reports found.
        """
        self._print("\n▶ Scanning reports directory...")
        
        # Determine reports directory
        reports_dir = Path(
            self.options.reports_dir or
            self.config.autopilot.reports_dir or
            DEFAULT_REPORTS_DIR
        )
        if not reports_dir.is_absolute():
            reports_dir = self.repo_root / reports_dir
        
        # Use specific report if provided
        if self.options.report_path:
            report_path = Path(self.options.report_path)
            if not report_path.is_absolute():
                report_path = self.repo_root / report_path
            
            if not report_path.exists():
                raise ReportDiscoveryError(f"Report not found: {report_path}")
            
            self._print(f"  Using specified report: {report_path.name}")
            
            return self.run_state.update(
                run,
                status=RunStatus.ANALYZING,
                report_path=str(report_path),
            )
        
        # Discover reports
        discovery = ReportDiscovery(reports_dir)
        reports = discovery.find_reports()
        
        if not reports:
            # NEW: bootstrap behavior — create reports dir and generate a report instead of erroring.
            self._print(f"  No reports found in {reports_dir}")
            self._print("  Creating bootstrap report...")
            bootstrap = generate_bootstrap_report(self.repo_root, reports_dir)
            self._print(f"  ✓ Created: {bootstrap}")
            reports = discovery.find_reports()
            if not reports:
                raise ReportDiscoveryError(f"Failed to generate a bootstrap report in {reports_dir}")
        
        self._print(f"  Found {len(reports)} report(s):")
        for r in reports[:5]:
            self._print(f"    - {r.name}")
        if len(reports) > 5:
            self._print(f"    ... and {len(reports) - 5} more")
        
        # Select latest
        report = discovery.select_latest()
        if report is None:
            raise ReportDiscoveryError("No unprocessed reports available")
        
        # Validate
        valid, error = discovery.validate_report(report)
        if not valid:
            raise ReportDiscoveryError(f"Report validation failed: {error}")
        
        self._print(f"\n  Selected: {report.name} (latest)")
        
        return self.run_state.update(
            run,
            status=RunStatus.ANALYZING,
            report_path=str(report.path),
        )
    
    def _phase_analysis(self, run: AutopilotRun) -> Tuple[AutopilotRun, AnalysisOutput]:
        """Phase 2: Analyze report.
        
        Args:
            run: Current run state.
        
        Returns:
            Tuple of (updated run, analysis output).
        
        Raises:
            AnalysisError: If analysis fails.
        """
        self._print(f"\n▶ Analyzing report: {Path(run.report_path).name}")
        
        # Create analyzer
        analyzer = ReportAnalyzer(
            config=self.config.autopilot,
            repo_root=self.repo_root,
        )
        
        # Run analysis
        analysis = analyzer.analyze(Path(run.report_path))
        
        # Save analysis
        analysis_path = self.autopilot_dir / "analysis.json"
        analysis_data = {
            "priority_item": analysis.priority_item,
            "description": analysis.description,
            "rationale": analysis.rationale,
            "acceptance_criteria": analysis.acceptance_criteria,
            "branch_name": analysis.branch_name,
            "analysis_timestamp": analysis.analysis_timestamp.isoformat(),
            "source_report": analysis.source_report,
            "excluded_items": analysis.excluded_items,
            "model_used": analysis.model_used,
            "provider": analysis.provider,
        }
        analysis_path.write_text(json.dumps(analysis_data, indent=2) + "\n")
        
        # Normalize branch name
        branch_name = normalize_branch_name(
            analysis.branch_name,
            self.config.autopilot.branch_prefix,
        )
        
        # Print analysis
        self._print("\n  Analysis complete:")
        self._print("  ┌" + "─" * 56 + "┐")
        self._print(f"  │ Priority: {analysis.priority_item[:52]:52} │")
        self._print("  ├" + "─" * 56 + "┤")
        desc_lines = [analysis.description[i:i+52] for i in range(0, min(len(analysis.description), 156), 52)]
        for line in desc_lines[:3]:
            self._print(f"  │ {line:54} │")
        self._print("  ├" + "─" * 56 + "┤")
        self._print(f"  │ Branch: {branch_name[:48]:48} │")
        self._print("  └" + "─" * 56 + "┘")
        
        return self.run_state.update(
            run,
            status=RunStatus.BRANCHING,
            analysis_path=str(analysis_path),
            branch_name=branch_name,
        ), analysis
    
    def _phase_branch(self, run: AutopilotRun, analysis: Optional[AnalysisOutput]) -> AutopilotRun:
        """Phase 3: Setup git branch.
        
        Args:
            run: Current run state.
            analysis: Analysis output.
        
        Returns:
            Updated run state.
        
        Raises:
            BranchError: If branch operations fail.
        """
        self._print("\n▶ Setting up branch...")
        
        branch_name = self.options.branch_name or run.branch_name
        if not branch_name and analysis:
            branch_name = normalize_branch_name(
                analysis.branch_name,
                self.config.autopilot.branch_prefix,
            )
        
        if not branch_name:
            raise BranchError("No branch name available")
        
        # Archive previous run if different branch
        archived = self.memory.archive_previous_run(branch_name)
        if archived:
            self._print(f"  Archived previous run to: {archived}")
        
        # Check for clean state
        if not self.branch_manager.is_clean():
            self._print("  ⚠ Working directory has uncommitted changes")
        
        # Pull latest
        try:
            self._print(f"  Pulling latest from {self.config.git.base_branch}...")
            self.branch_manager.pull_latest()
            self._print(f"  ✓ Base branch up to date")
        except BranchError as e:
            self._print(f"  ⚠ Could not pull latest: {e}")
        
        # Create/checkout branch
        is_new = self.branch_manager.create_branch(branch_name)
        if is_new:
            self._print(f"  ✓ Created branch: {branch_name}")
        else:
            self._print(f"  ✓ Checked out existing branch: {branch_name}")
        
        base_commit = self.branch_manager.get_current_commit()
        
        return self.run_state.update(
            run,
            status=RunStatus.PLANNING,
            branch_name=branch_name,
            base_commit=base_commit,
        )
    
    def _phase_prd(self, run: AutopilotRun, analysis: Optional[AnalysisOutput]) -> AutopilotRun:
        """Phase 4: Generate PRD.
        
        Args:
            run: Current run state.
            analysis: Analysis output.
        
        Returns:
            Updated run state.
        
        Raises:
            PRDGenerationError: If PRD generation fails.
        """
        self._print("\n▶ Generating PRD...")
        
        if analysis is None:
            analysis = self._load_analysis(run.analysis_path)
        
        generator = PRDGenerator(
            config=self.config.autopilot,
            repo_root=self.repo_root,
            branch_manager=self.branch_manager,
        )
        
        prd_path = generator.generate(analysis)
        self._print(f"  ✓ PRD saved to: {prd_path}")
        
        return self.run_state.update(
            run,
            prd_path=str(prd_path),
        )
    
    def _phase_tasks(self, run: AutopilotRun, analysis: Optional[AnalysisOutput]) -> AutopilotRun:
        """Phase 5: Generate tasks.
        
        Args:
            run: Current run state.
            analysis: Analysis output.
        
        Returns:
            Updated run state.
        
        Raises:
            TasksGenerationError: If task generation fails.
        """
        self._print("\n▶ Generating tasks...")
        
        if analysis is None:
            analysis = self._load_analysis(run.analysis_path)
        
        generator = TasksGenerator(
            config=self.config.autopilot,
            repo_root=self.repo_root,
            branch_manager=self.branch_manager,
        )
        
        # Use PRD path if available
        prd_path = Path(run.prd_path) if run.prd_path else None
        
        tasks_path, task_count = generator.generate(
            prd_path=prd_path or Path("PRD.md"),  # Fallback
            branch_name=run.branch_name,
        )
        
        self._print(f"  ✓ Generated {task_count} tasks")
        self._print(f"  ✓ Tasks saved to: {tasks_path}")
        
        return self.run_state.update(
            run,
            status=RunStatus.EXECUTING,
            tasks_path=str(tasks_path),
            tasks_total=task_count,
        )
    
    def _phase_execution(self, run: AutopilotRun) -> AutopilotRun:
        """Phase 6: Run verified execution.
        
        Args:
            run: Current run state.
        
        Returns:
            Updated run state.
        """
        self._print("\n▶ Starting verified execution...")
        
        from .run import run_tasks, RunOptions
        
        run_options = RunOptions(
            prd_json=run.tasks_path,
            max_iterations=self.config.limits.max_iterations,
            gate_type="full",
            dry_run=False,
            post_verify=True,
            verbose=self.options.verbose,
        )
        
        result = run_tasks(
            config_path=self.config.path,
            prd_path=Path(run.tasks_path) if run.tasks_path else None,
            options=run_options,
        )
        
        return self.run_state.update(
            run,
            status=RunStatus.PUSHING,
            session_id=result.session_id,
            tasks_completed=result.tasks_completed,
        )
    
    def _phase_pr(self, run: AutopilotRun, analysis: Optional[AnalysisOutput]) -> AutopilotRun:
        """Phase 7: Create pull request.
        
        Args:
            run: Current run state.
            analysis: Analysis output.
        
        Returns:
            Updated run state.
        
        Raises:
            PRCreationError: If PR creation fails.
        """
        self._print("\n▶ Creating pull request...")
        
        if analysis is None:
            analysis = self._load_analysis(run.analysis_path)
        
        # Push branch first
        self._print(f"  Pushing branch to {self.config.git.remote}...")
        self.branch_manager.push_branch(run.branch_name)
        self._print(f"  ✓ Branch pushed")
        
        # Load prd.json for task summary
        prd_data = None
        if run.tasks_path:
            try:
                prd_data = json.loads(Path(run.tasks_path).read_text())
            except Exception:
                pass
        
        # Create PR
        creator = PRCreator(
            config=self.config,
            repo_root=self.repo_root,
        )
        
        pr_url = creator.create(
            branch_name=run.branch_name,
            analysis=analysis,
            tasks_completed=run.tasks_completed,
            tasks_total=run.tasks_total,
            prd_data=prd_data,
        )
        
        self._print(f"  ✓ PR created: {pr_url}")
        
        return self.run_state.update(
            run,
            pr_created=True,
            pr_url=pr_url,
        )
    
    def _load_analysis(self, analysis_path: Optional[str]) -> AnalysisOutput:
        """Load analysis from file.
        
        Args:
            analysis_path: Path to analysis.json.
        
        Returns:
            AnalysisOutput.
        
        Raises:
            AnalysisError: If loading fails.
        """
        if not analysis_path:
            raise AnalysisError("No analysis path available")
        
        try:
            data = json.loads(Path(analysis_path).read_text())
            return AnalysisOutput(
                priority_item=data["priority_item"],
                description=data["description"],
                rationale=data["rationale"],
                acceptance_criteria=data["acceptance_criteria"],
                branch_name=data["branch_name"],
                analysis_timestamp=datetime.fromisoformat(data["analysis_timestamp"]),
                source_report=data.get("source_report", ""),
                excluded_items=data.get("excluded_items", []),
                model_used=data.get("model_used"),
                provider=data.get("provider"),
            )
        except Exception as e:
            raise AnalysisError(f"Failed to load analysis: {e}")
    
    def _error_to_exit_code(self, error: AutopilotError) -> ExitCode:
        """Map error type to exit code."""
        if isinstance(error, ReportDiscoveryError):
            return ExitCode.NO_REPORTS
        elif isinstance(error, AnalysisError):
            return ExitCode.ANALYSIS_FAILED
        elif isinstance(error, PRDGenerationError):
            return ExitCode.PRD_GENERATION_FAILED
        elif isinstance(error, TasksGenerationError):
            return ExitCode.TASK_GENERATION_FAILED
        elif isinstance(error, BranchError):
            return ExitCode.GIT_ERROR
        elif isinstance(error, PRCreationError):
            return ExitCode.PR_CREATION_FAILED
        else:
            return ExitCode.EXECUTION_FAILED


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def run_autopilot(
    config_path: Optional[Path] = None,
    options: Optional[AutopilotOptions] = None,
) -> AutopilotResult:
    """Run the autopilot pipeline.
    
    Args:
        config_path: Path to ralph.yml configuration.
        options: Autopilot options.
    
    Returns:
        AutopilotResult with outcome.
    """
    options = options or AutopilotOptions()
    
    # Load configuration
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        return AutopilotResult(
            exit_code=ExitCode.CONFIG_ERROR,
            error=str(e),
        )
    
    # Create and run orchestrator
    orchestrator = AutopilotOrchestrator(
        config=config,
        options=options,
    )
    
    return orchestrator.run()
