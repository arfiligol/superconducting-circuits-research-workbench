import { humanizeTraceLabel } from "@/features/data-browser/lib/trace-preview";

type PreviewPayloadRecord = Readonly<Record<string, unknown>> | undefined;

export function readinessTone(value: "ready" | "inspect_only" | "blocked") {
  if (value === "ready") {
    return "success" as const;
  }
  if (value === "inspect_only") {
    return "primary" as const;
  }
  return "warning" as const;
}

export function formatTraceValue(value: string) {
  return humanizeTraceLabel(value) || value;
}

export function formatTraceSource(value: string) {
  switch (value) {
    case "layout_simulation":
      return "Layout sim";
    case "circuit_simulation":
      return "Circuit sim";
    default:
      return formatTraceValue(value);
  }
}

export function formatCoverage(coverage: Record<string, number>) {
  const entries = Object.entries(coverage);
  if (entries.length === 0) {
    return "No source coverage";
  }
  return entries.map(([key, value]) => `${formatTraceSource(key)}: ${value}`).join(" · ");
}

export function resolvePreviewPoints(points: unknown) {
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

export function resolvePreviewHistory(previewPayload: PreviewPayloadRecord, fallback: string | null) {
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
