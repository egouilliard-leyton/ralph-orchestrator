# How To Schedule Ralph Autopilot

This guide explains how to set up Ralph's autopilot mode to run automatically on a schedule, using cron (Linux) or launchd (macOS).

## Prerequisites

- Ralph CLI installed and working
- A repository configured with `.ralph/ralph.yml`
- Autopilot configured in your Ralph settings
- Claude API key available
- GitHub CLI authenticated (if using PR creation)

## Understanding Autopilot Scheduling

### What Autopilot Does

When scheduled, Ralph autopilot:

1. Finds the latest report in your reports directory
2. Analyzes it to select the top priority item
3. Creates a feature branch
4. Generates a PRD and task list
5. Executes all tasks with verification
6. Creates a pull request with the changes

### Choosing a Schedule

**Recommended schedules:**

| Frequency | Best For | Schedule |
|-----------|----------|----------|
| Daily (2 AM) | Active projects | Every night |
| Weekly | Maintenance projects | Sunday 2 AM |
| On-demand | When reports arrive | After report generation |

## Setting Up on macOS (launchd)

### 1. Create a Wrapper Script

launchd has a minimal PATH, so we need a script that sets up the environment.

Create `~/bin/ralph-autopilot.sh`:

```bash
#!/bin/bash
# Ralph Autopilot Wrapper Script
# This script sets up the environment for scheduled execution

# Exit on any error
set -e

# =============================================================
# CONFIGURATION - Edit these values
# =============================================================

# Your project directory
PROJECT_DIR="/Users/YOUR_USERNAME/path/to/your/project"

# API keys (or load from a secure location)
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Log file location
LOG_FILE="$HOME/ralph-autopilot.log"

# =============================================================
# PATH SETUP - Don't edit unless you know what you're doing
# =============================================================

# Homebrew (Apple Silicon)
export PATH="/opt/homebrew/bin:$PATH"

# Homebrew (Intel)
export PATH="/usr/local/bin:$PATH"

# pipx tools (Ralph)
export PATH="$HOME/.local/bin:$PATH"

# npm global tools (Claude CLI)
export PATH="$(npm config get prefix 2>/dev/null || echo /usr/local)/bin:$PATH"

# uv tools
export PATH="$HOME/.cargo/bin:$PATH"

# =============================================================
# EXECUTION
# =============================================================

# Log start time
echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "Autopilot run started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Change to project directory
cd "$PROJECT_DIR"

# Run autopilot with PR creation
ralph autopilot --reports ./reports --create-pr >> "$LOG_FILE" 2>&1

# Log completion
echo "Autopilot run completed: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
```

Make it executable:

```bash
chmod +x ~/bin/ralph-autopilot.sh
```

### 2. Test the Script

Before scheduling, test that it works:

```bash
~/bin/ralph-autopilot.sh
```

Check the log file for any errors:

```bash
cat ~/ralph-autopilot.log
```

### 3. Create the launchd Plist

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
        <string>/Users/YOUR_USERNAME/bin/ralph-autopilot.sh</string>
    </array>
    
    <!-- Run daily at 2:00 AM -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <!-- Log output -->
    <key>StandardOutPath</key>
    <string>/tmp/ralph-launchd-stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/ralph-launchd-stderr.log</string>
    
    <!-- Run even if computer was asleep -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
```

Replace `YOUR_USERNAME` with your macOS username.

### 4. Load the Schedule

```bash
# Load the job
launchctl load ~/Library/LaunchAgents/com.ralph.autopilot.plist

# Verify it's loaded
launchctl list | grep ralph
```

You should see `com.ralph.autopilot` in the output.

### 5. Test the Scheduled Job

Trigger it manually to test:

```bash
launchctl start com.ralph.autopilot
```

Check the logs:

```bash
cat /tmp/ralph-launchd-stdout.log
cat /tmp/ralph-launchd-stderr.log
cat ~/ralph-autopilot.log
```

### 6. Managing the Schedule

**To stop the schedule:**

```bash
launchctl unload ~/Library/LaunchAgents/com.ralph.autopilot.plist
```

**To update the schedule:**

```bash
# Unload first
launchctl unload ~/Library/LaunchAgents/com.ralph.autopilot.plist

# Edit the plist file
nano ~/Library/LaunchAgents/com.ralph.autopilot.plist

# Reload
launchctl load ~/Library/LaunchAgents/com.ralph.autopilot.plist
```

**To view scheduled jobs:**

```bash
launchctl list | grep ralph
```

## Setting Up on Linux (cron)

### 7. Create the Wrapper Script

Create `~/bin/ralph-autopilot.sh` (same as macOS, adjust paths):

```bash
#!/bin/bash
# Ralph Autopilot Wrapper Script for Linux

set -e

# Configuration
PROJECT_DIR="/home/YOUR_USERNAME/path/to/your/project"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
LOG_FILE="$HOME/ralph-autopilot.log"

# PATH setup for common tool locations
export PATH="/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# npm global path
if command -v npm &> /dev/null; then
    export PATH="$(npm config get prefix)/bin:$PATH"
fi

