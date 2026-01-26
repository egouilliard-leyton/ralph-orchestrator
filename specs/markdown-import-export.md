# Markdown Import/Export Specification

**Version:** 1.0  
**Date:** 2026-01-25  
**Status:** Canonical Reference

This document specifies how Ralph imports tasks from markdown files (CR/PRD) and exports `prd.json` tasks back to markdown format.

> **Related Documents:**
> - [Canonical Artifacts](./canonical-artifacts.md) - Primary artifact specification
> - [prd.schema.json](../schemas/prd.schema.json) - Canonical task schema
> - [cr-markdown.schema.json](../schemas/cr-markdown.schema.json) - CR markdown schema

---

## Table of Contents

1. [Overview](#1-overview)
2. [Markdown Task Block Format](#2-markdown-task-block-format)
3. [Import: Markdown to prd.json](#3-import-markdown-to-prdjson)
4. [Export: prd.json to Markdown](#4-export-prdjson-to-markdown)
5. [CLI Commands](#5-cli-commands)
6. [Examples](#6-examples)
7. [Error Handling](#7-error-handling)

---

## 1. Overview

Ralph supports two task source formats:

| Format | File | Primary Use | Description |
|--------|------|-------------|-------------|
| **prd.json** | `.ralph/prd.json` | **Recommended** | Machine-readable JSON, Compound-compatible |
| **CR Markdown** | `changes/CR-*.md` | **Legacy/Compat** | Human-readable markdown with embedded JSON |

### Why Support Both?

- **prd.json** is the canonical format for execution—stable IDs, machine-parseable, no regex heuristics
- **CR Markdown** is valuable for human authoring, code review visibility, and legacy workflows
- Import/export bridges these formats without losing fidelity

### Design Principles

1. **prd.json is the source of truth** during execution
2. **Markdown is a view/authoring layer** that can be imported/exported
3. **Import is lossless** for required fields; metadata may be inferred
4. **Export preserves task structure** with human-readable formatting

---

## 2. Markdown Task Block Format

### 2.1 Location in Markdown

Tasks are embedded in a markdown file within a `## Task List` section as a fenced JSON code block:

```markdown
## Task List

```json
[
  {
    "id": "CR-MVP-1",
    "category": "setup",
    "description": "Create reference data collections",
    "steps": [
      "Create TaxOffice model",
      "Create Region model",
      "Add collection constants"
    ],
    "passes": false
  }
]
```​
```

### 2.2 CR Markdown Task Schema

Each task in the markdown JSON block follows this schema:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Task identifier (flexible format) |
| `category` | string | Yes | Task category (setup, feature, frontend, etc.) |
| `description` | string | Yes | What to do |
| `steps` | string[] | Yes | Steps to complete (maps to acceptanceCriteria) |
| `passes` | boolean | Yes | Completion status |

#### Allowed Categories

- `setup` - Initial setup and configuration
- `feature` - Core feature implementation
- `frontend` - UI/frontend work
- `backend` - Backend/API work
- `testing` - Test creation
- `documentation` - Docs and comments
- `integration` - Integration work
- `fix` - Bug fixes
- `refactor` - Code refactoring
- `infrastructure` - DevOps/infra work

### 2.3 Extracting Metadata from Markdown

The importer extracts project metadata from markdown frontmatter or headers:

```markdown
# CR: MVP Completion - Full Feature Implementation

**Created:** 2026-01-23
**Status:** Draft
**Scope:** Large
**Priority:** P1-High

## Summary

Complete implementation of all MVP features...
```

**Extraction rules:**

| prd.json field | Extracted from |
|----------------|----------------|
| `project` | First `# ` heading (after "CR: " prefix if present) |
| `description` | `## Summary` section first paragraph |
| `branchName` | Inferred from CR filename: `CR-MVP-COMPLETION.md` → `ralph/mvp-completion` |

---

## 3. Import: Markdown to prd.json

### 3.1 Transformation Rules

Each CR task is transformed to a prd.json task:

| CR Field | prd.json Field | Transformation |
|----------|----------------|----------------|
| `id` | `id` | Normalized to `T-NNN` format |
| `description` | `title` | Truncated to 100 chars if needed |
| `description` | `description` | Full description preserved |
| `steps` | `acceptanceCriteria` | Direct mapping |
| `category` | (metadata) | Stored in notes or used for priority grouping |
| `passes` | `passes` | Direct mapping |
| - | `priority` | **Inferred** from order + category |
| - | `notes` | Empty string (or category metadata) |

### 3.2 ID Normalization

CR IDs are converted to the canonical `T-NNN` format:

| Input ID | Output ID |
|----------|-----------|
| `CR-MVP-1` | `T-001` |
| `CR-MVP-25` | `T-025` |
| `TASK-003` | `T-003` |
| `setup-1` | `T-001` |
| `T-001` | `T-001` (unchanged) |

**Algorithm:**

1. Extract numeric suffix from ID
2. Zero-pad to 3 digits
3. Prefix with `T-`
4. If no numeric suffix, assign sequential number

### 3.3 Priority Assignment

Priorities are assigned based on:

1. **Original order** in markdown (primary)
2. **Category grouping** (secondary, optional)

Category priority order (when grouping enabled):

| Category | Priority Range |
|----------|----------------|
| `setup` | 1-10 |
| `backend` | 11-30 |
| `feature` | 31-60 |
| `frontend` | 61-80 |
| `integration` | 81-90 |
| `testing` | 91-95 |
| `documentation` | 96-99 |

Default behavior: preserve original order as priority (1, 2, 3, ...).

### 3.4 Import Algorithm

```
1. Read markdown file
2. Find "## Task List" section
3. Extract JSON code block content
4. Parse JSON array
5. Validate against cr-markdown.schema.json
6. Extract metadata from markdown headers
7. Transform each task:
   a. Normalize ID
   b. Map description → title + description
   c. Map steps → acceptanceCriteria
   d. Assign priority
   e. Initialize notes
8. Create prd.json structure
9. Validate against prd.schema.json
10. Write to .ralph/prd.json
```

---

## 4. Export: prd.json to Markdown

### 4.1 Export Format

Exporting produces a standalone markdown document or updates an existing CR file.

**Standalone export format:**

```markdown
# PRD: {project}

**Generated:** {timestamp}
**Branch:** {branchName}
**Status:** In Progress

## Summary

{description}

## Task List

```json
[
  {
    "id": "T-001",
    "title": "Task title",
    "description": "Full description",
    "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
    "priority": 1,
    "passes": false,
    "notes": ""
  }
]
```​

## Progress

- [x] T-001: Task title (completed)
- [ ] T-002: Another task (pending)

---

*Exported by Ralph orchestrator*
```

### 4.2 Export to Existing CR

When exporting to update an existing CR file:

1. Locate existing `## Task List` section
2. Replace JSON code block content only
3. Preserve all other markdown content
4. Update `## Progress` section if present

### 4.3 CR Format Export (Compatibility)

For export to legacy CR format:

| prd.json Field | CR Field | Transformation |
|----------------|----------|----------------|
| `id` | `id` | Keep as-is or convert to CR-XXX-N format |
| `title` | `description` | Use title as description |
| `acceptanceCriteria` | `steps` | Direct mapping |
| `priority` | (ordering) | Sort tasks by priority |
| `passes` | `passes` | Direct mapping |
| `notes` | - | Discarded (not in CR format) |
| `subtasks` | - | Flattened or discarded |

**Category inference:**

| Priority Range | Inferred Category |
|----------------|-------------------|
| 1-10 | `setup` |
| 11-30 | `backend` |
| 31-60 | `feature` |
| 61-80 | `frontend` |
| 81-90 | `integration` |
| 91-95 | `testing` |
| 96-99 | `documentation` |

---

## 5. CLI Commands

### 5.1 Import Command

```bash
# Import from CR markdown to prd.json
ralph import --cr changes/CR-MVP-COMPLETION.md

# Import with category-based priority grouping
ralph import --cr changes/CR-MVP-COMPLETION.md --group-by-category

# Import to custom output path
ralph import --cr changes/CR-MVP.md --output .ralph/tasks/mvp.json

# Dry run (validate and show transformed output)
ralph import --cr changes/CR-MVP.md --dry-run
```

**Options:**

| Flag | Description |
|------|-------------|
| `--cr <path>` | Path to CR markdown file |
| `--output <path>` | Output path (default: `.ralph/prd.json`) |
| `--group-by-category` | Group priorities by task category |
| `--dry-run` | Validate and preview without writing |
| `--preserve-ids` | Keep original IDs without normalization |

### 5.2 Export Command

```bash
# Export prd.json to standalone markdown
ralph export --format markdown --output tasks/prd-export.md

# Export to update existing CR file
ralph export --format cr --update changes/CR-MVP-COMPLETION.md

# Export specific fields only
ralph export --format json --fields id,title,passes
```

**Options:**

| Flag | Description |
|------|-------------|
| `--format <type>` | Output format: `markdown`, `cr`, `json` |
| `--output <path>` | Output file path |
| `--update <path>` | Update existing markdown file in-place |
| `--fields <list>` | Comma-separated fields to include |
| `--include-completed` | Include completed tasks (default: all) |

### 5.3 Validate Command

```bash
# Validate CR markdown format
ralph validate --cr changes/CR-MVP.md

# Validate prd.json
ralph validate --tasks .ralph/prd.json
```

---

## 6. Examples

### 6.1 Complete Import Example

**Input: `changes/CR-AUTH.md`**

```markdown
# CR: Add User Authentication

**Created:** 2026-01-25
**Status:** Draft

## Summary

Implement JWT-based authentication for the API.

## Task List

```json
[
  {
    "id": "CR-AUTH-1",
    "category": "setup",
    "description": "Add JWT dependency and configuration",
    "steps": [
      "Add PyJWT to requirements",
      "Create auth config module",
      "Add JWT_SECRET to env"
    ],
    "passes": false
  },
  {
    "id": "CR-AUTH-2",
    "category": "feature",
    "description": "Create auth service with token generation",
    "steps": [
      "Create AuthService class",
      "Implement create_token method",
      "Implement verify_token method",
      "Add unit tests"
    ],
    "passes": false
  }
]
```​
```

**Command:**

```bash
ralph import --cr changes/CR-AUTH.md
```

**Output: `.ralph/prd.json`**

```json
{
  "$schema": "https://ralph-orchestrator.dev/schemas/prd.schema.json",
  "project": "Add User Authentication",
  "branchName": "ralph/add-user-authentication",
  "description": "Implement JWT-based authentication for the API.",
  "tasks": [
    {
      "id": "T-001",
      "title": "Add JWT dependency and configuration",
      "description": "Add JWT dependency and configuration",
      "acceptanceCriteria": [
        "Add PyJWT to requirements",
        "Create auth config module",
        "Add JWT_SECRET to env"
      ],
      "priority": 1,
      "passes": false,
      "notes": "Imported from CR-AUTH-1 (category: setup)"
    },
    {
      "id": "T-002",
      "title": "Create auth service with token generation",
      "description": "Create auth service with token generation",
      "acceptanceCriteria": [
        "Create AuthService class",
        "Implement create_token method",
        "Implement verify_token method",
        "Add unit tests"
      ],
      "priority": 2,
      "passes": false,
      "notes": "Imported from CR-AUTH-2 (category: feature)"
    }
  ]
}
```

### 6.2 Export to CR Format Example

**Input: `.ralph/prd.json`**

```json
{
  "project": "User Auth",
  "branchName": "ralph/user-auth",
  "description": "Auth system",
  "tasks": [
    {
      "id": "T-001",
      "title": "Add JWT config",
      "description": "Set up JWT configuration",
      "acceptanceCriteria": ["Config file exists", "Tests pass"],
      "priority": 1,
      "passes": true,
      "notes": "Completed 2026-01-25"
    }
  ]
}
```

**Command:**

```bash
ralph export --format cr --output changes/CR-USER-AUTH.md
```

**Output: `changes/CR-USER-AUTH.md`**

```markdown
# CR: User Auth

**Generated:** 2026-01-25T15:30:00Z
**Branch:** ralph/user-auth
**Status:** In Progress

## Summary

Auth system

## Task List

```json
[
  {
    "id": "CR-USER-AUTH-1",
    "category": "setup",
    "description": "Add JWT config",
    "steps": [
      "Config file exists",
      "Tests pass"
    ],
    "passes": true
  }
]
```​

## Progress

- [x] CR-USER-AUTH-1: Add JWT config

---

*Exported by Ralph orchestrator on 2026-01-25*
```

### 6.3 Round-Trip Example

Demonstrating lossless round-trip (import → export → import):

```bash
# Start with CR markdown
ralph import --cr changes/CR-FEATURE.md

# Make changes, run tasks...
ralph run

# Export back to update CR
ralph export --format cr --update changes/CR-FEATURE.md

# Verify round-trip
ralph import --cr changes/CR-FEATURE.md --dry-run
# Should produce identical prd.json
```

---

## 7. Error Handling

### 7.1 Import Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `No task list found` | Missing `## Task List` section | Add section with JSON block |
| `Invalid JSON` | Malformed JSON in code block | Fix JSON syntax |
| `Schema validation failed` | Missing required fields | Add required fields |
| `Duplicate task IDs` | Same ID used multiple times | Use unique IDs |
| `Empty steps array` | Task has no steps | Add at least one step |

### 7.2 Export Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `No tasks to export` | prd.json has empty tasks array | Add tasks first |
| `Target file not writable` | Permission denied | Check file permissions |
| `Update target has no task list` | `--update` on file without task section | Use `--output` instead |

### 7.3 Validation Warnings

| Warning | Description |
|---------|-------------|
| `Non-standard ID format` | ID doesn't match T-NNN pattern |
| `Large priority gap` | Gap > 10 between consecutive priorities |
| `Long description truncated` | Description > 100 chars truncated for title |
| `Category not recognized` | Category not in standard list |

---

## Appendix A: Schema Cross-Reference

### prd.json (Canonical) vs CR Markdown (Compat)

| prd.json | CR Markdown | Notes |
|----------|-------------|-------|
| `project` | `# CR: {title}` | Extracted from H1 |
| `branchName` | (inferred) | From filename |
| `description` | `## Summary` | First paragraph |
| `tasks[].id` | `id` | Normalized to T-NNN |
| `tasks[].title` | `description` | Max 100 chars |
| `tasks[].description` | `description` | Full text |
| `tasks[].acceptanceCriteria` | `steps` | Direct mapping |
| `tasks[].priority` | (order) | From array position |
| `tasks[].passes` | `passes` | Direct mapping |
| `tasks[].notes` | - | Not in CR format |
| `tasks[].subtasks` | - | Not in CR format |
| - | `category` | Used for grouping |

### Subtask Handling

Subtasks in prd.json have no equivalent in CR markdown format. During export:

- **Option 1 (default):** Flatten subtasks into parent's steps
- **Option 2:** Create separate tasks for each subtask
- **Option 3:** Discard subtasks (warning issued)

During import, no subtasks are created (CR format doesn't support them).

---

*End of Markdown Import/Export Specification*
