"use client";

import * as React from "react";
import { useState, useCallback, useEffect } from "react";
import { PRResult, CreatePRRequest } from "@/services/api";
import { Button } from "@/components/ui/button";
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

function CheckCircleIcon({ className }: { className?: string }) {
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
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <path d="m9 11 3 3L22 4" />
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

interface CreatePRModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentBranch: string;
  baseBranch: string;
  acceptanceCriteria?: string[];
  taskTitle?: string;
  onCreatePR: (data: CreatePRRequest) => Promise<PRResult>;
}

export function CreatePRModal({
  open,
  onOpenChange,
  currentBranch,
  baseBranch,
  acceptanceCriteria,
  taskTitle,
  onCreatePR,
}: CreatePRModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prResult, setPrResult] = useState<PRResult | null>(null);

  // Generate default title from branch name
  useEffect(() => {
    if (open && !title) {
      // If we have a task title, use it
      if (taskTitle) {
        setTitle(taskTitle);
      } else {
        // Otherwise, try to generate from branch name
        // e.g., "feature/add-git-panel" -> "Add git panel"
        const branchParts = currentBranch.split("/");
        const branchName = branchParts[branchParts.length - 1] ?? currentBranch;
        const formatted = branchName
          .replace(/-/g, " ")
          .replace(/_/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase());
        setTitle(formatted);
      }
    }
  }, [open, currentBranch, taskTitle, title]);

  // Generate default description from acceptance criteria
  useEffect(() => {
    if (open && !description && acceptanceCriteria && acceptanceCriteria.length > 0) {
      const criteriaList = acceptanceCriteria
        .map((c) => `- [ ] ${c}`)
        .join("\n");
      setDescription(`## Changes\n\nDescribe your changes here.\n\n## Acceptance Criteria\n\n${criteriaList}`);
    }
  }, [open, acceptanceCriteria, description]);

  const handleCreate = useCallback(async () => {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      const result = await onCreatePR({
        title: title.trim(),
        description: description.trim(),
        baseBranch,
      });
      setPrResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create PR");
    } finally {
      setIsCreating(false);
    }
  }, [title, description, baseBranch, onCreatePR]);

  const handleClose = useCallback(() => {
    // Reset state when closing
    setTitle("");
    setDescription("");
    setError(null);
    setPrResult(null);
    onOpenChange(false);
  }, [onOpenChange]);

  const handleOpenPR = useCallback(() => {
    if (prResult?.url) {
      window.open(prResult.url, "_blank", "noopener,noreferrer");
    }
  }, [prResult]);

  // If PR was created successfully, show success state
  if (prResult) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircleIcon className="size-5 text-green-500" />
              Pull Request Created
            </DialogTitle>
            <DialogDescription>
              Your pull request has been created successfully.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div className="rounded-md bg-muted/50 p-4">
              <div className="flex items-center gap-2">
                <GitPullRequestIcon className="size-5 text-muted-foreground" />
                <div>
                  <div className="font-medium">{prResult.title}</div>
                  <div className="text-sm text-muted-foreground">
                    #{prResult.number}
                  </div>
                </div>
              </div>
            </div>
            <Button onClick={handleOpenPR} className="w-full">
              <ExternalLinkIcon className="size-4 mr-2" />
              Open in GitHub
            </Button>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Pull Request</DialogTitle>
          <DialogDescription>
            Create a pull request from{" "}
            <span className="font-mono font-semibold">{currentBranch}</span>
            {" "}to{" "}
            <span className="font-mono font-semibold">{baseBranch}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="pr-title" className="text-sm font-medium">
              Title
            </label>
            <Input
              id="pr-title"
              placeholder="Enter PR title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isCreating}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="pr-description" className="text-sm font-medium">
              Description
            </label>
            <textarea
              id="pr-description"
              className="flex min-h-32 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30"
              placeholder="Describe your changes..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isCreating}
            />
            <p className="text-xs text-muted-foreground">
              Supports Markdown formatting
            </p>
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={isCreating}>
              Cancel
            </Button>
          </DialogClose>
          <Button onClick={handleCreate} disabled={isCreating || !title.trim()}>
            {isCreating ? "Creating..." : "Create Pull Request"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
