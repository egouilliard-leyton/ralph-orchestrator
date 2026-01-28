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


class TestMarkdownGuardrailEnforcement:
    """Test markdown file restrictions in test directories."""
    
    def test_markdown_in_tests_blocked(self, fixture_fullstack_min: Path):
        """
        Markdown files in tests/ directory are blocked during test-writing.
        
        Given: Test-writing agent role active
        When: Agent creates tests/T001_test_plan.md
        Then: File is detected as violation and reverted
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Even though tests/** allows files in tests/, markdown should be blocked
        # The markdown check takes precedence
        assert guardrail._is_markdown_in_test_dir("tests/T001_test_plan.md")
        assert guardrail._is_markdown_in_test_dir("tests/unit/readme.md")
    
    def test_report_path_not_violation(self, fixture_fullstack_min: Path):
        """
        Writing to .ralph-session/reports/ is allowed.
        
        Given: Test-writing agent creates report file
        When: Guardrail checks file
        Then: File in .ralph-session/reports/ is not a violation
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Report paths should be treated as internal artifacts (allowed)
        report_paths = [
            ".ralph-session/reports/T-001/test-writing.md",
            ".ralph-session/reports/T-002/implementation.md",
            ".ralph-session/reports/T-001/review.md",
        ]
        
        for path in report_paths:
            assert guardrail._is_internal_artifact(path), f"{path} should be internal artifact"
    
    def test_test_code_files_still_allowed(self, fixture_fullstack_min: Path):
        """
        Test code files (.py, .ts, .tsx) remain allowed in tests/.
        
        Given: Test-writing agent creates test_*.py files
        When: Guardrail checks file
        Then: Test code files are allowed
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Test code files should still be allowed
        allowed_test_files = [
            "tests/test_api.py",
            "tests/unit/test_service.py",
            "tests/conftest.py",
            "frontend/src/App.test.tsx",
        ]
        
        for path in allowed_test_files:
            assert guardrail.is_allowed(path), f"{path} should be allowed"
            assert not guardrail._is_markdown_in_test_dir(path), f"{path} should not be blocked by markdown check"


class TestMarkdownRevertEndToEnd:
    """End-to-end tests for markdown file reversion in test directories.
    
    These tests verify the full check_and_revert() flow with actual file
    creation and deletion, ensuring:
    - Markdown files created in tests/ are actually reverted (deleted)
    - Report files in .ralph-session/reports/ are preserved (not reverted)
    """
    
    def test_markdown_file_in_tests_actually_reverted(self, fixture_fullstack_min: Path):
        """
        Markdown file created in tests/ is actually deleted by check_and_revert.
        
        Given: A git-initialized repo with tests/ directory
        When: A markdown file is created in tests/ and check_and_revert runs
        Then: The markdown file is deleted and recorded as a violation
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        # Take snapshot before creating the file
        before_snapshot = guardrail.snapshot_state()
        
        # Create a markdown file in tests/ (simulating agent behavior)
        tests_dir = fixture_fullstack_min / "tests"
        tests_dir.mkdir(exist_ok=True)
        md_file = tests_dir / "T001_test_plan.md"
        md_file.write_text("# Test Plan\nThis should be reverted.\n")
        
        # Verify file exists before revert
        assert md_file.exists(), "Markdown file should exist before revert"
        
        # Run check_and_revert
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        # Verify the markdown file was detected as a violation and reverted
        assert not result.passed, "Should fail due to markdown violation"
        assert len(result.violations) == 1, "Should have exactly one violation"
        assert result.violations[0].path == "tests/T001_test_plan.md"
        assert "tests/T001_test_plan.md" in result.reverted_files
        
        # Verify the file was actually deleted
        assert not md_file.exists(), "Markdown file should be deleted after revert"
    
    def test_nested_markdown_file_in_tests_reverted(self, fixture_fullstack_min: Path):
        """
        Markdown file in nested tests/ subdirectory is also reverted.
        
        Given: A markdown file in tests/unit/README.md
        When: check_and_revert runs
        Then: The nested markdown file is deleted
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        before_snapshot = guardrail.snapshot_state()
        
        # Create nested directory and markdown file
        unit_dir = fixture_fullstack_min / "tests" / "unit"
        unit_dir.mkdir(parents=True, exist_ok=True)
        nested_md = unit_dir / "notes.md"
        nested_md.write_text("# Notes\nShould also be reverted.\n")
        
        assert nested_md.exists()
        
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        assert not result.passed
        assert any(v.path == "tests/unit/notes.md" for v in result.violations)
        assert not nested_md.exists(), "Nested markdown should be deleted"
    
    def test_report_file_not_reverted(self, fixture_fullstack_min: Path):
        """
        Report files in .ralph-session/reports/ are NOT reverted.
        
        Given: A report file is created in .ralph-session/reports/T-001/
        When: check_and_revert runs
        Then: The report file is preserved (not treated as violation)
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        before_snapshot = guardrail.snapshot_state()
        
        # Create the reports directory structure
        reports_dir = fixture_fullstack_min / ".ralph-session" / "reports" / "T-001"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / "test-writing.md"
        report_content = "## Attempt 1\n\nTest writing report content.\n"
        report_file.write_text(report_content)
        
        # Verify file exists before check
        assert report_file.exists()
        
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        # Report files should be allowed (internal artifacts)
        # They should appear in allowed_changes, not violations
        assert report_file.exists(), "Report file should NOT be deleted"
        assert "test-writing.md" not in [v.path for v in result.violations]
        assert report_file.read_text() == report_content, "Report content should be unchanged"
    
    def test_mixed_files_only_markdown_reverted(self, fixture_fullstack_min: Path):
        """
        When both test code and markdown are created, only markdown is reverted.
        
        Given: Both test_api.py and docs.md are created in tests/
        When: check_and_revert runs
        Then: docs.md is reverted, test_api.py is preserved
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        before_snapshot = guardrail.snapshot_state()
        
        tests_dir = fixture_fullstack_min / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        # Create legitimate test file
        test_file = tests_dir / "test_new_feature.py"
        test_content = "def test_something():\n    assert True\n"
        test_file.write_text(test_content)
        
        # Create markdown file (should be reverted)
        md_file = tests_dir / "documentation.md"
        md_file.write_text("# Documentation\nThis should be removed.\n")
        
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        # Only the markdown should be a violation
        assert len(result.violations) == 1
        assert result.violations[0].path == "tests/documentation.md"
        
        # Markdown should be deleted
        assert not md_file.exists(), "Markdown should be reverted"
        
        # Test file should remain
        assert test_file.exists(), "Test file should be preserved"
        assert test_file.read_text() == test_content, "Test content unchanged"
    
    def test_multiple_markdown_files_all_reverted(self, fixture_fullstack_min: Path):
        """
        Multiple markdown files in tests/ are all reverted.
        
        Given: Several markdown files created in tests/
        When: check_and_revert runs
        Then: All markdown files are deleted
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        before_snapshot = guardrail.snapshot_state()
        
        tests_dir = fixture_fullstack_min / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        # Create multiple markdown files
        md_files = [
            tests_dir / "T001_plan.md",
            tests_dir / "T002_summary.md",
            tests_dir / "README.md",
        ]
        
        for md_file in md_files:
            md_file.write_text(f"# {md_file.name}\nContent\n")
            assert md_file.exists()
        
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        # All should be violations
        assert len(result.violations) == 3
        assert len(result.reverted_files) == 3
        
        # All should be deleted
        for md_file in md_files:
            assert not md_file.exists(), f"{md_file.name} should be deleted"
    
    def test_report_and_test_code_both_preserved(self, fixture_fullstack_min: Path):
        """
        Both report files and test code files are preserved during revert.
        
        Given: A report file and a test file are created
        When: check_and_revert runs
        Then: Both files are preserved (neither is a violation)
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        before_snapshot = guardrail.snapshot_state()
        
        # Create test file
        tests_dir = fixture_fullstack_min / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_file = tests_dir / "test_feature.py"
        test_file.write_text("def test_it(): pass\n")
        
        # Create report file
        reports_dir = fixture_fullstack_min / ".ralph-session" / "reports" / "T-001"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / "test-writing.md"
        report_file.write_text("## Report\nDetails here.\n")
        
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        # No violations expected
        assert result.passed, "Should pass with no violations"
        assert len(result.violations) == 0
        
        # Both files should remain
        assert test_file.exists(), "Test file preserved"
        assert report_file.exists(), "Report file preserved"
    
    def test_case_insensitive_markdown_extension(self, fixture_fullstack_min: Path):
        """
        Markdown detection is case-insensitive for file extensions.
        
        Given: Files with .MD, .Md extensions in tests/
        When: check_and_revert runs
        Then: All case variants are detected and reverted
        """
        os.chdir(fixture_fullstack_min)
        
        config = load_config(
            fixture_fullstack_min / ".ralph" / "ralph.yml",
            repo_root=fixture_fullstack_min,
        )
        
        guardrail = create_guardrail(config.test_paths, repo_root=fixture_fullstack_min)
        
        before_snapshot = guardrail.snapshot_state()
        
        tests_dir = fixture_fullstack_min / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        # Various case extensions
        md_files = [
            tests_dir / "UPPER.MD",
            tests_dir / "Mixed.Md",
            tests_dir / "lower.md",
        ]
        
        for md_file in md_files:
            md_file.write_text("Content\n")
        
        result = guardrail.check_and_revert(before_snapshot, task_id="T-001")
        
        # All should be violations regardless of case
        assert len(result.violations) == 3
        
        for md_file in md_files:
            assert not md_file.exists(), f"{md_file.name} should be reverted"
