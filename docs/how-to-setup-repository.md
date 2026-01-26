# How To Set Up a Repository for Ralph Orchestrator

This guide explains how to configure a new or existing repository to use the Ralph orchestrator for automated development workflows.

## Prerequisites

- Ralph CLI installed (`pipx install ralph-orchestrator`)
- Git repository initialized
- Project-specific tools available (npm, uv, pytest, etc.)
- Claude CLI configured and authenticated

## Steps

### 1. Initialize Ralph in Your Repository

Open your terminal and navigate to your project root directory. Run the Ralph initialization command:

```bash
ralph init
```

This will detect your project type and create the necessary configuration files.

### 2. Review the Generated Configuration

Open the generated `.ralph/ralph.yml` file. This file contains all repo-specific settings.

Key sections to review:

- **task_source**: Where Ralph reads tasks from
- **services**: Commands to start your backend/frontend (if applicable)
- **gates**: Quality checks that must pass for task completion
- **test_paths**: Allowed paths for test file modifications

### 3. Customize Service Commands

If your project has services that need to run during verification, update the `services` section:

```yaml
services:
  backend:
    start:
      dev: "your-start-command --port {port}"
    port: 8000
    health:
      - /health
```

Replace the placeholder commands with your actual start commands.

### 4. Customize Quality Gates

Update the `gates` section to match your project's quality checks:

```yaml
gates:
  full:
    - name: test
      cmd: "npm test"
      when: package.json
      fatal: true
```

Add or remove gates based on your project requirements.

### 5. Create Your Task List

Create or edit `.ralph/prd.json` with your tasks. Each task needs:

- **id**: Unique identifier (T-001, T-002, etc.)
- **title**: Short, action-oriented title
- **description**: What to do and why
- **acceptanceCriteria**: Verifiable conditions for completion
- **priority**: Execution order (1 = first)
- **passes**: Set to `false` (Ralph will update this)

### 6. Initialize Agent Memory (Optional)

If you want to track learnings across runs, create the `AGENTS.md` file in your project root:

```bash
cp ~/.ralph/templates/AGENTS.md.template ./AGENTS.md
```

This file will accumulate patterns and conventions discovered during automation.

### 7. Add Files to Git Ignore

Add the session directory to your `.gitignore`:

```
# Ralph session (transient)
.ralph-session/
```

Keep these files in version control:
- `.ralph/ralph.yml`
- `.ralph/prd.json`
- `AGENTS.md`

### 8. Run Ralph

Execute the orchestrator with your task list:

```bash
ralph run
```

Ralph will iterate through tasks, running implementation, testing, and review phases for each.

## Expected Results

After successful setup, you should have:

- `.ralph/ralph.yml` - Configuration file customized for your project
- `.ralph/prd.json` - Task list ready for execution
- `AGENTS.md` - Agent memory file (optional but recommended)
- `.gitignore` updated to exclude `.ralph-session/`

When you run `ralph run`, you should see:
- Session initialization with unique token
- Task execution progress
- Gate verification results
- Completion summary with pass/fail status

## Troubleshooting

### Configuration not found

If you see "Configuration file not found", ensure you're in the project root and `.ralph/ralph.yml` exists.

**Solution**: Run `ralph init` to create the configuration.

### Gate command fails

If a gate command fails with "command not found":

**Solution**: Ensure the tool is installed and in your PATH. Check the `when` condition matches an existing file.

### Health check timeout

If services fail to start or health checks timeout:

**Solution**: 
1. Verify the start command works when run manually
2. Check the health endpoint URL is correct
3. Increase the `timeout` value in configuration

### Tasks not advancing

If tasks are not being marked complete:

**Solution**: Check that acceptance criteria are verifiable and that agents are outputting the correct completion signals.

## Additional Information

### Related Commands

- `ralph run --cr path/to/CR.md` - Run with a Change Request file
- `ralph verify` - Run verification only (no task execution)
- `ralph autopilot` - Run automated self-improvement mode

### Configuration Templates

Ralph provides templates for different project types:
- `ralph.yml.python` - Python-only projects
- `ralph.yml.node` - Node.js projects
- `ralph.yml.fullstack` - Python backend + Node frontend
- `ralph.yml.minimal` - Bare minimum configuration

See the [Canonical Artifacts Specification](../specs/canonical-artifacts.md) for complete schema documentation.

### Related Guides

- [How To Install](./how-to-install.md) - Installation instructions
- [How To Use the CLI](./how-to-use-cli.md) - Complete CLI command reference
- [How To Create Tasks](./how-to-create-tasks.md) - Detailed task authoring guidance
- [How To Customize Config](./how-to-customize-config.md) - Configuration customization
- [How To Interpret Results](./how-to-interpret-results.md) - Understanding logs and failures
