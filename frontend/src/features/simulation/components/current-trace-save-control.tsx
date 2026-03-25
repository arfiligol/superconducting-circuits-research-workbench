"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Save } from "lucide-react";
import useSWR from "swr";
import { useSWRConfig } from "swr";

import { CurrentTraceSaveDialog } from "@/features/simulation/components/current-trace-save-dialog";
import { buildRawDataBrowseHref } from "@/features/data-browser/lib/browse-state";
import { type AppSelectOption } from "@/features/shared/components/app-select";
import { SurfaceTag } from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";
import {
  createDatasetDesign,
  listDesignBrowseRows,
  type DesignBrowseRow,
} from "@/lib/api/datasets";
import {
  publishSimulationResultTraces,
  taskDetailKey,
  type PublishedSimulationTrace,
  type TaskDetail,
} from "@/lib/api/tasks";

type CurrentTraceSaveControlProps = Readonly<{
  task: TaskDetail;
  activeDatasetId: string | null;
  traceKeys: readonly string[];
  metric: string;
  traceLabel: string | null;
  traceCount: number;
  defaultParameter: string | null;
}>;

export type MutationState = Readonly<{
  state: "idle" | "saving" | "error";
  message: string | null;
}>;

export type CreateDesignState = Readonly<{
  state: "idle" | "creating" | "error";
  message: string | null;
}>;

type SavedTraceState = Readonly<{
  designId: string;
  designName: string;
  traces: readonly PublishedSimulationTrace[];
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

  return "Unable to save the visible traces right now.";
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

export function CurrentTraceSaveControl({
  task,
  activeDatasetId,
  traceKeys,
  metric,
  traceLabel,
  traceCount,
  defaultParameter,
}: CurrentTraceSaveControlProps) {
  const { mutate } = useSWRConfig();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedDesignId, setSelectedDesignId] = useState("");
  const [showCreateDesign, setShowCreateDesign] = useState(false);
  const [newDesignName, setNewDesignName] = useState("");
  const [parameterName, setParameterName] = useState("");
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

    if (savedTraceState.traces.length === 1) {
      return buildRawDataBrowseHref({
        designId: savedTraceState.designId,
        traceId: savedTraceState.traces[0]?.traceId ?? null,
        designQuery: savedTraceState.designName,
      });
    }

    return buildRawDataBrowseHref({
      designId: savedTraceState.designId,
      designQuery: savedTraceState.designName,
    });
  }, [savedTraceState]);
  const saveDisabled = !activeDatasetId || traceKeys.length === 0;

  useEffect(() => {
    if (!isDialogOpen) {
      return;
    }

    setParameterName(defaultParameter ?? "");
  }, [defaultParameter, isDialogOpen]);

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
    if (traceKeys.length === 0 || !selectedDesignId) {
      setMutationState({
        state: "error",
        message: "Choose a design before saving the visible traces.",
      });
      return;
    }

    const normalizedParameterName = parameterName.trim();
    if (!normalizedParameterName) {
      setMutationState({
        state: "error",
        message:
          traceCount > 1
            ? "Enter the saved parameter prefix before saving these traces."
            : "Enter the saved parameter name before saving this trace.",
      });
      return;
    }

    setMutationState({ state: "saving", message: null });

    try {
      const result = await publishSimulationResultTraces(task.taskId, {
        traceKeys,
        metric,
        designId: selectedDesignId,
        parameterName: normalizedParameterName,
      });
      await mutate(taskDetailKey(task.taskId), result.task, { revalidate: false });
      setSavedTraceState({
        designId: result.design.designId,
        designName: result.design.name,
        traces: result.traces,
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
            setParameterName(defaultParameter ?? "");
            setIsDialogOpen(true);
          }}
          disabled={saveDisabled}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Save className="h-4 w-4" />
          Save Traces
        </button>

        {savedTraceState ? (
          <>
            <SurfaceTag tone="success">
              {savedTraceState.traces.length > 1
                ? `Saved ${savedTraceState.traces.length} traces to ${savedTraceState.designName}`
                : `Saved to ${savedTraceState.designName}`}
            </SurfaceTag>
            {rawDataHref ? (
              <Link
                href={rawDataHref}
                className="inline-flex items-center gap-2 text-sm font-medium text-primary transition hover:opacity-80"
              >
                {savedTraceState.traces.length > 1
                  ? "Open Saved Traces in Raw Data"
                  : "Open Saved Trace in Raw Data"}
                <ExternalLink className="h-4 w-4" />
              </Link>
            ) : null}
          </>
        ) : null}
      </div>

      <CurrentTraceSaveDialog
        open={isDialogOpen}
        traceLabel={traceLabel}
        traceCount={traceCount}
        parameterValue={parameterName}
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
        onParameterChange={setParameterName}
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
