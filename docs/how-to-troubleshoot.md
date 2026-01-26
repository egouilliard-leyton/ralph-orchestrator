# How To Troubleshoot Ralph Issues

This guide explains how to diagnose and fix common issues with Ralph, including tool prerequisites, PATH problems, and launchd scheduling issues.

## Prerequisites

- Ralph CLI installed
- Access to terminal/command line
- Basic understanding of your operating system

## Checking Your Environment

### 1. Run the Environment Scan

The first step for any issue is to run the Ralph scanner:

```bash
ralph scan
```

This checks all tools and reports their status:

```
Core Tools
──────────────────────────────────────────────────────────
  ✓ claude         /opt/homebrew/bin/claude (1.2.3)
  ✓ git            /usr/bin/git (2.39.0)
  ⚠ gh             not found (optional for PR creation)
```

- **✓ Green checkmark**: Tool is ready
- **⚠ Yellow warning**: Optional tool missing
- **✗ Red error**: Required tool missing

### 2. Get Fix Instructions

If tools are missing, get installation instructions:

```bash
ralph scan --fix
```

This shows exactly how to install each missing tool.

## Fixing Tool Prerequisites

### 3. Claude CLI Issues

**Problem:** "Claude CLI not found" or "Claude CLI error"

**Check:**

```bash
claude --version
```

**If not found:**

```bash
npm install -g @anthropic-ai/claude-cli
```

**If authentication fails:**

```bash
claude auth status
# If not authenticated:
claude auth login
```

**If API key is invalid:**

1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Create or copy your API key
3. Run `claude auth login` and paste the key

### 4. Git Issues

**Problem:** "Git not found" or "Not a git repository"

**Check:**

```bash
git --version
git status
```

**If git not installed:**

