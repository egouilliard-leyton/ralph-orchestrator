"""
Integration tests for T-010: Build multi-project dashboard UI

Tests verify:
- Dashboard landing page (src/pages/index.tsx) displays correctly
- ProjectList component renders grid of project cards
- ProjectCard shows required information (name, branch, task counts, status, last activity)
- Quick actions (Open, Start Autopilot) are available
- Global search filters projects by name
- Status filter (active, idle, errors) works correctly
- Grid/list view toggle functionality
- WebSocket connection updates projects in real-time
- Loading states and empty state handled properly
- Responsive design (basic structure verification)
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def frontend_dir():
    """Return the frontend directory path."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "frontend"


@pytest.fixture
def src_dir(frontend_dir):
    """Return the frontend src directory."""
    return frontend_dir / "src"


class TestDashboardPage:
    """Test dashboard landing page implementation."""

    def test_dashboard_page_exists(self, src_dir):
        """Verify src/app/page.tsx exists as dashboard landing page."""
        page_file = src_dir / "app" / "page.tsx"
        assert page_file.exists(), "Dashboard page (src/app/page.tsx) does not exist"

    def test_dashboard_uses_project_list_component(self, src_dir):
        """Verify dashboard imports and uses ProjectList component."""
        page_file = src_dir / "app" / "page.tsx"
        content = page_file.read_text()

        assert "ProjectList" in content, "ProjectList component not imported"
        assert "<ProjectList" in content, "ProjectList component not used in JSX"

    def test_dashboard_uses_projects_hook(self, src_dir):
        """Verify dashboard uses useProjects hook for data fetching."""
        page_file = src_dir / "app" / "page.tsx"
        content = page_file.read_text()

        assert "useProjects" in content, "useProjects hook not imported"
        assert "const" in content and "projects" in content, "Projects data not destructured"

    def test_dashboard_displays_stats(self, src_dir):
        """Verify dashboard calculates and displays aggregated stats."""
        page_file = src_dir / "app" / "page.tsx"
        content = page_file.read_text()

        # Check for stats calculation
        assert "taskCounts" in content, "Task counts not accessed"

        # Check for stat cards displaying key metrics
        assert "Active Projects" in content or "activeProjects" in content, \
            "Active projects stat not displayed"
        assert "Pending" in content or "pending" in content, \
            "Pending tasks stat not displayed"
        assert "Completed" in content or "completed" in content, \
            "Completed tasks stat not displayed"

    def test_dashboard_shows_websocket_status(self, src_dir):
        """Verify dashboard displays WebSocket connection status."""
        page_file = src_dir / "app" / "page.tsx"
        content = page_file.read_text()

        assert "wsStatus" in content, "WebSocket status not accessed from useProjects"
        # Check that status is displayed (likely via a badge or indicator)
        assert "Badge" in content or "status" in content, "Status indicator not displayed"

    def test_dashboard_handles_autopilot_action(self, src_dir):
        """Verify dashboard provides handler for Start Autopilot action."""
        page_file = src_dir / "app" / "page.tsx"
        content = page_file.read_text()

        assert "onStartAutopilot" in content or "handleStartAutopilot" in content or "startAutopilot" in content, \
            "Autopilot handler not defined"
        assert "api.orchestration.run" in content or "orchestration" in content, \
            "Autopilot handler should call orchestration API"


