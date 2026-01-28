"""Data models for research sub-agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ResearchOptions:
    """Options for research phase.

    Attributes:
        enabled: Whether research is enabled overall.
        backend_enabled: Whether backend research is enabled.
        frontend_enabled: Whether frontend research is enabled.
        web_enabled: Whether web research is enabled.
        backend_patterns: Glob patterns for backend files to scan.
        frontend_patterns: Glob patterns for frontend files to scan.
        max_web_queries: Maximum number of web search queries.
    """

    enabled: bool = True
    backend_enabled: bool = True
    frontend_enabled: bool = True
    web_enabled: bool = True
    backend_patterns: List[str] = field(
        default_factory=lambda: [
            "**/*.py",
            "**/models/**",
            "**/routes/**",
            "**/services/**",
            "**/api/**",
        ]
    )
    frontend_patterns: List[str] = field(
        default_factory=lambda: [
            "**/*.tsx",
            "**/*.jsx",
            "**/*.vue",
            "**/components/**",
            "**/pages/**",
        ]
    )
    max_web_queries: int = 5

    @classmethod
    def from_config(cls, config) -> "ResearchOptions":
        """Create options from Ralph config.

        Args:
            config: RalphConfig with optional research section.

        Returns:
            Configured ResearchOptions instance.
        """
        autopilot = config.raw_data.get("autopilot", {})
        research_config = autopilot.get("research", {})

        backend = research_config.get("backend", {})
        frontend = research_config.get("frontend", {})
        web = research_config.get("web", {})

        # Default patterns
        default_backend = [
            "**/*.py",
            "**/models/**",
            "**/routes/**",
            "**/services/**",
            "**/api/**",
        ]
        default_frontend = [
            "**/*.tsx",
            "**/*.jsx",
            "**/*.vue",
            "**/components/**",
            "**/pages/**",
        ]

        return cls(
            enabled=research_config.get("enabled", True),
            backend_enabled=backend.get("enabled", True),
            frontend_enabled=frontend.get("enabled", True),
            web_enabled=web.get("enabled", True),
            backend_patterns=backend.get("patterns", default_backend),
            frontend_patterns=frontend.get("patterns", default_frontend),
            max_web_queries=web.get("max_queries", 5),
        )


@dataclass
class FileInfo:
    """Information about a file found during research.

    Attributes:
        path: Relative path to the file.
        category: Category of the file (model, route, service, component, etc.).
        summary: Brief summary of the file's purpose.
        key_exports: Key exports/classes/functions in the file.
    """

    path: str
    category: str = ""
    summary: str = ""
    key_exports: List[str] = field(default_factory=list)


@dataclass
class WebSearchResult:
    """Result from a web search query.

    Attributes:
        query: The search query that was executed.
        title: Title of the search result.
        url: URL of the result.
        snippet: Relevant snippet from the result.
    """

    query: str
    title: str = ""
    url: str = ""
    snippet: str = ""


@dataclass
class ResearchResult:
    """Result from a single research agent.

    Attributes:
        researcher_type: Type of researcher (backend, frontend, web).
        success: Whether the research completed successfully.
        files: Files discovered during research.
        web_results: Web search results (for web researcher).
        summary: Summary of findings.
        recommendations: Specific recommendations for the PRD.
        error: Error message if research failed.
        duration_ms: Time taken in milliseconds.
    """

    researcher_type: str
    success: bool = False
    files: List[FileInfo] = field(default_factory=list)
    web_results: List[WebSearchResult] = field(default_factory=list)
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class ResearchContext:
    """Combined research context for PRD generation.

    Attributes:
        backend_result: Result from backend researcher.
        frontend_result: Result from frontend researcher.
        web_result: Result from web researcher.
        timestamp: When research was completed.
    """

    backend_result: Optional[ResearchResult] = None
    frontend_result: Optional[ResearchResult] = None
    web_result: Optional[ResearchResult] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_prd_context(self) -> Dict[str, Any]:
        """Convert research context to PRD context dictionary.

        Returns:
            Dictionary suitable for PRD generation prompts.
        """
        context: Dict[str, Any] = {
            "has_research": True,
            "research_timestamp": self.timestamp.isoformat(),
        }

        if self.backend_result and self.backend_result.success:
            context["backend"] = {
                "files": [
                    {
                        "path": f.path,
                        "category": f.category,
                        "summary": f.summary,
                    }
                    for f in self.backend_result.files[:20]  # Limit to top 20
                ],
                "summary": self.backend_result.summary,
                "recommendations": self.backend_result.recommendations,
            }

        if self.frontend_result and self.frontend_result.success:
            context["frontend"] = {
                "files": [
                    {
                        "path": f.path,
                        "category": f.category,
                        "summary": f.summary,
                    }
                    for f in self.frontend_result.files[:20]
                ],
                "summary": self.frontend_result.summary,
                "recommendations": self.frontend_result.recommendations,
            }

        if self.web_result and self.web_result.success:
            context["web"] = {
                "results": [
                    {
                        "query": r.query,
                        "title": r.title,
                        "snippet": r.snippet,
                    }
                    for r in self.web_result.web_results[:10]
                ],
                "summary": self.web_result.summary,
                "recommendations": self.web_result.recommendations,
            }

        return context

    def to_prompt_section(self) -> str:
        """Generate a prompt section with research findings.

        Returns:
            Formatted string for inclusion in PRD prompts.
        """
        sections = []

        if self.backend_result and self.backend_result.success:
            sections.append("## Backend Research Findings\n")
            sections.append(f"{self.backend_result.summary}\n")
            if self.backend_result.recommendations:
                sections.append("### Recommendations:\n")
                for rec in self.backend_result.recommendations:
                    sections.append(f"- {rec}\n")
            sections.append("\n")

        if self.frontend_result and self.frontend_result.success:
            sections.append("## Frontend Research Findings\n")
            sections.append(f"{self.frontend_result.summary}\n")
            if self.frontend_result.recommendations:
                sections.append("### Recommendations:\n")
                for rec in self.frontend_result.recommendations:
                    sections.append(f"- {rec}\n")
            sections.append("\n")

        if self.web_result and self.web_result.success:
            sections.append("## Web Research Findings\n")
            sections.append(f"{self.web_result.summary}\n")
            if self.web_result.web_results:
                sections.append("### Relevant Sources:\n")
                for result in self.web_result.web_results[:5]:
                    sections.append(f"- {result.title}: {result.snippet[:100]}...\n")
            sections.append("\n")

        return "".join(sections) if sections else ""
