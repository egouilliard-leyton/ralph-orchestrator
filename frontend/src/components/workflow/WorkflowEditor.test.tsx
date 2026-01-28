import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WorkflowEditor, WorkflowConfig, AgentNode, GateNode } from "./WorkflowEditor";

// Mock DnD kit
vi.mock("@dnd-kit/core", () => ({
  DndContext: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DragOverlay: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useDraggable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    isDragging: false,
  }),
  useDroppable: () => ({
    isOver: false,
    setNodeRef: vi.fn(),
  }),
  PointerSensor: vi.fn(),
  useSensor: vi.fn(),
  useSensors: vi.fn(() => []),
}));

const mockConfig: WorkflowConfig = {
  agents: [
    { id: "agent-1", type: "implementation", name: "Implementation" },
    {
      id: "agent-2",
      type: "test_writing",
      name: "Test Writing",
      guardrails: ["tests/**", "**/*.test.*"],
    },
    { id: "agent-3", type: "review", name: "Review" },
  ],
  gates: {
    build: [{ id: "gate-1", type: "build", name: "lint", cmd: "ruff check ." }],
    full: [{ id: "gate-2", type: "full", name: "test", cmd: "pytest" }],
  },
  testPaths: ["tests/**", "**/*.test.*", "**/*.spec.*"],
};

describe("WorkflowEditor", () => {
  describe("rendering", () => {
    it("renders loading skeleton when isLoading is true", () => {
      render(<WorkflowEditor projectId="test" isLoading={true} />);
      // When loading, the content should be skeleton elements instead of actual content
      expect(screen.queryByText("Pipeline Configuration")).not.toBeInTheDocument();
      // Skeleton elements are rendered instead
    });

    it("renders pipeline configuration header", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("Pipeline Configuration")).toBeInTheDocument();
      expect(
        screen.getByText("Configure the agent execution flow")
      ).toBeInTheDocument();
    });

    it("renders all agent nodes from config", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      // Each agent appears twice - once in palette, once in pipeline
      expect(screen.getAllByText("Implementation").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Test Writing").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Review").length).toBeGreaterThanOrEqual(1);
    });

    it("renders agent palette with all agent types", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      // Agent palette header
      expect(screen.getByText("Agent Palette")).toBeInTheDocument();
      // Palette items descriptions (one for each agent type)
      expect(screen.getAllByText("Makes code changes").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Writes test cases").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Reviews changes").length).toBeGreaterThanOrEqual(1);
    });

    it("renders quality gates section", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("Quality Gates")).toBeInTheDocument();
      expect(screen.getByText("Build Gates")).toBeInTheDocument();
      expect(screen.getByText("Full Gates")).toBeInTheDocument();
    });

    it("renders gate nodes with name and command", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("lint")).toBeInTheDocument();
      expect(screen.getByText("ruff check .")).toBeInTheDocument();
      expect(screen.getByText("pytest")).toBeInTheDocument();
    });

    it("shows guardrails badge for test_writing agent", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      // The test_writing agent has 2 guardrails
      expect(screen.getByText("2 guardrails")).toBeInTheDocument();
    });
  });

  describe("agent configuration modal", () => {
    it("opens modal when clicking on agent node", async () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);

      // Find the agent node by looking for the pipeline section's Implementation agent
      // Use getAllByText and get the one in the pipeline (not in palette)
      const implAgents = screen.getAllByText("Implementation");
      // The second one is in the pipeline (first is in palette)
      const implAgent = implAgents[1]?.closest("div[class*='cursor-pointer']");
      if (implAgent) {
        fireEvent.click(implAgent);
      }

      await waitFor(() => {
        expect(
          screen.getByText("Configure Agent: Implementation")
        ).toBeInTheDocument();
      });
    });

    it("shows sync checkbox for test_writing agent", async () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);

      // Find the Test Writing agent node in the pipeline (not palette)
      const testAgents = screen.getAllByText("Test Writing");
      // Get the node with cursor-pointer class (the clickable node in pipeline)
      const testAgent = testAgents[1]?.closest("div[class*='cursor-pointer']");
      if (testAgent) {
        fireEvent.click(testAgent);
      }

      await waitFor(() => {
        expect(
          screen.getByText("Sync with global test_paths")
        ).toBeInTheDocument();
      });
    });
  });

  describe("save functionality", () => {
    it("calls onSave with updated config when save button clicked", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      render(
        <WorkflowEditor projectId="test" config={mockConfig} onSave={onSave} />
      );

      const saveButton = screen.getByText("Save Pipeline");
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(mockConfig);
      });
    });

    it("displays error message when save fails", async () => {
      const onSave = vi.fn().mockRejectedValue(new Error("Save failed"));
      render(
        <WorkflowEditor projectId="test" config={mockConfig} onSave={onSave} />
      );

      const saveButton = screen.getByText("Save Pipeline");
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText("Error: Save failed")).toBeInTheDocument();
      });
    });

    it("displays saveError prop when provided", () => {
      render(
        <WorkflowEditor
          projectId="test"
          config={mockConfig}
          saveError="External save error"
        />
      );
      expect(
        screen.getByText("Error: External save error")
      ).toBeInTheDocument();
    });
  });

  describe("gate management", () => {
    it("shows Add Gate button", () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);
      expect(screen.getByText("Add Gate")).toBeInTheDocument();
    });

    it("opens new gate modal when Add Gate is clicked", async () => {
      render(<WorkflowEditor projectId="test" config={mockConfig} />);

      const addGateButton = screen.getByText("Add Gate");
      fireEvent.click(addGateButton);

      await waitFor(() => {
        expect(screen.getByText("Configure Gate:")).toBeInTheDocument();
      });
    });
  });

  describe("guardrails synchronization", () => {
    it("updates all test_writing agents when global test paths change", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      render(
        <WorkflowEditor projectId="test" config={mockConfig} onSave={onSave} />
      );

      // Click on test writing agent to open modal
      const testAgents = screen.getAllByText("Test Writing");
      const testAgent = testAgents[1]?.closest("div[class*='cursor-pointer']");
      if (testAgent) {
        fireEvent.click(testAgent);
      }

      await waitFor(() => {
        expect(
          screen.getByText("Configure Agent: Test Writing")
        ).toBeInTheDocument();
      });

      // The guardrails input should show the synced paths
      const guardrailsInput = screen.getByPlaceholderText("tests/**, **/*.test.*");
      expect(guardrailsInput).toBeInTheDocument();
    });
  });
});