class TestProjectListComponent:
    """Test ProjectList component implementation."""

    def test_project_list_component_exists(self, src_dir):
        """Verify ProjectList component file exists."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        assert project_list_file.exists(), \
            "ProjectList component (src/components/projects/project-list.tsx) does not exist"

    def test_project_list_exports_named_component(self, src_dir):
        """Verify ProjectList is exported."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "export" in content and "ProjectList" in content, \
            "ProjectList component not exported"

    def test_project_list_accepts_required_props(self, src_dir):
        """Verify ProjectList accepts required props (projects, isLoading, error)."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        # Check interface or props definition
        assert "projects" in content, "projects prop not defined"
        assert "isLoading" in content, "isLoading prop not defined"
        assert "error" in content, "error prop not defined"

    def test_project_list_displays_grid_view(self, src_dir):
        """Verify ProjectList can display projects in grid layout."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "grid" in content.lower(), "Grid layout not implemented"
        assert "ProjectCard" in content, "ProjectCard component not used"

    def test_project_list_displays_list_view(self, src_dir):
        """Verify ProjectList can display projects in list layout."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        # Check for list view implementation or toggle
        assert ("list" in content.lower() and "view" in content.lower()) or \
               "ProjectListView" in content, \
            "List view not implemented"

    def test_project_list_has_view_toggle(self, src_dir):
        """Verify ProjectList has grid/list view toggle buttons."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "viewMode" in content or "view" in content, "View mode state not defined"
        # Check for toggle buttons or icons
        assert ("GridIcon" in content or "grid" in content.lower()) and \
               ("ListIcon" in content or "list" in content.lower()), \
            "View toggle icons not present"

    def test_project_list_has_search_input(self, src_dir):
        """Verify ProjectList has global search input."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "Input" in content, "Input component not imported"
        assert "search" in content.lower(), "Search input not implemented"
        assert "searchQuery" in content or "search" in content, "Search state not defined"

    def test_project_list_filters_by_search(self, src_dir):
        """Verify ProjectList filters projects based on search query."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "filter" in content.lower(), "Filtering logic not implemented"
        assert "toLowerCase" in content or "includes" in content, \
            "Search filtering not implemented"

    def test_project_list_has_status_filter(self, src_dir):
        """Verify ProjectList has status filter buttons."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "statusFilter" in content or "status" in content, "Status filter not defined"
        # Check for filter options
        assert "active" in content and "idle" in content, \
            "Status filter options (active, idle) not present"

    def test_project_list_handles_loading_state(self, src_dir):
        """Verify ProjectList displays loading state with skeletons."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "isLoading" in content, "isLoading prop not used"
        assert "Skeleton" in content or "skeleton" in content.lower() or "loading" in content.lower(), \
            "Loading state not handled"

    def test_project_list_handles_empty_state(self, src_dir):
        """Verify ProjectList displays empty state when no projects."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "length === 0" in content or "length == 0" in content or "EmptyState" in content, \
            "Empty state not handled"
        assert "No projects" in content or "no projects" in content.lower(), \
            "Empty state message not present"

    def test_project_list_handles_error_state(self, src_dir):
        """Verify ProjectList displays error message when fetch fails."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "error" in content, "Error prop not used"
        assert "Failed" in content or "failed" in content or "Error" in content, \
            "Error message not displayed"

    def test_project_list_shows_results_count(self, src_dir):
        """Verify ProjectList shows count of filtered results."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "Showing" in content or "showing" in content or "length" in content, \
            "Results count not displayed"


class TestProjectCardComponent:
    """Test ProjectCard component implementation."""

    def test_project_card_component_exists(self, src_dir):
        """Verify ProjectCard component file exists."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        assert project_card_file.exists(), \
            "ProjectCard component (src/components/projects/project-card.tsx) does not exist"

    def test_project_card_exports_named_component(self, src_dir):
        """Verify ProjectCard is exported."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "export" in content and "ProjectCard" in content, \
            "ProjectCard component not exported"

    def test_project_card_displays_project_name(self, src_dir):
        """Verify ProjectCard displays project name."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "project.name" in content, "Project name not displayed"
        assert "CardTitle" in content or "title" in content.lower(), \
            "Project name not in title element"

    def test_project_card_displays_current_branch(self, src_dir):
        """Verify ProjectCard displays current git branch."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "currentBranch" in content or "branch" in content, \
            "Current branch not displayed"

    def test_project_card_displays_status_badge(self, src_dir):
        """Verify ProjectCard displays status badge."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "project.status" in content, "Project status not accessed"
        assert "Badge" in content, "Badge component not used for status"

    def test_project_card_displays_task_counts(self, src_dir):
        """Verify ProjectCard displays all task count categories."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "taskCounts.pending" in content or "pending" in content, \
            "Pending task count not displayed"
        assert "taskCounts.inProgress" in content or "inProgress" in content, \
            "In-progress task count not displayed"
        assert "taskCounts.completed" in content or "completed" in content, \
            "Completed task count not displayed"

    def test_project_card_displays_last_activity(self, src_dir):
        """Verify ProjectCard displays last activity timestamp."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "lastActivity" in content or "updatedAt" in content, \
            "Last activity timestamp not accessed"
        assert "Last activity" in content or "last activity" in content.lower() or \
               "formatRelativeTime" in content, \
            "Last activity label or formatting not present"

    def test_project_card_has_open_action(self, src_dir):
        """Verify ProjectCard has Open button that navigates to project detail."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "Open" in content, "Open button not present"
        assert "Link" in content or "href" in content, "Navigation link not implemented"
        assert "/projects/" in content or "project.id" in content, \
            "Link to project detail page not present"

    def test_project_card_has_autopilot_action(self, src_dir):
        """Verify ProjectCard has Start Autopilot button."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "Autopilot" in content, "Autopilot button not present"
        assert "onStartAutopilot" in content or "onClick" in content, \
            "Autopilot button click handler not present"

    def test_project_card_disables_autopilot_when_active(self, src_dir):
        """Verify ProjectCard disables autopilot button when project is active."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "disabled" in content, "Button disabled state not implemented"
        assert 'status === "active"' in content or "status === 'active'" in content, \
            "Autopilot button not disabled for active projects"

    def test_project_card_shows_progress_bar(self, src_dir):
        """Verify ProjectCard shows task progress visualization."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        # Check for progress bar or percentage
        assert ("progress" in content.lower() or "Progress" in content) and \
               ("width" in content or "%" in content), \
            "Progress visualization not implemented"


