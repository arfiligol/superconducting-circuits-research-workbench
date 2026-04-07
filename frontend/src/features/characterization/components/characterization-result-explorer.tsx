"use client";

import { useMemo, type CSSProperties, type ComponentType } from "react";
import dynamic from "next/dynamic";
import { FileJson, LineChart, LoaderCircle, Rows3 } from "lucide-react";
import { useTheme } from "next-themes";

import type { UseCharacterizationResultExplorerResult } from "@/features/characterization/hooks/use-characterization-result-explorer";
import type {
  CharacterizationArtifactMemberRef,
  CharacterizationArtifactPayload,
  CharacterizationArtifactPlotSeries,
  CharacterizationArtifactRef,
  CharacterizationArtifactPayloadViewKind,
  CharacterizationResultDetail,
} from "@/features/characterization/lib/contracts";
import {
  resolveCharacterizationArtifactCompareGroups,
  resolveCharacterizationArtifactLayout,
  resolveCharacterizationArtifactPlotSeries,
  resolveCharacterizationArtifactTableColumns,
  resolveCharacterizationArtifactTableRows,
  resolveCharacterizationSingleMemberTableProjection,
} from "@/features/characterization/lib/result-explorer";
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

function formatPayloadKindLabel(value: CharacterizationArtifactPayloadViewKind) {
  switch (value) {
    case "table":
      return "Table";
    case "plot":
      return "Plot";
    case "json":
      return "JSON";
    case "text":
      return "Text";
    default:
      return value;
  }
}

