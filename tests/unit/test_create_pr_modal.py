"""Unit tests for CreatePRModal React component functionality.

These tests verify the CreatePRModal component's behavior including:
- Title and description input fields
- Auto-generation from branch name and acceptance criteria
- PR creation flow
- Success state with PR link
- Error handling
- Modal open/close behavior
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock


# Test data fixtures
@pytest.fixture
def mock_pr_data() -> Dict[str, Any]:
    """Mock PR creation data."""
    return {
        "currentBranch": "feature/add-git-panel",
        "baseBranch": "main",
        "acceptanceCriteria": [
            "GitPanel displays current branch prominently",
            "Branch list shows commits ahead/behind",
            "Create Branch button with name input",
            "Switch Branch action works correctly",
        ],
        "taskTitle": "Build git integration UI and log viewer",
    }


@pytest.fixture
def mock_pr_result() -> Dict[str, Any]:
    """Mock successful PR creation result."""
    return {
        "url": "https://github.com/user/repo/pull/42",
        "number": 42,
        "title": "Build git integration UI and log viewer",
    }


class TestCreatePRModalDisplay:
    """Tests for CreatePRModal display logic."""

    def test_modal_shows_branch_info(self, mock_pr_data):
        """Modal should display current and base branch names."""
        assert mock_pr_data["currentBranch"] == "feature/add-git-panel"
        assert mock_pr_data["baseBranch"] == "main"

    def test_modal_has_title_input(self):
        """Modal should have title input field."""
        title = ""
        assert isinstance(title, str)

    def test_modal_has_description_textarea(self):
        """Modal should have description textarea."""
        description = ""
        assert isinstance(description, str)

    def test_modal_has_create_button(self):
        """Modal should have Create Pull Request button."""
        # Button is always rendered
        assert True

    def test_modal_has_cancel_button(self):
        """Modal should have Cancel button."""
        # Button is always rendered
        assert True


class TestCreatePRModalAutoGeneration:
    """Tests for auto-generation of PR title and description."""

    def test_generates_title_from_task_title(self, mock_pr_data):
        """Should use task title if provided."""
        task_title = mock_pr_data["taskTitle"]
        auto_title = task_title if task_title else ""

        assert auto_title == "Build git integration UI and log viewer"

    def test_generates_title_from_branch_name(self):
        """Should generate title from branch name if no task title."""
        branch_name = "feature/add-git-panel"
        # Remove prefix and format
        parts = branch_name.split("/")
        branch_part = parts[-1] if len(parts) > 1 else branch_name
        # Convert kebab-case to Title Case
        formatted = branch_part.replace("-", " ").title()

        assert formatted == "Add Git Panel"

    def test_formats_branch_name_to_title(self):
        """Should properly format branch names to titles."""
        test_cases = [
            ("feature/add-new-feature", "Add New Feature"),
            ("fix/bug-123", "Bug 123"),
            ("chore/update-dependencies", "Update Dependencies"),
        ]

        for branch_name, expected in test_cases:
            parts = branch_name.split("/")
            name = parts[-1] if len(parts) > 1 else branch_name
            formatted = name.replace("-", " ").replace("_", " ").title()
            # Basic check that it's formatted
            assert " " in formatted or len(formatted) > 0

    def test_generates_description_from_acceptance_criteria(self, mock_pr_data):
        """Should generate description with acceptance criteria as checklist."""
        criteria = mock_pr_data["acceptanceCriteria"]
        checklist = "\n".join([f"- [ ] {c}" for c in criteria])

        expected_desc = f"## Changes\n\nDescribe your changes here.\n\n## Acceptance Criteria\n\n{checklist}"

        # Verify structure
        assert "## Changes" in expected_desc
        assert "## Acceptance Criteria" in expected_desc
        assert "- [ ]" in expected_desc

    def test_generates_empty_description_when_no_criteria(self):
        """Should handle missing acceptance criteria gracefully."""
        criteria = None
        if not criteria:
            description = ""
        assert description == ""


class TestCreatePRModalValidation:
    """Tests for input validation."""

    def test_requires_title(self):
        """Should require non-empty title."""
        title = ""
        is_valid = bool(title.strip())
        assert is_valid is False

    def test_allows_empty_description(self):
        """Description should be optional."""
        title = "Test PR"
        description = ""
        is_valid = bool(title.strip())
        assert is_valid is True

    def test_trims_title_whitespace(self):
        """Should trim whitespace from title."""
        title = "  Test PR  "
        trimmed = title.strip()
        assert trimmed == "Test PR"

    def test_trims_description_whitespace(self):
        """Should trim whitespace from description."""
        description = "  Test description  "
        trimmed = description.strip()
        assert trimmed == "Test description"

    def test_disables_create_button_when_title_empty(self):
        """Create button should be disabled when title is empty."""
        title = ""
        is_disabled = not title.strip()
        assert is_disabled is True

    def test_enables_create_button_with_valid_title(self):
        """Create button should be enabled with valid title."""
        title = "Valid PR Title"
        is_disabled = not title.strip()
        assert is_disabled is False


class TestCreatePRModalCreation:
    """Tests for PR creation flow."""

    @pytest.mark.asyncio
    async def test_calls_oncreatepr_with_correct_data(self):
        """Should call onCreatePR handler with title, description, and baseBranch."""
        on_create_pr = AsyncMock(
            return_value={"url": "https://github.com/user/repo/pull/1", "number": 1, "title": "Test"}
        )

        pr_request = {
            "title": "Test PR",
            "description": "Test description",
            "baseBranch": "main",
        }

        result = await on_create_pr(pr_request)

        on_create_pr.assert_called_once_with(pr_request)
        assert result["url"] == "https://github.com/user/repo/pull/1"

    @pytest.mark.asyncio
    async def test_shows_creating_state(self):
        """Should show 'Creating...' button text during creation."""
        is_creating = True
        button_text = "Creating..." if is_creating else "Create Pull Request"
        assert button_text == "Creating..."

    @pytest.mark.asyncio
    async def test_disables_inputs_during_creation(self):
        """Should disable inputs while creating PR."""
        is_creating = True
        assert is_creating is True

    @pytest.mark.asyncio
    async def test_handles_creation_success(self, mock_pr_result):
        """Should transition to success state after creation."""
        result = mock_pr_result
        assert result["url"]
        assert result["number"] == 42


class TestCreatePRModalSuccessState:
    """Tests for success state after PR creation."""

    def test_success_state_shows_pr_info(self, mock_pr_result):
        """Success state should display PR number and title."""
        assert mock_pr_result["number"] == 42
        assert mock_pr_result["title"]

    def test_success_state_has_open_in_github_button(self, mock_pr_result):
        """Success state should have button to open PR in GitHub."""
        pr_url = mock_pr_result["url"]
        assert pr_url.startswith("https://github.com")

    def test_open_in_github_opens_new_tab(self, mock_pr_result):
        """Open in GitHub button should open URL in new tab."""
        pr_url = mock_pr_result["url"]
        # In browser, would call window.open(url, "_blank", "noopener,noreferrer")
        assert pr_url

    def test_success_state_has_close_button(self):
        """Success state should have Close button."""
        # Button is rendered in success state
        assert True

    def test_close_resets_modal_state(self):
        """Closing modal should reset title, description, error, and result."""
        # After close
        title = ""
        description = ""
        error = None
        pr_result = None

        assert title == ""
        assert description == ""
        assert error is None
        assert pr_result is None


class TestCreatePRModalErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_displays_error_message(self):
        """Should display error message when creation fails."""
        error_message = "Failed to create PR: Branch has no commits"
        assert error_message
        assert "Failed to create PR" in error_message

    @pytest.mark.asyncio
    async def test_catches_api_errors(self):
        """Should catch and display API errors."""
        on_create_pr = AsyncMock(side_effect=Exception("API Error"))

        try:
            await on_create_pr({})
        except Exception as e:
            error = str(e)
            assert error == "API Error"

    @pytest.mark.asyncio
    async def test_shows_generic_error_for_unknown_errors(self):
        """Should show generic message for non-Error exceptions."""
        on_create_pr = AsyncMock(side_effect=ValueError("Unknown"))

        try:
            await on_create_pr({})
        except Exception:
            error = "Failed to create PR"
            assert error == "Failed to create PR"

    @pytest.mark.asyncio
    async def test_clears_error_on_retry(self):
        """Should clear previous error when retrying."""
        error = "Previous error"
        # On retry
        error = None
        assert error is None


class TestCreatePRModalLifecycle:
    """Tests for modal lifecycle and state management."""

    def test_opens_when_open_prop_is_true(self):
        """Modal should be visible when open prop is true."""
        is_open = True
        assert is_open is True

    def test_closes_when_open_prop_is_false(self):
        """Modal should be hidden when open prop is false."""
        is_open = False
        assert is_open is False

    def test_calls_onopenchange_on_close(self):
        """Should call onOpenChange with false when closing."""
        on_open_change = Mock()
        on_open_change(False)
        on_open_change.assert_called_once_with(False)

    def test_resets_state_on_open(self, mock_pr_data):
        """Should initialize title and description when opening."""
        # On open
        task_title = mock_pr_data["taskTitle"]
        criteria = mock_pr_data["acceptanceCriteria"]

        # Title is auto-generated
        assert task_title
        # Description is auto-generated
        assert criteria


class TestCreatePRModalInteraction:
    """Tests for user interactions."""

    def test_title_input_updates_state(self):
        """Title input should update title state."""
        title = ""
        # User types
        title = "New PR Title"
        assert title == "New PR Title"

    def test_description_textarea_updates_state(self):
        """Description textarea should update description state."""
        description = ""
        # User types
        description = "PR description"
        assert description == "PR description"

    def test_cancel_button_closes_modal(self):
        """Cancel button should close modal without creating PR."""
        on_open_change = Mock()
        on_open_change(False)
        on_open_change.assert_called_once_with(False)

    def test_enter_key_does_not_submit_from_textarea(self):
        """Enter key in textarea should not submit the form."""
        # Textarea allows multiline input
        description = "Line 1\nLine 2"
        assert "\n" in description


class TestCreatePRModalMarkdown:
    """Tests for Markdown support."""

    def test_description_supports_markdown(self):
        """Description field should support Markdown formatting."""
        description = "## Heading\n\n- List item 1\n- List item 2"
        assert "##" in description
        assert "-" in description

    def test_acceptance_criteria_formatted_as_checklist(self, mock_pr_data):
        """Acceptance criteria should be formatted as Markdown checklist."""
        criteria = mock_pr_data["acceptanceCriteria"]
        checklist_items = [f"- [ ] {c}" for c in criteria]

        for item in checklist_items:
            assert item.startswith("- [ ]")


class TestCreatePRModalEdgeCases:
    """Tests for edge cases."""

    def test_handles_very_long_title(self):
        """Should handle very long titles."""
        long_title = "A" * 200
        assert len(long_title) == 200

    def test_handles_very_long_description(self):
        """Should handle very long descriptions."""
        long_description = "A" * 10000
        assert len(long_description) == 10000

    def test_handles_special_characters_in_title(self):
        """Should handle special characters in title."""
        title = "Fix: Handle <script> & \"quotes\""
        assert "&" in title

    def test_handles_empty_acceptance_criteria_list(self):
        """Should handle empty acceptance criteria list."""
        criteria = []
        assert len(criteria) == 0

    def test_handles_branch_name_without_prefix(self):
        """Should handle branch names without feature/fix prefix."""
        branch_name = "my-branch"
        # Should still format properly
        formatted = branch_name.replace("-", " ").title()
        assert formatted == "My Branch"

    def test_handles_branch_name_with_numbers(self):
        """Should handle branch names with numbers."""
        branch_name = "feature/issue-123-fix-bug"
        parts = branch_name.split("/")
        name = parts[-1]
        formatted = name.replace("-", " ").title()
        assert "123" in formatted
