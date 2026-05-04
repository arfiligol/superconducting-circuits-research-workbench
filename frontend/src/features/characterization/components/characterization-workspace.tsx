"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, LoaderCircle, Play, Search } from "lucide-react";

import { CharacterizationResultExplorer } from "@/features/characterization/components/characterization-result-explorer";
import { useCharacterizationRouteState } from "@/features/characterization/hooks/use-characterization-route-state";
import { useCharacterizationResultExplorer } from "@/features/characterization/hooks/use-characterization-result-explorer";
import { useCharacterizationWorkflowData } from "@/features/characterization/hooks/use-characterization-workflow-data";
import type {
  CharacterizationAnalysisRegistryRow,
  CharacterizationCollectionReadinessState,
  CharacterizationDataCollectionReview,
  CharacterizationPrerequisiteState,
} from "@/features/characterization/lib/contracts";
import {
  buildCharacterizationCollectionOptions,
  buildCharacterizationSweepAxisOptions,
  filterCharacterizationTraceRows,
} from "@/features/characterization/lib/trace-selection";
import {
  characterizationStatusTone,
  resolveCharacterizationSelectionRecovery,
  type CharacterizationResultStatusFilter,
} from "@/features/characterization/lib/workflow";
import {
  AppInlineSelect,
  AppSelectField,
} from "@/features/shared/components/app-select";
import {
  SurfaceHeader,
  SurfaceActionButton,
  type SurfaceInsetTone,
  SurfacePanel,
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";

const statusOptions = [
  { label: "All results", value: "all" },
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

function buildSectionError(summary: string, error: Error | undefined) {
  const detail = describeApiError(error);
  if (!detail) {
    return null;
  }

  return { summary, detail };
}

function formatCoverageLabel(sourceCoverage: Record<string, number>) {
  const segments = Object.entries(sourceCoverage).map(([source, count]) => `${source} ${count}`);
  return segments.length > 0 ? segments.join(" · ") : "No indexed source coverage";
}

function formatRepresentationLabel(value: string) {
  switch (value) {
    case "db":
      return "dB";
    case "mag":
      return "Magnitude";
    case "phase":
      return "Phase";
    case "real":
      return "Real";
    case "imag":
      return "Imag";
    default:
      return value.replaceAll("_", " ");
  }
}

function formatSourceLabel(value: string) {
  switch (value) {
    case "measurement":
      return "Measurement";
    case "layout_simulation":
      return "Layout";
    case "circuit_simulation":
      return "Circuit";
    default:
      return value.replaceAll("_", " ");
  }
}

function formatModeLabel(value: string) {
  switch (value) {
    case "base":
      return "Base";
    case "sideband":
      return "Sideband";
    default:
      return value.replaceAll("_", " ");
  }
}

function formatConfigLabel(field: string) {
  switch (field) {
    case "fit_window":
      return "Fit Window";
    case "comparison_window":
      return "Compare Window";
    case "temperature_window":
      return "Temp Window";
    case "residual_tolerance":
      return "Residual Tol.";
    case "prior_family":
      return "Prior Family";
    case "screening_mode":
      return "Screening Mode";
    case "cross_check_mode":
      return "Cross-check";
    default:
      return field.replaceAll("_", " ");
  }
}

function configPlaceholder(field: string) {
  switch (field) {
    case "fit_window":
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
      return "Enter value";
  }
}

function formatPipelineState(value: CharacterizationPrerequisiteState) {
  return value.replaceAll("_", " ");
}

function pipelineStateTone(value: CharacterizationPrerequisiteState) {
  switch (value) {
    case "ready":
      return "success" as const;
    case "requires_upstream_result":
      return "primary" as const;
    case "blocked":
    default:
      return "warning" as const;
  }
}

function availabilityTone(state: CharacterizationAnalysisRegistryRow["availabilityState"]) {
  if (state === "recommended") {
    return "primary" as const;
  }
  if (state === "unavailable") {
    return "warning" as const;
  }
  return "default" as const;
}

function collectionReadinessTone(state: CharacterizationCollectionReadinessState) {
  switch (state) {
    case "ready":
      return "success" as const;
    case "inspect_only":
      return "primary" as const;
    case "blocked":
    default:
      return "warning" as const;
  }
}

function taskStatusTone(status: string) {
  if (status === "completed") {
    return "success" as const;
  }
  if (status === "failed" || status === "terminated" || status === "cancelled") {
    return "warning" as const;
  }
  if (status === "queued" || status === "dispatching" || status === "running") {
    return "primary" as const;
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

function SectionNotice({
  title,
  detail,
  tone = "warning",
}: Readonly<{
  title: string;
  detail: string;
  tone?: SurfaceInsetTone;
}>) {
  return (
    <div
      className={cx(
        "rounded-[0.95rem] border px-4 py-3",
        resolveSurfaceInsetToneClass(tone),
      )}
    >
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}

function pipelineExplanation(analysis: CharacterizationAnalysisRegistryRow | null, selectedTraceCount: number) {
  if (!analysis) {
    return {
      tone: "default" as const,
      title: "Pipeline Guidance",
      detail:
        selectedTraceCount > 0
          ? "Select one pipeline step to review readiness, prerequisites, and next-step unlocks."
          : "Select traces first, then review how the pipeline reads this collection.",
    };
  }

  if (analysis.prerequisiteState === "ready") {
    return {
      tone: "success" as const,
      title: "Runnable Now",
      detail: analysis.traceCompatibility.summary,
    };
  }

  if (analysis.prerequisiteState === "requires_upstream_result") {
    return {
      tone: "primary" as const,
      title: "Needs Upstream Result",
      detail:
        analysis.upstreamResultRequirement?.summary ||
        "This analysis depends on an upstream persisted result before it can run.",
    };
  }

  return {
    tone: "warning" as const,
    title: "Blocked For This Collection",
    detail: analysis.traceCompatibility.summary,
  };
}

function latestRunStatusDetail(activeTask: ReturnType<typeof useCharacterizationWorkflowData>["activeTask"]) {
  if (!activeTask) {
    return null;
  }

  if (activeTask.resultHandoff?.availability === "ready") {
    return {
      title: "Result ready",
      message: `Updated ${activeTask.progress.updatedAt}. The latest result is ready in Result Preview.`,
    };
  }

  if (
    activeTask.status === "failed" ||
    activeTask.status === "terminated" ||
    activeTask.status === "cancelled"
  ) {
    return {
      title: "Run ended",
      message: `Updated ${activeTask.progress.updatedAt}. This run ended before a saved result was available.`,
    };
  }

  if (activeTask.resultHandoff?.availability === "pending" || activeTask.status === "completed") {
    return {
      title: "Saving result",
      message: `Updated ${activeTask.progress.updatedAt}. The analysis finished and the persisted result is still being prepared.`,
    };
  }

  return {
    title: "In progress",
    message: `Updated ${activeTask.progress.updatedAt}. This analysis is still running.`,
  };
}

function reviewSummary(review: CharacterizationDataCollectionReview | null, fallbackCount: number) {
  if (!review) {
    return fallbackCount === 0 ? "No traces selected" : `${fallbackCount} traces selected`;
  }

  return review.selectionSummary;
}

export function CharacterizationWorkspace() {
  const { routeIntent, syncRouteState } = useCharacterizationRouteState();
  const {
    activeDatasetState,
    traces,
    tracesError,
    isTracesLoading,
    selectedTraceIds,
    setSelectedTraceIds,
    toggleTraceSelection,
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
    inputCollectionPayload,
    dataCollectionReview,
    analysisRegistryError,
    isAnalysisRegistryLoading,
    selectedAnalysis,
    selectedAnalysisId,
    setSelectedAnalysisId,
    analysisConfigValues,
    updateAnalysisConfigValue,
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
    resultSelectionSource,
    isExplicitRouteResultPending,
    resolvedTaskId,
    activeTask,
    activeTaskError,
    isTaskTransitioning,
    resultDetail,
    resultDetailError,
    isResultDetailLoading,
    taskMutationState,
    submitCharacterizationTask,
    taggingMutationState,
    submitTagging,
    refreshCharacterizationWorkflow,
  } = useCharacterizationWorkflowData({
    selectedTaskId: routeIntent.selectedTaskId,
    requestedDesignId: routeIntent.requestedDesignId,
    requestedResultId: routeIntent.requestedResultId,
  });
  const [selectedSourceSelection, setSelectedSourceSelection] = useState("");
  const [selectedDesignatedMetric, setSelectedDesignatedMetric] = useState("");
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);
  const [sweepAxisFilter, setSweepAxisFilter] = useState("");
  const [collectionFilter, setCollectionFilter] = useState("");

  const selectedDesign = designs.find((design) => design.design_id === selectedDesignId) ?? null;
  const resultExplorer = useCharacterizationResultExplorer({
    datasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    designId: selectedDesignId,
    resultDetail: resultDetail ?? null,
  });
  const activeDatasetErrorNotice = buildSectionError(
    "Could not load the active dataset.",
    activeDatasetState.activeDatasetError,
  );
  const designsErrorNotice = buildSectionError("Could not load designs.", designsError);
  const tracesErrorNotice = buildSectionError("Could not load traces.", tracesError);
  const analysisRegistryErrorNotice = buildSectionError(
    "Could not load characterization pipeline state.",
    analysisRegistryError,
  );
  const runHistoryErrorNotice = buildSectionError("Could not load run history.", runHistoryError);
  const resultsErrorNotice = buildSectionError("Could not load saved results.", resultsError);
  const activeTaskErrorNotice = buildSectionError(
    "Could not load the active analysis run.",
    activeTaskError,
  );
  const resultDetailErrorNotice = buildSectionError(
    "Could not load result details.",
    resultDetailError,
  );
  const selectionRecovery = resolveCharacterizationSelectionRecovery({
    activeDatasetName: activeDatasetState.activeDataset?.name ?? null,
    requestedDesignId,
    resolvedDesignId: selectedDesignId,
    requestedResultId,
    resolvedResultId: selectedResultId,
  });
  const sweepAxisOptions = useMemo(() => buildCharacterizationSweepAxisOptions(traces), [traces]);
  const collectionOptions = useMemo(() => buildCharacterizationCollectionOptions(traces), [traces]);
  const visibleTraces = useMemo(
    () =>
      filterCharacterizationTraceRows(traces, {
        sweepAxis: sweepAxisFilter || null,
        collection: collectionFilter || null,
      }),
    [collectionFilter, sweepAxisFilter, traces],
  );
  const visibleSelectedTraceCount = visibleTraces.filter((trace) =>
    selectedTraceIds.includes(trace.trace_id),
  ).length;
  const traceSelectionSummary =
    selectedTraceIds.length === 0
      ? "No traces selected"
      : `${selectedTraceIds.length} traces selected`;
  const taskMutationTone =
    taskMutationState.state === "success"
      ? "success"
      : taskMutationState.state === "error"
        ? "error"
        : "primary";
  const taggingStateTone =
    taggingMutationState.state === "success"
      ? "border-emerald-500/30 bg-emerald-500/10"
      : taggingMutationState.state === "error"
        ? "border-amber-500/30 bg-amber-500/10"
        : "border-border bg-surface";
  const showResultControls =
    results.length > 0 || resultSearch.trim() !== "" || statusFilter !== "all";
  const selectedPipelineExplanation = pipelineExplanation(
    selectedAnalysis,
    selectedTraceIds.length,
  );
  const activeRunDetail = latestRunStatusDetail(activeTask);
  const downstreamAnalysisIds =
    resultDetail?.downstreamUnlockAnalysisIds.length
      ? resultDetail.downstreamUnlockAnalysisIds
      : selectedAnalysis?.downstreamUnlockAnalysisIds ?? [];
  const downstreamAnalyses = downstreamAnalysisIds
    .map((analysisId) => analysisRegistry.find((analysis) => analysis.analysisId === analysisId))
    .filter((analysis): analysis is CharacterizationAnalysisRegistryRow => Boolean(analysis));
  const additionalBlockedPipelineAnalyses = analysisRegistry.filter(
    (analysis) =>
      analysis.prerequisiteState === "requires_upstream_result" &&
      !downstreamAnalysisIds.includes(analysis.analysisId),
  );

  useEffect(() => {
    const sourceParameters = resultDetail?.identifySurface.sourceParameters ?? [];
    const firstSourceParameter =
      sourceParameters.find(
        (option) => option.artifactId === resultExplorer.selectedArtifactId,
      ) ?? sourceParameters[0];
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
  }, [resultDetail?.resultId, resultExplorer.selectedArtifactId]);

  useEffect(() => {
    setSweepAxisFilter("");
    setCollectionFilter("");
  }, [selectedDesignId]);

  useEffect(() => {
    syncRouteState({
      designId: selectedDesignId,
      resultId: selectedResultId,
      taskId: resolvedTaskId,
      isExplicitRouteResultPending,
      resolvedResultSource: resultSelectionSource,
    });
  }, [
    isExplicitRouteResultPending,
    resultSelectionSource,
    resolvedTaskId,
    selectedDesignId,
    selectedResultId,
    syncRouteState,
  ]);

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

  async function handleRunAnalysis() {
    await submitCharacterizationTask();
  }

  async function handleRefreshWorkflow() {
    setIsRefreshingWorkflow(true);
    try {
      await refreshCharacterizationWorkflow();
    } finally {
      setIsRefreshingWorkflow(false);
    }
  }

  function handleSelectAllVisibleTraces() {
    setSelectedTraceIds(visibleTraces.map((trace) => trace.trace_id));
  }

  function handleSelectBaseVisibleTraces() {
    setSelectedTraceIds(
      visibleTraces
        .filter((trace) => trace.trace_mode_group === "base")
        .map((trace) => trace.trace_id),
    );
  }

  function handleClearTraceSelection() {
    setSelectedTraceIds([]);
  }

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Research Workflow"
        title="Characterization"
        description="Review the backend-derived data collection, run one pipeline step at a time, and inspect member-aware results without leaving the workbench."
        actions={
          <button
            type="button"
            onClick={() => {
              void handleRefreshWorkflow();
            }}
            disabled={isRefreshingWorkflow}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRefreshingWorkflow ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            Refresh
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
          title="Select Active Dataset"
          description="Choose a dataset before entering the characterization pipeline workbench."
        >
          <p className="text-sm leading-6 text-muted-foreground">
            Pick a dataset in the shell to review the design scope, derived data collection, and analysis pipeline.
          </p>
          {activeDatasetErrorNotice ? (
            <div className="mt-4">
              <SectionNotice
                title={activeDatasetErrorNotice.summary}
                detail={activeDatasetErrorNotice.detail}
              />
            </div>
          ) : null}
        </SurfacePanel>
      ) : (
        <div className="space-y-6">
          <SurfacePanel
            title="Design / Source Scope"
            description="Choose the design and raw trace scope that anchor the derived collection review."
          >
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <SurfaceTag tone="default">{activeDatasetState.activeDataset.name}</SurfaceTag>
                <SurfaceTag tone="default">{activeDatasetState.activeDataset.datasetId}</SurfaceTag>
                {selectedDesign ? (
                  <SurfaceTag
                    tone={selectedDesign.compare_readiness === "ready" ? "success" : "default"}
                  >
                    {selectedDesign.compare_readiness}
                  </SurfaceTag>
                ) : null}
              </div>

              <AppSelectField
                label="Design"
                value={selectedDesignId ?? ""}
                onChange={setSelectedDesignId}
                options={designs.map((design) => ({
                  value: design.design_id,
                  label: design.name,
                  description: `${design.trace_count} traces · ${formatCoverageLabel(
                    design.source_coverage,
                  )}`,
                }))}
                placeholder={isDesignsLoading ? "Loading designs" : "Select a design"}
              />

              {selectedDesign ? (
                <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <SurfaceTag tone="default">{selectedDesign.design_id}</SurfaceTag>
                    <p className="text-sm font-medium text-foreground">
                      {selectedDesign.trace_count} traces in this design scope
                    </p>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    {formatCoverageLabel(selectedDesign.source_coverage)}
                  </p>
                </div>
              ) : null}
              {designsErrorNotice ? (
                <SectionNotice title={designsErrorNotice.summary} detail={designsErrorNotice.detail} />
              ) : null}

              <div className="rounded-[1rem] border border-border bg-background px-4 py-4 shadow-[0_8px_22px_rgba(15,23,42,0.05)]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Trace Selection
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {traceSelectionSummary}
                      {visibleTraces.length !== traces.length ? ` · ${visibleTraces.length} shown` : ""}
                      {visibleSelectedTraceCount > 0 &&
                      visibleSelectedTraceCount !== selectedTraceIds.length
                        ? ` · ${visibleSelectedTraceCount} shown selected`
                        : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SurfaceActionButton
                      type="button"
                      onClick={handleSelectAllVisibleTraces}
                      className="px-3 py-1.5 text-xs"
                    >
                      All
                    </SurfaceActionButton>
                    <SurfaceActionButton
                      type="button"
                      onClick={handleSelectBaseVisibleTraces}
                      className="px-3 py-1.5 text-xs"
                    >
                      Base
                    </SurfaceActionButton>
                    <SurfaceActionButton
                      type="button"
                      onClick={handleClearTraceSelection}
                      className="px-3 py-1.5 text-xs"
                    >
                      Clear
                    </SurfaceActionButton>
                  </div>
                </div>

                <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,0.85fr)_minmax(0,1.3fr)]">
                  {sweepAxisOptions.length > 0 ? (
                    <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                      <p className="mb-3 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Sweep Axis
                      </p>
                      <AppInlineSelect
                        ariaLabel="Characterization sweep axis filter"
                        value={sweepAxisFilter}
                        onChange={setSweepAxisFilter}
                        options={[
                          { value: "", label: "All sweep axes" },
                          ...sweepAxisOptions.map((axis) => ({
                            value: axis,
                            label: axis,
                          })),
                        ]}
                      />
                    </div>
                  ) : null}

                  {collectionOptions.length > 0 ? (
                    <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                      <p className="mb-3 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Collection Hint
                      </p>
                      <AppInlineSelect
                        ariaLabel="Characterization trace collection filter"
                        value={collectionFilter}
                        onChange={setCollectionFilter}
                        options={[
                          { value: "", label: "All collections" },
                          ...collectionOptions.map((option) => ({
                            value: option.value,
                            label: option.label,
                          })),
                        ]}
                      />
                    </div>
                  ) : null}

                  <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Derived Collection Hint
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Sweep-aware grouping stays backend-derived. These filters help you review the selected scope without inventing frontend-owned scientific meaning.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {sweepAxisOptions.map((axis) => (
                        <SurfaceTag key={axis} tone="default">
                          {axis}
                        </SurfaceTag>
                      ))}
                      {collectionOptions.slice(0, 4).map((option) => (
                        <SurfaceTag key={option.value} tone="default">
                          {option.label}
                        </SurfaceTag>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-4 overflow-x-auto rounded-[0.95rem] border border-border">
                  <table className="min-w-full table-fixed text-left text-sm">
                    <thead className="bg-surface text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      <tr>
                        <th className="w-14 px-3 py-3">Use</th>
                        <th className="min-w-[220px] px-3 py-3">Trace</th>
                        <th className="w-28 px-3 py-3">Family</th>
                        <th className="w-28 px-3 py-3">View</th>
                        <th className="w-24 px-3 py-3">Source</th>
                        <th className="w-24 px-3 py-3">Mode</th>
                        <th className="w-52 px-3 py-3">Sweep / Collection</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border bg-background">
                      {visibleTraces.map((trace) => {
                        const isSelected = selectedTraceIds.includes(trace.trace_id);
                        return (
                          <tr
                            key={trace.trace_id}
                            className={cx(
                              "cursor-pointer transition hover:bg-primary/[0.05]",
                              isSelected && "bg-primary/[0.08]",
                            )}
                            onClick={() => {
                              toggleTraceSelection(trace.trace_id);
                            }}
                          >
                            <td className="px-3 py-3 align-top">
                              <input
                                checked={isSelected}
                                readOnly
                                type="checkbox"
                                className="mt-1 h-4 w-4 rounded border-border text-primary"
                              />
                            </td>
                            <td className="px-3 py-3 align-top">
                              <p className="font-medium text-foreground">{trace.parameter}</p>
                              <p className="mt-1 text-xs text-muted-foreground">{trace.trace_id}</p>
                              <p className="mt-2 text-xs text-muted-foreground">
                                {trace.provenance_summary}
                              </p>
                            </td>
                            <td className="px-3 py-3 align-top text-muted-foreground">
                              {trace.family.replaceAll("_", " ")}
                            </td>
                            <td className="px-3 py-3 align-top text-muted-foreground">
                              {formatRepresentationLabel(trace.representation)}
                            </td>
                            <td className="px-3 py-3 align-top text-muted-foreground">
                              {formatSourceLabel(trace.source_kind)}
                            </td>
                            <td className="px-3 py-3 align-top text-muted-foreground">
                              {formatModeLabel(trace.trace_mode_group)}
                            </td>
                            <td className="px-3 py-3 align-top">
                              <div className="space-y-2">
                                <div className="flex flex-wrap gap-2">
                                  {trace.availableSweepAxes.length > 0 ? (
                                    trace.availableSweepAxes.map((axis) => (
                                      <SurfaceTag key={`${trace.trace_id}-${axis}`} tone="default">
                                        {axis}
                                      </SurfaceTag>
                                    ))
                                  ) : (
                                    <SurfaceTag tone="default">No sweep axis</SurfaceTag>
                                  )}
                                </div>
                                <p className="text-xs text-muted-foreground">{trace.axesSummary}</p>
                                {trace.collectionProjection ? (
                                  <p className="text-xs text-muted-foreground">
                                    {trace.collectionProjection.label} · {trace.collectionProjection.summary}
                                  </p>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {!isTracesLoading && visibleTraces.length === 0 ? (
                  <p className="mt-4 rounded-[0.95rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    No traces match the current design scope and sweep-aware filters yet.
                  </p>
                ) : null}
                {tracesErrorNotice ? (
                  <div className="mt-4">
                    <SectionNotice title={tracesErrorNotice.summary} detail={tracesErrorNotice.detail} />
                  </div>
                ) : null}
              </div>
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Data Collection Review"
            description="Review the backend-derived scientific collection before starting any analysis run."
          >
            <div className="space-y-4">
              {analysisRegistryErrorNotice ? (
                <SectionNotice
                  title={analysisRegistryErrorNotice.summary}
                  detail={analysisRegistryErrorNotice.detail}
                />
              ) : null}

              {dataCollectionReview ? (
                <>
                  <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Review Summary
                        </p>
                        <p className="mt-2 text-sm font-medium text-foreground">
                          {reviewSummary(dataCollectionReview, selectedTraceIds.length)}
                        </p>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {dataCollectionReview.groupingSummary}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-[11px]">
                        <SurfaceTag tone={collectionReadinessTone(dataCollectionReview.readinessState)}>
                          {dataCollectionReview.readinessState.replaceAll("_", " ")}
                        </SurfaceTag>
                        <SurfaceTag tone="default">
                          {dataCollectionReview.collectionMembers.length} members
                        </SurfaceTag>
                        <SurfaceTag tone="default">
                          {dataCollectionReview.runnableAnalyses.length} runnable
                        </SurfaceTag>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {dataCollectionReview.availableSweepAxes.map((axis) => (
                        <SurfaceTag key={axis} tone="default">
                          {axis}
                        </SurfaceTag>
                      ))}
                      {dataCollectionReview.sharedAxes.map((axis) => (
                        <SurfaceTag key={`${axis.name}-${axis.length}`} tone="default">
                          {axis.name}
                          {axis.unit ? ` (${axis.unit})` : ""}
                        </SurfaceTag>
                      ))}
                      {dataCollectionReview.collectionProjection ? (
                        <SurfaceTag tone="default">
                          {dataCollectionReview.collectionProjection.label}
                        </SurfaceTag>
                      ) : null}
                    </div>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                    <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Source Coverage
                      </p>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {formatCoverageLabel(dataCollectionReview.sourceCoverage)}
                      </p>

                      {inputCollectionPayload ? (
                        <div className="mt-4 space-y-2">
                          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                            Input Collection
                          </p>
                          <p className="text-sm text-foreground">
                            {inputCollectionPayload.groupingSummary}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <SurfaceTag tone="default">
                              {inputCollectionPayload.traceCount} traces
                            </SurfaceTag>
                            {inputCollectionPayload.axisSignature ? (
                              <SurfaceTag tone="default">{inputCollectionPayload.axisSignature}</SurfaceTag>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Runnable Analyses
                        </p>
                        <div className="mt-3 space-y-2">
                          {dataCollectionReview.runnableAnalyses.length > 0 ? (
                            dataCollectionReview.runnableAnalyses.map((analysis) => (
                              <div
                                key={analysis.analysisId}
                                className="rounded-xl border border-border bg-surface px-3 py-3"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <SurfaceTag tone={pipelineStateTone(analysis.prerequisiteState)}>
                                    {formatPipelineState(analysis.prerequisiteState)}
                                  </SurfaceTag>
                                  <SurfaceTag tone={availabilityTone(analysis.availabilityState)}>
                                    {analysis.availabilityState}
                                  </SurfaceTag>
                                </div>
                                <p className="mt-2 text-sm font-medium text-foreground">
                                  {analysis.label}
                                </p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {analysis.summary}
                                </p>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm text-muted-foreground">
                              No analysis is runnable for the current collection yet.
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Blocked Analyses
                        </p>
                        <div className="mt-3 space-y-2">
                          {dataCollectionReview.blockedAnalyses.length > 0 ? (
                            dataCollectionReview.blockedAnalyses.map((analysis) => (
                              <div
                                key={analysis.analysisId}
                                className="rounded-xl border border-border bg-surface px-3 py-3"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <SurfaceTag tone={pipelineStateTone(analysis.prerequisiteState)}>
                                    {formatPipelineState(analysis.prerequisiteState)}
                                  </SurfaceTag>
                                  <SurfaceTag tone={availabilityTone(analysis.availabilityState)}>
                                    {analysis.availabilityState}
                                  </SurfaceTag>
                                </div>
                                <p className="mt-2 text-sm font-medium text-foreground">
                                  {analysis.label}
                                </p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {analysis.summary}
                                </p>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm text-muted-foreground">
                              No blocked analyses are reported for this collection.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Collection Members
                    </p>
                    <div className="mt-3 grid gap-3 lg:grid-cols-2">
                      {dataCollectionReview.collectionMembers.map((member) => (
                        <div
                          key={member.memberKey}
                          className="rounded-xl border border-border bg-surface px-4 py-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <SurfaceTag tone="default">{member.memberKey}</SurfaceTag>
                            <SurfaceTag tone="default">{formatSourceLabel(member.sourceKind)}</SurfaceTag>
                            <SurfaceTag tone="default">{formatModeLabel(member.traceModeGroup)}</SurfaceTag>
                          </div>
                          <p className="mt-2 text-sm font-medium text-foreground">{member.label}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {member.parameter} · {formatRepresentationLabel(member.representation)} · {member.traceId}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">{member.provenanceSummary}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : isAnalysisRegistryLoading ? (
                <p className="text-sm text-muted-foreground">Loading data collection review…</p>
              ) : (
                <SectionNotice
                  title="No collection review available"
                  detail={
                    selectedTraceIds.length > 0
                      ? "The backend did not return a derived collection review for this trace scope."
                      : "Select traces to see the backend-derived data collection review."
                  }
                  tone="default"
                />
              )}
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Analysis Pipeline"
            description="Choose the current pipeline step, inspect prerequisites, and run only when the backend says the collection is ready."
          >
            <div className="space-y-4">
              <SectionNotice
                title={selectedPipelineExplanation.title}
                detail={selectedPipelineExplanation.detail}
                tone={selectedPipelineExplanation.tone}
              />

              <div className="grid gap-3 xl:grid-cols-2">
                {analysisRegistry.map((analysis) => (
                  <button
                    key={analysis.analysisId}
                    type="button"
                    onClick={() => {
                      setSelectedAnalysisId(analysis.analysisId);
                    }}
                    className={cx(
                      "rounded-[1rem] border px-4 py-4 text-left transition",
                      selectedAnalysisId === analysis.analysisId
                        ? "border-primary/35 bg-primary/10"
                        : "border-border bg-background hover:border-primary/25 hover:bg-primary/5",
                    )}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{analysis.label}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {analysis.analysisId}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <SurfaceTag tone={availabilityTone(analysis.availabilityState)}>
                          {analysis.availabilityState}
                        </SurfaceTag>
                        <SurfaceTag tone={pipelineStateTone(analysis.prerequisiteState)}>
                          {formatPipelineState(analysis.prerequisiteState)}
                        </SurfaceTag>
                      </div>
                    </div>

                    <p className="mt-3 text-sm text-muted-foreground">
                      {analysis.prerequisiteState === "requires_upstream_result"
                        ? analysis.upstreamResultRequirement?.summary || analysis.traceCompatibility.summary
                        : analysis.traceCompatibility.summary}
                    </p>

                    {analysis.downstreamUnlockAnalysisIds.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {analysis.downstreamUnlockAnalysisIds.map((analysisId) => (
                          <SurfaceTag key={`${analysis.analysisId}-${analysisId}`} tone="default">
                            Unlocks {analysisId}
                          </SurfaceTag>
                        ))}
                      </div>
                    ) : null}
                  </button>
                ))}
              </div>

              {analysisRegistryErrorNotice ? (
                <SectionNotice
                  title={analysisRegistryErrorNotice.summary}
                  detail={analysisRegistryErrorNotice.detail}
                />
              ) : null}

              {selectedAnalysis ? (
                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Selected Analysis
                      </p>
                      <p className="mt-2 text-sm font-medium text-foreground">
                        {selectedAnalysis.label}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <SurfaceTag tone={availabilityTone(selectedAnalysis.availabilityState)}>
                        {selectedAnalysis.availabilityState}
                      </SurfaceTag>
                      <SurfaceTag tone={pipelineStateTone(selectedAnalysis.prerequisiteState)}>
                        {formatPipelineState(selectedAnalysis.prerequisiteState)}
                      </SurfaceTag>
                    </div>
                  </div>

                  {selectedAnalysis.requiredConfigFields.length > 0 ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      {selectedAnalysis.requiredConfigFields.map((field) => (
                        <label
                          key={field}
                          className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3"
                        >
                          <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                            {formatConfigLabel(field)}
                          </p>
                          <input
                            value={analysisConfigValues[field] ?? ""}
                            onChange={(event) => {
                              updateAnalysisConfigValue(field, event.target.value);
                            }}
                            placeholder={configPlaceholder(field)}
                            className="w-full rounded-[0.8rem] border border-border/85 bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                          />
                        </label>
                      ))}
                    </div>
                  ) : null}

                  {taskMutationState.message ? (
                    <div
                      className={cx(
                        "mt-4 rounded-[0.95rem] border px-4 py-3 text-sm",
                        resolveSurfaceInsetToneClass(taskMutationTone),
                      )}
                    >
                      {taskMutationState.message}
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => {
                      void handleRunAnalysis();
                    }}
                    disabled={
                      taskMutationState.state === "submitting" ||
                      !selectedDesignId ||
                      !selectedAnalysis ||
                      selectedAnalysis.availabilityState === "unavailable" ||
                      selectedAnalysis.prerequisiteState !== "ready" ||
                      selectedTraceIds.length === 0
                    }
                    className="mt-4 inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {taskMutationState.state === "submitting" ? (
                      <LoaderCircle className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Run Analysis
                  </button>
                </div>
              ) : null}
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Active Analysis Run"
            description="Keep the latest page-local run state visible without turning the workbench into a task dashboard."
          >
            <div className="space-y-4">
              {activeTask ? (
                <div className="flex flex-wrap items-start justify-between gap-3 rounded-[0.95rem] border border-border bg-background px-4 py-4">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Current Analysis
                    </p>
                    <p className="mt-2 text-sm font-medium text-foreground">
                      {activeTask.progress.summary}
                    </p>
                    {activeRunDetail ? (
                      <p className="mt-1 text-sm text-muted-foreground">{activeRunDetail.message}</p>
                    ) : null}
                  </div>
                  <SurfaceTag tone={taskStatusTone(activeTask.status)}>{activeTask.status}</SurfaceTag>
                </div>
              ) : (
                <SectionNotice
                  title="No active run attached"
                  detail="Start an analysis or reattach through the shared queue to keep the current pipeline step in view here."
                  tone="default"
                />
              )}

              {isTaskTransitioning ? (
                <p className="text-sm text-muted-foreground">Refreshing active analysis run…</p>
              ) : null}
              {activeTaskErrorNotice ? (
                <SectionNotice
                  title={activeTaskErrorNotice.summary}
                  detail={activeTaskErrorNotice.detail}
                />
              ) : null}

              <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Run History
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Compact history for the current design scope.
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <SurfaceActionButton
                      type="button"
                      onClick={goToPrevRunHistoryPage}
                      disabled={!runHistoryMeta?.prevCursor}
                      className="px-3 py-1.5 text-xs"
                    >
                      Prev
                    </SurfaceActionButton>
                    <SurfaceActionButton
                      type="button"
                      onClick={goToNextRunHistoryPage}
                      disabled={!runHistoryMeta?.nextCursor}
                      className="px-3 py-1.5 text-xs"
                    >
                      Next
                    </SurfaceActionButton>
                  </div>
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
                      className="w-full rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-left transition hover:border-primary/25 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-foreground">{run.label}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {run.analysisId} · {run.updatedAt}
                          </p>
                        </div>
                        <SurfaceTag tone={characterizationStatusTone(run.status)}>{run.status}</SurfaceTag>
                      </div>
                      <p className="mt-3 text-sm text-muted-foreground">{run.provenanceSummary}</p>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                        <SurfaceTag tone="default">{run.traceCount} traces</SurfaceTag>
                        <SurfaceTag tone="default">{run.scope}</SurfaceTag>
                        {run.resultId ? <SurfaceTag tone="default">Open result</SurfaceTag> : null}
                      </div>
                    </button>
                  ))}

                  {isRunHistoryLoading ? (
                    <p className="text-sm text-muted-foreground">Loading run history…</p>
                  ) : null}
                  {!isRunHistoryLoading && runHistory.length === 0 ? (
                    <p className="rounded-[0.95rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                      No run history is available for this design scope yet.
                    </p>
                  ) : null}
                  {runHistoryErrorNotice ? (
                    <SectionNotice title={runHistoryErrorNotice.summary} detail={runHistoryErrorNotice.detail} />
                  ) : null}
                </div>
              </div>
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Result Preview"
            description="Inspect persisted results, member-aware artifacts, diagnostics, and identify-ready surfaces."
          >
            <div className="space-y-4">
              <div className="grid gap-6 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
                <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
                  <div>
                    <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Results
                    </h4>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Persisted results for the current design.
                    </p>
                  </div>

                  {showResultControls ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                      <label className="relative block">
                        <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                        <input
                          value={resultSearch}
                          onChange={(event) => {
                            setResultSearch(event.target.value);
                          }}
                          placeholder="Search results"
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
                  ) : null}

                  <div className={cx("space-y-3", showResultControls ? "mt-4" : "mt-0")}>
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
                        </div>

                        <p className="mt-3 text-sm text-muted-foreground">{result.freshnessSummary}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{result.provenanceSummary}</p>
                      </button>
                    ))}

                    {!isResultsLoading && results.length === 0 ? (
                      <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                        No saved result matches this scope and filter.
                      </p>
                    ) : null}
                    {resultsErrorNotice ? (
                      <SectionNotice title={resultsErrorNotice.summary} detail={resultsErrorNotice.detail} />
                    ) : null}
                  </div>
                </div>

                <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
                  <div>
                    <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Result Detail
                    </h4>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Inspect one persisted result, then tag parameters from the artifact surface that is currently in focus.
                    </p>
                  </div>

                  {!selectedResultId ? (
                    <p className="mt-4 rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                      Select a saved result to inspect its artifacts, diagnostics, and identify surface.
                    </p>
                  ) : null}

                  {resultDetail ? (
                    <div className="mt-4 space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h3 className="text-base font-semibold text-foreground">{resultDetail.title}</h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {resultDetail.analysisId} · {resultDetail.updatedAt}
                          </p>
                        </div>
                        <SurfaceTag tone={characterizationStatusTone(resultDetail.status)}>
                          {resultDetail.status}
                        </SurfaceTag>
                      </div>

                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                              Freshness
                            </p>
                            <p className="mt-2 text-sm text-foreground">
                              {resultDetail.freshnessSummary}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                              Provenance
                            </p>
                            <p className="mt-2 text-sm text-foreground">
                              {resultDetail.provenanceSummary}
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 flex flex-wrap gap-2">
                          <SurfaceTag tone="default">{resultDetail.traceCount} traces</SurfaceTag>
                          {resultDetail.inputResultRefs.map((ref) => (
                            <SurfaceTag key={`${ref.analysisId}-${ref.resultId}`} tone="default">
                              Upstream {ref.analysisId}
                            </SurfaceTag>
                          ))}
                        </div>
                      </div>

                      {resultDetail.diagnostics.length > 0 ? (
                        <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
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
                          </div>
                        </div>
                      ) : null}

                      <CharacterizationResultExplorer
                        resultDetail={resultDetail}
                        explorer={resultExplorer}
                      />

                      <details className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                          Debug Payload
                        </summary>
                        <div className="mt-4">
                          <ResultPayloadPreview payload={resultDetail.payload} />
                        </div>
                      </details>

                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                              Identify & Tag
                            </p>
                            <p className="mt-2 text-sm text-foreground">
                              Map one result parameter into a designated metric.
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
                            No identify candidates are available for this result yet.
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
                              No parameter tags were applied from this result yet.
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {isResultDetailLoading ? (
                    <p className="mt-4 text-sm text-muted-foreground">Loading result detail…</p>
                  ) : null}
                  {resultDetailErrorNotice ? (
                    <div className="mt-4">
                      <SectionNotice
                        title={resultDetailErrorNotice.summary}
                        detail={resultDetailErrorNotice.detail}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Downstream Analysis / Next Step"
            description="Keep the next pipeline step visible without implying runtime support that the backend has not granted yet."
          >
            <div className="space-y-4">
              {downstreamAnalyses.length > 0 ? (
                <div className="grid gap-3 xl:grid-cols-2">
                  {downstreamAnalyses.map((analysis) => (
                    <div
                      key={analysis.analysisId}
                      className="rounded-[1rem] border border-border bg-background px-4 py-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{analysis.label}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                            {analysis.analysisId}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <SurfaceTag tone={pipelineStateTone(analysis.prerequisiteState)}>
                            {formatPipelineState(analysis.prerequisiteState)}
                          </SurfaceTag>
                          <SurfaceTag tone={availabilityTone(analysis.availabilityState)}>
                            {analysis.availabilityState}
                          </SurfaceTag>
                        </div>
                      </div>
                      <p className="mt-3 text-sm text-muted-foreground">
                        {analysis.prerequisiteState === "requires_upstream_result"
                          ? analysis.upstreamResultRequirement?.summary || analysis.traceCompatibility.summary
                          : analysis.traceCompatibility.summary}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <SectionNotice
                  title="No downstream step unlocked yet"
                  detail="Complete or select a persisted result to see which next pipeline step becomes available from this workbench state."
                  tone="default"
                />
              )}

              {additionalBlockedPipelineAnalyses.length > 0 ? (
                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Still Waiting On Upstream Results
                  </p>
                  <div className="mt-3 space-y-2">
                    {additionalBlockedPipelineAnalyses.map((analysis) => (
                      <div
                        key={analysis.analysisId}
                        className="rounded-xl border border-border bg-surface px-3 py-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <SurfaceTag tone={pipelineStateTone(analysis.prerequisiteState)}>
                            {formatPipelineState(analysis.prerequisiteState)}
                          </SurfaceTag>
                          <SurfaceTag tone={availabilityTone(analysis.availabilityState)}>
                            {analysis.availabilityState}
                          </SurfaceTag>
                        </div>
                        <p className="mt-2 text-sm font-medium text-foreground">{analysis.label}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {analysis.upstreamResultRequirement?.summary || analysis.traceCompatibility.summary}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </SurfacePanel>
        </div>
      )}
    </div>
  );
}
