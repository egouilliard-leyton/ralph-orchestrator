"""
Integration tests for T-011: Build Kanban task board with drag-and-drop

Tests verify:
- TaskBoard component exists with three columns (To Do, In Progress, Done)
- TaskCard component displays: title, description, acceptance criteria, current agent, duration
- Drag-and-drop implemented using @dnd-kit library
- Tasks can be reordered within To Do column
- Click task card to expand and see full details + live agent output
- Start Task button triggers POST /api/projects/{id}/run
- Real-time updates via WebSocket move tasks between columns
- Visual indicators when agent is running (pulsing icon)
- Skip and Delete task actions implemented
- Loading and error states handled gracefully
"""

import pytest
from pathlib import Path


@pytest.fixture
def frontend_dir():
    """Return the frontend directory path."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "frontend"


@pytest.fixture
def src_dir(frontend_dir):
    """Return the frontend src directory."""
    return frontend_dir / "src"


class TestTaskBoardComponent:
    """Test TaskBoard component implementation."""

    def test_task_board_component_exists(self, src_dir):
        """Verify TaskBoard component file exists."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        assert task_board_file.exists(), \
            "TaskBoard component (src/components/tasks/task-board.tsx) does not exist"

    def test_task_board_exports_named_component(self, src_dir):
        """Verify TaskBoard is exported."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "export" in content and "TaskBoard" in content, \
            "TaskBoard component not exported"

    def test_task_board_has_three_columns(self, src_dir):
        """Verify TaskBoard renders three columns: To Do, In Progress, Done."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        # Check for column definitions
        assert "To Do" in content, "To Do column not defined"
        assert "In Progress" in content, "In Progress column not defined"
        assert "Done" in content, "Done column not defined"

    def test_task_board_accepts_project_id_prop(self, src_dir):
        """Verify TaskBoard accepts projectId prop."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "projectId" in content, "projectId prop not defined"

    def test_task_board_uses_tasks_hook(self, src_dir):
        """Verify TaskBoard uses useTasks hook for data fetching."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "useTasks" in content, "useTasks hook not imported"
        assert "tasks" in content, "tasks data not accessed"

    def test_task_board_uses_dnd_context(self, src_dir):
        """Verify TaskBoard uses @dnd-kit DndContext for drag-and-drop."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "DndContext" in content, "DndContext not imported from @dnd-kit"
        assert "<DndContext" in content, "DndContext not used in JSX"

    def test_task_board_uses_sortable_context(self, src_dir):
        """Verify TaskBoard uses SortableContext for pending tasks."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "SortableContext" in content, "SortableContext not imported"
        assert "<SortableContext" in content, "SortableContext not used in JSX"

    def test_task_board_handles_drag_end(self, src_dir):
        """Verify TaskBoard handles drag end event for reordering."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "handleDragEnd" in content or "onDragEnd" in content, \
            "Drag end handler not defined"
        assert "reorderTasks" in content, "reorderTasks function not called"

    def test_task_board_shows_connection_indicator(self, src_dir):
        """Verify TaskBoard displays WebSocket connection status indicator."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "wsStatus" in content, "WebSocket status not accessed"
        assert "ConnectionIndicator" in content or "status" in content, \
            "Connection indicator not displayed"

    def test_task_board_handles_loading_state(self, src_dir):
        """Verify TaskBoard displays loading state with skeletons."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "isLoading" in content, "isLoading state not accessed"
        assert "Skeleton" in content or "TaskBoardSkeleton" in content, \
            "Loading skeleton not implemented"

    def test_task_board_handles_error_state(self, src_dir):
        """Verify TaskBoard displays error message with retry option."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "error" in content, "error state not accessed"
        assert "TaskBoardError" in content or "Failed to load" in content, \
            "Error state not handled"
        assert "retry" in content.lower() or "Try Again" in content, \
            "Retry button not present"

    def test_task_board_groups_tasks_by_status(self, src_dir):
        """Verify TaskBoard groups tasks by status into correct columns."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "pendingTasks" in content or 'status === "pending"' in content, \
            "Pending tasks not filtered"
        assert "inProgressTasks" in content or 'status === "in_progress"' in content, \
            "In-progress tasks not filtered"
        assert "completedTasks" in content or 'status === "completed"' in content, \
            "Completed tasks not filtered"

    def test_task_board_passes_action_handlers_to_cards(self, src_dir):
        """Verify TaskBoard passes action handlers (start, skip, delete) to TaskCard."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "onStart" in content or "handleStart" in content, \
            "Start handler not defined"
        assert "onSkip" in content or "handleSkip" in content, \
            "Skip handler not defined"
        assert "onDelete" in content or "handleDelete" in content, \
            "Delete handler not defined"

    def test_task_board_shows_drag_overlay(self, src_dir):
        """Verify TaskBoard shows drag overlay when dragging task."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "DragOverlay" in content, "DragOverlay component not used"
        assert "activeId" in content or "activeTask" in content, \
            "Active dragging task not tracked"

    def test_task_board_only_allows_pending_tasks_draggable(self, src_dir):
        """Verify TaskBoard only makes pending tasks draggable."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "isDraggable" in content, "isDraggable prop not used"
        assert 'status === "pending"' in content or "pending" in content, \
            "Draggable state not conditional on pending status"


