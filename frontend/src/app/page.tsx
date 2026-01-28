"use client";

import { useCallback } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ProjectList } from "@/components/projects";
import { useProjects } from "@/hooks/use-projects";
import { api } from "@/services/api";

function getWsStatusBadge(status: string) {
  switch (status) {
    case "connected":
      return <Badge variant="success">Live</Badge>;
    case "connecting":
      return <Badge variant="warning">Connecting</Badge>;
    case "error":
      return <Badge variant="error">Error</Badge>;
    default:
      return <Badge variant="secondary">Offline</Badge>;
  }
}

export default function DashboardPage() {
  const { projects, isLoading, error, wsStatus } = useProjects();

  // Calculate aggregated stats
  const stats = {
    activeProjects: projects.filter((p) => p.status === "active").length,
    totalProjects: projects.length,
    pendingTasks: projects.reduce((sum, p) => sum + p.taskCounts.pending, 0),
    inProgressTasks: projects.reduce((sum, p) => sum + p.taskCounts.inProgress, 0),
    completedTasks: projects.reduce((sum, p) => sum + p.taskCounts.completed, 0),
    failedTasks: projects.reduce((sum, p) => sum + p.taskCounts.failed, 0),
  };

  const handleStartAutopilot = useCallback(async (projectId: string) => {
    try {
      await api.orchestration.run(projectId);
      // The WebSocket will handle the status update
    } catch (err) {
      console.error("Failed to start autopilot:", err);
      // In a real app, show a toast notification
    }
  }, []);

  return (
    <>
      <Header title="Dashboard" />
      <main className="flex flex-1 flex-col gap-4 p-4">
        {/* Connection Status */}
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold tracking-tight">Overview</h2>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Real-time</span>
            {getWsStatusBadge(wsStatus)}
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Projects</CardTitle>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-muted-foreground"
              >
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.activeProjects}</div>
              <p className="text-xs text-muted-foreground">
                {stats.totalProjects} total project{stats.totalProjects !== 1 ? "s" : ""}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Pending Tasks</CardTitle>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-yellow-500"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                {stats.pendingTasks}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.inProgressTasks} in progress
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Completed Tasks</CardTitle>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-green-500"
              >
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {stats.completedTasks}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.failedTasks > 0
                  ? `${stats.failedTasks} failed`
                  : "All successful"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-muted-foreground"
              >
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
              </svg>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.completedTasks + stats.failedTasks > 0
                  ? `${Math.round(
                      (stats.completedTasks /
                        (stats.completedTasks + stats.failedTasks)) *
                        100
                    )}%`
                  : "N/A"}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.completedTasks + stats.failedTasks} total completed
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Projects Section */}
        <div className="mt-4">
          <h3 className="text-lg font-semibold mb-4">Projects</h3>
          <ProjectList
            projects={projects}
            isLoading={isLoading}
            error={error}
            onStartAutopilot={handleStartAutopilot}
          />
        </div>
      </main>
    </>
  );
}
