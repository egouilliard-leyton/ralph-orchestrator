/**
 * Retry utilities with exponential backoff
 */

import { RetryConfig, DEFAULT_RETRY_CONFIG } from "@/lib/errors";

export interface RetryState {
  attempt: number;
  lastError?: Error;
}

/**
 * Calculate backoff delay with jitter
 */
export function calculateBackoff(
  attempt: number,
  config: RetryConfig = DEFAULT_RETRY_CONFIG
): number {
  const delay = config.initialDelay * Math.pow(config.backoffFactor, attempt);
  const cappedDelay = Math.min(delay, config.maxDelay);
  // Add jitter (0-25% of delay)
  const jitter = cappedDelay * Math.random() * 0.25;
  return Math.floor(cappedDelay + jitter);
}

/**
 * Sleep for a specified duration
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Determine if an error should trigger a retry
 */
export function shouldRetry(error: unknown): boolean {
  // Network errors - always retry
  if (error instanceof TypeError && error.message.includes("fetch")) {
    return true;
  }

  // Timeout errors - always retry
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }

  // Check for HTTP status codes
  if (error && typeof error === "object" && "status" in error) {
    const status = (error as { status: number }).status;
    // Only retry on server errors and specific client errors
    // 429 = rate limited, 408 = request timeout, 5xx = server errors
    if (status === 429 || status === 408 || status >= 500) {
      return true;
    }
    // Don't retry on client errors (4xx except 408, 429)
    if (status >= 400 && status < 500) {
      return false;
    }
  }

  return false;
}

/**
 * Execute a function with retry logic
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const fullConfig = { ...DEFAULT_RETRY_CONFIG, ...config };
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= fullConfig.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry if we've exhausted attempts or error isn't retryable
      if (attempt >= fullConfig.maxRetries || !shouldRetry(error)) {
        throw lastError;
      }

      // Wait before retrying
      const delay = calculateBackoff(attempt, fullConfig);
      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * Create a retry controller for manual retry management
 */
export function createRetryController(config: Partial<RetryConfig> = {}) {
  const fullConfig = { ...DEFAULT_RETRY_CONFIG, ...config };
  let attempt = 0;

  return {
    get attempt() {
      return attempt;
    },
    get canRetry() {
      return attempt < fullConfig.maxRetries;
    },
    get nextDelay() {
      return calculateBackoff(attempt, fullConfig);
    },
    increment() {
      attempt++;
    },
    reset() {
      attempt = 0;
    },
  };
}
