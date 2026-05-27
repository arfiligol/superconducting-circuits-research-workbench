"use client";

import { useEffect, useMemo, useState } from "react";
import { LoaderCircle, Play, Search } from "lucide-react";

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

function SecondaryDisclosure({
  title,
  meta,
  children,
  defaultOpen = false,
  className,
}: Readonly<{
  title: string;
  meta?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
}>) {
  return (
    <details
      open={defaultOpen}
      className={cx(
        "rounded-[0.95rem] border border-border bg-background px-4 py-3",
        className,
      )}
    >
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 text-left marker:hidden">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {title}
        </span>
        {meta ? <span className="text-xs text-muted-foreground">{meta}</span> : null}
      </summary>
      <div className="mt-4">{children}</div>
    </details>
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
      message: `Updated ${activeTask.progress.updatedAt}. The latest result is ready below.`,
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
  const selectedTraceRows = traces.filter((trace) =>
    selectedTraceIds.includes(trace.trace_id),
  );
  const selectedTraceInputAxisStructures = new Set(
    selectedTraceRows.map((trace) =>
      trace.availableSweepAxes.length > 0
        ? trace.availableSweepAxes.join("::")
        : "selected_scope",
    ),
  );
  const selectedTracesShareOneAxisStructure =
    selectedTraceIds.length <= 1 ||
    selectedTraceRows.length !== selectedTraceIds.length ||
    selectedTraceInputAxisStructures.size <= 1;
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
  }, [
    resultDetail?.identifySurface.designatedMetrics,
    resultDetail?.identifySurface.sourceParameters,
    resultDetail?.resultId,
    resultExplorer.selectedArtifactId,
  ]);

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
          <div className="grid gap-6 2xl:grid-cols-[minmax(0,0.95fr)_minmax(0,0.9fr)_minmax(0,1.15fr)]">
            <SurfacePanel
              title="Design Scope"
              description="Choose the design and trace scope for this run."
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
                      <SurfaceTag tone="default">
                        {selectedDesign.trace_count} traces
                      </SurfaceTag>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">
                      {formatCoverageLabel(selectedDesign.source_coverage)}
                    </p>
                  </div>
                ) : null}
                {designsErrorNotice ? (
                  <SectionNotice title={designsErrorNotice.summary} detail={designsErrorNotice.detail} />
                ) : null}

                <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Trace Scope
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

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
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
                          Collection
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
                  </div>

                  <SecondaryDisclosure
                    title="Browse Traces"
                    meta={`${visibleTraces.length} shown`}
                    defaultOpen={selectedTraceIds.length === 0}
                    className="mt-4 bg-surface"
                  >
                    <div className="overflow-x-auto rounded-[0.95rem] border border-border">
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
                        No traces match the current design scope and filters.
                      </p>
                    ) : null}
                    {tracesErrorNotice ? (
                      <div className="mt-4">
                        <SectionNotice title={tracesErrorNotice.summary} detail={tracesErrorNotice.detail} />
                      </div>
                    ) : null}
                  </SecondaryDisclosure>
                </div>

                {dataCollectionReview ? (
                  <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Collection Summary
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
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </SurfacePanel>

            <SurfacePanel
              title="Selected Analysis"
              description="Configure and submit the current pipeline step."
            >
              <div className="space-y-4">
                {selectedAnalysis &&
                (selectedAnalysis.prerequisiteState !== "ready" || selectedTraceIds.length === 0) ? (
                  <SectionNotice
                    title={selectedPipelineExplanation.title}
                    detail={selectedPipelineExplanation.detail}
                    tone={selectedPipelineExplanation.tone}
                  />
                ) : null}

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
                          Current Step
                        </p>
                        <p className="mt-2 text-base font-semibold text-foreground">
                          {selectedAnalysis.label}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {selectedAnalysis.analysisId}
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

                    <p className="mt-3 text-sm text-muted-foreground">
                      {selectedAnalysis.prerequisiteState === "requires_upstream_result"
                        ? selectedAnalysis.upstreamResultRequirement?.summary ||
                          selectedAnalysis.traceCompatibility.summary
                        : selectedAnalysis.traceCompatibility.summary}
                    </p>

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

                    {!selectedTracesShareOneAxisStructure ? (
                      <div className="mt-4">
                        <SectionNotice
                          title="Select One Input Axis Structure"
                          detail={
                            inputCollectionPayload?.groupingSummary ||
                            "Selected traces must share one persisted axis structure before this analysis can run."
                          }
                        />
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
                        selectedTraceIds.length === 0 ||
                        !selectedTracesShareOneAxisStructure
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
                ) : isAnalysisRegistryLoading ? (
                  <p className="text-sm text-muted-foreground">Loading analysis options…</p>
                ) : (
                  <SectionNotice
                    title="No analysis selected"
                    detail="Select a design and trace scope before running characterization."
                    tone="default"
                  />
                )}

                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Latest Run
                      </p>
                      <p className="mt-2 text-sm font-medium text-foreground">
                        {activeTask ? activeTask.progress.summary : "No active analysis run"}
                      </p>
                      {activeRunDetail ? (
                        <p className="mt-1 text-sm text-muted-foreground">{activeRunDetail.message}</p>
                      ) : null}
                    </div>
                    {activeTask ? (
                      <SurfaceTag tone={taskStatusTone(activeTask.status)}>{activeTask.status}</SurfaceTag>
                    ) : (
                      <SurfaceTag tone="default">idle</SurfaceTag>
                    )}
                  </div>
                </div>

                {isTaskTransitioning ? (
                  <p className="text-sm text-muted-foreground">Refreshing active analysis run…</p>
                ) : null}
                {activeTaskErrorNotice ? (
                  <SectionNotice
                    title={activeTaskErrorNotice.summary}
                    detail={activeTaskErrorNotice.detail}
                  />
                ) : null}

                <SecondaryDisclosure
                  title="Change Analysis"
                  meta={`${analysisRegistry.length} steps`}
                  defaultOpen={!selectedAnalysis && analysisRegistry.length > 0}
                >
                  <div className="grid gap-3">
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
                            : "border-border bg-surface hover:border-primary/25 hover:bg-primary/5",
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
                            ? analysis.upstreamResultRequirement?.summary ||
                              analysis.traceCompatibility.summary
                            : analysis.traceCompatibility.summary}
                        </p>
                      </button>
                    ))}
                  </div>
                </SecondaryDisclosure>
              </div>
            </SurfacePanel>

            <SurfacePanel
              title="Latest Result"
              description="Review the selected persisted result and apply identify tags."
            >
              <div className="space-y-4">
                {!selectedResultId ? (
                  <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    No saved result is selected for this design scope.
                  </p>
                ) : null}

                {resultDetail ? (
                  <div className="space-y-4">
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

                    <CharacterizationResultExplorer
                      resultDetail={resultDetail}
                      explorer={resultExplorer}
                    />

                    {resultDetail.diagnostics.length > 0 ? (
                      <SecondaryDisclosure
                        title="Fit Diagnostics"
                        meta={`${resultDetail.diagnostics.length} entries`}
                        className="bg-surface"
                      >
                        <div className="space-y-3">
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
                      </SecondaryDisclosure>
                    ) : null}

                    <SecondaryDisclosure title="Artifact Payload" meta="JSON" className="bg-surface">
                      <ResultPayloadPreview payload={resultDetail.payload} />
                    </SecondaryDisclosure>

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
                  <p className="text-sm text-muted-foreground">Loading result detail…</p>
                ) : null}
                {resultDetailErrorNotice ? (
                  <SectionNotice
                    title={resultDetailErrorNotice.summary}
                    detail={resultDetailErrorNotice.detail}
                  />
                ) : null}

                <SecondaryDisclosure
                  title="Saved Results"
                  meta={`${results.length} shown`}
                  defaultOpen={!selectedResultId}
                >
                  {showResultControls ? (
                    <div className="grid gap-3 md:grid-cols-[1fr_auto]">
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

                    {isResultsLoading ? (
                      <p className="text-sm text-muted-foreground">Loading saved results…</p>
                    ) : null}
                    {!isResultsLoading && results.length === 0 ? (
                      <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                        No saved result matches this scope and filter.
                      </p>
                    ) : null}
                    {resultsErrorNotice ? (
                      <SectionNotice title={resultsErrorNotice.summary} detail={resultsErrorNotice.detail} />
                    ) : null}
                  </div>
                </SecondaryDisclosure>
              </div>
            </SurfacePanel>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <SecondaryDisclosure
              title="Run History"
              meta={`${runHistory.length} runs`}
            >
              <div className="flex flex-wrap justify-end gap-2">
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
            </SecondaryDisclosure>

            <SecondaryDisclosure
              title="Collection Details"
              meta={
                dataCollectionReview
                  ? `${dataCollectionReview.collectionMembers.length} members`
                  : "pending"
              }
            >
              <div className="space-y-4">
                {dataCollectionReview ? (
                  <>
                    <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
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

                    <div className="grid gap-3">
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

                    <div className="grid gap-3">
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
                  </>
                ) : isAnalysisRegistryLoading ? (
                  <p className="text-sm text-muted-foreground">Loading collection details…</p>
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
            </SecondaryDisclosure>

            <SecondaryDisclosure
              title="Downstream Context"
              meta={`${downstreamAnalyses.length} unlocked`}
            >
              <div className="space-y-4">
                {downstreamAnalyses.length > 0 ? (
                  <div className="grid gap-3">
                    {downstreamAnalyses.map((analysis) => (
                      <div
                        key={analysis.analysisId}
                        className="rounded-[1rem] border border-border bg-surface px-4 py-4"
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
                    detail="Complete or select a persisted result to see the next available pipeline step."
                    tone="default"
                  />
                )}

                {additionalBlockedPipelineAnalyses.length > 0 ? (
                  <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Waiting On Upstream Results
                    </p>
                    <div className="mt-3 space-y-2">
                      {additionalBlockedPipelineAnalyses.map((analysis) => (
                        <div
                          key={analysis.analysisId}
                          className="rounded-xl border border-border bg-card px-3 py-3"
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
            </SecondaryDisclosure>
          </div>
        </div>
      )}
    </div>
  );
}
