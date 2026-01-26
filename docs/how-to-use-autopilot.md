# How To Use Autopilot Mode

This guide explains how to use Ralph's autopilot mode to automatically improve your software based on analysis reports.

## Prerequisites

- Ralph CLI installed (`pipx install ralph-orchestrator`)
- A configured repository with `.ralph/ralph.yml`
- Analysis reports in a reports directory
- One of the following LLM API keys:
  - Anthropic API key (`ANTHROPIC_API_KEY`)
  - OpenAI API key (`OPENAI_API_KEY`)
  - OpenRouter API key (`OPENROUTER_API_KEY`)
- GitHub CLI (`gh`) installed and authenticated (for PR creation)

## What Autopilot Does

Autopilot is a self-improvement pipeline that:

1. **Finds** the latest report in your reports directory
2. **Analyzes** the report to identify the #1 priority item
3. **Creates** a feature branch for the work
4. **Generates** a Product Requirements Document (PRD)
5. **Converts** the PRD into granular tasks
6. **Executes** the tasks using the verified execution engine
7. **Creates** a pull request with the changes

## Steps

### 1. Set Up Your Reports Directory

Create a directory to store your analysis reports:

```bash
mkdir -p reports
```

Add report files (markdown, text, or JSON) containing information Ralph should analyze, such as:
- Daily analytics reports
- Error logs and monitoring data
- User feedback summaries
- Performance metrics

### 2. Configure Autopilot Settings

Add autopilot configuration to your `.ralph/ralph.yml`:

```yaml
autopilot:
  enabled: true
  reports_dir: "./reports"      # Where reports are stored
  branch_prefix: "ralph/"       # Prefix for created branches
  create_pr: true               # Create PR when done
  
  analysis:
    provider: "anthropic"       # LLM provider to use
    recent_days: 7              # Avoid re-picking recent fixes
  
  prd:
    mode: "autonomous"          # Don't ask questions
    output_dir: "./tasks"
  
  tasks:
    output: ".ralph/prd.json"
    min_count: 8
    max_count: 15
```

### 3. Set Your API Key

Set the environment variable for your chosen LLM provider:

```bash
# Option 1: Anthropic (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Option 2: OpenAI
export OPENAI_API_KEY="sk-..."

# Option 3: OpenRouter
export OPENROUTER_API_KEY="sk-or-..."
```

### 4. Run Autopilot

#### Preview Mode (Dry Run)

First, run autopilot in dry-run mode to see what it would do:

```bash
ralph autopilot --dry-run
```

This shows you:
- Which report was selected
- What priority item was identified
- The proposed branch name
- Acceptance criteria

#### Full Run

When ready, run the full autopilot pipeline:

```bash
ralph autopilot
```

Or specify a custom reports directory:

```bash
ralph autopilot --reports ./custom-reports
```

### 5. Review the Results

After autopilot completes, you should see:
- A new feature branch created
- A PRD in the `tasks/` directory
- Tasks in `.ralph/prd.json`
- A pull request (if enabled)

Check the PR URL displayed in the output.

## Expected Results

When autopilot runs successfully, you will see:

```
✅ Autopilot complete!
   PR: https://github.com/your-org/your-repo/pull/123
   Tasks: 10/10
```

## Troubleshooting

### No LLM Provider Configured

**Error:** "No LLM provider configured"

**Solution:** Set one of the API key environment variables:
```bash
export ANTHROPIC_API_KEY="your-key"
```

### No Reports Found

If your reports directory is empty, Ralph will now **create a bootstrap report automatically** (so autopilot can still run).

**What happens:**
- Ralph creates the reports directory (if missing)
- Ralph writes a report like `reports/ralph-auto-report-YYYY-MM-DD.md`
- Autopilot then analyzes that report

**Recommended:** Replace the bootstrap report with a real report (metrics, errors, user feedback) for best results.

### GitHub CLI Not Authenticated

**Error:** "gh: not logged in"

**Solution:** Authenticate the GitHub CLI:
```bash
gh auth login
```

### Branch Already Exists

**Info:** Ralph will checkout the existing branch and continue from where it left off.

### Task Loop Did Not Complete

If the task loop doesn't complete all tasks:
1. Check `.ralph-session/` for logs
2. Review failed tasks in `.ralph/prd.json`
3. Run `ralph run --prd-json .ralph/prd.json` to resume

## Additional Information

### Resuming an Incomplete Run

If autopilot was interrupted, you can resume:

```bash
ralph autopilot --resume
```

### Skip PR Creation

To run autopilot without creating a PR:

```bash
ralph autopilot --no-create-pr
```

### Scheduling Autopilot

You can schedule autopilot to run daily using cron or launchd. See the scheduling documentation for examples.

### Viewing Progress

Progress is logged to `.ralph/progress.txt`. You can monitor it:

```bash
tail -f .ralph/progress.txt
```

### Archived Runs

Previous autopilot runs are archived in `.ralph/autopilot/archive/`. Each archive contains:
- The `prd.json` from that run
- The `progress.txt` log
- The `analysis.json` output

## Related Features

- [How To Set Up a Repository](./how-to-setup-repository.md) - Initial Ralph configuration
- [How To Create Tasks](./how-to-create-tasks.md) - Manual task creation
- [How To Use the CLI](./how-to-use-cli.md) - All CLI commands
- [How To Schedule Autopilot](./how-to-schedule-autopilot.md) - Run autopilot on a schedule
- [How To Interpret Results](./how-to-interpret-results.md) - Understanding logs and failures
- [How To Troubleshoot](./how-to-troubleshoot.md) - Common issues and solutions
