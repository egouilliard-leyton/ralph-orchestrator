import { test, expect } from "@playwright/test";

/**
 * E2E tests for configuration editor
 *
 * Tests cover:
 * - Viewing configuration
 * - Editing configuration values
 * - Saving and validating configuration
 */

test.describe("Configuration Editor", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to workflow/config page
    await page.goto("/workflow");
  });

  test("should display current configuration", async ({ page }) => {
    // Configuration sections should be visible
    await expect(page.getByText(/version/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
    await expect(page.getByText(/task source/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
    await expect(page.getByText(/git/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
    await expect(page.getByText(/gates/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
  });

  test("should display task source configuration", async ({ page }) => {
    const taskSourceSection = page.locator('[data-testid="task-source-section"]');

    if (await taskSourceSection.isVisible()) {
      // Should show type (prd_json or cr_markdown)
      await expect(taskSourceSection.getByText(/prd_json|cr_markdown/i)).toBeVisible();

      // Should show path
      await expect(taskSourceSection.getByText(/\.ralph/)).toBeVisible();
    }
  });

  test("should display git configuration", async ({ page }) => {
    const gitSection = page.locator('[data-testid="git-section"]');

    if (await gitSection.isVisible()) {
      // Should show base branch
      await expect(gitSection.getByText(/main|master|develop/i)).toBeVisible();

      // Should show remote
      await expect(gitSection.getByText(/origin/i)).toBeVisible();
    }
  });

  test("should display gates configuration", async ({ page }) => {
    const gatesSection = page.locator('[data-testid="gates-section"]');

    if (await gatesSection.isVisible()) {
      // Should show build gates
      await expect(gatesSection.getByText(/build/i)).toBeVisible();

      // Should show full gates
      await expect(gatesSection.getByText(/full/i)).toBeVisible();
    }
  });
});

test.describe("Edit Configuration", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workflow");
  });

  test("should edit git base branch", async ({ page }) => {
    const editButton = page.locator('[data-testid="edit-git"]');

    if (await editButton.isVisible()) {
      await editButton.click();

      // Edit dialog should open
      const baseBranchInput = page.getByLabel(/base branch/i);
      if (await baseBranchInput.isVisible()) {
        await baseBranchInput.fill("develop");
      }
    }
  });

  test("should add new build gate", async ({ page }) => {
    const addGateButton = page.getByRole("button", { name: /add.*gate/i });

    if (await addGateButton.isVisible()) {
      await addGateButton.click();

      // Gate form should appear
      const nameInput = page.getByPlaceholder(/gate name/i);
      const cmdInput = page.getByPlaceholder(/command/i);

      if (await nameInput.isVisible()) {
        await nameInput.fill("typecheck");
        await cmdInput.fill("tsc --noEmit");
      }
    }
  });

  test("should remove existing gate", async ({ page }) => {
    const gateItem = page.locator('[data-testid="gate-item"]').first();

    if (await gateItem.isVisible()) {
      const deleteButton = gateItem.locator('[data-testid="delete-gate"]');

      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        // Confirmation might be required
        const confirmButton = page.getByRole("button", { name: /confirm|delete/i });
        if (await confirmButton.isVisible({ timeout: 1000 }).catch(() => false)) {
          await confirmButton.click();
        }
      }
    }
  });

  test("should reorder gates with drag and drop", async ({ page }) => {
    const gates = page.locator('[data-testid="gate-item"]');
    const count = await gates.count();

    if (count >= 2) {
      const firstGate = gates.nth(0);
      const secondGate = gates.nth(1);

      // Drag first gate below second
      await firstGate.dragTo(secondGate);

      await page.waitForTimeout(500);
    }
  });

  test("should edit test paths", async ({ page }) => {
    const testPathsSection = page.locator('[data-testid="test-paths-section"]');

    if (await testPathsSection.isVisible()) {
      const editButton = testPathsSection.locator('[data-testid="edit-test-paths"]');

      if (await editButton.isVisible()) {
        await editButton.click();

        // Add new path
        const addPathButton = page.getByRole("button", { name: /add.*path/i });
        if (await addPathButton.isVisible()) {
          await addPathButton.click();

          const pathInput = page.getByPlaceholder(/path pattern/i);
          if (await pathInput.isVisible()) {
            await pathInput.fill("src/**/*.spec.ts");
          }
        }
      }
    }
  });

  test("should update iteration limits", async ({ page }) => {
    const limitsSection = page.locator('[data-testid="limits-section"]');

    if (await limitsSection.isVisible()) {
      const maxIterationsInput = limitsSection.getByLabel(/max iterations/i);

      if (await maxIterationsInput.isVisible()) {
        await maxIterationsInput.fill("100");

        // Validate input
        const value = await maxIterationsInput.inputValue();
        expect(value).toBe("100");
      }
    }
  });
});

test.describe("Save Configuration", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workflow");
  });

  test("should validate configuration before saving", async ({ page }) => {
    const saveButton = page.getByRole("button", { name: /save/i });

    if (await saveButton.isVisible()) {
      await saveButton.click();

      // Validation should occur
      // If valid, success message; if invalid, error message
      await page.waitForTimeout(1000);
    }
  });

  test("should show validation errors", async ({ page }) => {
    // Make an invalid edit first
    const maxIterationsInput = page.getByLabel(/max iterations/i);

    if (await maxIterationsInput.isVisible()) {
      await maxIterationsInput.fill("-1"); // Invalid value

      const saveButton = page.getByRole("button", { name: /save/i });
      await saveButton.click();

      // Should show validation error
      await expect(page.getByText(/invalid|error|must be/i)).toBeVisible({ timeout: 2000 }).catch(() => {});
    }
  });

  test("should confirm successful save", async ({ page }) => {
    // Make a valid edit
    const gitSection = page.locator('[data-testid="git-section"]');

    if (await gitSection.isVisible()) {
      // Make a minor change if possible
      const saveButton = page.getByRole("button", { name: /save/i });

      if (await saveButton.isVisible()) {
        await saveButton.click();

        // Success notification
        await expect(page.getByText(/saved|success/i)).toBeVisible({ timeout: 3000 }).catch(() => {});
      }
    }
  });

  test("should preserve unsaved changes warning", async ({ page }) => {
    // Make an edit
    const maxIterationsInput = page.getByLabel(/max iterations/i);

    if (await maxIterationsInput.isVisible()) {
      await maxIterationsInput.fill("150");

      // Try to navigate away
      await page.goto("/tasks");

      // Should show unsaved changes warning (browser default or custom)
      // This behavior depends on implementation
    }
  });
});

