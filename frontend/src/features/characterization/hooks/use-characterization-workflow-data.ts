"use client";

import { useEffect, useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import {
  applyCharacterizationTagging,
  characterizationResultDetailKey,
  getCharacterizationResult,
  listCharacterizationAnalysisRegistry,
  listCharacterizationResults,
  listCharacterizationRunHistory,
} from "@/features/characterization/lib/api";
import type {
  CharacterizationAnalysisRegistryRow,
  CharacterizationTaggingInput,
} from "@/features/characterization/lib/contracts";
import {
  resolveLatestCharacterizationTask,
  resolveSelectedCharacterizationDesignId,
  resolveSelectedCharacterizationResultId,
  type CharacterizationResultStatusFilter,
} from "@/features/characterization/lib/workflow";
import {
  datasetMetricsKey,
  listDesignBrowseRows,
  listTraceMetadata,
  type TraceMetadataRow,
} from "@/lib/api/datasets";
import { getTaskEnqueueFailureDetails } from "@/lib/api/client";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { useAppSession } from "@/lib/app-state/app-session";
import { useTaskQueue } from "@/lib/app-state/task-queue";
import {
  getTask,
  normalizeTaskSummary,
  submitTask,
  taskDetailKey,
  tasksListKey,
  type CharacterizationSetupDraft,
  type TaskDetail,
} from "@/lib/api/tasks";

type TaggingMutationState = Readonly<{
  state: "idle" | "submitting" | "success" | "error";
  message: string | null;
}>;

type TaskMutationState = Readonly<{
  state: "idle" | "submitting" | "success" | "error";
  message: string | null;
}>;

type CompletedRunSync = Readonly<{
  taskId: number;
  analysisId: string;
}>;

type UseCharacterizationWorkflowDataOptions = Readonly<{
  selectedTaskId: number | null;
  requestedDesignId: string | null;
  requestedResultId: string | null;
}>;

function defaultCharacterizationConfigValue(field: string) {
  switch (field) {
    case "fit_window":
      return "5.8, 7.2";
    case "comparison_window":
      return "5.8, 7.2";
    case "temperature_window":
      return "0.02, 0.08";
    case "residual_tolerance":
      return "0.02";
    case "prior_family":
      return "y_matrix";
    case "screening_mode":
      return "base";
    case "cross_check_mode":
      return "baseline";
    default:
      return "";
  }
}

function coerceCharacterizationConfigValue(field: string, rawValue: string) {
  const value = rawValue.trim();
  if (!value) {
    return null;
  }

  if (field.endsWith("_window")) {
    return value
      .split(",")
      .map((segment) => Number(segment.trim()))
      .filter((segment) => Number.isFinite(segment));
  }

  if (field.includes("tolerance")) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value;
  }

  if (value === "true") {
    return true;
  }

  if (value === "false") {
    return false;
  }

  const numericValue = Number(value);
  return Number.isFinite(numericValue) && `${numericValue}` === value ? numericValue : value;
}

function buildCharacterizationConfigDraft(
  analysis: CharacterizationAnalysisRegistryRow,
  values: Readonly<Record<string, string>>,
) {
  const draft: Record<string, unknown> = {};

  for (const field of analysis.requiredConfigFields) {
    draft[field] = coerceCharacterizationConfigValue(field, values[field] ?? "");
  }

  return draft;
}

function stringifyCharacterizationConfigValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.join(", ");
  }

  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  return value == null ? "" : String(value);
}

function buildCharacterizationSummary(input: Readonly<{
  analysisLabel: string;
  designId: string;
  designName: string | null;
  selectedTraceCount: number;
}>) {
  return `${input.analysisLabel} · ${input.designName ?? input.designId} · ${input.selectedTraceCount} traces`;
}

function shouldRefreshTask(task: TaskDetail | undefined) {
  return (
    task?.status === "queued" ||
    task?.status === "dispatching" ||
    task?.status === "running" ||
    task?.status === "cancellation_requested" ||
    task?.status === "cancelling" ||
    task?.status === "termination_requested" ||
    (task?.status === "completed" && task.resultHandoff?.availability === "pending")
  );
}

