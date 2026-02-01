"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ViewMode } from "@/hooks/use-project-filters";

interface ProjectListSkeletonProps {
  viewMode: ViewMode;
  count?: number;
}

export function ProjectListSkeleton({ viewMode, count = 6 }: ProjectListSkeletonProps) {
  if (viewMode === "grid") {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: count }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-3 w-24 mt-2" />
                </div>
                <Skeleton className="h-5 w-14" />
              </div>
            </CardHeader>
            <CardContent className="pb-3">
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((j) => (
                  <Skeleton key={j} className="h-14" />
                ))}
              </div>
              <Skeleton className="h-3 w-full mt-4" />
            </CardContent>
            <div className="flex gap-2 px-6 pb-6">
              <Skeleton className="h-8 flex-1" />
              <Skeleton className="h-8 flex-1" />
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-16 ml-auto" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-24" />
        </div>
      ))}
    </div>
  );
}
