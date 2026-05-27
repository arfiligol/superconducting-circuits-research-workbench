"use client";

import { useEffect, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";

import { CurrentTraceSaveControl } from "@/features/simulation/components/current-trace-save-control";
import {
  ExplorerControlPanel,
  ParameterSweepPanel,
  ResultSourcePanel,
  ResultViewPanel,
} from "@/features/simulation/components/simulation-result-explorer-sections";
import { formatExplorerAxisTitle } from "@/features/simulation/lib/simulation-result-explorer-labels";
import { useSimulationResultExplorer } from "@/features/simulation/hooks/use-simulation-result-explorer";
import { resolveSimulationExplorerSweepAxes } from "@/features/simulation/lib/simulation-result-explorer-state";
import {
  AppSegmentedControl,
  type AppSegmentedOption,
} from "@/features/shared/components/app-segmented-control";
import type { AppSelectOption } from "@/features/shared/components/app-select";
import { SurfacePanel } from "@/features/shared/components/surface-kit";
import type { TaskDetail } from "@/lib/api/tasks";

type SimulationResultExplorerProps = Readonly<{
  task: TaskDetail;
  activeDatasetId: string | null;
}>;

type ExplorerViewMode = "plot" | "table";

function resolveDefaultTraceParameter(
  family: string,
  outputPort: number,
  inputPort: number,
) {
  const familyPrefix = family === "s_matrix" ? "S" : family === "y_matrix" ? "Y" : "Z";
  return `${familyPrefix}${outputPort}${inputPort}`;
}

function getExplorerCopy(taskKind: TaskDetail["kind"]) {
  return {
    title:
      taskKind === "post_processing"
        ? "Post Processing Result Explorer"
        : "Simulation Result Explorer",
    description:
      taskKind === "post_processing"
        ? "Inspect saved post-processing outputs with family, source, metric, and port selectors."
        : "Inspect saved simulation outputs with family, source, metric, and port selectors.",
    loadingDescription:
      taskKind === "post_processing"
        ? "Loading post-processing result controls and plot data."
        : "Loading simulation result controls and plot data.",
    unavailableDescription:
      taskKind === "post_processing"
        ? "The post-processing result explorer is unavailable right now."
        : "The simulation result explorer is unavailable right now.",
    loadingLabel:
      taskKind === "post_processing"
        ? "Loading the persisted explorer surface for task"
        : "Loading the persisted explorer surface for task",
    errorLabel: taskKind === "post_processing" ? "post-processing" : "simulation",
    testPrefix: taskKind === "post_processing" ? "post-processing" : "simulation",
  };
}

export function SimulationResultExplorer({
  task,
  activeDatasetId,
}: SimulationResultExplorerProps) {
  const [viewMode, setViewMode] = useState<ExplorerViewMode>("plot");
  const [z0Input, setZ0Input] = useState("50");
  const [showComparedTraces, setShowComparedTraces] = useState(true);
  const explorer = useSimulationResultExplorer(task.taskId, true);
  const copy = getExplorerCopy(task.kind);
  const viewOptions = useMemo<readonly AppSegmentedOption<ExplorerViewMode>[]>(
    () => [
      { value: "plot", label: "Plot" },
      { value: "table", label: "Table" },
    ],
    [],
  );

  useEffect(() => {
    setViewMode("plot");
  }, [task.taskId]);

  useEffect(() => {
    if (!explorer.selection) {
      return;
    }

    setZ0Input(String(explorer.selection.z0));
  }, [explorer.selection]);

  const payload = explorer.data;
  const bootstrap = explorer.bootstrap;
  const selection = explorer.selection;
  const resolvedSelection = explorer.resolvedSelection;
  const familyOptions = bootstrap?.families ?? payload?.bootstrap.families ?? [];
  const sourceOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      explorer.selectedFamily?.availableSources.map((source) => ({
        value: source.key,
        label: source.label,
      })) ?? [],
    [explorer.selectedFamily],
  );
  const metricOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      explorer.selectedFamily?.availableMetrics.map((metric) => ({
        value: metric.key,
        label: metric.label,
        description: metric.unit ? `Unit · ${metric.unit}` : undefined,
      })) ?? [],
    [explorer.selectedFamily],
  );
  const sourceIsLocked = task.kind === "post_processing" && sourceOptions.length <= 1;
  const outputPortOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      bootstrap?.traceSelector.outputPorts.map((port) => ({
        value: String(port.port),
        label: port.label,
      })) ?? [],
    [bootstrap],
  );
  const inputPortOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      bootstrap?.traceSelector.inputPorts.map((port) => ({
        value: String(port.port),
        label: port.label,
      })) ?? [],
    [bootstrap],
  );
  const familySegmentOptions = useMemo<readonly AppSegmentedOption[]>(
    () =>
      familyOptions.map((family) => ({
        value: family.key,
        label: family.label,
      })),
    [familyOptions],
  );
  const ptcFamilyLabels = useMemo(
    () =>
      familyOptions
        .filter((family) => family.availableSources.some((source) => source.key === "ptc"))
        .map((family) => family.label),
    [familyOptions],
  );
  const showPtcFamilyHint =
    selection?.family === "s_matrix" &&
    !explorer.selectedFamily?.availableSources.some((source) => source.key === "ptc") &&
    ptcFamilyLabels.length > 0;
  const parameterSweepBase = bootstrap?.parameterSweep ??
    payload?.bootstrap.parameterSweep ?? {
      active: false,
      pointCount: 0,
      compareAxisIndex: null,
      axes: [],
    };
  const parameterSweep = useMemo(
    () => ({
      ...parameterSweepBase,
      axes: resolveSimulationExplorerSweepAxes(
        parameterSweepBase.axes,
        selection?.sweepIndex ?? null,
      ),
    }),
    [parameterSweepBase, selection?.sweepIndex],
  );
  const compareAxisIndex =
    parameterSweep.active && parameterSweep.axes.length > 0
      ? selection?.compareAxisIndex ?? parameterSweep.compareAxisIndex ?? 0
      : null;
  const compareAxis =
    compareAxisIndex !== null && compareAxisIndex < parameterSweep.axes.length
      ? parameterSweep.axes[compareAxisIndex]
      : null;
  const activeTraceSeries =
    compareAxis && compareAxis.selectedValueIndex < (payload?.plot.series.length ?? 0)
      ? payload?.plot.series[compareAxis.selectedValueIndex] ?? null
      : payload?.plot.series[0] ?? null;
  const visiblePlotSeries =
    compareAxis && !showComparedTraces && activeTraceSeries
      ? [activeTraceSeries]
      : payload?.plot.series ?? [];
  const visibleTraceKeys = useMemo(() => {
    const keys = visiblePlotSeries
      .map((series) => series.traceKey)
      .filter((traceKey): traceKey is string => typeof traceKey === "string" && traceKey.length > 0);
    if (keys.length > 0) {
      return [...new Set(keys)];
    }
    return payload?.selection.traceKey ? [payload.selection.traceKey] : [];
  }, [payload?.selection.traceKey, visiblePlotSeries]);
  const hasSeries = visiblePlotSeries.length > 0;
  const xAxisTitle = payload
    ? formatExplorerAxisTitle(payload.plot.xAxis.label, payload.plot.xAxis.unit)
    : "Frequency";
  const yAxisTitle = payload
    ? formatExplorerAxisTitle(payload.plot.yAxis.label, payload.plot.yAxis.unit)
    : "Result";
  const showZ0Control = selection?.family !== "s_matrix";
  const resultViewDescription =
    compareAxis && (payload?.plot.series.length ?? 0) > 1
      ? `Comparing ${compareAxis.label} traces while keeping ${activeTraceSeries?.label ?? "the active trace"} as the canonical current trace.`
      : `${activeTraceSeries?.label ?? "Backend plot selection"} updates as soon as the family, source, metric, port, or Z0 selection changes.`;

  useEffect(() => {
    setShowComparedTraces(true);
  }, [task.taskId, selection?.family, selection?.source, selection?.metric, compareAxisIndex]);

  if (explorer.isLoading || (!payload && !explorer.error)) {
    return (
      <SurfacePanel title={copy.title} description={copy.loadingDescription}>
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground"
        >
          <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
          <span>
            {copy.loadingLabel} #{task.taskId}.
          </span>
        </div>
      </SurfacePanel>
    );
  }

  if (explorer.error || !payload || !selection || !explorer.selectedFamily) {
    return (
      <SurfacePanel title={copy.title} description={copy.unavailableDescription}>
        <div className="rounded-[0.95rem] border border-rose-500/35 bg-rose-50/90 px-4 py-4 text-sm text-rose-950 dark:border-rose-500/45 dark:bg-rose-950/40 dark:text-rose-100">
          Unable to load the {copy.errorLabel} result explorer right now.{" "}
          {explorer.error instanceof Error ? explorer.error.message : "Unknown explorer error."}
        </div>
      </SurfacePanel>
    );
  }

  return (
    <SurfacePanel
      title={copy.title}
      description={copy.description}
      actions={
        <AppSegmentedControl
          value={viewMode}
          onChange={setViewMode}
          options={viewOptions}
          ariaLabel="Simulation result explorer view"
        />
      }
    >
      <div className="space-y-3">
        <ExplorerControlPanel
          selection={selection}
          familySegmentOptions={familySegmentOptions}
          explorer={explorer}
          saveControl={
            <CurrentTraceSaveControl
              task={task}
              activeDatasetId={activeDatasetId}
              traceKeys={visibleTraceKeys}
              metric={selection.metric}
              traceLabel={
                visibleTraceKeys.length > 1
                  ? `${visibleTraceKeys.length} visible traces`
                  : activeTraceSeries?.label ?? null
              }
              traceCount={visibleTraceKeys.length}
              defaultParameter={resolveDefaultTraceParameter(
                resolvedSelection?.family ?? selection.family,
                resolvedSelection?.outputPort ?? selection.outputPort,
                resolvedSelection?.inputPort ?? selection.inputPort,
              )}
            />
          }
          showZ0Control={showZ0Control}
          sourceIsLocked={sourceIsLocked}
          sourceOptions={sourceOptions}
          showPtcFamilyHint={showPtcFamilyHint}
          ptcFamilyLabels={ptcFamilyLabels}
          metricOptions={metricOptions}
          outputPortOptions={outputPortOptions}
          inputPortOptions={inputPortOptions}
          z0Input={z0Input}
          onZ0InputChange={setZ0Input}
          onZ0Blur={() => {
            const parsed = Number.parseFloat(z0Input);
            if (Number.isFinite(parsed) && parsed > 0) {
              explorer.setZ0(parsed);
            } else {
              setZ0Input(String(selection.z0));
            }
          }}
        />

        {parameterSweep.active && parameterSweep.axes.length > 0 ? (
          <ParameterSweepPanel
            parameterSweep={parameterSweep}
            compareAxisIndex={compareAxisIndex}
            explorer={explorer}
            explorerTestPrefix={copy.testPrefix}
            payloadSeriesCount={payload.plot.series.length}
            showComparedTraces={showComparedTraces}
            onToggleComparedTraces={() => {
              setShowComparedTraces((current) => !current);
            }}
          />
        ) : null}

        <ResultViewPanel
          viewMode={viewMode}
          payload={payload}
          visiblePlotSeries={visiblePlotSeries}
          hasSeries={hasSeries}
          xAxisTitle={xAxisTitle}
          yAxisTitle={yAxisTitle}
          resultViewDescription={resultViewDescription}
          isRefreshingSelection={explorer.isRefreshingSelection}
        />

        <ResultSourcePanel
          payload={payload}
          selection={selection}
          resolvedSelection={resolvedSelection}
          showZ0Control={showZ0Control}
        />
      </div>
    </SurfacePanel>
  );
}
