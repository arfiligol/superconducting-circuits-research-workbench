"use client";

import { useEffect, useState, useTransition } from "react";
import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useCharacterizationWorkflowData } from "@/features/characterization/hooks/use-characterization-workflow-data";
import {
  characterizationStatusTone,
  resolveCharacterizationSelectionRecovery,
  summarizeCharacterizationResults,
  type CharacterizationResultStatusFilter,
} from "@/features/characterization/lib/workflow";
import { AppSelectField } from "@/features/shared/components/app-select";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";
import type { TaskExecutionStatus } from "@/lib/api/tasks";
import { requestOpenGlobalContext } from "@/components/layout/workspace-shell-contract";
import {
  resolveTaskRecoveryNotice,
  summarizeTaskContextBinding,
  summarizeTaskLifecycle,
  summarizeTaskResultHandoff,
  summarizeTaskResultSurface,
} from "@/lib/task-surface";

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

function WorkbenchSummaryItem({
  label,
  value,
  detail,
}: Readonly<{
  label: string;
  value: string;
  detail: string;
}>) {
  return (
    <div
      className="rounded-[0.95rem] border border-border bg-background px-4 py-4 shadow-[0_6px_18px_rgba(15,23,42,0.05)]"
    >
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold text-foreground">{value}</p>
      <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
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
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);

  const selectionRecovery = resolveCharacterizationSelectionRecovery({
    activeDatasetName: activeDatasetState.activeDataset?.name ?? null,
    requestedDesignId,
    resolvedDesignId: selectedDesignId,
    requestedResultId,
    resolvedResultId: selectedResultId,
  });
  const resultSummary = summarizeCharacterizationResults(results);
  const taskRecovery = resolveTaskRecoveryNotice(
    parseTaskIdParam(searchParams.get("taskId")),
    latestCharacterizationTask?.taskId ?? null,
    activeTaskError,
  );
  const taskLifecycleSummary = summarizeTaskLifecycle(activeTask);
  const taskResultSummary = summarizeTaskResultSurface(activeTask);
  const taskContextBinding = summarizeTaskContextBinding({
    task: activeTask,
    activeDatasetId: activeDatasetState.activeDataset?.datasetId ?? null,
  });
  const taskResultHandoff = summarizeTaskResultHandoff(activeTask, taskResultSummary);
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
      <SurfaceHeader
        eyebrow="Research Workflow"
        title="Characterization"
        description="Stay inside the characterization workbench: design scope, analysis registry, run history, and persisted results. Queue browse and worker management stay in Global Context."
        actions={
          <button
            type="button"
            onClick={() => {
              void handleRefreshWorkflow();
            }}
            disabled={isRefreshingWorkflow}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Refresh Workbench
          </button>
        }
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
          <SurfacePanel
            title="Characterization Workbench Summary"
            description="One summary surface for the current workbench context. Queue browsing and task management stay in Global Context."
          >
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_repeat(3,minmax(0,0.45fr))]">
              <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4 shadow-[0_8px_22px_rgba(15,23,42,0.05)]">
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  {selectedDesignId ? <SurfaceTag tone="primary">{selectedDesignId}</SurfaceTag> : null}
                  {selectedAnalysisId ? (
                    <SurfaceTag tone="default">{selectedAnalysisLabel}</SurfaceTag>
                  ) : (
                    <SurfaceTag tone="default">All analyses</SurfaceTag>
                  )}
                  <SurfaceTag tone={taskLifecycleSummary.tone}>{taskLifecycleSummary.statusLabel}</SurfaceTag>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  Characterization stays focused on design-scoped registry, run history, and persisted result detail. Task awareness is kept compact so the workbench remains the primary surface.
                </p>
              </div>
              <WorkbenchSummaryItem
                label="Visible Designs"
                value={String(designs.length)}
                detail="Dataset-local design scopes available for characterization."
              />
              <WorkbenchSummaryItem
                label="Persisted Results"
                value={String(resultSummary.total)}
                detail="Persisted characterization results in the current scope."
              />
              <WorkbenchSummaryItem
                label="Run History"
                value={String(runHistory.length)}
                detail="Visible run-history rows on the current page."
              />
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Current Run"
            description="Compact task awareness only. Attach, queue browse, and deeper recovery stay in Global Context."
            actions={
              <button
                type="button"
                onClick={() => {
                  requestOpenGlobalContext("tasks");
                }}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                Open in Global Context
              </button>
            }
          >
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(240px,0.8fr)]">
              <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Current Characterization Run
                    </p>
                    <p className="mt-2 text-sm font-semibold text-foreground">
                      {activeTask
                        ? `Task #${activeTask.taskId}`
                        : latestCharacterizationTask
                          ? `Latest task #${latestCharacterizationTask.taskId}`
                          : "No attached characterization task"}
                    </p>
                  </div>
                  <SurfaceTag tone={taskLifecycleSummary.tone}>{taskLifecycleSummary.statusLabel}</SurfaceTag>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  {activeTask?.summary ??
                    latestCharacterizationTask?.summary ??
                    "Persisted run awareness appears here after you attach a characterization task from Global Context."}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {activeTask ? (
                    <button
                      type="button"
                      onClick={() => {
                        replaceSearchState({ taskId: String(activeTask.taskId) });
                      }}
                      className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                    >
                      View Task
                    </button>
                  ) : null}
                  {latestCharacterizationTask &&
                  latestCharacterizationTask.taskId !== activeTask?.taskId ? (
                    <button
                      type="button"
                      onClick={() => {
                        replaceSearchState({ taskId: String(latestCharacterizationTask.taskId) });
                      }}
                      className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                    >
                      Resume Latest
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="space-y-3">
                <div
                  className={cx(
                    "rounded-[0.95rem] border px-4 py-4 text-sm",
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
                  <p className="mt-2">{taskResultHandoff.message}</p>
                </div>

                {taskRecovery ? (
                  <div className="rounded-[0.95rem] border border-amber-500/30 bg-amber-500/8 px-4 py-4 text-sm text-foreground">
                    <p className="font-medium">{taskRecovery.title}</p>
                    <p className="mt-2">{taskRecovery.message}</p>
                  </div>
                ) : null}

                {!taskRecovery && taskContextBinding ? (
                  <div
                    className={cx(
                      "rounded-[0.95rem] border px-4 py-4 text-sm",
                      taskContextBinding.tone === "warning"
                        ? "border-amber-500/30 bg-amber-500/8 text-foreground"
                        : "border-emerald-500/25 bg-emerald-500/10 text-foreground",
                    )}
                  >
                    <p className="font-medium">{taskContextBinding.title}</p>
                    <p className="mt-2">{taskContextBinding.message}</p>
                  </div>
                ) : null}

                {activeTaskErrorMessage ? (
                  <div className="rounded-[0.95rem] border border-amber-500/30 bg-amber-500/8 px-4 py-4 text-sm text-foreground">
                    <p className="font-medium">Task detail unavailable</p>
                    <p className="mt-2">{activeTaskErrorMessage}</p>
                  </div>
                ) : null}
              </div>
            </div>
          </SurfacePanel>

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
