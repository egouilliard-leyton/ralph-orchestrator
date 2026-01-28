"use client";

import * as React from "react";
import { useState, useCallback } from "react";
import { Branch, GitStatus } from "@/services/api";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";

// Icons as inline SVGs
function GitBranchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="6" x2="6" y1="3" y2="15" />
      <circle cx="18" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M18 9a9 9 0 0 1-9 9" />
    </svg>
  );
}

function GitPullRequestIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="18" cy="18" r="3" />
      <circle cx="6" cy="6" r="3" />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
      <line x1="6" x2="6" y1="9" y2="21" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m5 12 7-7 7 7" />
      <path d="M12 19V5" />
    </svg>
  );
}

function ArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
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

function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </svg>
  );
}

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

function ConnectionIndicator({ status }: { status: WebSocketStatus }) {
  const statusConfig: Record<WebSocketStatus, { icon: React.FC<{ className?: string }>; label: string; className: string }> = {
    connected: { icon: WifiIcon, label: "Live", className: "text-green-600" },
    connecting: { icon: RefreshIcon, label: "Connecting", className: "text-yellow-600" },
    reconnecting: { icon: RefreshIcon, label: "Reconnecting", className: "text-yellow-600" },
    disconnected: { icon: WifiOffIcon, label: "Offline", className: "text-muted-foreground" },
    error: { icon: WifiOffIcon, label: "Error", className: "text-red-600" },
  };

  const config = statusConfig[status];
  const Icon = config.icon;
  const isSpinning = status === "connecting" || status === "reconnecting";

  return (
    <div className={cn("flex items-center gap-1 text-xs", config.className)}>
      <Icon className={cn(isSpinning && "animate-spin")} />
      <span>{config.label}</span>
    </div>
  );
}

interface GitPanelProps {
  projectId: string;
  gitStatus: GitStatus | null;
  isLoading: boolean;
  error: string | null;
  wsStatus?: WebSocketStatus;
  onRefresh: () => Promise<void>;
  onCreateBranch: (name: string, baseBranch?: string) => Promise<void>;
  onSwitchBranch: (branchName: string) => Promise<void>;
  onDeleteBranch: (branchName: string) => Promise<void>;
  onCreatePR: () => void;
  className?: string;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "Just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;

  return date.toLocaleDateString();
}

function truncateCommitMessage(message: string, maxLength = 50): string {
  const firstLine = message.split("\n")[0] ?? message;
  if (firstLine.length <= maxLength) return firstLine;
  return firstLine.substring(0, maxLength - 3) + "...";
}

