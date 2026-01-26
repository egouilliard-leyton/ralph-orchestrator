# How To Install Ralph Orchestrator

This guide explains how to install the Ralph orchestrator CLI tool on your computer so you can automate your development workflows.

## Prerequisites

- macOS, Linux, or Windows with WSL
- Python 3.10 or later installed
- Internet connection for downloading packages

## Steps

### 1. Verify Python Is Installed

Open your terminal and check that Python is available:

```bash
python3 --version
```

You should see a version number like "Python 3.11.4" or higher. If you see an error, install Python first from [python.org](https://python.org) or using your system's package manager.

### 2. Install pipx (Recommended Method)

pipx installs Python CLI tools in isolated environments, which prevents version conflicts with other tools.

**On macOS (using Homebrew):**

```bash
brew install pipx
pipx ensurepath
```

**On Linux (Debian/Ubuntu):**

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
```

**On Windows (WSL):**

```bash
pip install --user pipx
pipx ensurepath
```

After running `pipx ensurepath`, restart your terminal or run `source ~/.bashrc` (or `source ~/.zshrc` on macOS).

### 3. Install Ralph Orchestrator

Run the following command:

```bash
pipx install ralph-orchestrator
```

Wait for the installation to complete. You should see a success message.

### 4. Verify the Installation

Check that Ralph is available:

```bash
ralph --version
```

You should see the version number displayed.

### 5. Install the Claude CLI

Ralph requires the Claude CLI to run AI agents. Install it:

```bash
npm install -g @anthropic-ai/claude-cli
```

If you don't have npm, install Node.js first from [nodejs.org](https://nodejs.org).

### 6. Authenticate Claude CLI

Set up your Anthropic API key:

```bash
claude auth login
```

Follow the prompts to enter your API key. If you don't have one, get it from [console.anthropic.com](https://console.anthropic.com).

### 7. Run the Environment Scan

Verify everything is set up correctly:

```bash
ralph scan
```

This will check for all required and optional tools and show you what's ready and what might need attention.

## Expected Results

After successful installation, you should see:

- `ralph --version` displays the version number
- `claude --version` displays the Claude CLI version
- `ralph scan` shows green checkmarks for core tools

Example scan output:

```
═══════════════════════════════════════════════════════════
  RALPH ENVIRONMENT SCAN
═══════════════════════════════════════════════════════════

Core Tools
──────────────────────────────────────────────────────────
  ✓ claude         /opt/homebrew/bin/claude (1.2.3)
  ✓ git            /usr/bin/git (2.39.0)

═══════════════════════════════════════════════════════════
  RESULT: READY
═══════════════════════════════════════════════════════════
```

## Troubleshooting

### "command not found: ralph"

The PATH is not set up correctly.

**Solution:** 
1. Run `pipx ensurepath` again
2. Restart your terminal
3. If using zsh, add this to `~/.zshrc`: `export PATH="$HOME/.local/bin:$PATH"`

### "command not found: pipx"

pipx is not installed.

**Solution:** Follow step 2 again for your operating system.

### "Python not found" or version too old

Python 3.10+ is required.

**Solution:** 
- macOS: `brew install python@3.11`
- Linux: `sudo apt install python3.11`
- Windows: Download from [python.org](https://python.org)

### Claude CLI authentication failed

Your API key may be invalid or expired.

**Solution:**
1. Check your API key at [console.anthropic.com](https://console.anthropic.com)
2. Run `claude auth logout` then `claude auth login` again
3. Make sure you have API credits available

### Installation hangs or times out

Network issues or slow connection.

**Solution:**
1. Check your internet connection
2. Try again with a VPN if you're behind a firewall
3. Use pip directly: `pip install --user ralph-orchestrator`

## Additional Information

### Alternative Installation Methods

**From source (for development):**

```bash
git clone https://github.com/your-org/ralph-orchestrator.git
cd ralph-orchestrator
pip install -e .
```

**Using pip directly (not recommended):**

```bash
pip install ralph-orchestrator
```

Note: pip installs globally which may cause conflicts. Use pipx when possible.

### Upgrading Ralph

To update to the latest version:

```bash
pipx upgrade ralph-orchestrator
```

### Uninstalling Ralph

To remove Ralph:

```bash
pipx uninstall ralph-orchestrator
```

### Installing Optional Tools

For full functionality, you may want these optional tools:

| Tool | Purpose | Install Command |
|------|---------|-----------------|
| gh | GitHub PR creation | `brew install gh` |
| uv | Fast Python package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| agent-browser | UI testing | `npm install -g @anthropic/agent-browser` |
| robotframework | Robot Framework tests | `pip install robotframework robotframework-browser` |

Run `ralph scan --fix` to see installation instructions for any missing optional tools.

### Next Steps

After installation:
1. Navigate to your project directory
2. Run `ralph init` to set up configuration
3. See [How To Set Up a Repository](./how-to-setup-repository.md) for detailed setup instructions
