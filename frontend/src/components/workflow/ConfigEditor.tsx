"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { stringify as yamlStringify } from "yaml";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// Icons
const SaveIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </svg>
);

const ResetIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
  </svg>
);

const AlertCircleIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" x2="12" y1="8" y2="12" />
    <line x1="12" x2="12.01" y1="16" y2="16" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

// Types
export interface RalphConfig {
  version: string;
  task_source: {
    type: "prd_json" | "cr_markdown";
    path: string;
  };
  git: {
    base_branch: string;
    remote: string;
  };
  gates: {
    build: Array<{
      name: string;
      cmd: string;
      when?: string;
      timeout_seconds?: number;
      fatal?: boolean;
    }>;
    full: Array<{
      name: string;
      cmd: string;
      when?: string;
      timeout_seconds?: number;
      fatal?: boolean;
    }>;
  };
  test_paths?: string[];
  services?: {
    backend?: {
      start: { dev?: string; prod?: string };
      port: number;
      health?: string[];
      timeout?: number;
    };
    frontend?: {
      build?: string;
      serve: { dev?: string; prod?: string };
      port: number;
      timeout?: number;
    };
  };
  limits?: {
    claude_timeout?: number;
    max_iterations?: number;
    post_verify_iterations?: number;
    ui_fix_iterations?: number;
    robot_fix_iterations?: number;
  };
  autopilot?: {
    enabled?: boolean;
    reports_dir?: string;
    branch_prefix?: string;
    create_pr?: boolean;
  };
}

interface ValidationError {
  path: string;
  message: string;
}

interface ConfigEditorProps {
  projectId: string;
  config?: RalphConfig;
  isLoading?: boolean;
  onSave?: (config: RalphConfig) => Promise<void>;
  onValidate?: (config: RalphConfig) => Promise<ValidationError[]>;
}

// Default configuration
const defaultConfig: RalphConfig = {
  version: "1",
  task_source: {
    type: "prd_json",
    path: ".ralph/prd.json",
  },
  git: {
    base_branch: "main",
    remote: "origin",
  },
  gates: {
    build: [],
    full: [{ name: "test", cmd: "pytest" }],
  },
  test_paths: ["tests/**", "**/*.test.*", "**/*.spec.*"],
};

// Collapsible section component
function CollapsibleSection({
  title,
  description,
  children,
  defaultOpen = true,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border rounded-lg">
      <button
        className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/50 transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div>
          <h4 className="font-medium">{title}</h4>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        <div className="text-muted-foreground">
          {isOpen ? <ChevronDownIcon /> : <ChevronRightIcon />}
        </div>
      </button>
      {isOpen && (
        <div className="p-4 pt-0 border-t">
          {children}
        </div>
      )}
    </div>
  );
}