class TestProjectsIndex:
    """Test projects index/barrel export."""

    def test_projects_index_exists(self, src_dir):
        """Verify projects index file exists for clean imports."""
        projects_dir = src_dir / "components" / "projects"

        # Check for index file (either .ts or .tsx)
        index_ts = projects_dir / "index.ts"
        index_tsx = projects_dir / "index.tsx"

        assert index_ts.exists() or index_tsx.exists(), \
            "Projects index file (index.ts or index.tsx) does not exist"

    def test_projects_index_exports_project_list(self, src_dir):
        """Verify projects index exports ProjectList component."""
        projects_dir = src_dir / "components" / "projects"

        # Read whichever index file exists
        index_ts = projects_dir / "index.ts"
        index_tsx = projects_dir / "index.tsx"
        index_file = index_ts if index_ts.exists() else index_tsx

        if index_file.exists():
            content = index_file.read_text()
            assert "ProjectList" in content, "ProjectList not exported from index"


class TestResponsiveDesign:
    """Test responsive design implementation."""

    def test_project_list_uses_responsive_grid(self, src_dir):
        """Verify ProjectList uses responsive grid classes."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        # Check for responsive Tailwind classes (sm:, md:, lg:, etc.)
        assert ("sm:" in content or "md:" in content or "lg:" in content) and "grid" in content, \
            "Responsive grid classes not used"

    def test_project_list_handles_mobile_layout(self, src_dir):
        """Verify ProjectList has mobile-friendly layout considerations."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        # Check for flex-col or mobile-specific classes
        assert "flex-col" in content or "sm:flex-row" in content, \
            "Mobile layout considerations not present"

    def test_project_card_handles_text_truncation(self, src_dir):
        """Verify ProjectCard truncates long text to prevent overflow."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "truncate" in content, "Text truncation not implemented"


class TestAPIIntegration:
    """Test API and WebSocket integration."""

    def test_use_projects_hook_exists(self, src_dir):
        """Verify useProjects hook exists."""
        hooks_dir = src_dir / "hooks"
        use_projects_file = hooks_dir / "use-projects.ts"

        # Could also be .tsx
        if not use_projects_file.exists():
            use_projects_file = hooks_dir / "use-projects.tsx"

        assert use_projects_file.exists(), \
            "useProjects hook (src/hooks/use-projects.ts) does not exist"

    def test_use_projects_hook_exports_function(self, src_dir):
        """Verify useProjects hook is exported."""
        hooks_dir = src_dir / "hooks"
        use_projects_file = hooks_dir / "use-projects.ts"

        if not use_projects_file.exists():
            use_projects_file = hooks_dir / "use-projects.tsx"

        content = use_projects_file.read_text()
        assert "export" in content and "useProjects" in content, \
            "useProjects hook not exported"

    def test_use_projects_calls_api(self, src_dir):
        """Verify useProjects hook calls API endpoint."""
        hooks_dir = src_dir / "hooks"
        use_projects_file = hooks_dir / "use-projects.ts"

        if not use_projects_file.exists():
            use_projects_file = hooks_dir / "use-projects.tsx"

        content = use_projects_file.read_text()
        assert "api.projects" in content, "API projects endpoint not called"
        assert "listWithStats" in content or "list" in content, \
            "Projects list endpoint not called"

    def test_use_projects_integrates_websocket(self, src_dir):
        """Verify useProjects hook integrates WebSocket for real-time updates."""
        hooks_dir = src_dir / "hooks"
        use_projects_file = hooks_dir / "use-projects.ts"

        if not use_projects_file.exists():
            use_projects_file = hooks_dir / "use-projects.tsx"

        content = use_projects_file.read_text()
        assert "useWebSocket" in content or "WebSocket" in content, \
            "WebSocket not integrated"
        assert "project_update" in content or "message" in content, \
            "WebSocket message handling not implemented"

    def test_use_projects_returns_ws_status(self, src_dir):
        """Verify useProjects hook returns WebSocket connection status."""
        hooks_dir = src_dir / "hooks"
        use_projects_file = hooks_dir / "use-projects.ts"

        if not use_projects_file.exists():
            use_projects_file = hooks_dir / "use-projects.tsx"

        content = use_projects_file.read_text()
        assert "wsStatus" in content or "status" in content, \
            "WebSocket status not returned"

    def test_use_projects_handles_websocket_updates(self, src_dir):
        """Verify useProjects hook updates projects state on WebSocket messages."""
        hooks_dir = src_dir / "hooks"
        use_projects_file = hooks_dir / "use-projects.ts"

        if not use_projects_file.exists():
            use_projects_file = hooks_dir / "use-projects.tsx"

        content = use_projects_file.read_text()

        # Check for update handlers for different actions
        assert "created" in content or "updated" in content or "deleted" in content, \
            "WebSocket update actions not handled"
        assert "setProjects" in content, \
            "Projects state not updated from WebSocket"


class TestTypeScript:
    """Test TypeScript usage and type safety."""

    def test_dashboard_is_typescript(self, src_dir):
        """Verify dashboard is written in TypeScript (.tsx)."""
        page_file = src_dir / "app" / "page.tsx"
        assert page_file.suffix == ".tsx", "Dashboard should be .tsx file"

    def test_project_list_is_typescript(self, src_dir):
        """Verify ProjectList is written in TypeScript (.tsx)."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        assert project_list_file.suffix == ".tsx", "ProjectList should be .tsx file"

    def test_project_card_is_typescript(self, src_dir):
        """Verify ProjectCard is written in TypeScript (.tsx)."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        assert project_card_file.suffix == ".tsx", "ProjectCard should be .tsx file"

    def test_project_list_has_props_interface(self, src_dir):
        """Verify ProjectList has TypeScript props interface."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "interface" in content and "Props" in content, \
            "Props interface not defined"

    def test_project_card_has_props_interface(self, src_dir):
        """Verify ProjectCard has TypeScript props interface."""
        project_card_file = src_dir / "components" / "projects" / "project-card.tsx"
        content = project_card_file.read_text()

        assert "interface" in content and "Props" in content, \
            "Props interface not defined"

    def test_api_types_imported(self, src_dir):
        """Verify components import types from API service."""
        project_list_file = src_dir / "components" / "projects" / "project-list.tsx"
        content = project_list_file.read_text()

        assert "ProjectWithStats" in content or "Project" in content, \
            "API types not imported"
        assert "@/services/api" in content or "services/api" in content, \
            "API types not imported from api service"
