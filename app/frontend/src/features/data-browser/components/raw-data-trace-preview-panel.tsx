"use client";

import { useMemo } from "react";

import { TracePreviewPlot } from "@/features/data-browser/components/trace-preview-plot";
import {
  resolvePreviewHistory,
  resolvePreviewPoints,
} from "@/features/data-browser/lib/raw-data-browser-formatters";
import {
  humanizeTraceLabel,
  resolveTracePreviewContextTags,
  resolveTracePreviewSemantics,
} from "@/features/data-browser/lib/trace-preview";
import { AppSegmentedControl } from "@/features/shared/components/app-segmented-control";
import { SurfacePanel, SurfaceTag } from "@/features/shared/components/surface-kit";

import type { TraceDetail, TraceMetadataRow } from "@/features/data-browser/lib/contracts";

export function RawDataTracePreviewPanel({
  traceDetail,
  traceDetailError,
  isTraceDetailLoading,
  focusedTraceSummary,
  previewMode,
  setPreviewMode,
  className,
}: Readonly<{
  traceDetail: TraceDetail | undefined;
  traceDetailError: Error | undefined;
  isTraceDetailLoading: boolean;
  focusedTraceSummary: TraceMetadataRow | null;
  previewMode: "plot" | "table";
  setPreviewMode: (value: "plot" | "table") => void;
  className?: string;
}>) {
  const previewPoints = useMemo(
    () => resolvePreviewPoints(traceDetail?.preview_payload.points),
    [traceDetail?.preview_payload.points],
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
        axes: traceDetail?.axes ?? [],
        previewPayload:
          (traceDetail?.preview_payload as Readonly<Record<string, unknown>> | undefined) ?? null,
        traceSummary: focusedTraceSummary,
        fallbackSeriesLabel: traceDetail?.trace_id ?? null,
      }),
    [traceDetail?.axes, traceDetail?.preview_payload, traceDetail?.trace_id, focusedTraceSummary],
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
        traceDetail?.preview_payload as Readonly<Record<string, unknown>> | undefined,
        focusedTraceSummary?.provenance_summary ?? null,
      ),
    [traceDetail?.preview_payload, focusedTraceSummary?.provenance_summary],
  );
  const previewContextTags = useMemo(
    () =>
      resolveTracePreviewContextTags({
        previewPayload:
          (traceDetail?.preview_payload as Readonly<Record<string, unknown>> | undefined) ?? null,
        traceSummary: focusedTraceSummary,
      }),
    [traceDetail?.preview_payload, focusedTraceSummary],
  );

  return (
    <SurfacePanel title="Single Trace Preview" className={className}>
      {traceDetailError ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
          Unable to load trace preview. {traceDetailError.message}
        </div>
      ) : isTraceDetailLoading ? (
        <div className="rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          Loading single-trace preview...
        </div>
      ) : traceDetail ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Focused Trace</p>
              <h4 className="mt-2 break-all text-base font-semibold text-foreground">
                {traceDetail.trace_id}
              </h4>
              <p className="mt-1 text-sm text-muted-foreground">
                {focusedTraceSummary?.provenance_summary ?? previewSemantics.previewSeriesDetail}
              </p>
            </div>
            <AppSegmentedControl
              value={previewMode}
              onChange={(value) => {
                setPreviewMode(value as "plot" | "table");
              }}
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
                <span className="ml-2 font-medium text-foreground">{previewSemantics.xAxisTitle}</span>
              </div>
              <div>
                <span className="text-muted-foreground">
                  {hasSampledPreview ? "Preview" : "Point Count"}
                </span>
                <span className="ml-2 font-medium text-foreground">{previewPointCountLabel}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Y Axis</span>
                <span className="ml-2 font-medium text-foreground">{previewSemantics.yAxisTitle}</span>
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
                title={traceDetail.trace_id}
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
            <div className="space-y-4">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">History</p>
                <p className="mt-2 text-sm text-muted-foreground">{previewHistory.summary}</p>
              </div>

              <div className="rounded-[0.85rem] border border-border/70 bg-surface px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Context</p>
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
                <div className="rounded-[0.85rem] border border-border/70 bg-surface px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Process</p>
                  <ol className="mt-3 space-y-2">
                    {previewHistory.steps.map((step, index) => (
                      <li
                        key={`${step}:${index}`}
                        className="flex items-center gap-3 rounded-[0.8rem] border border-border/70 bg-background px-3 py-3"
                      >
                        <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full border border-border/80 bg-card px-2 text-sm font-semibold text-foreground">
                          {index + 1}
                        </span>
                        <span className="text-sm text-foreground">{humanizeTraceLabel(step) || step}</span>
                      </li>
                    ))}
                  </ol>
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
  );
}
