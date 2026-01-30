# Manual Testing Checklist

This document provides a comprehensive manual testing checklist for Ralph Orchestrator's web UI and CLI functionality.

## Pre-Testing Setup

- [ ] Python 3.10+ installed
- [ ] Node.js 18+ installed (for frontend)
- [ ] Git installed and configured
- [ ] Claude Code CLI installed and authenticated
- [ ] Ralph installed: `pip install -e .`

## CLI Functionality Tests

### Initialization Tests

- [ ] `ralph init` creates `.ralph/` directory
- [ ] `ralph init` creates `ralph.yml` template
- [ ] `ralph init` creates `prd.json` template
- [ ] `ralph init` skips existing files unless `--force`
- [ ] `ralph scan` detects Claude CLI installation
- [ ] `ralph scan` validates configuration

### Task Execution Tests

- [ ] `ralph run --dry-run` lists pending tasks
- [ ] `ralph run --dry-run` shows task count
- [ ] `ralph run` executes implementation agent
- [ ] `ralph run` executes test-writing agent
- [ ] `ralph run` executes quality gates
- [ ] `ralph run` executes review agent
- [ ] Task completion signal detected correctly
- [ ] Invalid session token rejected
- [ ] Gate failures trigger fix loops
- [ ] `--task-id` filters to specific task
- [ ] `--from-task-id` starts from specified task

### Flow Command Tests

- [ ] `ralph flow change` opens Claude session
- [ ] `ralph flow new` initializes and opens session
- [ ] Tasks generated from chat session
- [ ] Tasks validated against schema
- [ ] Approval prompt works correctly
- [ ] `--auto-approve` skips approval

### Autopilot Tests

- [ ] `ralph autopilot --dry-run` analyzes reports
- [ ] `ralph autopilot` executes full pipeline
- [ ] PRD generated from analysis
- [ ] Branch created with correct name
- [ ] PR opened on completion

### Parallel Execution Tests

- [ ] `ralph run --parallel` enables parallel mode
- [ ] `ralph run --parallel --max-parallel 5` limits concurrent groups
- [ ] Tasks partitioned by file overlap analysis
- [ ] Non-overlapping tasks run concurrently
- [ ] Overlapping tasks run in separate groups
- [ ] Group start/complete events logged
- [ ] Falls back to sequential on low confidence
- [ ] `--dry-run --parallel` shows partition plan

### Enhanced Subtask Tests

- [ ] Checkpoint mode: single agent handles all subtasks
- [ ] `<subtask-complete>` signal detected and validated
- [ ] Subtask progress tracked in session
- [ ] Independent subtask (`independent: true`) gets own verification loop
- [ ] `<promote-subtask>` signal creates new task
- [ ] Promoted task placed after parent in priority
- [ ] Original subtask marked with `promotedTo`
- [ ] Parent task completes when all subtasks pass

## Web UI Tests

### Starting the Server

- [ ] `ralph serve` starts on port 8000
- [ ] `ralph serve --port 9000` uses custom port
- [ ] Health endpoint responds: `GET /api/health`
- [ ] CORS allows localhost:3001

### Dashboard Tests

- [ ] Dashboard loads at `/`
- [ ] Projects listed with correct counts
- [ ] Aggregate statistics displayed
- [ ] Connection status indicator works
- [ ] Navigate to project details

### Project Management Tests

- [ ] Projects page shows all discovered projects
- [ ] Project card shows task counts (pending/progress/completed)
- [ ] Project card shows current branch
- [ ] Project card shows status badge
- [ ] "Open" link navigates to project detail
- [ ] "Start Autopilot" button triggers execution
- [ ] Disabled when already running

### Task Board Tests

- [ ] Task board shows three columns (To Do, In Progress, Done)
- [ ] Tasks appear in correct columns based on status
- [ ] Task cards show title and description
- [ ] Task cards show acceptance criteria count
- [ ] Click card opens detail sheet
- [ ] Detail sheet shows full acceptance criteria list
- [ ] "Start" button begins task execution
- [ ] "Skip" button skips task
- [ ] "Delete" button removes task

### Task Execution Monitoring

- [ ] Task card shows "Running" indicator when executing
- [ ] Current agent phase displayed (Implementing/Testing/Reviewing)
- [ ] Duration timer updates in real-time
- [ ] Iteration count updates
- [ ] Live output shown in detail sheet
- [ ] Gate results displayed
- [ ] Task moves to Done on completion

### Real-Time Updates (WebSocket)

- [ ] Connection established on page load
- [ ] Connection status indicator accurate
- [ ] Task status updates without refresh
- [ ] Agent phase changes reflected
- [ ] Gate results appear in real-time
- [ ] Reconnects after disconnect
- [ ] Multiple browser tabs receive updates

### Log Viewer Tests

- [ ] Log files listed with names and sizes
- [ ] Click file shows content
- [ ] Content scrolls properly
- [ ] Large files paginate
- [ ] Search/filter functionality works
- [ ] Log levels highlighted (info/warn/error)

