"use client";

import type {
  SimulationResultExplorerBootstrap,
  SimulationResultExplorerBootstrapPayload,
  SimulationResultExplorerFamily,
  SimulationResultExplorerPayload,
  SimulationResultExplorerQuery,
  SimulationResultExplorerSelection,
  SimulationResultExplorerViewPayload,
  SimulationResultExplorerViewSlice,
} from "@/lib/api/tasks";

export const SIMULATION_RESULT_EXPLORER_CACHE_LIMIT = 12;

export type EditableExplorerSelection = Readonly<{
  family: string;
  source: string;
  metric: string;
  sweepIndex: number | null;
  compareAxisIndex: number | null;
  traceKey: string | null;
  z0: number;
  outputPort: number;
  inputPort: number;
}>;

export function buildEditableSelection(
  selection: SimulationResultExplorerSelection,
): EditableExplorerSelection {
  return {
    family: selection.family,
    source: selection.source,
    metric: selection.metric,
    sweepIndex: selection.sweepIndex,
    compareAxisIndex: selection.compareAxisIndex,
    traceKey: selection.traceKey,
    z0: selection.z0Ohm,
    outputPort: selection.outputPort,
    inputPort: selection.inputPort,
  };
}

export function buildSimulationResultExplorerQuery(
  selection: EditableExplorerSelection | null,
): SimulationResultExplorerQuery | undefined {
  if (!selection) {
    return undefined;
  }

  return {
    family: selection.family,
    source: selection.source,
    metric: selection.metric,
    sweepIndex: selection.sweepIndex ?? undefined,
    compareAxisIndex: selection.compareAxisIndex ?? undefined,
    z0: selection.z0,
    outputPort: selection.outputPort,
    inputPort: selection.inputPort,
  };
}

export function buildSimulationResultExplorerSelectionCacheKey(
  taskId: number,
  selection: EditableExplorerSelection,
): string {
  const params = new URLSearchParams({
    family: selection.family,
    source: selection.source,
    metric: selection.metric,
    z0: String(selection.z0),
    output_port: String(selection.outputPort),
    input_port: String(selection.inputPort),
  });

  if (typeof selection.sweepIndex === "number") {
    params.set("sweep_index", String(selection.sweepIndex));
  }
  if (typeof selection.compareAxisIndex === "number") {
    params.set("compare_axis_index", String(selection.compareAxisIndex));
  }

  return `${taskId}:${params.toString()}`;
}

export function extractSimulationResultExplorerViewSlice(
  payload: SimulationResultExplorerViewPayload | SimulationResultExplorerPayload,
): SimulationResultExplorerViewSlice {
  return {
    selection: payload.selection,
    plot: payload.plot,
  };
}

export function composeSimulationResultExplorerPayload(
  bootstrapPayload: SimulationResultExplorerBootstrapPayload,
  viewSlice: SimulationResultExplorerViewSlice,
): SimulationResultExplorerPayload {
  return {
    ...bootstrapPayload,
    selection: viewSlice.selection,
    plot: viewSlice.plot,
  };
}

export function primeSimulationResultExplorerViewCache(
  cache: Map<string, SimulationResultExplorerViewSlice>,
  cacheKey: string,
  viewSlice: SimulationResultExplorerViewSlice,
  limit = SIMULATION_RESULT_EXPLORER_CACHE_LIMIT,
): Map<string, SimulationResultExplorerViewSlice> {
  cache.delete(cacheKey);
  cache.set(cacheKey, viewSlice);

  while (cache.size > limit) {
    const oldestKey = cache.keys().next().value;
    if (!oldestKey) {
      break;
    }
    cache.delete(oldestKey);
  }

  return cache;
}

export function encodeSimulationExplorerSweepIndex(
  axes: readonly Readonly<{
    values: readonly number[];
  }>[],
  coordinates: readonly number[],
): number | null {
  if (axes.length === 0) {
    return null;
  }

  let encoded = 0;
  for (let axisIndex = 0; axisIndex < axes.length; axisIndex += 1) {
    const axisSize = Math.max(axes[axisIndex]?.values.length ?? 0, 1);
    const coordinate = Math.min(
      Math.max(coordinates[axisIndex] ?? 0, 0),
      Math.max(axisSize - 1, 0),
    );
    encoded = encoded * axisSize + coordinate;
  }
  return encoded;
}

export function decodeSimulationExplorerSweepCoordinates(
  axes: readonly Readonly<{
    values: readonly number[];
  }>[],
  sweepIndex: number | null,
): readonly number[] {
  if (axes.length === 0 || !Number.isInteger(sweepIndex) || sweepIndex === null || sweepIndex < 0) {
    return axes.map(() => 0);
  }

  const coordinates = new Array<number>(axes.length).fill(0);
  let remaining = sweepIndex;

  for (let axisIndex = axes.length - 1; axisIndex >= 0; axisIndex -= 1) {
    const axisSize = Math.max(axes[axisIndex]?.values.length ?? 0, 1);
    coordinates[axisIndex] = remaining % axisSize;
    remaining = Math.floor(remaining / axisSize);
  }

  return coordinates;
}

export function resolveSimulationExplorerSweepAxes(
  axes: readonly Readonly<{
    parameter: string;
    label: string;
    unit: string | null;
    values: readonly number[];
    selectedValueIndex: number;
  }>[],
  sweepIndex: number | null,
) {
  const coordinates = decodeSimulationExplorerSweepCoordinates(axes, sweepIndex);

  return axes.map((axis, axisIndex) => ({
    ...axis,
    selectedValueIndex: coordinates[axisIndex] ?? axis.selectedValueIndex,
  }));
}

export function resolveAvailableExplorerFamily(
  families: readonly SimulationResultExplorerFamily[],
  familyKey: string,
): SimulationResultExplorerFamily | null {
  return families.find((family) => family.key === familyKey) ?? families[0] ?? null;
}

export function clampSimulationExplorerPort(
  nextPort: number,
  ports: readonly Readonly<{ port: number; label: string }>[],
): number {
  return ports.some((portOption) => portOption.port === nextPort)
    ? nextPort
    : (ports[0]?.port ?? 1);
}

export function extractBootstrapSelection(
  bootstrap: SimulationResultExplorerBootstrap,
): EditableExplorerSelection {
  return buildEditableSelection(bootstrap.defaultSelection);
}
