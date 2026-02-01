"use client";

import { Component, ReactNode, ErrorInfo } from "react";
import { ErrorFallback } from "./error-fallback";
import { AppError, ErrorCategory, classifyError } from "@/lib/errors";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Custom fallback component */
  fallback?: ReactNode | ((props: { error: AppError; reset: () => void }) => ReactNode);
  /** Callback when an error is caught */
  onError?: (error: AppError, errorInfo: ErrorInfo) => void;
  /** Whether to show retry button */
  showRetry?: boolean;
}

interface ErrorBoundaryState {
  error: AppError | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error: classifyError(error) };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const appError = classifyError(error);
    this.props.onError?.(appError, errorInfo);

    // Log to console in development
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught an error:", error, errorInfo);
    }
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    const { children, fallback, showRetry } = this.props;

    if (error) {
      // Custom fallback function
      if (typeof fallback === "function") {
        return fallback({ error, reset: this.reset });
      }

      // Custom fallback element
      if (fallback) {
        return fallback;
      }

      // Default fallback
      return (
        <ErrorFallback
          error={error}
          onReset={this.reset}
          onRetry={showRetry ? this.reset : undefined}
          showRetry={showRetry}
        />
      );
    }

    return children;
  }
}

/**
 * A simpler error boundary for wrapping smaller sections
 */
export function SectionErrorBoundary({
  children,
  name,
}: {
  children: ReactNode;
  name?: string;
}) {
  return (
    <ErrorBoundary
      onError={(error) => {
        console.error(`Error in section${name ? ` "${name}"` : ""}:`, error);
      }}
      fallback={({ error, reset }) => (
        <div className="p-4 border border-red-200 dark:border-red-800 rounded-lg bg-red-50 dark:bg-red-900/20">
          <p className="text-sm text-red-600 dark:text-red-400 mb-2">
            {name ? `Error loading ${name}` : "An error occurred"}
          </p>
          <button
            onClick={reset}
            className="text-xs text-red-600 dark:text-red-400 underline hover:no-underline"
          >
            Try again
          </button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
}
