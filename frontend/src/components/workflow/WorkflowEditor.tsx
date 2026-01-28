"use client";

import { useState, useCallback, useMemo } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  useDraggable,
  useDroppable,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

// Icons
const CodeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 18 22 12 16 6" />
    <polyline points="8 6 2 12 8 18" />
  </svg>
);

const TestIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
    <polyline points="14 2 14 8 20 8" />
    <path d="m9 15 2 2 4-4" />
  </svg>
);

const GateIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

const ReviewIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const PlusIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </svg>
);

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18" />
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
  </svg>
);

const GripIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="9" cy="5" r="1" />
    <circle cx="9" cy="12" r="1" />
    <circle cx="9" cy="19" r="1" />
    <circle cx="15" cy="5" r="1" />
    <circle cx="15" cy="12" r="1" />
    <circle cx="15" cy="19" r="1" />
  </svg>
);

const ArrowRightIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </svg>
);

// Types
export type AgentType = "implementation" | "test_writing" | "review" | "fix" | "planning";
export type GateType = "build" | "full";

export interface AgentNode {
  id: string;
  type: AgentType;
  name: string;
  model?: string;
  timeout?: number;
  allowedTools?: string[];
  guardrails?: string[];
}

export interface GateNode {
  id: string;
  type: GateType;
  name: string;
  cmd: string;
  when?: string;
  timeoutSeconds?: number;
  fatal?: boolean;
}

export interface AgentRoleConfig {
  model?: string;
  timeout?: number;
  allowed_tools?: string[];
}

export interface WorkflowConfig {
  agents: AgentNode[];
  gates: {
    build: GateNode[];
    full: GateNode[];
  };
  testPaths: string[];
  agentRoles?: {
    implementation?: AgentRoleConfig;
    test_writing?: AgentRoleConfig;
    review?: AgentRoleConfig;
    fix?: AgentRoleConfig;
    planning?: AgentRoleConfig;
  };
}

interface WorkflowEditorProps {
  projectId: string;
  config?: WorkflowConfig;
  isLoading?: boolean;
  onSave?: (config: WorkflowConfig) => Promise<void>;
  /** Error message from save operation */
  saveError?: string;
}

// Agent palette items
const agentPaletteItems: { type: AgentType; name: string; description: string }[] = [
  { type: "implementation", name: "Implementation", description: "Makes code changes" },
  { type: "test_writing", name: "Test Writing", description: "Writes test cases" },
  { type: "review", name: "Review", description: "Reviews changes" },
  { type: "fix", name: "Fix", description: "Fixes issues" },
  { type: "planning", name: "Planning", description: "Plans approach" },
];

// Default workflow configuration
const defaultConfig: WorkflowConfig = {
  agents: [
    { id: "agent-1", type: "implementation", name: "Implementation" },
    { id: "agent-2", type: "test_writing", name: "Test Writing", guardrails: ["tests/**", "**/*.test.*"] },
    { id: "agent-3", type: "review", name: "Review" },
  ],
  gates: {
    build: [
      { id: "gate-1", type: "build", name: "lint", cmd: "ruff check ." },
    ],
    full: [
      { id: "gate-2", type: "full", name: "test", cmd: "pytest" },
    ],
  },
  testPaths: ["tests/**", "**/*.test.*", "**/*.spec.*"],
};

