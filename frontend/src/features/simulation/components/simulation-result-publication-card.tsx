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
  publishSimulationResult,
  taskDetailKey,
  tasksListKey,
  type TaskDetail,
  type TaskPublicationSummary,
} from "@/lib/api/tasks";

type SimulationResultPublicationCardProps = Readonly<{
  task: TaskDetail;
  definitionName: string | null;
  activeDatasetId: string | null;
}>;

type MutationState = Readonly<{
  state: "idle" | "saving" | "success" | "error";
  message: string | null;
}>;

type CreateDesignState = Readonly<{
  state: "idle" | "creating" | "error";
  message: string | null;
}>;

const josephsonExamplePrefix = "JosephsonCircuits Examples: ";

function derivePublicationDesignName(definitionName: string | null, taskId: number) {
  if (definitionName) {
    const trimmed = definitionName.startsWith(josephsonExamplePrefix)
      ? definitionName.slice(josephsonExamplePrefix.length)
      : definitionName;
    const normalized = trimmed.trim();
    if (normalized) {
      return normalized;
    }
  }

  return `Simulation Result ${taskId}`;
}

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

function describePublicationError(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.errorCode) {
      case "design_not_found":
        return "The selected design is no longer available. Choose another design and save again.";
      case "simulation_result_publish_not_ready":
        return "This result is not ready to save yet. Wait for the run to finish persisting its traces.";
      case "simulation_result_publish_task_invalid":
        return "Only completed simulation runs can be saved to a design from this stage.";
      default:
        break;
    }

    switch (error.category) {
      case "validation_error":
        return "Choose a design before saving this result.";
      case "not_found":
        return "The active dataset or selected design is no longer available in this workspace.";
      case "conflict":
        return "This result cannot be saved in its current lifecycle state.";
      case "persistence_error":
      case "trace_store_error":
        return error.retryable
          ? "The save failed while writing the published traces. Retry is available."
          : "The save failed while writing the published traces.";
      default:
        break;
    }
  }

  return "Unable to save this result to the selected design right now.";
}

