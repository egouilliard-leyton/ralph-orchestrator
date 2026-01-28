"""Web researcher for Ralph orchestrator.

Uses web search to find documentation, best practices, and API references.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from typing import List, Optional

from .models import ResearchResult, ResearchOptions, WebSearchResult


class WebResearcher:
    """Researches web resources for relevant documentation.

    Uses Claude's web search capability to find relevant documentation,
    best practices, and API references for the task at hand.
    """

    def __init__(
        self,
        options: ResearchOptions,
    ):
        """Initialize web researcher.

        Args:
            options: Research configuration options.
        """
        self.options = options

    def research(
        self,
        analysis_context: Optional[str] = None,
        priority_item: Optional[str] = None,
    ) -> ResearchResult:
        """Perform web research.

        Args:
            analysis_context: Optional context from report analysis.
            priority_item: The priority item being researched.

        Returns:
            ResearchResult with web findings.
        """
        start_time = time.time()

        if not self.options.web_enabled:
            return ResearchResult(
                researcher_type="web",
                success=True,
                summary="Web research skipped (disabled)",
            )

        try:
            # Generate search queries based on context
            queries = self._generate_queries(analysis_context, priority_item)

            # Execute searches
            results = []
            for query in queries[: self.options.max_web_queries]:
                search_results = self._execute_search(query)
                results.extend(search_results)

            # Generate summary
            summary = self._generate_summary(results)
            recommendations = self._generate_recommendations(results, analysis_context)

            duration_ms = int((time.time() - start_time) * 1000)

            return ResearchResult(
                researcher_type="web",
                success=True,
                web_results=results,
                summary=summary,
                recommendations=recommendations,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return ResearchResult(
                researcher_type="web",
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _generate_queries(
        self,
        analysis_context: Optional[str],
        priority_item: Optional[str],
    ) -> List[str]:
        """Generate search queries based on context.

        Args:
            analysis_context: Context from report analysis.
            priority_item: The priority item title.

        Returns:
            List of search query strings.
        """
        queries = []

        if priority_item:
            # Clean up priority item for search
            clean_item = priority_item.replace("-", " ").replace("_", " ")
            queries.append(f"{clean_item} best practices")
            queries.append(f"{clean_item} implementation guide")

        if analysis_context:
            # Extract key terms from context
            context_lower = analysis_context.lower()

            # Look for specific technologies
            tech_terms = [
                "react",
                "vue",
                "angular",
                "python",
                "fastapi",
                "django",
                "flask",
                "typescript",
                "tailwind",
                "postgresql",
                "mongodb",
            ]
            for term in tech_terms:
                if term in context_lower and priority_item:
                    queries.append(f"{term} {priority_item}")
                    break

        # Add generic best practices query
        if priority_item:
            queries.append(f"software engineering {priority_item}")

        return queries[:5]  # Limit to 5 queries

    def _execute_search(self, query: str) -> List[WebSearchResult]:
        """Execute a web search query using Claude CLI.

        This uses Claude's web search tool to find relevant results.

        Args:
            query: Search query string.

        Returns:
            List of WebSearchResult objects.
        """
        # Get Claude CLI command
        claude_cmd = os.environ.get("RALPH_CLAUDE_CMD", "claude")
        argv0 = shlex.split(claude_cmd)[0] if claude_cmd else "claude"

        # Build prompt for web search
        prompt = f"""Search the web for: {query}

Return a JSON array with the top 3 most relevant results. Each result should have:
- title: Page title
- url: URL
- snippet: Brief relevant excerpt

Format:
[{{"title": "...", "url": "...", "snippet": "..."}}]

IMPORTANT: Return ONLY the JSON array, no other text."""

        try:
            cmd = [
                argv0,
                "--print",
                "--dangerously-skip-permissions",
                "--output-format",
                "text",
                "--model",
                "sonnet",
                "-p",
                prompt,
            ]

            proc = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                timeout=60,
            )

            if proc.returncode != 0:
                return []

            # Parse JSON from output
            output = proc.stdout.strip()

            # Try to extract JSON array from output
            try:
                # Look for JSON array in output
                start = output.find("[")
                end = output.rfind("]") + 1
                if start >= 0 and end > start:
                    json_str = output[start:end]
                    data = json.loads(json_str)

                    results = []
                    for item in data:
                        if isinstance(item, dict):
                            results.append(
                                WebSearchResult(
                                    query=query,
                                    title=item.get("title", ""),
                                    url=item.get("url", ""),
                                    snippet=item.get("snippet", ""),
                                )
                            )
                    return results
            except json.JSONDecodeError:
                pass

            return []

        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

    def _generate_summary(self, results: List[WebSearchResult]) -> str:
        """Generate a summary of web research findings.

        Args:
            results: List of web search results.

        Returns:
            Summary string.
        """
        if not results:
            return "No relevant web resources found."

        unique_queries = set(r.query for r in results)
        return f"Found {len(results)} relevant resources across {len(unique_queries)} queries."

    def _generate_recommendations(
        self, results: List[WebSearchResult], analysis_context: Optional[str]
    ) -> List[str]:
        """Generate recommendations from web findings.

        Args:
            results: List of web search results.
            analysis_context: Optional analysis context.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        if results:
            recommendations.append(
                "Review web research findings for current best practices"
            )

            # Look for documentation in results
            doc_results = [r for r in results if "doc" in r.title.lower()]
            if doc_results:
                recommendations.append(
                    f"Found {len(doc_results)} documentation resources - check for updates"
                )

        return recommendations