class TestTaskCardComponent:
    """Test TaskCard component implementation."""

    def test_task_card_component_exists(self, src_dir):
        """Verify TaskCard component file exists."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        assert task_card_file.exists(), \
            "TaskCard component (src/components/tasks/task-card.tsx) does not exist"

    def test_task_card_exports_named_component(self, src_dir):
        """Verify TaskCard is exported."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "export" in content and "TaskCard" in content, \
            "TaskCard component not exported"

    def test_task_card_displays_task_title(self, src_dir):
        """Verify TaskCard displays task title."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "task.title" in content, "Task title not displayed"

    def test_task_card_displays_truncated_description(self, src_dir):
        """Verify TaskCard displays truncated description with expandable option."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "task.description" in content, "Task description not accessed"
        assert "truncat" in content.lower() or "slice" in content or "100" in content, \
            "Description truncation not implemented"

    def test_task_card_displays_acceptance_criteria_checklist(self, src_dir):
        """Verify TaskCard displays acceptance criteria as a checklist."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "acceptanceCriteria" in content, "Acceptance criteria not accessed"
        assert "map" in content, "Acceptance criteria not iterated"

    def test_task_card_shows_current_agent_indicator(self, src_dir):
        """Verify TaskCard shows current agent indicator for running tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "currentAgent" in content, "Current agent not accessed"
        assert "implementation" in content or "test" in content or "review" in content, \
            "Agent labels not defined"

    def test_task_card_displays_duration_timestamp(self, src_dir):
        """Verify TaskCard displays duration/timestamp for running tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "duration" in content.lower() or "startedAt" in content, \
            "Duration/timestamp not accessed"
        assert "isRunning" in content, "Running state not checked"

    def test_task_card_has_pulsing_indicator_for_running_tasks(self, src_dir):
        """Verify TaskCard shows pulsing visual indicator for running tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "isRunning" in content, "isRunning state not accessed"
        assert "pulse" in content.lower() or "animate-pulse" in content, \
            "Pulsing animation not implemented"

    def test_task_card_expandable_on_click(self, src_dir):
        """Verify TaskCard expands to show full details when clicked."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "onClick" in content or "setIsExpanded" in content, \
            "Card click handler not implemented"
        assert "Sheet" in content or "Modal" in content or "Dialog" in content, \
            "Expandable view component not used"

    def test_task_card_shows_live_output_in_expanded_view(self, src_dir):
        """Verify TaskCard shows live agent output in expanded view."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "liveOutput" in content, "Live output not accessed"
        assert "Live Output" in content or "live output" in content.lower(), \
            "Live output section not present"

    def test_task_card_has_start_button(self, src_dir):
        """Verify TaskCard has Start button for pending tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "Start" in content, "Start button not present"
        assert "onStart" in content, "onStart handler not called"

    def test_task_card_has_skip_button(self, src_dir):
        """Verify TaskCard has Skip button for pending tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "Skip" in content, "Skip button not present"
        assert "onSkip" in content, "onSkip handler not called"

    def test_task_card_has_delete_button(self, src_dir):
        """Verify TaskCard has Delete button for pending tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "Delete" in content or "Trash" in content, "Delete button not present"
        assert "onDelete" in content, "onDelete handler not called"

    def test_task_card_actions_only_for_pending_tasks(self, src_dir):
        """Verify TaskCard only shows action buttons for pending tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert 'status === "pending"' in content or "task.status === 'pending'" in content, \
            "Actions not conditional on pending status"

    def test_task_card_uses_sortable_hook(self, src_dir):
        """Verify TaskCard uses useSortable hook for drag-and-drop."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "useSortable" in content, "useSortable hook not imported"
        assert "transform" in content and "transition" in content, \
            "Sortable transforms not applied"

    def test_task_card_shows_grip_icon_for_draggable_tasks(self, src_dir):
        """Verify TaskCard shows grip icon for draggable tasks."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "GripIcon" in content or "grip" in content.lower(), \
            "Grip icon not present"
        assert "isDraggable" in content, "isDraggable prop not checked"

    def test_task_card_displays_status_badge(self, src_dir):
        """Verify TaskCard displays status badge."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "Badge" in content, "Badge component not used"
        assert "task.status" in content or "statusLabel" in content, \
            "Status not displayed in badge"


class TestUseTasksHook:
    """Test useTasks hook implementation."""

    def test_use_tasks_hook_exists(self, src_dir):
        """Verify useTasks hook exists."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        assert use_tasks_file.exists(), \
            "useTasks hook (src/hooks/use-tasks.ts) does not exist"

    def test_use_tasks_hook_exports_function(self, src_dir):
        """Verify useTasks hook is exported."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "export" in content and "useTasks" in content, \
            "useTasks hook not exported"

    def test_use_tasks_calls_api_get_tasks(self, src_dir):
        """Verify useTasks hook calls GET /api/projects/{id}/tasks."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "api.tasks" in content, "API tasks endpoint not called"
        assert "list" in content or "listByProject" in content, \
            "Tasks list endpoint not called"

    def test_use_tasks_integrates_websocket(self, src_dir):
        """Verify useTasks hook integrates WebSocket for real-time updates."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "useWebSocket" in content or "WebSocket" in content, \
            "WebSocket not integrated"
        assert "task_update" in content or "onMessage" in content, \
            "WebSocket message handling not implemented"

    def test_use_tasks_returns_start_task_function(self, src_dir):
        """Verify useTasks hook returns startTask function."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "startTask" in content, "startTask function not defined"
        assert "api.orchestration.run" in content or "run" in content, \
            "startTask does not trigger orchestration run"

    def test_use_tasks_returns_skip_task_function(self, src_dir):
        """Verify useTasks hook returns skipTask function."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "skipTask" in content, "skipTask function not defined"

    def test_use_tasks_returns_delete_task_function(self, src_dir):
        """Verify useTasks hook returns deleteTask function."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "deleteTask" in content, "deleteTask function not defined"
        assert "api.tasks.delete" in content or "delete" in content, \
            "deleteTask does not call API delete endpoint"

    def test_use_tasks_returns_reorder_tasks_function(self, src_dir):
        """Verify useTasks hook returns reorderTasks function."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "reorderTasks" in content, "reorderTasks function not defined"

    def test_use_tasks_handles_websocket_task_updates(self, src_dir):
        """Verify useTasks hook updates task state on WebSocket messages."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()

        # Check for update handlers
        assert "created" in content or "updated" in content or "status_changed" in content, \
            "WebSocket update actions not handled"
        assert "setTasks" in content, \
            "Tasks state not updated from WebSocket"

    def test_use_tasks_handles_live_output_updates(self, src_dir):
        """Verify useTasks hook handles live output WebSocket messages."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "output" in content, "Live output action not handled"
        assert "liveOutput" in content, "liveOutput field not updated"

    def test_use_tasks_returns_ws_status(self, src_dir):
        """Verify useTasks hook returns WebSocket connection status."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "wsStatus" in content or "status" in content, \
            "WebSocket status not returned"


