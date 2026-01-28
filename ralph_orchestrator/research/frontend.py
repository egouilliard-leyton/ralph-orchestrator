"""Frontend researcher for Ralph orchestrator.

Scans React/Vue/CSS code to understand frontend structure and patterns.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Optional

from .models import FileInfo, ResearchResult, ResearchOptions


class FrontendResearcher:
    """Researches frontend codebase structure.

    Scans TSX/JSX/Vue files, components, and styles to understand
    the frontend architecture for informed PRD generation.
    """

    def __init__(
        self,
        repo_root: Path,
        options: ResearchOptions,
    ):
        """Initialize frontend researcher.

        Args:
            repo_root: Root directory of the repository.
            options: Research configuration options.
        """
        self.repo_root = repo_root
        self.options = options

    def research(self, analysis_context: Optional[str] = None) -> ResearchResult:
        """Perform frontend research.

        Args:
            analysis_context: Optional context from report analysis.

        Returns:
            ResearchResult with frontend findings.
        """
        start_time = time.time()

        if not self.options.frontend_enabled:
            return ResearchResult(
                researcher_type="frontend",
                success=True,
                summary="Frontend research skipped (disabled)",
            )

        try:
            files = self._scan_files()
            categorized = self._categorize_files(files)
            summary = self._generate_summary(categorized)
            recommendations = self._generate_recommendations(categorized, analysis_context)

            duration_ms = int((time.time() - start_time) * 1000)

            return ResearchResult(
                researcher_type="frontend",
                success=True,
                files=categorized,
                summary=summary,
                recommendations=recommendations,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return ResearchResult(
                researcher_type="frontend",
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _scan_files(self) -> List[Path]:
        """Scan for frontend files using configured patterns.

        Returns:
            List of matching file paths.
        """
        all_files: List[Path] = []

        for pattern in self.options.frontend_patterns:
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
                rel_path = str(f.relative_to(self.repo_root))
                if not any(
                    skip in rel_path
                    for skip in [
                        "node_modules",
                        ".git",
                        "dist",
                        "build",
                        ".next",
                        "__pycache__",
                    ]
                ):
                    unique_files.append(f)

        return unique_files

    def _categorize_files(self, files: List[Path]) -> List[FileInfo]:
        """Categorize files by their role in the frontend.

        Args:
            files: List of file paths to categorize.

        Returns:
            List of FileInfo with categories assigned.
        """
        categorized = []

        for file_path in files:
            rel_path = str(file_path.relative_to(self.repo_root))
            category = self._determine_category(rel_path, file_path.suffix)
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

        return sorted(categorized, key=lambda f: (f.category, f.path))

    def _determine_category(self, rel_path: str, suffix: str) -> str:
        """Determine the category of a frontend file.

        Args:
            rel_path: Relative file path.
            suffix: File extension.

        Returns:
            Category string.
        """
        path_lower = rel_path.lower()

        if "component" in path_lower:
            return "component"
        elif "page" in path_lower or "view" in path_lower:
            return "page"
        elif "hook" in path_lower or path_lower.startswith("use"):
            return "hook"
        elif "context" in path_lower or "provider" in path_lower:
            return "context"
        elif "store" in path_lower or "redux" in path_lower or "zustand" in path_lower:
            return "state"
        elif "util" in path_lower or "helper" in path_lower or "lib" in path_lower:
            return "utility"
        elif "style" in path_lower or suffix in [".css", ".scss", ".less"]:
            return "style"
        elif "test" in path_lower or "spec" in path_lower:
            return "test"
        elif "type" in path_lower and suffix == ".ts":
            return "types"
        elif "api" in path_lower or "service" in path_lower or "fetch" in path_lower:
            return "api"
        else:
            return "other"

    def _get_file_summary(self, file_path: Path) -> str:
        """Get a brief summary of what a file does.

        Args:
            file_path: Path to the file.

        Returns:
            Summary string.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            # Look for JSDoc comment at top
            jsdoc_match = re.search(r"/\*\*\s*(.*?)\s*\*/", content[:500], re.DOTALL)
            if jsdoc_match:
                comment = jsdoc_match.group(1).strip()
                # Clean up the comment
                comment = re.sub(r"\s*\*\s*", " ", comment)
                comment = re.sub(r"@\w+.*", "", comment).strip()
                if comment:
                    return comment[:200]

            # Look for default export to guess purpose
            if "export default" in content:
                match = re.search(
                    r"export default (?:function|class|const)?\s*(\w+)",
                    content,
                )
                if match:
                    return f"Exports {match.group(1)}"

            return f"Frontend file: {file_path.stem}"

        except Exception:
            return f"Frontend file: {file_path.stem}"

    def _extract_exports(self, file_path: Path) -> List[str]:
        """Extract key exports from a frontend file.

        Args:
            file_path: Path to the file.

        Returns:
            List of exported names.
        """
        exports = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            # Find named exports
            named_exports = re.findall(
                r"export (?:const|function|class|interface|type)\s+(\w+)",
                content,
            )
            exports.extend(named_exports)

            # Find default export
            default_match = re.search(
                r"export default (?:function|class|const)?\s*(\w+)?",
                content,
            )
            if default_match and default_match.group(1):
                exports.append(f"default: {default_match.group(1)}")

        except Exception:
            pass

        return exports[:10]

    def _generate_summary(self, files: List[FileInfo]) -> str:
        """Generate a summary of the frontend structure.

        Args:
            files: Categorized file list.

        Returns:
            Summary string.
        """
        counts = {}
        for f in files:
            counts[f.category] = counts.get(f.category, 0) + 1

        parts = []
        if counts:
            parts.append(f"Found {len(files)} frontend files:")
            for cat, count in sorted(counts.items()):
                parts.append(f"  - {cat}: {count} files")

        return "\n".join(parts) if parts else "No frontend files found."

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

        categories = {}
        for f in files:
            categories[f.category] = categories.get(f.category, 0) + 1

        if categories.get("component", 0) > 0:
            recommendations.append(
                f"Frontend has {categories['component']} components - follow existing patterns"
            )

        if categories.get("hook", 0) > 0:
            recommendations.append(
                "Custom hooks exist - consider creating hooks for shared logic"
            )

        if categories.get("context", 0) > 0:
            recommendations.append(
                "Context providers exist - use for cross-component state"
            )

        if categories.get("test", 0) > 0:
            recommendations.append(
                f"Frontend has {categories['test']} test files - maintain test coverage"
            )

        if categories.get("style", 0) > 5:
            recommendations.append(
                "Multiple style files - follow existing CSS conventions"
            )

        return recommendations
