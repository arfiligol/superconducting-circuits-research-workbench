"use client";

import { useMemo, type CSSProperties, type ComponentType } from "react";
import dynamic from "next/dynamic";
import { FileJson, LineChart, LoaderCircle, Rows3 } from "lucide-react";
import { useTheme } from "next-themes";

import type { UseCharacterizationResultExplorerResult } from "@/features/characterization/hooks/use-characterization-result-explorer";
import type {
  CharacterizationArtifactPayload,
  CharacterizationResultDetail,
} from "@/features/characterization/lib/contracts";
import { AppInlineSelect } from "@/features/shared/components/app-select";
import {
  AppSegmentedControl,
  type AppSegmentedOption,
} from "@/features/shared/components/app-segmented-control";
import { SurfaceTag, cx } from "@/features/shared/components/surface-kit";

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

function CharacterizationPlot({
  payload,
}: Readonly<{
  payload: CharacterizationArtifactPayload;
}>) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";
  const axisColor = isDark ? "#e7edf6" : "#0f172a";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.22)" : "rgba(148, 163, 184, 0.18)";
  const lineColor = isDark ? "rgba(148, 163, 184, 0.42)" : "rgba(148, 163, 184, 0.3)";
  const palette = ["#2563eb", "#0f766e", "#b45309", "#7c3aed", "#be185d", "#0891b2"];
  const plot = payload.plot;

  const layout = useMemo(
    () => ({
      title: undefined,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { t: 18, r: 260, b: 54, l: 62 },
      xaxis: {
        title: {
          text: plot?.xAxis.label ?? "X",
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
          text: plot?.yAxis.label ?? "Y",
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
    [axisColor, gridColor, lineColor, plot?.xAxis.label, plot?.yAxis.label],
  );

  if (!plot) {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-[0.95rem] border border-border/80 bg-background">
      <Plot
        data={plot.series.map((series, index) => ({
          type: "scatter",
          mode: "lines+markers",
          name: series.label,
          x: plot.xAxis.values,
          y: series.values,
          connectgaps: false,
          line: {
            color: palette[index % palette.length],
            width: 2.5,
          },
          marker: {
            color: palette[index % palette.length],
            size: 4,
          },
          hovertemplate: `${plot.xAxis.label}: %{x}<br>${plot.yAxis.label}: %{y}<extra>${series.label}</extra>`,
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
        className="h-[380px] w-full"
        style={{ width: "100%", height: "380px" }}
        useResizeHandler
      />
    </div>
  );
}

function CharacterizationTable({
  payload,
}: Readonly<{
  payload: CharacterizationArtifactPayload;
}>) {
  if (!payload.table) {
    return null;
  }

  return (
    <div className="overflow-x-auto rounded-[0.95rem] border border-border/80 bg-background">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-card">
          <tr className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
            {payload.table.columns.map((column) => (
              <th key={column.key} className="px-4 py-3">
                <div className="space-y-1">
                  <span>{column.label}</span>
                  <span className="block text-[10px] font-medium normal-case tracking-normal text-muted-foreground">
                    {column.role.replaceAll("_", " ")}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {payload.table.rows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`}>
              {payload.table?.columns.map((column) => {
                const value = row[column.key];
                return (
                  <td key={`${rowIndex}-${column.key}`} className="px-4 py-3 align-top">
                    {value == null ? (
                      <span className="inline-flex rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-950 dark:text-amber-100">
                        Masked
                      </span>
                    ) : (
                      <span className="font-medium text-foreground">{String(value)}</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CharacterizationStructuredPayload({
  payload,
}: Readonly<{
  payload: CharacterizationArtifactPayload;
}>) {
  if (payload.viewMode === "table" && payload.table) {
    return <CharacterizationTable payload={payload} />;
  }

  if (payload.viewMode === "plot" && payload.plot) {
    return <CharacterizationPlot payload={payload} />;
  }

  if (payload.textPayload) {
    return (
      <pre className="overflow-x-auto rounded-[0.95rem] border border-border bg-background px-4 py-4 text-xs leading-6 text-muted-foreground">
        {payload.textPayload}
      </pre>
    );
  }

  if (payload.jsonPayload) {
    return (
      <pre className="overflow-x-auto rounded-[0.95rem] border border-border bg-background px-4 py-4 text-xs leading-6 text-muted-foreground">
        {JSON.stringify(payload.jsonPayload, null, 2)}
      </pre>
    );
  }

  return (
    <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-5 text-sm text-muted-foreground">
      This artifact does not expose a renderable payload for the current preset.
    </div>
  );
}

export function CharacterizationResultExplorer({
  resultDetail,
  explorer,
}: Readonly<{
  resultDetail: CharacterizationResultDetail;
  explorer: UseCharacterizationResultExplorerResult;
}>) {
  const selectedArtifact = explorer.selectedArtifact;
  const viewModeOptions = (
    selectedArtifact?.querySpec.supportedViewModes ??
    []
  ).map(
    (viewMode) =>
      ({
        value: viewMode,
        label:
          viewMode === "table"
            ? "Table"
            : viewMode === "plot"
              ? "Plot"
              : viewMode === "json"
                ? "JSON"
                : "Text",
      }) satisfies AppSegmentedOption,
  );

  return (
    <div className="space-y-4">
      {resultDetail.inputCollectionPayload ? (
        <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                Input Collection
              </p>
              <p className="mt-2 text-sm text-foreground">
                {resultDetail.inputCollectionPayload.groupingSummary}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <SurfaceTag tone="default">
                {resultDetail.inputCollectionPayload.collectionCount} collections
              </SurfaceTag>
              <SurfaceTag
                tone={
                  resultDetail.inputCollectionPayload.readinessState === "ready"
                    ? "success"
                    : resultDetail.inputCollectionPayload.readinessState === "blocked"
                      ? "warning"
                      : "default"
                }
              >
                {resultDetail.inputCollectionPayload.readinessState.replaceAll("_", " ")}
              </SurfaceTag>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {resultDetail.inputCollectionPayload.availableSweepAxes.map((axis) => (
              <SurfaceTag key={axis} tone="default">
                {axis}
              </SurfaceTag>
            ))}
            {resultDetail.inputCollectionPayload.sharedAxes.map((axis) => (
              <SurfaceTag key={`${axis.family}-${axis.key}`} tone="default">
                {axis.label}
              </SurfaceTag>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              Result Explorer
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Inspect persisted artifacts through backend-defined presets and axis semantics.
            </p>
          </div>
          {selectedArtifact ? (
            <div className="flex flex-wrap gap-2 text-[11px]">
              <SurfaceTag tone="default">{selectedArtifact.category}</SurfaceTag>
              <SurfaceTag tone="default">{selectedArtifact.payloadFormat}</SurfaceTag>
              <SurfaceTag tone="default">{selectedArtifact.artifactId}</SurfaceTag>
            </div>
          ) : null}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {resultDetail.artifactManifest.map((artifact) => (
            <button
              key={artifact.artifactId}
              type="button"
              onClick={() => {
                explorer.setSelectedArtifactId(artifact.artifactId);
              }}
              className={cx(
                "rounded-full border px-3.5 py-2 text-sm font-medium transition",
                explorer.selectedArtifactId === artifact.artifactId
                  ? "border-primary/35 bg-primary/10 text-foreground"
                  : "border-border bg-background text-muted-foreground hover:border-primary/30 hover:text-foreground",
              )}
            >
              {artifact.title}
            </button>
          ))}
        </div>

        {selectedArtifact ? (
          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
              <p className="text-sm font-semibold text-foreground">{selectedArtifact.title}</p>
              <p className="mt-2 text-sm text-muted-foreground">{selectedArtifact.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedArtifact.axisSummary.inputAxes.map((axis) => (
                  <SurfaceTag key={`input-${axis.key}`} tone="default">
                    {axis.label}
                  </SurfaceTag>
                ))}
                {selectedArtifact.axisSummary.derivedAxes.map((axis) => (
                  <SurfaceTag key={`derived-${axis.key}`} tone="default">
                    {axis.label}
                  </SurfaceTag>
                ))}
                {selectedArtifact.axisSummary.metrics.map((axis) => (
                  <SurfaceTag key={`metric-${axis.key}`} tone="default">
                    {axis.label}
                  </SurfaceTag>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)]">
              {viewModeOptions.length > 0 && explorer.resolvedViewMode ? (
                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                  <p className="mb-3 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    View Mode
                  </p>
                  <AppSegmentedControl
                    value={explorer.resolvedViewMode}
                    onChange={explorer.setSelectedViewMode}
                    options={viewModeOptions}
                    ariaLabel="Characterization artifact view mode"
                  />
                </div>
              ) : null}

              {explorer.availablePresetViews.length > 0 ? (
                <AppInlineSelect
                  ariaLabel="Characterization artifact preset"
                  value={explorer.resolvedPresetId ?? ""}
                  onChange={explorer.setSelectedPresetId}
                  options={explorer.availablePresetViews.map((preset) => ({
                    value: preset.presetId,
                    label: preset.label,
                    description: preset.description,
                  }))}
                  className="rounded-[0.95rem] border border-border bg-background px-4 py-4"
                />
              ) : null}
            </div>
          </div>
        ) : null}

        {explorer.isPayloadLoading ? (
          <div className="mt-4 flex items-center gap-3 rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
            <LoaderCircle className="h-4 w-4 animate-spin" />
            Loading artifact payload…
          </div>
        ) : null}

        {explorer.payloadError ? (
          <div className="mt-4 rounded-[0.95rem] border border-amber-500/35 bg-amber-500/10 px-4 py-4 text-sm text-amber-950 dark:text-amber-100">
            Could not load the selected artifact payload. {explorer.payloadError.message}
          </div>
        ) : null}

        {explorer.payload ? (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[0.95rem] border border-border bg-background px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <SurfaceTag tone="default">
                  {explorer.payload.axisContract.rowAxis
                    ? `Rows ${explorer.payload.axisContract.rowAxis}`
                    : explorer.payload.axisContract.xAxis
                      ? `X ${explorer.payload.axisContract.xAxis}`
                      : "Preset view"}
                </SurfaceTag>
                {explorer.payload.axisContract.columnAxis ? (
                  <SurfaceTag tone="default">
                    Columns {explorer.payload.axisContract.columnAxis}
                  </SurfaceTag>
                ) : null}
                {explorer.payload.axisContract.seriesAxis ? (
                  <SurfaceTag tone="default">
                    Series {explorer.payload.axisContract.seriesAxis}
                  </SurfaceTag>
                ) : null}
                {explorer.payload.axisContract.metric ? (
                  <SurfaceTag tone="default">
                    Metric {explorer.payload.axisContract.metric}
                  </SurfaceTag>
                ) : null}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {explorer.payload.viewMode === "plot" ? (
                  <LineChart className="h-4 w-4" />
                ) : explorer.payload.viewMode === "table" ? (
                  <Rows3 className="h-4 w-4" />
                ) : (
                  <FileJson className="h-4 w-4" />
                )}
                {explorer.payload.viewMode}
              </div>
            </div>

            {explorer.payload.warnings.length > 0 ? (
              <div className="rounded-[0.95rem] border border-amber-500/35 bg-amber-500/10 px-4 py-4">
                <p className="text-sm font-semibold text-amber-950 dark:text-amber-100">
                  Payload Warnings
                </p>
                <ul className="mt-2 space-y-2 text-sm text-amber-950/90 dark:text-amber-100/90">
                  {explorer.payload.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <CharacterizationStructuredPayload payload={explorer.payload} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
