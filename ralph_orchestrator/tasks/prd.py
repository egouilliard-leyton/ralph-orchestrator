"""PRD (Product Requirements Document) task loader and updater.

Loads and validates .ralph/prd.json against schemas/prd.schema.json.
Provides task sorting by priority and supports --task and --from-task filtering.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ralph_orchestrator.config import validate_against_schema


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Subtask:
    """A subtask within a parent task."""
    id: str
    title: str
    acceptance_criteria: List[str]
    passes: bool = False
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "acceptanceCriteria": self.acceptance_criteria,
            "passes": self.passes,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subtask":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            acceptance_criteria=data.get("acceptanceCriteria", []),
            passes=data.get("passes", False),
            notes=data.get("notes", ""),
        )


@dataclass
class Task:
    """A single executable task."""
    id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    priority: int
    passes: bool = False
    notes: str = ""
    requires_tests: bool = True
    affects_frontend: bool = False
    subtasks: List[Subtask] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptanceCriteria": self.acceptance_criteria,
            "priority": self.priority,
            "passes": self.passes,
            "notes": self.notes,
            "requiresTests": self.requires_tests,
            "affectsFrontend": self.affects_frontend,
        }
        if self.subtasks:
            result["subtasks"] = [s.to_dict() for s in self.subtasks]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary."""
        subtasks = [Subtask.from_dict(s) for s in data.get("subtasks", [])]
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            acceptance_criteria=data.get("acceptanceCriteria", []),
            priority=data.get("priority", 999),
            passes=data.get("passes", False),
            notes=data.get("notes", ""),
            requires_tests=data.get("requiresTests", True),
            affects_frontend=data.get("affectsFrontend", False),
            subtasks=subtasks,
        )
    
    @property
    def is_complete(self) -> bool:
        """Check if task is complete (passes is True)."""
        return self.passes


@dataclass
class PRDMetadata:
    """Optional metadata for tracking and provenance."""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: Optional[str] = None  # manual, autopilot, imported-cr, imported-prd
    source_file: Optional[str] = None
    author: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {}
        if self.created_at:
            result["createdAt"] = self.created_at
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        if self.source:
            result["source"] = self.source
        if self.source_file:
            result["sourceFile"] = self.source_file
        if self.author:
            result["author"] = self.author
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PRDMetadata":
        """Create from dictionary."""
        return cls(
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            source=data.get("source"),
            source_file=data.get("sourceFile"),
            author=data.get("author"),
        )


