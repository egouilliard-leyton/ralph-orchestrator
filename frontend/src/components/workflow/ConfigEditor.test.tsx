import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ConfigEditor, RalphConfig } from "./ConfigEditor";

const mockConfig: RalphConfig = {
  version: "1",
  task_source: {
    type: "prd_json",
    path: ".ralph/prd.json",
  },
  git: {
    base_branch: "main",
    remote: "origin",
  },
  gates: {
    build: [{ name: "lint", cmd: "ruff check ." }],
    full: [{ name: "test", cmd: "pytest" }],
  },
  test_paths: ["tests/**", "**/*.test.*", "**/*.spec.*"],
};

describe("ConfigEditor", () => {
  describe("rendering", () => {
    it("renders loading skeleton when isLoading is true", () => {
      render(<ConfigEditor projectId="test" isLoading={true} />);
      // Should show skeletons, not the actual content
      expect(screen.queryByText("Configuration Editor")).not.toBeInTheDocument();
    });

    it("renders configuration editor header", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("Configuration Editor")).toBeInTheDocument();
    });

    it("renders YAML preview pane", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("YAML Preview")).toBeInTheDocument();
      expect(screen.getByText("Live preview of ralph.yml")).toBeInTheDocument();
    });

    it("renders all collapsible sections", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("Task Source")).toBeInTheDocument();
      expect(screen.getByText("Git Configuration")).toBeInTheDocument();
      expect(screen.getByText("Test Paths")).toBeInTheDocument();
      expect(screen.getByText("Services")).toBeInTheDocument();
      expect(screen.getByText("Limits")).toBeInTheDocument();
      expect(screen.getByText("Autopilot")).toBeInTheDocument();
    });

    it("displays Valid badge when there are no validation errors", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("Valid")).toBeInTheDocument();
    });
  });

  describe("YAML preview", () => {
    it("shows config values in YAML format", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      const preElement = document.querySelector("pre");
      expect(preElement).toBeInTheDocument();

      // Check that YAML output includes expected values
      const yamlContent = preElement?.textContent || "";
      expect(yamlContent).toContain("version: \"1\"");
      expect(yamlContent).toContain("prd_json");
      expect(yamlContent).toContain("main");
    });

    it("updates YAML preview when config changes", async () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);

      // Find and change the base branch input
      const branchInput = screen.getByDisplayValue("main");
      fireEvent.change(branchInput, { target: { value: "develop" } });

      await waitFor(() => {
        const preElement = document.querySelector("pre");
        const yamlContent = preElement?.textContent || "";
        expect(yamlContent).toContain("develop");
      });
    });
  });

  describe("form interactions", () => {
    it("toggles task source type buttons", async () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);

      // PRD JSON should be selected by default
      const prdButton = screen.getByText("PRD JSON");
      const crButton = screen.getByText("CR Markdown");

      // Click CR Markdown
      fireEvent.click(crButton);

      await waitFor(() => {
        // The YAML preview should update
        const preElement = document.querySelector("pre");
        const yamlContent = preElement?.textContent || "";
        expect(yamlContent).toContain("cr_markdown");
      });
    });

    it("updates test paths input", async () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);

      // Find the test paths input by its current value
      const testPathsInput = screen.getByDisplayValue(
        "tests/**, **/*.test.*, **/*.spec.*"
      );
      expect(testPathsInput).toBeInTheDocument();

      fireEvent.change(testPathsInput, {
        target: { value: "tests/**, spec/**" },
      });

      await waitFor(() => {
        const preElement = document.querySelector("pre");
        const yamlContent = preElement?.textContent || "";
        expect(yamlContent).toContain("spec/**");
      });
    });

    it("expands collapsed sections when clicked", async () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);

      // Services section is collapsed by default
      const servicesButton = screen.getByText("Services").closest("button");
      if (servicesButton) {
        fireEvent.click(servicesButton);
      }

      await waitFor(() => {
        expect(screen.getByText("Backend Service")).toBeInTheDocument();
      });
    });
  });

  describe("save and reset functionality", () => {
    it("calls onSave with updated config when save button clicked", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      render(
        <ConfigEditor projectId="test" config={mockConfig} onSave={onSave} />
      );

      // Make a change to enable save
      const branchInput = screen.getByDisplayValue("main");
      fireEvent.change(branchInput, { target: { value: "develop" } });

      const saveButton = screen.getByText("Save");
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(onSave).toHaveBeenCalled();
        const savedConfig = onSave.mock.calls[0][0] as RalphConfig;
        expect(savedConfig.git.base_branch).toBe("develop");
      });
    });

    it("resets form when reset button clicked", async () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);

      // Make a change
      const branchInput = screen.getByDisplayValue("main");
      fireEvent.change(branchInput, { target: { value: "develop" } });

      // Verify change was made
      expect(screen.getByDisplayValue("develop")).toBeInTheDocument();

      // Click reset
      const resetButton = screen.getByText("Reset");
      fireEvent.click(resetButton);

      await waitFor(() => {
        expect(screen.getByDisplayValue("main")).toBeInTheDocument();
      });
    });

    it("disables save button when there are no changes", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      const saveButton = screen.getByText("Save");
      expect(saveButton).toBeDisabled();
    });

    it("disables reset button when there are no changes", () => {
      render(<ConfigEditor projectId="test" config={mockConfig} />);
      const resetButton = screen.getByText("Reset");
      expect(resetButton).toBeDisabled();
    });
  });

  describe("validation", () => {
    it("calls onValidate when config changes", async () => {
      const onValidate = vi.fn().mockResolvedValue([]);
      render(
        <ConfigEditor
          projectId="test"
          config={mockConfig}
          onValidate={onValidate}
        />
      );

      // Make a change
      const branchInput = screen.getByDisplayValue("main");
      fireEvent.change(branchInput, { target: { value: "develop" } });

      // Wait for debounced validation
      await waitFor(
        () => {
          expect(onValidate).toHaveBeenCalled();
        },
        { timeout: 1000 }
      );
    });

    it("displays validation errors when present", async () => {
      const onValidate = vi
        .fn()
        .mockResolvedValue([{ path: "git.base_branch", message: "Invalid branch name" }]);

      render(
        <ConfigEditor
          projectId="test"
          config={mockConfig}
          onValidate={onValidate}
        />
      );

      // Make a change to trigger validation
      const branchInput = screen.getByDisplayValue("main");
      fireEvent.change(branchInput, { target: { value: "bad branch" } });

      await waitFor(
        () => {
          expect(screen.getByText("1 error")).toBeInTheDocument();
        },
        { timeout: 1000 }
      );
    });

    it("disables save button when validation errors exist", async () => {
      const onValidate = vi
        .fn()
        .mockResolvedValue([{ path: "git.base_branch", message: "Invalid branch" }]);

      render(
        <ConfigEditor
          projectId="test"
          config={mockConfig}
          onValidate={onValidate}
        />
      );

      // Make a change
      const branchInput = screen.getByDisplayValue("main");
      fireEvent.change(branchInput, { target: { value: "develop" } });

      await waitFor(
        () => {
          const saveButton = screen.getByText("Save");
          expect(saveButton).toBeDisabled();
        },
        { timeout: 1000 }
      );
    });
  });

  describe("YAML library edge cases", () => {
    it("handles special characters in config values", () => {
      const configWithSpecialChars: RalphConfig = {
        ...mockConfig,
        gates: {
          build: [{ name: "lint", cmd: "ruff check . --config='strict'" }],
          full: [{ name: "test", cmd: 'pytest -k "not slow"' }],
        },
      };

      render(<ConfigEditor projectId="test" config={configWithSpecialChars} />);

      const preElement = document.querySelector("pre");
      const yamlContent = preElement?.textContent || "";

      // Should properly quote strings with special characters
      expect(yamlContent).toContain("ruff check");
      expect(yamlContent).toContain("pytest");
    });

    it("handles empty arrays in config", () => {
      const configWithEmptyArrays: RalphConfig = {
        ...mockConfig,
        test_paths: [],
        gates: {
          build: [],
          full: [],
        },
      };

      render(<ConfigEditor projectId="test" config={configWithEmptyArrays} />);

      const preElement = document.querySelector("pre");
      const yamlContent = preElement?.textContent || "";

      // Empty arrays should be rendered properly
      expect(yamlContent).toContain("build: []");
      expect(yamlContent).toContain("full: []");
    });

    it("handles nested objects in services config", () => {
      const configWithServices: RalphConfig = {
        ...mockConfig,
        services: {
          backend: {
            start: { dev: "uvicorn app:main --reload", prod: "uvicorn app:main" },
            port: 8000,
            health: ["/health"],
            timeout: 30,
          },
        },
      };

      render(<ConfigEditor projectId="test" config={configWithServices} />);

      const preElement = document.querySelector("pre");
      const yamlContent = preElement?.textContent || "";

      expect(yamlContent).toContain("backend:");
      expect(yamlContent).toContain("uvicorn");
      expect(yamlContent).toContain("8000");
    });
  });
});
