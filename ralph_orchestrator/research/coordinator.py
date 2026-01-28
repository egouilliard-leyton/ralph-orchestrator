"""Research coordinator for Ralph orchestrator.

Orchestrates multiple research sub-agents to gather context for PRD generation.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .models import ResearchContext, ResearchOptions, ResearchResult
from .backend import BackendResearcher
from .frontend import FrontendResearcher
from .web import WebResearcher


class ResearchCoordinator:
    """Coordinates research sub-agents for PRD enhancement.

    Runs backend, frontend, and web researchers in parallel (or sequentially)
    to gather context that improves PRD generation quality.

    Usage:
        coordinator = ResearchCoordinator(
            repo_root=Path("/path/to/repo"),
            options=ResearchOptions(),
        )
        context = coordinator.research(
            analysis_context="User needs better error handling",
            priority_item="Improve error messages",
        )
        prd_context = context.to_prd_context()
    """

    def __init__(
        self,
        repo_root: Path,
        options: Optional[ResearchOptions] = None,
        verbose: bool = False,
    ):
        """Initialize research coordinator.

        Args:
            repo_root: Root directory of the repository.
            options: Research configuration options.
            verbose: Whether to print progress messages.
        """
        self.repo_root = repo_root
        self.options = options or ResearchOptions()
        self.verbose = verbose

        # Initialize researchers
        self.backend = BackendResearcher(repo_root, self.options)
        self.frontend = FrontendResearcher(repo_root, self.options)
        self.web = WebResearcher(self.options)

    def research(
        self,
        analysis_context: Optional[str] = None,
        priority_item: Optional[str] = None,
    ) -> ResearchContext:
        """Execute all enabled research agents.

        Args:
            analysis_context: Context from report analysis.
            priority_item: The priority item title from analysis.

        Returns:
            ResearchContext with all research results.
        """
        if not self.options.enabled:
            if self.verbose:
                print("  Research phase skipped (disabled)")
            return ResearchContext()

        context = ResearchContext()
        start_time = time.time()

        # Run backend research
        if self.options.backend_enabled:
            if self.verbose:
                print("  Running backend research...")
            context.backend_result = self.backend.research(analysis_context)
            if self.verbose:
                self._print_result("Backend", context.backend_result)

        # Run frontend research
        if self.options.frontend_enabled:
            if self.verbose:
                print("  Running frontend research...")
            context.frontend_result = self.frontend.research(analysis_context)
            if self.verbose:
                self._print_result("Frontend", context.frontend_result)

        # Run web research
        if self.options.web_enabled:
            if self.verbose:
                print("  Running web research...")
            context.web_result = self.web.research(analysis_context, priority_item)
            if self.verbose:
                self._print_result("Web", context.web_result)

        total_time = int((time.time() - start_time) * 1000)
        if self.verbose:
            print(f"  Research completed in {total_time}ms")

        return context

    def _print_result(self, name: str, result: ResearchResult) -> None:
        """Print a summary of a research result.

        Args:
            name: Name of the researcher.
            result: The research result.
        """
        if result.success:
            file_count = len(result.files)
            web_count = len(result.web_results)
            if file_count > 0:
                print(f"    {name}: Found {file_count} files ({result.duration_ms}ms)")
            elif web_count > 0:
                print(f"    {name}: Found {web_count} results ({result.duration_ms}ms)")
            else:
                print(f"    {name}: {result.summary[:50]}... ({result.duration_ms}ms)")
        else:
            print(f"    {name}: Failed - {result.error}")

    @classmethod
    def from_config(cls, config, verbose: bool = False) -> "ResearchCoordinator":
        """Create coordinator from Ralph config.

        Args:
            config: RalphConfig with optional research section.
            verbose: Whether to print progress messages.

        Returns:
            Configured ResearchCoordinator instance.
        """
        options = ResearchOptions.from_config(config)
        return cls(
            repo_root=config.repo_root,
            options=options,
            verbose=verbose,
        )
