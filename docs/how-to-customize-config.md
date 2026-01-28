# How To Customize Ralph Configuration

This guide explains how to customize the `.ralph/ralph.yml` configuration file to match your project's specific needs, including ports, commands, quality gates, and more.

## Prerequisites

- Ralph CLI installed
- A repository initialized with `ralph init`
- `.ralph/ralph.yml` file present in your project

## Understanding the Configuration File

### 1. Open Your Configuration File

Navigate to your project and open the configuration:

```
.ralph/ralph.yml
```

This file controls all aspects of how Ralph runs in your repository.

## Customizing Services

### 2. Configure Backend Service

If your project has a backend server, configure it in the `services` section:

```yaml
services:
  backend:
    # Commands to start the server
    start:
      dev: "npm run dev"              # Development mode (with hot reload)
      prod: "npm run start"           # Production mode
    
    # Port the server runs on
    port: 3000
    
    # Health check endpoint(s) to verify server is ready
    health:
      - /health
      - /api/status
    
    # How long to wait for server to be ready (seconds)
    timeout: 30
```

**Common backend configurations:**

| Framework | Start Command | Port |
|-----------|---------------|------|
| Express.js | `node server.js` | 3000 |
| FastAPI | `uvicorn main:app --port {port}` | 8000 |
| Django | `python manage.py runserver {port}` | 8000 |
| Rails | `rails server -p {port}` | 3000 |

Note: Use `{port}` as a placeholder - Ralph will substitute the configured port.

### 3. Configure Frontend Service

If you have a separate frontend, add frontend configuration:

```yaml
services:
  frontend:
    # Build command (runs before serving in prod mode)
    build: "npm run build"
    
    # Serve commands
    serve:
      dev: "npm run dev -- --port {port}"
      prod: "npm run preview -- --port {port}"
    
    port: 5173
    timeout: 30
```

**Common frontend configurations:**

| Framework | Dev Command | Build Command |
|-----------|-------------|---------------|
| Vite | `npm run dev -- --port {port}` | `npm run build` |
| Create React App | `PORT={port} npm start` | `npm run build` |
| Next.js | `npm run dev -- -p {port}` | `npm run build` |
| Vue CLI | `npm run serve -- --port {port}` | `npm run build` |

## Customizing Quality Gates

### 4. Configure Build Gates (Fast Checks)

Build gates run during the task loop for quick feedback:

```yaml
gates:
  build:
    - name: typecheck
      cmd: "npm run typecheck"
      when: tsconfig.json        # Only run if this file exists
      timeout_seconds: 120
      fatal: true                # Stop if this fails
    
    - name: lint
      cmd: "npm run lint"
      when: package.json
      timeout_seconds: 60
      fatal: false               # Continue even if this fails (warning only)
```

### 5. Configure Full Gates (Comprehensive Checks)

Full gates run after task completion for thorough verification:

```yaml
gates:
  full:
    - name: test
      cmd: "npm test"
      when: package.json
      timeout_seconds: 300
      fatal: true
    
    - name: typecheck
      cmd: "npm run typecheck"
      when: tsconfig.json
      timeout_seconds: 120
      fatal: true
    
    - name: lint
      cmd: "npm run lint"
      when: package.json
      timeout_seconds: 60
      fatal: false
    
    - name: build
      cmd: "npm run build"
      when: package.json
      timeout_seconds: 300
      fatal: true
```

**Gate properties explained:**

| Property | Description | Example |
|----------|-------------|---------|
| `name` | Display name for the gate | `test`, `lint`, `build` |
| `cmd` | Command to execute | `npm test`, `pytest` |
| `when` | File that must exist to run this gate | `package.json`, `pyproject.toml` |
| `timeout_seconds` | Maximum time to wait | `300` (5 minutes) |
| `fatal` | Stop on failure (true) or warn only (false) | `true` |

### 6. Common Gate Configurations by Stack

**Python projects:**

```yaml
gates:
  full:
    - name: pytest
      cmd: "pytest -x --tb=short"
      when: pyproject.toml
      timeout_seconds: 300
      fatal: true
    
    - name: mypy
      cmd: "mypy src/ --ignore-missing-imports"
      when: pyproject.toml
      timeout_seconds: 120
      fatal: true
    
    - name: ruff
      cmd: "ruff check src/"
      when: pyproject.toml
      timeout_seconds: 60
      fatal: false
```

