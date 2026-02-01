"use client";

import { cn } from "@/lib/utils";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { WifiIcon, WifiOffIcon, RefreshIcon } from "@/components/ui/icons";

interface ConnectionIndicatorProps {
  status: WebSocketStatus;
}

const statusConfig: Record<
  WebSocketStatus,
  { icon: React.FC<{ className?: string }>; label: string; className: string }
> = {
  connected: { icon: WifiIcon, label: "Connected", className: "text-green-600" },
  connecting: { icon: RefreshIcon, label: "Connecting...", className: "text-yellow-600 animate-spin" },
  reconnecting: { icon: RefreshIcon, label: "Reconnecting...", className: "text-yellow-600 animate-spin" },
  disconnected: { icon: WifiOffIcon, label: "Disconnected", className: "text-muted-foreground" },
  error: { icon: WifiOffIcon, label: "Connection error", className: "text-red-600" },
};

export function ConnectionIndicator({ status }: ConnectionIndicatorProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn("flex items-center gap-1 text-xs", config.className)}>
      <Icon />
      <span>{config.label}</span>
    </div>
  );
}
