"use client";

import { useState, useMemo, useCallback } from "react";
import { ProjectWithStats } from "@/services/api";

export type ViewMode = "grid" | "list";
export type StatusFilter = "all" | "active" | "idle" | "error";

interface UseProjectFiltersOptions {
  projects: ProjectWithStats[];
  initialViewMode?: ViewMode;
  initialStatusFilter?: StatusFilter;
  initialSearchQuery?: string;
}

interface UseProjectFiltersReturn {
  /** Current view mode */
  viewMode: ViewMode;
  /** Set view mode */
  setViewMode: (mode: ViewMode) => void;
  /** Current search query */
  searchQuery: string;
  /** Set search query */
  setSearchQuery: (query: string) => void;
  /** Current status filter */
  statusFilter: StatusFilter;
  /** Set status filter */
  setStatusFilter: (filter: StatusFilter) => void;
  /** Filtered projects */
  filteredProjects: ProjectWithStats[];
  /** Status counts for filter badges */
  statusCounts: Record<StatusFilter, number>;
  /** Whether any filters are active */
  hasActiveFilters: boolean;
  /** Clear all filters */
  clearFilters: () => void;
}

export function useProjectFilters({
  projects,
  initialViewMode = "grid",
  initialStatusFilter = "all",
  initialSearchQuery = "",
}: UseProjectFiltersOptions): UseProjectFiltersReturn {
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode);
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(initialStatusFilter);

  // Filter projects based on search and status
  const filteredProjects = useMemo(() => {
    return projects.filter((project) => {
      // Search filter
      const matchesSearch =
        searchQuery === "" ||
        project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        project.path.toLowerCase().includes(searchQuery.toLowerCase());

      // Status filter
      const matchesStatus =
        statusFilter === "all" || project.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [projects, searchQuery, statusFilter]);

  // Status counts for filter badges
  const statusCounts = useMemo(() => {
    return {
      all: projects.length,
      active: projects.filter((p) => p.status === "active").length,
      idle: projects.filter((p) => p.status === "idle").length,
      error: projects.filter((p) => p.status === "error").length,
    };
  }, [projects]);

  const hasActiveFilters = searchQuery !== "" || statusFilter !== "all";

  const clearFilters = useCallback(() => {
    setSearchQuery("");
    setStatusFilter("all");
  }, []);

  return {
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    filteredProjects,
    statusCounts,
    hasActiveFilters,
    clearFilters,
  };
}
