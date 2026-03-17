import type { TraceAxis, TraceMetadataRow } from "@/features/data-browser/lib/contracts";

function humanizeToken(value: string) {
  if (!value) {
    return value;
  }

  if (/^[a-z0-9]+$/.test(value)) {
    return `${value.slice(0, 1).toUpperCase()}${value.slice(1)}`;
  }

  return value;
}

export function humanizeTraceLabel(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  return value
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((token) => humanizeToken(token))
    .join(" ");
}

export type TracePreviewSemantics = Readonly<{
  xAxisName: string;
  xAxisUnit: string | null;
  xAxisUnitLabel: string;
  xAxisTitle: string;
  xAxisPointCount: number | null;
  xAxisPointCountLabel: string;
  previewSeriesLabel: string;
  previewSeriesDetail: string;
  previewSeriesUnitLabel: string;
  yAxisTitle: string;
  tableXAxisLabel: string;
  tableYAxisLabel: string;
}>;

export function resolveTracePreviewSemantics({
  axes,
  traceSummary,
  fallbackSeriesLabel,
}: Readonly<{
  axes: readonly TraceAxis[];
  traceSummary: TraceMetadataRow | null;
  fallbackSeriesLabel?: string | null;
}>): TracePreviewSemantics {
  const primaryAxis = axes[0] ?? null;
  const xAxisName = humanizeTraceLabel(primaryAxis?.name ?? "axis") || "Axis";
  const xAxisUnit = primaryAxis?.unit?.trim() ? primaryAxis.unit.trim() : null;
  const xAxisTitle = xAxisUnit ? `${xAxisName} (${xAxisUnit})` : xAxisName;
  const xAxisPointCount = typeof primaryAxis?.length === "number" ? primaryAxis.length : null;

  const seriesParts = [traceSummary?.parameter ?? null, humanizeTraceLabel(traceSummary?.representation)]
    .filter((value): value is string => Boolean(value && value.trim()));
  const previewSeriesLabel =
    seriesParts.join(" · ") ||
    humanizeTraceLabel(fallbackSeriesLabel) ||
    "Selected trace series";

  const previewSeriesDetail =
    humanizeTraceLabel(traceSummary?.family) || "Series family unavailable";

  return {
    xAxisName,
    xAxisUnit,
    xAxisUnitLabel: xAxisUnit ?? "Unit unavailable",
    xAxisTitle,
    xAxisPointCount,
    xAxisPointCountLabel:
      typeof xAxisPointCount === "number" ? `${xAxisPointCount} points` : "Point count unavailable",
    previewSeriesLabel,
    previewSeriesDetail,
    previewSeriesUnitLabel: "Unit unavailable",
    yAxisTitle: previewSeriesLabel,
    tableXAxisLabel: xAxisTitle,
    tableYAxisLabel: previewSeriesLabel,
  };
}
