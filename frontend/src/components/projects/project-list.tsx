"use client";

import * as React from "react";
import { ProjectWithStats } from "@/services/api";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { useProjectFilters } from "@/hooks/use-project-filters";
import { ProjectCard } from "./project-card";
import { ProjectFilters } from "./ProjectFilters";
import { ProjectListItem } from "./ProjectListItem";
import { ProjectListSkeleton } from "./ProjectListSkeleton";
import { ProjectEmptyState } from "./ProjectEmptyState";
import { ProjectError } from "./ProjectError";

interface ProjectListProps {
  projects: ProjectWithStats[];
  isLoading: boolean;
  error: string | null;
  wsStatus?: WebSocketStatus;
  onStartAutopilot?: (projectId: string) => void;
}

export function ProjectList({
  projects,
  isLoading,
  error,
  wsStatus,
  onStartAutopilot,
}: ProjectListProps) {
  const {
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    filteredProjects,
    statusCounts,
  } = useProjectFilters({ projects });

  if (error) {
    return <ProjectError error={error} />;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Filters toolbar */}
      <ProjectFilters
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        statusCounts={statusCounts}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        wsStatus={wsStatus}
      />

      {/* Loading State */}
      {isLoading && <ProjectListSkeleton viewMode={viewMode} />}

      {/* Empty State */}
      {!isLoading && filteredProjects.length === 0 && (
        <ProjectEmptyState searchQuery={searchQuery} statusFilter={statusFilter} />
      )}

      {/* Project Grid/List */}
      {!isLoading && filteredProjects.length > 0 && (
        <>
          {viewMode === "grid" ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onStartAutopilot={onStartAutopilot}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {filteredProjects.map((project) => (
                <ProjectListItem
                  key={project.id}
                  project={project}
                  onStartAutopilot={onStartAutopilot}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Results count */}
      {!isLoading && projects.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Showing {filteredProjects.length} of {projects.length} project
          {projects.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
