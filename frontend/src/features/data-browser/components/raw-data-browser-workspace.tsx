"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Pencil, Search, Trash2 } from "lucide-react";

import { TraceEditDialog } from "@/features/data-browser/components/trace-edit-dialog";
import { TracePreviewPlot } from "@/features/data-browser/components/trace-preview-plot";
import { useRawDataBrowserData } from "@/features/data-browser/hooks/use-raw-data-browser-data";
import {
  humanizeTraceLabel,
  resolveTracePreviewContextTags,
  resolveTracePreviewSemantics,
} from "@/features/data-browser/lib/trace-preview";
import { AppInlineSelect } from "@/features/shared/components/app-select";
import { AppSegmentedControl } from "@/features/shared/components/app-segmented-control";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";

import type { TraceMetadataRow } from "@/features/data-browser/lib/contracts";

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
  return entries.map(([key, value]) => `${formatTraceSource(key)}: ${value}`).join(" · ");
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

function resolvePreviewHistory(
  previewPayload: Readonly<Record<string, unknown>> | undefined,
  fallback: string | null,
) {
  const historySteps = Array.isArray(previewPayload?.history_steps)
    ? previewPayload.history_steps.filter((step): step is string => typeof step === "string")
    : [];
  const historySummary =
    typeof previewPayload?.history_summary === "string" ? previewPayload.history_summary : null;

  return {
    steps: historySteps,
    summary: historySummary ?? fallback ?? "No saved history is available for this trace yet.",
  };
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

function SelectionCheckbox({
  checked,
  indeterminate = false,
  disabled = false,
  onChange,
  ariaLabel,
}: Readonly<{
  checked: boolean;
  indeterminate?: boolean;
  disabled?: boolean;
  onChange: () => void;
  ariaLabel: string;
}>) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!inputRef.current) {
      return;
    }
    inputRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <input
      ref={inputRef}
      type="checkbox"
      aria-label={ariaLabel}
      checked={checked}
      disabled={disabled}
      onChange={() => {
        onChange();
      }}
      className="h-4 w-4 rounded border-border text-primary disabled:cursor-not-allowed disabled:opacity-45"
    />
  );
}

