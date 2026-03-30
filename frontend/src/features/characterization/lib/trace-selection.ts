import type { CharacterizationTraceSelectionRow } from "@/features/characterization/lib/contracts";

export function buildCharacterizationTraceCollectionValue(
  trace: Pick<CharacterizationTraceSelectionRow, "collectionProjection">,
) {
  if (!trace.collectionProjection) {
    return "";
  }

  return trace.collectionProjection.collectionId ?? trace.collectionProjection.label;
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
