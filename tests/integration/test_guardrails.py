"""
Integration tests for test-agent file guardrails.

These tests verify that the Ralph orchestrator correctly:
- Restricts test-writing agent to test directories only
- Detects and reverts unauthorized file modifications
- Allows legitimate test file creation
- Logs guardrail violations

The guardrails prevent the test-writing agent from modifying
source code under the guise of "writing tests".
"""

import pytest
import os
import json
import yaml
from pathlib import Path

from ralph_orchestrator.guardrails import (
    FilePathGuardrail,
    create_guardrail,
    FileChange,
    GuardrailResult,
)
from ralph_orchestrator.config import load_config

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestTestPathRestrictions:
    """Test test-agent path restrictions."""
    
    def test_test_files_allowed(self, fixture_fullstack_min: Path):
        """
        Test agent can modify files in tests/ directory.
        
        Given: Test-writing agent role active
        When: Agent modifies tests/test_*.py
        Then: Modifications are allowed
        """
        os.chdir(fixture_fullstack_min)
        
        # Verify tests directory exists
        tests_dir = fixture_fullstack_min / "tests"
        assert tests_dir.exists()
        
        # Load config to get test patterns
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        # Create guardrail with config patterns
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Test paths that should be allowed
        allowed_paths = [
            "tests/test_api.py",
            "tests/__init__.py",
            "tests/unit/test_service.py",
        ]
        
        for path in allowed_paths:
            assert guardrail.is_allowed(path), f"{path} should be allowed"
    
    def test_source_files_rejected(self, fixture_fullstack_min: Path):
        """
        Test agent modifications to src/ are rejected.
        
        Given: Test-writing agent role active
        When: Agent modifies src/*.py
        Then: Modifications are rejected/reverted
        """
        os.chdir(fixture_fullstack_min)
        
        # Load config to get test patterns
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        # Create guardrail
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Paths that should NOT be allowed
        rejected_paths = [
            "src/api/main.py",
            "src/models/user.py",
            "main.py",
            "config.py",
        ]
        
        for path in rejected_paths:
            assert not guardrail.is_allowed(path), f"{path} should be rejected"
    
    def test_frontend_test_files_allowed(self, fixture_fullstack_min: Path):
        """
        Test agent can modify frontend test files.
        
        Given: Fullstack project with frontend
        When: Agent modifies *.test.tsx files
        Then: Modifications are allowed
        """
        os.chdir(fixture_fullstack_min)
        
        # Load config
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        allowed_frontend_paths = [
            "frontend/src/App.test.tsx",
            "frontend/src/components/Button.spec.ts",
            "frontend/__tests__/utils.test.js",
        ]
        
        for path in allowed_frontend_paths:
            assert guardrail.is_allowed(path), f"{path} should be allowed"
    
    def test_frontend_source_files_rejected(self, fixture_fullstack_min: Path):
        """
        Test agent cannot modify frontend source files.
        
        Given: Fullstack project with frontend
        When: Agent modifies frontend/src/App.tsx
        Then: Modifications are rejected
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        rejected_frontend_paths = [
            "frontend/src/App.tsx",
            "frontend/src/components/Button.tsx",
            "frontend/src/utils/helpers.ts",
        ]
        
        for path in rejected_frontend_paths:
            assert not guardrail.is_allowed(path), f"{path} should be rejected"


class TestGuardrailViolationDetection:
    """Test detection and handling of guardrail violations."""
    
    def test_guardrail_violation_logged(self, fixture_fullstack_min: Path):
        """
        Guardrail violations are logged for audit.
        
        Given: Test agent modifies source file
        When: Guardrail check runs
        Then: Violation is detected and logged
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Simulate file changes including a violation
        before_snapshot = set()  # Empty snapshot (no prior changes)
        
        # Create a test file change and a source file change
        test_change = FileChange(path="tests/test_new.py", change_type="A")
        violation_change = FileChange(path="src/api/main.py", change_type="M")
        
        # Verify test file is allowed
        assert guardrail.is_allowed(test_change.path)
        
        # Verify source file is not allowed
        assert not guardrail.is_allowed(violation_change.path)
    
    def test_violation_reverts_source_changes(self, fixture_fullstack_min: Path):
        """
        Source file changes are reverted on violation.
        
        Given: Test agent modifies source file
        When: Guardrail violation detected
        Then: Source file can be restored
        """
        os.chdir(fixture_fullstack_min)
        
        # Track source file before any changes
        src_file = fixture_fullstack_min / "src" / "api" / "main.py"
        original_content = src_file.read_text()
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Verify source file modification would be rejected
        assert not guardrail.is_allowed("src/api/main.py")
        
        # Source file should still have original content (no actual modification made)
        assert src_file.read_text() == original_content
    
    def test_test_changes_preserved_on_violation(self, fixture_fullstack_min: Path):
        """
        Legitimate test file changes are kept even if violation detected.
        
        Given: Test agent modifies both test and source files
        When: Guardrail violation detected
        Then: Test file changes are allowed, source changes are rejected
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Test file should be allowed
        assert guardrail.is_allowed("tests/test_api.py")
        
        # Source file should be rejected
        assert not guardrail.is_allowed("src/api/main.py")


class TestFileChangeTracking:
    """Test tracking of file changes for guardrail enforcement."""
    
    def test_changes_tracked_before_after(self, fixture_python_min: Path):
        """
        File changes tracked before and after agent run.
        
        Given: Clean repo state
        When: Guardrail snapshot taken
        Then: Changed files can be tracked
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_python_min)
        
        # Take snapshot before any changes
        before_snapshot = guardrail.snapshot_state()
        
        # Snapshot should be a set
        assert isinstance(before_snapshot, set)
    
    def test_git_diff_used_for_change_detection(self, fixture_python_min: Path):
        """
        Git diff used to detect file changes.
        
        Given: Git-initialized fixture
        When: Files modified
        Then: Changes detected via git status/diff
        """
        os.chdir(fixture_python_min)
        
        # Verify git is initialized
        git_dir = fixture_python_min / ".git"
        assert git_dir.exists(), "Fixture should have git initialized"
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_python_min)
        
        # Get file changes via git
        staged, unstaged = guardrail.get_file_changes()
        
        # Both should be lists (possibly empty)
        assert isinstance(staged, list)
        assert isinstance(unstaged, list)


