"use client";

import { useEffect, useMemo, useState, type CSSProperties, type ComponentType } from "react";
import dynamic from "next/dynamic";
import { DatabaseZap, LineChart, Rows3 } from "lucide-react";
import { useTheme } from "next-themes";

import { CurrentTraceSaveControl } from "@/features/simulation/components/current-trace-save-control";
import { useSimulationResultExplorer } from "@/features/simulation/hooks/use-simulation-result-explorer";
import { AppNumberInput } from "@/features/shared/components/app-number-input";
import {
  AppSegmentedControl,
  type AppSegmentedOption,
} from "@/features/shared/components/app-segmented-control";
import {
  AppInlineSelect,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
import { SurfacePanel, SurfaceTag } from "@/features/shared/components/surface-kit";
import type { TaskDetail } from "@/lib/api/tasks";

type PlotComponentProps = Readonly<{
  data: readonly Record<string, unknown>[];
  layout: Record<string, unknown>;
  config: Record<string, unknown>;
  className?: string;
  style?: CSSProperties;
  useResizeHandler?: boolean;
}>;

const Plot = dynamic<PlotComponentProps>(
  () =>
    import("react-plotly.js").then(
      (module) => module.default as ComponentType<PlotComponentProps>,
    ),
  {
    ssr: false,
  },
);

type SimulationResultExplorerProps = Readonly<{
  task: TaskDetail;
  activeDatasetId: string | null;
}>;

type ExplorerViewMode = "plot" | "table";

function formatAxisTitle(label: string, unit: string) {
  return unit ? `${label} (${unit})` : label;
}

function ExplorerField({
  label,
  children,
  detail,
}: Readonly<{
  label: string;
  children: React.ReactNode;
  detail?: string;
}>) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </p>
        {detail ? <p className="text-xs text-muted-foreground">{detail}</p> : null}
      </div>
      {children}
    </div>
  );
}

function SimulationResultPlot({
  xValues,
  series,
  xAxisTitle,
  yAxisTitle,
}: Readonly<{
  xValues: readonly number[];
  series: readonly Readonly<{
    seriesId: string;
    label: string;
    values: readonly number[];
  }>[];
  xAxisTitle: string;
  yAxisTitle: string;
}>) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";
  const axisColor = isDark ? "#e7edf6" : "#0f172a";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.22)" : "rgba(148, 163, 184, 0.18)";
  const lineColor = isDark ? "rgba(148, 163, 184, 0.42)" : "rgba(148, 163, 184, 0.3)";
  const palette = ["#2563eb", "#0f766e", "#b45309", "#7c3aed"];
  const layout = useMemo(
    () => ({
      title: undefined,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { t: 18, r: 18, b: 54, l: 62 },
      xaxis: {
        title: {
          text: xAxisTitle,
          standoff: 16,
          font: { color: axisColor },
        },
        tickfont: {
          color: axisColor,
        },
        zeroline: false,
        gridcolor: gridColor,
        linecolor: lineColor,
        tickcolor: lineColor,
        automargin: true,
      },
      yaxis: {
        title: {
          text: yAxisTitle,
          standoff: 14,
          font: { color: axisColor },
        },
        tickfont: {
          color: axisColor,
        },
        zeroline: false,
        gridcolor: gridColor,
        linecolor: lineColor,
        tickcolor: lineColor,
        automargin: true,
      },
      legend: {
        orientation: "h",
        y: 1.14,
        x: 0,
        font: { color: axisColor },
      },
      font: {
        color: axisColor,
      },
    }),
    [axisColor, gridColor, lineColor, xAxisTitle, yAxisTitle],
  );

  return (
    <div className="overflow-hidden rounded-[0.95rem] border border-border/80 bg-background">
      <Plot
        data={series.map((entry, index) => ({
          type: "scatter",
          mode: "lines+markers",
          name: entry.label,
          x: xValues,
          y: entry.values,
          line: {
            color: palette[index % palette.length],
            width: 2.5,
          },
          marker: {
            color: palette[index % palette.length],
            size: 4,
          },
          hovertemplate: `${xAxisTitle}: %{x}<br>${yAxisTitle}: %{y}<extra>${entry.label}</extra>`,
        }))}
        layout={layout}
        config={{
          displaylogo: false,
          responsive: true,
          modeBarButtonsToRemove: [
            "select2d",
            "lasso2d",
            "autoScale2d",
            "toggleSpikelines",
          ],
        }}
        className="h-[360px] w-full"
        style={{ width: "100%", height: "360px" }}
        useResizeHandler
      />
    </div>
  );
}

