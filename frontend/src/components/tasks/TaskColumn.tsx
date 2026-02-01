"use client";

import { useMemo } from "react";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { TaskCard } from "./task-card";
import type { TaskWithUI } from "@/hooks/use-tasks";

export interface ColumnConfig {
  id: string;
  title: string;
  description: string;
  status: TaskWithUI["status"];
  emptyMessage: string;
  color: string;
}

interface TaskColumnProps {
  column: ColumnConfig;
  tasks: TaskWithUI[];
  onStart?: (taskId: string) => void;
  onSkip?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
}

export function TaskColumn({
  column,
  tasks,
  onStart,
  onSkip,
  onDelete,
}: TaskColumnProps) {
  const isDraggable = column.status === "pending";
  const taskIds = useMemo(() => tasks.map((t) => t.id), [tasks]);

  return (
    <Card className={cn("flex flex-col h-full border-t-4", column.color)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{column.title}</CardTitle>
          <Badge variant="secondary" className="text-xs">
            {tasks.length}
          </Badge>
        </div>
        <CardDescription>{column.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto pb-4">
        {tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            {column.emptyMessage}
          </p>
        ) : isDraggable ? (
          <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
            <div className="space-y-3">
              {tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  isDraggable
                  onStart={onStart}
                  onSkip={onSkip}
                  onDelete={onDelete}
                />
              ))}
            </div>
          </SortableContext>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export const TASK_COLUMNS: ColumnConfig[] = [
  {
    id: "todo",
    title: "To Do",
    description: "Tasks waiting to be started",
    status: "pending",
    emptyMessage: "No pending tasks",
    color: "border-t-gray-400",
  },
  {
    id: "in-progress",
    title: "In Progress",
    description: "Tasks currently being worked on",
    status: "in_progress",
    emptyMessage: "No tasks in progress",
    color: "border-t-yellow-500",
  },
  {
    id: "done",
    title: "Done",
    description: "Tasks that have been completed",
    status: "completed",
    emptyMessage: "No completed tasks",
    color: "border-t-green-500",
  },
];