**Node.js projects:**

```yaml
gates:
  full:
    - name: jest
      cmd: "npm test"
      when: package.json
      timeout_seconds: 300
      fatal: true
    
    - name: tsc
      cmd: "npx tsc --noEmit"
      when: tsconfig.json
      timeout_seconds: 120
      fatal: true
    
    - name: eslint
      cmd: "npm run lint"
      when: .eslintrc.json
      timeout_seconds: 60
      fatal: false
```

## Customizing Test Path Guardrails

### 7. Define Allowed Test Paths

The test-writing agent can only modify files matching these patterns:

```yaml
test_paths:
  - tests/**                    # Python tests
  - test_scripts/**             # Script tests
  - __tests__/**                # Jest tests
  - **/*.test.ts                # TypeScript test files
  - **/*.test.tsx               # React test files
  - **/*.spec.ts                # Spec files
  - **/e2e/**                   # End-to-end tests
  - **/cypress/**               # Cypress tests
```

This prevents the test agent from accidentally modifying production code.

## Customizing UI Verification

### 8. Configure Agent-Browser Tests

Enable browser-based UI testing:

```yaml
ui:
  agent_browser:
    enabled: true
    script: ui_tests/smoke_test.sh     # Path to test script
```

Or use inline test definitions:

```yaml
ui:
  agent_browser:
    enabled: true
    tests:
      - name: app_loads
        action: open /
        expected: "navigation visible"
      
      - name: login_works
        action: fill_form
        expected: "dashboard visible"
```

### 9. Configure Robot Framework Tests

Enable Robot Framework testing:

```yaml
ui:
  robot:
    enabled: true
    suite: ui_tests/robot              # Path to test suite
    variables:
      HEADLESS: "true"                 # Run without visible browser
      BROWSER: chromium                # Browser to use
      TIMEOUT: 30s                     # Element wait timeout
```

## Customizing Agent Settings

### 10. Configure AI Models per Role

Different tasks can use different AI models:

```yaml
agents:
  implementation:
    model: claude-opus-4-5-20251101    # Most capable for implementation
    timeout: 1800                       # 30 minutes
  
  test_writing:
    model: claude-sonnet-4-5-20250929  # Good balance for tests
    timeout: 1800
    allowed_tools:                      # Restrict tools for safety
      - Read
      - Grep
      - Glob
      - Edit
      - Write
      - LS
  
  review:
    model: haiku                        # Fast model for review
    timeout: 1800
    allowed_tools:                      # Read-only tools
      - Read
      - Grep
      - Glob
      - LS
  
  fix:
    model: claude-sonnet-4-5-20250929
    timeout: 1800
  
  planning:
    model: claude-sonnet-4-5-20250929
    timeout: 1800
    allowed_tools:
      - Read
      - Grep
      - Glob
      - LS
```

## Customizing Limits

### 11. Set Iteration and Timeout Limits

Control how long Ralph tries before giving up:

```yaml
limits:
  claude_timeout: 1800          # Max time per Claude call (seconds)
  max_iterations: 30            # Max attempts per task
  post_verify_iterations: 10    # Max runtime fix attempts
  ui_fix_iterations: 10         # Max UI fix attempts
  robot_fix_iterations: 10      # Max Robot fix attempts
```

**When to adjust:**
- Increase `max_iterations` for complex tasks
- Decrease for faster failure detection
- Increase `claude_timeout` for large codebases

## Customizing Autopilot

### 12. Configure Autopilot Mode

Enable automated self-improvement:

```yaml
autopilot:
  enabled: true

  # Where to find analysis reports
  reports_dir: ./reports

  # Branch naming convention
  branch_prefix: ralph/

  # Create PR when done
  create_pr: true

  # Analysis settings
  analysis:
    provider: anthropic
    model: claude-opus-4-5-20251101
    recent_days: 7              # Skip items fixed recently

  # PRD generation
  prd:
    mode: autonomous            # Don't ask questions
    output_dir: ./tasks

  # Task generation
  tasks:
    output: .ralph/prd.json
    min_count: 8                # Minimum tasks to generate
    max_count: 15               # Maximum tasks to generate

  # Progress tracking
  memory:
    progress: .ralph/progress.txt
    archive: .ralph/archive
```

### 13. Configure Research Phase

Control how autopilot researches your codebase before generating PRDs:

