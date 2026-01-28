"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TaskBoard } from "@/components/tasks/task-board";

interface ProjectDetails {
  path: string;
  name: string;
  git_branch?: string;
  git_commit?: string;
  git_remote?: string;
  task_count: number;
  tasks_completed: number;
  tasks_pending: number;
  status: string;
  session_id?: string;
  current_task?: string;
  has_config: boolean;
  config_version?: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const [project, setProject] = useState<ProjectDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("tasks");

  // Reconstruct the project path from the catch-all route segments
  const projectId = Array.isArray(params.projectId)
    ? "/" + params.projectId.join("/")
    : params.projectId || "";

  const fetchProjectData = useCallback(async () => {
    if (!projectId) return;

    try {
      setIsLoading(true);
      setError(null);

      // Fetch project details
      const projectResponse = await fetch(
        `http://localhost:8000/api/projects/${encodeURIComponent(projectId)}`
      );
      
      if (!projectResponse.ok) {
        throw new Error(`Failed to fetch project: ${projectResponse.statusText}`);
      }
      
      const projectData: ProjectDetails = await projectResponse.json();
      setProject(projectData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProjectData();
  }, [fetchProjectData]);

  if (isLoading) {
    return (
      <>
        <Header title="Loading..." />
        <main className="flex flex-1 flex-col gap-4 p-4">
          <div className="flex items-center gap-4">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-6 w-24" />
          </div>
          <Skeleton className="h-64 w-full" />
        </main>
      </>
    );
  }

  if (error || !project) {
    return (
      <>
        <Header title="Error" />
        <main className="flex flex-1 flex-col gap-4 p-4">
          <Card className="py-12">
            <CardContent className="flex flex-col items-center justify-center text-center">
              <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-4 mb-4">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-red-600 dark:text-red-400"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-1">Failed to load project</h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-4">
                {error || "Project not found"}
              </p>
              <Button asChild variant="outline">
                <Link href="/projects">Back to Projects</Link>
              </Button>
            </CardContent>
          </Card>
        </main>
      </>
    );
  }

  const totalTasks = project.task_count;
  const completedTasks = project.tasks_completed;
  const pendingTasks = project.tasks_pending;
  const progressPercent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  return (
    <>
      <Header title={project.name} />
      <main className="flex flex-1 flex-col gap-4 p-4">
        {/* Project Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/projects">← Back</Link>
            </Button>
            <div>
              <h2 className="text-2xl font-bold tracking-tight">{project.name}</h2>
              <div className="flex items-center gap-2 mt-1">
                {project.git_branch && (
                  <span className="text-sm text-muted-foreground font-mono">
                    {project.git_branch}
                  </span>
                )}
                <Badge variant={project.status === "completed" ? "success" : "secondary"}>
                  {project.status}
                </Badge>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={fetchProjectData}>
              Refresh
            </Button>
            <Button disabled={pendingTasks === 0}>
              Start Autopilot
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Tasks</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalTasks}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Pending</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{pendingTasks}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Completed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{completedTasks}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{progressPercent}%</div>
              <div className="mt-2 h-2 w-full rounded-full bg-muted">
                <div
                  className="h-2 rounded-full bg-green-500 transition-all"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
          <TabsList>
            <TabsTrigger value="tasks">Tasks</TabsTrigger>
            <TabsTrigger value="config">Config</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="tasks" className="mt-4">
            <TaskBoard projectId={projectId} />
          </TabsContent>

          <TabsContent value="config" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Configuration</CardTitle>
                <CardDescription>ralph.yml settings for this project</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Configuration version: {project.config_version || "1"}
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  Path: {project.path}
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logs" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Logs</CardTitle>
                <CardDescription>Session logs and output</CardDescription>
              </CardHeader>
              <CardContent>
                {project.session_id ? (
                  <p className="text-muted-foreground">
                    Session: {project.session_id}
                  </p>
                ) : (
                  <p className="text-muted-foreground">No active session</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </>
  );
}
