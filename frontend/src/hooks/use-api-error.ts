"use client";

import { useState, useCallback } from "react";
import { AppError, classifyError } from "@/lib/errors";

interface UseApiErrorReturn {
  /** The current error, if any */
  error: AppError | null;
  /** Set an error (will be classified if not already an AppError) */
  setError: (error: unknown) => void;
  /** Clear the current error */
  clearError: () => void;
  /** Whether there is an active error */
  hasError: boolean;
  /** Wrap an async function to automatically catch and classify errors */
  withErrorHandling: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
}

/**
 * Hook for managing API error state with classification
 */
export function useApiError(): UseApiErrorReturn {
  const [error, setErrorState] = useState<AppError | null>(null);

  const setError = useCallback((err: unknown) => {
    if (err === null) {
      setErrorState(null);
      return;
    }

    // If it's already an AppError, use it directly
    if (
      err &&
      typeof err === "object" &&
      "category" in err &&
      "userMessage" in err
    ) {
      setErrorState(err as AppError);
      return;
    }

    // Otherwise classify the error
    setErrorState(classifyError(err));
  }, []);

  const clearError = useCallback(() => {
    setErrorState(null);
  }, []);

  const withErrorHandling = useCallback(
    async <T>(fn: () => Promise<T>): Promise<T | undefined> => {
      try {
        clearError();
        return await fn();
      } catch (err) {
        setError(err);
        return undefined;
      }
    },
    [clearError, setError]
  );

  return {
    error,
    setError,
    clearError,
    hasError: error !== null,
    withErrorHandling,
  };
}