function describeCreateDesignError(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.errorCode) {
      case "dataset_design_conflict":
        return "A design with this name already exists in the active dataset. Select it from the list or choose a different name.";
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

function publicationTone(summary: TaskPublicationSummary) {
  if (summary.state === "published") {
    return "success" as const;
  }
  if (summary.publishAllowed) {
    return "primary" as const;
  }
  return "default" as const;
}

function CreateDesignDialog({
  open,
  datasetId,
  value,
  state,
  onValueChange,
  onClose,
  onSubmit,
}: Readonly<{
  open: boolean;
  datasetId: string | null;
  value: string;
  state: CreateDesignState;
  onValueChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}>) {
  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-design-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/82 px-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-[1.1rem] border border-border bg-card shadow-[0_28px_90px_rgba(0,0,0,0.34)]">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 id="create-design-dialog-title" className="text-base font-semibold text-foreground">
              New Design
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Create a design inside the active dataset, then save this result into it.
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
          <div className="rounded-[0.9rem] border border-border/80 bg-background px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              Active Dataset
            </p>
            <p className="mt-2 text-sm font-medium text-foreground">{datasetId ?? "--"}</p>
          </div>

          <label className="block">
            <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              Design Name
            </p>
            <input
              value={value}
              onChange={(event) => {
                onValueChange(event.target.value);
              }}
              placeholder="Enter a design name"
              className="w-full rounded-[0.95rem] border border-border/85 bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
            />
          </label>

          {state.message ? (
            <div
              className={cx(
                "rounded-[0.9rem] border px-4 py-3 text-sm",
                resolveSurfaceInsetToneClass(state.state === "error" ? "error" : "primary"),
              )}
            >
              {state.message}
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
              onClick={onSubmit}
              disabled={state.state === "creating"}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {state.state === "creating" ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {state.state === "creating" ? "Creating..." : "Create Design"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SimulationResultPublicationCard({
  task,
  definitionName,
  activeDatasetId,
}: SimulationResultPublicationCardProps) {
  const { mutate } = useSWRConfig();
  const publicationSummary =
    task.publicationSummary ??
    ({
      state: "not_published",
      publishAllowed: false,
      publicationKey: null,
      targetDatasetId: null,
      targetDesignId: null,
      targetDesignName: null,
      publishedTraceIds: [],
      publishedAt: null,
      sourceTaskId: task.taskId,
      sourceResultHandleIds: task.resultRefs.resultHandles.map((handle) => handle.handleId),
    } satisfies TaskPublicationSummary);
  const targetDatasetId = task.datasetId ?? activeDatasetId ?? null;
  const initialDesignName = useMemo(
    () =>
      publicationSummary.targetDesignName ??
      derivePublicationDesignName(definitionName, task.taskId),
    [definitionName, publicationSummary.targetDesignName, task.taskId],
  );
  const designsQuery = useSWR(
    targetDatasetId ? ["simulation-publication-designs", targetDatasetId] : null,
    () => (targetDatasetId ? listAllDatasetDesigns(targetDatasetId) : Promise.resolve([])),
  );
  const designOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      sortDesignRows(designsQuery.data ?? []).map((design) => ({
        value: design.design_id,
        label: design.name,
        description: `${design.trace_count} trace${design.trace_count === 1 ? "" : "s"}`,
      })),
    [designsQuery.data],
  );
  const [selectedDesignId, setSelectedDesignId] = useState<string>("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newDesignName, setNewDesignName] = useState(initialDesignName);
  const [mutationState, setMutationState] = useState<MutationState>({
    state: "idle",
    message: null,
  });
  const [createDesignState, setCreateDesignState] = useState<CreateDesignState>({
    state: "idle",
    message: null,
  });

  useEffect(() => {
    setNewDesignName(initialDesignName);
  }, [initialDesignName]);

  useEffect(() => {
    setMutationState({ state: "idle", message: null });
    setCreateDesignState({ state: "idle", message: null });
    setIsCreateDialogOpen(false);
  }, [task.taskId]);

  useEffect(() => {
    const availableIds = new Set((designsQuery.data ?? []).map((design) => design.design_id));
    const preferredDesignId = publicationSummary.targetDesignId;

    if (preferredDesignId && availableIds.has(preferredDesignId)) {
      setSelectedDesignId(preferredDesignId);
      return;
    }

    setSelectedDesignId((current) => {
      if (current && availableIds.has(current)) {
        return current;
      }

      const firstDesignId = sortDesignRows(designsQuery.data ?? [])[0]?.design_id ?? "";
      return firstDesignId;
    });
  }, [designsQuery.data, publicationSummary.targetDesignId]);

  const publishedTraceCount = publicationSummary.publishedTraceIds.length;
  const rawDataHref = useMemo(() => {
    if (
      publicationSummary.state !== "published" ||
      !publicationSummary.targetDesignId
    ) {
      return null;
    }

    return buildRawDataBrowseHref({
      designId: publicationSummary.targetDesignId,
      traceId: publicationSummary.publishedTraceIds[0] ?? null,
      designQuery: publicationSummary.targetDesignId,
    });
  }, [
    publicationSummary.publishedTraceIds,
    publicationSummary.state,
    publicationSummary.targetDesignId,
  ]);
  const canOpenRawDataBrowser =
    rawDataHref !== null &&
    publicationSummary.targetDatasetId !== null &&
    publicationSummary.targetDatasetId === activeDatasetId;

  async function handleCreateDesign() {
    const nextDesignName = newDesignName.trim();
    if (!targetDatasetId) {
      setCreateDesignState({
        state: "error",
        message: "An active dataset is required before creating a design.",
      });
      return;
    }
    if (!nextDesignName) {
      setCreateDesignState({
        state: "error",
        message: "Design name is required.",
      });
      return;
    }

    setCreateDesignState({ state: "creating", message: null });

    try {
      const result = await createDatasetDesign(targetDatasetId, {
        name: nextDesignName,
      });

      setSelectedDesignId(result.design.design_id);
      setNewDesignName(result.design.name);
      setIsCreateDialogOpen(false);
      setCreateDesignState({ state: "idle", message: null });
      setMutationState({
        state: "success",
        message: `Created ${result.design.name}. It is now selected as the save target.`,
      });

      await designsQuery.mutate(
        (current) => sortDesignRows([...(current ?? []), result.design]),
        { revalidate: false },
      );
    } catch (error) {
      setCreateDesignState({
        state: "error",
        message: describeCreateDesignError(error),
      });
    }
  }

  async function handlePublish() {
    if (!selectedDesignId) {
      setMutationState({
        state: "error",
        message: "Choose a design before saving this result.",
      });
      return;
    }

    setMutationState({ state: "saving", message: null });
    try {
      const result = await publishSimulationResult(task.taskId, {
        datasetId: targetDatasetId,
        designId: selectedDesignId,
      });
      await mutate(taskDetailKey(task.taskId), result.task, { revalidate: false });
      await mutate(tasksListKey);
      setMutationState({
        state: "success",
        message:
          result.operation === "already_published"
            ? `This result is already saved to ${result.design.name}.`
            : `Saved this result to ${result.design.name}.`,
      });
    } catch (error) {
      setMutationState({
        state: "error",
        message: describePublicationError(error),
      });
    }
  }

  return (
    <>
      <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Save to Design
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Keep the explorer in focus, then save the published traces into a design inside the
              active dataset.
            </p>
          </div>
          <SurfaceTag tone={publicationTone(publicationSummary)}>
            {publicationSummary.state === "published"
              ? "Saved to Design"
              : publicationSummary.publishAllowed
                ? "Ready to save"
                : "Task Result only"}
          </SurfaceTag>
        </div>

        <div className="mt-4 rounded-[0.95rem] border border-border bg-card px-4 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <SurfaceTag tone="default">Active Dataset</SurfaceTag>
            <p className="text-xs text-muted-foreground">Shell context</p>
          </div>
          <p className="mt-3 text-sm font-medium text-foreground">{targetDatasetId ?? "--"}</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Dataset context is fixed here. Choose the design that should own this saved result.
          </p>
        </div>

        {publicationSummary.state === "published" ? (
          <div className="mt-4 rounded-[0.95rem] border border-border bg-card px-4 py-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
              <div className="rounded-[0.85rem] border border-border/80 bg-background px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Saved Design
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {publicationSummary.targetDesignName ??
                    publicationSummary.targetDesignId ??
                    "--"}
                </p>
              </div>
              <div className="rounded-[0.85rem] border border-border/80 bg-background px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Published Traces
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {publishedTraceCount} trace{publishedTraceCount === 1 ? "" : "s"}
                </p>
              </div>
            </div>

            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              This result is already saved to the selected design. Open the saved design in Raw Data
              when you want to inspect the published traces directly.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              {canOpenRawDataBrowser && rawDataHref ? (
                <Link
                  href={rawDataHref}
                  className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Open Saved Design in Raw Data
                </Link>
              ) : null}
              {!canOpenRawDataBrowser && publicationSummary.targetDatasetId ? (
                <p className="text-xs leading-5 text-muted-foreground">
                  Activate dataset {publicationSummary.targetDatasetId} in the shell before opening
                  the saved design in Raw Data.
                </p>
              ) : null}
            </div>
          </div>
        ) : publicationSummary.publishAllowed ? (
          <div className="mt-4 rounded-[0.95rem] border border-border bg-card px-4 py-4">
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <AppSelectField
                label="Design"
                value={selectedDesignId}
                onChange={setSelectedDesignId}
                options={designOptions}
                placeholder={
                  designsQuery.isLoading ? "Loading designs..." : "Choose a design"
                }
                disabled={!targetDatasetId || designsQuery.isLoading || designOptions.length === 0}
              />
              <button
                type="button"
                onClick={() => {
                  setCreateDesignState({ state: "idle", message: null });
                  setMutationState({ state: "idle", message: null });
                  setNewDesignName(initialDesignName);
                  setIsCreateDialogOpen(true);
                }}
                disabled={!targetDatasetId}
                className="inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-full border border-border bg-background px-4 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Plus className="h-4 w-4" />
                New Design
              </button>
            </div>

            {designsQuery.error ? (
              <div
                className={cx(
                  "mt-3 rounded-[0.9rem] border px-4 py-3 text-sm",
                  resolveSurfaceInsetToneClass("error"),
                )}
              >
                Unable to load designs from the active dataset right now.
              </div>
            ) : null}

            {!designsQuery.isLoading && designOptions.length === 0 ? (
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                No designs are available in the active dataset yet. Create one, then save this
                result into it.
              </p>
            ) : null}

            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Saving publishes the current result into the selected design without changing the run
              itself.
            </p>

            <div className="mt-4">
              <button
                type="button"
                onClick={handlePublish}
                disabled={mutationState.state === "saving" || !selectedDesignId}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {mutationState.state === "saving" ? (
                  <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5" />
                )}
                {mutationState.state === "saving" ? "Saving to Design..." : "Save to Design"}
              </button>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm leading-6 text-muted-foreground">
            This output is still only a task result. Save to Design appears once the backend marks
            the current simulation result ready for publication.
          </p>
        )}

        {mutationState.message ? (
          <div
            className={cx(
              "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
              resolveSurfaceInsetToneClass(
                mutationState.state === "error"
                  ? "error"
                  : mutationState.state === "success"
                    ? "success"
                    : "primary",
              ),
            )}
          >
            {mutationState.message}
          </div>
        ) : null}
      </div>

      <CreateDesignDialog
        open={isCreateDialogOpen}
        datasetId={targetDatasetId}
        value={newDesignName}
        state={createDesignState}
        onValueChange={setNewDesignName}
        onClose={() => {
          setIsCreateDialogOpen(false);
          setCreateDesignState({ state: "idle", message: null });
        }}
        onSubmit={handleCreateDesign}
      />
    </>
  );
}