- macOS: `xcode-select --install` or `brew install git`
- Linux: `sudo apt install git`
- Windows: Download from [git-scm.com](https://git-scm.com)

**If not a git repository:**

```bash
git init
```

### 5. GitHub CLI Issues

**Problem:** "gh not found" or "gh: not logged in"

**Check:**

```bash
gh --version
gh auth status
```

**If gh not installed:**

- macOS: `brew install gh`
- Linux: See [cli.github.com](https://cli.github.com)

**If not authenticated:**

```bash
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

### 6. Python/uv Issues

**Problem:** "Python not found" or "uv not found"

**Check:**

```bash
python3 --version
uv --version
```

**If Python not installed:**

- macOS: `brew install python@3.11`
- Linux: `sudo apt install python3.11`

**If uv not installed:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your terminal.

### 7. Node.js/npm Issues

**Problem:** "npm not found" or "node not found"

**Check:**

```bash
node --version
npm --version
```

**If not installed:**

- macOS: `brew install node`
- Linux: See [nodejs.org](https://nodejs.org)
- Or use nvm: `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash`

### 8. Agent-Browser Issues

**Problem:** "agent-browser not found"

**Check:**

```bash
agent-browser --version
```

**If not installed:**

```bash
npm install -g @anthropic/agent-browser
```

**Note:** Requires Chrome or Chromium to be installed.

### 9. Robot Framework Issues

**Problem:** "robot not found" or browser library errors

**Check:**

```bash
robot --version
```

**If not installed:**

```bash
pip install robotframework robotframework-browser
rfbrowser init
```

The `rfbrowser init` command downloads required browser binaries.

## Fixing PATH Problems

### 10. Understanding PATH Issues

Many "command not found" errors are PATH issues. Your shell can't find the installed tool.

**Check your PATH:**

```bash
echo $PATH
```

This shows directories where your shell looks for commands.

### 11. Fixing PATH for pipx Tools

If `ralph` is not found after installation:

**Step 1:** Run the path setup again:

```bash
pipx ensurepath
```

**Step 2:** Restart your terminal or reload your shell config:

```bash
# For bash:
source ~/.bashrc

# For zsh (macOS default):
source ~/.zshrc
```

**Step 3:** If still not working, manually add to your shell config:

```bash
# Add this line to ~/.zshrc or ~/.bashrc:
export PATH="$HOME/.local/bin:$PATH"
```

### 12. Fixing PATH for npm Global Tools

If `claude` or other npm tools are not found:

**Check npm global directory:**

```bash
npm config get prefix
```

**Add to PATH:**

```bash
# Add to ~/.zshrc or ~/.bashrc:
export PATH="$(npm config get prefix)/bin:$PATH"
```

### 13. Fixing PATH for Homebrew (macOS)

If brew-installed tools are not found:

```bash
# For Apple Silicon Macs:
export PATH="/opt/homebrew/bin:$PATH"

# For Intel Macs:
export PATH="/usr/local/bin:$PATH"
```

Add the appropriate line to your `~/.zshrc`.

## Fixing launchd Scheduling Issues (macOS)

### 14. Understanding launchd PATH Problems

When running Ralph via launchd (scheduled tasks), the PATH is very minimal - typically just `/usr/bin:/bin:/usr/sbin:/sbin`. This means tools installed via Homebrew, npm, or pip won't be found.

**Symptom:** Ralph works in terminal but fails when scheduled.

### 15. Creating a launchd-Compatible Script

Instead of calling `ralph` directly, create a wrapper script:

**Step 1:** Create `~/bin/run-ralph.sh`:

```bash
#!/bin/bash

# Set up PATH for all tools
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$(npm config get prefix)/bin:$PATH"

# Set any required environment variables
export ANTHROPIC_API_KEY="your-key-here"

# Change to project directory
cd /path/to/your/project

# Run Ralph
ralph autopilot --reports ./reports --create-pr >> ~/ralph-autopilot.log 2>&1
```

**Step 2:** Make it executable:

```bash
chmod +x ~/bin/run-ralph.sh
```

### 16. Creating a launchd Plist File

Create `~/Library/LaunchAgents/com.ralph.autopilot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ralph.autopilot</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/YOUR_USERNAME/bin/run-ralph.sh</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/tmp/ralph-stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/ralph-stderr.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Replace `YOUR_USERNAME` with your actual username.

### 17. Loading the launchd Job

```bash
# Load the job
launchctl load ~/Library/LaunchAgents/com.ralph.autopilot.plist

# Check if it's loaded
launchctl list | grep ralph

# Unload if you need to modify
launchctl unload ~/Library/LaunchAgents/com.ralph.autopilot.plist
```

### 18. Testing launchd Jobs

**Test the wrapper script directly:**

```bash
~/bin/run-ralph.sh
```

**Test with launchd's environment:**

```bash
launchctl start com.ralph.autopilot
```

**Check the logs:**

```bash
cat /tmp/ralph-stdout.log
cat /tmp/ralph-stderr.log
cat ~/ralph-autopilot.log
```

## Common Error Messages and Solutions

### 19. "Configuration file not found"

**Cause:** Ralph can't find `.ralph/ralph.yml`

**Solution:**
1. Make sure you're in the project root directory
2. Run `ralph init` if you haven't set up the project

### 20. "Task source error"

**Cause:** Invalid or missing `.ralph/prd.json`

**Solution:**
1. Check the file exists: `ls .ralph/prd.json`
2. Validate the JSON: `cat .ralph/prd.json | python -m json.tool`
3. Run `ralph validate-tasks` to check for schema errors

### 21. "Checksum tampering detected"

**Cause:** Session files were modified unexpectedly

**Solution:**
1. Don't manually edit files in `.ralph-session/`
2. Delete the session and start fresh: `rm -rf .ralph-session/`
3. Run `ralph run` again

### 22. "Service startup failure"

**Cause:** Backend or frontend won't start

**Solution:**
1. Check if ports are in use: `lsof -i :8000`
2. Kill conflicting processes: `kill -9 <PID>`
3. Verify start commands work manually
4. Check service logs for errors

### 23. "Max iterations reached"

**Cause:** Task couldn't be completed within allowed attempts

**Solution:**
1. Check implementation logs for errors
2. Review acceptance criteria - make them more specific
3. Break the task into smaller subtasks
4. Increase `limits.max_iterations` in config (use sparingly)

## Debugging Techniques

### 24. Enable Verbose Mode

Get more detailed output:

```bash
ralph -v run
```

### 25. Enable Debug Mode

Get internal state dumps:

```bash
ralph --debug run
```

### 26. Check Claude CLI Directly

Test if Claude is working:

```bash
claude -p "Hello, respond with just 'OK'" --output-format text
```

### 27. Test Gate Commands Manually

If a gate fails, run it yourself:

```bash
# Copy the command from ralph.yml and run it:
npm test
uv run pytest
npx tsc --noEmit
```

### 28. Test Service Commands Manually

If services won't start:

```bash
# Copy from ralph.yml and run:
npm run dev
uv run uvicorn main:app --port 8000
```

## Expected Results

After troubleshooting:

- `ralph scan` shows green checkmarks for required tools
- `ralph run` executes without "command not found" errors
- Scheduled jobs (launchd) execute successfully
- Logs show clear progress through the workflow

## Additional Information

### Getting Help

If you're still stuck:

1. Run `ralph scan --json` and save the output
2. Collect logs from `.ralph-session/logs/`
3. Note the exact error message
4. Check the project's issue tracker

### Resetting Everything

For a completely fresh start:

```bash
# Remove session data
rm -rf .ralph-session/

# Optionally remove configuration (will need to re-initialize)
rm -rf .ralph/

# Re-initialize
ralph init
```

### Related Guides

- [How To Install](./how-to-install.md) - Installation guide
- [How To Interpret Results](./how-to-interpret-results.md) - Understanding output
- [How To Schedule Autopilot](./how-to-schedule-autopilot.md) - Scheduling guide
