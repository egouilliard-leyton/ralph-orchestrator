"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { LogFilter, LogLevel, LogSource } from "@/services/api";

interface UseLogViewerOptions {
  initialFilter?: LogFilter;
  onFilterChange?: (filter: LogFilter) => void;
}

interface UseLogViewerReturn {
  /** Whether auto-scroll is enabled */
  autoScroll: boolean;
  /** Toggle auto-scroll */
  toggleAutoScroll: () => void;
  /** Set auto-scroll state */
  setAutoScroll: (enabled: boolean) => void;
  /** Whether filter panel is shown */
  showFilters: boolean;
  /** Toggle filter panel visibility */
  toggleFilters: () => void;
  /** Current search input value */
  searchInput: string;
  /** Set search input value */
  setSearchInput: (value: string) => void;
  /** Handle search form submission */
  handleSearch: (e: React.FormEvent) => void;
  /** Clear search */
  clearSearch: () => void;
  /** Toggle a log level filter */
  toggleLevel: (level: LogLevel) => void;
  /** Toggle a log source filter */
  toggleSource: (source: LogSource) => void;
  /** Clear all filters */
  clearFilters: () => void;
  /** Whether any filters are active */
  hasActiveFilters: boolean;
  /** Current filter state */
  filter: LogFilter;
  /** Ref for scroll container */
  scrollRef: React.RefObject<HTMLDivElement | null>;
  /** Ref for bottom element (for auto-scroll) */
  bottomRef: React.RefObject<HTMLDivElement | null>;
  /** Handle scroll events */
  handleScroll: () => void;
}

export function useLogViewer({
  initialFilter = {},
  onFilterChange,
}: UseLogViewerOptions = {}): UseLogViewerReturn {
  const [autoScroll, setAutoScrollState] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [searchInput, setSearchInput] = useState(initialFilter.search ?? "");
  const [filter, setFilter] = useState<LogFilter>(initialFilter);

  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Sync filter changes to parent
  useEffect(() => {
    onFilterChange?.(filter);
  }, [filter, onFilterChange]);

  const setAutoScroll = useCallback((enabled: boolean) => {
    setAutoScrollState(enabled);
    if (enabled && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  const toggleAutoScroll = useCallback(() => {
    setAutoScrollState((prev) => {
      const next = !prev;
      if (next && bottomRef.current) {
        bottomRef.current.scrollIntoView({ behavior: "smooth" });
      }
      return next;
    });
  }, []);

  const toggleFilters = useCallback(() => {
    setShowFilters((prev) => !prev);
  }, []);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setFilter((prev) => ({
        ...prev,
        search: searchInput || undefined,
      }));
    },
    [searchInput]
  );

  const clearSearch = useCallback(() => {
    setSearchInput("");
    setFilter((prev) => ({
      ...prev,
      search: undefined,
    }));
  }, []);

  const toggleLevel = useCallback((level: LogLevel) => {
    setFilter((prev) => {
      const currentLevels = prev.levels ?? [];
      const newLevels = currentLevels.includes(level)
        ? currentLevels.filter((l) => l !== level)
        : [...currentLevels, level];
      return {
        ...prev,
        levels: newLevels.length > 0 ? newLevels : undefined,
      };
    });
  }, []);

  const toggleSource = useCallback((source: LogSource) => {
    setFilter((prev) => {
      const currentSources = prev.sources ?? [];
      const newSources = currentSources.includes(source)
        ? currentSources.filter((s) => s !== source)
        : [...currentSources, source];
      return {
        ...prev,
        sources: newSources.length > 0 ? newSources : undefined,
      };
    });
  }, []);

  const clearFilters = useCallback(() => {
    setSearchInput("");
    setFilter({});
  }, []);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

    if (!isAtBottom && autoScroll) {
      setAutoScrollState(false);
    }
  }, [autoScroll]);

  const hasActiveFilters = Boolean(
    filter.search ||
      (filter.levels && filter.levels.length > 0) ||
      (filter.sources && filter.sources.length > 0)
  );

  return {
    autoScroll,
    toggleAutoScroll,
    setAutoScroll,
    showFilters,
    toggleFilters,
    searchInput,
    setSearchInput,
    handleSearch,
    clearSearch,
    toggleLevel,
    toggleSource,
    clearFilters,
    hasActiveFilters,
    filter,
    scrollRef,
    bottomRef,
    handleScroll,
  };
}
