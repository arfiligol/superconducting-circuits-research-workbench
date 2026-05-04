import type { CharacterizationTraceSelectionRow } from "@/features/characterization/lib/contracts";

export function buildCharacterizationTraceCollectionValue(
  trace: Pick<CharacterizationTraceSelectionRow, "collectionProjection">,
) {
  if (!trace.collectionProjection) {
    return "";
  }

  return trace.collectionProjection.collectionId ?? trace.collectionProjection.label;
}

function buildTraceSelectionGroupValue(trace: CharacterizationTraceSelectionRow) {
  return (
    buildCharacterizationTraceCollectionValue(trace) ||
    trace.axisSignature ||
    trace.trace_id
  );
}

export function defaultCharacterizationTraceSelection(
  rows: readonly CharacterizationTraceSelectionRow[],
) {
  const candidateRows = rows.filter((trace) => trace.trace_mode_group === "base");
  const selectableRows = candidateRows.length > 0 ? candidateRows : rows;
  const groups = new Map<
    string,
    {
      firstIndex: number;
      hasSweepAxis: boolean;
      traceIds: string[];
    }
  >();

  for (const [index, trace] of selectableRows.entries()) {
    const groupValue = buildTraceSelectionGroupValue(trace);
    const group = groups.get(groupValue);
    if (group) {
      group.traceIds.push(trace.trace_id);
      group.hasSweepAxis = group.hasSweepAxis || trace.availableSweepAxes.length > 0;
      continue;
    }

    groups.set(groupValue, {
      firstIndex: index,
      hasSweepAxis: trace.availableSweepAxes.length > 0,
      traceIds: [trace.trace_id],
    });
  }

  return (
    Array.from(groups.values()).sort((left, right) => {
      if (left.hasSweepAxis !== right.hasSweepAxis) {
        return left.hasSweepAxis ? -1 : 1;
      }
      if (left.traceIds.length !== right.traceIds.length) {
        return right.traceIds.length - left.traceIds.length;
      }
      return left.firstIndex - right.firstIndex;
    })[0]?.traceIds ?? []
  );
}

export function buildCharacterizationSweepAxisOptions(
  rows: readonly CharacterizationTraceSelectionRow[],
) {
  return Array.from(
    new Set(rows.flatMap((trace) => trace.availableSweepAxes).filter(Boolean)),
  ).sort((left, right) => left.localeCompare(right));
}

export function buildCharacterizationCollectionOptions(
  rows: readonly CharacterizationTraceSelectionRow[],
) {
  const options = new Map<string, string>();

  for (const trace of rows) {
    const value = buildCharacterizationTraceCollectionValue(trace);
    if (!value || options.has(value)) {
      continue;
    }

    options.set(value, trace.collectionProjection?.label ?? value);
  }

  return Array.from(options.entries())
    .map(([value, label]) => ({ value, label }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

export function filterCharacterizationTraceRows(
  rows: readonly CharacterizationTraceSelectionRow[],
  filters: Readonly<{
    sweepAxis: string | null;
    collection: string | null;
  }>,
) {
  return rows.filter((trace) => {
    if (
      filters.sweepAxis &&
      !trace.availableSweepAxes.includes(filters.sweepAxis)
    ) {
      return false;
    }

    if (
      filters.collection &&
      buildCharacterizationTraceCollectionValue(trace) !== filters.collection
    ) {
      return false;
    }

    return true;
  });
}
