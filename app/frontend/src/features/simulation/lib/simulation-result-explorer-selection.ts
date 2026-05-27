"use client";

import type {
  SimulationResultExplorerBootstrap,
  SimulationResultExplorerBootstrapPayload,
  SimulationResultExplorerFamily,
  SimulationResultExplorerQuery,
} from "@/lib/api/tasks";

import {
  buildSimulationResultExplorerQuery,
  buildSimulationResultExplorerSelectionCacheKey,
  encodeSimulationExplorerSweepIndex,
  extractBootstrapSelection,
  type EditableExplorerSelection,
} from "./simulation-result-explorer-state";

export type ExplorerSelectionUpdateContext = Readonly<{
  bootstrap: SimulationResultExplorerBootstrap;
  resolvedSelection: EditableExplorerSelection | null;
}>;

export type SimulationResultExplorerDerivedState = Readonly<{
  bootstrapSelection: EditableExplorerSelection | null;
  effectiveSelection: EditableExplorerSelection | null;
  selectedFamily: SimulationResultExplorerFamily | null;
  viewQueryInput: SimulationResultExplorerQuery | undefined;
  bootstrapViewKey: string | null;
  requestedViewKey: string | null;
  isRefreshingSelection: boolean;
}>;

export function deriveSimulationResultExplorerState({
  taskId,
  bootstrapPayload,
  selection,
  activeViewKey,
}: Readonly<{
  taskId: number | null;
  bootstrapPayload: SimulationResultExplorerBootstrapPayload | undefined;
  selection: EditableExplorerSelection | null;
  activeViewKey: string | null;
}>): SimulationResultExplorerDerivedState {
  const bootstrapSelection = bootstrapPayload
    ? extractBootstrapSelection(bootstrapPayload.bootstrap)
    : null;
  const effectiveSelection = selection ?? bootstrapSelection;
  const selectedFamily =
    bootstrapPayload && effectiveSelection
      ? resolveAvailableExplorerFamily(
          bootstrapPayload.bootstrap.families,
          effectiveSelection.family,
        )
      : null;
  const viewQueryInput = buildSimulationResultExplorerQuery(effectiveSelection);
  const bootstrapViewKey =
    taskId !== null && bootstrapSelection
      ? buildSimulationResultExplorerSelectionCacheKey(taskId, bootstrapSelection)
      : null;
  const requestedViewKey =
    taskId !== null && effectiveSelection
      ? buildSimulationResultExplorerSelectionCacheKey(taskId, effectiveSelection)
      : null;

  return {
    bootstrapSelection,
    effectiveSelection,
    selectedFamily,
    viewQueryInput,
    bootstrapViewKey,
    requestedViewKey,
    isRefreshingSelection:
      requestedViewKey !== null &&
      activeViewKey !== null &&
      requestedViewKey !== activeViewKey,
  };
}

function resolveAvailableExplorerFamily(
  families: readonly SimulationResultExplorerFamily[],
  familyKey: string,
): SimulationResultExplorerFamily | null {
  return families.find((family) => family.key === familyKey) ?? families[0] ?? null;
}

function clampSimulationExplorerPort(
  nextPort: number,
  ports: readonly Readonly<{ port: number; label: string }>[],
): number {
  return ports.some((portOption) => portOption.port === nextPort)
    ? nextPort
    : (ports[0]?.port ?? 1);
}

export function buildExplorerSelectionUpdateContext(
  bootstrapPayload: SimulationResultExplorerBootstrapPayload | undefined,
  resolvedSelection: EditableExplorerSelection | null,
): ExplorerSelectionUpdateContext | null {
  if (!bootstrapPayload) {
    return null;
  }

  return {
    bootstrap: bootstrapPayload.bootstrap,
    resolvedSelection,
  };
}

export function updateExplorerFamilySelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  nextFamily: string,
): EditableExplorerSelection {
  const family = resolveAvailableExplorerFamily(context.bootstrap.families, nextFamily);
  if (!family) {
    return current;
  }

  const source =
    family.availableSources.find((option) => option.key === current.source)?.key ??
    family.availableSources[0]?.key ??
    current.source;
  const metric =
    family.availableMetrics.find((option) => option.key === current.metric)?.key ??
    family.availableMetrics[0]?.key ??
    current.metric;

  return {
    ...current,
    family: family.key,
    source,
    metric,
    compareAxisIndex: context.resolvedSelection?.compareAxisIndex ?? current.compareAxisIndex,
  };
}

export function updateExplorerSourceSelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  nextSource: string,
): EditableExplorerSelection {
  const family = resolveAvailableExplorerFamily(context.bootstrap.families, current.family);
  if (!family || !family.availableSources.some((option) => option.key === nextSource)) {
    return current;
  }

  return {
    ...current,
    source: nextSource,
  };
}

export function updateExplorerMetricSelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  nextMetric: string,
): EditableExplorerSelection {
  const family = resolveAvailableExplorerFamily(context.bootstrap.families, current.family);
  if (!family || !family.availableMetrics.some((option) => option.key === nextMetric)) {
    return current;
  }

  return {
    ...current,
    metric: nextMetric,
  };
}

export function updateExplorerSweepValueSelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  axisIndex: number,
  nextValueIndex: number,
): EditableExplorerSelection {
  const sweepAxes = context.bootstrap.parameterSweep.axes;
  if (
    !context.bootstrap.parameterSweep.active ||
    axisIndex < 0 ||
    axisIndex >= sweepAxes.length
  ) {
    return current;
  }

  const coordinates = sweepAxes.map((axis) => axis.selectedValueIndex);
  const axisSize = sweepAxes[axisIndex]?.values.length ?? 0;
  if (axisSize <= 0) {
    return current;
  }

  coordinates[axisIndex] = Math.min(Math.max(nextValueIndex, 0), axisSize - 1);

  return {
    ...current,
    sweepIndex: encodeSimulationExplorerSweepIndex(sweepAxes, coordinates),
  };
}

export function updateExplorerCompareAxisSelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  nextAxisIndex: number,
): EditableExplorerSelection {
  const sweepAxes = context.bootstrap.parameterSweep.axes;
  if (
    !context.bootstrap.parameterSweep.active ||
    nextAxisIndex < 0 ||
    nextAxisIndex >= sweepAxes.length
  ) {
    return current;
  }

  return {
    ...current,
    compareAxisIndex: nextAxisIndex,
  };
}

export function updateExplorerZ0Selection(
  current: EditableExplorerSelection,
  nextZ0: number,
): EditableExplorerSelection {
  if (!Number.isFinite(nextZ0) || nextZ0 <= 0) {
    return current;
  }

  return {
    ...current,
    z0: nextZ0,
  };
}

export function updateExplorerOutputPortSelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  nextPort: number,
): EditableExplorerSelection {
  return {
    ...current,
    outputPort: clampSimulationExplorerPort(
      nextPort,
      context.bootstrap.traceSelector.outputPorts,
    ),
  };
}

export function updateExplorerInputPortSelection(
  current: EditableExplorerSelection,
  context: ExplorerSelectionUpdateContext,
  nextPort: number,
): EditableExplorerSelection {
  return {
    ...current,
    inputPort: clampSimulationExplorerPort(
      nextPort,
      context.bootstrap.traceSelector.inputPorts,
    ),
  };
}
