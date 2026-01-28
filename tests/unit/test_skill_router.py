"""Unit tests for skill routing module."""

import pytest
from dataclasses import dataclass
from typing import Optional

from ralph_orchestrator.skills import (
    SkillRouter,
    SkillMapping,
    SkillInvocation,
    DEFAULT_SKILL_MAPPINGS,
)


@dataclass
class MockTask:
    """Mock task for testing."""

    id: str = "T-001"
    title: str = "Test task"
    description: str = ""
    affects_frontend: bool = False
    skill: Optional[str] = None


class TestSkillMapping:
    """Tests for SkillMapping dataclass."""

    def test_matches_text_case_insensitive(self):
        """Pattern matching should be case insensitive."""
        mapping = SkillMapping(
            skill_name="frontend-design",
            patterns=["React", "frontend"],
        )
        assert mapping.matches_text("react component")
        assert mapping.matches_text("REACT COMPONENT")
        assert mapping.matches_text("Frontend development")
        assert not mapping.matches_text("python backend")

    def test_matches_text_partial(self):
        """Patterns should match as substrings."""
        mapping = SkillMapping(
            skill_name="frontend-design",
            patterns=["ui"],
        )
        assert mapping.matches_text("Build UI component")
        assert mapping.matches_text("guitar hero")  # Contains "ui" in "guitar"
        assert not mapping.matches_text("backend service")

    def test_empty_patterns(self):
        """Empty patterns should not match anything."""
        mapping = SkillMapping(skill_name="test", patterns=[])
        assert not mapping.matches_text("anything")


class TestSkillInvocation:
    """Tests for SkillInvocation dataclass."""

    def test_get_prompt_prefix(self):
        """Should generate correct prompt prefix."""
        invocation = SkillInvocation(
            skill_name="frontend-design",
            reason="Pattern match",
        )
        prefix = invocation.get_prompt_prefix()
        assert "frontend-design" in prefix
        assert prefix.startswith("Use the /")

    def test_explicit_flag(self):
        """Should track if skill was explicit."""
        explicit = SkillInvocation(skill_name="test", explicit=True)
        auto = SkillInvocation(skill_name="test", explicit=False)
        assert explicit.explicit
        assert not auto.explicit


class TestSkillRouter:
    """Tests for SkillRouter class."""

    def test_disabled_returns_none(self):
        """Disabled router should always return None."""
        router = SkillRouter(enabled=False)
        task = MockTask(title="Build React component")
        assert router.detect_skill(task) is None

    def test_explicit_skill_takes_priority(self):
        """Explicit task.skill should override auto-detection."""
        router = SkillRouter()
        task = MockTask(
            title="Build React component",  # Would match frontend-design
            skill="docx",  # But explicit skill is docx
        )
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "docx"
        assert result.explicit

    def test_affects_frontend_triggers_frontend_skill(self):
        """affects_frontend=True should trigger frontend-design."""
        router = SkillRouter()
        task = MockTask(
            title="Update API endpoint",  # Doesn't match frontend patterns
            affects_frontend=True,
        )
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "frontend-design"
        assert "affectsFrontend" in result.reason

    def test_pattern_matching_frontend(self):
        """Should detect frontend skill from patterns."""
        router = SkillRouter()
        task = MockTask(title="Add new React component for dashboard")
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "frontend-design"

    def test_pattern_matching_docx(self):
        """Should detect docx skill from patterns."""
        router = SkillRouter()
        task = MockTask(title="Create user manual document")
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "docx"

    def test_pattern_matching_xlsx(self):
        """Should detect xlsx skill from patterns."""
        router = SkillRouter()
        task = MockTask(title="Data analysis in spreadsheet")
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "xlsx"

    def test_pattern_matching_pdf(self):
        """Should detect pdf skill from patterns."""
        router = SkillRouter()
        task = MockTask(title="Generate PDF report")
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "pdf"

    def test_no_match_returns_none(self):
        """Should return None if no patterns match."""
        router = SkillRouter()
        task = MockTask(title="Fix database connection issue")
        result = router.detect_skill(task)
        assert result is None

    def test_auto_detect_disabled(self):
        """Disabled auto-detect should skip pattern matching."""
        router = SkillRouter(auto_detect=False)
        task = MockTask(title="Build React component")
        result = router.detect_skill(task)
        assert result is None

    def test_auto_detect_disabled_but_explicit_works(self):
        """Explicit skill should work even with auto-detect disabled."""
        router = SkillRouter(auto_detect=False)
        task = MockTask(
            title="Build React component",
            skill="frontend-design",
        )
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "frontend-design"

    def test_custom_mappings(self):
        """Custom mappings should be used."""
        custom = SkillMapping(
            skill_name="custom-skill",
            patterns=["special"],
            priority=100,  # High priority
        )
        router = SkillRouter(mappings=[custom])
        task = MockTask(title="Special feature")
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "custom-skill"

    def test_priority_ordering(self):
        """Higher priority mappings should be checked first."""
        low = SkillMapping(skill_name="low", patterns=["test"], priority=1)
        high = SkillMapping(skill_name="high", patterns=["test"], priority=10)
        router = SkillRouter(mappings=[low, high])
        task = MockTask(title="test task")
        result = router.detect_skill(task)
        assert result is not None
        assert result.skill_name == "high"

    def test_get_skill_prompt_prefix(self):
        """Should generate prompt prefix for skill."""
        router = SkillRouter()
        skill = SkillInvocation(skill_name="frontend-design", reason="test")
        prefix = router.get_skill_prompt_prefix(skill)
        assert "frontend-design" in prefix


class TestDefaultMappings:
    """Tests for default skill mappings."""

    def test_default_mappings_exist(self):
        """Default mappings should be defined."""
        assert len(DEFAULT_SKILL_MAPPINGS) > 0

    def test_frontend_design_mapping(self):
        """frontend-design mapping should exist with common patterns."""
        frontend = next(
            (m for m in DEFAULT_SKILL_MAPPINGS if m.skill_name == "frontend-design"),
            None,
        )
        assert frontend is not None
        assert "react" in [p.lower() for p in frontend.patterns]
        assert "component" in [p.lower() for p in frontend.patterns]

    def test_all_mappings_have_skill_name(self):
        """All mappings should have skill_name set."""
        for mapping in DEFAULT_SKILL_MAPPINGS:
            assert mapping.skill_name
            assert len(mapping.skill_name) > 0