function defaultSelectedTraceIds(rows: readonly TraceMetadataRow[]) {
  const baseTraceIds = rows
    .filter((trace) => trace.trace_mode_group === "base")
    .map((trace) => trace.trace_id);

  if (baseTraceIds.length > 0) {
    return baseTraceIds;
  }

  return rows.map((trace) => trace.trace_id);
}

export function useCharacterizationWorkflowData({
  selectedTaskId,
  requestedDesignId,
  requestedResultId,
}: UseCharacterizationWorkflowDataOptions) {
  const { mutate } = useSWRConfig();
  const { session } = useAppSession();
  const activeDatasetState = useActiveDataset();
  const taskQueueState = useTaskQueue();
  const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null;
  const [resultSearch, setResultSearch] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<CharacterizationResultStatusFilter>("all");
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(
    requestedDesignId,
  );
  const [selectedResultId, setSelectedResultId] = useState<string | null>(
    requestedResultId,
  );
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);
  const [selectedTraceIds, setSelectedTraceIds] = useState<readonly string[]>([]);
  const [runHistoryCursor, setRunHistoryCursor] = useState<string | null>(null);
  const [analysisConfigValues, setAnalysisConfigValues] = useState<Record<string, string>>({});
  const [attachedTaskId, setAttachedTaskId] = useState<number | null>(selectedTaskId);
  const [completedRunSync, setCompletedRunSync] = useState<CompletedRunSync | null>(null);
  const [taggingMutationState, setTaggingMutationState] = useState<TaggingMutationState>({
    state: "idle",
    message: null,
  });
  const [taskMutationState, setTaskMutationState] = useState<TaskMutationState>({
    state: "idle",
    message: null,
  });

  const characterizationTasks = taskQueueState.tasks
    .map(normalizeTaskSummary)
    .filter((task) => task.kind === "characterization" && task.lane === "characterization");
  const latestCharacterizationTask = resolveLatestCharacterizationTask(characterizationTasks);
  const resolvedTaskId = attachedTaskId ?? latestCharacterizationTask?.taskId ?? null;
  const taskKey = resolvedTaskId ? taskDetailKey(resolvedTaskId) : null;
  const taskDetailQuery = useSWR(
    taskKey,
    () => (resolvedTaskId ? getTask(resolvedTaskId) : Promise.resolve(undefined)),
    {
      keepPreviousData: true,
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return shouldRefreshTask(currentData) ? 2_000 : 0;
      },
    },
  );
  const activeTask = taskDetailQuery.data;
  const hasAttachedTask =
    typeof resolvedTaskId === "number" && activeTask?.taskId === resolvedTaskId;

  useEffect(() => {
    if ((attachedTaskId === null && selectedTaskId === null) || !activeTask?.characterizationSetup) {
      return;
    }

    setSelectedDesignId(activeTask.characterizationSetup.design_id);
    setSelectedAnalysisId(activeTask.characterizationSetup.analysis_id);
    setSelectedTraceIds([...activeTask.characterizationSetup.selected_trace_ids]);
    setAnalysisConfigValues(
      Object.fromEntries(
        Object.entries(activeTask.characterizationSetup.analysis_config ?? {}).map(
          ([field, value]) => [field, stringifyCharacterizationConfigValue(value)],
        ),
      ),
    );
  }, [
    activeTask?.characterizationSetup,
    attachedTaskId,
    selectedTaskId,
  ]);

  const designsQuery = useSWR(
    activeDatasetId ? ["characterization-designs", activeDatasetId] : null,
    () =>
      activeDatasetId
        ? listDesignBrowseRows(activeDatasetId)
        : Promise.resolve(undefined),
  );

  const resolvedDesignId = resolveSelectedCharacterizationDesignId(
    selectedDesignId,
    designsQuery.data?.rows,
  );

  const tracesQuery = useSWR(
    activeDatasetId && resolvedDesignId
      ? ["characterization-traces", activeDatasetId, resolvedDesignId]
      : null,
    () =>
      activeDatasetId && resolvedDesignId
        ? listTraceMetadata(activeDatasetId, resolvedDesignId)
        : Promise.resolve(undefined),
  );

  const analysisRegistryQuery = useSWR(
    activeDatasetId && resolvedDesignId
      ? [
          "characterization-analysis-registry",
          activeDatasetId,
          resolvedDesignId,
          ...selectedTraceIds,
        ]
      : null,
    () =>
      activeDatasetId && resolvedDesignId
        ? listCharacterizationAnalysisRegistry(activeDatasetId, resolvedDesignId, {
            selectedTraceIds,
          })
        : Promise.resolve(undefined),
  );

  const selectedAnalysis =
    analysisRegistryQuery.data?.find((analysis) => analysis.analysisId === selectedAnalysisId) ??
    null;

  const runHistoryQuery = useSWR(
    activeDatasetId && resolvedDesignId
      ? [
          "characterization-run-history",
          activeDatasetId,
          resolvedDesignId,
          selectedAnalysisId,
          runHistoryCursor,
        ]
      : null,
    () =>
      activeDatasetId && resolvedDesignId
        ? listCharacterizationRunHistory(activeDatasetId, resolvedDesignId, {
            analysisId: selectedAnalysisId,
            cursor: runHistoryCursor,
          })
        : Promise.resolve(undefined),
  );

  const resultsQuery = useSWR(
    activeDatasetId && resolvedDesignId
      ? [
          "characterization-results",
          activeDatasetId,
          resolvedDesignId,
          resultSearch,
          statusFilter,
        ]
      : null,
    () =>
      activeDatasetId && resolvedDesignId
        ? listCharacterizationResults(activeDatasetId, resolvedDesignId, {
            search: resultSearch || null,
            status: statusFilter === "all" ? null : statusFilter,
          })
        : Promise.resolve(undefined),
  );

  const resolvedResultId = resolveSelectedCharacterizationResultId(
    selectedResultId,
    resultsQuery.data?.rows,
  );
  const detailKey =
    activeDatasetId && resolvedDesignId && resolvedResultId
      ? characterizationResultDetailKey(activeDatasetId, resolvedDesignId, resolvedResultId)
      : null;
  const detailQuery = useSWR(
    detailKey,
    () =>
      activeDatasetId && resolvedDesignId && resolvedResultId
        ? getCharacterizationResult(activeDatasetId, resolvedDesignId, resolvedResultId)
        : Promise.resolve(undefined),
  );

  useEffect(() => {
    setSelectedDesignId((current) =>
      resolveSelectedCharacterizationDesignId(current, designsQuery.data?.rows),
    );
  }, [designsQuery.data?.rows]);

  useEffect(() => {
    setSelectedResultId((current) =>
      resolveSelectedCharacterizationResultId(current, resultsQuery.data?.rows),
    );
  }, [resultsQuery.data?.rows]);

  useEffect(() => {
    setSelectedAnalysisId((current) => {
      const rows = analysisRegistryQuery.data ?? [];
      if (rows.length === 0) {
        return null;
      }

      if (current && rows.some((analysis) => analysis.analysisId === current)) {
        return current;
      }

      return (
        rows.find((analysis) => analysis.availabilityState === "recommended")?.analysisId ??
        rows.find((analysis) => analysis.availabilityState !== "unavailable")?.analysisId ??
        rows[0]?.analysisId ??
        null
      );
    });
  }, [analysisRegistryQuery.data]);

  useEffect(() => {
    const traces = tracesQuery.data?.rows ?? [];
    const availableTraceIds = new Set(traces.map((trace) => trace.trace_id));
    setSelectedTraceIds((current) => {
      const nextSelectedTraceIds = current.filter((traceId) => availableTraceIds.has(traceId));
      if (nextSelectedTraceIds.length > 0) {
        return nextSelectedTraceIds;
      }
      return defaultSelectedTraceIds(traces);
    });
  }, [tracesQuery.data?.rows]);

  useEffect(() => {
    if (!selectedAnalysis) {
      setAnalysisConfigValues({});
      return;
    }

    setAnalysisConfigValues((current) => {
      const nextValues: Record<string, string> = {};
      for (const field of selectedAnalysis.requiredConfigFields) {
        nextValues[field] = current[field] ?? defaultCharacterizationConfigValue(field);
      }
      return nextValues;
    });
  }, [selectedAnalysis?.analysisId, selectedAnalysis?.requiredConfigFields]);

  useEffect(() => {
    if (requestedDesignId !== selectedDesignId) {
      setSelectedDesignId(requestedDesignId);
    }
  }, [requestedDesignId, selectedDesignId]);

  useEffect(() => {
    if (requestedResultId !== selectedResultId) {
      setSelectedResultId(requestedResultId);
    }
  }, [requestedResultId, selectedResultId]);

  useEffect(() => {
    setAttachedTaskId(selectedTaskId);
  }, [selectedTaskId]);

  useEffect(() => {
    setResultSearch("");
    setStatusFilter("all");
    setSelectedDesignId(requestedDesignId);
    setSelectedResultId(requestedResultId);
    setSelectedAnalysisId(null);
    setSelectedTraceIds([]);
    setRunHistoryCursor(null);
    setAnalysisConfigValues({});
    setAttachedTaskId(selectedTaskId);
    setCompletedRunSync(null);
    setTaskMutationState({
      state: "idle",
      message: null,
    });
    setTaggingMutationState({
      state: "idle",
      message: null,
    });
  }, [activeDatasetId, requestedDesignId, requestedResultId, selectedTaskId]);

  useEffect(() => {
    setSelectedResultId(null);
    setSelectedAnalysisId(null);
    setSelectedTraceIds([]);
    setRunHistoryCursor(null);
    setAnalysisConfigValues({});
    setCompletedRunSync(null);
  }, [resolvedDesignId]);

  useEffect(() => {
    setRunHistoryCursor(null);
  }, [selectedAnalysisId]);

  useEffect(() => {
    setTaggingMutationState({
      state: "idle",
      message: null,
    });
  }, [resolvedResultId]);

  useEffect(() => {
    if (
      !completedRunSync ||
      activeTask?.taskId !== completedRunSync.taskId ||
      activeTask.status !== "completed"
    ) {
      return;
    }

    setResultSearch("");
    setStatusFilter("all");
    void Promise.all([runHistoryQuery.mutate(), resultsQuery.mutate()]);
  }, [activeTask, completedRunSync, resultsQuery, runHistoryQuery]);

  useEffect(() => {
    if (!completedRunSync || !resultsQuery.data?.rows.length) {
      return;
    }

    const matchingResult =
      resultsQuery.data.rows.find(
        (result) => result.analysisId === completedRunSync.analysisId,
      ) ?? resultsQuery.data.rows[0];

    if (!matchingResult) {
      return;
    }

    setSelectedResultId(matchingResult.resultId);
    setCompletedRunSync(null);
  }, [completedRunSync, resultsQuery.data?.rows]);

  async function submitTagging(input: CharacterizationTaggingInput) {
    if (!activeDatasetId || !resolvedDesignId || !resolvedResultId) {
      throw new Error("Select a saved result before applying identify tags.");
    }

    setTaggingMutationState({
      state: "submitting",
      message: null,
    });

    try {
      const result = await applyCharacterizationTagging(
        activeDatasetId,
        resolvedDesignId,
        resolvedResultId,
        input,
      );
      await Promise.all([
        mutate(detailKey),
        mutate(datasetMetricsKey(activeDatasetId)),
      ]);
      setTaggingMutationState({
        state: "success",
        message:
          result.taggingStatus === "already_applied"
            ? "This identify tag was already applied."
            : "Identify tag applied.",
      });
      return result;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to apply the identify tag.";
      setTaggingMutationState({
        state: "error",
        message,
      });
      throw error;
    }
  }

  async function submitCharacterizationTask() {
    if (!session?.canSubmitTasks) {
      const error = new Error("This session cannot start analyses.");
      setTaskMutationState({ state: "error", message: error.message });
      throw error;
    }

    if (!activeDatasetId) {
      const error = new Error("Attach an active dataset before running an analysis.");
      setTaskMutationState({ state: "error", message: error.message });
      throw error;
    }

    if (!resolvedDesignId) {
      const error = new Error("Choose a design before running an analysis.");
      setTaskMutationState({ state: "error", message: error.message });
      throw error;
    }

    if (!selectedAnalysis) {
      const error = new Error("Choose an analysis before running it.");
      setTaskMutationState({ state: "error", message: error.message });
      throw error;
    }

    if (selectedAnalysis.availabilityState === "unavailable") {
      const error = new Error("This analysis is not runnable for the current trace selection.");
      setTaskMutationState({ state: "error", message: error.message });
      throw error;
    }

    if (selectedTraceIds.length === 0) {
      const error = new Error("Select at least one trace before running an analysis.");
      setTaskMutationState({ state: "error", message: error.message });
      throw error;
    }

    for (const field of selectedAnalysis.requiredConfigFields) {
      if (!(analysisConfigValues[field] ?? "").trim()) {
        const error = new Error(`Provide ${field} before running this analysis.`);
        setTaskMutationState({ state: "error", message: error.message });
        throw error;
      }
    }

    const selectedDesign = designsQuery.data?.rows.find(
      (design) => design.design_id === resolvedDesignId,
    );
    const characterization_setup: CharacterizationSetupDraft = {
      design_id: resolvedDesignId,
      analysis_id: selectedAnalysis.analysisId,
      selected_trace_ids: selectedTraceIds,
      analysis_config: buildCharacterizationConfigDraft(selectedAnalysis, analysisConfigValues),
    };

    setTaskMutationState({ state: "submitting", message: null });

    try {
      const task = await submitTask({
        kind: "characterization",
        dataset_id: activeDatasetId,
        summary: buildCharacterizationSummary({
          analysisLabel: selectedAnalysis.label,
          designId: resolvedDesignId,
          designName: selectedDesign?.name ?? null,
          selectedTraceCount: selectedTraceIds.length,
        }),
        characterization_setup: {
          design_id: characterization_setup.design_id,
          analysis_id: characterization_setup.analysis_id,
          selected_trace_ids: characterization_setup.selected_trace_ids,
          analysis_config: characterization_setup.analysis_config,
        },
      });

      setAttachedTaskId(task.taskId);
      setCompletedRunSync({
        taskId: task.taskId,
        analysisId: selectedAnalysis.analysisId,
      });

      await Promise.all([
        mutate(tasksListKey),
        mutate(taskDetailKey(task.taskId), task, { revalidate: false }),
        taskQueueState.refreshTaskQueue(),
        runHistoryQuery.mutate(),
      ]);

      setTaskMutationState({
        state: "success",
        message: `Analysis started. Run #${task.taskId} is now in view.`,
      });

      return task;
    } catch (error) {
      const enqueueFailure = getTaskEnqueueFailureDetails(error);
      if (enqueueFailure?.taskId) {
        const persistedTask = await getTask(enqueueFailure.taskId).catch(() => null);
        if (persistedTask) {
          setAttachedTaskId(enqueueFailure.taskId);
        }
        await Promise.all([
          mutate(tasksListKey),
          taskQueueState.refreshTaskQueue(),
          runHistoryQuery.mutate(),
          persistedTask
            ? mutate(taskDetailKey(enqueueFailure.taskId), persistedTask, { revalidate: false })
            : Promise.resolve(undefined),
        ]);
      }

      const message = enqueueFailure?.taskId
        ? `Run #${enqueueFailure.taskId} was recorded but could not start yet${enqueueFailure.dispatch?.lastDispatchErrorCode ? ` (${enqueueFailure.dispatch.lastDispatchErrorCode})` : ""}. Review the latest analysis below before retrying.`
        : error instanceof Error
          ? error.message
          : "Could not start the analysis.";
      setTaskMutationState({ state: "error", message });
      throw error;
    }
  }

  function updateAnalysisConfigValue(field: string, value: string) {
    setAnalysisConfigValues((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function selectAllTraces() {
    const traceIds = tracesQuery.data?.rows.map((trace) => trace.trace_id) ?? [];
    setSelectedTraceIds(traceIds);
  }

  function selectBaseTraces() {
    const traceIds =
      tracesQuery.data?.rows
        .filter((trace) => trace.trace_mode_group === "base")
        .map((trace) => trace.trace_id) ?? [];
    setSelectedTraceIds(traceIds);
  }

  function clearTraceSelection() {
    setSelectedTraceIds([]);
  }

  function toggleTraceSelection(traceId: string) {
    setSelectedTraceIds((current) =>
      current.includes(traceId)
        ? current.filter((candidate) => candidate !== traceId)
        : [...current, traceId],
    );
  }

  function focusRunHistoryResult(resultId: string | null) {
    if (!resultId) {
      return;
    }

    setResultSearch("");
    setStatusFilter("all");
    setSelectedResultId(resultId);
  }

  function goToNextRunHistoryPage() {
    const nextCursor = runHistoryQuery.data?.meta.nextCursor ?? null;
    if (!nextCursor) {
      return;
    }
    setRunHistoryCursor(nextCursor);
  }

  function goToPrevRunHistoryPage() {
    const prevCursor = runHistoryQuery.data?.meta.prevCursor ?? null;
    if (prevCursor === runHistoryCursor) {
      return;
    }
    setRunHistoryCursor(prevCursor);
  }

  async function refreshCharacterizationWorkflow() {
    await Promise.all([
      activeDatasetState.refreshActiveDataset(),
      taskQueueState.refreshTaskQueue().then(() => undefined),
      taskDetailQuery.mutate(),
      designsQuery.mutate(),
      tracesQuery.mutate(),
      resultsQuery.mutate(),
      detailQuery.mutate(),
      analysisRegistryQuery.mutate(),
      runHistoryQuery.mutate(),
    ]);
  }

  return {
    session,
    activeDatasetState,
    taskQueueState,
    traces: tracesQuery.data?.rows ?? [],
    tracesMeta: tracesQuery.data?.meta,
    tracesError: tracesQuery.error as Error | undefined,
    isTracesLoading: tracesQuery.isLoading,
    selectedTraceIds,
    setSelectedTraceIds,
    toggleTraceSelection,
    selectAllTraces,
    selectBaseTraces,
    clearTraceSelection,
    resultSearch,
    setResultSearch,
    statusFilter,
    setStatusFilter,
    designs: designsQuery.data?.rows ?? [],
    designsMeta: designsQuery.data?.meta,
    designsError: designsQuery.error as Error | undefined,
    isDesignsLoading: designsQuery.isLoading,
    requestedDesignId,
    selectedDesignId: resolvedDesignId,
    setSelectedDesignId,
    analysisRegistry: analysisRegistryQuery.data ?? [],
    analysisRegistryError: analysisRegistryQuery.error as Error | undefined,
    isAnalysisRegistryLoading: analysisRegistryQuery.isLoading,
    selectedAnalysis,
    selectedAnalysisId,
    setSelectedAnalysisId,
    analysisConfigValues,
    updateAnalysisConfigValue,
    runHistory: runHistoryQuery.data?.rows ?? [],
    runHistoryMeta: runHistoryQuery.data?.meta,
    runHistoryError: runHistoryQuery.error as Error | undefined,
    isRunHistoryLoading: runHistoryQuery.isLoading,
    goToNextRunHistoryPage,
    goToPrevRunHistoryPage,
    focusRunHistoryResult,
    results: resultsQuery.data?.rows ?? [],
    resultsMeta: resultsQuery.data?.meta,
    resultsError: resultsQuery.error as Error | undefined,
    isResultsLoading: resultsQuery.isLoading,
    requestedResultId,
    selectedResultId: resolvedResultId,
    setSelectedResultId,
    characterizationTasks,
    latestCharacterizationTask,
    resolvedTaskId,
    activeTask,
    activeTaskError: taskDetailQuery.error as Error | undefined,
    isTaskTransitioning:
      typeof resolvedTaskId === "number" && (!hasAttachedTask || taskDetailQuery.isLoading),
    resultDetail: detailQuery.data,
    resultDetailError: detailQuery.error as Error | undefined,
    isResultDetailLoading: detailQuery.isLoading,
    taskMutationState,
    submitCharacterizationTask,
    taggingMutationState,
    submitTagging,
    refreshCharacterizationWorkflow,
  };
}