// Draggable palette item component
function PaletteItem({ type, name, description }: { type: AgentType; name: string; description: string }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette-${type}`,
    data: { type, name, isPalette: true },
  });

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn(
        "flex items-center gap-2 p-2 rounded-md border cursor-grab transition-colors",
        "hover:bg-accent hover:border-accent",
        isDragging && "opacity-50"
      )}
    >
      <div className="text-muted-foreground">
        <GripIcon />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{name}</div>
        <div className="text-xs text-muted-foreground truncate">{description}</div>
      </div>
    </div>
  );
}

// Node component for agents in the pipeline
function AgentNodeComponent({
  node,
  onClick,
  onRemove,
}: {
  node: AgentNode;
  onClick: () => void;
  onRemove: () => void;
}) {
  const getIcon = (type: AgentType) => {
    switch (type) {
      case "implementation":
      case "fix":
        return <CodeIcon />;
      case "test_writing":
        return <TestIcon />;
      case "review":
        return <ReviewIcon />;
      case "planning":
        return <ReviewIcon />;
      default:
        return <CodeIcon />;
    }
  };

  const getColor = (type: AgentType) => {
    switch (type) {
      case "implementation":
        return "border-blue-500 bg-blue-50 dark:bg-blue-950/30";
      case "test_writing":
        return "border-green-500 bg-green-50 dark:bg-green-950/30";
      case "review":
        return "border-purple-500 bg-purple-50 dark:bg-purple-950/30";
      case "fix":
        return "border-orange-500 bg-orange-50 dark:bg-orange-950/30";
      case "planning":
        return "border-cyan-500 bg-cyan-50 dark:bg-cyan-950/30";
      default:
        return "border-gray-500 bg-gray-50 dark:bg-gray-950/30";
    }
  };

  return (
    <div
      className={cn(
        "relative group w-40 p-3 rounded-lg border-2 cursor-pointer transition-all",
        "hover:shadow-md",
        getColor(node.type)
      )}
      onClick={onClick}
    >
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="absolute -top-2 -right-2 p-1 rounded-full bg-destructive text-white opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <TrashIcon />
      </button>
      <div className="flex items-center gap-2 mb-2">
        <div className="text-foreground">{getIcon(node.type)}</div>
        <span className="font-medium text-sm">{node.name}</span>
      </div>
      <div className="text-xs text-muted-foreground capitalize">{node.type.replace("_", " ")}</div>
      {node.guardrails && node.guardrails.length > 0 && (
        <Badge variant="secondary" className="mt-2 text-xs">
          {node.guardrails.length} guardrail{node.guardrails.length > 1 ? "s" : ""}
        </Badge>
      )}
    </div>
  );
}

// Gate node component
function GateNodeComponent({
  gate,
  onEdit,
  onRemove,
}: {
  gate: GateNode;
  onEdit: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      className={cn(
        "relative group w-36 p-3 rounded-lg border-2 cursor-pointer transition-all",
        "hover:shadow-md",
        gate.type === "build"
          ? "border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30"
          : "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/30"
      )}
      onClick={onEdit}
    >
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="absolute -top-2 -right-2 p-1 rounded-full bg-destructive text-white opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <TrashIcon />
      </button>
      <div className="flex items-center gap-2 mb-2">
        <div className="text-foreground">
          <GateIcon />
        </div>
        <span className="font-medium text-sm truncate">{gate.name}</span>
      </div>
      <div className="text-xs text-muted-foreground truncate font-mono">{gate.cmd}</div>
      <Badge variant="outline" className="mt-2 text-xs capitalize">
        {gate.type}
      </Badge>
    </div>
  );
}

// Drop zone for new agents
function DropZone({ id }: { id: string }) {
  const { isOver, setNodeRef } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "w-32 h-20 rounded-lg border-2 border-dashed flex items-center justify-center transition-colors",
        isOver ? "border-primary bg-primary/10" : "border-muted-foreground/30"
      )}
    >
      <PlusIcon />
    </div>
  );
}

// Agent configuration modal
function AgentConfigModal({
  agent,
  open,
  onClose,
  onSave,
  globalTestPaths,
  onUpdateGlobalTestPaths,
}: {
  agent: AgentNode | null;
  open: boolean;
  onClose: () => void;
  onSave: (agent: AgentNode) => void;
  /** Global test_paths from config - used as default guardrails for test_writing agents */
  globalTestPaths: string[];
  /** Callback to update global test_paths when guardrails change for test_writing agent */
  onUpdateGlobalTestPaths?: (paths: string[]) => void;
}) {
  const [formData, setFormData] = useState<Partial<AgentNode>>({});
  const [syncWithGlobal, setSyncWithGlobal] = useState(true);

  // Initialize form when agent changes
  const currentAgent = agent;
  if (currentAgent && formData.id !== currentAgent.id) {
    // For test_writing agents, check if guardrails match global test_paths
    const isTestWritingAgent = currentAgent.type === "test_writing";
    const guardrailsMatchGlobal = isTestWritingAgent &&
      JSON.stringify(currentAgent.guardrails?.sort()) === JSON.stringify(globalTestPaths.sort());

    setFormData({ ...currentAgent });
    setSyncWithGlobal(isTestWritingAgent && (guardrailsMatchGlobal || !currentAgent.guardrails?.length));
  }

  const handleSave = () => {
    if (formData.id) {
      const updatedAgent = formData as AgentNode;

      // If test_writing agent with sync enabled, update global test_paths
      if (updatedAgent.type === "test_writing" && syncWithGlobal && onUpdateGlobalTestPaths) {
        onUpdateGlobalTestPaths(updatedAgent.guardrails || []);
      }

      onSave(updatedAgent);
      onClose();
    }
  };

  const isTestWritingAgent = agent?.type === "test_writing";

  // When sync is enabled, guardrails should reflect global test_paths
  const effectiveGuardrails = isTestWritingAgent && syncWithGlobal
    ? globalTestPaths
    : formData.guardrails || [];

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configure Agent: {agent?.name}</DialogTitle>
          <DialogDescription>
            Customize the agent&apos;s behavior and constraints
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Name</label>
            <Input
              value={formData.name || ""}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Model (optional)</label>
            <Input
              value={formData.model || ""}
              onChange={(e) => setFormData({ ...formData, model: e.target.value })}
              placeholder="claude-sonnet-4-20250514"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Timeout (seconds)</label>
            <Input
              type="number"
              value={formData.timeout || 1800}
              onChange={(e) => setFormData({ ...formData, timeout: parseInt(e.target.value) || 1800 })}
            />
          </div>
          {isTestWritingAgent && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="sync-guardrails"
                  checked={syncWithGlobal}
                  onChange={(e) => {
                    setSyncWithGlobal(e.target.checked);
                    if (e.target.checked) {
                      // Sync guardrails with global test_paths
                      setFormData({ ...formData, guardrails: [...globalTestPaths] });
                    }
                  }}
                  className="rounded"
                />
                <label htmlFor="sync-guardrails" className="text-sm font-medium">
                  Sync with global test_paths
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                When enabled, guardrails are synchronized with the project&apos;s test_paths config
              </p>
            </div>
          )}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              Guardrails (allowed file paths)
              {isTestWritingAgent && syncWithGlobal && (
                <Badge variant="secondary" className="ml-2 text-xs">Synced</Badge>
              )}
            </label>
            <Input
              value={effectiveGuardrails.join(", ")}
              onChange={(e) => {
                const newGuardrails = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                setFormData({ ...formData, guardrails: newGuardrails });
                // If editing while synced, disable sync
                if (isTestWritingAgent && syncWithGlobal) {
                  setSyncWithGlobal(false);
                }
              }}
              placeholder="tests/**, **/*.test.*"
              disabled={isTestWritingAgent && syncWithGlobal}
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated glob patterns. Files outside these patterns cannot be modified.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Gate configuration modal
function GateConfigModal({
  gate,
  open,
  onClose,
  onSave,
}: {
  gate: GateNode | null;
  open: boolean;
  onClose: () => void;
  onSave: (gate: GateNode) => void;
}) {
  const [formData, setFormData] = useState<Partial<GateNode>>({});

  // Initialize form when gate changes
  const currentGate = gate;
  if (currentGate && formData.id !== currentGate.id) {
    setFormData({ ...currentGate });
  }

  const handleSave = () => {
    if (formData.id && formData.name && formData.cmd) {
      onSave(formData as GateNode);
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configure Gate: {gate?.name}</DialogTitle>
          <DialogDescription>
            Set up the quality gate command and options
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Name</label>
            <Input
              value={formData.name || ""}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="lint, test, build..."
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Command</label>
            <Input
              value={formData.cmd || ""}
              onChange={(e) => setFormData({ ...formData, cmd: e.target.value })}
              placeholder="pytest, ruff check ., npm test..."
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Type</label>
            <div className="flex gap-2">
              <Button
                variant={formData.type === "build" ? "default" : "outline"}
                size="sm"
                onClick={() => setFormData({ ...formData, type: "build" })}
              >
                Build (Fast)
              </Button>
              <Button
                variant={formData.type === "full" ? "default" : "outline"}
                size="sm"
                onClick={() => setFormData({ ...formData, type: "full" })}
              >
                Full (Comprehensive)
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Condition (optional)</label>
            <Input
              value={formData.when || ""}
              onChange={(e) => setFormData({ ...formData, when: e.target.value })}
              placeholder="*.py, package.json..."
            />
            <p className="text-xs text-muted-foreground">
              File pattern that must exist for gate to run
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Timeout (seconds)</label>
            <Input
              type="number"
              value={formData.timeoutSeconds || 300}
              onChange={(e) => setFormData({ ...formData, timeoutSeconds: parseInt(e.target.value) || 300 })}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="fatal"
              checked={formData.fatal !== false}
              onChange={(e) => setFormData({ ...formData, fatal: e.target.checked })}
              className="rounded"
            />
            <label htmlFor="fatal" className="text-sm">
              Fatal (failure stops execution)
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Loading skeleton
function WorkflowEditorSkeleton() {
  return (
    <div className="flex h-full">
      <div className="w-64 p-4 border-r">
        <Skeleton className="h-6 w-32 mb-4" />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
      <div className="flex-1 p-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="flex items-center gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 w-40" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function WorkflowEditor({ projectId, config: initialConfig, isLoading, onSave, saveError }: WorkflowEditorProps) {
  const [config, setConfig] = useState<WorkflowConfig>(initialConfig || defaultConfig);
  const [selectedAgent, setSelectedAgent] = useState<AgentNode | null>(null);
  const [selectedGate, setSelectedGate] = useState<GateNode | null>(null);
  const [agentModalOpen, setAgentModalOpen] = useState(false);
  const [gateModalOpen, setGateModalOpen] = useState(false);
  const [newGateModalOpen, setNewGateModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  // Sync config when initialConfig changes
  const prevInitialConfig = useMemo(() => initialConfig, [initialConfig]);
  if (prevInitialConfig !== initialConfig && initialConfig) {
    setConfig(initialConfig);
  }

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // Handle drag start
  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  }, []);

  // Handle drag end
  const handleDragEnd = useCallback((event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;

    if (!over) return;

    const activeData = active.data.current as { type: AgentType; name: string; isPalette?: boolean };

    if (activeData.isPalette && over.id === "pipeline-drop-zone") {
      // Add new agent from palette
      const newAgent: AgentNode = {
        id: `agent-${Date.now()}`,
        type: activeData.type,
        name: activeData.name,
        guardrails: activeData.type === "test_writing" ? config.testPaths : undefined,
      };
      setConfig((prev) => ({
        ...prev,
        agents: [...prev.agents, newAgent],
      }));
    }
  }, [config.testPaths]);

  // Handle removing an agent
  const handleRemoveAgent = useCallback((agentId: string) => {
    setConfig((prev) => ({
      ...prev,
      agents: prev.agents.filter((a) => a.id !== agentId),
    }));
  }, []);

  // Handle updating an agent
  const handleUpdateAgent = useCallback((updatedAgent: AgentNode) => {
    setConfig((prev) => ({
      ...prev,
      agents: prev.agents.map((a) => (a.id === updatedAgent.id ? updatedAgent : a)),
    }));
  }, []);

  // Handle removing a gate
  const handleRemoveGate = useCallback((gateId: string, gateType: GateType) => {
    setConfig((prev) => ({
      ...prev,
      gates: {
        ...prev.gates,
        [gateType]: prev.gates[gateType].filter((g) => g.id !== gateId),
      },
    }));
  }, []);

  // Handle updating a gate
  const handleUpdateGate = useCallback((updatedGate: GateNode) => {
    setConfig((prev) => ({
      ...prev,
      gates: {
        ...prev.gates,
        [updatedGate.type]: prev.gates[updatedGate.type].map((g) =>
          g.id === updatedGate.id ? updatedGate : g
        ),
      },
    }));
  }, []);

  // Handle adding a new gate
  const handleAddGate = useCallback((gate: GateNode) => {
    setConfig((prev) => ({
      ...prev,
      gates: {
        ...prev.gates,
        [gate.type]: [...prev.gates[gate.type], gate],
      },
    }));
  }, []);

  // Handle updating global test paths (for guardrails sync)
  const handleUpdateGlobalTestPaths = useCallback((paths: string[]) => {
    setConfig((prev) => {
      // Update testPaths
      const newConfig = { ...prev, testPaths: paths };

      // Also update guardrails of all test_writing agents to stay in sync
      newConfig.agents = prev.agents.map((agent) => {
        if (agent.type === "test_writing") {
          return { ...agent, guardrails: paths };
        }
        return agent;
      });

      return newConfig;
    });
  }, []);

  // Handle save
  const handleSave = useCallback(async () => {
    if (!onSave) return;
    setIsSaving(true);
    setLocalError(null);
    try {
      await onSave(config);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  }, [config, onSave]);

  // Active drag item
  const activePaletteItem = useMemo(() => {
    if (!activeId) return null;
    const item = agentPaletteItems.find((i) => `palette-${i.type}` === activeId);
    return item;
  }, [activeId]);

  if (isLoading) {
    return <WorkflowEditorSkeleton />;
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex h-full">
        {/* Agent Palette Sidebar */}
        <div className="w-64 border-r bg-muted/30 flex flex-col">
          <div className="p-4 border-b">
            <h3 className="font-semibold text-sm">Agent Palette</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Drag agents to the pipeline
            </p>
          </div>
          <div className="flex-1 p-4 space-y-2 overflow-y-auto">
            {agentPaletteItems.map((item) => (
              <PaletteItem key={item.type} {...item} />
            ))}
          </div>
        </div>

        {/* Main Pipeline Editor */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <div className="p-4 border-b flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Pipeline Configuration</h3>
              <p className="text-sm text-muted-foreground">
                Configure the agent execution flow
              </p>
              {(saveError || localError) && (
                <p className="text-sm text-destructive mt-1">
                  Error: {saveError || localError}
                </p>
              )}
            </div>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save Pipeline"}
            </Button>
          </div>

          {/* Pipeline Visualization */}
          <div className="flex-1 p-6 overflow-auto">
            {/* Agent Pipeline */}
            <div className="mb-8">
              <h4 className="text-sm font-medium text-muted-foreground mb-4">Agent Pipeline</h4>
              <div className="flex items-center gap-4 flex-wrap">
                {config.agents.map((agent, index) => (
                  <div key={agent.id} className="flex items-center gap-4">
                    <AgentNodeComponent
                      node={agent}
                      onClick={() => {
                        setSelectedAgent(agent);
                        setAgentModalOpen(true);
                      }}
                      onRemove={() => handleRemoveAgent(agent.id)}
                    />
                    {index < config.agents.length - 1 && (
                      <div className="text-muted-foreground">
                        <ArrowRightIcon />
                      </div>
                    )}
                  </div>
                ))}
                <div className="flex items-center gap-4">
                  {config.agents.length > 0 && (
                    <div className="text-muted-foreground">
                      <ArrowRightIcon />
                    </div>
                  )}
                  <DropZone id="pipeline-drop-zone" />
                </div>
              </div>
            </div>

            {/* Quality Gates */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-medium text-muted-foreground">Quality Gates</h4>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSelectedGate({
                      id: `gate-${Date.now()}`,
                      type: "build",
                      name: "",
                      cmd: "",
                      timeoutSeconds: 300,
                      fatal: true,
                    });
                    setNewGateModalOpen(true);
                  }}
                >
                  <PlusIcon /> Add Gate
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-6">
                {/* Build Gates */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Build Gates</CardTitle>
                    <CardDescription>Fast checks during task loop</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-3">
                      {config.gates.build.map((gate) => (
                        <GateNodeComponent
                          key={gate.id}
                          gate={gate}
                          onEdit={() => {
                            setSelectedGate(gate);
                            setGateModalOpen(true);
                          }}
                          onRemove={() => handleRemoveGate(gate.id, "build")}
                        />
                      ))}
                      {config.gates.build.length === 0 && (
                        <p className="text-sm text-muted-foreground">No build gates configured</p>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Full Gates */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Full Gates</CardTitle>
                    <CardDescription>Comprehensive checks after completion</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-3">
                      {config.gates.full.map((gate) => (
                        <GateNodeComponent
                          key={gate.id}
                          gate={gate}
                          onEdit={() => {
                            setSelectedGate(gate);
                            setGateModalOpen(true);
                          }}
                          onRemove={() => handleRemoveGate(gate.id, "full")}
                        />
                      ))}
                      {config.gates.full.length === 0 && (
                        <p className="text-sm text-muted-foreground">No full gates configured</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Drag Overlay */}
      <DragOverlay>
        {activePaletteItem && (
          <div className="flex items-center gap-2 p-2 rounded-md border bg-background shadow-lg">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{activePaletteItem.name}</div>
              <div className="text-xs text-muted-foreground">{activePaletteItem.description}</div>
            </div>
          </div>
        )}
      </DragOverlay>

      {/* Modals */}
      <AgentConfigModal
        agent={selectedAgent}
        open={agentModalOpen}
        onClose={() => {
          setAgentModalOpen(false);
          setSelectedAgent(null);
        }}
        onSave={handleUpdateAgent}
        globalTestPaths={config.testPaths}
        onUpdateGlobalTestPaths={handleUpdateGlobalTestPaths}
      />

      <GateConfigModal
        gate={selectedGate}
        open={gateModalOpen}
        onClose={() => {
          setGateModalOpen(false);
          setSelectedGate(null);
        }}
        onSave={handleUpdateGate}
      />

      <GateConfigModal
        gate={selectedGate}
        open={newGateModalOpen}
        onClose={() => {
          setNewGateModalOpen(false);
          setSelectedGate(null);
        }}
        onSave={(gate) => {
          handleAddGate(gate);
          setNewGateModalOpen(false);
          setSelectedGate(null);
        }}
      />
    </DndContext>
  );
}

export default WorkflowEditor;
