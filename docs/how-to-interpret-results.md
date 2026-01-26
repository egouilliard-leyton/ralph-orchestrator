# How To Interpret Results and Debug Failures

This guide explains how to understand the output from Ralph runs, find log files, review screenshots, and diagnose why tasks may have failed.

## Prerequisites

- Ralph CLI installed
- A completed or failed Ralph run
- Access to your project directory

## Understanding the Run Summary

### 1. Read the Final Summary

After a `ralph run` completes, you'll see a summary like this:

```
═══════════════════════════════════════════════════════════
  SUMMARY
═══════════════════════════════════════════════════════════
  Tasks: 8/10 completed
  Duration: 42m 18s
  Gates: 28 passed, 2 failed
  UI Tests: 3 passed, 1 failed
  
  Session logs: .ralph-session/logs/
  Screenshots: .ralph-session/artifacts/screenshots/
═══════════════════════════════════════════════════════════
```

**Key numbers to check:**
- **Tasks completed**: How many tasks passed vs total
- **Gates passed/failed**: Quality check results
- **UI Tests**: Browser test results
- **Duration**: How long the run took

### 2. Check the Exit Code

The exit code tells you the overall result:

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success | All done! |
| 3 | Task failed | Check task logs |
| 4 | Gate failed | Check gate logs |
| 5 | Verification failed | Check UI test logs |
| 6 | Tampering detected | Security issue - investigate |
| 7 | User abort | You cancelled the run |
| 8 | Claude CLI error | Check Claude authentication |
| 9 | Service failure | Check service logs |

## Finding and Reading Log Files

### 3. Navigate to the Session Directory

All logs from the current run are in:

```
.ralph-session/
├── session.json              # Run metadata
├── task-status.json          # Task completion status
├── logs/                     # All log files
│   ├── timeline.jsonl        # Event timeline
│   ├── impl-T-001.log        # Implementation logs
│   ├── test-T-001.log        # Test-writing logs
│   ├── review-T-001.log      # Review agent logs
│   └── gates-T-001.log       # Gate execution logs
└── artifacts/
    ├── screenshots/          # UI test screenshots
    └── robot/                # Robot Framework reports
```

### 4. View the Event Timeline

The `timeline.jsonl` file shows what happened in order:

```bash
cat .ralph-session/logs/timeline.jsonl | head -20
```

Each line is a timestamped event. Look for `"event":"task_complete"` and `"event":"task_start"` to track progress.

### 5. Read Implementation Agent Logs

To see what the AI did for a specific task:

```bash
cat .ralph-session/logs/impl-T-001.log
```

This shows:
- What files the agent read
- What changes it made
- Any errors it encountered
- The completion signal it sent

### 6. Read Test-Writing Agent Logs

To see what tests were written:

```bash
cat .ralph-session/logs/test-T-001.log
```

This shows:
- Which test files were created or modified
- What test cases were added
- Any guardrail violations (files outside allowed paths)

### 7. Read Gate Execution Logs

To see why quality checks failed:

```bash
cat .ralph-session/logs/gates-T-001.log
```

This shows:
- Each gate that ran (pytest, mypy, tsc, etc.)
- Pass/fail status for each
- Error output from failed gates

## Reviewing Screenshots and UI Test Results

### 8. View UI Test Screenshots

Screenshots are captured during UI tests, especially on failures:

```
.ralph-session/artifacts/screenshots/
├── 001-app-load.png
├── 002-dashboard.png
├── 003-login-failure.png     # Failure screenshot
└── ...
```

Open these in an image viewer to see what the browser showed at each step.

**Failure screenshots** (named with "failure") show exactly what was on screen when a test failed. Look for:
- Error messages visible on the page
- Missing elements that should be present
- Unexpected content or layout

### 9. View Robot Framework Reports

If Robot Framework tests ran, detailed HTML reports are available:

```
.ralph-session/artifacts/robot/
├── output.xml    # Raw test data
├── log.html      # Detailed step-by-step log
└── report.html   # Summary report
```

