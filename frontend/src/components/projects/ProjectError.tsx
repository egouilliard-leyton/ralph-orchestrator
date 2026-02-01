"use client";

import { Card, CardContent } from "@/components/ui/card";
import { AlertCircleIcon } from "@/components/ui/icons";

interface ProjectErrorProps {
  error: string;
}

export function ProjectError({ error }: ProjectErrorProps) {
  return (
    <Card className="py-12">
      <CardContent className="flex flex-col items-center justify-center text-center">
        <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-4 mb-4">
          <AlertCircleIcon className="text-red-600 dark:text-red-400" size={24} />
        </div>
        <h3 className="text-lg font-semibold mb-1">Failed to load projects</h3>
        <p className="text-sm text-muted-foreground max-w-sm">{error}</p>
      </CardContent>
    </Card>
  );
}
