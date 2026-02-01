"use client";

import { useState, useCallback, useMemo } from "react";
import {
  DragEndEvent,
  DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";

interface UseTaskDndOptions<T extends { id: string; status: string }> {
  /** All tasks */
  tasks: T[];
  /** Callback when tasks are reordered */
  onReorder?: (taskIds: string[]) => void;
  /** Status that allows dragging (defaults to "pending") */
  draggableStatus?: string;
}

interface UseTaskDndReturn<T extends { id: string }> {
  /** DnD sensors for the DndContext */
  sensors: ReturnType<typeof useSensors>;
  /** Collision detection algorithm */
  collisionDetection: typeof closestCenter;
  /** Currently dragged task ID */
  activeId: string | null;
  /** Currently dragged task object */
  activeTask: T | undefined;
  /** Handler for drag start */
  handleDragStart: (event: DragStartEvent) => void;
  /** Handler for drag end */
  handleDragEnd: (event: DragEndEvent) => void;
  /** Handler for drag cancel */
  handleDragCancel: () => void;
}

export function useTaskDnd<T extends { id: string; status: string }>({
  tasks,
  onReorder,
  draggableStatus = "pending",
}: UseTaskDndOptions<T>): UseTaskDndReturn<T> {
  const [activeId, setActiveId] = useState<string | null>(null);

  // Configure DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Get draggable tasks
  const draggableTasks = useMemo(
    () => tasks.filter((t) => t.status === draggableStatus),
    [tasks, draggableStatus]
  );

  // Find active task
  const activeTask = useMemo(
    () => tasks.find((t) => t.id === activeId),
    [tasks, activeId]
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveId(null);

      const { active, over } = event;
      if (!over || active.id === over.id) return;

      // Only allow reordering within draggable tasks
      const activeTask = draggableTasks.find((t) => t.id === active.id);
      const overTask = draggableTasks.find((t) => t.id === over.id);

      if (!activeTask || !overTask) return;

      const oldIndex = draggableTasks.findIndex((t) => t.id === active.id);
      const newIndex = draggableTasks.findIndex((t) => t.id === over.id);

      if (oldIndex === newIndex) return;

      // Create new order
      const newOrder = [...draggableTasks];
      const [removed] = newOrder.splice(oldIndex, 1);
      if (removed) {
        newOrder.splice(newIndex, 0, removed);
      }

      // Notify parent
      onReorder?.(newOrder.map((t) => t.id));
    },
    [draggableTasks, onReorder]
  );

  const handleDragCancel = useCallback(() => {
    setActiveId(null);
  }, []);

  return {
    sensors,
    collisionDetection: closestCenter,
    activeId,
    activeTask,
    handleDragStart,
    handleDragEnd,
    handleDragCancel,
  };
}
