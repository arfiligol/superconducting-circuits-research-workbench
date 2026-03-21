"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";

import {
  getSimulationResultExplorerBootstrap,
  getSimulationResultExplorerView,
  simulationResultExplorerBootstrapKey,
  simulationResultExplorerViewKey,
  type SimulationResultExplorerPayload,
  type SimulationResultExplorerViewSlice,
} from "@/lib/api/tasks";

import {
  buildEditableSelection,
  buildSimulationResultExplorerQuery,
  buildSimulationResultExplorerSelectionCacheKey,
  clampSimulationExplorerPort,
  composeSimulationResultExplorerPayload,
  encodeSimulationExplorerSweepIndex,
  extractBootstrapSelection,
  extractSimulationResultExplorerViewSlice,
  primeSimulationResultExplorerViewCache,
  resolveAvailableExplorerFamily,
  type EditableExplorerSelection,
} from "../lib/simulation-result-explorer-state";

export function useSimulationResultExplorer(taskId: number | null, enabled: boolean) {
  const [selection, setSelection] = useState<EditableExplorerSelection | null>(null);
  const [activeViewKey, setActiveViewKey] = useState<string | null>(null);
  const [activeViewSlice, setActiveViewSlice] =
    useState<SimulationResultExplorerViewSlice | null>(null);
  const viewCacheRef = useRef(new Map<string, SimulationResultExplorerViewSlice>());

  useEffect(() => {
    setSelection(null);
    setActiveViewKey(null);
    setActiveViewSlice(null);
    viewCacheRef.current = new Map();
  }, [taskId]);

  const bootstrapQuery = useSWR(
    enabled && taskId !== null ? simulationResultExplorerBootstrapKey(taskId) : null,
    () =>
      taskId !== null
        ? getSimulationResultExplorerBootstrap(taskId)
        : Promise.resolve(undefined),
  );

  const bootstrapPayload = bootstrapQuery.data;
  const bootstrapSelection = useMemo(
    () => (bootstrapPayload ? extractBootstrapSelection(bootstrapPayload.bootstrap) : null),
    [bootstrapPayload],
  );
  const effectiveSelection = selection ?? bootstrapSelection;
  const selectedFamily =
    bootstrapPayload && effectiveSelection
      ? resolveAvailableExplorerFamily(
          bootstrapPayload.bootstrap.families,
          effectiveSelection.family,
        )
      : null;
  const viewQueryInput = useMemo(
    () => buildSimulationResultExplorerQuery(effectiveSelection),
    [effectiveSelection],
  );
  const bootstrapViewKey =
    taskId !== null && bootstrapSelection
      ? buildSimulationResultExplorerSelectionCacheKey(taskId, bootstrapSelection)
      : null;
  const requestedViewKey =
    taskId !== null && effectiveSelection
      ? buildSimulationResultExplorerSelectionCacheKey(taskId, effectiveSelection)
      : null;

  useEffect(() => {
    if (!bootstrapPayload || taskId === null || !bootstrapViewKey) {
      return;
    }

    const bootstrapViewSlice = extractSimulationResultExplorerViewSlice(bootstrapPayload);
    primeSimulationResultExplorerViewCache(
      viewCacheRef.current,
      bootstrapViewKey,
      bootstrapViewSlice,
    );
    setSelection((current) => current ?? buildEditableSelection(bootstrapPayload.selection));
    setActiveViewSlice((current) =>
      current ?? extractSimulationResultExplorerViewSlice(bootstrapPayload),
    );
    setActiveViewKey((current) => current ?? bootstrapViewKey);
  }, [bootstrapPayload, bootstrapViewKey, taskId]);

  useEffect(() => {
    if (!requestedViewKey) {
      return;
    }

    if (requestedViewKey === bootstrapViewKey && bootstrapPayload) {
      setActiveViewSlice(extractSimulationResultExplorerViewSlice(bootstrapPayload));
      setActiveViewKey(requestedViewKey);
      return;
    }

    const cachedView = viewCacheRef.current.get(requestedViewKey);
    if (cachedView) {
      setActiveViewSlice(cachedView);
      setActiveViewKey(requestedViewKey);
    }
  }, [bootstrapPayload, bootstrapViewKey, requestedViewKey]);

  const shouldFetchView =
    enabled &&
    taskId !== null &&
    viewQueryInput !== undefined &&
    requestedViewKey !== null &&
    requestedViewKey !== bootstrapViewKey &&
    !viewCacheRef.current.has(requestedViewKey);
  const viewQuery = useSWR(
    shouldFetchView && taskId !== null && viewQueryInput
      ? simulationResultExplorerViewKey(taskId, viewQueryInput)
      : null,
    () =>
      taskId !== null && viewQueryInput
        ? getSimulationResultExplorerView(taskId, viewQueryInput)
        : Promise.resolve(undefined),
  );

  useEffect(() => {
    if (!viewQuery.data || taskId === null) {
      return;
    }

    const resolvedSelection = buildEditableSelection(viewQuery.data.selection);
    const resolvedViewKey = buildSimulationResultExplorerSelectionCacheKey(
      taskId,
      resolvedSelection,
    );
    const resolvedViewSlice = extractSimulationResultExplorerViewSlice(viewQuery.data);

    primeSimulationResultExplorerViewCache(
      viewCacheRef.current,
      resolvedViewKey,
      resolvedViewSlice,
    );
    setSelection(resolvedSelection);
    setActiveViewSlice(resolvedViewSlice);
    setActiveViewKey(resolvedViewKey);
  }, [taskId, viewQuery.data]);

  const data = useMemo<SimulationResultExplorerPayload | undefined>(() => {
    if (!bootstrapPayload || !activeViewSlice) {
      return bootstrapPayload;
    }

    return composeSimulationResultExplorerPayload(bootstrapPayload, activeViewSlice);
  }, [activeViewSlice, bootstrapPayload]);
  const resolvedSelection = useMemo(
    () => (data ? buildEditableSelection(data.selection) : null),
    [data],
  );
  const isRefreshingSelection =
    requestedViewKey !== null &&
    activeViewKey !== null &&
    requestedViewKey !== activeViewKey;

  function updateSelection(
    updater: (
      current: EditableExplorerSelection,
      payload: SimulationResultExplorerPayload,
    ) => EditableExplorerSelection,
  ) {
    if (!bootstrapPayload || !effectiveSelection) {
      return;
    }

    setSelection(updater(effectiveSelection, bootstrapPayload));
  }

  return {
    data,
    bootstrap: bootstrapPayload?.bootstrap,
    currentView: activeViewSlice,
    selection: effectiveSelection,
    resolvedSelection,
    selectedFamily,
    error: viewQuery.error ?? bootstrapQuery.error,
    isLoading: bootstrapQuery.isLoading && !data,
    isValidating: bootstrapQuery.isValidating || viewQuery.isValidating,
    isRefreshingSelection,
    async mutate() {
      await Promise.all([bootstrapQuery.mutate(), viewQuery.mutate()]);
    },
    setFamily(nextFamily: string) {
      updateSelection((current, nextPayload) => {
        const family = resolveAvailableExplorerFamily(
          nextPayload.bootstrap.families,
          nextFamily,
        );
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
          compareAxisIndex: nextPayload.selection.compareAxisIndex,
        };
      });
    },
    setSource(nextSource: string) {
      updateSelection((current, nextPayload) => {
        const family = resolveAvailableExplorerFamily(
          nextPayload.bootstrap.families,
          current.family,
        );
        if (!family) {
          return current;
        }

        if (!family.availableSources.some((option) => option.key === nextSource)) {
          return current;
        }

        return {
          ...current,
          source: nextSource,
        };
      });
    },
    setMetric(nextMetric: string) {
      updateSelection((current, nextPayload) => {
        const family = resolveAvailableExplorerFamily(
          nextPayload.bootstrap.families,
          current.family,
        );
        if (!family) {
          return current;
        }

        if (!family.availableMetrics.some((option) => option.key === nextMetric)) {
          return current;
        }

        return {
          ...current,
          metric: nextMetric,
        };
      });
    },
    setSweepValue(axisIndex: number, nextValueIndex: number) {
      updateSelection((current, nextPayload) => {
        const sweepAxes = nextPayload.bootstrap.parameterSweep.axes;
        if (
          !nextPayload.bootstrap.parameterSweep.active ||
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
        const encoded = encodeSimulationExplorerSweepIndex(sweepAxes, coordinates);

        return {
          ...current,
          sweepIndex: encoded,
        };
      });
    },
    setZ0(nextZ0: number) {
      if (!Number.isFinite(nextZ0) || nextZ0 <= 0) {
        return;
      }

      updateSelection((current) => ({
        ...current,
        z0: nextZ0,
      }));
    },
    setOutputPort(nextPort: number) {
      updateSelection((current, nextPayload) => ({
        ...current,
        outputPort: clampSimulationExplorerPort(
          nextPort,
          nextPayload.bootstrap.traceSelector.outputPorts,
        ),
      }));
    },
    setInputPort(nextPort: number) {
      updateSelection((current, nextPayload) => ({
        ...current,
        inputPort: clampSimulationExplorerPort(
          nextPort,
          nextPayload.bootstrap.traceSelector.inputPorts,
        ),
      }));
    },
  };
}
