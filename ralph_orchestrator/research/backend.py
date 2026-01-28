"""Backend researcher for Ralph orchestrator.

Scans Python/API code to understand backend structure and patterns.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from .models import FileInfo, ResearchResult, ResearchOptions


class BackendResearcher:
    """Researches backend codebase structure.

    Scans Python files, models, routes, and services to understand
    the backend architecture for informed PRD generation.
    """

    def __init__(
        self,
        repo_root: Path,
        options: ResearchOptions,
    ):
        """Initialize backend researcher.

        Args:
            repo_root: Root directory of the repository.
            options: Research configuration options.
        """
        self.repo_root = repo_root
        self.options = options

    def research(self, analysis_context: Optional[str] = None) -> ResearchResult:
        """Perform backend research.

        Args:
            analysis_context: Optional context from report analysis.

        Returns:
            ResearchResult with backend findings.
        """
        start_time = time.time()

        if not self.options.backend_enabled:
            return ResearchResult(
                researcher_type="backend",
                success=True,
                summary="Backend research skipped (disabled)",
            )

        try:
            files = self._scan_files()
            categorized = self._categorize_files(files)
            summary = self._generate_summary(categorized)
            recommendations = self._generate_recommendations(categorized, analysis_context)

            duration_ms = int((time.time() - start_time) * 1000)

            return ResearchResult(
                researcher_type="backend",
                success=True,
                files=categorized,
                summary=summary,
                recommendations=recommendations,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return ResearchResult(
                researcher_type="backend",
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _scan_files(self) -> List[Path]:
        """Scan for backend files using configured patterns.

        Returns:
            List of matching file paths.
        """
        all_files: List[Path] = []

        for pattern in self.options.backend_patterns:
            # Convert pattern to glob
            try:
                matches = list(self.repo_root.glob(pattern))
                all_files.extend(matches)
            except Exception:
                continue

        # Deduplicate and filter
        seen = set()
        unique_files = []
        for f in all_files:
            if f.is_file() and str(f) not in seen:
                seen.add(str(f))
                # Skip common non-code directories
                rel_path = str(f.relative_to(self.repo_root))
                if not any(
                    skip in rel_path
                    for skip in [
                        "__pycache__",
                        ".git",
                        "node_modules",
                        ".venv",
                        "venv",
                        ".pytest_cache",
                        ".mypy_cache",
                    ]
                ):
                    unique_files.append(f)

        return unique_files

    def _categorize_files(self, files: List[Path]) -> List[FileInfo]:
        """Categorize files by their role in the backend.

        Args:
            files: List of file paths to categorize.

        Returns:
            List of FileInfo with categories assigned.
        """
        categorized = []

        for file_path in files:
            rel_path = str(file_path.relative_to(self.repo_root))
            category = self._determine_category(rel_path)
            summary = self._get_file_summary(file_path)
            exports = self._extract_exports(file_path)

            categorized.append(
                FileInfo(
                    path=rel_path,
                    category=category,
                    summary=summary,
                    key_exports=exports,
                )
            )

        # Sort by category for readability
        return sorted(categorized, key=lambda f: (f.category, f.path))

    def _determine_category(self, rel_path: str) -> str:
        """Determine the category of a backend file.

        Args:
            rel_path: Relative file path.

        Returns:
            Category string.
        """
        path_lower = rel_path.lower()

        if "model" in path_lower:
            return "model"
        elif "route" in path_lower or "endpoint" in path_lower or "api" in path_lower:
            return "route"
        elif "service" in path_lower:
            return "service"
        elif "util" in path_lower or "helper" in path_lower:
            return "utility"
        elif "config" in path_lower or "setting" in path_lower:
            return "config"
        elif "test" in path_lower:
            return "test"
        elif "migration" in path_lower:
            return "migration"
        else:
            return "other"

    def _get_file_summary(self, file_path: Path) -> str:
        """Get a brief summary of what a file does.

        Args:
            file_path: Path to the file.

        Returns:
            Summary string (extracted from docstring or generated).
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            # Look for module docstring
            in_docstring = False
            docstring_lines = []

            for line in lines[:30]:  # Only check first 30 lines
                stripped = line.strip()

                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if in_docstring:
                        # End of docstring
                        break
                    else:
                        # Start of docstring
                        in_docstring = True
                        if len(stripped) > 3:
                            docstring_lines.append(stripped[3:])
                elif in_docstring:
                    if stripped.endswith('"""') or stripped.endswith("'''"):
                        docstring_lines.append(stripped[:-3])
                        break
                    docstring_lines.append(stripped)

            if docstring_lines:
                return " ".join(docstring_lines[:2])[:200]

            return f"Python module: {file_path.stem}"

        except Exception:
            return f"Python module: {file_path.stem}"

    def _extract_exports(self, file_path: Path) -> List[str]:
        """Extract key exports from a Python file.

        Args:
            file_path: Path to the file.

        Returns:
            List of class and function names.
        """
        exports = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            for line in content.split("\n"):
                stripped = line.strip()

                # Look for class definitions
                if stripped.startswith("class "):
                    class_name = stripped.split("(")[0].split(":")[0].replace("class ", "")
                    if not class_name.startswith("_"):
                        exports.append(f"class {class_name}")

                # Look for function definitions at module level
                elif stripped.startswith("def ") and not line.startswith(" "):
                    func_name = stripped.split("(")[0].replace("def ", "")
                    if not func_name.startswith("_"):
                        exports.append(f"def {func_name}")

        except Exception:
            pass

        return exports[:10]  # Limit to 10 exports

    def _generate_summary(self, files: List[FileInfo]) -> str:
        """Generate a summary of the backend structure.

        Args:
            files: Categorized file list.

        Returns:
            Summary string.
        """
        # Count by category
        counts = {}
        for f in files:
            counts[f.category] = counts.get(f.category, 0) + 1

        parts = []
        if counts:
            parts.append(f"Found {len(files)} backend files:")
            for cat, count in sorted(counts.items()):
                parts.append(f"  - {cat}: {count} files")

        return "\n".join(parts) if parts else "No backend files found."

    def _generate_recommendations(
        self, files: List[FileInfo], analysis_context: Optional[str]
    ) -> List[str]:
        """Generate recommendations for the PRD.

        Args:
            files: Categorized file list.
            analysis_context: Optional context from report analysis.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        # Count categories
        categories = {}
        for f in files:
            categories[f.category] = categories.get(f.category, 0) + 1

        # Generate recommendations based on structure
        if categories.get("model", 0) > 0:
            recommendations.append(
                f"Backend has {categories['model']} model files - consider data model impacts"
            )

        if categories.get("route", 0) > 0:
            recommendations.append(
                f"Backend has {categories['route']} API routes - ensure API compatibility"
            )

        if categories.get("service", 0) > 0:
            recommendations.append(
                "Service layer exists - implement changes through services when possible"
            )

        if categories.get("test", 0) > 0:
            recommendations.append(
                f"Backend has {categories['test']} test files - maintain test coverage"
            )

        return recommendations
