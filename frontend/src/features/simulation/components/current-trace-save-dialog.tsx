"use client";

import { LoaderCircle, Plus, Save, X } from "lucide-react";

import { AppSelectField, type AppSelectOption } from "@/features/shared/components/app-select";
import {
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";

import type {
  CreateDesignState,
  MutationState,
} from "./current-trace-save-control";

export function CurrentTraceSaveDialog({
  open,
  traceLabel,
  traceCount,
  parameterValue,
  designValue,
  designOptions,
  mutationState,
  createState,
  createName,
  canSave,
  onClose,
  onDesignChange,
  onParameterChange,
  onCreateNameChange,
  onCreateToggle,
  onCreate,
  onSave,
  showCreate,
}: Readonly<{
  open: boolean;
  traceLabel: string | null;
  traceCount: number;
  parameterValue: string;
  designValue: string;
  designOptions: readonly AppSelectOption[];
  mutationState: MutationState;
  createState: CreateDesignState;
  createName: string;
  canSave: boolean;
  onClose: () => void;
  onDesignChange: (value: string) => void;
  onParameterChange: (value: string) => void;
  onCreateNameChange: (value: string) => void;
  onCreateToggle: () => void;
  onCreate: () => void;
  onSave: () => void;
  showCreate: boolean;
}>) {
  if (!open) {
    return null;
  }

  const tone =
    mutationState.state === "error"
      ? "error"
      : createState.state === "error"
        ? "error"
        : "default";
  const feedbackMessage = mutationState.message ?? createState.message;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="save-current-trace-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/82 px-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-[1.1rem] border border-border bg-card shadow-[0_28px_90px_rgba(0,0,0,0.34)]">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2
              id="save-current-trace-dialog-title"
              className="text-base font-semibold text-foreground"
            >
              Save Traces
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {traceCount > 1
                ? `${traceCount} visible traces will be saved as separate traces in the selected Target Design Scope.`
                : traceLabel
                  ? `${traceLabel} will be saved into the selected Target Design Scope.`
                  : "Save the current explorer trace into a Target Design Scope."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/35 hover:bg-primary/10 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <AppSelectField
            label="Target Design Scope"
            value={designValue}
            onChange={onDesignChange}
            options={designOptions}
            placeholder="Select an active design scope"
          />

          <label className="block">
            <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              {traceCount > 1 ? "Parameter Prefix" : "Parameter"}
            </p>
            <input
              value={parameterValue}
              onChange={(event) => {
                onParameterChange(event.target.value);
              }}
              placeholder="Enter the saved parameter name"
              className="w-full rounded-[0.95rem] border border-border/85 bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
            />
          </label>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onCreateToggle}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              <Plus className="h-4 w-4" />
              Create New Scope
            </button>
          </div>

          {showCreate ? (
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
              <label className="block">
                <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  New Target Design Scope Name
                </p>
                <input
                  value={createName}
                  onChange={(event) => {
                    onCreateNameChange(event.target.value);
                  }}
                  placeholder="Enter a design scope name"
                  className="w-full rounded-[0.95rem] border border-border/85 bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                />
              </label>
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={onCreate}
                  disabled={createState.state === "creating"}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {createState.state === "creating" ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                  {createState.state === "creating" ? "Creating..." : "Create Scope"}
                </button>
              </div>
            </div>
          ) : null}

          {feedbackMessage ? (
            <div
              className={cx(
                "rounded-[0.9rem] border px-4 py-3 text-sm",
                resolveSurfaceInsetToneClass(tone),
              )}
            >
              {feedbackMessage}
            </div>
          ) : null}

          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={!canSave || mutationState.state === "saving"}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {mutationState.state === "saving" ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {mutationState.state === "saving" ? "Saving..." : "Save Traces"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
