"""Test-writing agent file guardrails.

Enforces file restrictions for the test-writing agent:
- Only allows modifications to files matching test_paths patterns
- Tracks file changes using git diff
- Reverts unauthorized file modifications
"""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

from .timeline import TimelineLogger, EventType


@dataclass
class FileChange:
    """Represents a file change detected by git."""
    path: str
    change_type: str  # M (modified), A (added), D (deleted), ? (untracked)
    
    @property
    def is_new(self) -> bool:
        """Check if this is a new file."""
        return self.change_type in ("A", "?")
    
    @property
    def is_modified(self) -> bool:
        """Check if this is a modified existing file."""
        return self.change_type == "M"
    
    @property
    def is_deleted(self) -> bool:
        """Check if this is a deleted file."""
        return self.change_type == "D"


@dataclass
class GuardrailResult:
    """Result of guardrail check."""
    passed: bool
    allowed_changes: List[FileChange] = field(default_factory=list)
    violations: List[FileChange] = field(default_factory=list)
    reverted_files: List[str] = field(default_factory=list)
    error: Optional[str] = None


class FilePathGuardrail:
    """Guardrail that restricts file modifications to test paths.
    
    The test-writing agent is only allowed to modify files matching
    the configured test_paths patterns. Any other modifications are
    detected and reverted.
    """
    
    def __init__(
        self,
        test_paths: List[str],
        repo_root: Optional[Path] = None,
        timeline: Optional[TimelineLogger] = None,
    ):
        """Initialize guardrail.
        
        Args:
            test_paths: List of glob patterns for allowed test paths.
            repo_root: Repository root directory. Defaults to cwd.
            timeline: Timeline logger for events.
        """
        self.test_paths = test_paths
        self.repo_root = repo_root or Path.cwd()
        self.timeline = timeline
        
        # Normalize patterns
        self._patterns = self._normalize_patterns(test_paths)
    
    def _normalize_patterns(self, patterns: List[str]) -> List[str]:
        """Normalize glob patterns for matching.
        
        Converts patterns like "tests/**" to work with fnmatch.
        """
        normalized = []
        for pattern in patterns:
            # Remove leading ./ if present
            pattern = pattern.lstrip("./")
            normalized.append(pattern)
        return normalized
    
    def _is_markdown_in_test_dir(self, file_path: str) -> bool:
        """Check if a file is a markdown file inside a test directory.
        
        Markdown documentation files (.md) should not be created in test
        directories during test-writing. They should go to the designated
        report file under .ralph-session/reports/.
        
        Args:
            file_path: Relative path to check.
            
        Returns:
            True if this is a .md file inside a test directory.
        """
        # Normalize path
        file_path = file_path.lstrip("./")
        
        # Check if it's a markdown file
        if not file_path.lower().endswith(".md"):
            return False
        
        # Check if it's under any test directory pattern
        for pattern in self._patterns:
            # Extract the base directory from the pattern
            # e.g., "tests/**" -> "tests", "test/**/*.py" -> "test"
            if "**" in pattern:
                base_dir = pattern.partition("**")[0].rstrip("/")
            elif "/" in pattern:
                base_dir = pattern.split("/")[0]
            else:
                # Pattern like "*.py" - not a directory pattern
                continue
            
            # Check if the markdown file is under this test directory
            if base_dir and file_path.startswith(base_dir + "/"):
                return True
        
        return False
    
    def is_allowed(self, file_path: str) -> bool:
        """Check if a file path is allowed for test-writing agent.
        
        Args:
            file_path: Relative path to check.
            
        Returns:
            True if path matches test patterns.
        """
        # Normalize path
        file_path = file_path.lstrip("./")
        
        for pattern in self._patterns:
            # Handle ** recursive patterns
            if "**" in pattern:
                # Convert ** to work with fnmatch
                # tests/** -> tests/* and tests/*/*, etc.
                base, _, suffix = pattern.partition("**")
                
                # Check if file is under the base directory
                if file_path.startswith(base.rstrip("/")):
                    # Check any suffix pattern
                    if suffix:
                        remainder = file_path[len(base.rstrip("/")):]
                        remainder = remainder.lstrip("/")
                        suffix_pattern = suffix.lstrip("/")
                        if fnmatch.fnmatch(remainder, suffix_pattern) or fnmatch.fnmatch(file_path, f"{base}*{suffix}"):
                            return True
                    else:
                        return True
            
            # Standard glob match
            if fnmatch.fnmatch(file_path, pattern):
                return True
            
            # Also match if pattern is a directory prefix
            if pattern.endswith("/**"):
                dir_prefix = pattern[:-3]
                if file_path.startswith(dir_prefix + "/") or file_path.startswith(dir_prefix):
                    return True
        
        return False

    def _is_internal_artifact(self, file_path: str) -> bool:
        """Check if a path is an internal Ralph artifact we should ignore.

        The guardrail is meant to restrict what the *test-writing agent* can
        change in the repo. The orchestrator itself creates run artifacts under
        `.ralph-session/` (logs, timeline, etc.) and `.ralph/` (outputs). Those
        should never be treated as agent violations.
        """
        # Normalize path - only strip leading "./" but keep the dot for hidden dirs
        p = file_path
        if p.startswith("./"):
            p = p[2:]
        
        return (
            p.startswith(".ralph-session/")
            or p.startswith(".ralph-session")  # Also match exact dir name
            or p.startswith(".ralph/")
            or p.startswith(".ralph")  # Also match exact dir name
            or p.startswith(".git/")
            or p.startswith(".git")  # Also match exact dir name
        )
    
    def get_file_changes(self) -> Tuple[List[FileChange], List[FileChange]]:
        """Get current file changes from git.
        
        Returns:
            Tuple of (staged_changes, unstaged_changes).
        """
        staged = []
        unstaged = []
        
        try:
            # Get staged changes
            result = subprocess.run(
                ["git", "diff", "--name-status", "--cached"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split("\t", 1)
                        if len(parts) == 2:
                            staged.append(FileChange(
                                path=parts[1],
                                change_type=parts[0][0],
                            ))
            
            # Get unstaged changes (modified tracked files)
            result = subprocess.run(
                ["git", "diff", "--name-status"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split("\t", 1)
                        if len(parts) == 2:
                            unstaged.append(FileChange(
                                path=parts[1],
                                change_type=parts[0][0],
                            ))
            
            # Get untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        unstaged.append(FileChange(
                            path=line,
                            change_type="?",
                        ))
        
        except Exception as e:
            # Log error but continue
            if self.timeline:
                self.timeline.log(
                    EventType.AGENT_FAILED,
                    error=f"Failed to get git changes: {e}",
                    role="guardrail",
                )
        
        return staged, unstaged
    
    def snapshot_state(self) -> Set[str]:
        """Take snapshot of current changed files.
        
        Returns:
            Set of file paths that are currently modified.
        """
        staged, unstaged = self.get_file_changes()
        return {c.path for c in staged + unstaged}
    
    def check_and_revert(
        self,
        before_snapshot: Set[str],
        task_id: Optional[str] = None,
    ) -> GuardrailResult:
        """Check for violations and revert unauthorized changes.
        
        Args:
            before_snapshot: Set of file paths from before agent ran.
            task_id: Task ID for logging.
            
        Returns:
            GuardrailResult with violation details.
        """
        # Get current changes
        staged, unstaged = self.get_file_changes()
        all_changes = staged + unstaged
        
        # Find new changes (not in before snapshot)
        new_changes = [c for c in all_changes if c.path not in before_snapshot]
        
        # Classify changes
        allowed_changes = []
        violations = []
        
        for change in new_changes:
            if self._is_internal_artifact(change.path):
                allowed_changes.append(change)
            elif self._is_markdown_in_test_dir(change.path):
                # Markdown files in test directories are never allowed
                # They should go to .ralph-session/reports/ instead
                violations.append(change)
            elif self.is_allowed(change.path):
                allowed_changes.append(change)
            else:
                violations.append(change)
        
        # Revert violations
        reverted_files = []
        for violation in violations:
            reverted = self._revert_file(violation)
            if reverted:
                reverted_files.append(violation.path)
        
        # Log violations
        if violations and self.timeline:
            self.timeline.log(
                EventType.AGENT_FAILED,
                task_id=task_id,
                role="guardrail",
                error=f"Guardrail violation: {len(violations)} unauthorized file changes",
                details={
                    "violations": [v.path for v in violations],
                    "reverted": reverted_files,
                },
            )
        
        return GuardrailResult(
            passed=len(violations) == 0,
            allowed_changes=allowed_changes,
            violations=violations,
            reverted_files=reverted_files,
        )
    
    def _revert_file(self, change: FileChange) -> bool:
        """Revert a single file change.
        
        Args:
            change: File change to revert.
            
        Returns:
            True if successfully reverted.
        """
        file_path = self.repo_root / change.path
        
        try:
            if change.is_new:
                # Delete new/untracked file
                if file_path.exists():
                    file_path.unlink()
                    return True
            else:
                # Restore tracked file from git
                result = subprocess.run(
                    ["git", "checkout", "--", change.path],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return result.returncode == 0
        
        except Exception:
            return False
        
        return False


def create_guardrail(
    test_paths: List[str],
    repo_root: Optional[Path] = None,
    timeline: Optional[TimelineLogger] = None,
) -> FilePathGuardrail:
    """Create a test path guardrail.
    
    Args:
        test_paths: List of glob patterns for allowed test paths.
        repo_root: Repository root directory.
        timeline: Timeline logger for events.
        
    Returns:
        Configured FilePathGuardrail instance.
    """
    return FilePathGuardrail(
        test_paths=test_paths,
        repo_root=repo_root,
        timeline=timeline,
    )
