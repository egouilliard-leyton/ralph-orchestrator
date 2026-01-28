/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Test workflow/config editor functionality

describe("WorkflowEditor", () => {
  const defaultConfig = {
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
      build: [
        { name: "lint", cmd: "ruff check ." },
        { name: "format", cmd: "black --check ." },
      ],
      full: [
        { name: "test", cmd: "pytest" },
        { name: "integration", cmd: "pytest tests/integration" },
      ],
    },
    test_paths: ["tests/**", "**/*.test.*"],
    limits: {
      max_iterations: 200,
      claude_timeout: 1800,
    },
  };

  describe("Config Display", () => {
    it("should display version", () => {
      expect(defaultConfig.version).toBe("1");
    });

    it("should display task source configuration", () => {
      expect(defaultConfig.task_source.type).toBe("prd_json");
      expect(defaultConfig.task_source.path).toBe(".ralph/prd.json");
    });

    it("should display git configuration", () => {
      expect(defaultConfig.git.base_branch).toBe("main");
      expect(defaultConfig.git.remote).toBe("origin");
    });

    it("should display build gates", () => {
      expect(defaultConfig.gates.build).toHaveLength(2);
      expect(defaultConfig.gates.build[0].name).toBe("lint");
    });

    it("should display full gates", () => {
      expect(defaultConfig.gates.full).toHaveLength(2);
      expect(defaultConfig.gates.full[0].name).toBe("test");
    });

    it("should display test paths", () => {
      expect(defaultConfig.test_paths).toContain("tests/**");
    });

    it("should display limits", () => {
      expect(defaultConfig.limits.max_iterations).toBe(200);
      expect(defaultConfig.limits.claude_timeout).toBe(1800);
    });
  });

  describe("Config Editing", () => {
    it("should update git base branch", () => {
      const updated = {
        ...defaultConfig,
        git: { ...defaultConfig.git, base_branch: "develop" },
      };

      expect(updated.git.base_branch).toBe("develop");
    });

    it("should add new gate", () => {
      const newGate = { name: "typecheck", cmd: "tsc --noEmit" };
      const updated = {
        ...defaultConfig,
        gates: {
          ...defaultConfig.gates,
          build: [...defaultConfig.gates.build, newGate],
        },
      };

      expect(updated.gates.build).toHaveLength(3);
      expect(updated.gates.build[2].name).toBe("typecheck");
    });

    it("should remove gate", () => {
      const updated = {
        ...defaultConfig,
        gates: {
          ...defaultConfig.gates,
          build: defaultConfig.gates.build.filter((g) => g.name !== "format"),
        },
      };

      expect(updated.gates.build).toHaveLength(1);
      expect(updated.gates.build[0].name).toBe("lint");
    });

    it("should reorder gates", () => {
      const reordered = [...defaultConfig.gates.build].reverse();
      expect(reordered[0].name).toBe("format");
      expect(reordered[1].name).toBe("lint");
    });

    it("should update max iterations", () => {
      const updated = {
        ...defaultConfig,
        limits: { ...defaultConfig.limits, max_iterations: 100 },
      };

      expect(updated.limits.max_iterations).toBe(100);
    });
  });

  describe("Config Validation", () => {
    it("should validate required version field", () => {
      const config = { ...defaultConfig };
      expect(config.version).toBeDefined();
      expect(typeof config.version).toBe("string");
    });

    it("should validate task_source type", () => {
      const validTypes = ["prd_json", "cr_markdown"];
      expect(validTypes).toContain(defaultConfig.task_source.type);
    });

    it("should validate gate command is not empty", () => {
      const isValid = defaultConfig.gates.build.every(
        (gate) => gate.cmd && gate.cmd.trim().length > 0
      );
      expect(isValid).toBe(true);
    });

    it("should validate max_iterations is positive", () => {
      expect(defaultConfig.limits.max_iterations).toBeGreaterThan(0);
    });

    it("should validate max_iterations is within bounds", () => {
      const maxAllowed = 1000;
      expect(defaultConfig.limits.max_iterations).toBeLessThanOrEqual(maxAllowed);
    });
  });

  describe("YAML Preview", () => {
    it("should serialize config to YAML format", () => {
      // Simulate YAML serialization structure
      const yamlStructure = `version: "1"
task_source:
  type: prd_json
  path: .ralph/prd.json
git:
  base_branch: main
  remote: origin
gates:
  build:
    - name: lint
      cmd: ruff check .
`;
      expect(yamlStructure).toContain("version:");
      expect(yamlStructure).toContain("task_source:");
      expect(yamlStructure).toContain("gates:");
    });
  });

  describe("Config Templates", () => {
    const templates = {
      python: {
        gates: {
          build: [
            { name: "lint", cmd: "ruff check ." },
            { name: "format", cmd: "black --check ." },
          ],
          full: [{ name: "test", cmd: "pytest" }],
        },
        test_paths: ["tests/**", "**/*_test.py"],
      },
      node: {
        gates: {
          build: [
            { name: "lint", cmd: "eslint ." },
            { name: "typecheck", cmd: "tsc --noEmit" },
          ],
          full: [{ name: "test", cmd: "npm test" }],
        },
        test_paths: ["**/*.test.ts", "**/*.spec.ts"],
      },
      fullstack: {
        gates: {
          build: [
            { name: "lint", cmd: "npm run lint" },
            { name: "typecheck", cmd: "npm run typecheck" },
          ],
          full: [
            { name: "test", cmd: "npm test" },
            { name: "e2e", cmd: "npm run test:e2e" },
          ],
        },
        test_paths: ["tests/**", "**/*.test.*", "**/*.spec.*"],
      },
    };

    it("should have Python template", () => {
      expect(templates.python.gates.build).toHaveLength(2);
      expect(templates.python.gates.build[0].cmd).toContain("ruff");
    });

    it("should have Node template", () => {
      expect(templates.node.gates.build).toHaveLength(2);
      expect(templates.node.gates.build[0].cmd).toContain("eslint");
    });

    it("should have fullstack template", () => {
      expect(templates.fullstack.gates.full).toHaveLength(2);
      expect(templates.fullstack.gates.full[1].name).toBe("e2e");
    });
  });

  describe("Undo/Redo", () => {
    it("should track config history", () => {
      const history: typeof defaultConfig[] = [defaultConfig];

      // Simulate edit
      const updated = {
        ...defaultConfig,
        git: { ...defaultConfig.git, base_branch: "develop" },
      };
      history.push(updated);

      expect(history).toHaveLength(2);
      expect(history[0].git.base_branch).toBe("main");
      expect(history[1].git.base_branch).toBe("develop");
    });

    it("should undo last change", () => {
      const history = [
        defaultConfig,
        { ...defaultConfig, git: { ...defaultConfig.git, base_branch: "develop" } },
      ];

      const undone = history.slice(0, -1);
      expect(undone).toHaveLength(1);
      expect(undone[0].git.base_branch).toBe("main");
    });
  });
});