```yaml
autopilot:
  # Research configuration
  research:
    enabled: true               # Enable research phase (default: true)

    backend:
      enabled: true             # Scan Python/API code
      patterns:                 # File patterns to scan
        - "**/*.py"
        - "**/models/**"
        - "**/routes/**"
        - "**/services/**"
        - "**/api/**"

    frontend:
      enabled: true             # Scan frontend code
      patterns:
        - "**/*.tsx"
        - "**/*.jsx"
        - "**/*.vue"
        - "**/components/**"
        - "**/styles/**"

    web:
      enabled: true             # Search web for docs/best practices
      max_queries: 5            # Maximum web search queries
```

**Research Types:**

| Type | Purpose | Default Patterns |
|------|---------|------------------|
| `backend` | Scan Python files, models, routes, services | `**/*.py`, `**/models/**`, `**/routes/**` |
| `frontend` | Scan TSX/JSX/Vue, components, styles | `**/*.tsx`, `**/*.jsx`, `**/components/**` |
| `web` | Search documentation and best practices | N/A (uses queries) |

## Customizing Skills

### 14. Configure Skill Routing

Skills enable specialized Claude plugins for specific task types:

```yaml
skills:
  enabled: true                 # Enable skill routing (default: true)
  auto_detect: true             # Auto-detect skills from task content

  # Custom skill mappings (in addition to defaults)
  custom_mappings:
    - skill_name: "custom-skill"
      patterns:                 # Keywords that trigger this skill
        - "custom keyword"
        - "specific term"

    - skill_name: "data-viz"
      patterns:
        - "chart"
        - "graph"
        - "visualization"
```

**Default Skills:**

Ralph includes built-in skill detection for common task types:

| Skill | Triggers | Purpose |
|-------|----------|---------|
| `frontend-design` | "UI", "component", "styling" | Frontend development |
| `docx` | "document", "word", ".docx" | Word document creation |
| `xlsx` | "spreadsheet", "excel", ".xlsx" | Spreadsheet manipulation |
| `pdf` | "PDF", "form", "report" | PDF processing |
| `pptx` | "presentation", "slides" | PowerPoint creation |

Skills are automatically applied when task descriptions match their trigger patterns.

## Customizing Git and PR Settings

### 13. Configure Git Behavior

Set your git defaults:

```yaml
git:
  base_branch: main             # Or "master", "develop", etc.
  remote: origin                # Remote name
```

### 14. Configure PR Templates

Customize how PRs are created:

```yaml
pr:
  enabled: true
  title_template: "Ralph: {priority_item}"
  body_template: |
    ## Summary
    {description}
    
    ## Rationale
    {rationale}
    
    ## Tasks Completed
    {task_summary}
    
    ## Testing
    - All gates passed
    - UI tests passed
```

## Expected Results

After customizing your configuration:

- Running `ralph run` should use your custom commands
- Gates should match your project's quality checks
- Services should start on your specified ports
- UI tests should run with your specified settings

## Troubleshooting

### Gate command not found

The command in your gate doesn't exist.

**Solution:** Verify the command works when run manually in your terminal.

### Service fails to start

The start command or port is incorrect.

**Solution:** 
1. Try the start command manually
2. Check if the port is already in use
3. Verify the command uses `{port}` placeholder

### Test path not allowed

The test agent tried to modify files outside allowed paths.

**Solution:** Add the correct pattern to `test_paths`.

### UI tests not running

Agent-browser or Robot Framework not configured.

**Solution:** 
1. Set `enabled: true` under `ui.agent_browser` or `ui.robot`
2. Verify the script or suite path exists

## Additional Information

### Validating Your Configuration

Check for syntax errors:

```bash
ralph scan
```

This will report any configuration issues.

### Using Environment Variables

Override settings via environment:

```bash
RALPH_IMPL_MODEL=claude-opus-4-5-20251101 ralph run
```

### Configuration Templates

Ralph provides starter templates:

| Template | Best For |
|----------|----------|
| `ralph.yml.minimal` | Simple projects |
| `ralph.yml.python` | Python-only projects |
| `ralph.yml.node` | Node.js projects |
| `ralph.yml.fullstack` | Backend + Frontend projects |

### Related Guides

- [How To Set Up a Repository](./how-to-setup-repository.md) - Initial setup
- [How To Use the CLI](./how-to-use-cli.md) - Command options
- [How To Interpret Results](./how-to-interpret-results.md) - Understanding output
