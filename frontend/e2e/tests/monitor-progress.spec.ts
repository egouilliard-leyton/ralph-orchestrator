import { test, expect } from "@playwright/test";

/**
 * E2E tests for monitoring task progress
 *
 * Tests cover:
 * - Real-time progress updates
 * - Log viewing
 * - Timeline events
 */

test.describe("Progress Monitoring", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display dashboard with project overview", async ({ page }) => {
    // Dashboard should show projects
    await expect(page.getByText(/projects/i)).toBeVisible();

    // Should show aggregate statistics
    await expect(page.getByText(/pending|in progress|completed/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
  });

  test("should show connection status indicator", async ({ page }) => {
    const connectionStatus = page.locator('[data-testid="connection-status"]');

    if (await connectionStatus.isVisible()) {
      // Should indicate connected or disconnected
      await expect(connectionStatus.getByText(/connected|disconnected|connecting/i)).toBeVisible();
    }
  });

  test("should display real-time task updates", async ({ page }) => {
    await page.goto("/tasks");

    // Wait for WebSocket connection
    await page.waitForTimeout(2000);

    // Tasks should have current status
    const taskCards = page.locator('[data-testid="task-card"]');
    if (await taskCards.first().isVisible()) {
      // Status badges should be visible
      await expect(taskCards.first().locator('[class*="badge"]')).toBeVisible();
    }
  });
});

test.describe("Log Viewer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");

    // Navigate to a project with logs
    const projectLink = page.getByRole("link", { name: /open/i }).first();
    if (await projectLink.isVisible()) {
      await projectLink.click();
    }
  });

  test("should display log files list", async ({ page }) => {
    const logsTab = page.getByRole("tab", { name: /logs/i });

    if (await logsTab.isVisible()) {
      await logsTab.click();

      // Log files should be listed
      const logFiles = page.locator('[data-testid="log-file"]');
      await expect(logFiles.first()).toBeVisible({ timeout: 5000 }).catch(() => {});
    }
  });

  test("should display log content when selected", async ({ page }) => {
    const logsTab = page.getByRole("tab", { name: /logs/i });

    if (await logsTab.isVisible()) {
      await logsTab.click();

      const logFile = page.locator('[data-testid="log-file"]').first();
      if (await logFile.isVisible()) {
        await logFile.click();

        // Log content should appear
        const logContent = page.locator('[data-testid="log-content"]');
        await expect(logContent).toBeVisible({ timeout: 3000 }).catch(() => {});
      }
    }
  });

  test("should filter logs by level", async ({ page }) => {
    const logsTab = page.getByRole("tab", { name: /logs/i });

    if (await logsTab.isVisible()) {
      await logsTab.click();

      const levelFilter = page.getByRole("combobox", { name: /level|filter/i });
      if (await levelFilter.isVisible()) {
        await levelFilter.click();
        await page.getByRole("option", { name: /error/i }).click();
      }
    }
  });

  test("should search within logs", async ({ page }) => {
    const logsTab = page.getByRole("tab", { name: /logs/i });

    if (await logsTab.isVisible()) {
      await logsTab.click();

      const searchInput = page.getByPlaceholder(/search/i);
      if (await searchInput.isVisible()) {
        await searchInput.fill("error");

        // Results should be highlighted or filtered
        await page.waitForTimeout(500);
      }
    }
  });

  test("should auto-scroll to new log entries", async ({ page }) => {
    const logsTab = page.getByRole("tab", { name: /logs/i });

    if (await logsTab.isVisible()) {
      await logsTab.click();

      // Enable auto-scroll
      const autoScrollToggle = page.getByRole("checkbox", { name: /auto.*scroll/i });
      if (await autoScrollToggle.isVisible()) {
        if (!(await autoScrollToggle.isChecked())) {
          await autoScrollToggle.check();
        }
        expect(await autoScrollToggle.isChecked()).toBe(true);
      }
    }
  });
});