### Timeline Tests

- [ ] Timeline shows chronological events
- [ ] Event types have distinct icons
- [ ] Timestamps formatted correctly
- [ ] Event details expandable
- [ ] Filter by event type works
- [ ] Pagination works for long timelines

### Git Panel Tests

- [ ] Current branch displayed
- [ ] Branch list shows all branches
- [ ] Ahead/behind indicators accurate
- [ ] Switch branch functionality works
- [ ] Uncommitted changes warning appears
- [ ] Create branch dialog opens
- [ ] Branch name validation works
- [ ] Create branch from task auto-generates name

### Pull Request Creation Tests

- [ ] Create PR dialog opens
- [ ] Title field required
- [ ] Body field accepts markdown
- [ ] Base branch selection works
- [ ] Draft PR checkbox works
- [ ] Labels can be added
- [ ] Success shows PR URL link
- [ ] Error messages displayed clearly

### Configuration Editor Tests

- [ ] Current config displayed
- [ ] Git settings editable (base_branch, remote)
- [ ] Build gates listed
- [ ] Full gates listed
- [ ] Add new gate works
- [ ] Remove gate works
- [ ] Reorder gates with drag-and-drop
- [ ] Test paths editable
- [ ] Limits editable (max_iterations, timeout)
- [ ] Save validates configuration
- [ ] Save writes to ralph.yml
- [ ] YAML preview toggle works
- [ ] Unsaved changes warning

## API Endpoint Tests

### Project Endpoints

- [ ] `GET /api/projects` returns project list
- [ ] `GET /api/projects?refresh=true` forces rescan
- [ ] `GET /api/projects/{id}` returns specific project
- [ ] 404 returned for unknown project

### Task Endpoints

- [ ] `GET /api/projects/{id}/tasks` returns task list
- [ ] Task counts accurate (total/completed/pending)
- [ ] 400 returned for malformed prd.json
- [ ] `POST /api/projects/{id}/run` starts execution
- [ ] `POST /api/projects/{id}/run` with dry_run returns preview
- [ ] `POST /api/projects/{id}/stop` cancels execution
- [ ] 409 returned when already running

### Configuration Endpoints

- [ ] `GET /api/projects/{id}/config` returns config
- [ ] `PUT /api/projects/{id}/config` updates config
- [ ] Invalid config returns validation errors
- [ ] Deep merge preserves unmodified fields

### Git Endpoints

- [ ] `GET /api/projects/{id}/branches` lists branches
- [ ] `POST /api/projects/{id}/branches` creates branch
- [ ] Branch name validation works
- [ ] `POST /api/projects/{id}/pr` creates PR
- [ ] GitHub and GitLab both supported

### Log Endpoints

- [ ] `GET /api/projects/{id}/logs` lists log files
- [ ] `GET /api/projects/{id}/logs/{name}` returns content
- [ ] 404 for missing log files

### Timeline Endpoint

- [ ] `GET /api/projects/{id}/timeline` returns events
- [ ] Pagination works (limit/offset)
- [ ] Events in chronological order

## Security Tests

- [ ] Session token verified for completion signals
- [ ] Checksum tamper detection works
- [ ] Guardrail restricts test-agent file access
- [ ] No credentials exposed in logs
- [ ] CORS properly configured

## Performance Tests

- [ ] Large project list loads quickly
- [ ] Long log files paginate properly
- [ ] Many timeline events handled
- [ ] WebSocket doesn't memory leak
- [ ] Concurrent requests handled

## Error Handling Tests

- [ ] Network errors show user-friendly message
- [ ] API errors display detail
- [ ] Invalid JSON in prd.json handled
- [ ] Missing config handled gracefully
- [ ] WebSocket reconnection works

## Browser Compatibility

- [ ] Chrome latest - all features work
- [ ] Firefox latest - all features work
- [ ] Safari latest - all features work

## Accessibility Tests

- [ ] Keyboard navigation works
- [ ] Screen reader compatible
- [ ] Color contrast sufficient
- [ ] Focus indicators visible

---

## Test Results Summary

| Category | Total | Passed | Failed | Notes |
|----------|-------|--------|--------|-------|
| CLI | | | | |
| Dashboard | | | | |
| Task Board | | | | |
| Git Panel | | | | |
| Config Editor | | | | |
| API Endpoints | | | | |
| WebSocket | | | | |
| Security | | | | |

**Tested By:** _________________

**Date:** _________________

**Version:** _________________

**Notes:**

---

## Known Issues

List any issues discovered during testing:

1. Issue description
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Priority (High/Medium/Low)

---

## Sign-Off

- [ ] All critical tests pass
- [ ] No regressions in CLI functionality
- [ ] All acceptance criteria for T-015 met
- [ ] Test coverage >80% for new code

**Approved By:** _________________

**Date:** _________________
