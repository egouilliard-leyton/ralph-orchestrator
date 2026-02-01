# T-012 Implementation Report

## Implementation - 2026-01-27T14:30:00Z

### Summary
Built workflow editor and config management UI for Ralph Orchestrator, enabling visual pipeline configuration and ralph.yml editing through a modern web interface.

### Files Created
- `frontend/src/components/workflow/WorkflowEditor.tsx` - Visual pipeline editor component
- `frontend/src/components/workflow/ConfigEditor.tsx` - Split-pane configuration editor
- `frontend/src/components/workflow/index.ts` - Module exports
- `frontend/src/components/ui/dialog.tsx` - Radix dialog component (shadcn pattern)
- `frontend/src/hooks/use-config.ts` - Config management hook with API integration

### Files Modified
- `frontend/src/app/workflow/page.tsx` - Updated to use new editor components
- `frontend/src/services/api.ts` - Added config types and API endpoints

### Features Implemented

#### WorkflowEditor Component
- Visual flowchart displaying agent pipeline (Implementation -> Test -> Gates -> Review)
- Agent nodes with type-specific colors and icons
- Draggable agent palette sidebar with agent types: implementation, test_writing, review, fix, planning
- Drop zone for adding new agents to pipeline
- Click-to-configure modal for each agent (name, model, timeout, guardrails)
- Gate nodes showing command and type (build/full)
- Add/remove gate functionality with configuration form
- Save button persists changes via API

#### ConfigEditor Component
- Split-pane layout with form editor (left) and YAML preview (right)
- Collapsible sections for:
  - Task Source (type, path)
  - Git Configuration (base_branch, remote)
  - Test Paths (guardrail patterns)
  - Services (backend/frontend configuration)
  - Limits (timeouts, iterations)
  - Autopilot settings
- Live YAML preview updates as form values change
- Validation against JSON schema with error display
- Save and Reset buttons
- Loading and error state handling

#### API Integration
- Added config types: RalphConfig, Gate, ServiceConfig, ConfigValidationResult
- New endpoints:
  - GET /api/projects/{id}/config
  - PUT /api/projects/{id}/config
  - POST /api/projects/{id}/config/validate
- useConfig hook for state management

### Acceptance Criteria Status
- [x] src/components/WorkflowEditor.tsx displays pipeline as visual flowchart
- [x] Agent nodes show: name, type, guardrails summary
- [x] Agent palette sidebar with draggable agent types
- [x] Click agent node to configure (modal with prompt, guardrails settings)
- [x] Gate nodes show command and status
- [x] Add/remove gate buttons with configuration form
- [x] Save button persists pipeline to ralph.yml via API
- [x] src/components/ConfigEditor.tsx with split-pane layout
- [x] Left pane: form editor for common settings (task_source, gates, services)
- [x] Right pane: live YAML preview updates as form changes
- [x] Validation against JSON schema before save (shows errors)
- [x] Save and Reset buttons
- [x] Both components handle loading and error states

### Technical Notes
- Used existing dnd-kit library for drag-and-drop functionality
- Created dialog component following shadcn/ui patterns
- YAML preview is generated client-side for instant feedback
- Config conversion utilities handle bidirectional mapping between workflow and API formats
- Workflow page uses tabs to switch between Pipeline Editor and Configuration views

---

## Implementation - 2026-01-27T16:20:00Z

### Summary
Addressed all feedback issues from the previous iteration of the workflow editor and config management UI components.

### Issues Fixed

#### 1. Agent guardrails synchronization between WorkflowEditor and backend
- **Problem**: Agent guardrails in WorkflowEditor were not properly synchronized with the backend's `test_paths` config
- **Solution**:
  - Added `globalTestPaths` and `onUpdateGlobalTestPaths` props to `AgentConfigModal`
  - Added "Sync with global test_paths" checkbox for test_writing agents
  - When sync is enabled, guardrails automatically reflect the project's `test_paths`
  - Changes to test_writing agent guardrails can propagate back to global `test_paths`
  - Added visual indicator (Badge) showing when guardrails are synced
  - Added `handleUpdateGlobalTestPaths` callback that updates both `testPaths` and all test_writing agents' guardrails

#### 2. ConfigUpdateRequest validation before merge
- **Problem**: The API blindly merged updates without validating the incoming structure
- **Solution**:
  - Added `@field_validator("updates")` to `ConfigUpdateRequest` in `server/api.py`
  - Validates allowed top-level keys (version, task_source, git, gates, test_paths, services, limits, autopilot, agents, ui, pr)
  - Validates field types (e.g., version must be string, test_paths must be array of strings)
  - Validates nested structures (e.g., task_source.type must be 'prd_json' or 'cr_markdown')
  - Validates agent types against allowed set (implementation, test_writing, review, fix, planning)
  - Returns 422 with clear error messages for invalid inputs

#### 3. YAML preview without library support
- **Problem**: Manual YAML generation using string concatenation didn't handle edge cases
- **Solution**:
  - Added `yaml` package to frontend dependencies
  - Replaced manual `configToYaml` function with `yaml` library's `stringify`
  - Properly handles special characters, quoting, and multiline strings
  - Configured YAML output options (indent: 2, no line wrapping, plain strings)

#### 4. Missing component/UI behavior tests
- **Problem**: No component tests existed for WorkflowEditor and ConfigEditor
- **Solution**:
  - Set up vitest with React Testing Library for frontend
  - Added `vitest.config.ts` with proper alias resolution for `@/` imports
  - Added `src/test/setup.ts` with jest-dom matchers and mocks (matchMedia, ResizeObserver)
  - Created `WorkflowEditor.test.tsx` with 15 tests covering:
    - Rendering states (loading, agents, gates, palette)
    - Agent configuration modal behavior
    - Save functionality and error handling
    - Guardrails synchronization
  - Created `ConfigEditor.test.tsx` with 20 tests covering:
    - Rendering states (loading, sections, YAML preview)
    - Form interactions (toggle buttons, inputs)
    - Save and reset functionality
    - Validation display
    - YAML library edge cases (special chars, empty arrays, nested objects)
  - Added `TestConfigUpdateRequestValidation` class to `tests/unit/test_api.py` with 15 tests

### Files Modified
- `frontend/src/components/workflow/WorkflowEditor.tsx` - Added guardrails sync, error handling
- `frontend/src/components/workflow/ConfigEditor.tsx` - Switched to yaml library
- `server/api.py` - Added ConfigUpdateRequest validation
- `frontend/package.json` - Added yaml dependency and test scripts
- `frontend/vitest.config.ts` - New file for test configuration
- `frontend/src/test/setup.ts` - New file for test setup
- `frontend/src/components/workflow/WorkflowEditor.test.tsx` - New test file
- `frontend/src/components/workflow/ConfigEditor.test.tsx` - New test file
- `tests/unit/test_api.py` - Added ConfigUpdateRequest validation tests

### Test Results
- Frontend tests: 35 passed
- Backend ConfigUpdateRequest validation tests: 15 passed

### Notes for Next Iteration
- Consider adding E2E tests with Playwright for full integration testing
- The DnD functionality is mocked in tests - may need integration tests to verify drag-and-drop works correctly
- Consider adding debounce to guardrails sync to avoid excessive re-renders