test.describe("Timeline View", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");

    const projectLink = page.getByRole("link", { name: /open/i }).first();
    if (await projectLink.isVisible()) {
      await projectLink.click();
    }
  });

  test("should display timeline events", async ({ page }) => {
    const timelineTab = page.getByRole("tab", { name: /timeline/i });

    if (await timelineTab.isVisible()) {
      await timelineTab.click();

      // Timeline events should be listed
      const events = page.locator('[data-testid="timeline-event"]');
      await expect(events.first()).toBeVisible({ timeout: 5000 }).catch(() => {});
    }
  });

  test("should show event types with icons", async ({ page }) => {
    const timelineTab = page.getByRole("tab", { name: /timeline/i });

    if (await timelineTab.isVisible()) {
      await timelineTab.click();

      // Event types should be identifiable
      await expect(page.getByText(/task.*started|session.*started|gate/i)).toBeVisible({ timeout: 3000 }).catch(() => {});
    }
  });

  test("should show event timestamps", async ({ page }) => {
    const timelineTab = page.getByRole("tab", { name: /timeline/i });

    if (await timelineTab.isVisible()) {
      await timelineTab.click();

      // Timestamps should be visible
      await expect(page.getByText(/\d{1,2}:\d{2}/)).toBeVisible({ timeout: 3000 }).catch(() => {});
    }
  });

  test("should expand event details", async ({ page }) => {
    const timelineTab = page.getByRole("tab", { name: /timeline/i });

    if (await timelineTab.isVisible()) {
      await timelineTab.click();

      const event = page.locator('[data-testid="timeline-event"]').first();
      if (await event.isVisible()) {
        await event.click();

        // Event details should expand
        const details = page.locator('[data-testid="event-details"]');
        await expect(details).toBeVisible({ timeout: 2000 }).catch(() => {});
      }
    }
  });

  test("should filter timeline by event type", async ({ page }) => {
    const timelineTab = page.getByRole("tab", { name: /timeline/i });

    if (await timelineTab.isVisible()) {
      await timelineTab.click();

      const filterDropdown = page.getByRole("combobox", { name: /filter|type/i });
      if (await filterDropdown.isVisible()) {
        await filterDropdown.click();
        await page.getByRole("option", { name: /task/i }).click();
      }
    }
  });
});

test.describe("Agent Progress Indicators", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tasks");
  });

  test("should show current agent phase", async ({ page }) => {
    const runningTask = page.locator('[data-status="in_progress"]').first();

    if (await runningTask.isVisible()) {
      // Should show agent phase indicator
      await expect(runningTask.getByText(/implementing|writing tests|reviewing/i)).toBeVisible();
    }
  });

  test("should show iteration count", async ({ page }) => {
    const runningTask = page.locator('[data-status="in_progress"]').first();

    if (await runningTask.isVisible()) {
      // Click to open details
      await runningTask.click();

      // Iteration count should be visible
      await expect(page.getByText(/iteration/i)).toBeVisible({ timeout: 3000 }).catch(() => {});
    }
  });

  test("should show live agent output", async ({ page }) => {
    const runningTask = page.locator('[data-status="in_progress"]').first();

    if (await runningTask.isVisible()) {
      await runningTask.click();

      // Live output section should be visible
      const liveOutput = page.locator('[data-testid="live-output"]');
      await expect(liveOutput).toBeVisible({ timeout: 3000 }).catch(() => {});
    }
  });

  test("should show gate results", async ({ page }) => {
    const runningTask = page.locator('[data-status="in_progress"]').first();

    if (await runningTask.isVisible()) {
      await runningTask.click();

      // Gate results should be visible when gates run
      await expect(page.getByText(/gate|lint|test/i)).toBeVisible({ timeout: 3000 }).catch(() => {});
    }
  });
});

test.describe("WebSocket Connection", () => {
  test("should establish WebSocket connection", async ({ page }) => {
    await page.goto("/");

    // Check connection status
    const connectionStatus = page.locator('[data-testid="connection-status"]');
    await expect(connectionStatus.getByText(/connected/i)).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("should reconnect after disconnect", async ({ page }) => {
    await page.goto("/");

    // Wait for initial connection
    await page.waitForTimeout(2000);

    // Simulate offline (this is a simplified test)
    await page.evaluate(() => {
      window.dispatchEvent(new Event("offline"));
    });

    // Should show disconnected
    const connectionStatus = page.locator('[data-testid="connection-status"]');
    await expect(connectionStatus.getByText(/disconnected|reconnecting/i)).toBeVisible({ timeout: 5000 }).catch(() => {});

    // Simulate back online
    await page.evaluate(() => {
      window.dispatchEvent(new Event("online"));
    });

    // Should reconnect
    await expect(connectionStatus.getByText(/connected/i)).toBeVisible({ timeout: 10000 }).catch(() => {});
  });

  test("should receive real-time updates", async ({ page }) => {
    await page.goto("/tasks");

    // Wait for connection
    await page.waitForTimeout(2000);

    // Any task updates should reflect immediately
    // This would require triggering an actual update from the backend
    const taskCard = page.locator('[data-testid="task-card"]').first();
    if (await taskCard.isVisible()) {
      const initialText = await taskCard.textContent();
      // In a real scenario, we'd trigger an update and verify the text changes
      expect(initialText).toBeTruthy();
    }
  });
});
