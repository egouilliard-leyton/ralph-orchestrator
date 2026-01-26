# How To Use the Ralph CLI

This guide explains how to use the Ralph command-line interface to automate your development workflow with AI-assisted task execution.

## Prerequisites

- Ralph CLI installed (`pipx install ralph-orchestrator`)
- Claude CLI installed and authenticated
- Git repository initialized
- Internet connection

## Steps

### 1. Check Your Environment

Before starting, verify that all required tools are available.

1. Open your terminal in your project directory.
2. Run the scan command:
   ```bash
   ralph scan
   ```
3. You should see a list of tools with checkmarks (✓) for available tools and warnings (⚠) for optional missing tools.
4. If any required tools are missing, run:
   ```bash
   ralph scan --fix
   ```
5. Follow the installation instructions displayed.

### 2. Initialize Your Repository

Set up Ralph configuration in your project.

1. Navigate to your project's root directory.
2. Run the init command:
   ```bash
   ralph init
   ```
3. Ralph will detect your project type (Python, Node, or fullstack) and create appropriate configuration files.
4. You should see files created in the `.ralph/` directory:
   - `ralph.yml` - Main configuration
   - `prd.json` - Task list (empty)
   - `progress.txt` - Progress log
5. Review `.ralph/ralph.yml` and customize:
   - Service ports and commands
   - Quality gate commands
   - Test path patterns

### 3. Create Tasks

Define the work to be done using one of these methods.

**Option 0: Chat to Create a Document (PRD / Change Request)**

If you want a real interactive conversation (Claude Code style) to help you write a PRD or Change Request:

1. Open your terminal in your project directory.
2. Start a chat:
   ```bash
   # For an existing codebase change request (recommended)
   ralph chat --mode change-request
   
   # For a new feature PRD
   ralph chat --mode prd
   ```
3. Claude will open in interactive mode. Explain what you want to change.
4. When ready, ask Claude to **write the final document** to the output file path that Ralph printed.
5. Once the file is written, Ralph will **automatically exit the chat** and confirm the file exists.

If you want to keep chatting after the file is written, run:

```bash
ralph chat --mode change-request --no-auto-exit
```

**Option A: Manual Task Creation**

1. Open `.ralph/prd.json` in your editor.
2. Add tasks following this structure:
   ```json
   {
     "project": "Your Feature Name",
     "description": "Brief description of the work",
     "tasks": [
       {
         "id": "T-001",
         "title": "First task title",
         "description": "What to implement",
         "acceptanceCriteria": [
           "Criteria 1",
           "Criteria 2"
         ],
         "priority": 1,
         "passes": false,
         "notes": ""
       }
     ]
   }
   ```
3. Save the file.

**Option B: Autopilot Task Generation**

1. Place analysis reports in a `reports/` directory.
2. Run autopilot in dry-run mode first:
   ```bash
   ralph autopilot --dry-run
   ```
3. Review the analysis output showing the selected priority item.
4. Run autopilot to generate tasks:
   ```bash
   ralph autopilot
   ```
5. Check `.ralph/prd.json` for the generated tasks.

### 4. Run Task Execution

Execute the verified task loop.

1. Start the execution:
   ```bash
   ralph run
   ```
2. Ralph will process each task in order:
   - Implementation agent implements the changes
   - Test-writing agent adds tests
   - Quality gates verify the code
   - Review agent checks acceptance criteria
3. Watch the progress in your terminal.
4. When complete, you should see a summary showing all tasks completed.

**Common Options:**

- Run a specific task only:
  ```bash
  ralph run --task T-003
  ```
- Skip post-completion verification:
  ```bash
  ralph run --post-verify off
  ```
- Use fast gates only during development:
  ```bash
  ralph run --gates build
  ```

### 5. Verify Changes

Run verification separately after manual changes.

1. Run the verify command:
   ```bash
   ralph verify
   ```
2. This runs:
   - Quality gates (tests, linting, type checking)
   - UI tests (if configured)
   - Robot Framework tests (if configured)
3. If failures occur, run with fix mode:
   ```bash
   ralph verify --fix
   ```

### 6. Run Full Autopilot Pipeline

Execute the complete automated workflow.

1. Ensure you have reports in your configured reports directory.
2. Run autopilot with PR creation:
   ```bash
   ralph autopilot --create-pr
   ```
3. Ralph will:
   - Analyze the latest report
   - Create a feature branch
   - Generate a PRD document
   - Generate tasks
   - Execute the verified task loop
   - Create a pull request
4. You should see a PR URL when complete.

## Expected Results

After successful execution:

- All tasks marked as `passes: true` in `.ralph/prd.json`
- Quality gates passing
- Session logs available in `.ralph-session/logs/`
- Screenshots (if UI tests ran) in `.ralph-session/artifacts/screenshots/`
- Progress recorded in `.ralph/progress.txt`
- PR created (if autopilot with `--create-pr`)

## Troubleshooting

### "Configuration error" (Exit code 1)

1. Run `ralph scan` to check for issues.
2. Verify `.ralph/ralph.yml` exists and is valid YAML.
3. Check that required fields are present:
   - `version: "1"`
   - `task_source` section
   - `gates.full` with at least one gate

### "Claude CLI error" (Exit code 8)

1. Verify Claude CLI is installed: `claude --version`
2. Check authentication: `claude auth status`
3. Ensure your API key is valid.

### "Gate failure" (Exit code 4)

1. Check the gate output in `.ralph-session/logs/gates-T-XXX.log`
2. Fix the failing tests or code issues manually.
3. Re-run: `ralph run --from-task T-XXX`

### "Service startup failure" (Exit code 9)

1. Check if ports are already in use.
2. Verify service commands in `ralph.yml` are correct.
3. Try starting services manually to diagnose.

### Tasks Not Advancing

1. Check `.ralph-session/logs/impl-T-XXX.log` for agent output.
2. Verify session token is valid (no tampering).
3. Review acceptance criteria - ensure they are verifiable.

## Additional Information

### Verbose Mode

For detailed output during execution:
```bash
ralph -v run
```

### Debug Mode

For troubleshooting issues:
```bash
ralph --debug run
```

### Using Custom Configuration

Specify a different config file:
```bash
ralph -c ./custom/ralph.yml run
```

### Environment Variables

Override settings via environment:
- `RALPH_IMPL_MODEL` - Implementation agent model
- `RALPH_MAX_ITERATIONS` - Max task iterations
- `RALPH_CLAUDE_TIMEOUT` - Timeout per Claude call

### Related Features

- See [How To Install](./how-to-install.md) for installation instructions.
- See [How To Create Tasks](./how-to-create-tasks.md) for detailed task authoring guidance.
- See [How To Setup Repository](./how-to-setup-repository.md) for configuration details.
- See [How To Customize Config](./how-to-customize-config.md) for configuration customization.
- See [How To Interpret Results](./how-to-interpret-results.md) for understanding logs and failures.
- See [How To Troubleshoot](./how-to-troubleshoot.md) for common issues and solutions.
- See [CLI Contract Specification](../specs/cli-contract.md) for complete command reference.
