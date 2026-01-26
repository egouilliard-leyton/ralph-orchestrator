# How To Create Tasks for Ralph Orchestrator

This guide explains how to create effective task lists in the `prd.json` format that Ralph can execute successfully.

## Prerequisites

- Repository configured with Ralph (`.ralph/ralph.yml` exists)
- Understanding of your project's acceptance criteria patterns
- Knowledge of the feature or change you want to implement

## Steps

### 1. Open the Task List File

Navigate to your project and open the task list file:

```
.ralph/prd.json
```

If the file doesn't exist, create it using the template structure.

### 2. Set the Project Metadata

Fill in the top-level fields:

```json
{
  "project": "Feature Name",
  "branchName": "ralph/feature-name",
  "description": "Brief description of what this feature does"
}
```

Use kebab-case for branch names. The description should be one sentence.

### 3. Create Tasks with Unique IDs

Each task must have a unique ID in the format `T-NNN`:

```json
{
  "id": "T-001",
  "title": "Add user authentication endpoint"
}
```

IDs should be sequential (T-001, T-002, T-003).

### 4. Write Action-Oriented Titles

Titles should start with a verb and be under 100 characters:

**Good titles:**
- "Add JWT dependency and configuration"
- "Create user registration API endpoint"
- "Implement login form component"

**Poor titles:**
- "JWT" (too vague)
- "The user should be able to..." (not action-oriented)
- "Fix the authentication system to properly handle..." (too long)

### 5. Write Clear Descriptions

Descriptions should explain what to do AND why:

```json
{
  "description": "Install PyJWT package and create auth configuration module with JWT settings. The configuration should support environment-based secrets for security."
}
```

Include context that helps the implementation agent understand the goal.

### 6. Define Verifiable Acceptance Criteria

Each criterion must be boolean (pass/fail) and machine-verifiable:

**Verifiable patterns:**

| Pattern | Example |
|---------|---------|
| File exists | `File \`src/auth.py\` exists` |
| File contains | `File \`config.py\` contains \`JWT_SECRET\`` |
| Command succeeds | `Run \`npm test\` - exits with code 0` |
| API response | `POST /api/login returns 200 on valid credentials` |
| Browser check | `agent-browser: open /login - form renders` |

**Non-verifiable (avoid):**
- "Code is clean" (subjective)
- "Works correctly" (vague)
- "User can login" (not machine-testable as written)

### 7. Set Task Priorities

Priorities determine execution order. Lower numbers run first:

```json
{
  "priority": 1
}
```

**Priority guidelines:**
- 1-3: Setup and configuration tasks
- 4-6: Core implementation tasks
- 7-9: Integration and UI tasks
- 10+: Verification and testing tasks

### 8. Initialize Status Fields

New tasks should have:

```json
{
  "passes": false,
  "notes": ""
}
```

The `passes` field is script-controlled - agents cannot modify it directly. The `notes` field will be populated with verification evidence.

### 9. (Optional) Add Subtasks for Complex Tasks

If a task has multiple distinct steps, use subtasks:

```json
{
  "id": "T-003",
  "title": "Implement auth service",
  "subtasks": [
    {
      "id": "T-003.1",
      "title": "Implement create_token method",
      "acceptanceCriteria": ["Token contains user_id claim"],
      "passes": false,
      "notes": ""
    }
  ]
}
```

Parent task passes only when all subtasks pass.

### 10. Validate Your Task List

Save the file and validate it against the schema:

```bash
ralph validate-tasks
```

Fix any schema validation errors before running.

## Expected Results

A well-formed task list should:

- Have 8-15 tasks for a typical feature
- Be ordered by dependency (prerequisites first)
- Have at least one acceptance criterion per task
- Use consistent terminology throughout
- Be executable in one agent iteration per task

When Ralph runs, you should see:
- Tasks executing in priority order
- Clear pass/fail results for each criterion
- Notes populated with verification evidence

## Troubleshooting

### Task validation fails

If schema validation reports errors:

**Solution**: Check that all required fields are present, IDs match the `T-NNN` pattern, and acceptance criteria is a non-empty array.

### Task takes too many iterations

If a task repeatedly fails and retries:

**Solution**: The task may be too large. Break it into smaller subtasks or separate tasks.

### Acceptance criteria not verifiable

If review rejects because criteria aren't verified:

**Solution**: Rewrite criteria using verifiable patterns (command success, file existence, API response).

### Tasks execute out of order

If dependent tasks run before prerequisites:

**Solution**: Ensure priority numbers reflect dependencies. Lower priority tasks run first.

## Additional Information

### Acceptance Criteria Best Practices

1. **One criterion per line** - Don't combine multiple checks
2. **Be specific** - Include exact file paths, commands, responses
3. **Include the verification method** - "Run `command`" or "agent-browser: action"
4. **Make each criterion independent** - Can be verified in isolation

### Task Granularity Guidelines

- **Too small**: "Add import statement" (trivial)
- **Just right**: "Add JWT dependency and configuration" (single concern, verifiable)
- **Too large**: "Implement complete authentication system" (multiple concerns)

### Example Task List

See `examples/prd-example-authentication.json` for a complete, well-structured task list demonstrating all best practices.

---

## Importing Tasks from CR Markdown

If you have existing tasks in a Change Request (CR) markdown file, you can import them to `prd.json` format.

### CR Markdown Format

CR files contain tasks in a `## Task List` section with embedded JSON:

```markdown
## Task List

```json
[
  {
    "id": "CR-FEATURE-1",
    "category": "setup",
    "description": "Task description here",
    "steps": [
      "Step 1",
      "Step 2"
    ],
    "passes": false
  }
]
```​
```

### Import Command

```bash
# Generate tasks from CR/PRD markdown
ralph tasks --from changes/CR-FEATURE.md --out .ralph/prd.json --task-count 8-15

# Preview (writes + prints a short task list)
ralph tasks --from changes/CR-FEATURE.md --out .ralph/prd.json --dry-run
```

### What Gets Transformed

| CR Field | prd.json Field |
|----------|----------------|
| `id` (e.g., CR-FEAT-1) | `id` (normalized to T-001) |
| `description` | `title` and `description` |
| `steps` | `acceptanceCriteria` |
| `category` | Preserved in `notes` |
| `passes` | `passes` |

### After Import

1. Review the generated `.ralph/prd.json`
2. Adjust priorities if needed
3. Add any missing acceptance criteria
4. Run `ralph validate-tasks` to verify

See `examples/cr-import-example.md` for a complete import example.

---

## Exporting Tasks to Markdown

Export your `prd.json` tasks to a human-readable markdown format:

```bash
# Export to standalone markdown
ralph export --format markdown --output tasks/current-prd.md

# Export to CR format for code review
ralph export --format cr --output changes/CR-EXPORT.md

# Update existing CR file in-place
ralph export --format cr --update changes/CR-FEATURE.md
```

### Export Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `markdown` | Clean markdown with task list | Documentation, sharing |
| `cr` | CR-compatible with JSON block | Code review, legacy workflows |
| `json` | Raw JSON output | Debugging, scripting |

See [Markdown Import/Export Specification](../specs/markdown-import-export.md) for complete details.

---

## Related Guides

- [How To Set Up a Repository](./how-to-setup-repository.md) - Initial Ralph configuration
- [How To Use the CLI](./how-to-use-cli.md) - Running tasks and CLI commands
- [How To Use Autopilot](./how-to-use-autopilot.md) - Automated task generation
- [How To Interpret Results](./how-to-interpret-results.md) - Understanding task execution results
