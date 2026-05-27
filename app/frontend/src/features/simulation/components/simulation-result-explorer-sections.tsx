"use client";

import { useMemo, type CSSProperties, type ComponentType, type ReactNode } from "react";
import dynamic from "next/dynamic";
import { DatabaseZap, LineChart, LoaderCircle, Rows3 } from "lucide-react";
import { useTheme } from "next-themes";

import { AppNumberInput } from "@/features/shared/components/app-number-input";
import {
  AppInlineSelect,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
import {
  AppSegmentedControl,
  type AppSegmentedOption,
} from "@/features/shared/components/app-segmented-control";
import { SurfaceTag, cx } from "@/features/shared/components/surface-kit";
import type { SimulationResultExplorerPayload } from "@/lib/api/tasks";

import type { EditableExplorerSelection } from "../lib/simulation-result-explorer-state";

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

function formatSweepValueLabel(value: number, unit: string | null) {
  const compactValue = Number.isInteger(value)
    ? String(value)
    : value.toFixed(6).replace(/0+$/u, "").replace(/\.$/u, "");
  return unit ? `${compactValue} ${unit}` : compactValue;
}

function ExplorerField({
  label,
  children,
  detail,
}: Readonly<{
  label: string;
  children: ReactNode;
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
  const legendOnSide = series.length > 1;
  const layout = useMemo(
    () => ({
      title: undefined,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { t: 18, r: legendOnSide ? 260 : 18, b: 54, l: 62 },
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
        orientation: "v",
        y: 1,
        x: 1.02,
        yanchor: "top",
        xanchor: "left",
        font: { color: axisColor },
      },
      font: {
        color: axisColor,
      },
    }),
    [axisColor, gridColor, legendOnSide, lineColor, xAxisTitle, yAxisTitle],
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

type ExplorerSelectionHandlers = Readonly<{
  setFamily: (value: string) => void;
  setSource: (value: string) => void;
  setMetric: (value: string) => void;
  setOutputPort: (value: number) => void;
  setInputPort: (value: number) => void;
  setCompareAxis: (value: number) => void;
  setSweepValue: (axisIndex: number, valueIndex: number) => void;
}>;

export function ExplorerControlPanel({
  selection,
  familySegmentOptions,
  explorer,
  saveControl,
  showZ0Control,
  sourceIsLocked,
  sourceOptions,
  showPtcFamilyHint,
  ptcFamilyLabels,
  metricOptions,
  outputPortOptions,
  inputPortOptions,
  z0Input,
  onZ0InputChange,
  onZ0Blur,
}: Readonly<{
  selection: EditableExplorerSelection;
  familySegmentOptions: readonly AppSegmentedOption[];
  explorer: ExplorerSelectionHandlers;
  saveControl: ReactNode;
  showZ0Control: boolean;
  sourceIsLocked: boolean;
  sourceOptions: readonly AppSelectOption[];
  showPtcFamilyHint: boolean;
  ptcFamilyLabels: readonly string[];
  metricOptions: readonly AppSelectOption[];
  outputPortOptions: readonly AppSelectOption[];
  inputPortOptions: readonly AppSelectOption[];
  z0Input: string;
  onZ0InputChange: (value: string) => void;
  onZ0Blur: () => void;
}>) {
  return (
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
          {saveControl}
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
                  onZ0InputChange(event.target.value);
                }}
                onBlur={onZ0Blur}
                className="min-h-11 rounded-[1rem] border-border/85 bg-surface/95 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_8px_24px_rgba(15,23,42,0.06)] focus:ring-primary/20"
              />
            </ExplorerField>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function ParameterSweepPanel({
  parameterSweep,
  compareAxisIndex,
  explorer,
  explorerTestPrefix,
  payloadSeriesCount,
  showComparedTraces,
  onToggleComparedTraces,
}: Readonly<{
  parameterSweep: SimulationResultExplorerPayload["bootstrap"]["parameterSweep"];
  compareAxisIndex: number | null;
  explorer: ExplorerSelectionHandlers;
  explorerTestPrefix: string;
  payloadSeriesCount: number;
  showComparedTraces: boolean;
  onToggleComparedTraces: () => void;
}>) {
  const compareAxis =
    compareAxisIndex !== null && compareAxisIndex < parameterSweep.axes.length
      ? parameterSweep.axes[compareAxisIndex]
      : null;
  const fixedSweepAxes = parameterSweep.axes.filter(
    (_axis, axisIndex) => axisIndex !== compareAxisIndex,
  );

  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Parameter Sweep
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {parameterSweep.axes.length === 1
              ? `Single-axis sweep results show every ${compareAxis?.label ?? "sweep"} trace. Choose the active trace or focus a single trace when you want a less crowded plot.`
              : "Choose a compare axis to draw multiple traces, then fix the remaining sweep dimensions to single values."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SurfaceTag tone="default">
            {payloadSeriesCount > 0 ? `${payloadSeriesCount} traces` : `${parameterSweep.pointCount} total points`}
          </SurfaceTag>
          <SurfaceTag tone="default">{parameterSweep.pointCount} total points</SurfaceTag>
        </div>
      </div>

      <div
        className={cx(
          "mt-4 grid gap-4",
          fixedSweepAxes.length <= 1
            ? "md:grid-cols-1 xl:grid-cols-3"
            : fixedSweepAxes.length === 2
              ? "md:grid-cols-2 xl:grid-cols-4"
              : "md:grid-cols-2 xl:grid-cols-5",
        )}
      >
        {parameterSweep.axes.length > 1 ? (
          <ExplorerField label="Compare Axis">
            <AppInlineSelect
              ariaLabel="Simulation result compare axis"
              testId={`${explorerTestPrefix}-result-compare-axis`}
              value={String(compareAxisIndex ?? 0)}
              onChange={(nextValue) => {
                explorer.setCompareAxis(Number.parseInt(nextValue, 10));
              }}
              options={parameterSweep.axes.map((axis, axisIndex) => ({
                value: String(axisIndex),
                label: axis.label,
                description: axis.unit ? `Unit · ${axis.unit}` : undefined,
              }))}
            />
          </ExplorerField>
        ) : null}

        {compareAxis ? (
          <ExplorerField
            label="Active Trace"
            detail={compareAxis.unit ? `Unit · ${compareAxis.unit}` : undefined}
          >
            <AppInlineSelect
              ariaLabel={`${compareAxis.label} active trace`}
              testId={`${explorerTestPrefix}-result-active-trace`}
              value={String(compareAxis.selectedValueIndex)}
              onChange={(nextValue) => {
                explorer.setSweepValue(compareAxisIndex ?? 0, Number.parseInt(nextValue, 10));
              }}
              options={compareAxis.values.map((value, valueIndex) => ({
                value: String(valueIndex),
                label: formatSweepValueLabel(value, compareAxis.unit),
              }))}
            />
          </ExplorerField>
        ) : null}

        {parameterSweep.axes.map((axis, axisIndex) => {
          if (axisIndex === compareAxisIndex) {
            return null;
          }

          return (
            <ExplorerField
              key={`${axis.parameter}-${axisIndex}`}
              label={axis.label}
              detail={axis.unit ? `Unit · ${axis.unit}` : undefined}
            >
              <AppInlineSelect
                ariaLabel={`${axis.label} sweep selection`}
                testId={`${explorerTestPrefix}-result-sweep-axis-${axisIndex}`}
                value={String(axis.selectedValueIndex)}
                onChange={(nextValue) => {
                  explorer.setSweepValue(axisIndex, Number.parseInt(nextValue, 10));
                }}
                options={axis.values.map((value, valueIndex) => ({
                  value: String(valueIndex),
                  label: formatSweepValueLabel(value, axis.unit),
                }))}
              />
            </ExplorerField>
          );
        })}

        {compareAxis && payloadSeriesCount > 1 ? (
          <ExplorerField label="Trace Visibility">
            <button
              type="button"
              className="inline-flex min-h-11 cursor-pointer items-center justify-center rounded-[1rem] border border-border/85 bg-surface/95 px-4 py-3 text-sm font-medium text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_8px_24px_rgba(15,23,42,0.06)] transition hover:border-primary/35 hover:text-primary"
              onClick={onToggleComparedTraces}
            >
              {showComparedTraces ? "Focus active trace" : "Show all traces"}
            </button>
          </ExplorerField>
        ) : null}
      </div>
    </div>
  );
}

export function ResultViewPanel({
  viewMode,
  payload,
  visiblePlotSeries,
  hasSeries,
  xAxisTitle,
  yAxisTitle,
  resultViewDescription,
  isRefreshingSelection,
}: Readonly<{
  viewMode: "plot" | "table";
  payload: SimulationResultExplorerPayload;
  visiblePlotSeries: SimulationResultExplorerPayload["plot"]["series"];
  hasSeries: boolean;
  xAxisTitle: string;
  yAxisTitle: string;
  resultViewDescription: string;
  isRefreshingSelection: boolean;
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Result View
          </p>
          <p className="mt-2 text-sm text-muted-foreground">{resultViewDescription}</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {viewMode === "plot" ? <LineChart className="h-4 w-4" /> : <Rows3 className="h-4 w-4" />}
          {viewMode === "plot" ? "Plot view" : "Table view"}
        </div>
      </div>

      {isRefreshingSelection ? (
        <div
          role="status"
          aria-live="polite"
          className="mt-4 flex items-center gap-3 rounded-[0.95rem] border border-primary/25 bg-primary/10 px-4 py-3 text-sm text-foreground/80"
        >
          <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
          <span>
            Refreshing explorer selection while keeping the previous full-resolution view visible.
          </span>
        </div>
      ) : null}

      <div className="mt-4">
        {hasSeries ? (
          viewMode === "plot" ? (
            <SimulationResultPlot
              xValues={payload.plot.xAxis.values}
              series={visiblePlotSeries}
              xAxisTitle={xAxisTitle}
              yAxisTitle={yAxisTitle}
            />
          ) : (
            <div className="overflow-hidden rounded-lg border border-border/80">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-card">
                  <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                    <th className="px-4 py-3">{xAxisTitle}</th>
                    {visiblePlotSeries.map((series) => (
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
                      {visiblePlotSeries.map((series) => (
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
  );
}

export function ResultSourcePanel({
  payload,
  selection,
  resolvedSelection,
  showZ0Control,
}: Readonly<{
  payload: SimulationResultExplorerPayload;
  selection: EditableExplorerSelection;
  resolvedSelection: EditableExplorerSelection | null;
  showZ0Control: boolean;
}>) {
  return (
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
          {payload.resultBasis.tracePayloadAvailable ? "Trace payload attached" : "Trace payload pending"}
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
            {(resolvedSelection?.source ?? selection.source).toUpperCase()} ·{" "}
            {payload.selection.outputPortLabel ??
              `Port ${resolvedSelection?.outputPort ?? selection.outputPort}`}{" "}
            to{" "}
            {payload.selection.inputPortLabel ??
              `Port ${resolvedSelection?.inputPort ?? selection.inputPort}`}
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
  );
}
