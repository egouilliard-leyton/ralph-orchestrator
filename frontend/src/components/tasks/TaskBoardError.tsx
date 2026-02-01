"use client";

import { Button } from "@/components/ui/button";
import { AlertCircleIcon, RefreshIcon } from "@/components/ui/icons";

interface TaskBoardErrorProps {
  error: string;
  onRetry: () => void;
}

export function TaskBoardError({ error, onRetry }: TaskBoardErrorProps) {
  return (
    <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)] text-center">
      <div className="text-red-500 mb-4">
        <AlertCircleIcon size={48} />
      </div>
      <h3 className="text-lg font-semibold mb-2">Failed to load tasks</h3>
      <p className="text-sm text-muted-foreground mb-4 max-w-md">{error}</p>
      <Button onClick={onRetry}>
        <RefreshIcon className="mr-2" size={14} />
        Try Again
      </Button>
    </div>
  );
}
