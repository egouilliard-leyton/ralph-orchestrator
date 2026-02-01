"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FolderIcon } from "@/components/ui/icons";
import { StatusFilter } from "@/hooks/use-project-filters";

interface ProjectEmptyStateProps {
  searchQuery: string;
  statusFilter: StatusFilter;
}

export function ProjectEmptyState({ searchQuery, statusFilter }: ProjectEmptyStateProps) {
  const hasFilters = searchQuery || statusFilter !== "all";

  return (
    <Card className="py-12">
      <CardContent className="flex flex-col items-center justify-center text-center">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FolderIcon className="text-muted-foreground" size={24} />
        </div>
        {hasFilters ? (
          <>
            <h3 className="text-lg font-semibold mb-1">No matching projects</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              No projects match your current search or filters. Try adjusting your criteria.
            </p>
          </>
        ) : (
          <>
            <h3 className="text-lg font-semibold mb-1">No projects yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-4">
              Get started by creating your first project or initializing an existing directory.
            </p>
            <Button asChild>
              <Link href="/projects/new">Create Project</Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
