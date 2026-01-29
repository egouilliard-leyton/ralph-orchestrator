"""Parallel task execution with file-set pre-allocation.

This module provides infrastructure for running tasks in parallel by:
1. Analyzing tasks to estimate which files they'll touch
2. Partitioning tasks into non-overlapping groups
3. Running groups concurrently

The file-set pre-allocation approach ensures tasks in the same parallel
group won't have conflicting file modifications.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .tasks.prd import Task


@dataclass
class TaskFileAnalysis:
    """Analysis of which files a task is likely to touch.

    Attributes:
        task_id: The task identifier.
        estimated_files: Set of file paths the task may modify.
        confidence: Confidence score 0-1 based on analysis quality.
        keywords: Keywords extracted from the task description.
    """
    task_id: str
    estimated_files: Set[str] = field(default_factory=set)
    confidence: float = 0.5
    keywords: Set[str] = field(default_factory=set)


@dataclass
class TaskGroup:
    """A group of tasks that can run in parallel.

    Tasks in the same group are expected to not have overlapping file
    modifications, so they can safely run concurrently.

    Attributes:
        group_id: Unique identifier for this group.
        tasks: List of tasks in this group.
        estimated_files: Union of all estimated files for tasks in group.
    """
    group_id: str
    tasks: List["Task"] = field(default_factory=list)
    estimated_files: Set[str] = field(default_factory=set)

    def add_task(self, task: "Task", analysis: TaskFileAnalysis) -> None:
        """Add a task to this group.

        Args:
            task: Task to add.
            analysis: File analysis for the task.
        """
        self.tasks.append(task)
        self.estimated_files.update(analysis.estimated_files)

    def has_overlap(self, analysis: TaskFileAnalysis) -> bool:
        """Check if a task's files overlap with this group.

        Args:
            analysis: File analysis to check.

        Returns:
            True if there's overlap, False otherwise.
        """
        return bool(self.estimated_files & analysis.estimated_files)


class TaskFileAnalyzer:
    """Estimates which files a task will modify based on description and codebase.

    The analyzer uses heuristics to identify likely file paths:
    - Explicit file paths mentioned in the task description
    - Module/component names that map to file patterns
    - Keywords that suggest certain file types
    """

    # Common file extensions by category
    EXTENSION_PATTERNS = {
        "python": {".py"},
        "javascript": {".js", ".jsx", ".ts", ".tsx"},
        "frontend": {".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html", ".vue"},
        "backend": {".py", ".go", ".rs", ".java"},
        "test": {"test_", "_test.py", ".test.js", ".spec.ts"},
        "config": {".yml", ".yaml", ".json", ".toml", ".ini"},
        "documentation": {".md", ".rst", ".txt"},
    }

    # Keywords that suggest file types/locations
    KEYWORD_FILE_HINTS = {
        "api": ["api/", "routes/", "endpoints/", "handlers/"],
        "database": ["models/", "db/", "migrations/", "schema"],
        "frontend": ["frontend/", "ui/", "components/", "pages/", "src/"],
        "backend": ["backend/", "server/", "api/", "services/"],
        "test": ["tests/", "test/", "__tests__/", "spec/"],
        "config": ["config/", ".ralph/", "settings/"],
        "cli": ["cli.py", "commands/", "__main__.py"],
        "auth": ["auth/", "authentication/", "security/"],
        "utils": ["utils/", "helpers/", "common/", "lib/"],
    }

    def __init__(self, repo_root: Path):
        """Initialize analyzer.

        Args:
            repo_root: Root path of the repository.
        """
        self.repo_root = repo_root
        self._file_cache: Optional[Set[str]] = None

    def _get_all_files(self) -> Set[str]:
        """Get all files in the repository (cached)."""
        if self._file_cache is None:
            self._file_cache = set()
            try:
                for path in self.repo_root.rglob("*"):
                    if path.is_file() and not any(
                        part.startswith(".") for part in path.parts
                    ):
                        rel_path = str(path.relative_to(self.repo_root))
                        # Skip common non-code directories
                        if not any(
                            skip in rel_path
                            for skip in ["node_modules/", "__pycache__/", ".git/", "venv/", ".venv/"]
                        ):
                            self._file_cache.add(rel_path)
            except Exception:
                pass
        return self._file_cache

    def _extract_explicit_paths(self, text: str) -> Set[str]:
        """Extract explicitly mentioned file paths from text.

        Args:
            text: Text to search for paths.

        Returns:
            Set of extracted file paths.
        """
        paths = set()

        # Match file paths with extensions
        # e.g., src/components/Button.tsx, tests/unit/test_api.py
        path_pattern = re.compile(
            r'\b([\w\-./]+\.(py|js|jsx|ts|tsx|css|scss|html|yml|yaml|json|md|rs|go))\b',
            re.IGNORECASE
        )
        for match in path_pattern.finditer(text):
            paths.add(match.group(1))

        # Match directory-style references
        # e.g., src/services/, ralph_orchestrator/
        dir_pattern = re.compile(r'\b([\w\-]+/[\w\-/]+)\b')
        for match in dir_pattern.finditer(text):
            potential_dir = match.group(1)
            # Check if it looks like a real path
            if "/" in potential_dir and not potential_dir.startswith("http"):
                paths.add(potential_dir)

        return paths

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract relevant keywords from task description.

        Args:
            text: Text to extract keywords from.

        Returns:
            Set of keywords.
        """
        keywords = set()
        text_lower = text.lower()

        for keyword in self.KEYWORD_FILE_HINTS.keys():
            if keyword in text_lower:
                keywords.add(keyword)

        # Look for component/module names (CamelCase or snake_case)
        camel_pattern = re.compile(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b')
        snake_pattern = re.compile(r'\b([a-z]+_[a-z_]+)\b')

        for match in camel_pattern.finditer(text):
            keywords.add(match.group(1).lower())
        for match in snake_pattern.finditer(text):
            keywords.add(match.group(1))

        return keywords

    def _match_keywords_to_files(self, keywords: Set[str]) -> Set[str]:
        """Match keywords to actual files in the repository.

        Args:
            keywords: Keywords to match.

        Returns:
            Set of matched file paths.
        """
        matched = set()
        all_files = self._get_all_files()

        for keyword in keywords:
            # Check for keyword in file paths
            for hint_patterns in self.KEYWORD_FILE_HINTS.get(keyword, []):
                for file_path in all_files:
                    if hint_patterns in file_path:
                        matched.add(file_path)

            # Also check if keyword appears in filename
            keyword_lower = keyword.lower().replace("_", "").replace("-", "")
            for file_path in all_files:
                filename = Path(file_path).stem.lower().replace("_", "").replace("-", "")
                if keyword_lower in filename or filename in keyword_lower:
                    matched.add(file_path)

        return matched

    def analyze(self, task: "Task") -> TaskFileAnalysis:
        """Analyze a task to estimate which files it will modify.

        Args:
            task: Task to analyze.

        Returns:
            TaskFileAnalysis with estimated files.
        """
        # Combine title, description, and acceptance criteria
        text = f"{task.title}\n{task.description}"
        text += "\n".join(task.acceptance_criteria)

        # Extract explicit paths
        explicit_paths = self._extract_explicit_paths(text)

        # Extract keywords
        keywords = self._extract_keywords(text)

        # Match keywords to files
        keyword_files = self._match_keywords_to_files(keywords)

        # Combine all estimated files
        estimated_files = explicit_paths | keyword_files

        # Calculate confidence based on how much we found
        confidence = 0.3  # Base confidence
        if explicit_paths:
            confidence += 0.4  # Explicit paths are high confidence
        if keyword_files:
            confidence += 0.2  # Keyword matches add confidence
        if len(estimated_files) > 10:
            confidence -= 0.1  # Many files = less precise

        confidence = max(0.1, min(1.0, confidence))

        return TaskFileAnalysis(
            task_id=task.id,
            estimated_files=estimated_files,
            confidence=confidence,
            keywords=keywords,
        )


class TaskPartitioner:
    """Partitions tasks into non-overlapping groups for parallel execution.

    Uses a greedy algorithm to assign tasks to groups:
    1. Sort tasks by estimated file count (larger first for better packing)
    2. For each task, try to add to an existing group with no overlap
    3. If no suitable group, create a new group
    """

    def __init__(self, max_groups: int = 10):
        """Initialize partitioner.

        Args:
            max_groups: Maximum number of parallel groups to create.
        """
        self.max_groups = max_groups

    def partition(
        self,
        tasks: List["Task"],
        repo_root: Path,
        min_confidence: float = 0.3,
    ) -> List[TaskGroup]:
        """Partition tasks into non-overlapping groups.

        Args:
            tasks: List of tasks to partition.
            repo_root: Repository root for file analysis.
            min_confidence: Minimum confidence to use analysis (below this,
                           tasks run sequentially).

        Returns:
            List of TaskGroup objects.
        """
        if not tasks:
            return []

        analyzer = TaskFileAnalyzer(repo_root)

        # Analyze all tasks
        analyses: Dict[str, TaskFileAnalysis] = {}
        for task in tasks:
            analyses[task.id] = analyzer.analyze(task)

        # Check if confidence is too low for parallel execution
        avg_confidence = sum(a.confidence for a in analyses.values()) / len(analyses)
        if avg_confidence < min_confidence:
            # Fall back to sequential: one task per group
            return [
                TaskGroup(
                    group_id=f"group-{i+1}",
                    tasks=[task],
                    estimated_files=analyses[task.id].estimated_files,
                )
                for i, task in enumerate(tasks)
            ]

        # Sort tasks by number of estimated files (descending)
        # This helps with bin packing - put larger tasks first
        sorted_tasks = sorted(
            tasks,
            key=lambda t: len(analyses[t.id].estimated_files),
            reverse=True,
        )

        groups: List[TaskGroup] = []

        for task in sorted_tasks:
            analysis = analyses[task.id]

            # Try to find an existing group with no overlap
            placed = False
            for group in groups:
                if not group.has_overlap(analysis):
                    group.add_task(task, analysis)
                    placed = True
                    break

            if not placed:
                # Create new group if under max
                if len(groups) < self.max_groups:
                    new_group = TaskGroup(
                        group_id=f"group-{len(groups)+1}",
                        tasks=[task],
                        estimated_files=analysis.estimated_files.copy(),
                    )
                    groups.append(new_group)
                else:
                    # Add to smallest group if at max
                    smallest = min(groups, key=lambda g: len(g.tasks))
                    smallest.add_task(task, analysis)

        return groups

    def get_partition_summary(self, groups: List[TaskGroup]) -> str:
        """Get a human-readable summary of the partition.

        Args:
            groups: List of task groups.

        Returns:
            Summary string.
        """
        lines = [f"Partitioned into {len(groups)} groups:"]
        for group in groups:
            task_ids = ", ".join(t.id for t in group.tasks)
            lines.append(f"  {group.group_id}: [{task_ids}] ({len(group.estimated_files)} files)")
        return "\n".join(lines)
