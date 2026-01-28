"use client";

import { Header } from "@/components/layout/header";
import { TaskBoard } from "@/components/tasks";

export default function TasksPage() {
  return (
    <>
      <Header title="Tasks" />
      <main className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Task Board</h2>
            <p className="text-muted-foreground">
              Kanban-style task visualization with drag-and-drop
            </p>
          </div>
        </div>
        <TaskBoard />
      </main>
    </>
  );
}
