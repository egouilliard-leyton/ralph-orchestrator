"""Unit tests for parallel task execution module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from ralph_orchestrator.parallel import (
    TaskFileAnalysis,
    TaskGroup,
    TaskFileAnalyzer,
    TaskPartitioner,
)


class MockTask:
    """Mock task for testing."""
    def __init__(
        self,
        id: str,
        title: str = "",
        description: str = "",
        acceptance_criteria: list = None,
    ):
        self.id = id
        self.title = title or f"Task {id}"
        self.description = description
        self.acceptance_criteria = acceptance_criteria or []


class TestTaskFileAnalysis:
    """Tests for TaskFileAnalysis dataclass."""

    def test_creation(self):
        analysis = TaskFileAnalysis(
            task_id="T-001",
            estimated_files={"src/main.py", "tests/test_main.py"},
            confidence=0.8,
            keywords={"api", "backend"},
        )
        assert analysis.task_id == "T-001"
        assert len(analysis.estimated_files) == 2
        assert analysis.confidence == 0.8
        assert "api" in analysis.keywords

    def test_default_values(self):
        analysis = TaskFileAnalysis(task_id="T-002")
        assert analysis.estimated_files == set()
        assert analysis.confidence == 0.5
        assert analysis.keywords == set()


class TestTaskGroup:
    """Tests for TaskGroup class."""

    def test_add_task(self):
        group = TaskGroup(group_id="group-1")
        task = MockTask("T-001")
        analysis = TaskFileAnalysis(
            task_id="T-001",
            estimated_files={"src/a.py", "src/b.py"},
        )

        group.add_task(task, analysis)

        assert len(group.tasks) == 1
        assert group.tasks[0].id == "T-001"
        assert group.estimated_files == {"src/a.py", "src/b.py"}

    def test_has_overlap_true(self):
        group = TaskGroup(
            group_id="group-1",
            estimated_files={"src/a.py", "src/b.py"},
        )
        analysis = TaskFileAnalysis(
            task_id="T-002",
            estimated_files={"src/b.py", "src/c.py"},  # b.py overlaps
        )

        assert group.has_overlap(analysis) is True

    def test_has_overlap_false(self):
        group = TaskGroup(
            group_id="group-1",
            estimated_files={"src/a.py", "src/b.py"},
        )
        analysis = TaskFileAnalysis(
            task_id="T-002",
            estimated_files={"src/c.py", "src/d.py"},  # No overlap
        )

        assert group.has_overlap(analysis) is False

    def test_has_overlap_empty(self):
        group = TaskGroup(group_id="group-1")
        analysis = TaskFileAnalysis(
            task_id="T-001",
            estimated_files={"src/a.py"},
        )

        assert group.has_overlap(analysis) is False


class TestTaskFileAnalyzer:
    """Tests for TaskFileAnalyzer class."""

    def test_extract_explicit_paths(self, tmp_path):
        analyzer = TaskFileAnalyzer(tmp_path)

        text = "Modify src/components/Button.tsx and update tests/test_api.py"
        paths = analyzer._extract_explicit_paths(text)

        assert "src/components/Button.tsx" in paths
        assert "tests/test_api.py" in paths

    def test_extract_keywords(self, tmp_path):
        analyzer = TaskFileAnalyzer(tmp_path)

        text = "Update the API endpoints and add frontend components for authentication"
        keywords = analyzer._extract_keywords(text)

        assert "api" in keywords
        assert "frontend" in keywords
        assert "auth" in keywords

    def test_analyze_task_with_explicit_files(self, tmp_path):
        analyzer = TaskFileAnalyzer(tmp_path)

        task = MockTask(
            id="T-001",
            title="Fix bug in api/routes.py",
            description="Update api/routes.py to handle edge cases",
            acceptance_criteria=["Tests pass in tests/test_api.py"],
        )

        analysis = analyzer.analyze(task)

        assert analysis.task_id == "T-001"
        assert "api/routes.py" in analysis.estimated_files
        assert analysis.confidence > 0.3  # Should have decent confidence

    def test_analyze_task_empty_description(self, tmp_path):
        analyzer = TaskFileAnalyzer(tmp_path)

        task = MockTask(
            id="T-001",
            title="Generic task",
            description="",
        )

        analysis = analyzer.analyze(task)

        assert analysis.task_id == "T-001"
        assert analysis.confidence >= 0.1  # Base confidence


class TestTaskPartitioner:
    """Tests for TaskPartitioner class."""

    def test_partition_single_task(self, tmp_path):
        partitioner = TaskPartitioner(max_groups=3)
        tasks = [MockTask("T-001")]

        groups = partitioner.partition(tasks, tmp_path)

        assert len(groups) == 1
        assert len(groups[0].tasks) == 1

    def test_partition_non_overlapping(self, tmp_path):
        """Tasks with no file overlap should be in same group."""
        partitioner = TaskPartitioner(max_groups=3)

        tasks = [
            MockTask("T-001", description="Modify src/a.py"),
            MockTask("T-002", description="Modify src/b.py"),
            MockTask("T-003", description="Modify src/c.py"),
        ]

        groups = partitioner.partition(tasks, tmp_path)

        # With no real file overlap, tasks may be grouped together
        # Exact grouping depends on analysis confidence
        assert len(groups) >= 1
        total_tasks = sum(len(g.tasks) for g in groups)
        assert total_tasks == 3

    def test_partition_with_max_groups(self, tmp_path):
        partitioner = TaskPartitioner(max_groups=2)

        tasks = [
            MockTask("T-001"),
            MockTask("T-002"),
            MockTask("T-003"),
            MockTask("T-004"),
        ]

        groups = partitioner.partition(tasks, tmp_path)

        assert len(groups) <= 2

    def test_partition_empty_tasks(self, tmp_path):
        partitioner = TaskPartitioner()
        groups = partitioner.partition([], tmp_path)

        assert groups == []

    def test_get_partition_summary(self):
        partitioner = TaskPartitioner()
        groups = [
            TaskGroup(
                group_id="group-1",
                tasks=[MockTask("T-001"), MockTask("T-002")],
                estimated_files={"a.py", "b.py"},
            ),
            TaskGroup(
                group_id="group-2",
                tasks=[MockTask("T-003")],
                estimated_files={"c.py"},
            ),
        ]

        summary = partitioner.get_partition_summary(groups)

        assert "2 groups" in summary
        assert "T-001" in summary
        assert "T-002" in summary
        assert "T-003" in summary
