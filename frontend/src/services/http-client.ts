/**
 * Enhanced HTTP client with retry, timeout, and error handling
 */

import { AppError, classifyHttpError, classifyError } from "@/lib/errors";
import { withRetry, shouldRetry } from "./retry";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HttpClientConfig {
  /** Request timeout in milliseconds (default: 30000) */
  timeout?: number;
  /** Enable automatic retry (default: true) */
  retry?: boolean;
  /** Maximum number of retries (default: 3) */
  maxRetries?: number;
  /** Initial retry delay in milliseconds (default: 1000) */
  retryDelay?: number;
  /** Base URL override */
  baseUrl?: string;
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
  timeout?: number;
  retry?: boolean;
}

export class HttpError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string,
    public appError: AppError
  ) {
    super(message);
    this.name = "HttpError";
  }
}

const DEFAULT_CONFIG: Required<HttpClientConfig> = {
  timeout: 30000,
  retry: true,
  maxRetries: 3,
  retryDelay: 1000,
  baseUrl: API_BASE_URL,
};

/**
 * Create a fetch request with timeout support
 */
function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout: number
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  return fetch(url, {
    ...options,
    signal: controller.signal,
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

/**
 * Create an HTTP client with enhanced features
 */
export function createHttpClient(config: HttpClientConfig = {}) {
  const clientConfig = { ...DEFAULT_CONFIG, ...config };

  async function request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { params, timeout, retry, ...fetchOptions } = options;
    const requestTimeout = timeout ?? clientConfig.timeout;
    const shouldRetryRequest = retry ?? clientConfig.retry;

    let url = `${clientConfig.baseUrl}${endpoint}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const doRequest = async (): Promise<T> => {
      const response = await fetchWithTimeout(
        url,
        {
          ...fetchOptions,
          headers: {
            "Content-Type": "application/json",
            ...fetchOptions.headers,
          },
        },
        requestTimeout
      );

      if (!response.ok) {
        const errorMessage = await response.text().catch(() => response.statusText);
        const appError = classifyHttpError(response.status, errorMessage);
        throw new HttpError(response.status, response.statusText, errorMessage, appError);
      }

      // Handle empty responses
      const text = await response.text();
      if (!text) {
        return {} as T;
      }

      return JSON.parse(text) as T;
    };

    if (shouldRetryRequest) {
      return withRetry(doRequest, {
        maxRetries: clientConfig.maxRetries,
        initialDelay: clientConfig.retryDelay,
      });
    }

    return doRequest();
  }

  return {
    get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
      return request<T>(endpoint, { ...options, method: "GET" });
    },

    post<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
      return request<T>(endpoint, {
        ...options,
        method: "POST",
        body: data ? JSON.stringify(data) : undefined,
      });
    },

    put<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
      return request<T>(endpoint, {
        ...options,
        method: "PUT",
        body: data ? JSON.stringify(data) : undefined,
      });
    },

    patch<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
      return request<T>(endpoint, {
        ...options,
        method: "PATCH",
        body: data ? JSON.stringify(data) : undefined,
      });
    },

    delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
      return request<T>(endpoint, { ...options, method: "DELETE" });
    },

    request,
  };
}

/**
 * Default HTTP client instance
 */
export const httpClient = createHttpClient();

/**
 * Extract AppError from any error
 */
export function getAppError(error: unknown): AppError {
  if (error instanceof HttpError) {
    return error.appError;
  }
  return classifyError(error);
}
