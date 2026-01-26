"""Agent modules for Ralph orchestrator.

This package contains:
- prompts: Prompt templates for different agent roles
- claude: Claude CLI invocation wrapper
"""

from .prompts import (
    build_implementation_prompt,
    build_test_writing_prompt,
    build_review_prompt,
    build_fix_prompt,
    AgentRole,
)
from .claude import ClaudeRunner, ClaudeResult, invoke_claude

__all__ = [
    "build_implementation_prompt",
    "build_test_writing_prompt",
    "build_review_prompt",
    "build_fix_prompt",
    "AgentRole",
    "ClaudeRunner",
    "ClaudeResult",
    "invoke_claude",
]