// Form field component
function FormField({
  label,
  description,
  error,
  children,
}: {
  label: string;
  description?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {description && !error && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      {error && (
        <p className="text-xs text-destructive flex items-center gap-1">
          <AlertCircleIcon /> {error}
        </p>
      )}
    </div>
  );
}

// YAML preview component
function YamlPreview({ config }: { config: RalphConfig }) {
  const yaml = useMemo(() => {
    return configToYaml(config);
  }, [config]);

  return (
    <pre className="text-xs font-mono bg-muted p-4 rounded-lg overflow-auto h-full">
      <code>{yaml}</code>
    </pre>
  );
}

/**
 * Convert config object to YAML string using the yaml library.
 * This properly handles edge cases like special characters, multiline strings,
 * and maintains consistent formatting.
 */
function configToYaml(config: RalphConfig): string {
  // Build the config object in the desired key order for ralph.yml
  const orderedConfig: Record<string, unknown> = {
    version: config.version,
    task_source: config.task_source,
    git: config.git,
  };

  // Add test_paths if present
  if (config.test_paths && config.test_paths.length > 0) {
    orderedConfig.test_paths = config.test_paths;
  }

  // Add gates
  orderedConfig.gates = {
    build: config.gates.build.map((gate) => {
      const gateObj: Record<string, unknown> = {
        name: gate.name,
        cmd: gate.cmd,
      };
      if (gate.when) gateObj.when = gate.when;
      if (gate.timeout_seconds) gateObj.timeout_seconds = gate.timeout_seconds;
      if (gate.fatal !== undefined && gate.fatal !== true) gateObj.fatal = gate.fatal;
      return gateObj;
    }),
    full: config.gates.full.map((gate) => {
      const gateObj: Record<string, unknown> = {
        name: gate.name,
        cmd: gate.cmd,
      };
      if (gate.when) gateObj.when = gate.when;
      if (gate.timeout_seconds) gateObj.timeout_seconds = gate.timeout_seconds;
      if (gate.fatal !== undefined && gate.fatal !== true) gateObj.fatal = gate.fatal;
      return gateObj;
    }),
  };

  // Add services if present
  if (config.services) {
    const services: Record<string, unknown> = {};

    if (config.services.backend) {
      const backend: Record<string, unknown> = {
        start: {},
        port: config.services.backend.port,
      };
      if (config.services.backend.start.dev) {
        (backend.start as Record<string, string>).dev = config.services.backend.start.dev;
      }
      if (config.services.backend.start.prod) {
        (backend.start as Record<string, string>).prod = config.services.backend.start.prod;
      }
      if (config.services.backend.health && config.services.backend.health.length > 0) {
        backend.health = config.services.backend.health;
      }
      if (config.services.backend.timeout) {
        backend.timeout = config.services.backend.timeout;
      }
      services.backend = backend;
    }

    if (config.services.frontend) {
      const frontend: Record<string, unknown> = {
        serve: {},
        port: config.services.frontend.port,
      };
      if (config.services.frontend.build) {
        frontend.build = config.services.frontend.build;
      }
      if (config.services.frontend.serve.dev) {
        (frontend.serve as Record<string, string>).dev = config.services.frontend.serve.dev;
      }
      if (config.services.frontend.serve.prod) {
        (frontend.serve as Record<string, string>).prod = config.services.frontend.serve.prod;
      }
      if (config.services.frontend.timeout) {
        frontend.timeout = config.services.frontend.timeout;
      }
      services.frontend = frontend;
    }

    if (Object.keys(services).length > 0) {
      orderedConfig.services = services;
    }
  }

  // Add limits if present and has values
  if (config.limits) {
    const limits: Record<string, number> = {};
    if (config.limits.claude_timeout) limits.claude_timeout = config.limits.claude_timeout;
    if (config.limits.max_iterations) limits.max_iterations = config.limits.max_iterations;
    if (config.limits.post_verify_iterations) limits.post_verify_iterations = config.limits.post_verify_iterations;
    if (config.limits.ui_fix_iterations) limits.ui_fix_iterations = config.limits.ui_fix_iterations;
    if (config.limits.robot_fix_iterations) limits.robot_fix_iterations = config.limits.robot_fix_iterations;

    if (Object.keys(limits).length > 0) {
      orderedConfig.limits = limits;
    }
  }

  // Add autopilot if present
  if (config.autopilot) {
    const autopilot: Record<string, unknown> = {};
    if (config.autopilot.enabled !== undefined) autopilot.enabled = config.autopilot.enabled;
    if (config.autopilot.reports_dir) autopilot.reports_dir = config.autopilot.reports_dir;
    if (config.autopilot.branch_prefix) autopilot.branch_prefix = config.autopilot.branch_prefix;
    if (config.autopilot.create_pr !== undefined) autopilot.create_pr = config.autopilot.create_pr;

    if (Object.keys(autopilot).length > 0) {
      orderedConfig.autopilot = autopilot;
    }
  }

  // Use the yaml library to generate proper YAML output
  return yamlStringify(orderedConfig, {
    indent: 2,
    lineWidth: 0, // Don't wrap long lines
    defaultStringType: "PLAIN", // Use plain strings where possible
    defaultKeyType: "PLAIN",
  });
}

// Loading skeleton
function ConfigEditorSkeleton() {
  return (
    <div className="flex h-full">
      <div className="flex-1 p-4 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
      <div className="w-1/3 border-l p-4">
        <Skeleton className="h-6 w-32 mb-4" />
        <Skeleton className="h-full w-full" />
      </div>
    </div>
  );
}

export function ConfigEditor({
  projectId,
  config: initialConfig,
  isLoading,
  onSave,
  onValidate,
}: ConfigEditorProps) {
  const [config, setConfig] = useState<RalphConfig>(initialConfig || defaultConfig);
  const [originalConfig, setOriginalConfig] = useState<RalphConfig>(initialConfig || defaultConfig);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);

  // Sync with initialConfig when it changes
  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
      setOriginalConfig(initialConfig);
    }
  }, [initialConfig]);

  // Validate on config change
  useEffect(() => {
    if (onValidate) {
      setIsValidating(true);
      const timer = setTimeout(async () => {
        try {
          const errors = await onValidate(config);
          setValidationErrors(errors);
        } catch {
          // Validation failed
        } finally {
          setIsValidating(false);
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [config, onValidate]);

  // Check if config has changed
  const hasChanges = useMemo(() => {
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  }, [config, originalConfig]);

  // Get error for a specific path
  const getError = useCallback(
    (path: string) => {
      return validationErrors.find((e) => e.path === path)?.message;
    },
    [validationErrors]
  );

  // Handle save
  const handleSave = useCallback(async () => {
    if (!onSave || validationErrors.length > 0) return;
    setIsSaving(true);
    try {
      await onSave(config);
      setOriginalConfig(config);
    } finally {
      setIsSaving(false);
    }
  }, [config, onSave, validationErrors]);

  // Handle reset
  const handleReset = useCallback(() => {
    setConfig(originalConfig);
  }, [originalConfig]);

  // Update nested config value
  const updateConfig = useCallback((path: string, value: unknown) => {
    setConfig((prev) => {
      const newConfig = JSON.parse(JSON.stringify(prev));
      const parts = path.split(".");
      let current = newConfig;
      for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i];
        if (part) {
          if (!(part in current)) {
            current[part] = {};
          }
          current = current[part];
        }
      }
      const lastPart = parts[parts.length - 1];
      if (lastPart) {
        current[lastPart] = value;
      }
      return newConfig;
    });
  }, []);

  if (isLoading) {
    return <ConfigEditorSkeleton />;
  }

  return (
    <div className="flex h-full">
      {/* Form Editor (Left Pane) */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">Configuration Editor</h3>
            {validationErrors.length > 0 ? (
              <Badge variant="destructive" className="flex items-center gap-1">
                <AlertCircleIcon /> {validationErrors.length} error{validationErrors.length > 1 ? "s" : ""}
              </Badge>
            ) : isValidating ? (
              <Badge variant="secondary">Validating...</Badge>
            ) : (
              <Badge variant="outline" className="flex items-center gap-1 text-green-600 border-green-600">
                <CheckCircleIcon /> Valid
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              disabled={!hasChanges}
            >
              <ResetIcon /> Reset
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={isSaving || validationErrors.length > 0 || !hasChanges}
            >
              <SaveIcon /> {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Task Source */}
          <CollapsibleSection
            title="Task Source"
            description="Configure where tasks are loaded from"
          >
            <div className="space-y-4 mt-4">
              <FormField
                label="Source Type"
                description="Type of task source file"
                error={getError("task_source.type")}
              >
                <div className="flex gap-2">
                  <Button
                    variant={config.task_source.type === "prd_json" ? "default" : "outline"}
                    size="sm"
                    onClick={() => updateConfig("task_source.type", "prd_json")}
                  >
                    PRD JSON
                  </Button>
                  <Button
                    variant={config.task_source.type === "cr_markdown" ? "default" : "outline"}
                    size="sm"
                    onClick={() => updateConfig("task_source.type", "cr_markdown")}
                  >
                    CR Markdown
                  </Button>
                </div>
              </FormField>
              <FormField
                label="Path"
                description="Path to the task source file"
                error={getError("task_source.path")}
              >
                <Input
                  value={config.task_source.path}
                  onChange={(e) => updateConfig("task_source.path", e.target.value)}
                  placeholder=".ralph/prd.json"
                  className="font-mono"
                />
              </FormField>
            </div>
          </CollapsibleSection>

          {/* Git Configuration */}
          <CollapsibleSection
            title="Git Configuration"
            description="Version control settings"
          >
            <div className="space-y-4 mt-4">
              <FormField
                label="Base Branch"
                description="Branch to create feature branches from"
                error={getError("git.base_branch")}
              >
                <Input
                  value={config.git.base_branch}
                  onChange={(e) => updateConfig("git.base_branch", e.target.value)}
                  placeholder="main"
                />
              </FormField>
              <FormField
                label="Remote"
                description="Git remote name"
                error={getError("git.remote")}
              >
                <Input
                  value={config.git.remote}
                  onChange={(e) => updateConfig("git.remote", e.target.value)}
                  placeholder="origin"
                />
              </FormField>
            </div>
          </CollapsibleSection>

          {/* Test Paths */}
          <CollapsibleSection
            title="Test Paths"
            description="Glob patterns for test file paths (guardrails)"
          >
            <div className="space-y-4 mt-4">
              <FormField
                label="Test Path Patterns"
                description="Comma-separated glob patterns for allowed test file locations"
                error={getError("test_paths")}
              >
                <Input
                  value={config.test_paths?.join(", ") || ""}
                  onChange={(e) =>
                    updateConfig(
                      "test_paths",
                      e.target.value.split(",").map((s) => s.trim()).filter(Boolean)
                    )
                  }
                  placeholder="tests/**, **/*.test.*, **/*.spec.*"
                  className="font-mono"
                />
              </FormField>
            </div>
          </CollapsibleSection>

          {/* Services */}
          <CollapsibleSection
            title="Services"
            description="Backend and frontend service configuration"
            defaultOpen={false}
          >
            <div className="space-y-6 mt-4">
              {/* Backend */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm">Backend Service</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField label="Dev Command">
                    <Input
                      value={config.services?.backend?.start.dev || ""}
                      onChange={(e) => updateConfig("services.backend.start.dev", e.target.value)}
                      placeholder="uvicorn app:main --reload"
                      className="font-mono"
                    />
                  </FormField>
                  <FormField label="Production Command">
                    <Input
                      value={config.services?.backend?.start.prod || ""}
                      onChange={(e) => updateConfig("services.backend.start.prod", e.target.value)}
                      placeholder="uvicorn app:main"
                      className="font-mono"
                    />
                  </FormField>
                  <FormField label="Port">
                    <Input
                      type="number"
                      value={config.services?.backend?.port || 8000}
                      onChange={(e) => updateConfig("services.backend.port", parseInt(e.target.value) || 8000)}
                      placeholder="8000"
                    />
                  </FormField>
                  <FormField label="Health Check Endpoints">
                    <Input
                      value={config.services?.backend?.health?.join(", ") || ""}
                      onChange={(e) =>
                        updateConfig(
                          "services.backend.health",
                          e.target.value.split(",").map((s) => s.trim()).filter(Boolean)
                        )
                      }
                      placeholder="/health, /api/status"
                      className="font-mono"
                    />
                  </FormField>
                </CardContent>
              </Card>

              {/* Frontend */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-sm">Frontend Service</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField label="Build Command">
                    <Input
                      value={config.services?.frontend?.build || ""}
                      onChange={(e) => updateConfig("services.frontend.build", e.target.value)}
                      placeholder="npm run build"
                      className="font-mono"
                    />
                  </FormField>
                  <FormField label="Dev Serve Command">
                    <Input
                      value={config.services?.frontend?.serve.dev || ""}
                      onChange={(e) => updateConfig("services.frontend.serve.dev", e.target.value)}
                      placeholder="npm run dev"
                      className="font-mono"
                    />
                  </FormField>
                  <FormField label="Production Serve Command">
                    <Input
                      value={config.services?.frontend?.serve.prod || ""}
                      onChange={(e) => updateConfig("services.frontend.serve.prod", e.target.value)}
                      placeholder="npm run start"
                      className="font-mono"
                    />
                  </FormField>
                  <FormField label="Port">
                    <Input
                      type="number"
                      value={config.services?.frontend?.port || 3000}
                      onChange={(e) => updateConfig("services.frontend.port", parseInt(e.target.value) || 3000)}
                      placeholder="3000"
                    />
                  </FormField>
                </CardContent>
              </Card>
            </div>
          </CollapsibleSection>

          {/* Limits */}
          <CollapsibleSection
            title="Limits"
            description="Iteration and timeout limits"
            defaultOpen={false}
          >
            <div className="grid grid-cols-2 gap-4 mt-4">
              <FormField
                label="Claude Timeout (seconds)"
                description="Timeout per Claude call"
              >
                <Input
                  type="number"
                  value={config.limits?.claude_timeout || 1800}
                  onChange={(e) => updateConfig("limits.claude_timeout", parseInt(e.target.value) || 1800)}
                />
              </FormField>
              <FormField
                label="Max Iterations"
                description="Max task loop iterations"
              >
                <Input
                  type="number"
                  value={config.limits?.max_iterations || 30}
                  onChange={(e) => updateConfig("limits.max_iterations", parseInt(e.target.value) || 30)}
                />
              </FormField>
              <FormField
                label="Post-Verify Iterations"
                description="Max runtime fix iterations"
              >
                <Input
                  type="number"
                  value={config.limits?.post_verify_iterations || 10}
                  onChange={(e) => updateConfig("limits.post_verify_iterations", parseInt(e.target.value) || 10)}
                />
              </FormField>
              <FormField
                label="UI Fix Iterations"
                description="Max agent-browser fix iterations"
              >
                <Input
                  type="number"
                  value={config.limits?.ui_fix_iterations || 10}
                  onChange={(e) => updateConfig("limits.ui_fix_iterations", parseInt(e.target.value) || 10)}
                />
              </FormField>
            </div>
          </CollapsibleSection>

          {/* Autopilot */}
          <CollapsibleSection
            title="Autopilot"
            description="Autonomous execution configuration"
            defaultOpen={false}
          >
            <div className="space-y-4 mt-4">
              <FormField label="Enabled">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="autopilot-enabled"
                    checked={config.autopilot?.enabled || false}
                    onChange={(e) => updateConfig("autopilot.enabled", e.target.checked)}
                    className="rounded"
                  />
                  <label htmlFor="autopilot-enabled" className="text-sm">
                    Enable autopilot mode
                  </label>
                </div>
              </FormField>
              <FormField label="Reports Directory">
                <Input
                  value={config.autopilot?.reports_dir || "./reports"}
                  onChange={(e) => updateConfig("autopilot.reports_dir", e.target.value)}
                  placeholder="./reports"
                  className="font-mono"
                />
              </FormField>
              <FormField label="Branch Prefix">
                <Input
                  value={config.autopilot?.branch_prefix || "ralph/"}
                  onChange={(e) => updateConfig("autopilot.branch_prefix", e.target.value)}
                  placeholder="ralph/"
                />
              </FormField>
              <FormField label="Create PR">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="autopilot-create-pr"
                    checked={config.autopilot?.create_pr !== false}
                    onChange={(e) => updateConfig("autopilot.create_pr", e.target.checked)}
                    className="rounded"
                  />
                  <label htmlFor="autopilot-create-pr" className="text-sm">
                    Automatically create PR after completion
                  </label>
                </div>
              </FormField>
            </div>
          </CollapsibleSection>
        </div>
      </div>

      {/* YAML Preview (Right Pane) */}
      <div className="w-1/3 border-l flex flex-col bg-muted/30">
        <div className="p-4 border-b shrink-0">
          <h4 className="font-medium text-sm">YAML Preview</h4>
          <p className="text-xs text-muted-foreground">
            Live preview of ralph.yml
          </p>
        </div>
        <div className="flex-1 overflow-auto p-4">
          <YamlPreview config={config} />
        </div>
      </div>
    </div>
  );
}

export default ConfigEditor;
