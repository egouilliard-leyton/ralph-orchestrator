"""Data models for skill routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SkillMapping:
    """Mapping of patterns to a skill.

    Attributes:
        skill_name: Name of the Claude skill (e.g., 'frontend-design').
        patterns: Keywords that trigger this skill (matched against task title/description).
        file_patterns: File glob patterns that trigger this skill.
        priority: Higher priority mappings are checked first (default 5).
        description: Human-readable description of when this skill applies.
    """

    skill_name: str
    patterns: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    priority: int = 5
    description: str = ""

    def matches_text(self, text: str) -> bool:
        """Check if any pattern matches the given text (case-insensitive).

        Args:
            text: Text to match against patterns.

        Returns:
            True if any pattern matches.
        """
        text_lower = text.lower()
        for pattern in self.patterns:
            if pattern.lower() in text_lower:
                return True
        return False


@dataclass
class SkillInvocation:
    """Represents a skill to invoke for a task.

    Attributes:
        skill_name: Name of the Claude skill.
        reason: Why this skill was selected.
        explicit: Whether the skill was explicitly specified in the task.
        mapping: The SkillMapping that triggered this invocation (if auto-detected).
    """

    skill_name: str
    reason: str = ""
    explicit: bool = False
    mapping: Optional[SkillMapping] = None

    def get_prompt_prefix(self) -> str:
        """Generate prompt prefix to invoke the skill.

        Returns:
            Prompt prefix string.
        """
        return f"Use the /{self.skill_name} skill for this task.\n\n"
