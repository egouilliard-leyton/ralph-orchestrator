"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { WebSocketStatus } from "@/hooks/use-websocket";

// Icons
function WifiIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 13a10 10 0 0 1 14 0" />
      <path d="M8.5 16.5a5 5 0 0 1 7 0" />
      <path d="M2 8.82a15 15 0 0 1 20 0" />
      <line x1="12" x2="12.01" y1="20" y2="20" />
    </svg>
  );
}

function WifiOffIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="2" x2="22" y1="2" y2="22" />
      <path d="M8.5 16.5a5 5 0 0 1 7 0" />
      <path d="M2 8.82a15 15 0 0 1 4.17-2.65" />
      <path d="M10.66 5c4.01-.36 8.14.9 11.34 3.76" />
      <path d="M16.85 11.25a10 10 0 0 1 2.22 1.68" />
      <path d="M5 13a10 10 0 0 1 5.24-2.76" />
      <line x1="12" x2="12.01" y1="20" y2="20" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 16h5v5" />
    </svg>
  );
}

const STATUS_CONFIG: Record<
  WebSocketStatus,
  { icon: React.FC<{ className?: string }>; label: string; className: string; pulse?: boolean }
> = {
  connected: {
    icon: WifiIcon,
    label: "Connected",
    className: "text-green-600 dark:text-green-400",
  },
  connecting: {
    icon: RefreshIcon,
    label: "Connecting...",
    className: "text-yellow-600 dark:text-yellow-400",
    pulse: true,
  },
  reconnecting: {
    icon: RefreshIcon,
    label: "Reconnecting...",
    className: "text-yellow-600 dark:text-yellow-400",
    pulse: true,
  },
  disconnected: {
    icon: WifiOffIcon,
    label: "Disconnected",
    className: "text-muted-foreground",
  },
  error: {
    icon: WifiOffIcon,
    label: "Connection error",
    className: "text-red-600 dark:text-red-400",
  },
};

interface ConnectionStatusProps {
  /** WebSocket connection status */
  status: WebSocketStatus;
  /** Whether to show the status label */
  showLabel?: boolean;
  /** Short label variant (e.g., "Live" instead of "Connected") */
  shortLabel?: boolean;
  /** Current reconnect attempt number (for reconnecting status) */
  reconnectAttempt?: number;
  /** Optional additional className */
  className?: string;
}

/**
 * A reusable connection status indicator component.
 * Shows connection state with appropriate icon and optional label.
 *
 * @example
 * ```tsx
 * // Icon only
 * <ConnectionStatus status={wsStatus} />
 *
 * // With label
 * <ConnectionStatus status={wsStatus} showLabel />
 *
 * // With short label and reconnect info
 * <ConnectionStatus status={wsStatus} showLabel shortLabel reconnectAttempt={3} />
 * ```
 */
export function ConnectionStatus({
  status,
  showLabel = true,
  shortLabel = false,
  reconnectAttempt,
  className,
}: ConnectionStatusProps) {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  const getLabel = () => {
    if (!showLabel) return null;

    if (shortLabel) {
      switch (status) {
        case "connected":
          return "Live";
        case "connecting":
          return "Connecting";
        case "reconnecting":
          return reconnectAttempt ? `Retry ${reconnectAttempt}` : "Reconnecting";
        case "disconnected":
          return "Offline";
        case "error":
          return "Error";
      }
    }

    if (status === "reconnecting" && reconnectAttempt) {
      return `Reconnecting (attempt ${reconnectAttempt})...`;
    }

    return config.label;
  };

  return (
    <div className={cn("flex items-center gap-1 text-xs", config.className, className)}>
      <Icon className={cn(config.pulse && "animate-spin")} />
      {showLabel && <span>{getLabel()}</span>}
    </div>
  );
}

/**
 * A compact badge-style connection indicator.
 * Shows a colored dot with optional pulse animation for connecting states.
 */
export function ConnectionDot({
  status,
  className,
}: {
  status: WebSocketStatus;
  className?: string;
}) {
  const dotColors: Record<WebSocketStatus, string> = {
    connected: "bg-green-500",
    connecting: "bg-yellow-500 animate-pulse",
    reconnecting: "bg-yellow-500 animate-pulse",
    disconnected: "bg-gray-400",
    error: "bg-red-500",
  };

  return (
    <span
      className={cn("inline-block w-2 h-2 rounded-full", dotColors[status], className)}
      title={STATUS_CONFIG[status].label}
    />
  );
}
