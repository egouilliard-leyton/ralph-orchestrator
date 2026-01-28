"use client";

import { useState, useCallback, useEffect } from "react";
import { api, RalphConfig, ConfigValidationResult } from "@/services/api";

interface UseConfigOptions {
  projectId: string;
}

interface UseConfigReturn {
  config: RalphConfig | null;
  isLoading: boolean;
  error: string | null;
  validationErrors: Array<{ path: string; message: string }>;
  saveConfig: (config: RalphConfig) => Promise<void>;
  validateConfig: (config: RalphConfig) => Promise<Array<{ path: string; message: string }>>;
  refetch: () => Promise<void>;
}

export function useConfig({ projectId }: UseConfigOptions): UseConfigReturn {
  const [config, setConfig] = useState<RalphConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<Array<{ path: string; message: string }>>([]);

  // Fetch config
  const fetchConfig = useCallback(async () => {
    if (!projectId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await api.config.get(projectId);
      setConfig(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch config";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Initial fetch
  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  // Validate config
  const validateConfig = useCallback(
    async (configData: RalphConfig): Promise<Array<{ path: string; message: string }>> => {
      if (!projectId) return [];

      try {
        const result: ConfigValidationResult = await api.config.validate(projectId, configData);
        const errors = result.errors || [];
        setValidationErrors(errors);
        return errors;
      } catch (err) {
        // If validation endpoint fails, return empty errors (assume valid)
        console.error("Validation failed:", err);
        setValidationErrors([]);
        return [];
      }
    },
    [projectId]
  );

  // Save config
  const saveConfig = useCallback(
    async (configData: RalphConfig): Promise<void> => {
      if (!projectId) return;

      // Validate first
      const errors = await validateConfig(configData);
      if (errors.length > 0) {
        throw new Error(`Validation failed: ${errors.map((e) => e.message).join(", ")}`);
      }

      try {
        const updatedConfig = await api.config.update(projectId, configData);
        setConfig(updatedConfig);
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to save config";
        setError(message);
        throw err;
      }
    },
    [projectId, validateConfig]
  );

  return {
    config,
    isLoading,
    error,
    validationErrors,
    saveConfig,
    validateConfig,
    refetch: fetchConfig,
  };
}

export default useConfig;
