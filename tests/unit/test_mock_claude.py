"""
Unit tests for the mock Claude CLI.

These tests verify the mock Claude behavior to ensure it correctly
simulates the real Claude CLI for testing purposes.
"""

import pytest
import sys
import os
from pathlib import Path
from io import StringIO
from unittest.mock import patch

# Add mock_claude to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mock_claude"))
from mock_claude import MockClaudeCLI


class TestMockClaudeTokenExtraction:
    """Tests for session token extraction from prompts."""
    
    def test_extract_token_from_standard_format(self):
        """Extract token from standard SESSION_TOKEN format."""
        cli = MockClaudeCLI()
        cli.prompt = 'SESSION_TOKEN: "ralph-20260125-143052-a1b2c3d4e5f6g7h8"'
        
        token = cli.extract_session_token()
        
        assert token == "ralph-20260125-143052-a1b2c3d4e5f6g7h8"
    
    def test_extract_token_from_xml_format(self):
        """Extract token from XML session attribute."""
        cli = MockClaudeCLI()
        cli.prompt = '<task-done session="ralph-20260125-143052-a1b2c3d4e5f6g7h8">'
        
        token = cli.extract_session_token()
        
        assert token == "ralph-20260125-143052-a1b2c3d4e5f6g7h8"
    
    def test_extract_token_fallback_to_default(self):
        """Return default token when none found in prompt."""
        cli = MockClaudeCLI()
        cli.prompt = "No token here"
        
        token = cli.extract_session_token()
        
        assert token.startswith("ralph-")


class TestMockClaudeTaskIdExtraction:
    """Tests for task ID extraction from prompts."""
    
    def test_extract_task_id_standard(self):
        """Extract task ID from standard format."""
        cli = MockClaudeCLI()
        cli.prompt = "Task: T-003\nImplement the feature"
        
        task_id = cli.extract_task_id()
        
        assert task_id == "T-003"
    
    def test_extract_task_id_inline(self):
        """Extract task ID from inline reference."""
        cli = MockClaudeCLI()
        cli.prompt = "Working on T-007 implementation"
        
        task_id = cli.extract_task_id()
        
        assert task_id == "T-007"
    
    def test_extract_task_id_default(self):
        """Return default task ID when none found."""
        cli = MockClaudeCLI()
        cli.prompt = "No task ID here"
        
        task_id = cli.extract_task_id()
        
        assert task_id == "T-001"


class TestMockClaudeRoleDetection:
    """Tests for agent role detection from prompts."""
    
    def test_detect_implementation_role(self):
        """Detect implementation role from generic prompt."""
        cli = MockClaudeCLI()
        cli.prompt = "Implement the authentication feature"
        
        role = cli.detect_role()
        
        assert role == "implementation"
    
    def test_detect_test_writing_role(self):
        """Detect test writing role from guardrail prompt."""
        cli = MockClaudeCLI()
        cli.prompt = "Write tests with guardrail restrictions"
        
        role = cli.detect_role()
        
        assert role == "test_writing"
    
    def test_detect_review_role(self):
        """Detect review role from read-only prompt."""
        cli = MockClaudeCLI()
        cli.prompt = "Code review task. READ-ONLY mode"
        
        role = cli.detect_role()
        
        assert role == "review"
    
    def test_detect_fix_role(self):
        """Detect fix role from error prompt."""
        cli = MockClaudeCLI()
        cli.prompt = "Fix issues found during verification"
        
        role = cli.detect_role()
        
        assert role == "fix"
    
    def test_detect_analysis_role(self):
        """Detect analysis role from report prompt."""
        cli = MockClaudeCLI()
        cli.prompt = "Analyze this report and identify priorities"
        
        role = cli.detect_role()
        
        assert role == "analysis"


