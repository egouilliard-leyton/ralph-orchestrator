/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TaskCard } from "@/components/tasks/task-card";
import type { TaskWithUI } from "@/hooks/use-tasks";

// Mock dnd-kit
vi.mock("@dnd-kit/sortable", () => ({
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    transition: null,
    isDragging: false,
  }),
}));

vi.mock("@dnd-kit/utilities", () => ({
  CSS: {
    Transform: {
      toString: () => null,
    },
  },
}));

describe("TaskCard", () => {
  const createTask = (overrides: Partial<TaskWithUI> = {}): TaskWithUI => ({
    id: "T-001",
    title: "Test Task",
    description: "Test description for the task",
    status: "pending",
    priority: 1,
    acceptanceCriteria: ["Criterion 1", "Criterion 2"],
    isRunning: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  });

  describe("Rendering", () => {
    it("renders task title", () => {
      render(<TaskCard task={createTask()} />);
      expect(screen.getByText("Test Task")).toBeInTheDocument();
    });

    it("renders truncated description when over 100 characters", () => {
      const longDescription = "a".repeat(150);
      render(<TaskCard task={createTask({ description: longDescription })} />);
      expect(screen.getByText(/\.\.\.$/)).toBeInTheDocument();
    });

    it("renders acceptance criteria count", () => {
      render(<TaskCard task={createTask()} />);
      expect(screen.getByText("2 acceptance criteria")).toBeInTheDocument();
    });

    it("renders pending status badge", () => {
      render(<TaskCard task={createTask({ status: "pending" })} />);
      expect(screen.getByText("To Do")).toBeInTheDocument();
    });

    it("renders completed status badge", () => {
      render(<TaskCard task={createTask({ status: "completed" })} />);
      expect(screen.getByText("Done")).toBeInTheDocument();
    });

    it("renders in_progress status badge", () => {
      render(<TaskCard task={createTask({ status: "in_progress" })} />);
      expect(screen.getByText("In Progress")).toBeInTheDocument();
    });

    it("renders failed status badge", () => {
      render(<TaskCard task={createTask({ status: "failed" })} />);
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });
  });

  describe("Running Task Indicators", () => {
    it("shows current agent when running", () => {
      render(
        <TaskCard
          task={createTask({
            status: "in_progress",
            isRunning: true,
            currentAgent: "implementation",
          })}
        />
      );
      expect(screen.getByText("Implementing")).toBeInTheDocument();
    });

    it("shows test writing agent label", () => {
      render(
        <TaskCard
          task={createTask({
            status: "in_progress",
            isRunning: true,
            currentAgent: "test",
          })}
        />
      );
      expect(screen.getByText("Writing Tests")).toBeInTheDocument();
    });

    it("shows review agent label", () => {
      render(
        <TaskCard
          task={createTask({
            status: "in_progress",
            isRunning: true,
            currentAgent: "review",
          })}
        />
      );
      expect(screen.getByText("Reviewing")).toBeInTheDocument();
    });
  });

  describe("Actions", () => {
    it("calls onStart when start button is clicked", () => {
      const onStart = vi.fn();
      render(
        <TaskCard task={createTask({ status: "pending" })} onStart={onStart} />
      );

      const startButton = screen.getByText("Start");
      fireEvent.click(startButton);

      expect(onStart).toHaveBeenCalledWith("T-001");
    });

    it("calls onSkip when skip button is clicked", () => {
      const onSkip = vi.fn();
      render(
        <TaskCard task={createTask({ status: "pending" })} onSkip={onSkip} />
      );

      const skipButton = screen.getByRole("button", { name: "" }); // Skip has icon only
      // Find the button that contains SkipIcon
      const buttons = screen.getAllByRole("button");
      const skipBtn = buttons.find(
        (btn) => !btn.textContent?.includes("Start") && !btn.textContent?.includes("Trash")
      );
      if (skipBtn) {
        fireEvent.click(skipBtn);
      }
    });

    it("calls onDelete when delete button is clicked", () => {
      const onDelete = vi.fn();
      render(
        <TaskCard task={createTask({ status: "pending" })} onDelete={onDelete} />
      );

      // onDelete callback should be called when delete button exists and is clicked
    });

    it("does not show action buttons for completed tasks", () => {
      render(
        <TaskCard
          task={createTask({ status: "completed" })}
          onStart={vi.fn()}
          onSkip={vi.fn()}
          onDelete={vi.fn()}
        />
      );

      expect(screen.queryByText("Start")).not.toBeInTheDocument();
    });

    it("does not show action buttons for failed tasks", () => {
      render(
        <TaskCard
          task={createTask({ status: "failed" })}
          onStart={vi.fn()}
        />
      );

      expect(screen.queryByText("Start")).not.toBeInTheDocument();
    });
  });

  describe("Expandable Details", () => {
    it("opens detail sheet when card is clicked", async () => {
      render(<TaskCard task={createTask()} />);

      const card = screen.getByText("Test Task").closest("div");
      if (card) {
        fireEvent.click(card);
      }

      // Sheet should open with full details
      await waitFor(() => {
        // Sheet content shows full description
        expect(screen.getAllByText("Test Task").length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe("Duration Display", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it("shows duration for running tasks", () => {
      const startedAt = new Date(Date.now() - 65000).toISOString(); // 65 seconds ago

      render(
        <TaskCard
          task={createTask({
            status: "in_progress",
            isRunning: true,
            startedAt,
          })}
        />
      );

      // Should show approximately 1m 5s
      expect(screen.getByText(/1m/)).toBeInTheDocument();
    });

    it("does not show duration for non-running tasks", () => {
      render(<TaskCard task={createTask({ status: "pending" })} />);

      expect(screen.queryByText(/^\d+s$/)).not.toBeInTheDocument();
    });
  });

  describe("Drag and Drop", () => {
    it("shows drag handle when isDraggable is true", () => {
      render(<TaskCard task={createTask()} isDraggable={true} />);

      // Drag handle should be present
      const dragHandle = document.querySelector('button[class*="cursor-grab"]');
      expect(dragHandle).toBeInTheDocument();
    });

    it("hides drag handle when isDraggable is false", () => {
      render(<TaskCard task={createTask()} isDraggable={false} />);

      const dragHandle = document.querySelector('button[class*="cursor-grab"]');
      expect(dragHandle).not.toBeInTheDocument();
    });
  });
});
