"use client";

import * as React from "react";
import Link from "next/link";
import { ProjectWithStats } from "@/services/api";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface ProjectCardProps {
  project: ProjectWithStats;
  onStartAutopilot?: (projectId: string) => void;
  className?: string;
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

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Never";

  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "Just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;

  return date.toLocaleDateString();
}

export function ProjectCard({
  project,
  onStartAutopilot,
  className,
}: ProjectCardProps) {
  const totalTasks =
    project.taskCounts.pending +
    project.taskCounts.inProgress +
    project.taskCounts.completed +
    project.taskCounts.failed;

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base truncate" title={project.name}>
              {project.name}
            </CardTitle>
            {project.currentBranch && (
              <CardDescription className="truncate mt-1" title={project.currentBranch}>
                <span className="font-mono text-xs">{project.currentBranch}</span>
              </CardDescription>
            )}
          </div>
          <Badge variant={getStatusBadgeVariant(project.status)}>
            {project.status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="flex-1 pb-3">
        {/* Task counts */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md bg-muted/50 p-2">
            <div className="text-lg font-semibold text-yellow-600 dark:text-yellow-400">
              {project.taskCounts.pending}
            </div>
            <div className="text-xs text-muted-foreground">Pending</div>
          </div>
          <div className="rounded-md bg-muted/50 p-2">
            <div className="text-lg font-semibold text-blue-600 dark:text-blue-400">
              {project.taskCounts.inProgress}
            </div>
            <div className="text-xs text-muted-foreground">In Progress</div>
          </div>
          <div className="rounded-md bg-muted/50 p-2">
            <div className="text-lg font-semibold text-green-600 dark:text-green-400">
              {project.taskCounts.completed}
            </div>
            <div className="text-xs text-muted-foreground">Completed</div>
          </div>
        </div>

        {/* Failed tasks indicator */}
        {project.taskCounts.failed > 0 && (
          <div className="mt-2 text-xs text-red-600 dark:text-red-400">
            {project.taskCounts.failed} failed task{project.taskCounts.failed !== 1 ? "s" : ""}
          </div>
        )}

        {/* Last activity */}
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>Last activity</span>
          <span>{formatRelativeTime(project.lastActivity ?? project.updatedAt)}</span>
        </div>

        {/* Total tasks progress */}
        {totalTasks > 0 && (
          <div className="mt-2">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>Progress</span>
              <span>
                {project.taskCounts.completed}/{totalTasks} tasks
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-green-500 transition-all duration-300"
                style={{
                  width: `${(project.taskCounts.completed / totalTasks) * 100}%`,
                }}
              />
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="gap-2 pt-0">
        <Button asChild variant="outline" size="sm" className="flex-1">
          <Link href={`/projects/${project.id}`}>Open</Link>
        </Button>
        <Button
          variant="default"
          size="sm"
          className="flex-1"
          onClick={() => onStartAutopilot?.(project.id)}
          disabled={project.status === "active"}
        >
          {project.status === "active" ? "Running" : "Start Autopilot"}
        </Button>
      </CardFooter>
    </Card>
  );
}
