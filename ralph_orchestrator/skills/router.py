"""Skill router for Ralph orchestrator.

Routes tasks to specialized Claude skills based on task properties and patterns.
"""

from __future__ import annotations

from typing import List, Optional

from .models import SkillMapping, SkillInvocation
from .defaults import DEFAULT_SKILL_MAPPINGS


class SkillRouter:
    """Routes tasks to appropriate Claude skills.

    The router checks multiple sources in priority order:
    1. Explicit task.skill annotation (highest priority)
    2. Task affectsFrontend flag
    3. Pattern matching on task title and description
    4. File pattern matching (future enhancement)

    Example usage:
        router = SkillRouter()
        skill = router.detect_skill(task)
        if skill:
            prompt = skill.get_prompt_prefix() + base_prompt
    """

    def __init__(
        self,
        mappings: Optional[List[SkillMapping]] = None,
        enabled: bool = True,
        auto_detect: bool = True,
    ):
        """Initialize skill router.

        Args:
            mappings: Custom skill mappings (defaults to DEFAULT_SKILL_MAPPINGS).
            enabled: Whether skill routing is enabled.
            auto_detect: Whether to auto-detect skills from patterns.
        """
        self.mappings = mappings or DEFAULT_SKILL_MAPPINGS
        self.enabled = enabled
        self.auto_detect = auto_detect

        # Sort mappings by priority (highest first)
        self.mappings = sorted(self.mappings, key=lambda m: m.priority, reverse=True)

    def detect_skill(self, task) -> Optional[SkillInvocation]:
        """Detect which skill should handle this task.

        Args:
            task: Task object with id, title, description, etc.

        Returns:
            SkillInvocation if a skill should be used, None otherwise.
        """
        if not self.enabled:
            return None

        # 1. Check explicit task.skill annotation (highest priority)
        explicit_skill = getattr(task, "skill", None)
        if explicit_skill:
            return SkillInvocation(
                skill_name=explicit_skill,
                reason=f"Explicit skill annotation: {explicit_skill}",
                explicit=True,
            )

        # 2. Check affectsFrontend flag
        affects_frontend = getattr(task, "affects_frontend", False)
        if affects_frontend:
            return SkillInvocation(
                skill_name="frontend-design",
                reason="Task affects frontend (affectsFrontend=true)",
                explicit=False,
            )

        # 3. Auto-detect from patterns (if enabled)
        if not self.auto_detect:
            return None

        # Build text to match against
        title = getattr(task, "title", "") or ""
        description = getattr(task, "description", "") or ""
        combined_text = f"{title} {description}"

        # Check each mapping by priority
        for mapping in self.mappings:
            if mapping.matches_text(combined_text):
                return SkillInvocation(
                    skill_name=mapping.skill_name,
                    reason=f"Pattern match: {mapping.description}",
                    explicit=False,
                    mapping=mapping,
                )

        return None

    def get_skill_prompt_prefix(self, skill: SkillInvocation) -> str:
        """Generate prompt prefix to invoke skill.

        Args:
            skill: The skill invocation to generate prefix for.

        Returns:
            Prompt prefix string to prepend to the agent prompt.
        """
        return skill.get_prompt_prefix()

    @classmethod
    def from_config(cls, config) -> "SkillRouter":
        """Create router from Ralph config.

        Args:
            config: RalphConfig with optional skills section.

        Returns:
            Configured SkillRouter instance.
        """
        skills_config = config.raw_data.get("skills", {})
        enabled = skills_config.get("enabled", True)
        auto_detect = skills_config.get("auto_detect", True)

        # Build mappings from config + defaults
        custom_mappings = skills_config.get("custom_mappings", [])
        mappings = list(DEFAULT_SKILL_MAPPINGS)

        for custom in custom_mappings:
            mappings.append(
                SkillMapping(
                    skill_name=custom.get("skill_name", ""),
                    patterns=custom.get("patterns", []),
                    file_patterns=custom.get("file_patterns", []),
                    priority=custom.get("priority", 5),
                    description=custom.get("description", "Custom mapping"),
                )
            )

        return cls(mappings=mappings, enabled=enabled, auto_detect=auto_detect)
