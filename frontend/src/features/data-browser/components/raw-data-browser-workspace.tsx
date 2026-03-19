"use client";

import { useDeferredValue, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { TracePreviewPlot } from "@/features/data-browser/components/trace-preview-plot";
import { useRawDataBrowserData } from "@/features/data-browser/hooks/use-raw-data-browser-data";
import {
  humanizeTraceLabel,
  resolveTracePreviewSemantics,
} from "@/features/data-browser/lib/trace-preview";
import { AppInlineSelect } from "@/features/shared/components/app-select";
import { AppSegmentedControl } from "@/features/shared/components/app-segmented-control";
import { SurfaceHeader, SurfacePanel, SurfaceTag, cx } from "@/features/shared/components/surface-kit";

function readinessTone(value: "ready" | "inspect_only" | "blocked") {
  if (value === "ready") {
    return "success" as const;
  }
  if (value === "inspect_only") {
    return "primary" as const;
  }
  return "warning" as const;
}

function formatCoverage(coverage: Record<string, number>) {
  const entries = Object.entries(coverage);
  if (entries.length === 0) {
    return "No source coverage";
  }
  return entries.map(([key, value]) => `${key}: ${value}`).join(" · ");
}

function formatTraceValue(value: string) {
  return humanizeTraceLabel(value) || value;
}

function formatTraceSource(value: string) {
  switch (value) {
    case "layout_simulation":
      return "Layout sim";
    case "circuit_simulation":
      return "Circuit sim";
    default:
      return formatTraceValue(value);
  }
}

function resolvePreviewPoints(points: unknown) {
  if (!Array.isArray(points)) {
    return [];
  }

  return points.filter(
    (point): point is number[] =>
      Array.isArray(point) &&
      point.length >= 2 &&
      typeof point[0] === "number" &&
      Number.isFinite(point[0]) &&
      typeof point[1] === "number" &&
      Number.isFinite(point[1]),
  );
}

function SearchField({
  label,
  placeholder,
  value,
  onChange,
}: Readonly<{
  label: string;
  placeholder: string;
  value: string;
  onChange: (nextValue: string) => void;
}>) {
  return (
    <label className="block rounded-[1rem] border border-border bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
      <span className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
        <Search className="h-3.5 w-3.5" />
        {label}
      </span>
      <div className="flex items-center gap-3 rounded-[0.85rem] border border-border/80 bg-background px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          placeholder={placeholder}
        />
      </div>
    </label>
  );
}

function TraceFilterSelect({
  label,
  value,
  onChange,
  options,
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
}>) {
  return (
    <div className="min-w-0">
      <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <AppInlineSelect
        ariaLabel={label}
        value={value}
        onChange={onChange}
        options={options.map((option) => ({
          value: option,
          label: option ? option.replaceAll("_", " ") : `All ${label.toLowerCase()}`,
        }))}
        placeholder={`All ${label.toLowerCase()}`}
      />
    </div>
  );
}

export function RawDataBrowserWorkspace() {
  const browser = useRawDataBrowserData();
  const deferredDesignSearch = useDeferredValue(browser.designSearch);
  const deferredTraceSearch = useDeferredValue(browser.filters.search);
  const [previewMode, setPreviewMode] = useState<"plot" | "table">("plot");
  const selectedDesign = browser.designs.find((row) => row.design_id === browser.selectedDesignId) ?? null;
  const selectedTraceSummary =
    browser.traces.find((row) => row.trace_id === browser.selectedTraceId) ?? null;
  const previewPoints = useMemo(
    () => resolvePreviewPoints(browser.traceDetail?.preview_payload.points),
    [browser.traceDetail?.preview_payload.points],
  );
  const previewSeries = useMemo(() => {
    const x = previewPoints.map((point) => point[0]);
    const y = previewPoints.map((point) => point[1]);

    return {
      x,
      y,
      isPlotReady: x.length > 0 && x.length === y.length,
    };
  }, [previewPoints]);
  const previewSemantics = useMemo(
    () =>
      resolveTracePreviewSemantics({
        axes: browser.traceDetail?.axes ?? [],
        traceSummary: selectedTraceSummary,
        fallbackSeriesLabel: browser.traceDetail?.trace_id ?? null,
      }),
    [browser.traceDetail?.axes, browser.traceDetail?.trace_id, selectedTraceSummary],
  );
  const previewPointCount = previewPoints.length;
  const hasSampledPreview =
    typeof previewSemantics.xAxisPointCount === "number" &&
    previewPointCount > 0 &&
    previewPointCount < previewSemantics.xAxisPointCount;
  const previewPointCountLabel = hasSampledPreview
    ? `${previewPointCount} of ${previewSemantics.xAxisPointCount} points`
    : previewSemantics.xAxisPointCountLabel;

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw Data Browser"
        title="Raw Data"
        description="Choose a design, narrow the trace list, and open one preview at a time."
      />

      <SurfacePanel
        title="Design Scopes"
        description="Start with a design here, then move straight into trace selection and preview."
      >
        {browser.designsError ? (
          <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
            Unable to load design scopes. {browser.designsError.message}
          </div>
        ) : null}
        <SearchField
          label="Search Design"
          placeholder="Search design name or id"
          value={browser.designSearch}
          onChange={browser.setDesignSearch}
        />
        {browser.isDesignsLoading ? (
          <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            Loading designs for {deferredDesignSearch || "the active dataset"}...
          </div>
        ) : browser.designs.length > 0 ? (
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 xl:grid-cols-2">
              {browser.designs.map((design) => (
                <button
                  key={design.design_id}
                  type="button"
                  onClick={() => {
                    browser.setSelectedDesignId(design.design_id);
                  }}
                  className={cx(
                    "w-full rounded-xl border px-4 py-4 text-left transition",
                    design.design_id === browser.selectedDesignId
                      ? "border-primary/40 bg-primary/10"
                      : "border-border bg-surface hover:border-primary/25",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-foreground">{design.name}</h3>
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {formatCoverage(design.source_coverage)}
                      </p>
                    </div>
                    <SurfaceTag tone={readinessTone(design.compare_readiness)}>
                      {design.compare_readiness}
                    </SurfaceTag>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                    <span>{design.trace_count} traces</span>
                    <span className="truncate">{design.updated_at}</span>
                  </div>
                </button>
              ))}
            </div>

            {selectedDesign ? (
              <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/80 pb-4">
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Selected Design
                    </p>
                    <h3 className="mt-2 text-base font-semibold text-foreground">
                      {selectedDesign.name}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selectedDesign.design_id}
                    </p>
                  </div>
                  <SurfaceTag tone={readinessTone(selectedDesign.compare_readiness)}>
                    {selectedDesign.compare_readiness}
                  </SurfaceTag>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Source Coverage
                    </p>
                    <p className="mt-2 text-sm font-medium text-foreground">
                      {formatCoverage(selectedDesign.source_coverage)}
                    </p>
                  </div>
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Browse State
                    </p>
                    <p className="mt-2 text-sm font-medium text-foreground">
                      {selectedDesign.compare_readiness === "ready"
                        ? "Ready for compare-aware browsing"
                        : selectedDesign.compare_readiness === "inspect_only"
                          ? "Single-source inspection only"
                          : "Blocked until more traces arrive"}
                    </p>
                  </div>
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Trace Count
                    </p>
                    <p className="mt-2 text-sm font-medium text-foreground">
                      {selectedDesign.trace_count}
                    </p>
                  </div>
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Updated
                    </p>
                    <p className="mt-2 text-sm font-medium text-foreground">
                      {selectedDesign.updated_at}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Select a design scope to browse its trace summaries.
              </div>
            )}

            <div className="flex items-center justify-between gap-3 pt-1 text-sm">
              <button
                type="button"
                onClick={browser.goToPrevDesignPage}
                disabled={!browser.designsMeta?.prev_cursor}
                className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={browser.goToNextDesignPage}
                disabled={!browser.designsMeta?.next_cursor}
                className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            No design scopes are available for the active dataset.
          </div>
        )}
      </SurfacePanel>

      <section className="grid gap-5 xl:grid-cols-[minmax(340px,0.9fr)_minmax(0,1.1fr)] xl:items-start">
        <SurfacePanel
          title="Trace Summaries"
          description="Trace browsing stays metadata-only until one row is selected for preview."
        >
            {browser.tracesError ? (
              <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
                Unable to load trace summaries. {browser.tracesError.message}
              </div>
            ) : null}
            <div className="rounded-[1rem] border border-border bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.9fr)_minmax(0,0.95fr)_minmax(0,0.95fr)]">
                <div className="min-w-0">
                  <p className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    <Search className="h-3.5 w-3.5" />
                    Search
                  </p>
                  <div className="flex items-center gap-3 rounded-[0.95rem] border border-border/80 bg-background px-3 py-3">
                    <Search className="h-4 w-4 text-muted-foreground" />
                    <input
                      value={browser.filters.search}
                      onChange={(event) => {
                        browser.setFilters((current) => ({
                          ...current,
                          search: event.target.value,
                        }));
                      }}
                      placeholder="Parameter or history"
                      className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                    />
                  </div>
                </div>
                <TraceFilterSelect
                  label="Family"
                  value={browser.filters.family}
                  onChange={(value) => {
                    browser.setFilters((current) => ({ ...current, family: value }));
                  }}
                  options={["", "s_matrix", "y_matrix", "z_matrix"]}
                />
                <TraceFilterSelect
                  label="View"
                  value={browser.filters.representation}
                  onChange={(value) => {
                    browser.setFilters((current) => ({ ...current, representation: value }));
                  }}
                  options={["", "real", "imaginary", "magnitude", "phase"]}
                />
                <TraceFilterSelect
                  label="Source"
                  value={browser.filters.sourceKind}
                  onChange={(value) => {
                    browser.setFilters((current) => ({ ...current, sourceKind: value }));
                  }}
                  options={["", "measurement", "layout_simulation", "circuit_simulation"]}
                />
              </div>
            </div>

            {browser.isTracesLoading ? (
              <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Loading trace summaries for {deferredTraceSearch || "the selected design"}...
              </div>
            ) : browser.traces.length > 0 ? (
              <div className="mt-4 overflow-hidden rounded-xl border border-border/80">
                <table className="min-w-full table-fixed divide-y divide-border text-sm">
                  <thead className="bg-surface">
                    <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      <th className="w-[22%] px-4 py-3">Parameter</th>
                      <th className="w-[18%] px-4 py-3">Family</th>
                      <th className="w-[16%] px-4 py-3">View</th>
                      <th className="w-[18%] px-4 py-3">Origin</th>
                      <th className="px-4 py-3">History</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-card">
                    {browser.traces.map((trace) => (
                      <tr
                        key={trace.trace_id}
                        className={cx(
                          "cursor-pointer transition hover:bg-primary/5",
                          trace.trace_id === browser.selectedTraceId && "bg-primary/10",
                        )}
                        onClick={() => {
                          browser.setSelectedTraceId(trace.trace_id);
                        }}
                      >
                        <td className="px-4 py-3 font-medium text-foreground">{trace.parameter}</td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatTraceValue(trace.family)}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatTraceValue(trace.representation)}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatTraceSource(trace.source_kind)}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{trace.provenance_summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="flex items-center justify-between gap-3 border-t border-border bg-surface px-4 py-3 text-sm">
                  <button
                    type="button"
                    onClick={browser.goToPrevTracePage}
                    disabled={!browser.tracesMeta?.prev_cursor}
                    className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={browser.goToNextTracePage}
                    disabled={!browser.tracesMeta?.next_cursor}
                    className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                No trace summaries match the current filters.
              </div>
            )}
        </SurfacePanel>

        <SurfacePanel
          title="Single Trace Preview"
          description="Only the selected trace triggers the detail path, so plot and table stay tied to one persisted preview payload at a time."
          className="xl:sticky xl:top-5"
        >
            {browser.traceDetailError ? (
              <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
                Unable to load trace preview. {browser.traceDetailError.message}
              </div>
            ) : null}
            {browser.isTraceDetailLoading ? (
              <div className="rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Loading single-trace preview...
              </div>
            ) : browser.traceDetail ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Selected Trace
                    </p>
                    <h4 className="mt-2 break-all text-base font-semibold text-foreground">
                      {browser.traceDetail.trace_id}
                    </h4>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selectedTraceSummary?.provenance_summary ?? previewSemantics.previewSeriesDetail}
                    </p>
                  </div>
                  <AppSegmentedControl
                    value={previewMode}
                    onChange={setPreviewMode}
                    options={[
                      { value: "plot", label: "Plot" },
                      { value: "table", label: "Table" },
                    ]}
                    ariaLabel="Single trace preview view"
                  />
                </div>

                <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-3">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">X Axis</span>
                      <span className="ml-2 font-medium text-foreground">
                        {previewSemantics.xAxisTitle}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        {hasSampledPreview ? "Preview" : "Point Count"}
                      </span>
                      <span className="ml-2 font-medium text-foreground">
                        {previewPointCountLabel}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Y Axis</span>
                      <span className="ml-2 font-medium text-foreground">
                        {previewSemantics.yAxisTitle}
                      </span>
                    </div>
                  </div>
                </div>

                {previewMode === "plot" ? (
                  previewSeries.isPlotReady ? (
                    <TracePreviewPlot
                      x={previewSeries.x}
                      y={previewSeries.y}
                      xLabel={previewSemantics.xAxisTitle}
                      yLabel={previewSemantics.yAxisTitle}
                      title={browser.traceDetail.trace_id}
                    />
                  ) : (
                    <div className="rounded-[0.95rem] border border-dashed border-border bg-background px-4 py-5 text-sm text-muted-foreground">
                      Plot view is unavailable because the preview payload does not expose a numeric x/y series.
                    </div>
                  )
                ) : (
                  <div className="overflow-hidden rounded-lg border border-border/80">
                    <table className="min-w-full divide-y divide-border text-sm">
                      <thead className="bg-card">
                        <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          <th className="px-4 py-3">{previewSemantics.tableXAxisLabel}</th>
                          <th className="px-4 py-3">{previewSemantics.tableYAxisLabel}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border bg-surface">
                        {previewPoints.map((point, index) => (
                          <tr key={`${point[0]}-${index}`}>
                            <td className="px-4 py-3 text-muted-foreground">{point[0]}</td>
                            <td className="px-4 py-3 font-medium text-foreground">{point[1]}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      X Axis
                    </p>
                    <div className="mt-2 space-y-2 text-sm">
                      <div className="flex items-start justify-between gap-4">
                        <span className="text-muted-foreground">Axis</span>
                        <span className="text-right font-medium text-foreground">
                          {previewSemantics.xAxisName}
                        </span>
                      </div>
                      <div className="flex items-start justify-between gap-4">
                        <span className="text-muted-foreground">Unit</span>
                        <span className="text-right font-medium text-foreground">
                          {previewSemantics.xAxisUnitLabel}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Preview Series
                    </p>
                    <div className="mt-2 space-y-2 text-sm">
                      <div className="flex items-start justify-between gap-4">
                        <span className="text-muted-foreground">Y Axis</span>
                        <span className="text-right font-medium text-foreground">
                          {previewSemantics.previewSeriesLabel}
                        </span>
                      </div>
                      <div className="flex items-start justify-between gap-4">
                        <span className="text-muted-foreground">Y Unit</span>
                        <span className="text-right font-medium text-foreground">
                          {previewSemantics.previewSeriesUnitLabel}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3 md:col-span-2 xl:col-span-1">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Preview Source
                    </p>
                    <p className="mt-2 break-all text-sm font-medium text-foreground">
                      {browser.traceDetail.payload_ref?.store_key ?? "No payload ref"}
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {browser.traceDetail.payload_ref?.group_path ?? "No group path"}
                    </p>
                  </div>
                </div>

                <div className="rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Provenance
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Preview details follow the selected trace and its saved payload reference.
                  </p>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Select one trace summary to load the single-trace preview path.
              </div>
            )}
        </SurfacePanel>
      </section>
    </div>
  );
}
