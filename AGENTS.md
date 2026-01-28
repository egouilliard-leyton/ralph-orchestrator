# AGENTS.md

> This file captures codebase patterns and conventions discovered during automated development.
> AI agents read this file to understand project-specific context.
> Updates are made by automation runs - manual edits may be overwritten.

## Codebase Patterns

### Architecture

The codebase follows a modular architecture with these key directories:

- **`ralph_orchestrator/`** - Core orchestrator modules (cli, run, autopilot, config, etc.)
- **`ralph_orchestrator/agents/`** - Agent roles, prompts, and signal validation
- **`ralph_orchestrator/research/`** - Research sub-agents for PRD enhancement
  - `coordinator.py` - Orchestrates research phases
  - `backend.py` - Scans Python/API code patterns
  - `frontend.py` - Scans React/Vue/CSS components
  - `web.py` - Web search for docs/best practices
- **`ralph_orchestrator/skills/`** - Skill routing for specialized Claude plugins
  - `router.py` - Detects and applies skills for tasks
  - `defaults.py` - Default skill mappings (frontend-design, docx, xlsx, etc.)

### Naming Conventions

<!-- Discovered naming conventions will be added here -->

### Testing Patterns

<!-- Discovered testing patterns will be added here -->

### Common Gotchas

<!-- Discovered gotchas and pitfalls will be added here -->

---

## Technology Stack

<!-- Auto-detected during ralph init -->

- **Backend**: 
- **Frontend**: 
- **Database**: 
- **Testing**: 

---

## File Organization

```
<!-- Directory structure summary will be added here -->
```

---

## Recent Learnings

<!-- Learnings from automation runs will be appended below -->

---

*Last updated: [timestamp] by Ralph orchestrator*