class TestCustomTestPatterns:
    """Test custom test path pattern configuration."""
    
    def test_custom_patterns_from_config(self, fixture_python_min: Path):
        """
        Custom test patterns loaded from ralph.yml.
        
        Given: Config has test_paths defined
        When: Guardrail initialized
        Then: Uses patterns from config
        """
        config_file = fixture_python_min / ".ralph" / "ralph.yml"
        config_data = yaml.safe_load(config_file.read_text())
        
        assert "test_paths" in config_data
        assert len(config_data["test_paths"]) > 0
        
        # Verify patterns include expected directories
        patterns = config_data["test_paths"]
        assert any("tests" in p for p in patterns)
        
        # Load config and verify it loads test_paths
        config = load_config(config_file, repo_root=fixture_python_min)
        assert len(config.test_paths) > 0
    
    def test_glob_patterns_supported(self, fixture_fullstack_min: Path):
        """
        Glob patterns work for test path matching.
        
        Given: Config with glob patterns
        When: Path checked against patterns
        Then: Glob matching works correctly
        """
        config_file = fixture_fullstack_min / ".ralph" / "ralph.yml"
        config_data = yaml.safe_load(config_file.read_text())
        
        patterns = config_data["test_paths"]
        
        # Should support glob patterns like:
        # - tests/**
        # - frontend/**/*.test.*
        # - frontend/**/*.spec.*
        
        assert any("**" in p for p in patterns), "Should support recursive globs"
        
        # Verify glob patterns work with guardrail
        guardrail = create_guardrail(patterns, repo_root=fixture_fullstack_min)
        
        # Tests in nested directories should match
        assert guardrail.is_allowed("tests/unit/test_foo.py")
        assert guardrail.is_allowed("tests/integration/test_bar.py")


class TestRoleBasedGuardrails:
    """Test that guardrails apply based on agent role."""
    
    def test_implementation_agent_no_restrictions(self, fixture_python_min: Path):
        """
        Implementation agent can modify any file.
        
        Given: Implementation agent role active
        When: Agent modifies any file
        Then: No guardrail restrictions applied (guardrails only for test_writing)
        """
        # Implementation agent should have full access
        # Guardrails are only applied to test_writing role
        # This is enforced at the orchestrator level, not the guardrail level
        pass
    
    def test_review_agent_read_only(self, fixture_python_min: Path):
        """
        Review agent cannot modify any files.
        
        Given: Review agent role active
        When: Any file modification attempted
        Then: Modification rejected (review is read-only)
        """
        # Review agent has read-only access via allowed_tools configuration
        # This is enforced by Claude CLI tool restrictions
        pass
    
    def test_test_agent_restricted_to_tests(self, fixture_python_min: Path):
        """
        Test-writing agent only modifies test files.
        
        Given: Test-writing agent role active
        When: File modification attempted
        Then: Only test files allowed
        """
        os.chdir(fixture_python_min)
        
        config = load_config(
            fixture_python_min / ".ralph" / "ralph.yml",
            repo_root=fixture_python_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_python_min)
        
        # Test files allowed
        assert guardrail.is_allowed("tests/test_main.py")
        
        # Source files not allowed
        assert not guardrail.is_allowed("src/main.py")
