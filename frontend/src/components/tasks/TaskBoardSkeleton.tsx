"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function TaskBoardSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-3 h-[calc(100vh-200px)]">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="flex flex-col h-full">
          <CardHeader className="pb-2">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-4 w-40 mt-1" />
          </CardHeader>
          <CardContent className="flex-1">
            <div className="space-y-3">
              {[1, 2, 3].map((j) => (
                <Skeleton key={j} className="h-24 w-full rounded-xl" />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
