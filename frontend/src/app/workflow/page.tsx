"use client";

import { useState, useCallback } from "react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { WorkflowEditor, ConfigEditor, WorkflowConfig, RalphConfig as EditorRalphConfig } from "@/components/workflow";
import { useConfig } from "@/hooks/use-config";
import { RalphConfig } from "@/services/api";

// Tab icons
const WorkflowIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);

const ConfigIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

type TabType = "workflow" | "config";

// Project selector (placeholder - in real app would be a dropdown with actual projects)
function ProjectSelector({
  projectId,
  onSelect,
}: {
  projectId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">Project:</span>
      <select
        value={projectId}
        onChange={(e) => onSelect(e.target.value)}
        className="text-sm border rounded px-2 py-1 bg-background"
      >
        <option value="default">Default Project</option>
        <option value="demo">Demo Project</option>
      </select>
    </div>
  );
}

// Convert API RalphConfig to WorkflowConfig format
function apiConfigToWorkflow(config: RalphConfig | null): WorkflowConfig {
  if (!config) {
    return {
      agents: [
        { id: "agent-1", type: "implementation", name: "Implementation" },
        { id: "agent-2", type: "test_writing", name: "Test Writing", guardrails: ["tests/**"] },
        { id: "agent-3", type: "review", name: "Review" },
      ],
      gates: {
        build: [],
        full: [{ id: "gate-1", type: "full", name: "test", cmd: "pytest" }],
      },
      testPaths: ["tests/**", "**/*.test.*", "**/*.spec.*"],
    };
  }

  // Build agents from config
  const agents = [];
  if (config.agents?.implementation || true) {
    agents.push({
      id: "agent-impl",
      type: "implementation" as const,
      name: "Implementation",
      model: config.agents?.implementation?.model,
      timeout: config.agents?.implementation?.timeout,
    });
  }
  if (config.agents?.test_writing || true) {
    agents.push({
      id: "agent-test",
      type: "test_writing" as const,
      name: "Test Writing",
      guardrails: config.test_paths || [],
      model: config.agents?.test_writing?.model,
      timeout: config.agents?.test_writing?.timeout,
    });
  }
  if (config.agents?.review || true) {
    agents.push({
      id: "agent-review",
      type: "review" as const,
      name: "Review",
      model: config.agents?.review?.model,
      timeout: config.agents?.review?.timeout,
    });
  }

  // Build gates
  const buildGates = (config.gates?.build || []).map((g, i) => ({
    id: `gate-build-${i}`,
    type: "build" as const,
    name: g.name,
    cmd: g.cmd,
    when: g.when,
    timeoutSeconds: g.timeout_seconds,
    fatal: g.fatal,
  }));

  const fullGates = (config.gates?.full || []).map((g, i) => ({
    id: `gate-full-${i}`,
    type: "full" as const,
    name: g.name,
    cmd: g.cmd,
    when: g.when,
    timeoutSeconds: g.timeout_seconds,
    fatal: g.fatal,
  }));

  return {
    agents,
    gates: { build: buildGates, full: fullGates },
    testPaths: config.test_paths || [],
  };
}

// Convert WorkflowConfig back to API RalphConfig format
function workflowToApiConfig(workflow: WorkflowConfig, baseConfig: RalphConfig | null): RalphConfig {
  const base = baseConfig || {
    version: "1",
    task_source: { type: "prd_json" as const, path: ".ralph/prd.json" },
    git: { base_branch: "main", remote: "origin" },
    gates: { build: [], full: [] },
  };

  return {
    ...base,
    test_paths: workflow.testPaths,
    gates: {
      build: workflow.gates.build.map((g) => ({
        name: g.name,
        cmd: g.cmd,
        when: g.when,
        timeout_seconds: g.timeoutSeconds,
        fatal: g.fatal,
      })),
      full: workflow.gates.full.map((g) => ({
        name: g.name,
        cmd: g.cmd,
        when: g.when,
        timeout_seconds: g.timeoutSeconds,
        fatal: g.fatal,
      })),
    },
    agents: {
      implementation: workflow.agents.find((a) => a.type === "implementation")
        ? { model: workflow.agents.find((a) => a.type === "implementation")?.model, timeout: workflow.agents.find((a) => a.type === "implementation")?.timeout }
        : undefined,
      test_writing: workflow.agents.find((a) => a.type === "test_writing")
        ? { model: workflow.agents.find((a) => a.type === "test_writing")?.model, timeout: workflow.agents.find((a) => a.type === "test_writing")?.timeout }
        : undefined,
      review: workflow.agents.find((a) => a.type === "review")
        ? { model: workflow.agents.find((a) => a.type === "review")?.model, timeout: workflow.agents.find((a) => a.type === "review")?.timeout }
        : undefined,
      fix: workflow.agents.find((a) => a.type === "fix")
        ? { model: workflow.agents.find((a) => a.type === "fix")?.model, timeout: workflow.agents.find((a) => a.type === "fix")?.timeout }
        : undefined,
      planning: workflow.agents.find((a) => a.type === "planning")
        ? { model: workflow.agents.find((a) => a.type === "planning")?.model, timeout: workflow.agents.find((a) => a.type === "planning")?.timeout }
        : undefined,
    },
  };
}

export default function WorkflowPage() {
  const [activeTab, setActiveTab] = useState<TabType>("workflow");
  const [projectId, setProjectId] = useState("default");

  // Use config hook
  const { config, isLoading, error, saveConfig, validateConfig } = useConfig({ projectId });

  // Convert API config to workflow format
  const workflowConfig = apiConfigToWorkflow(config);

  // Handle workflow save
  const handleWorkflowSave = useCallback(
    async (workflow: WorkflowConfig) => {
      const apiConfig = workflowToApiConfig(workflow, config);
      await saveConfig(apiConfig);
    },
    [config, saveConfig]
  );

  // Handle config save
  const handleConfigSave = useCallback(
    async (updatedConfig: EditorRalphConfig) => {
      await saveConfig(updatedConfig as RalphConfig);
    },
    [saveConfig]
  );

  // Handle config validation
  const handleConfigValidate = useCallback(
    async (updatedConfig: EditorRalphConfig) => {
      return await validateConfig(updatedConfig as RalphConfig);
    },
    [validateConfig]
  );

  return (
    <>
      <Header title="Workflow" />
      <main className="flex flex-1 flex-col h-[calc(100vh-60px)]">
        {/* Page Header */}
        <div className="flex items-center justify-between p-4 border-b shrink-0">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Workflow Editor</h2>
            <p className="text-muted-foreground">
              Design and manage your development workflows
            </p>
          </div>
          <ProjectSelector projectId={projectId} onSelect={setProjectId} />
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 p-2 border-b bg-muted/30 shrink-0">
          <Button
            variant={activeTab === "workflow" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("workflow")}
            className="flex items-center gap-2"
          >
            <WorkflowIcon />
            Pipeline Editor
          </Button>
          <Button
            variant={activeTab === "config" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("config")}
            className="flex items-center gap-2"
          >
            <ConfigIcon />
            Configuration
          </Button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="p-4 bg-destructive/10 text-destructive border-b shrink-0">
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === "workflow" ? (
            <WorkflowEditor
              projectId={projectId}
              config={workflowConfig}
              isLoading={isLoading}
              onSave={handleWorkflowSave}
            />
          ) : (
            <ConfigEditor
              projectId={projectId}
              config={config as EditorRalphConfig | undefined}
              isLoading={isLoading}
              onSave={handleConfigSave}
              onValidate={handleConfigValidate}
            />
          )}
        </div>
      </main>
    </>
  );
}
