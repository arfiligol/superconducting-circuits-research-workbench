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

export type TracePreviewContextTag = Readonly<{
  label: string;
  value: string;
}>;

function formatAxisTitle(label: string, unit: string | null) {
  return unit ? `${label} (${unit})` : label;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function readOptionalString(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

export function resolveTracePreviewSemantics({
  axes,
  previewPayload,
  traceSummary,
  fallbackSeriesLabel,
}: Readonly<{
  axes: readonly TraceAxis[];
  previewPayload?: Readonly<Record<string, unknown>> | null;
  traceSummary: TraceMetadataRow | null;
  fallbackSeriesLabel?: string | null;
}>): TracePreviewSemantics {
  const primaryAxis = axes[0] ?? null;
  const xAxisName = humanizeTraceLabel(primaryAxis?.name ?? "axis") || "Axis";
  const xAxisUnit = primaryAxis?.unit?.trim() ? primaryAxis.unit.trim() : null;
  const xAxisTitle = xAxisUnit ? `${xAxisName} (${xAxisUnit})` : xAxisName;
  const xAxisPointCount = typeof primaryAxis?.length === "number" ? primaryAxis.length : null;
  const yAxisPayload = asRecord(previewPayload?.y_axis);
  const contextPayload = asRecord(previewPayload?.context);
  const payloadSeriesLabel = readOptionalString(yAxisPayload?.label);
  const payloadSeriesUnit =
    readOptionalString(yAxisPayload?.unit) ?? readOptionalString(contextPayload?.metric_unit);

  const seriesParts = [traceSummary?.parameter ?? null, humanizeTraceLabel(traceSummary?.representation)]
    .filter((value): value is string => Boolean(value && value.trim()));
  const previewSeriesLabel =
    payloadSeriesLabel ||
    seriesParts.join(" · ") ||
    humanizeTraceLabel(fallbackSeriesLabel) ||
    "Selected trace series";

  const previewSeriesDetail =
    readOptionalString(contextPayload?.family_label) ||
    humanizeTraceLabel(traceSummary?.family) ||
    "Series family unavailable";
  const yAxisTitle = formatAxisTitle(previewSeriesLabel, payloadSeriesUnit);

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
    previewSeriesUnitLabel: payloadSeriesUnit ?? "Unit unavailable",
    yAxisTitle,
    tableXAxisLabel: xAxisTitle,
    tableYAxisLabel: yAxisTitle,
  };
}

export function resolveTracePreviewContextTags({
  previewPayload,
  traceSummary,
}: Readonly<{
  previewPayload?: Readonly<Record<string, unknown>> | null;
  traceSummary: TraceMetadataRow | null;
}>): readonly TracePreviewContextTag[] {
  const contextPayload = asRecord(previewPayload?.context);
  const tags: TracePreviewContextTag[] = [];
  const originLabel =
    readOptionalString(contextPayload?.origin_label) ||
    (traceSummary ? humanizeTraceLabel(traceSummary.source_kind) : null);
  const sourceLabel = readOptionalString(contextPayload?.source_label);
  const metricLabel = readOptionalString(contextPayload?.metric_label);
  const metricUnit = readOptionalString(contextPayload?.metric_unit);
  const portLabel = readOptionalString(contextPayload?.port_label);

  if (originLabel) {
    tags.push({ label: "Origin", value: originLabel });
  }
  if (sourceLabel) {
    tags.push({ label: "Source", value: sourceLabel });
  }
  if (metricLabel) {
    tags.push({
      label: "Metric",
      value: formatAxisTitle(metricLabel, metricUnit),
    });
  }
  if (portLabel) {
    tags.push({ label: "Ports", value: portLabel });
  }

  return tags;
}