export function SimulationResultExplorer({
  task,
  activeDatasetId,
}: SimulationResultExplorerProps) {
  const [viewMode, setViewMode] = useState<ExplorerViewMode>("plot");
  const [z0Input, setZ0Input] = useState("50");
  const explorer = useSimulationResultExplorer(task.taskId, true);
  const explorerTitle =
    task.kind === "post_processing"
      ? "Post Processing Result Explorer"
      : "Simulation Result Explorer";
  const explorerDescription =
    task.kind === "post_processing"
      ? "Inspect saved post-processing outputs with family, source, metric, and port selectors."
      : "Inspect saved simulation outputs with family, source, metric, and port selectors.";
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
  const selection = explorer.selection;
  const familyOptions = payload?.bootstrap.families ?? [];
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
      payload?.bootstrap.traceSelector.outputPorts.map((port) => ({
        value: String(port.port),
        label: port.label,
      })) ?? [],
    [payload],
  );
  const inputPortOptions = useMemo<readonly AppSelectOption[]>(
    () =>
      payload?.bootstrap.traceSelector.inputPorts.map((port) => ({
        value: String(port.port),
        label: port.label,
      })) ?? [],
    [payload],
  );
  const xAxisTitle = payload
    ? formatAxisTitle(payload.plot.xAxis.label, payload.plot.xAxis.unit)
    : "Frequency";
  const yAxisTitle = payload
    ? formatAxisTitle(payload.plot.yAxis.label, payload.plot.yAxis.unit)
    : "Result";
  const hasSeries = (payload?.plot.series.length ?? 0) > 0;
  const showZ0Control = selection?.family !== "s_matrix";
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

  if (explorer.isLoading || (!payload && !explorer.error)) {
    return (
      <SurfacePanel
        title={explorerTitle}
        description={
          task.kind === "post_processing"
            ? "Loading post-processing result controls and plot data."
            : "Loading simulation result controls and plot data."
        }
      >
        <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
          Loading the persisted explorer surface for task #{task.taskId}.
        </div>
      </SurfacePanel>
    );
  }

  if (explorer.error || !payload || !selection || !explorer.selectedFamily) {
    return (
      <SurfacePanel
        title={explorerTitle}
        description={
          task.kind === "post_processing"
            ? "The post-processing result explorer is unavailable right now."
            : "The simulation result explorer is unavailable right now."
        }
      >
        <div className="rounded-[0.95rem] border border-rose-500/35 bg-rose-50/90 px-4 py-4 text-sm text-rose-950 dark:border-rose-500/45 dark:bg-rose-950/40 dark:text-rose-100">
          Unable to load the {task.kind === "post_processing" ? "post-processing" : "simulation"} result explorer right now.{" "}
          {explorer.error instanceof Error ? explorer.error.message : "Unknown explorer error."}
        </div>
      </SurfacePanel>
    );
  }

  return (
    <SurfacePanel
      title={explorerTitle}
      description={explorerDescription}
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
        <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
          <div className="space-y-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0 xl:flex-1">
                <AppSegmentedControl
                  value={selection.family}
                  onChange={explorer.setFamily}
                  options={familySegmentOptions}
                  ariaLabel="Simulation result family"
                />
              </div>
              <CurrentTraceSaveControl
                task={task}
                activeDatasetId={activeDatasetId}
                traceKey={payload.selection.traceKey}
                traceLabel={payload.plot.series[0]?.label ?? null}
              />
            </div>

            <div
              className={
                showZ0Control
                  ? "grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,0.74fr)_minmax(0,1.08fr)_minmax(0,0.76fr)_minmax(0,0.76fr)_minmax(0,0.54fr)]"
                  : "grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.2fr)_minmax(0,0.86fr)_minmax(0,0.86fr)]"
              }
            >
              <ExplorerField label="Source">
                <div className="space-y-2">
                  {sourceIsLocked ? (
                    <div className="min-h-11 rounded-[1rem] border border-border/85 bg-surface/95 px-4 py-3 text-sm font-medium text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_8px_24px_rgba(15,23,42,0.06)]">
                      {sourceOptions[0]?.label ?? selection.source.toUpperCase()}
                    </div>
                  ) : (
                    <AppInlineSelect
                      ariaLabel="Simulation result source"
                      value={selection.source}
                      onChange={explorer.setSource}
                      options={sourceOptions}
                    />
                  )}
                  {showPtcFamilyHint ? (
                    <p className="text-xs leading-5 text-muted-foreground">
                      PTC results appear when you switch to {ptcFamilyLabels.join(" or ")}.
                    </p>
                  ) : null}
                </div>
              </ExplorerField>
              <ExplorerField label="Metric">
                <AppInlineSelect
                  ariaLabel="Simulation result metric"
                  value={selection.metric}
                  onChange={explorer.setMetric}
                  options={metricOptions}
                  valueClassName="text-[0.84rem] sm:text-[0.9rem]"
                />
              </ExplorerField>
              <ExplorerField label="Output">
                <AppInlineSelect
                  ariaLabel="Simulation result output port"
                  value={String(selection.outputPort)}
                  onChange={(nextValue) => {
                    explorer.setOutputPort(Number.parseInt(nextValue, 10));
                  }}
                  options={outputPortOptions}
                />
              </ExplorerField>
              <ExplorerField label="Input">
                <AppInlineSelect
                  ariaLabel="Simulation result input port"
                  value={String(selection.inputPort)}
                  onChange={(nextValue) => {
                    explorer.setInputPort(Number.parseInt(nextValue, 10));
                  }}
                  options={inputPortOptions}
                />
              </ExplorerField>
              {showZ0Control ? (
                <ExplorerField label="Z0">
                  <AppNumberInput
                    min="1"
                    step="0.1"
                    value={z0Input}
                    wheelBehavior="adjust"
                    onChange={(event) => {
                      setZ0Input(event.target.value);
                    }}
                    onBlur={() => {
                      const parsed = Number.parseFloat(z0Input);
                      if (Number.isFinite(parsed) && parsed > 0) {
                        explorer.setZ0(parsed);
                      } else {
                        setZ0Input(String(selection.z0));
                      }
                    }}
                    className="min-h-11 rounded-[1rem] border-border/85 bg-surface/95 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_8px_24px_rgba(15,23,42,0.06)] focus:ring-primary/20"
                  />
                </ExplorerField>
              ) : null}
            </div>
          </div>
        </div>

        <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Result View
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                {payload.plot.series[0]?.label ?? "Backend plot selection"} updates as soon as the
                family, source, metric, port, or Z0 selection changes.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {viewMode === "plot" ? (
                <LineChart className="h-4 w-4" />
              ) : (
                <Rows3 className="h-4 w-4" />
              )}
              {viewMode === "plot" ? "Plot view" : "Table view"}
            </div>
          </div>

          <div className="mt-4">
            {hasSeries ? (
              viewMode === "plot" ? (
                <SimulationResultPlot
                  xValues={payload.plot.xAxis.values}
                  series={payload.plot.series}
                  xAxisTitle={xAxisTitle}
                  yAxisTitle={yAxisTitle}
                />
              ) : (
                <div className="overflow-hidden rounded-lg border border-border/80">
                  <table className="min-w-full divide-y divide-border text-sm">
                    <thead className="bg-card">
                      <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                        <th className="px-4 py-3">{xAxisTitle}</th>
                        {payload.plot.series.map((series) => (
                          <th key={series.seriesId} className="px-4 py-3">
                            {series.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border bg-surface">
                      {payload.plot.xAxis.values.map((xValue, index) => (
                        <tr key={`${xValue}-${index}`}>
                          <td className="px-4 py-3 text-muted-foreground">{xValue}</td>
                          {payload.plot.series.map((series) => (
                            <td
                              key={`${series.seriesId}-${index}`}
                              className="px-4 py-3 font-medium text-foreground"
                            >
                              {series.values[index] ?? "--"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : (
              <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-5 text-sm text-muted-foreground">
                The explorer did not return any plottable series for the current result selection.
              </div>
            )}
          </div>

          <div className="mt-4 rounded-[0.95rem] border border-border/80 bg-card px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
              <div>
                <span className="text-muted-foreground">X Axis</span>
                <span className="ml-2 font-medium text-foreground">{xAxisTitle}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Y Axis</span>
                <span className="ml-2 font-medium text-foreground">{yAxisTitle}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Points</span>
                <span className="ml-2 font-medium text-foreground">
                  {payload.plot.xAxis.values.length}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Result Source
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                This view is attached to the saved result for task #{payload.taskId}.
              </p>
            </div>
            <DatabaseZap className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
            <SurfaceTag tone="primary">
              {payload.runtimeMode === "local" ? "Local mode" : "Online mode"}
            </SurfaceTag>
            <SurfaceTag tone={payload.resultBasis.tracePayloadAvailable ? "success" : "default"}>
              {payload.resultBasis.tracePayloadAvailable
                ? "Trace payload attached"
                : "Trace payload pending"}
            </SurfaceTag>
            <SurfaceTag tone="default">Trace batch {payload.resultBasis.traceBatchId ?? "--"}</SurfaceTag>
            {payload.resultBasis.primaryResultHandleId ? (
              <SurfaceTag tone="default">Handle {payload.resultBasis.primaryResultHandleId}</SurfaceTag>
            ) : null}
          </div>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
            <div>
              <span className="text-muted-foreground">Selection</span>
              <span className="ml-2 font-medium text-foreground">
                {selection.source.toUpperCase()} ·{" "}
                {payload.selection.outputPortLabel ?? `Port ${selection.outputPort}`} to{" "}
                {payload.selection.inputPortLabel ?? `Port ${selection.inputPort}`}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Mode</span>
              <span className="ml-2 font-medium text-foreground">
                {payload.selection.outputMode ?? "mode_0"}
              </span>
            </div>
            {!showZ0Control ? (
              <p className="text-xs leading-5 text-muted-foreground">
                Z0 only applies to Y/Z derived explorer families.
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </SurfacePanel>
  );
}
