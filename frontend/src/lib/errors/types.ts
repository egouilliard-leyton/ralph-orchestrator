/**
 * Error classification system for the frontend
 */

export enum ErrorCategory {
  NETWORK = "network",
  TIMEOUT = "timeout",
  VALIDATION = "validation",
  SERVER = "server",
  AUTH = "auth",
  NOT_FOUND = "not_found",
  UNKNOWN = "unknown",
}

export interface AppError {
  /** Error category for handling decisions */
  category: ErrorCategory;
  /** Technical error message */
  message: string;
  /** User-friendly error message */
  userMessage: string;
  /** Whether this error can be retried */
  retryable: boolean;
  /** Original error if available */
  cause?: Error;
  /** HTTP status code if applicable */
  statusCode?: number;
}

export interface RetryConfig {
  /** Maximum number of retry attempts */
  maxRetries: number;
  /** Initial delay in milliseconds */
  initialDelay: number;
  /** Maximum delay in milliseconds */
  maxDelay: number;
  /** Backoff multiplier */
  backoffFactor: number;
}

export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffFactor: 2,
};
