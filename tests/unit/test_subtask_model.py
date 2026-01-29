"""Unit tests for enhanced Subtask model."""

import pytest
from ralph_orchestrator.tasks.prd import Subtask


class TestSubtaskModel:
    """Tests for enhanced Subtask dataclass."""

    def test_basic_creation(self):
        subtask = Subtask(
            id="T-001.1",
            title="Implement helper function",
            acceptance_criteria=["Function returns correct value", "Has type hints"],
        )

        assert subtask.id == "T-001.1"
        assert subtask.title == "Implement helper function"
        assert len(subtask.acceptance_criteria) == 2
        assert subtask.passes is False
        assert subtask.notes == ""
        assert subtask.description == ""
        assert subtask.independent is False
        assert subtask.promoted_to is None

    def test_creation_with_all_fields(self):
        subtask = Subtask(
            id="T-001.2",
            title="Complex subtask",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            passes=True,
            notes="Completed successfully",
            description="Detailed description of what to do",
            independent=True,
            promoted_to="T-002",
        )

        assert subtask.passes is True
        assert subtask.notes == "Completed successfully"
        assert subtask.description == "Detailed description of what to do"
        assert subtask.independent is True
        assert subtask.promoted_to == "T-002"

    def test_to_dict_minimal(self):
        subtask = Subtask(
            id="T-001.1",
            title="Basic subtask",
            acceptance_criteria=["Criterion"],
        )

        result = subtask.to_dict()

        assert result["id"] == "T-001.1"
        assert result["title"] == "Basic subtask"
        assert result["acceptanceCriteria"] == ["Criterion"]
        assert result["passes"] is False
        assert result["notes"] == ""
        # Optional fields should not be present when empty/default
        assert "description" not in result
        assert "independent" not in result
        assert "promotedTo" not in result

    def test_to_dict_with_optional_fields(self):
        subtask = Subtask(
            id="T-001.1",
            title="Complex subtask",
            acceptance_criteria=["Criterion"],
            description="Detailed description",
            independent=True,
            promoted_to="T-002",
        )

        result = subtask.to_dict()

        assert result["description"] == "Detailed description"
        assert result["independent"] is True
        assert result["promotedTo"] == "T-002"

    def test_from_dict_minimal(self):
        data = {
            "id": "T-001.1",
            "title": "Basic subtask",
            "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
        }

        subtask = Subtask.from_dict(data)

        assert subtask.id == "T-001.1"
        assert subtask.title == "Basic subtask"
        assert subtask.acceptance_criteria == ["Criterion 1", "Criterion 2"]
        assert subtask.passes is False
        assert subtask.notes == ""
        assert subtask.description == ""
        assert subtask.independent is False
        assert subtask.promoted_to is None

    def test_from_dict_with_all_fields(self):
        data = {
            "id": "T-001.2",
            "title": "Full subtask",
            "acceptanceCriteria": ["Criterion"],
            "passes": True,
            "notes": "Done",
            "description": "Full description",
            "independent": True,
            "promotedTo": "T-003",
        }

        subtask = Subtask.from_dict(data)

        assert subtask.id == "T-001.2"
        assert subtask.passes is True
        assert subtask.notes == "Done"
        assert subtask.description == "Full description"
        assert subtask.independent is True
        assert subtask.promoted_to == "T-003"

    def test_roundtrip_serialization(self):
        """Test that to_dict -> from_dict preserves all data."""
        original = Subtask(
            id="T-001.1",
            title="Roundtrip test",
            acceptance_criteria=["A", "B", "C"],
            passes=True,
            notes="Test notes",
            description="Test description",
            independent=True,
            promoted_to="T-005",
        )

        serialized = original.to_dict()
        restored = Subtask.from_dict(serialized)

        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.acceptance_criteria == original.acceptance_criteria
        assert restored.passes == original.passes
        assert restored.notes == original.notes
        assert restored.description == original.description
        assert restored.independent == original.independent
        assert restored.promoted_to == original.promoted_to

    def test_independent_default_false(self):
        """Verify independent defaults to False for backward compatibility."""
        data = {
            "id": "T-001.1",
            "title": "Legacy subtask",
            "acceptanceCriteria": ["Criterion"],
            "passes": False,
        }

        subtask = Subtask.from_dict(data)

        assert subtask.independent is False

    def test_promoted_to_null_handling(self):
        """Test that None/null promotedTo is handled correctly."""
        data = {
            "id": "T-001.1",
            "title": "Test",
            "acceptanceCriteria": ["C"],
            "promotedTo": None,
        }

        subtask = Subtask.from_dict(data)

        assert subtask.promoted_to is None