export function GitPanel({
  projectId,
  gitStatus,
  isLoading,
  error,
  wsStatus,
  onRefresh,
  onCreateBranch,
  onSwitchBranch,
  onDeleteBranch,
  onCreatePR,
  className,
}: GitPanelProps) {
  const [showCreateBranchDialog, setShowCreateBranchDialog] = useState(false);
  const [showDeleteConfirmDialog, setShowDeleteConfirmDialog] = useState(false);
  const [branchToDelete, setBranchToDelete] = useState<string | null>(null);
  const [newBranchName, setNewBranchName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSwitching, setIsSwitching] = useState<string | null>(null);

  const handleCreateBranch = useCallback(async () => {
    if (!newBranchName.trim()) return;

    setIsCreating(true);
    try {
      await onCreateBranch(newBranchName.trim(), gitStatus?.currentBranch);
      setNewBranchName("");
      setShowCreateBranchDialog(false);
    } finally {
      setIsCreating(false);
    }
  }, [newBranchName, gitStatus?.currentBranch, onCreateBranch]);

  const handleSwitchBranch = useCallback(async (branchName: string) => {
    setIsSwitching(branchName);
    try {
      await onSwitchBranch(branchName);
    } finally {
      setIsSwitching(null);
    }
  }, [onSwitchBranch]);

  const handleDeleteBranch = useCallback(async () => {
    if (!branchToDelete) return;

    setIsDeleting(true);
    try {
      await onDeleteBranch(branchToDelete);
      setBranchToDelete(null);
      setShowDeleteConfirmDialog(false);
    } finally {
      setIsDeleting(false);
    }
  }, [branchToDelete, onDeleteBranch]);

  const confirmDelete = useCallback((branchName: string) => {
    setBranchToDelete(branchName);
    setShowDeleteConfirmDialog(true);
  }, []);

  // Separate local and remote branches
  const localBranches = gitStatus?.branches.filter(b => !b.isRemote) ?? [];

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <GitBranchIcon className="size-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Git</CardTitle>
              {gitStatus && (
                <CardDescription className="mt-1">
                  <span className="font-mono text-xs font-semibold text-foreground">
                    {gitStatus.currentBranch}
                  </span>
                  {gitStatus.isDirty && (
                    <Badge variant="warning" className="ml-2">
                      uncommitted changes
                    </Badge>
                  )}
                </CardDescription>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {wsStatus && (
              <>
                <ConnectionIndicator status={wsStatus} />
                <div className="w-px h-4 bg-border mx-1" />
              </>
            )}
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onRefresh}
              disabled={isLoading}
              title="Refresh"
            >
              <RefreshIcon className={cn("size-4", isLoading && "animate-spin")} />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 space-y-4">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Current Branch Status */}
        {gitStatus && (
          <div className="rounded-md bg-muted/50 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Current Branch</span>
              </div>
              <div className="flex items-center gap-2">
                {localBranches.find(b => b.isCurrent)?.ahead ? (
                  <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                    <ArrowUpIcon className="size-3" />
                    {localBranches.find(b => b.isCurrent)?.ahead}
                  </span>
                ) : null}
                {localBranches.find(b => b.isCurrent)?.behind ? (
                  <span className="flex items-center gap-1 text-xs text-yellow-600 dark:text-yellow-400">
                    <ArrowDownIcon className="size-3" />
                    {localBranches.find(b => b.isCurrent)?.behind}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="mt-2 font-mono text-lg font-bold">
              {gitStatus.currentBranch}
            </div>
            {localBranches.find(b => b.isCurrent)?.lastCommit && (
              <div className="mt-2 text-xs text-muted-foreground">
                <span className="font-mono">
                  {localBranches.find(b => b.isCurrent)?.lastCommit.sha.substring(0, 7)}
                </span>
                {" - "}
                {truncateCommitMessage(
                  localBranches.find(b => b.isCurrent)?.lastCommit.message ?? ""
                )}
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={() => setShowCreateBranchDialog(true)}
          >
            <PlusIcon className="size-4 mr-1" />
            New Branch
          </Button>
          <Button
            variant="default"
            size="sm"
            className="flex-1"
            onClick={onCreatePR}
          >
            <GitPullRequestIcon className="size-4 mr-1" />
            Create PR
          </Button>
        </div>

        {/* Branch List */}
        <div className="space-y-2">
          <div className="text-sm font-medium text-muted-foreground">
            Local Branches ({localBranches.length})
          </div>
          <div className="max-h-64 overflow-y-auto space-y-1">
            {localBranches.map((branch) => (
              <BranchItem
                key={branch.name}
                branch={branch}
                isSwitching={isSwitching === branch.name}
                onSwitch={() => handleSwitchBranch(branch.name)}
                onDelete={() => confirmDelete(branch.name)}
              />
            ))}
            {localBranches.length === 0 && (
              <div className="text-sm text-muted-foreground text-center py-4">
                No branches found
              </div>
            )}
          </div>
        </div>
      </CardContent>

      {/* Create Branch Dialog */}
      <Dialog open={showCreateBranchDialog} onOpenChange={setShowCreateBranchDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Branch</DialogTitle>
            <DialogDescription>
              Create a new branch from {gitStatus?.currentBranch ?? "current branch"}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label htmlFor="branch-name" className="text-sm font-medium">
                Branch Name
              </label>
              <Input
                id="branch-name"
                placeholder="feature/my-new-feature"
                value={newBranchName}
                onChange={(e) => setNewBranchName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isCreating) {
                    void handleCreateBranch();
                  }
                }}
              />
              <p className="text-xs text-muted-foreground">
                Use kebab-case with a prefix like feature/, fix/, or chore/
              </p>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              onClick={handleCreateBranch}
              disabled={!newBranchName.trim() || isCreating}
            >
              {isCreating ? "Creating..." : "Create Branch"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteConfirmDialog} onOpenChange={setShowDeleteConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Branch</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the branch{" "}
              <span className="font-mono font-semibold">{branchToDelete}</span>?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={handleDeleteBranch}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting..." : "Delete Branch"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

interface BranchItemProps {
  branch: Branch;
  isSwitching: boolean;
  onSwitch: () => void;
  onDelete: () => void;
}

function BranchItem({ branch, isSwitching, onSwitch, onDelete }: BranchItemProps) {
  return (
    <div
      className={cn(
        "group flex items-center justify-between rounded-md px-3 py-2 text-sm",
        branch.isCurrent
          ? "bg-primary/10 border border-primary/20"
          : "hover:bg-muted/50"
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "font-mono truncate",
              branch.isCurrent && "font-semibold"
            )}
            title={branch.name}
          >
            {branch.name}
          </span>
          {branch.isCurrent && (
            <CheckIcon className="size-3 text-primary shrink-0" />
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
          <span className="font-mono">
            {branch.lastCommit.sha.substring(0, 7)}
          </span>
          <span className="truncate" title={branch.lastCommit.message}>
            {truncateCommitMessage(branch.lastCommit.message, 30)}
          </span>
          <span className="shrink-0">
            {formatRelativeTime(branch.lastCommit.timestamp)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1 ml-2">
        {/* Ahead/Behind indicators */}
        {branch.ahead > 0 && (
          <span className="flex items-center gap-0.5 text-xs text-green-600 dark:text-green-400">
            <ArrowUpIcon className="size-3" />
            {branch.ahead}
          </span>
        )}
        {branch.behind > 0 && (
          <span className="flex items-center gap-0.5 text-xs text-yellow-600 dark:text-yellow-400">
            <ArrowDownIcon className="size-3" />
            {branch.behind}
          </span>
        )}

        {/* Actions */}
        {!branch.isCurrent && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onSwitch}
              disabled={isSwitching}
              title="Switch to this branch"
            >
              {isSwitching ? (
                <RefreshIcon className="size-3 animate-spin" />
              ) : (
                <CheckIcon className="size-3" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onDelete}
              className="text-destructive hover:text-destructive"
              title="Delete branch"
            >
              <TrashIcon className="size-3" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