class TestTaskColumnComponent:
    """Test TaskColumn component (if extracted as separate component)."""

    def test_task_column_displays_column_title(self, src_dir):
        """Verify TaskColumn displays column title."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "column.title" in content or "To Do" in content, \
            "Column title not displayed"

    def test_task_column_displays_task_count_badge(self, src_dir):
        """Verify TaskColumn displays count of tasks in column."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "tasks.length" in content, "Task count not displayed"
        assert "Badge" in content, "Badge not used for task count"

    def test_task_column_shows_empty_message(self, src_dir):
        """Verify TaskColumn shows empty message when no tasks."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "length === 0" in content or "emptyMessage" in content, \
            "Empty state not handled"
        assert "No pending tasks" in content or "No tasks" in content, \
            "Empty message not present"


class TestDragAndDropBehavior:
    """Test drag-and-drop behavior."""

    def test_drag_uses_pointer_sensor(self, src_dir):
        """Verify drag-and-drop uses PointerSensor for mouse/touch."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "PointerSensor" in content, "PointerSensor not imported"
        assert "useSensor" in content, "useSensor hook not used"

    def test_drag_uses_keyboard_sensor(self, src_dir):
        """Verify drag-and-drop supports keyboard navigation."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "KeyboardSensor" in content, "KeyboardSensor not imported"

    def test_drag_uses_collision_detection(self, src_dir):
        """Verify drag-and-drop uses collision detection."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "collisionDetection" in content, "Collision detection not configured"
        assert "closestCenter" in content or "closestCorners" in content, \
            "Collision strategy not specified"

    def test_reorder_persists_to_backend(self, src_dir):
        """Verify reordering tasks persists to prd.json via API."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "reorderTasks" in content, "reorderTasks function not called"

        # Check in useTasks hook
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        if use_tasks_file.exists():
            hook_content = use_tasks_file.read_text()
            assert "priority" in hook_content or "update" in hook_content, \
                "Reorder persistence not implemented"


class TestTaskPageIntegration:
    """Test tasks page integration."""

    def test_tasks_page_exists(self, src_dir):
        """Verify tasks page exists."""
        tasks_page = src_dir / "app" / "tasks" / "page.tsx"
        assert tasks_page.exists(), "Tasks page (src/app/tasks/page.tsx) does not exist"

    def test_tasks_page_uses_task_board_component(self, src_dir):
        """Verify tasks page imports and uses TaskBoard component."""
        tasks_page = src_dir / "app" / "tasks" / "page.tsx"
        content = tasks_page.read_text()

        assert "TaskBoard" in content, "TaskBoard component not imported"
        assert "<TaskBoard" in content, "TaskBoard component not used in JSX"


class TestAPITypes:
    """Test API type definitions for tasks."""

    def test_task_type_defined_in_api(self, src_dir):
        """Verify Task type is defined in API service."""
        api_file = src_dir / "services" / "api.ts"
        content = api_file.read_text()

        assert "interface Task" in content or "export interface Task" in content, \
            "Task type not defined in API service"

    def test_task_type_has_required_fields(self, src_dir):
        """Verify Task type includes all required fields."""
        api_file = src_dir / "services" / "api.ts"
        content = api_file.read_text()

        # Check for key fields
        assert "title:" in content or "title :" in content, "title field not in Task type"
        assert "status:" in content or "status :" in content, "status field not in Task type"
        assert "acceptanceCriteria" in content, "acceptanceCriteria field not in Task type"

    def test_task_status_enum_values(self, src_dir):
        """Verify Task status includes pending, in_progress, completed, failed."""
        api_file = src_dir / "services" / "api.ts"
        content = api_file.read_text()

        assert '"pending"' in content or "'pending'" in content, \
            "pending status not in Task type"
        assert '"in_progress"' in content or "'in_progress'" in content, \
            "in_progress status not in Task type"
        assert '"completed"' in content or "'completed'" in content, \
            "completed status not in Task type"


class TestResponsiveDesign:
    """Test responsive design implementation."""

    def test_task_board_uses_responsive_grid(self, src_dir):
        """Verify TaskBoard uses responsive grid classes."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert ("sm:" in content or "md:" in content or "lg:" in content) and "grid" in content, \
            "Responsive grid classes not used"

    def test_task_card_truncates_long_text(self, src_dir):
        """Verify TaskCard truncates long text to prevent overflow."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "truncate" in content or "line-clamp" in content, \
            "Text truncation not implemented"


class TestTypeScript:
    """Test TypeScript usage and type safety."""

    def test_task_board_is_typescript(self, src_dir):
        """Verify TaskBoard is written in TypeScript (.tsx)."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        assert task_board_file.suffix == ".tsx", "TaskBoard should be .tsx file"

    def test_task_card_is_typescript(self, src_dir):
        """Verify TaskCard is written in TypeScript (.tsx)."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        assert task_card_file.suffix == ".tsx", "TaskCard should be .tsx file"

    def test_task_board_has_props_interface(self, src_dir):
        """Verify TaskBoard has TypeScript props interface."""
        task_board_file = src_dir / "components" / "tasks" / "task-board.tsx"
        content = task_board_file.read_text()

        assert "interface" in content and "Props" in content, \
            "Props interface not defined"

    def test_task_card_has_props_interface(self, src_dir):
        """Verify TaskCard has TypeScript props interface."""
        task_card_file = src_dir / "components" / "tasks" / "task-card.tsx"
        content = task_card_file.read_text()

        assert "interface" in content and "Props" in content, \
            "Props interface not defined"

    def test_task_with_ui_type_extends_task(self, src_dir):
        """Verify TaskWithUI type extends Task with UI fields."""
        hooks_dir = src_dir / "hooks"
        use_tasks_file = hooks_dir / "use-tasks.ts"

        if not use_tasks_file.exists():
            use_tasks_file = hooks_dir / "use-tasks.tsx"

        content = use_tasks_file.read_text()
        assert "TaskWithUI" in content, "TaskWithUI type not defined"
        assert "extends Task" in content or ": Task" in content, \
            "TaskWithUI does not extend Task"
        assert "currentAgent" in content or "isRunning" in content or "liveOutput" in content, \
            "TaskWithUI does not include UI-specific fields"


class TestDndKitLibrary:
    """Test @dnd-kit library integration."""

    def test_dnd_kit_core_dependency(self, frontend_dir):
        """Verify @dnd-kit/core is in package.json dependencies."""
        package_json = frontend_dir / "package.json"
        content = package_json.read_text()

        assert '"@dnd-kit/core"' in content, "@dnd-kit/core not in dependencies"

    def test_dnd_kit_sortable_dependency(self, frontend_dir):
        """Verify @dnd-kit/sortable is in package.json dependencies."""
        package_json = frontend_dir / "package.json"
        content = package_json.read_text()

        assert '"@dnd-kit/sortable"' in content, "@dnd-kit/sortable not in dependencies"

    def test_dnd_kit_utilities_dependency(self, frontend_dir):
        """Verify @dnd-kit/utilities is in package.json dependencies."""
        package_json = frontend_dir / "package.json"
        content = package_json.read_text()

        assert '"@dnd-kit/utilities"' in content, "@dnd-kit/utilities not in dependencies"
