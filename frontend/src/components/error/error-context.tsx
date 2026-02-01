"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { AppError } from "@/lib/errors";

interface ErrorContextValue {
  /** Current global error, if any */
  error: AppError | null;
  /** Report an error to the global handler */
  reportError: (error: AppError) => void;
  /** Clear the current error */
  clearError: () => void;
}

const ErrorContext = createContext<ErrorContextValue | null>(null);

export interface ErrorProviderProps {
  children: ReactNode;
  /** Callback when an error is reported */
  onError?: (error: AppError) => void;
}

export function ErrorProvider({ children, onError }: ErrorProviderProps) {
  const [error, setError] = useState<AppError | null>(null);

  const reportError = useCallback(
    (newError: AppError) => {
      setError(newError);
      onError?.(newError);
    },
    [onError]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return (
    <ErrorContext.Provider value={{ error, reportError, clearError }}>
      {children}
    </ErrorContext.Provider>
  );
}

export function useErrorContext(): ErrorContextValue {
  const context = useContext(ErrorContext);
  if (!context) {
    throw new Error("useErrorContext must be used within an ErrorProvider");
  }
  return context;
}

/**
 * Hook to report errors to the global error context
 * Returns null if not within an ErrorProvider (for optional use)
 */
export function useErrorReporter(): ((error: AppError) => void) | null {
  const context = useContext(ErrorContext);
  return context?.reportError ?? null;
}
