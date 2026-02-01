/**
 * Error classification utilities
 */

import { ErrorCategory, AppError } from "./types";

/**
 * User-friendly error messages by category
 */
const USER_MESSAGES: Record<ErrorCategory, string> = {
  [ErrorCategory.NETWORK]: "Unable to connect to the server. Please check your internet connection.",
  [ErrorCategory.TIMEOUT]: "The request took too long to complete. Please try again.",
  [ErrorCategory.VALIDATION]: "The data provided is invalid. Please check and try again.",
  [ErrorCategory.SERVER]: "Something went wrong on the server. Please try again later.",
  [ErrorCategory.AUTH]: "You are not authorized to perform this action.",
  [ErrorCategory.NOT_FOUND]: "The requested resource was not found.",
  [ErrorCategory.UNKNOWN]: "An unexpected error occurred. Please try again.",
};

/**
 * Determine if an error category is retryable
 */
function isRetryable(category: ErrorCategory): boolean {
  switch (category) {
    case ErrorCategory.NETWORK:
    case ErrorCategory.TIMEOUT:
    case ErrorCategory.SERVER:
      return true;
    case ErrorCategory.VALIDATION:
    case ErrorCategory.AUTH:
    case ErrorCategory.NOT_FOUND:
    case ErrorCategory.UNKNOWN:
      return false;
  }
}

/**
 * Classify an error from HTTP status code
 */
export function classifyHttpError(status: number, message?: string): AppError {
  let category: ErrorCategory;

  if (status === 0) {
    category = ErrorCategory.NETWORK;
  } else if (status === 401 || status === 403) {
    category = ErrorCategory.AUTH;
  } else if (status === 404) {
    category = ErrorCategory.NOT_FOUND;
  } else if (status === 408 || status === 504) {
    category = ErrorCategory.TIMEOUT;
  } else if (status >= 400 && status < 500) {
    category = ErrorCategory.VALIDATION;
  } else if (status >= 500) {
    category = ErrorCategory.SERVER;
  } else {
    category = ErrorCategory.UNKNOWN;
  }

  return {
    category,
    message: message || `HTTP ${status}`,
    userMessage: USER_MESSAGES[category],
    retryable: isRetryable(category),
    statusCode: status,
  };
}

/**
 * Classify an error from a JavaScript Error object
 */
export function classifyError(error: unknown): AppError {
  // Handle fetch/network errors
  if (error instanceof TypeError && error.message.includes("fetch")) {
    return {
      category: ErrorCategory.NETWORK,
      message: error.message,
      userMessage: USER_MESSAGES[ErrorCategory.NETWORK],
      retryable: true,
      cause: error,
    };
  }

  // Handle AbortError (timeout)
  if (error instanceof DOMException && error.name === "AbortError") {
    return {
      category: ErrorCategory.TIMEOUT,
      message: "Request was aborted",
      userMessage: USER_MESSAGES[ErrorCategory.TIMEOUT],
      retryable: true,
      cause: error,
    };
  }

  // Handle our ApiError from api.ts
  if (
    error &&
    typeof error === "object" &&
    "status" in error &&
    "statusText" in error
  ) {
    const apiError = error as { status: number; statusText: string; message?: string };
    return classifyHttpError(apiError.status, apiError.message || apiError.statusText);
  }

  // Handle generic errors
  if (error instanceof Error) {
    return {
      category: ErrorCategory.UNKNOWN,
      message: error.message,
      userMessage: USER_MESSAGES[ErrorCategory.UNKNOWN],
      retryable: false,
      cause: error,
    };
  }

  // Handle unknown error types
  return {
    category: ErrorCategory.UNKNOWN,
    message: String(error),
    userMessage: USER_MESSAGES[ErrorCategory.UNKNOWN],
    retryable: false,
  };
}

/**
 * Create an AppError from a message
 */
export function createAppError(
  category: ErrorCategory,
  message: string,
  userMessage?: string
): AppError {
  return {
    category,
    message,
    userMessage: userMessage || USER_MESSAGES[category],
    retryable: isRetryable(category),
  };
}
