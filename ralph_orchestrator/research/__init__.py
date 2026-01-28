"""Research module for Ralph orchestrator.

Provides research sub-agents for enhanced PRD creation with codebase
and web research capabilities.
"""

from .models import ResearchResult, ResearchContext, ResearchOptions
from .coordinator import ResearchCoordinator
from .backend import BackendResearcher
from .frontend import FrontendResearcher
from .web import WebResearcher

__all__ = [
    "ResearchResult",
    "ResearchContext",
    "ResearchOptions",
    "ResearchCoordinator",
    "BackendResearcher",
    "FrontendResearcher",
    "WebResearcher",
]
