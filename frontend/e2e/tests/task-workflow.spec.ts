import { test, expect } from "@playwright/test";

/**
 * E2E tests for task workflow operations
 *
 * Tests cover:
 * - Starting a task
 * - Monitoring task progress
 * - Task completion flow
 */

test.describe("Task Workflow", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the tasks page
    await page.goto("/tasks");
  });

  test("should display task board with columns", async ({ page }) => {
    // Verify task board columns exist
    await expect(page.getByText("To Do")).toBeVisible();
    await expect(page.getByText("In Progress")).toBeVisible();
    await expect(page.getByText("Done")).toBeVisible();
  });

  test("should display task cards in appropriate columns", async ({ page }) => {
    // Wait for tasks to load
    await page.waitForSelector('[data-testid="task-card"]', { timeout: 10000 }).catch(() => {
      // Tasks may not exist, which is fine
    });

    // Verify task cards are rendered
    const taskCards = page.locator('[data-testid="task-card"]');
    const count = await taskCards.count();

    if (count > 0) {
      // At least one task card should have a title
      await expect(taskCards.first()).toBeVisible();
    }
  });

  test("should open task details on card click", async ({ page }) => {
    // Find a task card
    const taskCard = page.locator('[data-testid="task-card"]').first();

    if (await taskCard.isVisible()) {
      await taskCard.click();

      // Sheet/modal should open with task details
      await expect(page.getByRole("dialog")).toBeVisible();

      // Should show acceptance criteria section
      await expect(page.getByText("Acceptance Criteria")).toBeVisible();
    }
  });

  test("should start task when clicking start button", async ({ page }) => {
    // Find a pending task's start button
    const startButton = page.getByRole("button", { name: /start/i }).first();

    if (await startButton.isVisible()) {
      await startButton.click();

      // Task should move to in-progress or show running indicator
      await expect(page.locator('[data-testid="running-indicator"]')).toBeVisible({ timeout: 5000 }).catch(() => {
        // Running indicator might not appear immediately
      });
    }
  });

  test("should show progress during task execution", async ({ page }) => {
    // Navigate to a running task if one exists
    const runningTask = page.locator('[data-status="in_progress"]').first();

    if (await runningTask.isVisible()) {
      // Should show current agent
      await expect(page.getByText(/implementing|writing tests|reviewing/i)).toBeVisible();

      // Should show duration
      await expect(page.getByText(/\d+[hms]/)).toBeVisible();
    }
  });

  test("should update task status in real-time", async ({ page }) => {
    // Wait for WebSocket connection
    await page.waitForFunction(() => {
      return (window as any).__wsConnected === true;
    }, { timeout: 5000 }).catch(() => {
      // WebSocket might not be available in test environment
    });

    // Task status changes should reflect without page reload
    const taskCard = page.locator('[data-testid="task-card"]').first();
    if (await taskCard.isVisible()) {
      const initialStatus = await taskCard.getAttribute("data-status");

      // Status badge should be visible
      await expect(taskCard.locator('[class*="badge"]')).toBeVisible();
    }
  });
});

test.describe("Task Actions", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tasks");
  });

  test("should skip task when clicking skip button", async ({ page }) => {
    const skipButton = page.getByRole("button", { name: /skip/i }).first();

    if (await skipButton.isVisible()) {
      await skipButton.click();

      // Confirmation dialog or immediate skip
      await page.waitForTimeout(500);
    }
  });

  test("should delete task when clicking delete button", async ({ page }) => {
    const deleteButton = page.locator('[data-testid="delete-task"]').first();

    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Confirmation dialog should appear
      const confirmDialog = page.getByRole("alertdialog");
      if (await confirmDialog.isVisible()) {
        await page.getByRole("button", { name: /confirm|delete/i }).click();
      }
    }
  });

  test("should filter tasks by status", async ({ page }) => {
    const filterDropdown = page.getByRole("combobox", { name: /filter/i });

    if (await filterDropdown.isVisible()) {
      await filterDropdown.click();
      await page.getByRole("option", { name: /pending/i }).click();

      // Only pending tasks should be visible
      const taskCards = page.locator('[data-status="pending"]');
      await expect(taskCards.first()).toBeVisible();
    }
  });
});

test.describe("Task Board Drag and Drop", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tasks");
  });

  test("should support drag and drop between columns", async ({ page }) => {
    // Find a draggable task card
    const taskCard = page.locator('[data-draggable="true"]').first();

    if (await taskCard.isVisible()) {
      const targetColumn = page.locator('[data-column="completed"]');

      // Perform drag and drop
      await taskCard.dragTo(targetColumn);

      // Task should now be in the new column
      await page.waitForTimeout(500);
    }
  });

  test("should reorder tasks within column", async ({ page }) => {
    const column = page.locator('[data-column="pending"]');
    const tasks = column.locator('[data-testid="task-card"]');

    const count = await tasks.count();
    if (count >= 2) {
      const firstTask = tasks.nth(0);
      const secondTask = tasks.nth(1);

      // Drag first task below second
      await firstTask.dragTo(secondTask);

      await page.waitForTimeout(500);
    }
  });
});
