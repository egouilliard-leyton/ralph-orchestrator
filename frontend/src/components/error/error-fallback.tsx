"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AlertCircleIcon, RefreshIcon } from "@/components/ui/icons";
import { AppError, ErrorCategory } from "@/lib/errors";

export interface ErrorFallbackProps {
  /** The error to display */
  error: AppError | Error;
  /** Callback to retry the operation */
  onRetry?: () => void;
  /** Callback to reset/dismiss the error */
  onReset?: () => void;
  /** Title override */
  title?: string;
  /** Whether to show retry button (auto-detected from error if not specified) */
  showRetry?: boolean;
  /** Additional className */
  className?: string;
}

function getErrorTitle(error: AppError | Error): string {
  if ("category" in error) {
    switch (error.category) {
      case ErrorCategory.NETWORK:
        return "Connection Error";
      case ErrorCategory.TIMEOUT:
        return "Request Timeout";
      case ErrorCategory.AUTH:
        return "Access Denied";
      case ErrorCategory.NOT_FOUND:
        return "Not Found";
      case ErrorCategory.SERVER:
        return "Server Error";
      case ErrorCategory.VALIDATION:
        return "Invalid Request";
      default:
        return "Something Went Wrong";
    }
  }
  return "Something Went Wrong";
}

function getErrorMessage(error: AppError | Error): string {
  if ("userMessage" in error) {
    return error.userMessage;
  }
  return error.message || "An unexpected error occurred.";
}

function isRetryable(error: AppError | Error): boolean {
  if ("retryable" in error) {
    return error.retryable;
  }
  return false;
}

export function ErrorFallback({
  error,
  onRetry,
  onReset,
  title,
  showRetry,
  className,
}: ErrorFallbackProps) {
  const errorTitle = title ?? getErrorTitle(error);
  const errorMessage = getErrorMessage(error);
  const canRetry = showRetry ?? (isRetryable(error) && Boolean(onRetry));

  return (
    <Card className={className}>
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-4 mb-4">
          <AlertCircleIcon className="text-red-600 dark:text-red-400" size={24} />
        </div>
        <h3 className="text-lg font-semibold mb-2">{errorTitle}</h3>
        <p className="text-sm text-muted-foreground max-w-sm mb-6">
          {errorMessage}
        </p>
        <div className="flex items-center gap-3">
          {canRetry && onRetry && (
            <Button onClick={onRetry} variant="default">
              <RefreshIcon className="mr-2" size={16} />
              Try Again
            </Button>
          )}
          {onReset && (
            <Button onClick={onReset} variant="outline">
              Go Back
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Compact error display for inline use
 */
export function InlineError({
  error,
  onRetry,
  className,
}: {
  error: AppError | Error;
  onRetry?: () => void;
  className?: string;
}) {
  const errorMessage = getErrorMessage(error);
  const canRetry = isRetryable(error) && Boolean(onRetry);

  return (
    <div
      className={`flex items-center gap-2 text-sm text-red-600 dark:text-red-400 ${className ?? ""}`}
    >
      <AlertCircleIcon size={14} />
      <span>{errorMessage}</span>
      {canRetry && onRetry && (
        <Button onClick={onRetry} variant="ghost" size="xs" className="ml-2">
          Retry
        </Button>
      )}
    </div>
  );
}