@dataclass
class PRDData:
    """Full PRD data structure."""
    project: str
    description: str
    tasks: List[Task]
    branch_name: Optional[str] = None
    version: str = "1"
    metadata: Optional[PRDMetadata] = None
    schema_ref: Optional[str] = None
    _path: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "project": self.project,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
        }
        if self.schema_ref:
            result["$schema"] = self.schema_ref
        if self.branch_name:
            result["branchName"] = self.branch_name
        if self.version:
            result["version"] = self.version
        if self.metadata:
            meta_dict = self.metadata.to_dict()
            if meta_dict:
                result["metadata"] = meta_dict
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: Optional[Path] = None) -> "PRDData":
        """Create from dictionary."""
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        metadata = None
        if "metadata" in data:
            metadata = PRDMetadata.from_dict(data["metadata"])
        
        return cls(
            project=data["project"],
            description=data["description"],
            tasks=tasks,
            branch_name=data.get("branchName"),
            version=data.get("version", "1"),
            metadata=metadata,
            schema_ref=data.get("$schema"),
            _path=path,
        )
    
    @property
    def path(self) -> Optional[Path]:
        """Get the path this PRD was loaded from."""
        return self._path
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending (not passed) tasks, sorted by priority."""
        pending = [t for t in self.tasks if not t.passes]
        return sorted(pending, key=lambda t: (t.priority, t.id))
    
    def get_completed_tasks(self) -> List[Task]:
        """Get all completed (passed) tasks."""
        return [t for t in self.tasks if t.passes]
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Find a task by its ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


def load_prd(path: Path) -> PRDData:
    """Load and validate a PRD JSON file.
    
    Args:
        path: Path to the prd.json file.
        
    Returns:
        PRDData instance with parsed tasks.
        
    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file is invalid JSON or fails schema validation.
    """
    if not path.exists():
        raise FileNotFoundError(f"PRD file not found: {path}")
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")
    
    # Validate against schema
    valid, errors = validate_against_schema(data, "prd.schema.json")
    if not valid:
        raise ValueError(
            f"Invalid PRD file {path}:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )
    
    return PRDData.from_dict(data, path=path)


def save_prd(prd: PRDData, path: Optional[Path] = None) -> Path:
    """Save PRD data to a JSON file.
    
    Args:
        prd: PRDData instance to save.
        path: Path to save to. Defaults to prd._path if available.
        
    Returns:
        Path the file was saved to.
        
    Raises:
        ValueError: If no path specified and prd has no path.
    """
    if path is None:
        path = prd._path
    if path is None:
        raise ValueError("No path specified and PRD has no path set")
    
    # Update metadata timestamp
    if prd.metadata is None:
        prd.metadata = PRDMetadata()
    prd.metadata.updated_at = utc_now_iso()
    
    # Convert to dict and serialize
    data = prd.to_dict()
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write with proper formatting
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(content, encoding="utf-8")
    
    # Update internal path reference
    prd._path = path
    
    return path


def get_pending_tasks(
    prd: PRDData,
    task_id: Optional[str] = None,
    from_task_id: Optional[str] = None,
) -> List[Task]:
    """Get pending tasks with optional filtering.
    
    Args:
        prd: PRDData instance.
        task_id: If specified, return only this task (if pending).
        from_task_id: If specified, return tasks starting from this ID.
        
    Returns:
        List of pending tasks sorted by priority.
        
    Raises:
        ValueError: If specified task_id or from_task_id not found.
    """
    pending = prd.get_pending_tasks()
    
    # Filter to specific task
    if task_id:
        task = prd.get_task_by_id(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.passes:
            return []  # Task already complete
        return [task]
    
    # Filter from specific task
    if from_task_id:
        task = prd.get_task_by_id(from_task_id)
        if task is None:
            raise ValueError(f"Task {from_task_id} not found")
        
        # Find position in sorted pending list
        found = False
        result = []
        for t in pending:
            if t.id == from_task_id:
                found = True
            if found:
                result.append(t)
        
        if not found and not task.passes:
            # Task is pending but not in list? Shouldn't happen
            raise ValueError(f"Task {from_task_id} not found in pending tasks")
        
        return result
    
    return pending


def get_task_by_id(prd: PRDData, task_id: str) -> Optional[Task]:
    """Get a task by its ID."""
    return prd.get_task_by_id(task_id)


def mark_task_complete(
    prd: PRDData,
    task_id: str,
    notes: Optional[str] = None,
    save: bool = True,
) -> Task:
    """Mark a task as complete.
    
    Args:
        prd: PRDData instance.
        task_id: ID of task to mark complete.
        notes: Optional notes to add to the task.
        save: Whether to save the PRD after updating.
        
    Returns:
        The updated Task.
        
    Raises:
        ValueError: If task not found.
    """
    task = prd.get_task_by_id(task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")
    
    task.passes = True
    if notes:
        if task.notes:
            task.notes += f"\n{notes}"
        else:
            task.notes = notes
    
    if save and prd._path:
        save_prd(prd)
    
    return task


def update_task_notes(
    prd: PRDData,
    task_id: str,
    notes: str,
    append: bool = True,
    save: bool = True,
) -> Task:
    """Update notes for a task.
    
    Args:
        prd: PRDData instance.
        task_id: ID of task to update.
        notes: Notes to add/set.
        append: If True, append to existing notes. If False, replace.
        save: Whether to save the PRD after updating.
        
    Returns:
        The updated Task.
        
    Raises:
        ValueError: If task not found.
    """
    task = prd.get_task_by_id(task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")
    
    if append and task.notes:
        task.notes += f"\n{notes}"
    else:
        task.notes = notes
    
    if save and prd._path:
        save_prd(prd)
    
    return task


def validate_task_id(task_id: str) -> bool:
    """Validate task ID format (T-NNN)."""
    return bool(re.match(r"^T-[0-9]{3}$", task_id))


def generate_next_task_id(prd: PRDData) -> str:
    """Generate the next available task ID."""
    max_num = 0
    for task in prd.tasks:
        match = re.match(r"^T-([0-9]{3})$", task.id)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return f"T-{max_num + 1:03d}"


def create_task(
    prd: PRDData,
    title: str,
    description: str,
    acceptance_criteria: List[str],
    priority: Optional[int] = None,
    task_id: Optional[str] = None,
    requires_tests: bool = True,
    affects_frontend: bool = False,
    save: bool = True,
) -> Task:
    """Create a new task and add it to the PRD.
    
    Args:
        prd: PRDData instance.
        title: Task title.
        description: Task description.
        acceptance_criteria: List of acceptance criteria.
        priority: Task priority. Defaults to max+1.
        task_id: Task ID. Defaults to auto-generated.
        requires_tests: Whether task requires automated tests. Defaults to True.
        affects_frontend: Whether task modifies frontend code. Defaults to False.
        save: Whether to save the PRD after adding.
        
    Returns:
        The created Task.
    """
    if task_id is None:
        task_id = generate_next_task_id(prd)
    
    if priority is None:
        max_priority = max((t.priority for t in prd.tasks), default=0)
        priority = max_priority + 1
    
    task = Task(
        id=task_id,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        priority=priority,
        passes=False,
        notes="",
        requires_tests=requires_tests,
        affects_frontend=affects_frontend,
    )
    
    prd.tasks.append(task)
    
    if save and prd._path:
        save_prd(prd)
    
    return task
