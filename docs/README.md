# Ralph Orchestrator Documentation

Welcome to the Ralph Orchestrator documentation. This guide will help you install, configure, and use Ralph to automate your development workflows.

## Getting Started

If you're new to Ralph, start here:

1. **[How To Install](./how-to-install.md)** - Install Ralph and its prerequisites
2. **[How To Set Up a Repository](./how-to-setup-repository.md)** - Initialize Ralph in your project
3. **[How To Use the CLI](./how-to-use-cli.md)** - Learn the basic commands

## How-To Guides

Step-by-step guides for common tasks:

### Setup and Configuration

| Guide | Description |
|-------|-------------|
| [How To Install](./how-to-install.md) | Install Ralph CLI and prerequisites |
| [How To Set Up a Repository](./how-to-setup-repository.md) | Initialize Ralph in your project |
| [How To Customize Config](./how-to-customize-config.md) | Customize ports, commands, and gates |

### Working with Tasks

| Guide | Description |
|-------|-------------|
| [How To Use Flow](./how-to-use-flow.md) | One-command flows: chat → tasks → execute |
| [How To Create Tasks](./how-to-create-tasks.md) | Create and structure task lists |
| [How To Use the CLI](./how-to-use-cli.md) | Run tasks and manage workflows |

### Autopilot and Automation

| Guide | Description |
|-------|-------------|
| [How To Use Autopilot](./how-to-use-autopilot.md) | Set up automated self-improvement with research |
| [How To Schedule Autopilot](./how-to-schedule-autopilot.md) | Run autopilot on a schedule (cron/launchd) |

### Advanced Features

| Feature | Description |
|---------|-------------|
| Research Sub-agents | Backend, frontend, and web researchers gather context before PRD generation |
| Skill Routing | Specialized Claude plugins auto-applied based on task content |
| UI Test Flags | Control smoke tests and Robot Framework with `--with-smoke`, `--no-smoke`, `--with-robot`, `--no-robot` |

### Troubleshooting

| Guide | Description |
|-------|-------------|
| [How To Interpret Results](./how-to-interpret-results.md) | Understand logs, screenshots, and failures |
| [How To Troubleshoot](./how-to-troubleshoot.md) | Fix common issues and PATH problems |

## Reference Documentation

Detailed technical specifications:

| Document | Description |
|----------|-------------|
| [CLI Contract](../specs/cli-contract.md) | Complete CLI command reference |
| [Canonical Artifacts](../specs/canonical-artifacts.md) | File formats and schemas |
| [Design Decisions](../specs/design-decisions.md) | Rationale behind key decisions |
| [Testing Strategy](../specs/testing-strategy.md) | How to test the orchestrator |

## Quick References

Condensed reference cards:

| Document | Description |
|----------|-------------|
| [Artifacts Quick Reference](./artifacts-quick-reference.md) | Quick lookup for file locations |
| [Testing Quick Reference](./testing-quick-reference.md) | Quick lookup for testing commands |

## Migration Guides

For users coming from other systems:

| Document | Description |
|----------|-------------|
| [MongoDB-RAG-Agent Migration](./migration-playbook-mongodb-rag-agent.md) | Migrate from the original ralph-verified.sh |

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture Diagram](./architecture-diagram.md) | System architecture overview |

## Additional Resources

- **Templates**: See `templates/.ralph/` for configuration templates
- **Examples**: See `examples/` for sample task files and CR documents
- **Schemas**: See `schemas/` for JSON Schema files for validation

## Getting Help

If you're stuck:

1. Run `ralph scan` to check your environment
2. Check the [Troubleshooting Guide](./how-to-troubleshoot.md)
3. Review the [Interpret Results Guide](./how-to-interpret-results.md) for log analysis
4. Check the project's issue tracker for known issues
