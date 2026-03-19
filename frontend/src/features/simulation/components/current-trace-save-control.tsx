"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, LoaderCircle, Plus, Save, X } from "lucide-react";
import useSWR from "swr";
import { useSWRConfig } from "swr";

import { buildRawDataBrowseHref } from "@/features/data-browser/lib/browse-state";
import { AppSelectField, type AppSelectOption } from "@/features/shared/components/app-select";
import {
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";
import {
  createDatasetDesign,
  listDesignBrowseRows,
  type DesignBrowseRow,
} from "@/lib/api/datasets";
import {
  publishSimulationResultTrace,
  taskDetailKey,
  type PublishedSimulationTrace,
  type TaskDetail,
} from "@/lib/api/tasks";

type CurrentTraceSaveControlProps = Readonly<{
  task: TaskDetail;
  activeDatasetId: string | null;
  traceKey: string | null;
  traceLabel: string | null;
}>;

type MutationState = Readonly<{
  state: "idle" | "saving" | "error";
  message: string | null;
}>;

type CreateDesignState = Readonly<{
  state: "idle" | "creating" | "error";
  message: string | null;
}>;

type SavedTraceState = Readonly<{
  designId: string;
  designName: string;
  trace: PublishedSimulationTrace;
}>;

async function listAllDatasetDesigns(datasetId: string) {
  const rows: DesignBrowseRow[] = [];
  let cursor: string | null = null;

  do {
    const page = await listDesignBrowseRows(datasetId, { cursor });
    rows.push(...page.rows);
    cursor = page.meta?.next_cursor ?? null;
  } while (cursor);

  return rows;
}

function sortDesignRows(rows: readonly DesignBrowseRow[]) {
  return [...rows].sort((left, right) => left.name.localeCompare(right.name));
}

function describePublishError(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.errorCode) {
      case "design_not_found":
        return "The selected design is no longer available. Choose another design and save again.";
      case "simulation_result_publish_not_ready":
        return "This result is not ready to save yet.";
      case "simulation_result_publish_task_invalid":
        return "Only completed results can save the current trace.";
      default:
        break;
    }

    switch (error.category) {
      case "validation_error":
        return "Choose a design before saving this trace.";
      case "not_found":
        return "The active dataset or selected design is no longer available.";
      case "conflict":
        return "This trace cannot be saved in its current state.";
      default:
        break;
    }
  }

  return "Unable to save the current trace right now.";
}

function describeCreateDesignError(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.errorCode) {
      case "dataset_design_conflict":
        return "A design with this name already exists. Select it from the list or choose a different name.";
      default:
        break;
    }

    switch (error.category) {
      case "validation_error":
        return "Enter a valid design name before creating it.";
      case "not_found":
        return "The active dataset is no longer available for design creation.";
      default:
        break;
    }
  }

  return "Unable to create a new design right now.";
}

