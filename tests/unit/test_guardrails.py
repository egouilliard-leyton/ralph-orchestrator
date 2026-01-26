"""Unit tests for test-writing guardrails."""

import pytest

from ralph_orchestrator.guardrails import (
    FilePathGuardrail,
    FileChange,
    create_guardrail,
)


class TestTestPathMatching:
    """Tests for test path pattern matching."""
    
    @pytest.fixture
    def default_guardrail(self):
        """Create guardrail with default test patterns."""
        return FilePathGuardrail(
            test_paths=["tests/**", "**/*.test.*", "**/*.spec.*", "test_*.py"],
        )
    
    def test_tests_directory_allowed(self, default_guardrail):
        """Files in tests/ directory are allowed."""
        assert default_guardrail.is_allowed("tests/test_main.py")
        assert default_guardrail.is_allowed("tests/__init__.py")
        assert default_guardrail.is_allowed("tests/unit/test_auth.py")
    
    def test_test_file_pattern_allowed(self, default_guardrail):
        """Files matching *.test.* pattern are allowed."""
        assert default_guardrail.is_allowed("src/App.test.tsx")
        assert default_guardrail.is_allowed("components/Button.test.js")
    
    def test_spec_file_pattern_allowed(self, default_guardrail):
        """Files matching *.spec.* pattern are allowed."""
        assert default_guardrail.is_allowed("src/utils.spec.ts")
        assert default_guardrail.is_allowed("lib/parser.spec.py")
    
    def test_test_prefix_pattern_allowed(self, default_guardrail):
        """Files matching test_*.py pattern are allowed."""
        assert default_guardrail.is_allowed("test_utils.py")
        assert default_guardrail.is_allowed("test_main.py")
    
    def test_source_files_rejected(self, default_guardrail):
        """Source files are not allowed."""
        assert not default_guardrail.is_allowed("src/main.py")
        assert not default_guardrail.is_allowed("lib/utils.py")
        assert not default_guardrail.is_allowed("app.py")
    
    def test_config_files_rejected(self, default_guardrail):
        """Configuration files are not allowed."""
        assert not default_guardrail.is_allowed("config.py")
        assert not default_guardrail.is_allowed("settings.json")
        assert not default_guardrail.is_allowed("pyproject.toml")


class TestRecursivePatterns:
    """Tests for recursive glob patterns."""
    
    def test_recursive_tests_pattern(self):
        """tests/** matches nested directories."""
        guardrail = FilePathGuardrail(test_paths=["tests/**"])
        
        assert guardrail.is_allowed("tests/test_main.py")
        assert guardrail.is_allowed("tests/unit/test_auth.py")
        assert guardrail.is_allowed("tests/unit/integration/test_api.py")
    
    def test_recursive_test_file_pattern(self):
        """**/*.test.* matches in any directory."""
        guardrail = FilePathGuardrail(test_paths=["**/*.test.*"])
        
        assert guardrail.is_allowed("App.test.tsx")
        assert guardrail.is_allowed("src/App.test.tsx")
        assert guardrail.is_allowed("src/components/Button.test.tsx")


class TestCustomPatterns:
    """Tests for custom test path patterns."""
    
    def test_frontend_test_directory(self):
        """Frontend-specific test directory pattern."""
        guardrail = FilePathGuardrail(
            test_paths=["frontend/__tests__/**", "frontend/**/*.test.*"]
        )
        
        assert guardrail.is_allowed("frontend/__tests__/utils.test.js")
        assert guardrail.is_allowed("frontend/src/App.test.tsx")
        assert not guardrail.is_allowed("frontend/src/App.tsx")
    
    def test_multiple_test_directories(self):
        """Multiple test directory patterns."""
        guardrail = FilePathGuardrail(
            test_paths=["tests/**", "backend/tests/**", "frontend/__tests__/**"]
        )
        
        assert guardrail.is_allowed("tests/test_main.py")
        assert guardrail.is_allowed("backend/tests/test_api.py")
        assert guardrail.is_allowed("frontend/__tests__/App.test.js")


class TestFileChangeTracking:
    """Tests for FileChange data class."""
    
    def test_new_file_detection(self):
        """FileChange correctly identifies new files."""
        added = FileChange(path="tests/new_test.py", change_type="A")
        untracked = FileChange(path="tests/untracked.py", change_type="?")
        
        assert added.is_new is True
        assert untracked.is_new is True
        assert added.is_modified is False
    
    def test_modified_file_detection(self):
        """FileChange correctly identifies modified files."""
        modified = FileChange(path="tests/test_main.py", change_type="M")
        
        assert modified.is_modified is True
        assert modified.is_new is False
        assert modified.is_deleted is False
    
    def test_deleted_file_detection(self):
        """FileChange correctly identifies deleted files."""
        deleted = FileChange(path="tests/old_test.py", change_type="D")
        
        assert deleted.is_deleted is True
        assert deleted.is_new is False
        assert deleted.is_modified is False


class TestGuardrailFactory:
    """Tests for guardrail factory function."""
    
    def test_create_guardrail_with_patterns(self):
        """Factory creates guardrail with specified patterns."""
        guardrail = create_guardrail(
            test_paths=["tests/**", "**/*.test.*"],
        )
        
        assert isinstance(guardrail, FilePathGuardrail)
        assert guardrail.is_allowed("tests/test_main.py")
        assert guardrail.is_allowed("src/App.test.tsx")
    
    def test_create_guardrail_with_repo_root(self, tmp_path):
        """Factory accepts repo_root parameter."""
        guardrail = create_guardrail(
            test_paths=["tests/**"],
            repo_root=tmp_path,
        )
        
        assert guardrail.repo_root == tmp_path


class TestPathNormalization:
    """Tests for path normalization."""
    
    def test_leading_dot_slash_removed(self):
        """Leading ./ is normalized in paths."""
        guardrail = FilePathGuardrail(test_paths=["tests/**"])
        
        assert guardrail.is_allowed("./tests/test_main.py")
        assert guardrail.is_allowed("tests/test_main.py")
    
    def test_pattern_leading_dot_slash_handled(self):
        """Patterns with leading ./ are normalized."""
        guardrail = FilePathGuardrail(test_paths=["./tests/**"])
        
        assert guardrail.is_allowed("tests/test_main.py")
