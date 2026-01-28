/**
 * End-to-end tests for Ralph Dashboard using Playwright.
 *
 * Tests cover:
 * - Start task workflow
 * - Monitor progress with real-time updates
 * - Create branch workflow
 * - Create PR workflow
 * - Edit configuration workflow
 */

import { test, expect, Page } from '@playwright/test';
import { promises as fs } from 'fs';
import { join } from 'path';

// Test configuration
const TEST_PROJECT_PATH = process.env.TEST_PROJECT_PATH || '/tmp/ralph-e2e-test';
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const API_URL = process.env.API_URL || 'http://localhost:8000';

/**
 * Helper function to wait for WebSocket connection
 */
async function waitForWebSocket(page: Page) {
  await page.waitForFunction(() => {
    return (window as any).__websocket_ready === true;
  }, { timeout: 5000 });
}

/**
 * Helper function to setup test project
 */
async function setupTestProject() {
  // Create project directory structure
  await fs.mkdir(join(TEST_PROJECT_PATH, '.ralph'), { recursive: true });

  // Create prd.json
  const prdData = {
    project: 'E2E Test Project',
    description: 'Testing Ralph Dashboard E2E',
    tasks: [
      {
        id: 'T-001',
        title: 'Test Task 1',
        description: 'First test task',
        acceptanceCriteria: ['Criterion 1', 'Criterion 2'],
        priority: 1,
        passes: false,
        notes: '',
        requiresTests: true,
      },
      {
        id: 'T-002',
        title: 'Test Task 2',
        description: 'Second test task',
        acceptanceCriteria: ['Criterion A'],
        priority: 2,
        passes: false,
        notes: '',
        requiresTests: false,
      },
    ],
  };

  await fs.writeFile(
    join(TEST_PROJECT_PATH, '.ralph', 'prd.json'),
    JSON.stringify(prdData, null, 2)
  );

  // Create ralph.yml
  const configData = `version: "1"
task_source:
  type: prd_json
  path: .ralph/prd.json
git:
  base_branch: main
  remote: origin
gates:
  build:
    - name: lint
      cmd: echo "Linting..."
  full:
    - name: test
      cmd: echo "Testing..."
test_paths:
  - tests/**
`;

  await fs.writeFile(
    join(TEST_PROJECT_PATH, '.ralph', 'ralph.yml'),
    configData
  );
}

/**
 * Helper function to cleanup test project
 */
async function cleanupTestProject() {
  try {
    await fs.rm(TEST_PROJECT_PATH, { recursive: true, force: true });
  } catch (error) {
    // Ignore cleanup errors
  }
}