function SaveDialog({
  open,
  traceLabel,
  designValue,
  designOptions,
  mutationState,
  createState,
  createName,
  canSave,
  onClose,
  onDesignChange,
  onCreateNameChange,
  onCreateToggle,
  onCreate,
  onSave,
  showCreate,
}: Readonly<{
  open: boolean;
  traceLabel: string | null;
  designValue: string;
  designOptions: readonly AppSelectOption[];
  mutationState: MutationState;
  createState: CreateDesignState;
  createName: string;
  canSave: boolean;
  onClose: () => void;
  onDesignChange: (value: string) => void;
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
              Save Current Trace
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {traceLabel ? `${traceLabel} will be saved into the selected design.` : "Save the current explorer trace into a design."}
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
            label="Design"
            value={designValue}
            onChange={onDesignChange}
            options={designOptions}
            placeholder="Select a design"
          />

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onCreateToggle}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              <Plus className="h-4 w-4" />
              New Design
            </button>
          </div>

          {showCreate ? (
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
              <label className="block">
                <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Design Name
                </p>
                <input
                  value={createName}
                  onChange={(event) => {
                    onCreateNameChange(event.target.value);
                  }}
                  placeholder="Enter a design name"
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
                  {createState.state === "creating" ? "Creating..." : "Create Design"}
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
              {mutationState.state === "saving" ? "Saving..." : "Save Current Trace"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function CurrentTraceSaveControl({
  task,
  activeDatasetId,
  traceKey,
  traceLabel,
}: CurrentTraceSaveControlProps) {
  const { mutate } = useSWRConfig();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedDesignId, setSelectedDesignId] = useState("");
  const [showCreateDesign, setShowCreateDesign] = useState(false);
  const [newDesignName, setNewDesignName] = useState("");
  const [mutationState, setMutationState] = useState<MutationState>({
    state: "idle",
    message: null,
  });
  const [createDesignState, setCreateDesignState] = useState<CreateDesignState>({
    state: "idle",
    message: null,
  });
  const [savedTraceState, setSavedTraceState] = useState<SavedTraceState | null>(null);

  const designListQuery = useSWR(
    activeDatasetId ? ["dataset-designs-for-trace-save", activeDatasetId] : null,
    ([, datasetId]: readonly [string, string]) => listAllDatasetDesigns(datasetId),
  );
  const designOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      sortDesignRows(designListQuery.data ?? []).map((design) => ({
        value: design.design_id,
        label: design.name,
        description: `Design ${design.design_id}`,
      })),
    [designListQuery.data],
  );

  useEffect(() => {
    if (!selectedDesignId && designOptions[0]) {
      setSelectedDesignId(designOptions[0].value);
    }
  }, [designOptions, selectedDesignId]);

  const rawDataHref = useMemo(() => {
    if (!savedTraceState) {
      return null;
    }

    return buildRawDataBrowseHref({
      designId: savedTraceState.designId,
      traceId: savedTraceState.trace.traceId,
      designQuery: savedTraceState.designName,
    });
  }, [savedTraceState]);
  const saveDisabled = !activeDatasetId || !traceKey;

  async function handleCreateDesign() {
    if (!activeDatasetId) {
      setCreateDesignState({
        state: "error",
        message: "Attach an active dataset before creating a design.",
      });
      return;
    }

    if (!newDesignName.trim()) {
      setCreateDesignState({
        state: "error",
        message: "Enter a valid design name before creating it.",
      });
      return;
    }

    setCreateDesignState({ state: "creating", message: null });

    try {
      const result = await createDatasetDesign(activeDatasetId, {
        name: newDesignName.trim(),
      });
      await designListQuery.mutate(
        (current) => sortDesignRows([...(current ?? []), result.design]),
        { revalidate: false },
      );
      setSelectedDesignId(result.design.design_id);
      setNewDesignName("");
      setShowCreateDesign(false);
      setCreateDesignState({ state: "idle", message: null });
    } catch (error) {
      setCreateDesignState({
        state: "error",
        message: describeCreateDesignError(error),
      });
    }
  }

  async function handleSaveTrace() {
    if (!traceKey || !selectedDesignId) {
      setMutationState({
        state: "error",
        message: "Choose a design before saving the current trace.",
      });
      return;
    }

    setMutationState({ state: "saving", message: null });

    try {
      const result = await publishSimulationResultTrace(task.taskId, {
        traceKey,
        designId: selectedDesignId,
      });
      await mutate(taskDetailKey(task.taskId), result.task, { revalidate: false });
      setSavedTraceState({
        designId: result.design.designId,
        designName: result.design.name,
        trace: result.trace,
      });
      setMutationState({ state: "idle", message: null });
      setIsDialogOpen(false);
    } catch (error) {
      setMutationState({
        state: "error",
        message: describePublishError(error),
      });
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setMutationState({ state: "idle", message: null });
            setCreateDesignState({ state: "idle", message: null });
            setShowCreateDesign(false);
            setIsDialogOpen(true);
          }}
          disabled={saveDisabled}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Save className="h-4 w-4" />
          Save Current Trace
        </button>

        {savedTraceState ? (
          <>
            <SurfaceTag tone="success">Saved to {savedTraceState.designName}</SurfaceTag>
            {rawDataHref ? (
              <Link
                href={rawDataHref}
                className="inline-flex items-center gap-2 text-sm font-medium text-primary transition hover:opacity-80"
              >
                Open Saved Trace in Raw Data
                <ExternalLink className="h-4 w-4" />
              </Link>
            ) : null}
          </>
        ) : null}
      </div>

      <SaveDialog
        open={isDialogOpen}
        traceLabel={traceLabel}
        designValue={selectedDesignId}
        designOptions={designOptions}
        mutationState={mutationState}
        createState={createDesignState}
        createName={newDesignName}
        canSave={!saveDisabled && !!selectedDesignId}
        onClose={() => {
          setIsDialogOpen(false);
        }}
        onDesignChange={setSelectedDesignId}
        onCreateNameChange={setNewDesignName}
        onCreateToggle={() => {
          setCreateDesignState({ state: "idle", message: null });
          setShowCreateDesign((current) => !current);
        }}
        onCreate={() => {
          void handleCreateDesign();
        }}
        onSave={() => {
          void handleSaveTrace();
        }}
        showCreate={showCreateDesign}
      />
    </>
  );
}
