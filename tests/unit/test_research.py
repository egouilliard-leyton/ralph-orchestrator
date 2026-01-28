"""Unit tests for research module."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from ralph_orchestrator.research import (
    ResearchOptions,
    ResearchResult,
    ResearchContext,
    BackendResearcher,
    FrontendResearcher,
    ResearchCoordinator,
)
from ralph_orchestrator.research.models import FileInfo, WebSearchResult


class TestResearchOptions:
    """Tests for ResearchOptions dataclass."""

    def test_defaults(self):
        """Default options should be reasonable."""
        opts = ResearchOptions()
        assert opts.enabled
        assert opts.backend_enabled
        assert opts.frontend_enabled
        assert opts.web_enabled
        assert opts.max_web_queries == 5

    def test_disabled(self):
        """Can disable all research."""
        opts = ResearchOptions(enabled=False)
        assert not opts.enabled

    def test_selective_disable(self):
        """Can disable individual researchers."""
        opts = ResearchOptions(
            backend_enabled=False,
            frontend_enabled=True,
            web_enabled=False,
        )
        assert not opts.backend_enabled
        assert opts.frontend_enabled
        assert not opts.web_enabled

    def test_custom_patterns(self):
        """Can provide custom file patterns."""
        opts = ResearchOptions(
            backend_patterns=["**/*.go"],
            frontend_patterns=["**/*.svelte"],
        )
        assert "**/*.go" in opts.backend_patterns
        assert "**/*.svelte" in opts.frontend_patterns


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_creation(self):
        """Should create with required fields."""
        info = FileInfo(
            path="src/models/user.py",
            category="model",
            summary="User model",
        )
        assert info.path == "src/models/user.py"
        assert info.category == "model"
        assert info.summary == "User model"

    def test_key_exports(self):
        """Should store key exports."""
        info = FileInfo(
            path="test.py",
            key_exports=["class User", "def get_user"],
        )
        assert len(info.key_exports) == 2


class TestResearchResult:
    """Tests for ResearchResult dataclass."""

    def test_success_result(self):
        """Should track successful research."""
        result = ResearchResult(
            researcher_type="backend",
            success=True,
            files=[FileInfo(path="test.py")],
            summary="Found files",
        )
        assert result.success
        assert len(result.files) == 1
        assert result.error is None

    def test_failure_result(self):
        """Should track failed research."""
        result = ResearchResult(
            researcher_type="frontend",
            success=False,
            error="Permission denied",
        )
        assert not result.success
        assert result.error == "Permission denied"


class TestResearchContext:
    """Tests for ResearchContext dataclass."""

    def test_to_prd_context_empty(self):
        """Empty context should still produce valid dict."""
        ctx = ResearchContext()
        result = ctx.to_prd_context()
        assert result["has_research"]
        assert "research_timestamp" in result

    def test_to_prd_context_with_backend(self):
        """Should include backend results."""
        ctx = ResearchContext(
            backend_result=ResearchResult(
                researcher_type="backend",
                success=True,
                files=[FileInfo(path="test.py", category="model")],
                summary="Found models",
                recommendations=["Check models"],
            )
        )
        result = ctx.to_prd_context()
        assert "backend" in result
        assert len(result["backend"]["files"]) == 1
        assert result["backend"]["summary"] == "Found models"

    def test_to_prd_context_with_all(self):
        """Should include all researcher results."""
        ctx = ResearchContext(
            backend_result=ResearchResult(
                researcher_type="backend",
                success=True,
                summary="Backend found",
            ),
            frontend_result=ResearchResult(
                researcher_type="frontend",
                success=True,
                summary="Frontend found",
            ),
            web_result=ResearchResult(
                researcher_type="web",
                success=True,
                summary="Web found",
                web_results=[
                    WebSearchResult(
                        query="test",
                        title="Test result",
                        snippet="Found something",
                    )
                ],
            ),
        )
        result = ctx.to_prd_context()
        assert "backend" in result
        assert "frontend" in result
        assert "web" in result

    def test_to_prompt_section(self):
        """Should generate formatted prompt section."""
        ctx = ResearchContext(
            backend_result=ResearchResult(
                researcher_type="backend",
                success=True,
                summary="Found 5 models",
                recommendations=["Check user model", "Review routes"],
            )
        )
        section = ctx.to_prompt_section()
        assert "Backend Research Findings" in section
        assert "Found 5 models" in section
        assert "Check user model" in section


class TestBackendResearcher:
    """Tests for BackendResearcher."""

    def test_disabled_research(self):
        """Should skip when disabled."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions(backend_enabled=False)
            researcher = BackendResearcher(Path(tmpdir), opts)
            result = researcher.research()
            assert result.success
            assert "skipped" in result.summary.lower()

    def test_empty_directory(self):
        """Should handle empty directories."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions()
            researcher = BackendResearcher(Path(tmpdir), opts)
            result = researcher.research()
            assert result.success
            assert len(result.files) == 0

    def test_finds_python_files(self):
        """Should find Python files."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create a Python file
            (tmppath / "test.py").write_text("# Test file\nclass TestClass:\n    pass\n")

            opts = ResearchOptions(backend_patterns=["*.py"])
            researcher = BackendResearcher(tmppath, opts)
            result = researcher.research()

            assert result.success
            assert len(result.files) >= 1
            assert any(f.path == "test.py" for f in result.files)

    def test_categorizes_files(self):
        """Should categorize files by type."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            models = tmppath / "models"
            models.mkdir()
            (models / "user.py").write_text("class User:\n    pass\n")

            opts = ResearchOptions(backend_patterns=["**/*.py"])
            researcher = BackendResearcher(tmppath, opts)
            result = researcher.research()

            # Should find the file
            assert result.success
            model_files = [f for f in result.files if f.category == "model"]
            assert len(model_files) >= 1

    def test_extracts_docstring(self):
        """Should extract module docstring as summary."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "module.py").write_text('"""This is the module summary."""\n\nclass Foo:\n    pass\n')

            opts = ResearchOptions(backend_patterns=["*.py"])
            researcher = BackendResearcher(tmppath, opts)
            result = researcher.research()

            assert result.success
            module_file = next((f for f in result.files if f.path == "module.py"), None)
            assert module_file is not None
            assert "module summary" in module_file.summary.lower()


class TestFrontendResearcher:
    """Tests for FrontendResearcher."""

    def test_disabled_research(self):
        """Should skip when disabled."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions(frontend_enabled=False)
            researcher = FrontendResearcher(Path(tmpdir), opts)
            result = researcher.research()
            assert result.success
            assert "skipped" in result.summary.lower()

    def test_finds_tsx_files(self):
        """Should find TSX files."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "Button.tsx").write_text("export const Button = () => <button>Click</button>;\n")

            opts = ResearchOptions(frontend_patterns=["*.tsx"])
            researcher = FrontendResearcher(tmppath, opts)
            result = researcher.research()

            assert result.success
            assert len(result.files) >= 1
            assert any("Button" in f.path for f in result.files)

    def test_categorizes_components(self):
        """Should categorize component files."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            components = tmppath / "components"
            components.mkdir()
            (components / "Header.tsx").write_text("export default function Header() {}\n")

            opts = ResearchOptions(frontend_patterns=["**/*.tsx"])
            researcher = FrontendResearcher(tmppath, opts)
            result = researcher.research()

            assert result.success
            component_files = [f for f in result.files if f.category == "component"]
            assert len(component_files) >= 1