function TraceRowActionButton({
  label,
  disabled = false,
  icon,
  onClick,
  tone = "default",
}: Readonly<{
  label: string;
  disabled?: boolean;
  icon: ReactNode;
  onClick: () => void;
  tone?: "default" | "destructive";
}>) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className={cx(
        "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        tone === "destructive"
          ? "border-rose-500/25 bg-rose-500/8 text-rose-700 hover:border-rose-500/40 hover:bg-rose-500/12 dark:text-rose-200"
          : "border-border bg-surface text-foreground hover:border-primary/30 hover:bg-primary/10",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

export function RawDataBrowserWorkspace() {
  const browser = useRawDataBrowserData();
  const deferredDesignSearch = useDeferredValue(browser.designSearch);
  const deferredTraceSearch = useDeferredValue(browser.filters.search);
  const [previewMode, setPreviewMode] = useState<"plot" | "table">("plot");
  const selectedDesign =
    browser.designs.find((row) => row.design_id === browser.selectedDesignId) ?? null;
  const focusedTraceSummary =
    browser.traces.find((row) => row.trace_id === browser.focusedTraceId) ?? null;
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
        previewPayload:
          (browser.traceDetail?.preview_payload as Readonly<Record<string, unknown>> | undefined) ??
          null,
        traceSummary: focusedTraceSummary,
        fallbackSeriesLabel: browser.traceDetail?.trace_id ?? null,
      }),
    [
      browser.traceDetail?.axes,
      browser.traceDetail?.preview_payload,
      browser.traceDetail?.trace_id,
      focusedTraceSummary,
    ],
  );
  const previewPointCount = previewPoints.length;
  const hasSampledPreview =
    typeof previewSemantics.xAxisPointCount === "number" &&
    previewPointCount > 0 &&
    previewPointCount < previewSemantics.xAxisPointCount;
  const previewPointCountLabel = hasSampledPreview
    ? `${previewPointCount} of ${previewSemantics.xAxisPointCount} points`
    : previewSemantics.xAxisPointCountLabel;
  const previewHistory = useMemo(
    () =>
      resolvePreviewHistory(
        browser.traceDetail?.preview_payload as Readonly<Record<string, unknown>> | undefined,
        focusedTraceSummary?.provenance_summary ?? null,
      ),
    [browser.traceDetail?.preview_payload, focusedTraceSummary?.provenance_summary],
  );
  const previewContextTags = useMemo(
    () =>
      resolveTracePreviewContextTags({
        previewPayload:
          (browser.traceDetail?.preview_payload as Readonly<Record<string, unknown>> | undefined) ??
          null,
        traceSummary: focusedTraceSummary,
      }),
    [browser.traceDetail?.preview_payload, focusedTraceSummary],
  );
  const hasAnySelections = browser.selectedTraceCount > 0;
  const traceDeleteDialog = useMemo(() => {
    if (!browser.pendingDeleteRequest) {
      return null;
    }

    if (browser.pendingDeleteRequest.kind === "single") {
      return {
        title: "Delete Trace",
        description:
          "Delete this saved trace from the current design? This removes the summary row immediately and clears the preview if the focused trace is deleted.",
        confirmLabel: "Delete Trace",
        details: (
          <DeleteScopeCard
            title={browser.pendingDeleteRequest.trace.parameter}
            items={[
              {
                label: "Trace ID",
                value: browser.pendingDeleteRequest.trace.traceId,
              },
              {
                label: "Context",
                value: browser.pendingDeleteRequest.trace.provenanceSummary,
              },
            ]}
          />
        ),
      };
    }

    return {
      title: "Delete Selected Traces",
      description: `Delete ${browser.pendingDeleteRequest.traceIds.length} selected traces from this design? This removes each listed row immediately and safely resolves any deleted preview focus.`,
      confirmLabel: `Delete ${browser.pendingDeleteRequest.traceIds.length} Traces`,
      details: (
        <DeleteScopeList
          traces={browser.pendingDeleteRequest.traces}
          totalCount={browser.pendingDeleteRequest.traceIds.length}
        />
      ),
    };
  }, [browser.pendingDeleteRequest]);

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw Data Browser"
        title="Raw Data"
        description="Choose a design, narrow the trace summaries, edit or delete allowed rows, and keep the preview scoped to one focused trace."
      />

      <SurfacePanel
        title="Design Scopes"
        description="Start with a design here, then move straight into trace summaries and the preview path."
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
                      <p className="mt-1 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]">
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
                  <DesignSummaryTile label="Source Coverage" value={formatCoverage(selectedDesign.source_coverage)} />
                  <DesignSummaryTile
                    label="Browse State"
                    value={
                      selectedDesign.compare_readiness === "ready"
                        ? "Ready for compare-aware browsing"
                        : selectedDesign.compare_readiness === "inspect_only"
                          ? "Single-source inspection only"
                          : "Blocked until more traces arrive"
                    }
                  />
                  <DesignSummaryTile label="Trace Count" value={String(selectedDesign.trace_count)} />
                  <DesignSummaryTile label="Updated" value={selectedDesign.updated_at} />
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

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.82fr)] xl:items-start">
        <SurfacePanel
          title="Trace Summaries"
          description="Focused preview stays single-trace, while selected rows drive batch delete only."
        >
          {browser.notice ? (
            <div
              className={cx(
                "mb-4 rounded-[1rem] border px-4 py-3 text-sm",
                resolveSurfaceInsetToneClass(
                  browser.notice.tone === "success" ? "success" : "warning",
                ),
              )}
            >
              {browser.notice.message}
            </div>
          ) : null}
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
                    placeholder="Parameter or note"
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
            <div className="mt-4 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border border-border bg-surface px-4 py-4">
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Batch Selection
                  </p>
                  <p className="mt-2 text-sm text-foreground">
                    {hasAnySelections
                      ? `${browser.selectedTraceCount} traces selected for delete.`
                      : "Select deletable rows without affecting the single-trace preview."}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={browser.toggleSelectAllVisibleTraces}
                    disabled={!browser.canSelectVisibleTraces}
                    className="rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/30 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {browser.allVisibleDeletableTracesSelected ? "Clear Visible" : "Select Visible"}
                  </button>
                  <button
                    type="button"
                    onClick={browser.clearSelectedTraceIds}
                    disabled={!hasAnySelections}
                    className="rounded-full border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition hover:border-primary/30 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    onClick={browser.requestBatchDeleteSelectedTraces}
                    disabled={!hasAnySelections}
                    className="inline-flex items-center gap-2 rounded-full border border-rose-500/25 bg-rose-500/8 px-3 py-2 text-sm font-medium text-rose-700 transition hover:border-rose-500/40 hover:bg-rose-500/12 disabled:cursor-not-allowed disabled:opacity-60 dark:text-rose-200"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete Selected
                  </button>
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-border/80">
                <table className="min-w-full table-fixed divide-y divide-border text-sm">
                  <thead className="bg-surface">
                    <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      <th className="w-14 px-3 py-3">
                        <SelectionCheckbox
                          ariaLabel="Select visible deletable traces"
                          checked={browser.allVisibleDeletableTracesSelected}
                          indeterminate={
                            hasAnySelections && !browser.allVisibleDeletableTracesSelected
                          }
                          disabled={!browser.canSelectVisibleTraces}
                          onChange={browser.toggleSelectAllVisibleTraces}
                        />
                      </th>
                      <th className="w-[30%] px-4 py-3">Trace</th>
                      <th className="w-[15%] px-4 py-3">Family</th>
                      <th className="w-[14%] px-4 py-3">View</th>
                      <th className="w-[14%] px-4 py-3">Origin</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-card">
                    {browser.traces.map((trace) => (
                      <TraceSummaryRow
                        key={trace.trace_id}
                        trace={trace}
                        isFocused={trace.trace_id === browser.focusedTraceId}
                        isSelected={browser.isTraceSelected(trace.trace_id)}
                        onFocus={browser.focusTrace}
                        onToggleSelected={browser.toggleTraceSelection}
                        onEdit={browser.openEditDialog}
                        onDelete={browser.requestSingleDelete}
                      />
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
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              No trace summaries match the current filters.
            </div>
          )}
        </SurfacePanel>

        <SurfacePanel title="Single Trace Preview" className="xl:sticky xl:top-5">
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
                    Focused Trace
                  </p>
                  <h4 className="mt-2 break-all text-base font-semibold text-foreground">
                    {browser.traceDetail.trace_id}
                  </h4>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {focusedTraceSummary?.provenance_summary ?? previewSemantics.previewSeriesDetail}
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

              <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      History
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">{previewHistory.summary}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <SurfaceTag tone="default">
                        {hasSampledPreview ? "Preview" : "Point Count"} · {previewPointCountLabel}
                      </SurfaceTag>
                      {previewContextTags.map((tag) => (
                        <SurfaceTag key={`${tag.label}:${tag.value}`} tone="default">
                          {tag.label} · {tag.value}
                        </SurfaceTag>
                      ))}
                    </div>
                  </div>
                  {previewHistory.steps.length > 0 ? (
                    <div className="flex flex-wrap justify-end gap-2">
                      {previewHistory.steps.map((step, index) => (
                        <SurfaceTag key={`${step}:${index}`} tone="default">
                          {index + 1}. {step}
                        </SurfaceTag>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              Select one trace summary to load the single-trace preview path.
            </div>
          )}
        </SurfacePanel>
      </section>

      <TraceEditDialog
        open={Boolean(browser.editTraceId)}
        detail={browser.traceEditDetail}
        isLoading={browser.isTraceEditDetailLoading}
        error={browser.traceEditDetailError}
        saveErrorMessage={browser.editSaveErrorMessage}
        isSaving={browser.isEditSavePending}
        onClose={browser.closeEditDialog}
        onSave={browser.saveEditedTrace}
      />

      <ConfirmActionDialog
        open={Boolean(browser.pendingDeleteRequest && traceDeleteDialog)}
        title={traceDeleteDialog?.title ?? "Delete Trace"}
        description={
          traceDeleteDialog?.description ??
          "Delete the selected traces from this design."
        }
        details={traceDeleteDialog?.details}
        confirmLabel={traceDeleteDialog?.confirmLabel ?? "Delete Trace"}
        tone="destructive"
        isPending={browser.isDeletePending}
        onCancel={browser.closeDeleteDialog}
        onConfirm={() => {
          void browser.confirmDeleteRequest();
        }}
      />
    </div>
  );
}

function DeleteScopeCard({
  title,
  items,
}: Readonly<{
  title: string;
  items: readonly Readonly<{
    label: string;
    value: string;
  }>[];
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-surface px-4 py-4">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <dl className="mt-3 space-y-2 text-sm">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col gap-1">
            <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              {item.label}
            </dt>
            <dd className="break-all text-muted-foreground">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function DeleteScopeList({
  traces,
  totalCount,
}: Readonly<{
  traces: readonly Readonly<{
    traceId: string;
    parameter: string;
    provenanceSummary: string;
  }>[];
  totalCount: number;
}>) {
  const visibleTraces = traces.slice(0, 4);
  const hiddenCount = Math.max(totalCount - visibleTraces.length, 0);

  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-surface px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        Delete Scope
      </p>
      <div className="mt-3 space-y-3">
        {visibleTraces.map((trace) => (
          <div key={trace.traceId} className="rounded-[0.85rem] border border-border/70 bg-background px-3 py-3">
            <p className="text-sm font-medium text-foreground">{trace.parameter}</p>
            <p className="mt-1 break-all text-xs text-muted-foreground">{trace.traceId}</p>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {trace.provenanceSummary}
            </p>
          </div>
        ))}
        {hiddenCount > 0 ? (
          <p className="text-xs text-muted-foreground">
            +{hiddenCount} more selected traces in this delete request.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function DesignSummaryTile({
  label,
  value,
}: Readonly<{
  label: string;
  value: string;
}>) {
  return (
    <div className="min-w-0 rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-sm font-medium text-foreground [overflow-wrap:anywhere]">
        {value}
      </p>
    </div>
  );
}

function TraceSummaryRow({
  trace,
  isFocused,
  isSelected,
  onFocus,
  onToggleSelected,
  onEdit,
  onDelete,
}: Readonly<{
  trace: TraceMetadataRow;
  isFocused: boolean;
  isSelected: boolean;
  onFocus: (traceId: string) => void;
  onToggleSelected: (traceId: string) => void;
  onEdit: (traceId: string) => void;
  onDelete: (trace: TraceMetadataRow) => void;
}>) {
  const hasRowActions = trace.allowed_actions.edit || trace.allowed_actions.delete;

  return (
    <tr
      className={cx(
        "cursor-pointer transition hover:bg-primary/5",
        isFocused && "bg-primary/10",
      )}
      onClick={() => {
        onFocus(trace.trace_id);
      }}
    >
      <td className="px-3 py-3 align-top">
        <div
          onClick={(event) => {
            event.stopPropagation();
          }}
        >
          <SelectionCheckbox
            ariaLabel={`Select ${trace.trace_id}`}
            checked={isSelected}
            disabled={!trace.allowed_actions.delete}
            onChange={() => {
              onToggleSelected(trace.trace_id);
            }}
          />
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        <p className="font-medium text-foreground">{trace.parameter}</p>
        <p className="mt-1 break-all text-xs text-muted-foreground">{trace.trace_id}</p>
        <p className="mt-2 text-xs text-muted-foreground">{trace.provenance_summary}</p>
      </td>
      <td className="px-4 py-3 align-top text-muted-foreground">
        {formatTraceValue(trace.family)}
      </td>
      <td className="px-4 py-3 align-top text-muted-foreground">
        {formatTraceValue(trace.representation)}
      </td>
      <td className="px-4 py-3 align-top text-muted-foreground">
        {formatTraceSource(trace.source_kind)}
      </td>
      <td className="px-4 py-3 align-top">
        {hasRowActions ? (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {trace.allowed_actions.edit ? (
                <TraceRowActionButton
                  label="Edit"
                  icon={<Pencil className="h-3.5 w-3.5" />}
                  onClick={() => {
                    onEdit(trace.trace_id);
                  }}
                />
              ) : null}
              {trace.allowed_actions.delete ? (
                <TraceRowActionButton
                  label="Delete"
                  tone="destructive"
                  icon={<Trash2 className="h-3.5 w-3.5" />}
                  onClick={() => {
                    onDelete(trace);
                  }}
                />
              ) : null}
            </div>
            <p className="text-xs leading-5 text-muted-foreground">
              {trace.mutation_policy_summary}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Locked
            </p>
            <p className="text-xs leading-5 text-muted-foreground">
              {trace.mutation_policy_summary}
            </p>
          </div>
        )}
      </td>
    </tr>
  );
}
