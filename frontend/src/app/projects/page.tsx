"use client";

import { useCallback } from "react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { ProjectList } from "@/components/projects";
import { useProjects } from "@/hooks/use-projects";
import { api } from "@/services/api";

export default function ProjectsPage() {
  const { projects, isLoading, error, wsStatus, refetch } = useProjects();

  const handleStartAutopilot = useCallback(async (projectId: string) => {
    try {
      await api.orchestration.run(projectId);
      // The WebSocket will handle the status update
    } catch (err) {
      console.error("Failed to start autopilot:", err);
    }
  }, []);

  return (
    <>
      <Header title="Projects" />
      <main className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Projects</h2>
            <p className="text-muted-foreground">
              Manage your development projects
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              Refresh
            </Button>
            <Button>New Project</Button>
          </div>
        </div>
        <ProjectList
          projects={projects}
          isLoading={isLoading}
          error={error}
          wsStatus={wsStatus}
          onStartAutopilot={handleStartAutopilot}
        />
      </main>
    </>
  );
}