test.describe('Ralph Dashboard E2E Tests', () => {
  test.beforeAll(async () => {
    await setupTestProject();
  });

  test.afterAll(async () => {
    await cleanupTestProject();
  });

  test.describe('Project Selection and Dashboard', () => {
    test('should load project list on dashboard', async ({ page }) => {
      await page.goto(BASE_URL);

      // Wait for projects to load
      await page.waitForSelector('[data-testid="project-list"]', { timeout: 10000 });

      // Should show project cards
      const projectCards = await page.locator('[data-testid="project-card"]').count();
      expect(projectCards).toBeGreaterThan(0);
    });

    test('should display project details', async ({ page }) => {
      await page.goto(BASE_URL);
      await page.waitForSelector('[data-testid="project-card"]');

      // Click on first project
      await page.click('[data-testid="project-card"]:first-child');

      // Should navigate to project page
      await expect(page).toHaveURL(new RegExp('/project/'));

      // Should show project name
      await expect(page.locator('[data-testid="project-name"]')).toBeVisible();

      // Should show task board
      await expect(page.locator('[data-testid="task-board"]')).toBeVisible();
    });
  });

  test.describe('Start Task Workflow', () => {
    test('should start a task and show progress', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Wait for task board to load
      await page.waitForSelector('[data-testid="task-card"]', { timeout: 10000 });

      // Find the first pending task
      const firstTask = page.locator('[data-testid="task-card"]').first();
      await expect(firstTask).toBeVisible();

      // Click start button
      await firstTask.locator('[data-testid="start-task-button"]').click();

      // Should show confirmation dialog
      await expect(page.locator('[data-testid="start-task-dialog"]')).toBeVisible();

      // Confirm start
      await page.click('[data-testid="confirm-start-button"]');

      // Should show task progress panel
      await expect(page.locator('[data-testid="task-progress-panel"]')).toBeVisible({ timeout: 5000 });

      // Should show current agent
      await expect(page.locator('[data-testid="current-agent"]')).toBeVisible();

      // Should show progress indicator
      await expect(page.locator('[data-testid="progress-indicator"]')).toBeVisible();
    });

    test('should receive real-time updates via WebSocket', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Setup WebSocket message listener
      const wsMessages: any[] = [];
      await page.evaluate(() => {
        (window as any).__ws_messages = [];
        const originalWebSocket = (window as any).WebSocket;
        (window as any).WebSocket = class extends originalWebSocket {
          constructor(url: string) {
            super(url);
            this.addEventListener('message', (event) => {
              try {
                const data = JSON.parse(event.data);
                (window as any).__ws_messages.push(data);
              } catch (e) {
                // Ignore parse errors
              }
            });
          }
        };
      });

      // Wait for WebSocket connection
      await waitForWebSocket(page);

      // Trigger task start
      await page.click('[data-testid="task-card"]:first-child [data-testid="start-task-button"]');
      await page.click('[data-testid="confirm-start-button"]');

      // Wait for WebSocket messages
      await page.waitForFunction(() => {
        return (window as any).__ws_messages.length > 0;
      }, { timeout: 10000 });

      // Get messages
      const messages = await page.evaluate(() => (window as any).__ws_messages);

      // Should receive task started event
      expect(messages.some((msg: any) => msg.type === 'task_started')).toBe(true);
    });

    test('should display agent output in real-time', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Start a task
      await page.click('[data-testid="task-card"]:first-child [data-testid="start-task-button"]');
      await page.click('[data-testid="confirm-start-button"]');

      // Should show log viewer
      await expect(page.locator('[data-testid="log-viewer"]')).toBeVisible({ timeout: 5000 });

      // Wait for log content
      await page.waitForFunction(() => {
        const logViewer = document.querySelector('[data-testid="log-viewer"]');
        return logViewer && logViewer.textContent && logViewer.textContent.length > 0;
      }, { timeout: 10000 });

      // Should show agent output
      const logContent = await page.locator('[data-testid="log-viewer"]').textContent();
      expect(logContent).toBeTruthy();
    });
  });

  test.describe('Monitor Progress', () => {
    test('should show iteration count', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Start task
      await page.click('[data-testid="task-card"]:first-child [data-testid="start-task-button"]');
      await page.click('[data-testid="confirm-start-button"]');

      // Should show iteration counter
      await expect(page.locator('[data-testid="iteration-counter"]')).toBeVisible({ timeout: 5000 });

      // Should show iteration number
      const iterationText = await page.locator('[data-testid="iteration-counter"]').textContent();
      expect(iterationText).toMatch(/Iteration \d+/);
    });

    test('should show gate results', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Start task
      await page.click('[data-testid="task-card"]:first-child [data-testid="start-task-button"]');
      await page.click('[data-testid="confirm-start-button"]');

      // Wait for gates section
      await expect(page.locator('[data-testid="gates-section"]')).toBeVisible({ timeout: 15000 });

      // Should show gate results
      const gateResults = await page.locator('[data-testid="gate-result"]').count();
      expect(gateResults).toBeGreaterThan(0);
    });

    test('should update task status when completed', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      const taskCard = page.locator('[data-testid="task-card"]').first();

      // Get initial status
      const initialStatus = await taskCard.getAttribute('data-status');

      // Start and wait for completion (mocked)
      await page.click('[data-testid="task-card"]:first-child [data-testid="start-task-button"]');
      await page.click('[data-testid="confirm-start-button"]');

      // Simulate task completion via WebSocket message
      await page.evaluate(() => {
        // This would be sent by the actual server
        const event = new CustomEvent('ws-message', {
          detail: {
            type: 'task_completed',
            task_id: 'T-001',
            success: true,
          },
        });
        window.dispatchEvent(event);
      });

      // Wait for status update
      await page.waitForFunction(
        (expectedStatus) => {
          const card = document.querySelector('[data-testid="task-card"]');
          return card && card.getAttribute('data-status') !== expectedStatus;
        },
        initialStatus,
        { timeout: 10000 }
      );

      // Verify status changed
      const newStatus = await taskCard.getAttribute('data-status');
      expect(newStatus).not.toBe(initialStatus);
    });
  });

  test.describe('Create Branch Workflow', () => {
    test('should open create branch dialog', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open git panel
      await page.click('[data-testid="git-panel-toggle"]');

      // Should show git panel
      await expect(page.locator('[data-testid="git-panel"]')).toBeVisible();

      // Click create branch button
      await page.click('[data-testid="create-branch-button"]');

      // Should show create branch dialog
      await expect(page.locator('[data-testid="create-branch-dialog"]')).toBeVisible();
    });

    test('should create branch with valid name', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open git panel and dialog
      await page.click('[data-testid="git-panel-toggle"]');
      await page.click('[data-testid="create-branch-button"]');

      // Fill branch name
      await page.fill('[data-testid="branch-name-input"]', 'feature/test-branch');

      // Submit
      await page.click('[data-testid="create-branch-submit"]');

      // Should show success message
      await expect(page.locator('[data-testid="success-toast"]')).toBeVisible({ timeout: 5000 });

      // Dialog should close
      await expect(page.locator('[data-testid="create-branch-dialog"]')).not.toBeVisible();
    });

    test('should validate branch name', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open dialog
      await page.click('[data-testid="git-panel-toggle"]');
      await page.click('[data-testid="create-branch-button"]');

      // Try invalid branch name
      await page.fill('[data-testid="branch-name-input"]', 'invalid branch name');
      await page.click('[data-testid="create-branch-submit"]');

      // Should show validation error
      await expect(page.locator('[data-testid="validation-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="validation-error"]')).toContainText('Invalid branch name');
    });
  });

  test.describe('Create PR Workflow', () => {
    test('should open create PR modal', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open git panel
      await page.click('[data-testid="git-panel-toggle"]');

      // Click create PR button
      await page.click('[data-testid="create-pr-button"]');

      // Should show create PR modal
      await expect(page.locator('[data-testid="create-pr-modal"]')).toBeVisible();
    });

    test('should create PR with title and description', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open PR modal
      await page.click('[data-testid="git-panel-toggle"]');
      await page.click('[data-testid="create-pr-button"]');

      // Fill form
      await page.fill('[data-testid="pr-title-input"]', 'Test PR Title');
      await page.fill('[data-testid="pr-description-input"]', 'Test PR description content');

      // Select base branch
      await page.click('[data-testid="base-branch-select"]');
      await page.click('[data-testid="branch-option-main"]');

      // Submit
      await page.click('[data-testid="create-pr-submit"]');

      // Should show success message with PR URL
      await expect(page.locator('[data-testid="pr-created-success"]')).toBeVisible({ timeout: 10000 });

      // Should contain PR link
      const prLink = await page.locator('[data-testid="pr-url-link"]');
      await expect(prLink).toBeVisible();
    });

    test('should validate PR form fields', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open PR modal
      await page.click('[data-testid="git-panel-toggle"]');
      await page.click('[data-testid="create-pr-button"]');

      // Try to submit without title
      await page.click('[data-testid="create-pr-submit"]');

      // Should show validation error
      await expect(page.locator('[data-testid="title-validation-error"]')).toBeVisible();
    });
  });

  test.describe('Edit Configuration Workflow', () => {
    test('should open config editor', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Click settings/config button
      await page.click('[data-testid="config-editor-button"]');

      // Should show config editor panel
      await expect(page.locator('[data-testid="config-editor-panel"]')).toBeVisible();
    });

    test('should display current configuration', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open config editor
      await page.click('[data-testid="config-editor-button"]');

      // Should show YAML editor with content
      const editorContent = await page.locator('[data-testid="config-yaml-editor"]').textContent();
      expect(editorContent).toContain('version:');
      expect(editorContent).toContain('task_source:');
    });

    test('should save configuration changes', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open config editor
      await page.click('[data-testid="config-editor-button"]');

      // Modify config
      await page.click('[data-testid="add-gate-button"]');
      await page.fill('[data-testid="gate-name-input"]', 'new-gate');
      await page.fill('[data-testid="gate-cmd-input"]', 'echo "test"');

      // Save
      await page.click('[data-testid="save-config-button"]');

      // Should show success message
      await expect(page.locator('[data-testid="config-saved-success"]')).toBeVisible({ timeout: 5000 });
    });

    test('should validate YAML syntax', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Open config editor
      await page.click('[data-testid="config-editor-button"]');

      // Enter invalid YAML
      await page.locator('[data-testid="config-yaml-editor"]').fill('invalid: yaml: syntax:');

      // Try to save
      await page.click('[data-testid="save-config-button"]');

      // Should show validation error
      await expect(page.locator('[data-testid="yaml-syntax-error"]')).toBeVisible();
    });
  });

  test.describe('Error Handling', () => {
    test('should handle API errors gracefully', async ({ page }) => {
      // Mock API to return error
      await page.route(`${API_URL}/api/projects`, route => {
        route.fulfill({
          status: 500,
          body: JSON.stringify({ detail: 'Internal server error' }),
        });
      });

      await page.goto(BASE_URL);

      // Should show error message
      await expect(page.locator('[data-testid="error-message"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('Failed to load projects');
    });

    test('should handle WebSocket disconnection', async ({ page }) => {
      await page.goto(`${BASE_URL}/project/${encodeURIComponent(TEST_PROJECT_PATH)}`);

      // Wait for WebSocket connection
      await waitForWebSocket(page);

      // Simulate WebSocket disconnection
      await page.evaluate(() => {
        const ws = (window as any).__websocket;
        if (ws) {
          ws.close();
        }
      });

      // Should show reconnection indicator
      await expect(page.locator('[data-testid="ws-reconnecting-indicator"]')).toBeVisible({ timeout: 3000 });
    });
  });

  test.describe('Accessibility', () => {
    test('should be keyboard navigable', async ({ page }) => {
      await page.goto(BASE_URL);

      // Tab through elements
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');

      // Should focus on interactive element
      const focusedElement = await page.evaluate(() => document.activeElement?.getAttribute('data-testid'));
      expect(focusedElement).toBeTruthy();
    });

    test('should have proper ARIA labels', async ({ page }) => {
      await page.goto(BASE_URL);

      // Check for ARIA labels on key elements
      const projectCard = page.locator('[data-testid="project-card"]').first();
      const ariaLabel = await projectCard.getAttribute('aria-label');
      expect(ariaLabel).toBeTruthy();
    });
  });
});