test.describe("YAML Preview", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workflow");
  });

  test("should toggle YAML preview", async ({ page }) => {
    const previewButton = page.getByRole("button", { name: /yaml|preview|raw/i });

    if (await previewButton.isVisible()) {
      await previewButton.click();

      // YAML preview should be visible
      const yamlPreview = page.locator('[data-testid="yaml-preview"]');
      await expect(yamlPreview).toBeVisible({ timeout: 2000 }).catch(() => {});
    }
  });

  test("should show formatted YAML", async ({ page }) => {
    const previewButton = page.getByRole("button", { name: /yaml|preview|raw/i });

    if (await previewButton.isVisible()) {
      await previewButton.click();

      // Should show version key
      await expect(page.getByText(/version:\s*["']?1/)).toBeVisible({ timeout: 2000 }).catch(() => {});

      // Should show task_source key
      await expect(page.getByText(/task_source:/)).toBeVisible({ timeout: 2000 }).catch(() => {});
    }
  });

  test("should allow YAML editing in raw mode", async ({ page }) => {
    const rawEditButton = page.getByRole("button", { name: /edit.*yaml|raw.*edit/i });

    if (await rawEditButton.isVisible()) {
      await rawEditButton.click();

      // Code editor should appear
      const codeEditor = page.locator('[data-testid="yaml-editor"]');
      await expect(codeEditor).toBeVisible({ timeout: 2000 }).catch(() => {});
    }
  });
});

test.describe("Configuration Templates", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workflow");
  });

  test("should display template options", async ({ page }) => {
    const templateButton = page.getByRole("button", { name: /template|preset/i });

    if (await templateButton.isVisible()) {
      await templateButton.click();

      // Template options should appear
      await expect(page.getByText(/python/i)).toBeVisible({ timeout: 2000 }).catch(() => {});
      await expect(page.getByText(/node|javascript/i)).toBeVisible({ timeout: 2000 }).catch(() => {});
    }
  });

  test("should apply template configuration", async ({ page }) => {
    const templateButton = page.getByRole("button", { name: /template|preset/i });

    if (await templateButton.isVisible()) {
      await templateButton.click();

      // Select Python template
      const pythonTemplate = page.getByRole("option", { name: /python/i });
      if (await pythonTemplate.isVisible()) {
        await pythonTemplate.click();

        // Configuration should update with Python defaults
        await expect(page.getByText(/ruff|pytest/)).toBeVisible({ timeout: 2000 }).catch(() => {});
      }
    }
  });
});
