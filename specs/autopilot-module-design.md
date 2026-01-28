# Ralph Autopilot Module Design Specification

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Design Document

This document defines the detailed design for the Ralph autopilot module, which implements a Compound Product–style self-improvement pipeline: report ingestion → analysis → branch → PRD → tasks → verified run → PR.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Pipeline Flow](#2-pipeline-flow)
3. [Module Structure](#3-module-structure)
4. [Phase Specifications](#4-phase-specifications)
   - [4.1 Report Discovery](#41-report-discovery)
   - [4.2 Report Analysis](#42-report-analysis)
   - [4.3 Branch Management](#43-branch-management)
   - [4.4 PRD Generation](#44-prd-generation)
   - [4.5 Task Generation](#45-task-generation)
   - [4.6 Verified Execution](#46-verified-execution)
   - [4.7 PR Creation](#47-pr-creation)
5. [Data Models](#5-data-models)
6. [Configuration Contract](#6-configuration-contract)
7. [Prompt Templates](#7-prompt-templates)
8. [Error Handling](#8-error-handling)
9. [Artifact Management](#9-artifact-management)
10. [Testing Strategy](#10-testing-strategy)

---

## 1. Overview

### 1.1 Purpose

The autopilot module enables Ralph to operate in a fully autonomous self-improvement mode. Given a directory of analysis reports (e.g., daily analytics, error logs, user feedback), autopilot:

1. **Selects** the highest-priority actionable item
2. **Researches** the codebase and web for context (optional)
3. **Plans** the implementation (PRD + tasks)
4. **Executes** using the verified execution engine
5. **Delivers** via pull request

### 1.2 Design Goals

- **Autonomous operation**: No human intervention required after launch
- **Safe defaults**: Never auto-merge, always work on feature branches
- **Auditable**: Full artifact trail for every decision and action
- **Configurable**: All behaviors controllable via `.ralph/ralph.yml`
- **Resumable**: Can recover from interruptions using run state

### 1.3 Key Borrowables from Compound Product

| Compound Asset | Ralph Equivalent | Adaptation |
|----------------|------------------|------------|
| `analyze-report.sh` | `autopilot/analysis.py` | Multi-provider LLM support, structured output |
| `auto-compound.sh` | `autopilot/orchestrator.py` | Python implementation, integrated with config |
| `skills/prd/SKILL.md` | `autopilot/prd_gen.py` | Embedded as prompt template |
| `skills/tasks/SKILL.md` | `autopilot/tasks_gen.py` | Embedded as prompt template |
| `progress.txt` | `.ralph/autopilot/progress.txt` | Enhanced with structured events |
| `prd.json` | `.ralph/prd.json` | Same format, schema-validated |

---

## 2. Pipeline Flow

### 2.1 High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AUTOPILOT PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐                                                       │
│  │ ralph        │                                                       │
│  │ autopilot    │                                                       │
│  │ --reports    │                                                       │
│  │ ./reports    │                                                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 1: REPORT DISCOVERY                                        │   │
│  │                                                                  │   │
│  │  • Find reports in configured directory                          │   │
│  │  • Filter by recency (most recent first)                         │   │
│  │  • Select latest unprocessed report                              │   │
│  │                                                                  │   │
│  │  Output: report_path                                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 2: REPORT ANALYSIS                                         │   │
│  │                                                                  │   │
│  │  • Load report content                                           │   │
│  │  • Load recent PRDs to exclude already-fixed items               │   │
│  │  • Call LLM with analysis prompt                                 │   │
│  │  • Parse and validate JSON response                              │   │
│  │                                                                  │   │
│  │  Output: analysis.json                                           │   │
│  │    - priority_item                                               │   │
│  │    - description                                                 │   │
│  │    - rationale                                                   │   │
│  │    - acceptance_criteria[]                                       │   │
│  │    - branch_name                                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         │  ──── DRY RUN STOPS HERE ────                                │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 2.5: RESEARCH (optional, --with-research)                  │   │
│  │                                                                  │   │
│  │  • Backend Researcher: Scan Python/API code patterns             │   │
│  │  • Frontend Researcher: Scan React/Vue/CSS components            │   │
│  │  • Web Researcher: Search docs and best practices                │   │
│  │                                                                  │   │
│  │  Output: research_context added to PRD generation                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 3: BRANCH MANAGEMENT                                       │   │
│  │                                                                  │   │
│  │  • Pull latest from base branch (git.base_branch)                │   │
│  │  • Create or checkout feature branch                             │   │
│  │  • Archive previous run if different branch                      │   │
│  │                                                                  │   │
│  │  Output: active feature branch                                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 4: PRD GENERATION                                          │   │
│  │                                                                  │   │
│  │  • Generate PRD prompt from analysis                             │   │
│  │  • Call Claude CLI with PRD skill                                │   │
│  │  • Verify PRD file created                                       │   │
│  │  • Commit PRD to branch                                          │   │
│  │                                                                  │   │
│  │  Output: tasks/prd-{feature}.md                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 5: TASK GENERATION                                         │   │
│  │                                                                  │   │
│  │  • Generate tasks prompt from PRD                                │   │
│  │  • Call Claude CLI with tasks skill                              │   │
│  │  • Validate prd.json schema                                      │   │
│  │  • Commit prd.json to branch                                     │   │
│  │                                                                  │   │
│  │  Output: .ralph/prd.json                                         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 6: VERIFIED EXECUTION                                      │   │
│  │                                                                  │   │
│  │  • Initialize session                                            │   │
│  │  • Run task loop (implementation → tests → gates → review)       │   │
│  │  • Run post-verification (build/runtime + UI)                    │   │
│  │                                                                  │   │
│  │  Output: all tasks completed, verification passed                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 7: PR CREATION (if enabled)                                │   │
│  │                                                                  │   │
│  │  • Push branch to remote                                         │   │
│  │  • Generate PR title and body from templates                     │   │
│  │  • Create PR via gh CLI                                          │   │
│  │  • Log PR URL                                                    │   │
│  │                                                                  │   │
│  │  Output: PR URL                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────┐                                                       │
│  │   COMPLETE   │                                                       │
│  └──────────────┘                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 State Transitions

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PENDING   │────►│  ANALYZING  │────►│  PLANNING   │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FAILED    │◄────│  EXECUTING  │◄────│  BRANCHING  │
└─────────────┘     └──────┬──────┘     └─────────────┘
       ▲                   │
       │                   ▼
       │            ┌─────────────┐     ┌─────────────┐
       └────────────│  VERIFYING  │────►│   PUSHING   │
                    └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  COMPLETED  │
                                        └─────────────┘
```

---

## 3. Module Structure

### 3.1 File Layout

```
ralph/autopilot/
├── __init__.py
├── orchestrator.py      # Main autopilot pipeline coordinator
├── discovery.py         # Report discovery and selection
├── analysis.py          # Report analysis with LLM
├── branch.py            # Git branch management
├── prd_gen.py           # PRD generation
├── tasks_gen.py         # Task list generation
├── pr.py                # Pull request creation
├── run_state.py         # Run persistence and recovery
├── memory.py            # Progress tracking and archival
└── prompts/             # Prompt templates
    ├── analysis.py      # Analysis prompt template
    ├── prd.py           # PRD generation prompt template
    └── tasks.py         # Tasks generation prompt template

ralph/research/          # Research sub-agents (see research/ module)
├── __init__.py
├── coordinator.py       # ResearchCoordinator orchestrates research phases
├── backend.py           # BackendResearcher scans Python/API code
├── frontend.py          # FrontendResearcher scans React/Vue/CSS
└── web.py               # WebResearcher uses web search for docs

ralph/skills/            # Skill routing (see skills/ module)
├── __init__.py
├── router.py            # SkillRouter detects skills for tasks
└── defaults.py          # Default skill mappings
```

### 3.2 Module Dependencies

```
                    ┌────────────────┐
                    │  orchestrator  │
                    └───────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │           │       │       │           │
        ▼           ▼       ▼       ▼           ▼
  ┌──────────┐ ┌────────┐ ┌────┐ ┌────────┐ ┌────┐
  │discovery │ │analysis│ │prd │ │tasks   │ │ pr │
  └──────────┘ └────────┘ │_gen│ │_gen    │ └────┘
                          └────┘ └────────┘
        │           │       │       │           │
        └───────────┴───────┴───────┴───────────┘
                            │
                    ┌───────┴───────┐
                    │               │
                ┌───────┐     ┌──────────┐
                │branch │     │run_state │
                └───────┘     └──────────┘
                    │               │
                    └───────┬───────┘
                            │
                        ┌───────┐
                        │memory │
                        └───────┘
```

---

## 4. Phase Specifications

### 4.1 Report Discovery

**Purpose:** Find and select the most appropriate report to process.

#### 4.1.1 Discovery Logic

```python
# autopilot/discovery.py

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional

@dataclass
class ReportInfo:
    path: Path
    name: str
    modified_at: datetime
    size_bytes: int
    extension: str

class ReportDiscovery:
    """Discovers and selects reports for analysis."""
    
    SUPPORTED_EXTENSIONS = [".md", ".txt", ".json", ".html"]
    
    def __init__(self, reports_dir: Path, processed_reports: list[str] = None):
        """Initialize with reports directory and optional processed list."""
        self.reports_dir = reports_dir
        self.processed = set(processed_reports or [])
    
    def find_reports(self) -> list[ReportInfo]:
        """Find all reports in directory.
        
        Returns: List of ReportInfo sorted by modified_at (newest first)
        """
        reports = []
        for ext in self.SUPPORTED_EXTENSIONS:
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
            exclude_processed: Skip reports already processed
        
        Returns: ReportInfo or None if no reports available
        """
        for report in self.find_reports():
            if exclude_processed and report.name in self.processed:
                continue
            return report
        return None
```

#### 4.1.2 Report Validation

```python
def validate_report(self, report: ReportInfo) -> tuple[bool, Optional[str]]:
    """Validate report is suitable for analysis.
    
    Checks:
    1. File exists and is readable
    2. File is not empty
    3. File is not too large (< 1MB)
    4. Content appears to be valid report format
    
    Returns: (valid, error_message)
    """
    if not report.path.exists():
        return False, f"Report file does not exist: {report.path}"
    
    if report.size_bytes == 0:
        return False, "Report file is empty"
    
    if report.size_bytes > 1_000_000:  # 1MB
        return False, f"Report file too large: {report.size_bytes} bytes"
    
    # Check content is parseable
    try:
        content = report.path.read_text()
        if len(content.strip()) < 50:
            return False, "Report content too short"
    except Exception as e:
        return False, f"Cannot read report: {e}"
    
    return True, None
```

---

### 4.2 Report Analysis

**Purpose:** Analyze report content to identify the #1 priority item.

#### 4.2.1 Analysis Runner

```python
# autopilot/analysis.py

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum

class AnalysisProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    GATEWAY = "gateway"

@dataclass
class AnalysisOutput:
    """Output from report analysis phase."""
    priority_item: str           # Brief title
    description: str             # 2-3 sentences
    rationale: str               # Why this is #1 priority
    acceptance_criteria: list[str]  # 3-5 verifiable criteria
    branch_name: str             # Suggested branch name
    analysis_timestamp: datetime
    source_report: str
    excluded_items: list[dict]   # Items considered but not selected
    model_used: str
    provider: AnalysisProvider

class ReportAnalyzer:
    """Analyzes reports to identify actionable priorities."""
    
    def __init__(
        self,
        config: AnalysisConfig,
        repo_root: Path,
        cmd_runner: CommandRunner,
    ):
        self.config = config
        self.repo_root = repo_root
        self.cmd_runner = cmd_runner
        self.provider = self._detect_provider()
    
    def _detect_provider(self) -> AnalysisProvider:
        """Detect available LLM provider from environment."""
        import os
        
        if os.environ.get("VERCEL_OIDC_TOKEN") or os.environ.get("AI_GATEWAY_API_KEY"):
            return AnalysisProvider.GATEWAY
        if os.environ.get("ANTHROPIC_API_KEY"):
            return AnalysisProvider.ANTHROPIC
        if os.environ.get("OPENAI_API_KEY"):
            return AnalysisProvider.OPENAI
        if os.environ.get("OPENROUTER_API_KEY"):
            return AnalysisProvider.OPENROUTER
        
        raise ValueError(
            "No LLM provider configured. Set one of: "
            "ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, AI_GATEWAY_API_KEY"
        )
    
    def _load_recent_prds(self, days: int = 7) -> str:
        """Load recent PRD titles to exclude from consideration."""
        from datetime import datetime, timedelta
        
        tasks_dir = self.repo_root / "tasks"
        if not tasks_dir.exists():
            return ""
        
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        
        for prd in tasks_dir.glob("prd-*.md"):
            stat = prd.stat()
            if datetime.fromtimestamp(stat.st_mtime) > cutoff:
                # Extract title from first heading
                try:
                    content = prd.read_text()
                    for line in content.split("\n"):
                        if line.startswith("# "):
                            title = line[2:].strip()
                            date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                            recent.append(f"- {date}: {title}")
                            break
                except:
                    pass
        
        if not recent:
            return ""
        
        return "\n## Recently Fixed (Last 7 Days) - DO NOT PICK THESE AGAIN\n" + "\n".join(recent)
    
    def analyze(self, report_path: Path) -> AnalysisOutput:
        """Analyze report and return structured output.
        
        Args:
            report_path: Path to report file
        
        Returns: AnalysisOutput with priority item details
        
        Raises:
            AnalysisError: If analysis fails
        """
        # Load report content
        report_content = report_path.read_text()
        
        # Get recent PRDs to exclude
        recent_fixes = self._load_recent_prds(self.config.recent_days)
        
        # Generate prompt
        prompt = self._generate_analysis_prompt(report_content, recent_fixes)
        
        # Call LLM based on provider
        response = self._call_llm(prompt)
        
        # Parse and validate response
        return self._parse_response(response, report_path)
    
    def _generate_analysis_prompt(self, report_content: str, recent_fixes: str) -> str:
        """Generate the analysis prompt."""
        from .prompts.analysis import ANALYSIS_PROMPT_TEMPLATE
        return ANALYSIS_PROMPT_TEMPLATE.format(
            report_content=report_content,
            recent_fixes=recent_fixes,
        )
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API based on configured provider."""
        # Implementation varies by provider - see Section 4.2.3
        ...
    
    def _parse_response(self, response: str, report_path: Path) -> AnalysisOutput:
        """Parse LLM response into AnalysisOutput.
        
        Handles:
        - Raw JSON
        - JSON wrapped in markdown code blocks
        - Partial JSON extraction
        """
        import json
        
        # Try direct JSON parse
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract from markdown
            import re
            match = re.search(r'\{[^{}]*"priority_item"[^{}]*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise AnalysisError(f"Could not parse analysis response: {response[:200]}")
        
        # Validate required fields
        required = ["priority_item", "description", "rationale", "acceptance_criteria", "branch_name"]
        for field in required:
            if field not in data:
                raise AnalysisError(f"Missing required field: {field}")
        
        return AnalysisOutput(
            priority_item=data["priority_item"],
            description=data["description"],
            rationale=data["rationale"],
            acceptance_criteria=data["acceptance_criteria"],
            branch_name=self._normalize_branch_name(data["branch_name"]),
            analysis_timestamp=datetime.now(),
            source_report=str(report_path),
            excluded_items=data.get("excluded_items", []),
            model_used=self._get_model_name(),
            provider=self.provider,
        )
    
    def _normalize_branch_name(self, name: str) -> str:
        """Ensure branch name has correct prefix."""
        from ..config import AutopilotConfig
        prefix = self.config.branch_prefix
        
        if name.startswith(prefix):
            return name
        
        # Remove any existing prefix and add configured one
        import re
        cleaned = re.sub(r'^[a-zA-Z]+/', '', name)
        return f"{prefix}{cleaned}"
```

#### 4.2.2 Analysis Prompt Template

```python
# autopilot/prompts/analysis.py

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
  "branch_name": "ralph/kebab-case-feature-name"
}}"""
```

#### 4.2.3 Multi-Provider LLM Support

```python
# autopilot/analysis.py (continued)

def _call_llm(self, prompt: str) -> str:
    """Call LLM API based on configured provider."""
    import os
    import json
    import urllib.request
    
    if self.provider == AnalysisProvider.ANTHROPIC:
        return self._call_anthropic(prompt)
    elif self.provider == AnalysisProvider.OPENAI:
        return self._call_openai(prompt)
    elif self.provider == AnalysisProvider.OPENROUTER:
        return self._call_openrouter(prompt)
    elif self.provider == AnalysisProvider.GATEWAY:
        return self._call_gateway(prompt)
    else:
        raise ValueError(f"Unknown provider: {self.provider}")

def _call_anthropic(self, prompt: str) -> str:
    """Call Anthropic API directly."""
    import os
    import json
    import urllib.request
    
    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = self.config.model or "claude-sonnet-4-20250514"
    
    request_data = json.dumps({
        "model": model,
        "max_tokens": 1024,
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
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        return data["content"][0]["text"]

def _call_openai(self, prompt: str) -> str:
    """Call OpenAI API."""
    import os
    import json
    import urllib.request
    
    api_key = os.environ["OPENAI_API_KEY"]
    model = self.config.model or "gpt-4o"
    
    request_data = json.dumps({
        "model": model,
        "max_completion_tokens": 1024,
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
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

def _call_openrouter(self, prompt: str) -> str:
    """Call OpenRouter API."""
    import os
    import json
    import urllib.request
    
    api_key = os.environ["OPENROUTER_API_KEY"]
    model = self.config.model or "anthropic/claude-sonnet-4"
    
    request_data = json.dumps({
        "model": model,
        "max_tokens": 1024,
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
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

def _call_gateway(self, prompt: str) -> str:
    """Call AI Gateway (Vercel or compatible)."""
    import os
    import json
    import urllib.request
    
    gateway_url = os.environ.get("AI_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1")
    auth_token = os.environ.get("VERCEL_OIDC_TOKEN") or os.environ.get("AI_GATEWAY_API_KEY")
    model = self.config.model or "anthropic/claude-sonnet-4"
    
    request_data = json.dumps({
        "model": model,
        "max_tokens": 1024,
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
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
```

---

### 4.3 Branch Management

**Purpose:** Create and manage feature branches for autopilot runs.

#### 4.3.1 Branch Manager

```python
# autopilot/branch.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class BranchState:
    current_branch: str
    base_branch: str
    is_new: bool
    commit_sha: str

class BranchManager:
    """Manages git branches for autopilot runs."""
    
    def __init__(
        self,
        repo_root: Path,
        cmd_runner: CommandRunner,
        git_config: GitConfig,
    ):
        self.repo_root = repo_root
        self.cmd_runner = cmd_runner
        self.git_config = git_config
    
    def ensure_clean_state(self) -> bool:
        """Ensure working directory is clean.
        
        Returns: True if clean, False if uncommitted changes
        """
        result = self.cmd_runner.run("git status --porcelain")
        return len(result.stdout.strip()) == 0
    
    def pull_latest(self) -> None:
        """Pull latest from base branch."""
        remote = self.git_config.remote
        base = self.git_config.base_branch
        
        # Fetch and checkout base branch
        self.cmd_runner.run(f"git fetch {remote} {base}")
        self.cmd_runner.run(f"git checkout {base}")
        self.cmd_runner.run(f"git pull {remote} {base}")
    
    def create_or_checkout(self, branch_name: str) -> BranchState:
        """Create new branch or checkout existing.
        
        Args:
            branch_name: Target branch name
        
        Returns: BranchState with branch details
        """
        # Check if branch exists
        result = self.cmd_runner.run(
            f"git rev-parse --verify {branch_name}",
            timeout=10,
        )
        
        if result.exit_code == 0:
            # Branch exists - checkout
            self.cmd_runner.run(f"git checkout {branch_name}")
            is_new = False
        else:
            # Create new branch from base
            self.cmd_runner.run(f"git checkout -b {branch_name}")
            is_new = True
        
        # Get current commit SHA
        result = self.cmd_runner.run("git rev-parse HEAD")
        commit_sha = result.stdout.strip()
        
        return BranchState(
            current_branch=branch_name,
            base_branch=self.git_config.base_branch,
            is_new=is_new,
            commit_sha=commit_sha,
        )
    
    def commit_file(self, path: Path, message: str) -> str:
        """Stage and commit a file.
        
        Args:
            path: Path to file
            message: Commit message
        
        Returns: Commit SHA
        """
        self.cmd_runner.run(f"git add {path}")
        self.cmd_runner.run(f'git commit -m "{message}"')
        
        result = self.cmd_runner.run("git rev-parse HEAD")
        return result.stdout.strip()
    
    def push(self, branch_name: str, force: bool = False) -> None:
        """Push branch to remote.
        
        Args:
            branch_name: Branch to push
            force: Use force push (not recommended)
        """
        remote = self.git_config.remote
        force_flag = "--force" if force else ""
        self.cmd_runner.run(f"git push -u {remote} {branch_name} {force_flag}")
```

---

### 4.4 PRD Generation

**Purpose:** Generate a Product Requirements Document from analysis output.

#### 4.4.1 PRD Generator

```python
# autopilot/prd_gen.py

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional

@dataclass
class PRDResult:
    path: Path
    title: str
    task_count: int
    generated_at: datetime
    commit_sha: Optional[str]

class PRDGenerator:
    """Generates PRD documents from analysis output."""
    
    def __init__(
        self,
        config: PRDConfig,
        repo_root: Path,
        cmd_runner: CommandRunner,
        branch_manager: BranchManager,
    ):
        self.config = config
        self.repo_root = repo_root
        self.cmd_runner = cmd_runner
        self.branch_manager = branch_manager
    
    def generate(self, analysis: AnalysisOutput) -> PRDResult:
        """Generate PRD from analysis output.
        
        Args:
            analysis: Output from report analysis
        
        Returns: PRDResult with path and metadata
        """
        # Determine output path
        feature_name = self._extract_feature_name(analysis.branch_name)
        prd_filename = f"prd-{feature_name}.md"
        output_dir = self.repo_root / self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        prd_path = output_dir / prd_filename
        
        # Generate prompt
        prompt = self._generate_prd_prompt(analysis, prd_path)
        
        # Call Claude CLI
        if self.config.mode == "autonomous":
            result = self._call_claude_autonomous(prompt)
        else:
            result = self._call_claude_interactive(prompt)
        
        # Verify PRD was created
        if not prd_path.exists():
            raise PRDGenerationError(f"PRD was not created at {prd_path}")
        
        # Parse task count from PRD
        task_count = self._count_tasks_in_prd(prd_path)
        
        # Commit PRD
        commit_sha = None
        if self.config.auto_commit:
            commit_sha = self.branch_manager.commit_file(
                prd_path,
                f"docs: add PRD for {analysis.priority_item}",
            )
        
        return PRDResult(
            path=prd_path,
            title=analysis.priority_item,
            task_count=task_count,
            generated_at=datetime.now(),
            commit_sha=commit_sha,
        )
    
    def _extract_feature_name(self, branch_name: str) -> str:
        """Extract feature name from branch name."""
        import re
        # Remove prefix (e.g., ralph/fix-signup -> fix-signup)
        return re.sub(r'^[a-zA-Z]+/', '', branch_name)
    
    def _generate_prd_prompt(self, analysis: AnalysisOutput, output_path: Path) -> str:
        """Generate the PRD creation prompt."""
        from .prompts.prd import PRD_PROMPT_TEMPLATE
        
        criteria_text = "\n".join(f"- {c}" for c in analysis.acceptance_criteria)
        
        return PRD_PROMPT_TEMPLATE.format(
            priority_item=analysis.priority_item,
            description=analysis.description,
            rationale=analysis.rationale,
            acceptance_criteria=criteria_text,
            output_path=output_path,
        )
    
    def _call_claude_autonomous(self, prompt: str) -> str:
        """Call Claude CLI in autonomous mode."""
        result = self.cmd_runner.run_claude(
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            timeout=600,  # 10 minutes
            allowed_tools=None,  # All tools
            output_format="text",
        )
        
        if result.exit_code != 0:
            raise PRDGenerationError(f"Claude failed: {result.stderr}")
        
        return result.stdout
    
    def _count_tasks_in_prd(self, prd_path: Path) -> int:
        """Count T-XXX tasks in PRD."""
        import re
        content = prd_path.read_text()
        matches = re.findall(r'###\s+T-\d+', content)
        return len(matches)
```

#### 4.4.2 PRD Prompt Template

```python
# autopilot/prompts/prd.py

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
```

---

### 4.5 Task Generation

**Purpose:** Convert PRD to executable `prd.json` task list.

#### 4.5.1 Tasks Generator

```python
# autopilot/tasks_gen.py

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional
import json

@dataclass
class TasksResult:
    path: Path
    task_count: int
    branch_name: str
    generated_at: datetime
    commit_sha: Optional[str]

class TasksGenerator:
    """Generates prd.json from PRD markdown."""
    
    def __init__(
        self,
        config: TasksConfig,
        repo_root: Path,
        cmd_runner: CommandRunner,
        branch_manager: BranchManager,
    ):
        self.config = config
        self.repo_root = repo_root
        self.cmd_runner = cmd_runner
        self.branch_manager = branch_manager
    
    def generate(self, prd_path: Path, branch_name: str) -> TasksResult:
        """Generate prd.json from PRD.
        
        Args:
            prd_path: Path to PRD markdown
            branch_name: Git branch name
        
        Returns: TasksResult with path and metadata
        """
        output_path = self.repo_root / self.config.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate prompt
        prompt = self._generate_tasks_prompt(prd_path, output_path, branch_name)
        
        # Call Claude CLI
        result = self._call_claude(prompt)
        
        # Verify prd.json was created
        if not output_path.exists():
            raise TasksGenerationError(f"prd.json was not created at {output_path}")
        
        # Validate schema
        task_list = self._validate_prd_json(output_path)
        task_count = len(task_list["tasks"])
        
        # Check task count bounds
        if task_count < self.config.min_count:
            raise TasksGenerationError(
                f"Generated {task_count} tasks, minimum is {self.config.min_count}"
            )
        if task_count > self.config.max_count:
            raise TasksGenerationError(
                f"Generated {task_count} tasks, maximum is {self.config.max_count}"
            )
        
        # Commit prd.json
        commit_sha = None
        if self.config.auto_commit:
            commit_sha = self.branch_manager.commit_file(
                output_path,
                f"chore: add prd.json tasks for {branch_name}",
            )
        
        return TasksResult(
            path=output_path,
            task_count=task_count,
            branch_name=branch_name,
            generated_at=datetime.now(),
            commit_sha=commit_sha,
        )
    
    def _generate_tasks_prompt(
        self,
        prd_path: Path,
        output_path: Path,
        branch_name: str,
    ) -> str:
        """Generate the tasks creation prompt."""
        from .prompts.tasks import TASKS_PROMPT_TEMPLATE
        
        return TASKS_PROMPT_TEMPLATE.format(
            prd_path=prd_path,
            output_path=output_path,
            branch_name=branch_name,
            min_tasks=self.config.min_count,
            max_tasks=self.config.max_count,
        )
    
    def _call_claude(self, prompt: str) -> str:
        """Call Claude CLI for task generation."""
        result = self.cmd_runner.run_claude(
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            timeout=600,
            allowed_tools=["Read", "Write", "Glob", "LS"],
            output_format="text",
        )
        
        if result.exit_code != 0:
            raise TasksGenerationError(f"Claude failed: {result.stderr}")
        
        return result.stdout
    
    def _validate_prd_json(self, path: Path) -> dict:
        """Validate prd.json against schema.
        
        Returns: Parsed JSON data
        Raises: TasksGenerationError if invalid
        """
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise TasksGenerationError(f"Invalid JSON: {e}")
        
        # Required fields
        required = ["project", "branchName", "description", "tasks"]
        for field in required:
            if field not in data:
                raise TasksGenerationError(f"Missing required field: {field}")
        
        # Validate each task
        for i, task in enumerate(data["tasks"]):
            task_required = ["id", "title", "acceptanceCriteria", "priority", "passes"]
            for field in task_required:
                if field not in task:
                    raise TasksGenerationError(
                        f"Task {i} missing required field: {field}"
                    )
            
            # Ensure passes is False initially
            if task["passes"] != False:
                task["passes"] = False
        
        # Write back sanitized version
        path.write_text(json.dumps(data, indent=2))
        
        return data
```

#### 4.5.2 Tasks Prompt Template

```python
# autopilot/prompts/tasks.py

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

OUTPUT FORMAT:
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
```

---

### 4.6 Verified Execution

**Purpose:** Run the verified execution engine on generated tasks.

#### 4.6.1 Execution Integration

```python
# autopilot/orchestrator.py (partial)

def run_verified_execution(
    self,
    prd_path: Path,
    max_iterations: Optional[int] = None,
) -> ExecutionResult:
    """Run verified execution engine on tasks.
    
    This delegates to the main ralph run command internally.
    
    Args:
        prd_path: Path to prd.json
        max_iterations: Override max iterations
    
    Returns: ExecutionResult with completion status
    """
    from ..session import SessionManager
    from ..tasks import TaskParser, TaskSelector, TaskStatusManager
    from ..agents import PromptGenerator, SignalValidator
    from ..gates import GateRunner
    from ..ui import UIFixLoop
    
    # Load config
    config = self.config_loader.load()
    
    # Initialize session
    session_mgr = SessionManager(self.session_dir)
    session = session_mgr.create(prd_path, config)
    
    # Update run state
    self.run_state.update(
        status=RunStatus.EXECUTING,
        session_id=session.session_id,
    )
    
    try:
        # Run main task loop
        from ..engine import MainLoop
        loop = MainLoop(
            session=session,
            config=config,
            cmd_runner=self.cmd_runner,
        )
        
        task_result = loop.run(
            max_iterations=max_iterations or config.limits.max_iterations
        )
        
        if not task_result.all_complete:
            return ExecutionResult(
                success=False,
                tasks_completed=task_result.completed,
                tasks_total=task_result.total,
                failure_reason=f"Task loop incomplete: {task_result.failure_reason}",
            )
        
        # Run post-verification if enabled
        if config.ui and config.ui.agent_browser.enabled:
            self.run_state.update(status=RunStatus.VERIFYING)
            
            verify_result = loop.run_post_verification()
            if not verify_result.success:
                return ExecutionResult(
                    success=False,
                    tasks_completed=task_result.completed,
                    tasks_total=task_result.total,
                    failure_reason=f"Verification failed: {verify_result.failure_reason}",
                )
        
        return ExecutionResult(
            success=True,
            tasks_completed=task_result.completed,
            tasks_total=task_result.total,
        )
        
    except Exception as e:
        session_mgr.abort(session, str(e))
        raise
```

---

### 4.7 PR Creation

**Purpose:** Create a pull request with the completed changes.

#### 4.7.1 PR Creator

```python
# autopilot/pr.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class PRResult:
    url: str
    number: int
    title: str
    branch: str

class PRCreator:
    """Creates pull requests via gh CLI."""
    
    def __init__(
        self,
        config: PRConfig,
        git_config: GitConfig,
        cmd_runner: CommandRunner,
    ):
        self.config = config
        self.git_config = git_config
        self.cmd_runner = cmd_runner
    
    def create(
        self,
        branch_name: str,
        analysis: AnalysisOutput,
        tasks_completed: int,
        tasks_total: int,
        progress_content: str,
        prd_json: dict,
    ) -> PRResult:
        """Create a pull request.
        
        Args:
            branch_name: Feature branch name
            analysis: Analysis output
            tasks_completed: Number of completed tasks
            tasks_total: Total number of tasks
            progress_content: Content from progress.txt
            prd_json: Parsed prd.json data
        
        Returns: PRResult with PR URL and details
        """
        # Push branch first
        self._push_branch(branch_name)
        
        # Generate PR title
        title = self._generate_title(analysis.priority_item)
        
        # Generate PR body
        body = self._generate_body(
            analysis=analysis,
            tasks_completed=tasks_completed,
            tasks_total=tasks_total,
            progress_content=progress_content,
            prd_json=prd_json,
        )
        
        # Create PR via gh CLI
        result = self.cmd_runner.run(
            f'gh pr create --title "{title}" --body "{body}" '
            f'--base {self.git_config.base_branch} --head {branch_name}'
        )
        
        if result.exit_code != 0:
            raise PRCreationError(f"Failed to create PR: {result.stderr}")
        
        # Parse PR URL from output
        pr_url = result.stdout.strip()
        pr_number = self._extract_pr_number(pr_url)
        
        return PRResult(
            url=pr_url,
            number=pr_number,
            title=title,
            branch=branch_name,
        )
    
    def _push_branch(self, branch_name: str) -> None:
        """Push branch to remote."""
        result = self.cmd_runner.run(
            f"git push -u {self.git_config.remote} {branch_name}"
        )
        if result.exit_code != 0:
            raise PRCreationError(f"Failed to push branch: {result.stderr}")
    
    def _generate_title(self, priority_item: str) -> str:
        """Generate PR title from template."""
        template = self.config.title_template
        return template.format(priority_item=priority_item)
    
    def _generate_body(
        self,
        analysis: AnalysisOutput,
        tasks_completed: int,
        tasks_total: int,
        progress_content: str,
        prd_json: dict,
    ) -> str:
        """Generate PR body."""
        # Get last 50 lines of progress
        progress_lines = progress_content.strip().split("\n")[-50:]
        progress_excerpt = "\n".join(progress_lines)
        
        # Format task summary
        task_summary = "\n".join(
            f"- {t['id']}: {t['title']} - {'✅' if t['passes'] else '❌'}"
            for t in prd_json["tasks"]
        )
        
        return f"""## Ralph Autopilot: {analysis.priority_item}

**Generated from report:** {analysis.source_report}

### Rationale
{analysis.rationale}

### Acceptance Criteria
{chr(10).join(f'- [ ] {c}' for c in analysis.acceptance_criteria)}

### Tasks Completed ({tasks_completed}/{tasks_total})
{task_summary}

### Progress Log
```
{progress_excerpt}
```

---
*This PR was automatically generated by Ralph Autopilot from report analysis.*
"""
    
    def _extract_pr_number(self, pr_url: str) -> int:
        """Extract PR number from URL."""
        import re
        match = re.search(r'/pull/(\d+)', pr_url)
        return int(match.group(1)) if match else 0
```

---

## 5. Data Models

### 5.1 Autopilot Run State

```python
# autopilot/run_state.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import json

class RunStatus(Enum):
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

class RunStateManager:
    """Manages autopilot run persistence."""
    
    def __init__(self, autopilot_dir: Path):
        self.autopilot_dir = autopilot_dir
        self.runs_dir = autopilot_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
    
    def create(self) -> AutopilotRun:
        """Create a new run with generated ID."""
        run_id = self._generate_run_id()
        run = AutopilotRun(
            run_id=run_id,
            started_at=datetime.now(),
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
            run = self.load(run_path.stem)
            if run.status not in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABORTED]:
                return run
        return None
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID."""
        import secrets
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        rand = secrets.token_hex(4)
        return f"{ts}-{rand}"
    
    def _save(self, run: AutopilotRun) -> None:
        """Save run state to disk."""
        path = self.runs_dir / f"{run.run_id}.json"
        path.write_text(json.dumps(self._to_dict(run), indent=2))
    
    def _to_dict(self, run: AutopilotRun) -> dict:
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
    
    def _from_dict(self, data: dict) -> AutopilotRun:
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
```

---

## 6. Configuration Contract

### 6.1 Autopilot Configuration in ralph.yml

```yaml
# .ralph/ralph.yml (autopilot section)

autopilot:
  enabled: true
  
  # Report discovery
  reports_dir: "./reports"          # Directory containing analysis reports
  report_patterns:                  # Optional file patterns
    - "*.md"
    - "*.txt"
  
  # Branch settings
  branch_prefix: "ralph/"           # Prefix for created branches
  
  # PR settings
  create_pr: true                   # Create PR after completion
  
  # Analysis phase
  analysis:
    provider: "anthropic"           # anthropic | openai | openrouter | gateway
    model: null                     # Optional model override
    recent_days: 7                  # Exclude items fixed in last N days
  
  # PRD generation
  prd:
    mode: "autonomous"              # autonomous | interactive
    output_dir: "./tasks"           # Where to save PRD markdown
    auto_commit: true               # Commit PRD to branch
  
  # Task generation
  tasks:
    output: ".ralph/prd.json"       # Output path
    min_count: 8                    # Minimum tasks required
    max_count: 15                   # Maximum tasks allowed
    auto_commit: true               # Commit tasks to branch
  
  # Memory / progress tracking
  memory:
    progress: ".ralph/progress.txt"         # Progress log
    archive: ".ralph/autopilot/archive"     # Archived runs
```

### 6.2 Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API key | One of these |
| `OPENAI_API_KEY` | OpenAI API key | required |
| `OPENROUTER_API_KEY` | OpenRouter API key | |
| `AI_GATEWAY_API_KEY` | AI Gateway API key | |
| `VERCEL_OIDC_TOKEN` | Vercel OIDC token | |
| `AI_GATEWAY_URL` | Custom AI Gateway URL | Optional |

---

## 7. Prompt Templates

### 7.1 Prompt Template Architecture

All prompts are stored in `ralph/autopilot/prompts/` as Python modules with template strings. This allows:

1. **Version control** of prompt text
2. **Type-safe** parameter substitution
3. **Testing** of prompt generation
4. **Overrides** via config (future)

```python
# autopilot/prompts/__init__.py

from .analysis import ANALYSIS_PROMPT_TEMPLATE
from .prd import PRD_PROMPT_TEMPLATE
from .tasks import TASKS_PROMPT_TEMPLATE

__all__ = [
    "ANALYSIS_PROMPT_TEMPLATE",
    "PRD_PROMPT_TEMPLATE", 
    "TASKS_PROMPT_TEMPLATE",
]
```

### 7.2 Prompt Parameters

| Prompt | Parameters |
|--------|------------|
| Analysis | `report_content`, `recent_fixes` |
| PRD | `priority_item`, `description`, `rationale`, `acceptance_criteria`, `output_path` |
| Tasks | `prd_path`, `output_path`, `branch_name`, `min_tasks`, `max_tasks` |

---

## 8. Error Handling

### 8.1 Error Hierarchy

```python
# ralph/autopilot/errors.py

class AutopilotError(Exception):
    """Base class for autopilot errors."""
    pass

class ReportDiscoveryError(AutopilotError):
    """Error during report discovery phase."""
    pass

class AnalysisError(AutopilotError):
    """Error during report analysis phase."""
    pass

class BranchError(AutopilotError):
    """Error during branch management."""
    pass

class PRDGenerationError(AutopilotError):
    """Error during PRD generation."""
    pass

class TasksGenerationError(AutopilotError):
    """Error during tasks generation."""
    pass

class ExecutionError(AutopilotError):
    """Error during verified execution."""
    pass

class PRCreationError(AutopilotError):
    """Error during PR creation."""
    pass
```

### 8.2 Error Recovery

```python
# autopilot/orchestrator.py (error handling)

def run(self, dry_run: bool = False) -> AutopilotResult:
    """Run the full autopilot pipeline with error recovery."""
    
    # Check for incomplete run to resume
    incomplete = self.run_state_mgr.get_latest_incomplete()
    if incomplete:
        self.logger.info(f"Resuming incomplete run: {incomplete.run_id}")
        run = incomplete
    else:
        run = self.run_state_mgr.create()
    
    try:
        # Phase 1: Report Discovery
        if run.status == RunStatus.PENDING:
            run = self._run_discovery_phase(run)
        
        # Phase 2: Analysis
        if run.status == RunStatus.ANALYZING:
            run = self._run_analysis_phase(run)
        
        if dry_run:
            self.logger.info("Dry run - stopping after analysis")
            return AutopilotResult(
                success=True,
                run_id=run.run_id,
                dry_run=True,
                analysis=self._load_analysis(run.analysis_path),
            )
        
        # Phase 3: Branch Management
        if run.status == RunStatus.BRANCHING:
            run = self._run_branch_phase(run)
        
        # Phase 4: PRD Generation
        if run.status == RunStatus.PLANNING:
            run = self._run_prd_phase(run)
        
        # Phase 5: Tasks Generation
        if run.tasks_path is None:
            run = self._run_tasks_phase(run)
        
        # Phase 6: Verified Execution
        if run.status == RunStatus.EXECUTING:
            run = self._run_execution_phase(run)
        
        # Phase 7: PR Creation
        if run.status == RunStatus.PUSHING and self.config.create_pr:
            run = self._run_pr_phase(run)
        
        # Mark complete
        run = self.run_state_mgr.update(
            run,
            status=RunStatus.COMPLETED,
            completed_at=datetime.now(),
        )
        
        return AutopilotResult(
            success=True,
            run_id=run.run_id,
            pr_url=run.pr_url,
            tasks_completed=run.tasks_completed,
            tasks_total=run.tasks_total,
        )
        
    except AutopilotError as e:
        # Mark run as failed
        self.run_state_mgr.update(
            run,
            status=RunStatus.FAILED,
            failure_reason=str(e),
            failure_phase=run.status.value,
            completed_at=datetime.now(),
        )
        raise
```

---

## 9. Artifact Management

### 9.1 Directory Structure

```
.ralph/
├── ralph.yml                      # Configuration
├── prd.json                       # Generated tasks (active)
├── progress.txt                   # Progress log (active)
└── autopilot/
    ├── analysis.json              # Latest analysis output
    ├── runs/
    │   ├── 20260125-143022-a1b2.json   # Run state
    │   ├── 20260124-091500-c3d4.json
    │   └── ...
    └── archive/
        └── 2026-01-24-fix-signup/
            ├── prd.json           # Archived tasks
            ├── progress.txt       # Archived progress
            └── analysis.json      # Archived analysis
```

### 9.2 Archival Logic

```python
# autopilot/memory.py

class MemoryManager:
    """Manages progress tracking and archival."""
    
    def __init__(self, config: MemoryConfig, repo_root: Path):
        self.config = config
        self.repo_root = repo_root
        self.progress_path = repo_root / config.progress
        self.archive_dir = repo_root / config.archive
    
    def archive_previous_run(self, current_branch: str) -> Optional[Path]:
        """Archive previous run if branch changed.
        
        Returns: Path to archive folder, or None if no archive
        """
        prd_path = self.repo_root / ".ralph/prd.json"
        if not prd_path.exists():
            return None
        
        try:
            prd_data = json.loads(prd_path.read_text())
            previous_branch = prd_data.get("branchName", "")
        except:
            return None
        
        if previous_branch == current_branch:
            return None  # Same branch, no archive
        
        # Create archive folder
        date = datetime.now().strftime("%Y-%m-%d")
        folder_name = previous_branch.split("/")[-1] or "unknown"
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
        """Append message to progress log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_path, "a") as f:
            f.write(line)
    
    def get_progress_content(self, max_lines: int = 100) -> str:
        """Get progress log content."""
        if not self.progress_path.exists():
            return ""
        
        lines = self.progress_path.read_text().strip().split("\n")
        return "\n".join(lines[-max_lines:])
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

| Module | Test Focus |
|--------|------------|
| `discovery.py` | Report finding, filtering, validation |
| `analysis.py` | Prompt generation, response parsing, provider detection |
| `branch.py` | Branch creation, checkout, commit operations |
| `prd_gen.py` | Prompt generation, file verification |
| `tasks_gen.py` | Prompt generation, schema validation |
| `pr.py` | Title/body generation, URL parsing |
| `run_state.py` | State persistence, recovery |
| `memory.py` | Archival, progress logging |

### 10.2 Integration Tests

```python
# tests/autopilot/test_pipeline.py

def test_full_pipeline_mock_llm():
    """Test full pipeline with mocked LLM responses."""
    # Setup fixture repo with reports
    # Configure mock LLM responses
    # Run autopilot
    # Verify:
    #   - analysis.json created
    #   - PRD created
    #   - prd.json created with valid schema
    #   - Branch created
    #   - (PR creation mocked)

def test_dry_run_stops_after_analysis():
    """Test --dry-run flag stops pipeline after analysis."""

def test_resume_from_failure():
    """Test resuming incomplete run after failure."""

def test_archive_previous_run():
    """Test archival when branch changes."""
```

### 10.3 Mock LLM Responses

```python
# tests/autopilot/fixtures/mock_responses.py

MOCK_ANALYSIS_RESPONSE = """{
  "priority_item": "Fix signup form validation",
  "description": "The signup form is not validating email format correctly, leading to invalid submissions.",
  "rationale": "This is causing 15% of signup attempts to fail, directly impacting conversion.",
  "acceptance_criteria": [
    "Email validation shows error for invalid formats",
    "Valid emails are accepted without error",
    "Form cannot be submitted with invalid email"
  ],
  "estimated_tasks": 8,
  "branch_name": "ralph/fix-signup-validation"
}"""

MOCK_PRD_OUTPUT = """# PRD: Fix Signup Form Validation

## Introduction
Fix email validation on the signup form to properly reject invalid email formats.

## Goals
- Implement proper email format validation
- Show clear error messages for invalid emails
- Prevent form submission with invalid data

## Tasks

### T-001: Audit current email validation
...
"""
```

---

## Appendix A: CLI Integration

### A.1 Autopilot Command

```python
# cli.py (autopilot command)

@cli.command()
@click.option("--reports", type=Path, default="./reports", help="Reports directory")
@click.option("--dry-run", is_flag=True, help="Stop after analysis, show plan")
@click.option("--create-pr/--no-create-pr", default=None, help="Override PR creation")
@click.option("--resume", is_flag=True, help="Resume last incomplete run")
def autopilot(reports, dry_run, create_pr, resume):
    """Run autopilot self-improvement mode.
    
    1. Find latest report in reports directory
    2. Analyze report to pick #1 priority
    3. Generate PRD and tasks
    4. Run verified execution loop
    5. Create PR (optional)
    
    Examples:
        ralph autopilot --reports ./reports
        ralph autopilot --dry-run
        ralph autopilot --no-create-pr
        ralph autopilot --resume
    """
    from ralph.autopilot import AutopilotOrchestrator
    
    orchestrator = AutopilotOrchestrator(
        repo_root=Path.cwd(),
        reports_dir=reports,
        create_pr_override=create_pr,
    )
    
    if resume:
        result = orchestrator.resume()
    else:
        result = orchestrator.run(dry_run=dry_run)
    
    if result.success:
        click.echo(f"✅ Autopilot complete!")
        if result.pr_url:
            click.echo(f"   PR: {result.pr_url}")
        click.echo(f"   Tasks: {result.tasks_completed}/{result.tasks_total}")
    else:
        click.echo(f"❌ Autopilot failed: {result.failure_reason}", err=True)
        raise SystemExit(1)
```

---

## Appendix B: Scheduling (launchd)

### B.1 Example launchd plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ralph.autopilot</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ralph</string>
        <string>autopilot</string>
        <string>--reports</string>
        <string>./reports</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/you/projects/myapp</string>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
        <key>ANTHROPIC_API_KEY</key>
        <string>sk-ant-...</string>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/tmp/ralph-autopilot.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/ralph-autopilot.err</string>
</dict>
</plist>
```

---

*End of Autopilot Module Design Specification*
