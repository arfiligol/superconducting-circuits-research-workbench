"use client";

import { useState } from "react";
import { LoaderCircle, Plus, X } from "lucide-react";

import { SearchField } from "@/features/data-browser/components/raw-data-browser-controls";
import {
  formatCoverage,
  readinessTone,
} from "@/features/data-browser/lib/raw-data-browser-formatters";
import { AppSelectField, type AppSelectOption } from "@/features/shared/components/app-select";
import {
  SurfaceActionButton,
  SurfacePanel,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";

import type { CursorMeta, DesignBrowseRow } from "@/features/data-browser/lib/contracts";

type LifecycleDialog = "create" | "rename" | "merge" | "archive" | "delete" | null;

function lifecycleTone(state: DesignBrowseRow["lifecycle_state"]) {
  if (state === "active") {
    return "success" as const;
  }
  if (state === "archived") {
    return "warning" as const;
  }
  return "default" as const;
}

function DesignSummaryTile({
  label,
  value,
}: Readonly<{
  label: string;
  value: string;
}>) {
  return (
    <div className="min-w-0 rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-sm font-medium text-foreground [overflow-wrap:anywhere]">
        {value}
      </p>
    </div>
  );
}

function DesignScopeTextDialog({
  open,
  title,
  description,
  label,
  value,
  confirmLabel,
  isPending,
  feedbackMessage,
  onValueChange,
  onCancel,
  onConfirm,
}: Readonly<{
  open: boolean;
  title: string;
  description: string;
  label: string;
  value: string;
  confirmLabel: string;
  isPending: boolean;
  feedbackMessage: string | null;
  onValueChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}>) {
  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/75 px-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/35 hover:bg-primary/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <label className="mt-5 block rounded-xl border border-border bg-surface px-4 py-3">
          <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            {label}
          </span>
          <input
            value={value}
            onChange={(event) => {
              onValueChange(event.target.value);
            }}
            disabled={isPending}
            className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            placeholder="PF6FQ Q0"
          />
        </label>
        {feedbackMessage ? (
          <div className="mt-4 rounded-[0.9rem] border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
            {feedbackMessage}
          </div>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <SurfaceActionButton onClick={onCancel} disabled={isPending} shape="soft">
            Cancel
          </SurfaceActionButton>
          <SurfaceActionButton onClick={onConfirm} disabled={isPending || !value.trim()}>
            {isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            {confirmLabel}
          </SurfaceActionButton>
        </div>
      </div>
    </div>
  );
}

function DesignScopeMergeDialog({
  open,
  sourceDesign,
  options,
  targetValue,
  isPending,
  feedbackMessage,
  onTargetChange,
  onCancel,
  onConfirm,
}: Readonly<{
  open: boolean;
  sourceDesign: DesignBrowseRow | null;
  options: readonly AppSelectOption[];
  targetValue: string;
  isPending: boolean;
  feedbackMessage: string | null;
  onTargetChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}>) {
  if (!open || !sourceDesign) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/75 px-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground">Merge Design Scope</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Merge {sourceDesign.name} into another active scope. The backend owns all re-parenting; the page clears stale trace preview and selection after success.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/35 hover:bg-primary/10 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-5">
          <AppSelectField
            label="Active Target Design Scope"
            value={targetValue}
            onChange={onTargetChange}
            options={options}
            placeholder="Choose merge target"
            disabled={isPending}
          />
        </div>
        {feedbackMessage ? (
          <div className="mt-4 rounded-[0.9rem] border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
            {feedbackMessage}
          </div>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <SurfaceActionButton onClick={onCancel} disabled={isPending} shape="soft">
            Cancel
          </SurfaceActionButton>
          <SurfaceActionButton onClick={onConfirm} disabled={isPending || !targetValue}>
            {isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            Merge Scope
          </SurfaceActionButton>
        </div>
      </div>
    </div>
  );
}

export function RawDataDesignScopesPanel({
  designsError,
  isDesignsLoading,
  deferredDesignSearch,
  designSearch,
  setDesignSearch,
  designs,
  selectedDesignId,
  setSelectedDesignId,
  selectedDesign,
  designsMeta,
  goToPrevDesignPage,
  goToNextDesignPage,
  activeDesigns,
  designLifecycleState,
  createDesignScope,
  renameSelectedDesignScope,
  mergeSelectedDesignScope,
  archiveSelectedDesignScope,
  deleteSelectedDesignScope,
}: Readonly<{
  designsError: Error | undefined;
  isDesignsLoading: boolean;
  deferredDesignSearch: string;
  designSearch: string;
  setDesignSearch: (value: string) => void;
  designs: readonly DesignBrowseRow[];
  selectedDesignId: string | null;
  setSelectedDesignId: (designId: string) => void;
  selectedDesign: DesignBrowseRow | null;
  designsMeta: CursorMeta | undefined;
  goToPrevDesignPage: () => void;
  goToNextDesignPage: () => void;
  activeDesigns: readonly DesignBrowseRow[];
  designLifecycleState: Readonly<{
    state: "idle" | "submitting" | "error";
    message: string | null;
  }>;
  createDesignScope: (name: string) => Promise<void>;
  renameSelectedDesignScope: (name: string) => Promise<void>;
  mergeSelectedDesignScope: (targetDesignId: string) => Promise<void>;
  archiveSelectedDesignScope: () => Promise<void>;
  deleteSelectedDesignScope: () => Promise<void>;
}>) {
  const [activeDialog, setActiveDialog] = useState<LifecycleDialog>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [mergeTargetId, setMergeTargetId] = useState("");
  const isLifecyclePending = designLifecycleState.state === "submitting";
  const mergeOptions = activeDesigns
    .filter((design) => design.design_id !== selectedDesign?.design_id)
    .map((design) => ({
      value: design.design_id,
      label: design.name,
      description: `${design.trace_count} traces · ${design.design_id}`,
    }));

  return (
    <SurfacePanel
      title="Design Scopes"
      description="Start with a design here, then move straight into trace summaries and the preview path."
    >
      {designsError ? (
        <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
          Unable to load design scopes. {designsError.message}
        </div>
      ) : null}
      {designLifecycleState.state === "error" && designLifecycleState.message ? (
        <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
          {designLifecycleState.message}
        </div>
      ) : null}
      {isDesignsLoading ? (
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          Loading designs for {deferredDesignSearch || "the active dataset"}...
        </div>
      ) : designs.length > 0 ? (
        <div className="mt-4 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.42fr)] xl:items-start">
          <div className="space-y-4">
            <SearchField
              label="Search Design"
              placeholder="Search design name or id"
              value={designSearch}
              onChange={setDesignSearch}
            />
            <div className="flex justify-end">
              <SurfaceActionButton
                onClick={() => {
                  setNameDraft("");
                  setActiveDialog("create");
                }}
              >
                <Plus className="h-4 w-4" />
                Create Design Scope
              </SurfaceActionButton>
            </div>
            <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
              <div className="space-y-3">
                {designs.map((design) => (
                  <button
                    key={design.design_id}
                    type="button"
                    onClick={() => {
                      setSelectedDesignId(design.design_id);
                    }}
                    className={cx(
                      "w-full cursor-pointer rounded-xl border px-4 py-4 text-left transition",
                      design.design_id === selectedDesignId
                        ? "border-primary/40 bg-primary/10"
                        : "border-border bg-background hover:border-primary/25",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-foreground">{design.name}</h3>
                        <p className="mt-1 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]">
                          {formatCoverage(design.source_coverage)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col gap-2">
                        <SurfaceTag tone={readinessTone(design.compare_readiness)}>
                          {design.compare_readiness}
                        </SurfaceTag>
                        <SurfaceTag tone={lifecycleTone(design.lifecycle_state)}>
                          {design.lifecycle_state}
                        </SurfaceTag>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      <span>{design.trace_count} traces</span>
                      <span className="truncate">{design.updated_at}</span>
                    </div>
                  </button>
                ))}
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-border/80 pt-4 text-sm">
                <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  Up to {designsMeta?.limit ?? 6} design scopes per page
                </p>
                <div className="flex items-center gap-2">
                  <SurfaceActionButton
                    onClick={goToPrevDesignPage}
                    disabled={!designsMeta?.prev_cursor}
                    shape="soft"
                  >
                    Previous
                  </SurfaceActionButton>
                  <SurfaceActionButton
                    onClick={goToNextDesignPage}
                    disabled={!designsMeta?.next_cursor}
                    shape="soft"
                  >
                    Next
                  </SurfaceActionButton>
                </div>
              </div>
            </div>
          </div>

          {selectedDesign ? (
            <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)] xl:max-w-[22rem] xl:justify-self-end">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/80 pb-4">
                <div className="min-w-0">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Selected Design
                  </p>
                  <h3 className="mt-2 text-base font-semibold text-foreground">
                    {selectedDesign.name}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">{selectedDesign.design_id}</p>
                </div>
                <div className="flex flex-col gap-2">
                  <SurfaceTag tone={readinessTone(selectedDesign.compare_readiness)}>
                    {selectedDesign.compare_readiness}
                  </SurfaceTag>
                  <SurfaceTag tone={lifecycleTone(selectedDesign.lifecycle_state)}>
                    {selectedDesign.lifecycle_state}
                  </SurfaceTag>
                </div>
              </div>
              {selectedDesign.redirect_design_id ? (
                <p className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-foreground">
                  Redirect target: {selectedDesign.redirect_design_id}
                </p>
              ) : null}
              <div className="mt-4 flex flex-col gap-3">
                <DesignSummaryTile label="Lifecycle" value={selectedDesign.lifecycle_state} />
                <DesignSummaryTile
                  label="Source Coverage"
                  value={formatCoverage(selectedDesign.source_coverage)}
                />
                <DesignSummaryTile
                  label="Browse State"
                  value={
                    selectedDesign.compare_readiness === "ready"
                      ? "Ready for compare-aware browsing"
                      : selectedDesign.compare_readiness === "inspect_only"
                        ? "Single-source inspection only"
                        : "Blocked until more traces arrive"
                  }
                />
                <DesignSummaryTile label="Trace Count" value={String(selectedDesign.trace_count)} />
                <DesignSummaryTile label="Updated" value={selectedDesign.updated_at} />
                <DesignSummaryTile
                  label="Mutation Policy"
                  value={selectedDesign.mutation_policy_summary}
                />
                <div className="flex flex-wrap gap-2 pt-1">
                  <SurfaceActionButton
                    onClick={() => {
                      setNameDraft(selectedDesign.name);
                      setActiveDialog("rename");
                    }}
                    disabled={!selectedDesign.allowed_actions.rename}
                    shape="soft"
                  >
                    Rename
                  </SurfaceActionButton>
                  <SurfaceActionButton
                    onClick={() => {
                      setMergeTargetId("");
                      setActiveDialog("merge");
                    }}
                    disabled={!selectedDesign.allowed_actions.merge || mergeOptions.length === 0}
                    shape="soft"
                  >
                    Merge
                  </SurfaceActionButton>
                  <SurfaceActionButton
                    onClick={() => {
                      setActiveDialog("archive");
                    }}
                    disabled={!selectedDesign.allowed_actions.archive}
                    tone="destructive"
                  >
                    Archive
                  </SurfaceActionButton>
                  <SurfaceActionButton
                    onClick={() => {
                      setActiveDialog("delete");
                    }}
                    disabled={!selectedDesign.allowed_actions.delete}
                    tone="destructive"
                  >
                    Delete
                  </SurfaceActionButton>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground xl:max-w-[22rem] xl:justify-self-end">
              Select a design scope to browse its trace summaries.
            </div>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            No design scopes are available for the active dataset.
          </div>
          <SurfaceActionButton
            onClick={() => {
              setNameDraft("");
              setActiveDialog("create");
            }}
          >
            <Plus className="h-4 w-4" />
            Create Design Scope
          </SurfaceActionButton>
        </div>
      )}

      <DesignScopeTextDialog
        open={activeDialog === "create"}
        title="Create Design Scope"
        description="Create an active dataset-local scope that ingestion, simulation publication, and characterization can target explicitly."
        label="Display Name"
        value={nameDraft}
        confirmLabel="Create Scope"
        isPending={isLifecyclePending}
        feedbackMessage={designLifecycleState.message}
        onValueChange={setNameDraft}
        onCancel={() => {
          setActiveDialog(null);
        }}
        onConfirm={() => {
          void createDesignScope(nameDraft).then(() => {
            setActiveDialog(null);
          });
        }}
      />
      <DesignScopeTextDialog
        open={activeDialog === "rename"}
        title="Rename Design Scope"
        description="Rename changes only the display label. The design_id remains stable."
        label="Display Name"
        value={nameDraft}
        confirmLabel="Rename Scope"
        isPending={isLifecyclePending}
        feedbackMessage={designLifecycleState.message}
        onValueChange={setNameDraft}
        onCancel={() => {
          setActiveDialog(null);
        }}
        onConfirm={() => {
          void renameSelectedDesignScope(nameDraft).then(() => {
            setActiveDialog(null);
          });
        }}
      />
      <DesignScopeMergeDialog
        open={activeDialog === "merge"}
        sourceDesign={selectedDesign}
        options={mergeOptions}
        targetValue={mergeTargetId}
        isPending={isLifecyclePending}
        feedbackMessage={designLifecycleState.message}
        onTargetChange={setMergeTargetId}
        onCancel={() => {
          setActiveDialog(null);
        }}
        onConfirm={() => {
          void mergeSelectedDesignScope(mergeTargetId).then(() => {
            setActiveDialog(null);
          });
        }}
      />
      <ConfirmActionDialog
        open={activeDialog === "archive"}
        title="Archive Design Scope"
        description="Archive this scope? It will stop appearing as a normal target selector option. Backend lifecycle rules decide whether a redirect target is available."
        confirmLabel="Archive Scope"
        tone="destructive"
        isPending={isLifecyclePending}
        onCancel={() => {
          setActiveDialog(null);
        }}
        onConfirm={() => {
          void archiveSelectedDesignScope().then(() => {
            setActiveDialog(null);
          });
        }}
      />
      <ConfirmActionDialog
        open={activeDialog === "delete"}
        title="Delete Design Scope"
        description="Delete this scope? This is a backend lifecycle request; the frontend will not re-parent traces or rewrite store references."
        confirmLabel="Delete Scope"
        tone="destructive"
        isPending={isLifecyclePending}
        onCancel={() => {
          setActiveDialog(null);
        }}
        onConfirm={() => {
          void deleteSelectedDesignScope().then(() => {
            setActiveDialog(null);
          });
        }}
      />
    </SurfacePanel>
  );
}
