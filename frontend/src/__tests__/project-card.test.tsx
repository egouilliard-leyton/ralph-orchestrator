/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProjectCard } from "@/components/projects/project-card";
import type { ProjectWithStats } from "@/services/api";

// Mock Next.js Link
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe("ProjectCard", () => {
  const createProject = (
    overrides: Partial<ProjectWithStats> = {}
  ): ProjectWithStats => ({
    id: "test-project",
    name: "Test Project",
    path: "/path/to/project",
    status: "idle",
    currentBranch: "main",
    taskCounts: {
      pending: 3,
      inProgress: 1,
      completed: 5,
      failed: 0,
    },
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  });

  describe("Rendering", () => {
    it("renders project name", () => {
      render(<ProjectCard project={createProject()} />);
      expect(screen.getByText("Test Project")).toBeInTheDocument();
    });

    it("renders current branch", () => {
      render(<ProjectCard project={createProject({ currentBranch: "feature/test" })} />);
      expect(screen.getByText("feature/test")).toBeInTheDocument();
    });

    it("renders status badge", () => {
      render(<ProjectCard project={createProject({ status: "idle" })} />);
      expect(screen.getByText("idle")).toBeInTheDocument();
    });

    it("renders active status badge", () => {
      render(<ProjectCard project={createProject({ status: "active" })} />);
      expect(screen.getByText("active")).toBeInTheDocument();
    });

    it("renders error status badge", () => {
      render(<ProjectCard project={createProject({ status: "error" })} />);
      expect(screen.getByText("error")).toBeInTheDocument();
    });
  });

  describe("Task Counts", () => {
    it("displays pending task count", () => {
      render(<ProjectCard project={createProject()} />);
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("Pending")).toBeInTheDocument();
    });

    it("displays in progress task count", () => {
      render(<ProjectCard project={createProject()} />);
      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText("In Progress")).toBeInTheDocument();
    });

    it("displays completed task count", () => {
      render(<ProjectCard project={createProject()} />);
      expect(screen.getByText("5")).toBeInTheDocument();
      expect(screen.getByText("Completed")).toBeInTheDocument();
    });

    it("shows failed tasks indicator when present", () => {
      render(
        <ProjectCard
          project={createProject({
            taskCounts: {
              pending: 0,
              inProgress: 0,
              completed: 3,
              failed: 2,
            },
          })}
        />
      );
      expect(screen.getByText("2 failed tasks")).toBeInTheDocument();
    });

    it("does not show failed indicator when no failures", () => {
      render(
        <ProjectCard
          project={createProject({
            taskCounts: {
              pending: 1,
              inProgress: 0,
              completed: 1,
              failed: 0,
            },
          })}
        />
      );
      expect(screen.queryByText(/failed task/)).not.toBeInTheDocument();
    });
  });

  describe("Progress Bar", () => {
    it("shows progress bar when tasks exist", () => {
      render(<ProjectCard project={createProject()} />);
      expect(screen.getByText("Progress")).toBeInTheDocument();
      expect(screen.getByText("5/9 tasks")).toBeInTheDocument();
    });

    it("calculates progress percentage correctly", () => {
      const { container } = render(
        <ProjectCard
          project={createProject({
            taskCounts: {
              pending: 0,
              inProgress: 0,
              completed: 10,
              failed: 0,
            },
          })}
        />
      );

      // 100% progress
      const progressBar = container.querySelector('[class*="bg-green-500"]');
      expect(progressBar).toHaveStyle({ width: "100%" });
    });
  });

  describe("Actions", () => {
    it("renders Open button with correct link", () => {
      render(<ProjectCard project={createProject()} />);
      const openLink = screen.getByText("Open").closest("a");
      expect(openLink).toHaveAttribute("href", "/projects/test-project");
    });

    it("calls onStartAutopilot when autopilot button is clicked", () => {
      const onStartAutopilot = vi.fn();
      render(
        <ProjectCard
          project={createProject()}
          onStartAutopilot={onStartAutopilot}
        />
      );

      const autopilotButton = screen.getByText("Start Autopilot");
      fireEvent.click(autopilotButton);

      expect(onStartAutopilot).toHaveBeenCalledWith("test-project");
    });

    it("disables autopilot button when project is active", () => {
      render(
        <ProjectCard
          project={createProject({ status: "active" })}
          onStartAutopilot={vi.fn()}
        />
      );

      const runningButton = screen.getByText("Running");
      expect(runningButton).toBeDisabled();
    });

    it("enables autopilot button when project is idle", () => {
      render(
        <ProjectCard
          project={createProject({ status: "idle" })}
          onStartAutopilot={vi.fn()}
        />
      );

      const autopilotButton = screen.getByText("Start Autopilot");
      expect(autopilotButton).not.toBeDisabled();
    });
  });

  describe("Last Activity", () => {
    it("displays last activity time", () => {
      const recentDate = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 mins ago
      render(
        <ProjectCard
          project={createProject({ lastActivity: recentDate })}
        />
      );
      expect(screen.getByText("Last activity")).toBeInTheDocument();
    });

    it("displays 'Just now' for very recent activity", () => {
      const recentDate = new Date(Date.now() - 30 * 1000).toISOString(); // 30 seconds ago
      render(
        <ProjectCard
          project={createProject({ lastActivity: recentDate })}
        />
      );
      expect(screen.getByText("Just now")).toBeInTheDocument();
    });

    it("displays 'Never' when no activity date", () => {
      const project = createProject();
      delete (project as any).lastActivity;
      delete (project as any).updatedAt;
      render(<ProjectCard project={project} />);
      expect(screen.getByText("Never")).toBeInTheDocument();
    });
  });

  describe("CSS Classes", () => {
    it("applies custom className", () => {
      const { container } = render(
        <ProjectCard project={createProject()} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass("custom-class");
    });
  });
});
