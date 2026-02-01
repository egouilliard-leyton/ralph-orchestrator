"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProjectWithStats } from "@/services/api";
import { formatRelativeTime } from "@/lib/format-time";

interface ProjectListItemProps {
  project: ProjectWithStats;
  onStartAutopilot?: (projectId: string) => void;
}

function getStatusBadgeVariant(status: ProjectWithStats["status"]) {
  switch (status) {
    case "active":
      return "success";
    case "idle":
      return "secondary";
    case "error":
      return "error";
    default:
      return "secondary";
  }
}

export function ProjectListItem({ project, onStartAutopilot }: ProjectListItemProps) {
  const totalTasks =
    project.taskCounts.pending +
    project.taskCounts.inProgress +
    project.taskCounts.completed +
    project.taskCounts.failed;

  return (
    <div className="flex items-center gap-4 p-4 border rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{project.name}</span>
          {project.currentBranch && (
            <span className="text-xs text-muted-foreground font-mono truncate">
              {project.currentBranch}
            </span>
          )}
        </div>
      </div>

      <Badge variant={getStatusBadgeVariant(project.status)} className="shrink-0">
        {project.status}
      </Badge>

      <div className="hidden sm:flex items-center gap-4 text-sm text-muted-foreground shrink-0">
        <span className="text-yellow-600 dark:text-yellow-400">
          {project.taskCounts.pending} pending
        </span>
        <span className="text-blue-600 dark:text-blue-400">
          {project.taskCounts.inProgress} in progress
        </span>
        <span className="text-green-600 dark:text-green-400">
          {project.taskCounts.completed}/{totalTasks}
        </span>
      </div>

      <span className="hidden md:block text-xs text-muted-foreground shrink-0">
        {formatRelativeTime(project.lastActivity ?? project.updatedAt)}
      </span>

      <div className="flex items-center gap-2 shrink-0">
        <Button asChild variant="outline" size="sm">
          <Link href={`/projects/${project.id}`}>Open</Link>
        </Button>
        <Button
          variant="default"
          size="sm"
          onClick={() => onStartAutopilot?.(project.id)}
          disabled={project.status === "active"}
        >
          {project.status === "active" ? "Running" : "Autopilot"}
        </Button>
      </div>
    </div>
  );
}
