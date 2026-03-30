"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { LoaderCircle, Play, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { CharacterizationResultExplorer } from "@/features/characterization/components/characterization-result-explorer";
import { useCharacterizationResultExplorer } from "@/features/characterization/hooks/use-characterization-result-explorer";
import { useCharacterizationWorkflowData } from "@/features/characterization/hooks/use-characterization-workflow-data";
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

function uniqueStrings(values: readonly string[]) {
  return Array.from(new Set(values.filter((value) => value.trim().length > 0)));
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
      : "No preferred modes";
  const selectedLabel =
    input.selectedTraceCount > 0
      ? `${input.matchedTraceCount}/${input.selectedTraceCount} match`
      : `${input.matchedTraceCount} compatible`;

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

function analysisAvailabilityGroup(state: "recommended" | "available" | "unavailable") {
  if (state === "recommended") {
    return "Recommended";
  }
  if (state === "available") {
    return "Available";
  }
  return "Unavailable";
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
      return "Measure";
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
      return "All";
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

export function CharacterizationWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsValue = searchParams.toString();
  const [, startTransition] = useTransition();
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
    analysisRegistryError,
    isAnalysisRegistryLoading,
    selectedAnalysis,
    selectedAnalysisId,
    setSelectedAnalysisId,
    analysisConfigValues,
    updateAnalysisConfigValue,
    results,
    resultsError,
    isResultsLoading,
    requestedResultId,
    selectedResultId,
    setSelectedResultId,
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
    selectedTaskId: parseTaskIdParam(searchParams.get("taskId")),
    requestedDesignId: searchParams.get("designId"),
    requestedResultId: searchParams.get("resultId"),
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
    "Could not load analyses.",
    analysisRegistryError,
  );
  const resultsErrorNotice = buildSectionError("Could not load saved results.", resultsError);
  const activeTaskErrorNotice = buildSectionError(
    "Could not load the latest analysis.",
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
  const analysisOptions = useMemo(
    () =>
      analysisRegistry.map((analysis) => ({
        value: analysis.analysisId,
        label: analysis.label,
        description: formatTraceCompatibilityLabel(analysis.traceCompatibility),
        disabled: analysis.availabilityState === "unavailable",
        group: analysisAvailabilityGroup(analysis.availabilityState),
      })),
    [analysisRegistry],
  );
  const sweepAxisOptions = useMemo(
    () => buildCharacterizationSweepAxisOptions(traces),
    [traces],
  );
  const collectionOptions = useMemo(
    () => buildCharacterizationCollectionOptions(traces),
    [traces],
  );
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
  const noRunnableAnalyses =
    analysisRegistry.length > 0 &&
    analysisRegistry.every((analysis) => analysis.availabilityState === "unavailable");
  const analysisExplanation = selectedAnalysis
    ? {
        tone:
          selectedAnalysis.availabilityState === "recommended"
            ? ("primary" as const)
            : selectedAnalysis.availabilityState === "unavailable"
              ? ("warning" as const)
              : ("default" as const),
        title:
          selectedAnalysis.availabilityState === "unavailable"
            ? "Readiness Explanation"
            : "Validation Explanation",
        detail:
          selectedAnalysis.availabilityState === "unavailable"
            ? formatTraceCompatibilityLabel(selectedAnalysis.traceCompatibility)
            : `Ready for the current trace scope. ${formatTraceCompatibilityLabel(
                selectedAnalysis.traceCompatibility,
              )}`,
      }
    : noRunnableAnalyses
      ? {
          tone: "warning" as const,
          title: "Readiness Explanation",
          detail:
            uniqueStrings(
              analysisRegistry.map((analysis) => analysis.traceCompatibility.summary),
            ).join(" · ") || "No analysis is runnable for this trace scope yet.",
        }
      : {
          tone: "default" as const,
          title: "Validation Explanation",
          detail:
            selectedTraceIds.length > 0
              ? "Choose an analysis to review how it fits the current trace scope."
              : "Select traces to see which analyses can run for this scope.",
        };
  const latestRunStatusDetail = activeTask
    ? activeTask.resultHandoff?.availability === "ready"
      ? {
          title: "Result ready",
          message: `Updated ${activeTask.progress.updatedAt}. The latest result is ready below.`,
        }
      : activeTask.status === "failed" ||
          activeTask.status === "terminated" ||
          activeTask.status === "cancelled"
        ? {
            title: "Run ended",
            message: `Updated ${activeTask.progress.updatedAt}. This run ended before a saved result was available.`,
          }
        : activeTask.resultHandoff?.availability === "pending" || activeTask.status === "completed"
          ? {
              title: "Saving result",
              message: `Updated ${activeTask.progress.updatedAt}. The analysis finished and the saved result is still being prepared.`,
            }
          : {
              title: "In progress",
              message: `Updated ${activeTask.progress.updatedAt}. This analysis is still running.`,
            }
    : null;

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
    const nextHref = buildCharacterizationSearchHref(pathname, searchParamsValue, {
      designId: selectedDesignId,
      resultId: selectedResultId,
      taskId: resolvedTaskId ? String(resolvedTaskId) : null,
    });
    const currentHref = searchParamsValue ? `${pathname}?${searchParamsValue}` : pathname;

    if (nextHref === currentHref) {
      return;
    }

    startTransition(() => {
      router.replace(nextHref, { scroll: false });
    });
  }, [
    pathname,
    resolvedTaskId,
    router,
    searchParamsValue,
    selectedDesignId,
    selectedResultId,
    startTransition,
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
        description="Choose a design, run a characterization analysis, and keep the latest saved result in view."
        actions={
          <button
            type="button"
            onClick={() => {
              void handleRefreshWorkflow();
            }}
            disabled={isRefreshingWorkflow}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRefreshingWorkflow ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : null}
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
          description="Choose a dataset before running characterization analyses."
        >
          <p className="text-sm leading-6 text-muted-foreground">
            Pick a dataset in the shell to start characterization work.
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
            title="Select Data Scope"
            description="Choose a design and the traces that define this analysis."
          >
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <SurfaceTag tone="default">{activeDatasetState.activeDataset.name}</SurfaceTag>
                <SurfaceTag tone="default">
                  {activeDatasetState.activeDataset.datasetId}
                </SurfaceTag>
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
                      {selectedDesign.trace_count} traces in view
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
                      {visibleTraces.length !== traces.length
                        ? ` · ${visibleTraces.length} shown`
                        : ""}
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
                      Collection Projection
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Backend grouping hints keep sweep-aware traces together without claiming value-level or provenance-derived meaning.
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
                              <p className="mt-1 text-xs text-muted-foreground">
                                {trace.trace_id}
                              </p>
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
                                <p className="text-xs text-muted-foreground">
                                  {trace.axesSummary}
                                </p>
                                {trace.collectionProjection ? (
                                  <p className="text-xs text-muted-foreground">
                                    {trace.collectionProjection.label} ·{" "}
                                    {trace.collectionProjection.summary}
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
            title="Choose Analysis & Setup"
            description="Pick an analysis for this scope, then fill the required setup."
          >
            <div className="space-y-4">
              <AppSelectField
                label="Analysis"
                value={selectedAnalysisId ?? ""}
                onChange={setSelectedAnalysisId}
                options={analysisOptions}
                placeholder={
                  isAnalysisRegistryLoading
                    ? "Loading analyses"
                    : noRunnableAnalyses
                      ? "None available"
                      : "Select an analysis"
                }
              />
              <SectionNotice
                title={analysisExplanation.title}
                detail={analysisExplanation.detail}
                tone={analysisExplanation.tone}
              />
              {selectedAnalysis ? (
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <SurfaceTag tone={analysisAvailabilityTone(selectedAnalysis.availabilityState)}>
                    {selectedAnalysis.availabilityState}
                  </SurfaceTag>
                  <SurfaceTag tone="default">{selectedAnalysis.analysisId}</SurfaceTag>
                </div>
              ) : null}
              {analysisRegistryErrorNotice ? (
                <SectionNotice
                  title={analysisRegistryErrorNotice.summary}
                  detail={analysisRegistryErrorNotice.detail}
                />
              ) : null}

              {selectedAnalysis?.requiredConfigFields.length ? (
                <div className="grid gap-3 md:grid-cols-2">
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
                    "rounded-[0.95rem] border px-4 py-3 text-sm",
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
                  selectedTraceIds.length === 0
                }
                className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {taskMutationState.state === "submitting" ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Run Analysis
              </button>
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Inspect Result"
            description="Review saved results for this design and keep the current analysis context light."
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
                    {latestRunStatusDetail ? (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {latestRunStatusDetail.message}
                      </p>
                    ) : null}
                  </div>
                  <SurfaceTag tone={taskStatusTone(activeTask.status)}>
                    {activeTask.status}
                  </SurfaceTag>
                </div>
              ) : null}
              {isTaskTransitioning ? (
                <p className="text-sm text-muted-foreground">Refreshing current analysis…</p>
              ) : null}
              {activeTaskErrorNotice ? (
                <SectionNotice
                  title={activeTaskErrorNotice.summary}
                  detail={activeTaskErrorNotice.detail}
                />
              ) : null}

              <div className="grid gap-6 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
                <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
                  <div>
                    <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Results
                    </h4>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Saved analysis results for the current design.
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

                        <p className="mt-3 text-sm text-muted-foreground">
                          {result.freshnessSummary}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {result.provenanceSummary}
                        </p>
                      </button>
                    ))}

                    {!isResultsLoading && results.length === 0 ? (
                      <p className="rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                        No saved result matches this scope and filter.
                      </p>
                    ) : null}
                    {resultsErrorNotice ? (
                      <SectionNotice
                        title={resultsErrorNotice.summary}
                        detail={resultsErrorNotice.detail}
                      />
                    ) : null}
                  </div>
                </div>

                <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
                  <div>
                    <h4 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Result Detail
                    </h4>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Inspect one saved result, then tag parameters from it.
                    </p>
                  </div>

                  {!selectedResultId ? (
                    <p className="mt-4 rounded-[1rem] border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                      Select a saved result to inspect its details, diagnostics, and tags.
                    </p>
                  ) : null}

                  {resultDetail ? (
                    <div className="mt-4 space-y-4">
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
                        {resultDetail.inputCollectionPayload ? (
                          <div className="mt-4">
                            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                              Collection Scope
                            </p>
                            <p className="mt-2 text-sm text-foreground">
                              {resultDetail.inputCollectionPayload.groupingSummary}
                            </p>
                          </div>
                        ) : null}
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
        </div>
      )}
    </div>
  );
}