class TestResearchCoordinator:
    """Tests for ResearchCoordinator."""

    def test_disabled_research(self):
        """Should skip all when disabled."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions(enabled=False)
            coordinator = ResearchCoordinator(Path(tmpdir), opts)
            result = coordinator.research()

            assert result.backend_result is None
            assert result.frontend_result is None
            assert result.web_result is None

    def test_runs_all_researchers(self):
        """Should run all enabled researchers."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions(
                backend_enabled=True,
                frontend_enabled=True,
                web_enabled=False,  # Disable web to avoid actual API calls
            )
            coordinator = ResearchCoordinator(Path(tmpdir), opts)
            result = coordinator.research()

            assert result.backend_result is not None
            assert result.frontend_result is not None
            assert result.web_result is None

    def test_selective_researchers(self):
        """Should only run selected researchers."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions(
                backend_enabled=True,
                frontend_enabled=False,
                web_enabled=False,
            )
            coordinator = ResearchCoordinator(Path(tmpdir), opts)
            result = coordinator.research()

            assert result.backend_result is not None
            assert result.frontend_result is None
            assert result.web_result is None

    def test_passes_context_to_researchers(self):
        """Should pass analysis context to researchers."""
        with TemporaryDirectory() as tmpdir:
            opts = ResearchOptions(web_enabled=False)
            coordinator = ResearchCoordinator(Path(tmpdir), opts)
            result = coordinator.research(
                analysis_context="Need to fix user authentication",
                priority_item="Fix login flow",
            )

            # Just verify it runs without error
            assert result is not None
