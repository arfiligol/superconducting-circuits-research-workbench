"use client";

import { useEffect, useState, useTransition } from "react";
import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useCharacterizationWorkflowData } from "@/features/characterization/hooks/use-characterization-workflow-data";
import {
  filterCharacterizationTasks,
  characterizationStatusTone,
  resolveCharacterizationSelectionRecovery,
  summarizeCharacterizationResults,
  summarizeCharacterizationTasks,
  type CharacterizationTaskScope,
  type CharacterizationTaskStatusFilter,
  type CharacterizationResultStatusFilter,
} from "@/features/characterization/lib/workflow";
import {
  ResearchTaskQueuePanel,
  ResearchWorkflowHero,
  ResearchWorkflowOverviewPanel,
} from "@/features/shared/components/research-workflow-panels";
import { AppSelectField } from "@/features/shared/components/app-select";
import {
  SurfacePanel,
  SurfaceStat,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";
import { TaskEventHistoryPanel } from "@/features/shared/components/task-event-history-panel";
import {
  TaskAttachmentPanel,
  TaskLifecyclePanel,
  TaskResultPanel,
} from "@/features/shared/components/task-workflow-panels";
import { ApiError } from "@/lib/api/client";
import type { TaskExecutionStatus } from "@/lib/api/tasks";
import { summarizeTaskEventHistory } from "@/lib/task-event-history";
import { summarizeResearchWorkflowSurface } from "@/lib/research-workflow-surface";
import {
  resolveTaskConnectionState,
  resolveTaskRecoveryNotice,
  summarizeTaskActionGates,
  summarizeTaskContextBinding,
  summarizeTaskLifecycle,
  summarizeTaskResultHandoff,
  summarizeTaskResultSurface,
} from "@/lib/task-surface";

const taskScopeOptions = [
  { label: "Active dataset", value: "dataset" },
  { label: "All characterization tasks", value: "all" },
] as const satisfies readonly Readonly<{
  label: string;
  value: CharacterizationTaskScope;
}>[];

const taskStatusOptions = [
  { label: "All statuses", value: "all" },
  { label: "Queued or running", value: "active" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
] as const satisfies readonly Readonly<{
  label: string;
  value: CharacterizationTaskStatusFilter;
}>[];

const statusOptions = [
  { label: "All persisted results", value: "all" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
  { label: "Blocked", value: "blocked" },
] as const satisfies readonly Readonly<{
  label: string;
  value: CharacterizationResultStatusFilter;
}>[];

function describeApiError(error: Error | undefined) {
  if (!error) {
    return null;
  }

  if (error instanceof ApiError) {
    const debugHint = error.debugRef ? ` Ref: ${error.debugRef}.` : "";
    return `${error.message}${debugHint}`;
  }

  return error.message;
}

function formatCoverageLabel(sourceCoverage: Record<string, number>) {
  const segments = Object.entries(sourceCoverage).map(([source, count]) => `${source} ${count}`);
  return segments.length > 0 ? segments.join(" · ") : "No indexed source coverage";
}

function formatTraceCompatibilityLabel(input: Readonly<{
  matchedTraceCount: number;
  selectedTraceCount: number;
  recommendedTraceModes: readonly string[];
  summary: string;
}>) {
  const modeLabel =
    input.recommendedTraceModes.length > 0
      ? input.recommendedTraceModes.join(", ")
      : "No preferred trace modes";
  const selectedLabel =
    input.selectedTraceCount > 0
      ? `${input.matchedTraceCount}/${input.selectedTraceCount} selected traces match`
      : `${input.matchedTraceCount} matched traces available`;

  return `${input.summary} · ${selectedLabel} · ${modeLabel}`;
}

function analysisAvailabilityTone(state: "recommended" | "available" | "unavailable") {
  if (state === "recommended") {
    return "primary" as const;
  }
  if (state === "unavailable") {
    return "warning" as const;
  }
  return "default" as const;
}

function ResultPayloadPreview({ payload }: Readonly<{ payload: Readonly<Record<string, unknown>> }>) {
  return (
    <pre className="overflow-x-auto rounded-2xl border border-border bg-surface px-4 py-4 text-xs leading-6 text-muted-foreground">
      {JSON.stringify(payload, null, 2)}
    </pre>
  );
}

function buildSourceSelectionValue(artifactId: string, sourceParameter: string) {
  return `${artifactId}::${sourceParameter}`;
}

function parseTaskIdParam(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function buildCharacterizationSearchHref(
  pathname: string,
  searchParamsValue: string,
  updates: Readonly<Record<string, string | null>>,
) {
  const params = new URLSearchParams(searchParamsValue);

  for (const [key, value] of Object.entries(updates)) {
    if (value === null) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  }

  const nextSearch = params.toString();
  return nextSearch ? `${pathname}?${nextSearch}` : pathname;
}

function taskStatusTone(status: TaskExecutionStatus) {
  if (status === "completed") {
    return "success" as const;
  }

  if (
    status === "running" ||
    status === "dispatching" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  ) {
    return "primary" as const;
  }

  if (status === "failed" || status === "cancelled" || status === "terminated") {
    return "warning" as const;
  }

  return "default" as const;
}

type CharacterizationTaskCardProps = Readonly<{
  isSelected: boolean;
  onAttach: (taskId: number) => void;
  task: ReturnType<typeof filterCharacterizationTasks>[number];
}>;

function CharacterizationTaskCard({
  isSelected,
  onAttach,
  task,
}: CharacterizationTaskCardProps) {
  return (
    <div
      className={cx(
        "rounded-[1rem] border px-4 py-4 shadow-[0_10px_30px_rgba(0,0,0,0.08)] transition",
        isSelected
          ? "border-primary/40 bg-card"
          : "border-border bg-card hover:border-primary/25 hover:bg-primary/5",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground">
            {task.summary || "Characterization task"}
          </h3>
          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Task #{task.taskId}
          </p>
        </div>
        <SurfaceTag tone={taskStatusTone(task.status)}>{task.status}</SurfaceTag>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <SurfaceTag tone="default">{task.executionMode}</SurfaceTag>
        {task.datasetId ? <SurfaceTag tone="default">{task.datasetId}</SurfaceTag> : null}
        <SurfaceTag tone="default">{task.ownerDisplayName}</SurfaceTag>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/80 pt-4">
        <p className="text-xs text-muted-foreground">
          {task.hasActionAuthority
            ? task.allowedActions.attach
              ? "Attach is allowed by backend task authority."
              : "Attach is blocked by backend task authority."
            : "Attach authority is not exposed by the backend yet."}
        </p>
        <button
          type="button"
          onClick={() => {
            onAttach(task.taskId);
          }}
          disabled={!task.allowedActions.attach}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Attach
        </button>
      </div>
    </div>
  );
}

export function CharacterizationWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const {
    activeDatasetState,
    designSearch,
    setDesignSearch,
    resultSearch,
    setResultSearch,
    statusFilter,
    setStatusFilter,
    designs,
    designsError,
    isDesignsLoading,
    requestedDesignId,
    selectedDesignId,
    setSelectedDesignId,
    analysisRegistry,
    analysisRegistryError,
    isAnalysisRegistryLoading,
    selectedAnalysisId,
    setSelectedAnalysisId,
    runHistory,
    runHistoryMeta,
    runHistoryError,
    isRunHistoryLoading,
    goToNextRunHistoryPage,
    goToPrevRunHistoryPage,
    focusRunHistoryResult,
    results,
    resultsError,
    isResultsLoading,
    requestedResultId,
    selectedResultId,
    setSelectedResultId,
    characterizationTasks,
    latestCharacterizationTask,
    resolvedTaskId,
    activeTask,
    activeTaskError,
    isTaskTransitioning,
    resultDetail,
    resultDetailError,
    isResultDetailLoading,
    taggingMutationState,
    submitTagging,
    refreshCharacterizationWorkflow,
  } = useCharacterizationWorkflowData(parseTaskIdParam(searchParams.get("taskId")));
  const [selectedSourceSelection, setSelectedSourceSelection] = useState("");
  const [selectedDesignatedMetric, setSelectedDesignatedMetric] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [taskScope, setTaskScope] = useState<CharacterizationTaskScope>("dataset");
  const [taskStatusFilter, setTaskStatusFilter] =
    useState<CharacterizationTaskStatusFilter>("all");
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);

  const selectionRecovery = resolveCharacterizationSelectionRecovery({
    activeDatasetName: activeDatasetState.activeDataset?.name ?? null,
    requestedDesignId,
    resolvedDesignId: selectedDesignId,
    requestedResultId,
    resolvedResultId: selectedResultId,
  });
  const resultSummary = summarizeCharacterizationResults(results);
  const taskSummary = summarizeCharacterizationTasks(characterizationTasks);
  const filteredTasks = filterCharacterizationTasks(characterizationTasks, {
    searchQuery: taskQuery,
    scope: taskScope,
    statusFilter: taskStatusFilter,
    activeDatasetId: activeDatasetState.activeDataset?.datasetId ?? null,
  });
  const taskConnectionState = resolveTaskConnectionState({
    requestedTaskId: parseTaskIdParam(searchParams.get("taskId")),
    resolvedTaskId,
    latestTaskId: latestCharacterizationTask?.taskId ?? null,
    activeTask,
  });
  const taskRecovery = resolveTaskRecoveryNotice(
    parseTaskIdParam(searchParams.get("taskId")),
    latestCharacterizationTask?.taskId ?? null,
    activeTaskError,
  );
  const taskLifecycleSummary = summarizeTaskLifecycle(activeTask);
  const taskResultSummary = summarizeTaskResultSurface(activeTask);
  const taskActionGates = summarizeTaskActionGates(activeTask);
  const taskContextBinding = summarizeTaskContextBinding({
    task: activeTask,
    activeDatasetId: activeDatasetState.activeDataset?.datasetId ?? null,
  });
  const taskResultHandoff = summarizeTaskResultHandoff(activeTask, taskResultSummary);
  const eventHistorySummary = summarizeTaskEventHistory(activeTask);
  const workflowSurfaceSummary = summarizeResearchWorkflowSurface({
    connectionState: taskConnectionState,
    lifecycleSummary: taskLifecycleSummary,
    eventHistorySummary,
    resultSummary: taskResultSummary,
  });
  const selectedAnalysisLabel =
    analysisRegistry.find((analysis) => analysis.analysisId === selectedAnalysisId)?.label ??
    selectedAnalysisId;
  const activeDatasetErrorMessage = describeApiError(activeDatasetState.activeDatasetError);
  const activeTaskErrorMessage = describeApiError(activeTaskError);
  const designsErrorMessage = describeApiError(designsError);
  const analysisRegistryErrorMessage = describeApiError(analysisRegistryError);
  const runHistoryErrorMessage = describeApiError(runHistoryError);
  const resultsErrorMessage = describeApiError(resultsError);
  const resultDetailErrorMessage = describeApiError(resultDetailError);
  const taggingStateTone =
    taggingMutationState.state === "success"
      ? "border-emerald-500/30 bg-emerald-500/10"
      : taggingMutationState.state === "error"
        ? "border-amber-500/30 bg-amber-500/10"
        : "border-border bg-surface";
  const eventHistoryNarrative = !activeTask
    ? "Attach a characterization task to inspect persisted dispatch, event, and result state alongside run history."
    : taskConnectionState.isStaleSnapshot && resolvedTaskId !== null
      ? `Showing persisted events from task #${activeTask.taskId} while task #${resolvedTaskId} reattaches so the page keeps execution context during refresh or route changes.`
      : taskConnectionState.hasNewerLatestTask && taskConnectionState.latestTaskId !== null
        ? `Task #${taskConnectionState.selectedTaskId} remains attached for comparison while newer characterization activity exists on task #${taskConnectionState.latestTaskId}.`
        : latestCharacterizationTask && resolvedTaskId === latestCharacterizationTask.taskId
          ? `Following the latest characterization task #${latestCharacterizationTask.taskId}. Persisted events and result publication should continue to update here.`
          : `Task #${activeTask.taskId} keeps a persisted event trail so refreshes do not erase characterization execution context.`;

  useEffect(() => {
    const firstSourceParameter = resultDetail?.identifySurface.sourceParameters[0];
    const firstDesignatedMetric = resultDetail?.identifySurface.designatedMetrics[0];
    setSelectedSourceSelection(
      firstSourceParameter
        ? buildSourceSelectionValue(
            firstSourceParameter.artifactId,
            firstSourceParameter.sourceParameter,
          )
        : "",
    );
    setSelectedDesignatedMetric(firstDesignatedMetric?.metricKey ?? "");
  }, [resultDetail?.resultId]);

  async function handleSubmitTagging() {
    if (!selectedSourceSelection || !selectedDesignatedMetric) {
      return;
    }

    const [artifactId, sourceParameter] = selectedSourceSelection.split("::");
    if (!artifactId || !sourceParameter) {
      return;
    }
    await submitTagging({
      artifactId,
      sourceParameter,
      designatedMetric: selectedDesignatedMetric,
    });
  }

  function replaceSearchState(updates: Readonly<Record<string, string | null>>) {
    startTransition(() => {
      router.replace(
        buildCharacterizationSearchHref(pathname, searchParams.toString(), updates),
        {
          scroll: false,
        },
      );
    });
  }

  async function handleRefreshWorkflow() {
    setIsRefreshingWorkflow(true);
    try {
      await refreshCharacterizationWorkflow();
    } finally {
      setIsRefreshingWorkflow(false);
    }
  }

  return (
    <div className="space-y-8">
      <ResearchWorkflowHero
        eyebrow="Research Workflow"
        title="Characterization"
        description="Attach persisted characterization tasks, recover them after refresh, and hand off terminal work into the persisted run-history and result surfaces without replacing those artifact views."
        contextTags={[
          {
            label: activeDatasetState.activeDataset?.name ?? "Dataset not attached",
            tone: activeDatasetState.activeDataset
              ? "success"
              : activeDatasetState.status === "error"
                ? "warning"
                : "default",
          },
          ...(selectedDesignId ? [{ label: selectedDesignId, tone: "primary" as const }] : []),
          ...(resolvedTaskId !== null
            ? [
                {
                  label: `Task #${resolvedTaskId}`,
                  tone: taskConnectionState.isAttached ? "success" : "warning",
                } as const,
              ]
            : []),
          {
            label: taskLifecycleSummary.statusLabel,
            tone: taskLifecycleSummary.tone,
          },
          ...(taskConnectionState.isFollowingLatest
            ? [{ label: "Following latest queue task", tone: "success" as const }]
            : []),
        ]}
        submitAuthorityLabel="Characterization keeps persisted result and run-history surfaces intact while task attachment and recovery semantics come from the shared task contract."
        stats={[
          { label: "Task Rows", value: String(taskSummary.total) },
          { label: "Active", value: String(taskSummary.activeCount), tone: "primary" },
          { label: "Persisted Results", value: String(resultSummary.total) },
        ]}
      />

      {selectionRecovery ? (
        <div
          className={cx(
            "rounded-[1rem] border px-4 py-4",
            selectionRecovery.tone === "warning"
              ? "border-amber-500/25 bg-amber-500/10"
              : "border-border bg-surface",
          )}
        >
          <p className="text-sm font-semibold text-foreground">{selectionRecovery.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{selectionRecovery.message}</p>
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <SurfaceStat label="Visible Designs" value={String(designs.length)} tone="primary" />
        <SurfaceStat label="Analysis Registry" value={String(analysisRegistry.length)} />
        <SurfaceStat label="Persisted Results" value={String(resultSummary.total)} />
        <SurfaceStat label="Run History Rows" value={String(runHistory.length)} />
      </div>

      {!activeDatasetState.activeDataset ? (
        <SurfacePanel
          title="Attach Active Dataset"
          description="Characterization surfaces always read from the shared shell active dataset before any design-scoped browse state is applied."
        >
          <p className="text-sm leading-6 text-muted-foreground">
            {activeDatasetErrorMessage ??
              "This page keeps only page-local design, analysis, and result browse state. Dataset authority continues to come from the shared shell context."}
          </p>
        </SurfacePanel>
      ) : (
        <div className="space-y-6">
          <ResearchTaskQueuePanel
            title="Characterization Task Queue"
            description="Attach persisted characterization tasks into the page body while keeping Run History as the artifact surface rather than a replacement queue."
            searchValue={taskQuery}
            onSearchChange={setTaskQuery}
            searchPlaceholder="Find by task id, summary, or dataset"
            scopeValue={taskScope}
            onScopeChange={(value) => {
              setTaskScope(value as CharacterizationTaskScope);
            }}
            scopeOptions={taskScopeOptions}
            statusValue={taskStatusFilter}
            onStatusChange={(value) => {
              setTaskStatusFilter(value as CharacterizationTaskStatusFilter);
            }}
            statusOptions={taskStatusOptions}
            summaryLabel={`Showing ${filteredTasks.length} of ${characterizationTasks.length} characterization tasks`}
            summaryTags={[
              ...(taskConnectionState.mode === "explicit" && resolvedTaskId !== null
                ? [{ label: `Locked to task #${resolvedTaskId}`, tone: "warning" as const }]
                : []),
              ...(taskConnectionState.isFollowingLatest && taskConnectionState.latestTaskId !== null
                ? [
                    {
                      label: `Following latest #${taskConnectionState.latestTaskId}`,
                      tone: "success" as const,
                    },
                  ]
                : []),
            ]}
            isRefreshing={isRefreshingWorkflow}
            onRefresh={() => {
              void handleRefreshWorkflow();
            }}
            isEmpty={filteredTasks.length === 0}
            emptyMessage="No characterization tasks match the current filters."
          >
            {filteredTasks.map((task) => (
              <CharacterizationTaskCard
                key={task.taskId}
                isSelected={task.taskId === resolvedTaskId}
                onAttach={(taskId) => {
                  replaceSearchState({ taskId: String(taskId) });
                }}
                task={task}
              />
            ))}
          </ResearchTaskQueuePanel>

          <ResearchWorkflowOverviewPanel
            summary={workflowSurfaceSummary}
            narrative={eventHistoryNarrative}
          />

          <TaskAttachmentPanel
            task={activeTask}
            connectionState={taskConnectionState}
            recoveryNotice={taskRecovery}
            taskErrorMessage={activeTaskErrorMessage}
            isRefreshing={isRefreshingWorkflow}
            isTransitioning={isTaskTransitioning}
            onRefresh={() => {
              void handleRefreshWorkflow();
            }}
            onAttachLatest={
              latestCharacterizationTask
                ? () => {
                    replaceSearchState({ taskId: String(latestCharacterizationTask.taskId) });
                  }
                : null
            }
            onFollowLatest={() => {
              replaceSearchState({ taskId: null });
            }}
          />

          <TaskLifecyclePanel task={activeTask} summary={taskLifecycleSummary} />

          <SurfacePanel
            title="Task Controls / Result Handoff"
            description="Attach follows backend `allowed_actions.attach`. Run History remains the persisted artifact surface, while control availability stays keyed to backend action authority."
          >
            <div className="grid gap-3 md:grid-cols-4">
              {[
                taskActionGates.attach,
                taskActionGates.cancel,
                taskActionGates.terminate,
                taskActionGates.retry,
              ].map((gate) => (
                <div
                  key={gate.action}
                  className={cx(
                    "rounded-[0.9rem] border px-4 py-4",
                    gate.enabled
                      ? "border-primary/25 bg-primary/10"
                      : "border-border bg-surface",
                  )}
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    {gate.action}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-foreground">
                    {gate.enabled ? "Allowed" : "Blocked"}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">{gate.reason}</p>
                </div>
              ))}
            </div>

            {!taskActionGates.hasActionAuthority ? (
              <div className="mt-4 rounded-[0.9rem] border border-amber-500/30 bg-amber-500/8 px-4 py-3 text-sm text-foreground">
                Backend `allowed_actions` are not present in the current task payload, so control
                affordances stay gated rather than guessed in the page body.
              </div>
            ) : null}

            {taskContextBinding ? (
              <div
                className={cx(
                  "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
                  taskContextBinding.tone === "warning"
                    ? "border-amber-500/30 bg-amber-500/8 text-foreground"
                    : "border-emerald-500/25 bg-emerald-500/10 text-foreground",
                )}
              >
                <p className="font-medium">{taskContextBinding.title}</p>
                <p className="mt-1">{taskContextBinding.message}</p>
              </div>
            ) : null}

            <div
              className={cx(
                "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
                taskResultHandoff.tone === "success"
                  ? "border-emerald-500/25 bg-emerald-500/10 text-foreground"
                  : taskResultHandoff.tone === "warning"
                    ? "border-amber-500/30 bg-amber-500/8 text-foreground"
                    : taskResultHandoff.tone === "primary"
                      ? "border-primary/30 bg-primary/8 text-foreground"
                      : "border-border bg-surface text-muted-foreground",
              )}
            >
              <p className="font-medium">{taskResultHandoff.title}</p>
              <p className="mt-1">{taskResultHandoff.message}</p>
              {taskResultHandoff.isReady ? (
                <p className="mt-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Continue into Run History and Persisted Result Detail below for artifact review
                  and identify tagging.
                </p>
              ) : null}
            </div>
          </SurfacePanel>

          <TaskEventHistoryPanel
            title="Task Event History"
            description="Inspect persisted event records so dispatch changes, progress movement, and task outcomes remain readable after refresh or recovery."
            task={activeTask}
            narrative={eventHistoryNarrative}
            emptyMessage="No persisted characterization task events are attached yet. Use the queue above to attach a task into this workflow surface."
          />

          <TaskResultPanel task={activeTask} summary={taskResultSummary} />

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1fr_1fr]">
            <SurfacePanel
              title="Design Scope"
              description="Pick one dataset-local design scope, then browse characterization registry, run history, and persisted result summaries within that scope."
            >
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <input
                  value={designSearch}
                  onChange={(event) => {
                    setDesignSearch(event.target.value);
                  }}
                  placeholder="Search designs"
                  className="w-full rounded-xl border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none transition focus:border-primary/40"
                />
              </label>

              <div className="mt-4 space-y-3">
                {designs.map((design) => (
                  <button
                    key={design.design_id}
                    type="button"
                    onClick={() => {
                      setSelectedDesignId(design.design_id);
                    }}
                    className={cx(
                      "w-full rounded-[1rem] border px-4 py-4 text-left transition",
                      selectedDesignId === design.design_id
                        ? "border-primary/35 bg-primary/10"
                        : "border-border bg-surface hover:border-primary/25 hover:bg-primary/5",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-foreground">
                          {design.name}
                        </h3>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {design.design_id}
                        </p>
                      </div>
                      <SurfaceTag tone="default">{design.compare_readiness}</SurfaceTag>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                      <span>{design.trace_count} traces</span>
                      <span>{formatCoverageLabel(design.source_coverage)}</span>
                    </div>
                  </button>
                ))}

                {!isDesignsLoading && designs.length === 0 ? (
                  <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    No visible design scope matches this dataset search.
                  </p>
                ) : null}
                {designsErrorMessage ? (
                  <p className="text-sm text-amber-700">{designsErrorMessage}</p>
                ) : null}
              </div>
            </SurfacePanel>

            <SurfacePanel
              title="Analysis Registry"
              description="Availability, compatibility, and required configuration summary only. This registry does not submit or attach analyses."
            >
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedAnalysisId(null);
                  }}
                  className={cx(
                    "rounded-full border px-3 py-1.5 text-xs font-medium transition",
                    selectedAnalysisId === null
                      ? "border-primary/35 bg-primary/10 text-foreground"
                      : "border-border bg-surface text-muted-foreground hover:border-primary/25 hover:text-foreground",
                  )}
                >
                  All analyses
                </button>
                {resultDetail ? (
                  <SurfaceTag tone="default">
                    Trace context {resultDetail.inputTraceIds.length}
                  </SurfaceTag>
                ) : (
                  <SurfaceTag tone="default">No selected trace context</SurfaceTag>
                )}
              </div>

              <div className="mt-4 space-y-3">
                {analysisRegistry.map((analysis) => (
                  <button
                    key={analysis.analysisId}
                    type="button"
                    onClick={() => {
                      setSelectedAnalysisId((current) =>
                        current === analysis.analysisId ? null : analysis.analysisId,
                      );
                    }}
                    className={cx(
                      "w-full rounded-[1rem] border px-4 py-4 text-left transition",
                      selectedAnalysisId === analysis.analysisId
                        ? "border-primary/35 bg-card"
                        : "border-border bg-surface hover:border-primary/25 hover:bg-primary/5",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-foreground">
                          {analysis.label}
                        </h3>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {analysis.analysisId}
                        </p>
                      </div>
                      <SurfaceTag tone={analysisAvailabilityTone(analysis.availabilityState)}>
                        {analysis.availabilityState}
                      </SurfaceTag>
                    </div>

                    <p className="mt-3 text-sm text-muted-foreground">
                      {formatTraceCompatibilityLabel(analysis.traceCompatibility)}
                    </p>

                    <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                      {analysis.requiredConfigFields.length > 0 ? (
                        analysis.requiredConfigFields.map((field) => (
                          <SurfaceTag key={field} tone="default">
                            {field}
                          </SurfaceTag>
                        ))
                      ) : (
                        <SurfaceTag tone="default">No required config fields</SurfaceTag>
                      )}
                    </div>
                  </button>
                ))}

                {!isAnalysisRegistryLoading && analysisRegistry.length === 0 ? (
                  <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    No characterization analysis registry rows are visible for this design scope.
                  </p>
                ) : null}
                {analysisRegistryErrorMessage ? (
                  <p className="text-sm text-amber-700">{analysisRegistryErrorMessage}</p>
                ) : null}
              </div>
            </SurfacePanel>

            <SurfacePanel
              title="Run History"
              description="Persisted characterization run history only. This surface does not replace the shared task queue."
            >
              <div className="flex flex-wrap items-center gap-2">
                {selectedAnalysisId ? (
                  <SurfaceTag tone="primary">{selectedAnalysisLabel}</SurfaceTag>
                ) : (
                  <SurfaceTag tone="default">All analyses</SurfaceTag>
                )}
                <SurfaceTag tone="default">
                  {selectedAnalysisId ? "Filtered" : "Unfiltered"}
                </SurfaceTag>
              </div>

              <div className="mt-4 space-y-3">
                {runHistory.map((run) => (
                  <button
                    key={run.runId}
                    type="button"
                    onClick={() => {
                      focusRunHistoryResult(run.resultId);
                    }}
                    disabled={!run.resultId}
                    className={cx(
                      "w-full rounded-[1rem] border px-4 py-4 text-left transition",
                      run.resultId && selectedResultId === run.resultId
                        ? "border-primary/35 bg-card"
                        : "border-border bg-surface",
                      run.resultId
                        ? "hover:border-primary/25 hover:bg-primary/5"
                        : "cursor-default opacity-80",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-foreground">
                          {run.label}
                        </h3>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {run.analysisId} · {run.runId}
                        </p>
                      </div>
                      <SurfaceTag tone={characterizationStatusTone(run.status)}>
                        {run.status}
                      </SurfaceTag>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                      <SurfaceTag tone="default">{run.scope}</SurfaceTag>
                      <SurfaceTag tone="default">{run.traceCount} traces</SurfaceTag>
                      <SurfaceTag tone="default">{run.updatedAt}</SurfaceTag>
                    </div>

                    <p className="mt-3 text-sm text-muted-foreground">{run.sourcesSummary}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{run.provenanceSummary}</p>
                    <p className="mt-3 text-xs font-medium text-foreground">
                      {run.resultId
                        ? `Open persisted detail ${run.resultId}`
                        : "No persisted result detail is attached to this history row."}
                    </p>
                  </button>
                ))}

                {!isRunHistoryLoading && runHistory.length === 0 ? (
                  <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    {selectedAnalysisId
                      ? "No persisted run history matches the selected analysis filter."
                      : "No persisted run history is visible for this design scope yet."}
                  </p>
                ) : null}
                {runHistoryErrorMessage ? (
                  <p className="text-sm text-amber-700">{runHistoryErrorMessage}</p>
                ) : null}
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-4 text-xs text-muted-foreground">
                <span>
                  {runHistory.length} row{runHistory.length === 1 ? "" : "s"} on this page
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={goToPrevRunHistoryPage}
                    disabled={!runHistoryMeta?.prevCursor}
                    className="rounded-full border border-border px-3 py-1.5 font-medium text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={goToNextRunHistoryPage}
                    disabled={!runHistoryMeta?.nextCursor}
                    className="rounded-full border border-border px-3 py-1.5 font-medium text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            </SurfacePanel>
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.2fr]">
            <SurfacePanel
              title="Result Summary List"
              description="Summary-first browse surface for persisted characterization results. Select one row to expand diagnostics, payload, and identify tagging detail."
            >
              <div className="grid gap-3 md:grid-cols-[1fr_auto]">
                <label className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <input
                    value={resultSearch}
                    onChange={(event) => {
                      setResultSearch(event.target.value);
                    }}
                    placeholder="Search results or analysis id"
                    className="w-full rounded-xl border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none transition focus:border-primary/40"
                  />
                </label>
                <AppSelectField
                  className="min-w-[220px]"
                  triggerClassName="min-h-10"
                  menuClassName="right-0 left-auto w-[280px]"
                  label="Status"
                  value={statusFilter}
                  onChange={(nextValue) => {
                    setStatusFilter(nextValue as CharacterizationResultStatusFilter);
                  }}
                  options={statusOptions}
                />
              </div>

              <div className="mt-4 space-y-3">
                {results.map((result) => (
                  <button
                    key={result.resultId}
                    type="button"
                    onClick={() => {
                      setSelectedResultId(result.resultId);
                    }}
                    className={cx(
                      "w-full rounded-[1rem] border px-4 py-4 text-left transition",
                      selectedResultId === result.resultId
                        ? "border-primary/35 bg-card"
                        : "border-border bg-surface hover:border-primary/25 hover:bg-primary/5",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-foreground">
                          {result.title}
                        </h3>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {result.analysisId}
                        </p>
                      </div>
                      <SurfaceTag tone={characterizationStatusTone(result.status)}>
                        {result.status}
                      </SurfaceTag>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                      <SurfaceTag tone="default">{result.traceCount} traces</SurfaceTag>
                      <SurfaceTag tone="default">{result.artifactCount} artifacts</SurfaceTag>
                      <SurfaceTag tone="default">{result.updatedAt}</SurfaceTag>
                    </div>

                    <p className="mt-3 text-sm text-muted-foreground">{result.freshnessSummary}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{result.provenanceSummary}</p>
                  </button>
                ))}

                {!isResultsLoading && results.length === 0 ? (
                  <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    No persisted characterization result matches this design scope and filter set.
                  </p>
                ) : null}
                {resultsErrorMessage ? (
                  <p className="text-sm text-amber-700">{resultsErrorMessage}</p>
                ) : null}
              </div>
            </SurfacePanel>

            <SurfacePanel
              title="Persisted Result Detail"
              description="Detail path only. Payload, diagnostics, artifact references, and identify tagging stay scoped to one persisted result."
            >
              {!selectedResultId ? (
                <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                  Select one persisted characterization result to inspect detail payload, diagnostics, and identify tagging affordances.
                </p>
              ) : null}

              {resultDetail ? (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">
                        {resultDetail.title}
                      </h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {resultDetail.analysisId} · {resultDetail.updatedAt}
                      </p>
                    </div>
                    <SurfaceTag tone={characterizationStatusTone(resultDetail.status)}>
                      {resultDetail.status}
                    </SurfaceTag>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-border bg-surface px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Freshness
                      </p>
                      <p className="mt-2 text-sm text-foreground">
                        {resultDetail.freshnessSummary}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border bg-surface px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Provenance
                      </p>
                      <p className="mt-2 text-sm text-foreground">
                        {resultDetail.provenanceSummary}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-surface px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Input Trace Scope
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {resultDetail.inputTraceIds.map((traceId) => (
                        <SurfaceTag key={traceId} tone="default">
                          {traceId}
                        </SurfaceTag>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-surface px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Diagnostics
                      </p>
                      <SurfaceTag
                        tone={
                          resultDetail.diagnostics.some((diagnostic) => diagnostic.blocking)
                            ? "warning"
                            : "default"
                        }
                      >
                        {resultDetail.diagnostics.length} entries
                      </SurfaceTag>
                    </div>

                    <div className="mt-3 space-y-3">
                      {resultDetail.diagnostics.map((diagnostic) => (
                        <div
                          key={`${diagnostic.code}-${diagnostic.message}`}
                          className={cx(
                            "rounded-xl border px-3 py-3",
                            diagnostic.blocking
                              ? "border-amber-500/25 bg-amber-500/10"
                              : "border-border bg-card",
                          )}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <SurfaceTag tone={diagnostic.blocking ? "warning" : "default"}>
                              {diagnostic.severity}
                            </SurfaceTag>
                            <span className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                              {diagnostic.code}
                            </span>
                          </div>
                          <p className="mt-2 text-sm text-foreground">{diagnostic.message}</p>
                        </div>
                      ))}
                      {resultDetail.diagnostics.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          No diagnostics were attached to this persisted result detail.
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-surface px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Artifact References
                      </p>
                      <SurfaceTag tone="default">
                        {resultDetail.artifactRefs.length} refs
                      </SurfaceTag>
                    </div>
                    <div className="mt-3 space-y-3">
                      {resultDetail.artifactRefs.map((artifact) => (
                        <div
                          key={artifact.artifactId}
                          className="rounded-xl border border-border bg-card px-3 py-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <SurfaceTag tone="default">{artifact.category}</SurfaceTag>
                            <SurfaceTag tone="default">{artifact.viewKind}</SurfaceTag>
                            <SurfaceTag tone="default">{artifact.payloadFormat}</SurfaceTag>
                          </div>
                          <p className="mt-2 text-sm font-medium text-foreground">
                            {artifact.title}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {artifact.payloadLocator ?? "No materialized locator available"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="mb-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Payload Preview
                    </p>
                    <ResultPayloadPreview payload={resultDetail.payload} />
                  </div>

                  <div className="rounded-2xl border border-border bg-surface px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          Identify & Tag
                        </p>
                        <p className="mt-2 text-sm text-foreground">
                          Choose one source parameter from this persisted result detail and map it to a dataset-level designated metric.
                        </p>
                      </div>
                      <SurfaceTag tone="primary">
                        {resultDetail.identifySurface.appliedTags.length} applied
                      </SurfaceTag>
                    </div>

                    {taggingMutationState.message ? (
                      <div
                        className={cx(
                          "mt-4 rounded-xl border px-4 py-3 text-sm text-foreground",
                          taggingStateTone,
                        )}
                      >
                        {taggingMutationState.message}
                      </div>
                    ) : null}

                    {resultDetail.identifySurface.sourceParameters.length > 0 &&
                    resultDetail.identifySurface.designatedMetrics.length > 0 ? (
                      <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
                        <AppSelectField
                          className="bg-card"
                          label="Source Parameter"
                          value={selectedSourceSelection}
                          onChange={setSelectedSourceSelection}
                          options={resultDetail.identifySurface.sourceParameters.map((option) => ({
                            value: buildSourceSelectionValue(
                              option.artifactId,
                              option.sourceParameter,
                            ),
                            label: `${option.artifactTitle} · ${option.label}`,
                            description: option.currentDesignatedMetric
                              ? `Tagged: ${option.currentDesignatedMetric}`
                              : "Not tagged yet",
                          }))}
                        />

                        <AppSelectField
                          className="bg-card"
                          label="Designated Metric"
                          value={selectedDesignatedMetric}
                          onChange={setSelectedDesignatedMetric}
                          options={resultDetail.identifySurface.designatedMetrics.map((option) => ({
                            value: option.metricKey,
                            label: option.label,
                            description: option.metricKey,
                          }))}
                        />

                        <button
                          type="button"
                          onClick={() => {
                            void handleSubmitTagging();
                          }}
                          disabled={
                            taggingMutationState.state === "submitting" ||
                            !selectedSourceSelection ||
                            !selectedDesignatedMetric
                          }
                          className="inline-flex min-h-11 items-center justify-center rounded-xl bg-primary px-4 py-3 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {taggingMutationState.state === "submitting"
                            ? "Tagging…"
                            : "Tag Parameter"}
                        </button>
                      </div>
                    ) : (
                      <p className="mt-4 text-sm text-muted-foreground">
                        No identify candidates are available for this persisted result detail yet.
                      </p>
                    )}

                    <div className="mt-4 space-y-3">
                      {resultDetail.identifySurface.appliedTags.map((tag) => (
                        <div
                          key={`${tag.artifactId}:${tag.sourceParameter}:${tag.designatedMetric}`}
                          className="rounded-xl border border-border bg-card px-4 py-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <SurfaceTag tone="success">{tag.designatedMetric}</SurfaceTag>
                            <SurfaceTag tone="default">{tag.sourceParameter}</SurfaceTag>
                            <SurfaceTag tone="default">{tag.artifactId}</SurfaceTag>
                          </div>
                          <p className="mt-2 text-sm text-foreground">
                            {tag.designatedMetricLabel}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            Tagged at {tag.taggedAt}
                          </p>
                        </div>
                      ))}
                      {resultDetail.identifySurface.appliedTags.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          No parameter tags were applied from this result detail yet.
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {isResultDetailLoading ? (
                <p className="mt-4 text-sm text-muted-foreground">
                  Loading persisted result detail…
                </p>
              ) : null}
              {resultDetailErrorMessage ? (
                <p className="mt-4 text-sm text-amber-700">{resultDetailErrorMessage}</p>
              ) : null}
            </SurfacePanel>
          </div>
        </div>
      )}
    </div>
  );
}
