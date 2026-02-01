"use client";

import { useState, useCallback, useRef } from "react";
import { RetryConfig, DEFAULT_RETRY_CONFIG } from "@/lib/errors";
import { calculateBackoff } from "@/services/retry";

interface UseRetryState {
  /** Current retry attempt number (0 = initial attempt) */
  attempt: number;
  /** Whether currently retrying */
  isRetrying: boolean;
  /** Whether more retries are available */
  canRetry: boolean;
  /** Time until next retry (in ms), if scheduled */
  nextRetryIn: number | null;
}

interface UseRetryReturn extends UseRetryState {
  /** Trigger a retry */
  retry: () => void;
  /** Reset retry state */
  reset: () => void;
  /** Execute a function with retry tracking */
  execute: <T>(fn: () => Promise<T>) => Promise<T>;
}

/**
 * Hook for manual retry management
 */
export function useRetry(
  config: Partial<RetryConfig> = {},
  onRetry?: () => void
): UseRetryReturn {
  const fullConfig = { ...DEFAULT_RETRY_CONFIG, ...config };
  const [state, setState] = useState<UseRetryState>({
    attempt: 0,
    isRetrying: false,
    canRetry: true,
    nextRetryIn: null,
  });

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    clearTimer();
    setState({
      attempt: 0,
      isRetrying: false,
      canRetry: true,
      nextRetryIn: null,
    });
  }, [clearTimer]);

  const retry = useCallback(() => {
    if (!state.canRetry || state.isRetrying) return;

    const nextAttempt = state.attempt + 1;
    const delay = calculateBackoff(state.attempt, fullConfig);

    setState((prev) => ({
      ...prev,
      isRetrying: true,
      nextRetryIn: delay,
    }));

    clearTimer();
    timerRef.current = setTimeout(() => {
      setState((prev) => ({
        ...prev,
        attempt: nextAttempt,
        isRetrying: false,
        canRetry: nextAttempt < fullConfig.maxRetries,
        nextRetryIn: null,
      }));
      onRetry?.();
    }, delay);
  }, [state.canRetry, state.isRetrying, state.attempt, fullConfig, clearTimer, onRetry]);

  const execute = useCallback(
    async <T>(fn: () => Promise<T>): Promise<T> => {
      setState((prev) => ({ ...prev, isRetrying: true }));

      try {
        const result = await fn();
        reset();
        return result;
      } catch (error) {
        setState((prev) => ({
          ...prev,
          attempt: prev.attempt + 1,
          isRetrying: false,
          canRetry: prev.attempt + 1 < fullConfig.maxRetries,
        }));
        throw error;
      }
    },
    [fullConfig.maxRetries, reset]
  );

  return {
    ...state,
    retry,
    reset,
    execute,
  };
}