function formatSourceKind(value: string) {
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

function resolveAxisLabel(
  artifact: CharacterizationArtifactRef | null,
  axisKey: string | null,
  fallback: string,
) {
  if (!axisKey) {
    return fallback;
  }

  return artifact?.axes.find((axis) => axis.axisKey === axisKey)?.label ?? axisKey;
}

function resolveMetricLabel(artifact: CharacterizationArtifactRef | null, fallback: string) {
  return artifact?.metric?.label ?? fallback;
}

function memberSummary(member: CharacterizationArtifactMemberRef | null) {
  if (!member) {
    return null;
  }

  return `${formatSourceKind(member.sourceKind)} · ${member.parameter} · ${member.traceId}`;
}

function MemberBadge({
  member,
  compareLabel,
}: Readonly<{
  member: CharacterizationArtifactMemberRef | null;
  compareLabel: string;
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <SurfaceTag tone="default">{compareLabel}</SurfaceTag>
        {member ? <SurfaceTag tone="default">{formatSourceKind(member.sourceKind)}</SurfaceTag> : null}
      </div>
      {member ? (
        <>
          <p className="mt-2 text-sm font-medium text-foreground">{member.label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{memberSummary(member)}</p>
          <p className="mt-1 text-xs text-muted-foreground">{member.provenanceSummary}</p>
        </>
      ) : null}
    </div>
  );
}

function CompareAwareTable({
  payload,
  selectedArtifact,
}: Readonly<{
  payload: CharacterizationArtifactPayload;
  selectedArtifact: CharacterizationArtifactRef | null;
}>) {
  const layout = resolveCharacterizationArtifactLayout(payload);
  const rowLabels = resolveCharacterizationArtifactTableRows(payload);
  const columnLabels = resolveCharacterizationArtifactTableColumns(payload);
  const compareGroups = resolveCharacterizationArtifactCompareGroups(payload);
  const singleMemberProjection = resolveCharacterizationSingleMemberTableProjection(payload);
  const effectiveGroups =
    compareGroups.length > 0
      ? compareGroups
      : singleMemberProjection.cells.length > 0
        ? [
            {
              compareKey: "selected-scope",
              compareLabel: "Selected scope",
              member: null,
              cells: singleMemberProjection.cells,
              mask: singleMemberProjection.mask,
              series: [],
            },
          ]
        : [];
  const rowAxisLabel = resolveAxisLabel(selectedArtifact, layout?.rowsAxis ?? null, "Rows");
  const columnAxisLabel = resolveAxisLabel(
    selectedArtifact,
    layout?.columnsAxis ?? null,
    "Columns",
  );
  const metricLabel = resolveMetricLabel(
    selectedArtifact,
    layout?.cellMetric ?? "Metric",
  );

  if (effectiveGroups.length === 0 || rowLabels.length === 0 || columnLabels.length === 0) {
    return (
      <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-5 text-sm text-muted-foreground">
        The selected preset did not expose a table payload yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-[11px]">
        <SurfaceTag tone="default">{rowAxisLabel}</SurfaceTag>
        <SurfaceTag tone="default">{columnAxisLabel}</SurfaceTag>
        <SurfaceTag tone="default">{metricLabel}</SurfaceTag>
        {layout?.compareAxis ? (
          <SurfaceTag tone="default">
            Compare {resolveAxisLabel(selectedArtifact, layout.compareAxis, layout.compareAxis)}
          </SurfaceTag>
        ) : null}
      </div>

      {effectiveGroups.length > 1 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {effectiveGroups.map((group) => (
            <div key={group.compareKey} className="space-y-3">
              <MemberBadge member={group.member} compareLabel={group.compareLabel} />
              <div className="overflow-x-auto rounded-[0.95rem] border border-border bg-background">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-card">
                    <tr className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      <th className="px-4 py-3">{rowAxisLabel}</th>
                      {columnLabels.map((column) => (
                        <th key={`${group.compareKey}-${column.label}`} className="px-4 py-3">
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rowLabels.map((row, rowIndex) => (
                      <tr key={`${group.compareKey}-${row.label}`}>
                        <td className="px-4 py-3 font-medium text-foreground">{row.label}</td>
                        {columnLabels.map((column, columnIndex) => {
                          const value = group.cells[rowIndex]?.[columnIndex] ?? null;
                          const masked = group.mask[rowIndex]?.[columnIndex] ?? value == null;
                          return (
                            <td
                              key={`${group.compareKey}-${row.label}-${column.label}`}
                              className="px-4 py-3"
                            >
                              {masked ? (
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
            </div>
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[0.95rem] border border-border bg-background">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-card">
              <tr className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                <th className="px-4 py-3">{rowAxisLabel}</th>
                {columnLabels.map((column) => (
                  <th key={column.label} className="px-4 py-3">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rowLabels.map((row, rowIndex) => (
                <tr key={row.label}>
                  <td className="px-4 py-3 font-medium text-foreground">{row.label}</td>
                  {columnLabels.map((column, columnIndex) => {
                    const value = effectiveGroups[0]?.cells[rowIndex]?.[columnIndex] ?? null;
                    const masked =
                      effectiveGroups[0]?.mask[rowIndex]?.[columnIndex] ?? value == null;
                    return (
                      <td key={`${row.label}-${column.label}`} className="px-4 py-3">
                        {masked ? (
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
      )}
    </div>
  );
}

function CompareAwarePlot({
  payload,
  selectedArtifact,
}: Readonly<{
  payload: CharacterizationArtifactPayload;
  selectedArtifact: CharacterizationArtifactRef | null;
}>) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";
  const axisColor = isDark ? "#e7edf6" : "#0f172a";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.22)" : "rgba(148, 163, 184, 0.18)";
  const lineColor = isDark ? "rgba(148, 163, 184, 0.42)" : "rgba(148, 163, 184, 0.3)";
  const palette = ["#2563eb", "#0f766e", "#b45309", "#7c3aed", "#be185d", "#0891b2"];
  const layout = resolveCharacterizationArtifactLayout(payload);
  const compareGroups = resolveCharacterizationArtifactCompareGroups(payload);
  const series = resolveCharacterizationArtifactPlotSeries(payload);
  const xAxisLabel = resolveAxisLabel(selectedArtifact, layout?.xAxis ?? null, "X");
  const yAxisLabel = resolveMetricLabel(selectedArtifact, layout?.yMetric ?? "Y");
  const compareAxisLabel = resolveAxisLabel(
    selectedArtifact,
    layout?.compareAxis ?? null,
    "Member",
  );

  const plotLayout = useMemo(
    () => ({
      title: undefined,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { t: 18, r: 260, b: 54, l: 62 },
      xaxis: {
        title: {
          text: xAxisLabel,
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
          text: yAxisLabel,
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
    [axisColor, gridColor, lineColor, xAxisLabel, yAxisLabel],
  );

  if (series.length === 0) {
    return (
      <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-5 text-sm text-muted-foreground">
        The selected preset did not expose a plot payload yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-[11px]">
        <SurfaceTag tone="default">{xAxisLabel}</SurfaceTag>
        <SurfaceTag tone="default">{yAxisLabel}</SurfaceTag>
        {layout?.seriesAxis ? (
          <SurfaceTag tone="default">
            Series {resolveAxisLabel(selectedArtifact, layout.seriesAxis, layout.seriesAxis)}
          </SurfaceTag>
        ) : null}
        {layout?.compareAxis ? <SurfaceTag tone="default">Compare {compareAxisLabel}</SurfaceTag> : null}
      </div>

      {compareGroups.length > 1 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {compareGroups.map((group) => (
            <MemberBadge
              key={group.compareKey}
              member={group.member}
              compareLabel={group.compareLabel}
            />
          ))}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-[0.95rem] border border-border/80 bg-background">
        <Plot
          data={series.map((item: CharacterizationArtifactPlotSeries, index) => ({
            type: "scatter",
            mode: "lines+markers",
            name:
              compareGroups.length > 1 && item.compareLabel
                ? `${item.compareLabel} · ${item.seriesLabel}`
                : item.seriesLabel,
            x: item.xValues,
            y: item.yValues,
            connectgaps: false,
            line: {
              color: palette[index % palette.length],
              width: 2.5,
            },
            marker: {
              color: palette[index % palette.length],
              size: 4,
            },
            hovertemplate: `${xAxisLabel}: %{x}<br>${yAxisLabel}: %{y}<extra>${
              compareGroups.length > 1 && item.compareLabel
                ? `${item.compareLabel} · ${item.seriesLabel}`
                : item.seriesLabel
            }</extra>`,
          }))}
          layout={plotLayout}
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
    </div>
  );
}

function CharacterizationStructuredPayload({
  payload,
  selectedArtifact,
}: Readonly<{
  payload: CharacterizationArtifactPayload;
  selectedArtifact: CharacterizationArtifactRef | null;
}>) {
  if (payload.viewKind === "table") {
    return <CompareAwareTable payload={payload} selectedArtifact={selectedArtifact} />;
  }

  if (payload.viewKind === "plot") {
    return <CompareAwarePlot payload={payload} selectedArtifact={selectedArtifact} />;
  }

  return (
    <pre className="overflow-x-auto rounded-[0.95rem] border border-border bg-background px-4 py-4 text-xs leading-6 text-muted-foreground">
      {JSON.stringify(payload.payload, null, 2)}
    </pre>
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
  const supportedViewModes = selectedArtifact?.querySpec?.supportedViewModes ?? [];
  const viewModeOptions = supportedViewModes.map(
    (viewMode) =>
      ({
        value: viewMode,
        label: formatPayloadKindLabel(viewMode),
      }) satisfies AppSegmentedOption,
  );
  const payloadLayout = resolveCharacterizationArtifactLayout(explorer.payload);

  return (
    <div className="space-y-4">
      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              Result Explorer
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Inspect persisted artifacts through backend-defined presets, compare groups, and axis semantics.
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
          {resultDetail.artifactRefs.map((artifact) => (
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
              <p className="mt-2 text-sm text-muted-foreground">
                {selectedArtifact.viewKind === "preset_query"
                  ? "Preset-driven artifact. Table and plot semantics come from backend query presets."
                  : "Static artifact. The payload view is fixed by the backend manifest."}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedArtifact.axes.map((axis) => (
                  <SurfaceTag key={axis.axisKey} tone="default">
                    {axis.label}
                  </SurfaceTag>
                ))}
                {selectedArtifact.metric ? (
                  <SurfaceTag tone="default">{selectedArtifact.metric.label}</SurfaceTag>
                ) : null}
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
                    description:
                      preset.compareAxis
                        ? `Compare ${preset.compareAxis}`
                        : preset.viewKind === "table"
                          ? "Backend-defined table preset"
                          : "Backend-defined plot preset",
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
                {payloadLayout?.rowsAxis ? (
                  <SurfaceTag tone="default">
                    Rows {resolveAxisLabel(selectedArtifact, payloadLayout.rowsAxis, payloadLayout.rowsAxis)}
                  </SurfaceTag>
                ) : payloadLayout?.xAxis ? (
                  <SurfaceTag tone="default">
                    X {resolveAxisLabel(selectedArtifact, payloadLayout.xAxis, payloadLayout.xAxis)}
                  </SurfaceTag>
                ) : null}
                {payloadLayout?.columnsAxis ? (
                  <SurfaceTag tone="default">
                    Columns{" "}
                    {resolveAxisLabel(
                      selectedArtifact,
                      payloadLayout.columnsAxis,
                      payloadLayout.columnsAxis,
                    )}
                  </SurfaceTag>
                ) : null}
                {payloadLayout?.seriesAxis ? (
                  <SurfaceTag tone="default">
                    Series{" "}
                    {resolveAxisLabel(
                      selectedArtifact,
                      payloadLayout.seriesAxis,
                      payloadLayout.seriesAxis,
                    )}
                  </SurfaceTag>
                ) : null}
                {payloadLayout?.compareAxis ? (
                  <SurfaceTag tone="default">
                    Compare{" "}
                    {resolveAxisLabel(
                      selectedArtifact,
                      payloadLayout.compareAxis,
                      payloadLayout.compareAxis,
                    )}
                  </SurfaceTag>
                ) : null}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {explorer.payload.viewKind === "plot" ? (
                  <LineChart className="h-4 w-4" />
                ) : explorer.payload.viewKind === "table" ? (
                  <Rows3 className="h-4 w-4" />
                ) : (
                  <FileJson className="h-4 w-4" />
                )}
                {formatPayloadKindLabel(explorer.payload.viewKind)}
              </div>
            </div>

            {explorer.payload.diagnostics.length > 0 ? (
              <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Payload Diagnostics
                </p>
                <div className="mt-3 space-y-2">
                  {explorer.payload.diagnostics.map((diagnostic) => (
                    <div
                      key={`${diagnostic.code}-${diagnostic.message}`}
                      className={cx(
                        "rounded-xl border px-3 py-3 text-sm",
                        diagnostic.blocking
                          ? "border-amber-500/25 bg-amber-500/10"
                          : "border-border bg-surface",
                      )}
                    >
                      <p className="font-medium text-foreground">{diagnostic.message}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{diagnostic.code}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <CharacterizationStructuredPayload
              payload={explorer.payload}
              selectedArtifact={selectedArtifact}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