# Log and run
echo "" >> "$LOG_FILE"
echo "======================================== " >> "$LOG_FILE"
echo "Autopilot run started: $(date)" >> "$LOG_FILE"
cd "$PROJECT_DIR"
ralph autopilot --reports ./reports --create-pr >> "$LOG_FILE" 2>&1
echo "Autopilot run completed: $(date)" >> "$LOG_FILE"
```

Make executable:

```bash
chmod +x ~/bin/ralph-autopilot.sh
```

### 8. Add to Crontab

Open the cron editor:

```bash
crontab -e
```

Add a line for daily execution at 2 AM:

```cron
# Ralph Autopilot - runs daily at 2:00 AM
0 2 * * * /home/YOUR_USERNAME/bin/ralph-autopilot.sh
```

**Common cron schedules:**

| Schedule | Cron Expression |
|----------|-----------------|
| Daily at 2 AM | `0 2 * * *` |
| Weekly Sunday 2 AM | `0 2 * * 0` |
| Every 6 hours | `0 */6 * * *` |
| Weekdays at 2 AM | `0 2 * * 1-5` |

### 9. Verify the Cron Job

List your cron jobs:

```bash
crontab -l
```

Check cron logs (location varies by system):

```bash
# Ubuntu/Debian
grep CRON /var/log/syslog

# CentOS/RHEL
cat /var/log/cron
```

## Handling API Keys Securely

### 10. Using Environment Files

Instead of hardcoding keys, use an environment file:

Create `~/.ralph-env`:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."
```

Secure the file:

```bash
chmod 600 ~/.ralph-env
```

Update your wrapper script to source it:

```bash
#!/bin/bash
# Load environment
source ~/.ralph-env

# Rest of script...
```

### 11. Using macOS Keychain (Advanced)

For better security on macOS, store keys in Keychain:

```bash
# Store the key
security add-generic-password -a "$USER" -s "anthropic-api-key" -w "your-key-here"

# Retrieve in script
export ANTHROPIC_API_KEY=$(security find-generic-password -a "$USER" -s "anthropic-api-key" -w)
```

## Monitoring Scheduled Runs

### 12. Checking Run Status

View the latest log entries:

```bash
tail -100 ~/ralph-autopilot.log
```

Watch in real-time during a run:

```bash
tail -f ~/ralph-autopilot.log
```

### 13. Setting Up Notifications (Optional)

Add to the end of your wrapper script:

**macOS notification:**

```bash
# At end of script
if [ $? -eq 0 ]; then
    osascript -e 'display notification "Autopilot completed successfully" with title "Ralph"'
else
    osascript -e 'display notification "Autopilot failed - check logs" with title "Ralph"'
fi
```

**Email notification (Linux):**

```bash
# At end of script
if [ $? -eq 0 ]; then
    echo "Ralph autopilot completed successfully" | mail -s "Ralph: Success" you@example.com
else
    tail -50 "$LOG_FILE" | mail -s "Ralph: Failed" you@example.com
fi
```

### 14. Creating a Status Dashboard

Create a simple status script `~/bin/ralph-status.sh`:

```bash
#!/bin/bash

echo "=== Ralph Autopilot Status ==="
echo ""

# Last run time
echo "Last run:"
grep "Autopilot run started" ~/ralph-autopilot.log | tail -1

# Last completion
echo ""
echo "Last completion:"
grep "Autopilot run completed" ~/ralph-autopilot.log | tail -1

# Recent errors
echo ""
echo "Recent errors (if any):"
grep -i "error\|failed\|exception" ~/ralph-autopilot.log | tail -5

# Schedule status (macOS)
echo ""
echo "Schedule status:"
launchctl list | grep ralph || echo "Not scheduled"
```

## Expected Results

After setting up scheduling:

- The wrapper script runs without errors when tested manually
- The scheduled job appears in `launchctl list` (macOS) or `crontab -l` (Linux)
- Log files show successful runs at scheduled times
- PRs appear in your repository after scheduled runs

## Troubleshooting

### Job doesn't run at scheduled time

**macOS:**
1. Check if the plist is loaded: `launchctl list | grep ralph`
2. Look for errors: `cat /tmp/ralph-launchd-stderr.log`
3. Ensure your Mac is not sleeping at the scheduled time

**Linux:**
1. Check cron daemon is running: `systemctl status cron`
2. Check cron logs for your job
3. Verify the script path is correct

### "Command not found" errors

PATH is not set up correctly in the wrapper script.

**Solution:** Add all necessary paths to the script (see step 1/7 above).

### Authentication failures

API keys not available in scheduled environment.

**Solution:** 
1. Ensure keys are exported in the wrapper script
2. Check file permissions on `.ralph-env`
3. Verify keys are still valid

### Job runs but does nothing

The script may exit early due to errors.

**Solution:**
1. Check all log files for errors
2. Test the script manually: `~/bin/ralph-autopilot.sh`
3. Ensure the project directory exists

## Additional Information

### Multiple Projects

Create separate wrapper scripts and plist files for each project:

- `ralph-autopilot-project1.sh`
- `com.ralph.autopilot.project1.plist`

### Conditional Running

Only run if reports exist:

```bash
# Add to wrapper script
REPORTS_DIR="$PROJECT_DIR/reports"
if [ -z "$(ls -A $REPORTS_DIR 2>/dev/null)" ]; then
    echo "No reports found, skipping" >> "$LOG_FILE"
    exit 0
fi
```

### Cleanup Old Logs

Add log rotation to your wrapper:

```bash
# Keep last 1000 lines
if [ -f "$LOG_FILE" ]; then
    tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp"
    mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
```

### Related Guides

- [How To Use Autopilot](./how-to-use-autopilot.md) - Autopilot configuration
- [How To Troubleshoot](./how-to-troubleshoot.md) - Common issues
- [How To Interpret Results](./how-to-interpret-results.md) - Understanding output