Open `report.html` in your browser for a visual summary, or `log.html` for detailed step-by-step information.

## Diagnosing Common Failures

### 10. Task Reached Max Iterations

**Symptom:** A task keeps retrying and eventually fails with "max iterations reached."

**Cause:** The implementation doesn't meet the acceptance criteria, or the criteria are not verifiable.

**What to check:**
1. Read the implementation log: `cat .ralph-session/logs/impl-T-XXX.log`
2. Read the review log: `cat .ralph-session/logs/review-T-XXX.log`
3. Look for the rejection reason in the review log

**Solution:** 
- Make acceptance criteria more specific and verifiable
- Break the task into smaller subtasks
- Provide more context in the task description

### 11. Gate Failure

**Symptom:** Exit code 4, "Gate failure" message.

**Cause:** A quality check (test, type check, lint) failed.

**What to check:**
1. Read the gate log: `cat .ralph-session/logs/gates-T-XXX.log`
2. Look for the specific error message
3. The failing command output shows exactly what went wrong

**Solution:**
- Fix the code issue identified in the error message
- Run the gate manually to see the full output: e.g., `uv run pytest -v`

### 12. UI Test Failure

**Symptom:** Exit code 5, UI verification failed.

**Cause:** Something in the UI doesn't work as expected.

**What to check:**
1. Open the failure screenshot
2. Check the agent-browser or Robot logs
3. Look for console errors in the browser logs

**Solution:**
- Review the screenshot to see what's wrong
- Check if the expected element exists with the right selector
- Verify the service is running and accessible

### 13. Service Startup Failure

**Symptom:** Exit code 9, services won't start.

**Cause:** Backend or frontend failed to start or health check failed.

**What to check:**
1. Check if ports are already in use: `lsof -i :8000`
2. Try starting the service manually with the command in `ralph.yml`
3. Check the service logs if available

**Solution:**
- Kill any processes using the required ports
- Fix the start command in your configuration
- Verify dependencies are installed

### 14. Checksum Tampering Detected

**Symptom:** Exit code 6, "tampering detected" warning.

**Cause:** The task status file was modified outside of Ralph's control.

**What to check:**
1. No one should manually edit `.ralph-session/task-status.json`
2. This is a security mechanism to prevent agents from marking tasks complete without approval

**Solution:**
- Delete `.ralph-session/` and start fresh: `rm -rf .ralph-session/`
- Don't manually edit session files

## Expected Results

After investigating a failure, you should have:

- **Clear understanding** of which step failed
- **Specific error message** from the relevant log
- **Screenshot evidence** (for UI failures)
- **Action plan** to fix the issue

## Troubleshooting

### Can't find log files

The `.ralph-session/` directory is created when you run `ralph run`.

**Solution:** Make sure you're in the correct project directory and have run Ralph at least once.

### Log files are empty

The run may have failed before reaching that phase.

**Solution:** Check earlier logs (session.json, timeline.jsonl) to see where it stopped.

### Screenshots are black or blank

The browser may have failed to load the page.

**Solution:** Check if services were running, verify the URL is correct, check for console errors.

## Additional Information

### Verbose Mode for More Details

Run with verbose flag for more output:

```bash
ralph -v run
```

### Debug Mode for Troubleshooting

Run with debug flag for internal state dumps:

```bash
ralph --debug run
```

### Cleaning Up Between Runs

To start fresh:

```bash
rm -rf .ralph-session/
ralph run
```

### Checking Task Status

View the current task status:

```bash
cat .ralph-session/task-status.json
```

Or check the main task file:

```bash
cat .ralph/prd.json
```

### Resuming a Failed Run

If a run was interrupted, you can resume:

```bash
ralph run --resume
```

Or start from a specific task:

```bash
ralph run --from-task T-003
```

### Related Guides

- [How To Use the CLI](./how-to-use-cli.md) - Complete CLI command reference
- [How To Troubleshoot](./how-to-troubleshoot.md) - Common issues and solutions
- [How To Customize Config](./how-to-customize-config.md) - Configuration options