class TestMockClaudeDirectives:
    """Tests for special directive handling."""
    
    def test_detect_invalid_token_directive(self):
        """Detect SIMULATE_INVALID_TOKEN directive."""
        cli = MockClaudeCLI()
        cli.prompt = "Task: T-001 SIMULATE_INVALID_TOKEN"
        
        directive = cli.check_special_directives()
        
        assert directive == "invalid_token"
    
    def test_detect_no_signal_directive(self):
        """Detect SIMULATE_NO_SIGNAL directive."""
        cli = MockClaudeCLI()
        cli.prompt = "Task: T-001 SIMULATE_NO_SIGNAL"
        
        directive = cli.check_special_directives()
        
        assert directive == "no_signal"
    
    def test_detect_review_reject_directive(self):
        """Detect SIMULATE_REVIEW_REJECT directive."""
        cli = MockClaudeCLI()
        cli.prompt = "Review SIMULATE_REVIEW_REJECT"
        
        directive = cli.check_special_directives()
        
        assert directive == "review_reject"
    
    def test_no_directive_returns_none(self):
        """Return None when no directive present."""
        cli = MockClaudeCLI()
        cli.prompt = "Normal prompt without directives"
        
        directive = cli.check_special_directives()
        
        assert directive is None


class TestMockClaudeResponses:
    """Tests for response generation."""
    
    def test_implementation_response_contains_signal(self):
        """Implementation response contains task-done signal."""
        cli = MockClaudeCLI()
        cli.prompt = 'SESSION_TOKEN: "ralph-test-token" Task: T-001'
        
        response = cli.generate_response()
        
        assert "<task-done" in response
        assert "ralph-test-token" in response
    
    def test_invalid_token_response(self):
        """Invalid token directive produces wrong token in response."""
        cli = MockClaudeCLI()
        cli.prompt = "SIMULATE_INVALID_TOKEN Task: T-001"
        
        response = cli.generate_response()
        
        assert "<task-done" in response
        assert "wrong-token" in response
    
    def test_no_signal_response(self):
        """No signal directive produces response without signal."""
        cli = MockClaudeCLI()
        cli.prompt = "SIMULATE_NO_SIGNAL Task: T-001"
        
        response = cli.generate_response()
        
        assert "<task-done" not in response
        assert "<tests-done" not in response
    
    def test_review_response_contains_approval(self):
        """Review role produces review-approved signal."""
        cli = MockClaudeCLI()
        cli.prompt = 'SESSION_TOKEN: "ralph-test" Code review task READ-ONLY'
        
        response = cli.generate_response()
        
        assert "<review-approved" in response
    
    def test_analysis_response_is_json(self):
        """Analysis role produces valid JSON."""
        import json
        
        cli = MockClaudeCLI()
        cli.prompt = "Analyze this report"
        
        response = cli.generate_response()
        
        # Should be valid JSON
        data = json.loads(response)
        assert "priority_item" in data
        assert "branch_name" in data


@pytest.mark.unit
class TestMockClaudeIntegration:
    """Integration tests for mock Claude CLI behavior."""
    
    def test_full_implementation_workflow(self):
        """Test full implementation agent workflow."""
        cli = MockClaudeCLI()
        cli.prompt = '''SESSION_TOKEN: "ralph-20260125-143052-abcdef1234567890"
        
        Task: T-001
        Title: Add multiply function
        
        Implement the multiply function in src/main.py.
        '''
        
        response = cli.generate_response()
        
        # Should have valid completion signal with correct token
        assert "<task-done" in response
        assert "ralph-20260125-143052-abcdef1234567890" in response
        assert "T-001" in response
    
    def test_test_writing_workflow(self):
        """Test test-writing agent workflow."""
        cli = MockClaudeCLI()
        cli.prompt = '''SESSION_TOKEN: "ralph-test-token"
        
        Write tests with guardrail restrictions.
        Only modify files in tests/ directory.
        '''
        
        response = cli.generate_response()
        
        assert "<tests-done" in response
        assert "ralph-test-token" in response
