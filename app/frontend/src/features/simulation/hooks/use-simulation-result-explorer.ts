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
  buildSimulationResultExplorerSelectionCacheKey,
  composeSimulationResultExplorerPayload,
  extractSimulationResultExplorerViewSlice,
  primeSimulationResultExplorerViewCache,
  type EditableExplorerSelection,
} from "../lib/simulation-result-explorer-state";
import {
  buildExplorerSelectionUpdateContext,
  deriveSimulationResultExplorerState,
  updateExplorerCompareAxisSelection,
  updateExplorerFamilySelection,
  updateExplorerInputPortSelection,
  updateExplorerMetricSelection,
  updateExplorerOutputPortSelection,
  updateExplorerSourceSelection,
  updateExplorerSweepValueSelection,
  updateExplorerZ0Selection,
  type ExplorerSelectionUpdateContext,
} from "../lib/simulation-result-explorer-selection";

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
  const {
    bootstrapSelection,
    effectiveSelection,
    selectedFamily,
    viewQueryInput,
    bootstrapViewKey,
    requestedViewKey,
    isRefreshingSelection,
  } = useMemo(
    () =>
      deriveSimulationResultExplorerState({
        taskId,
        bootstrapPayload,
        selection,
        activeViewKey,
      }),
    [activeViewKey, bootstrapPayload, selection, taskId],
  );

  useEffect(() => {
    if (!bootstrapPayload || taskId === null || !bootstrapViewKey) {
      return;
    }

    setSelection((current) => current ?? bootstrapSelection);

    const cachedBootstrapView = viewCacheRef.current.get(bootstrapViewKey);
    if (!cachedBootstrapView) {
      return;
    }

    setActiveViewSlice((current) => current ?? cachedBootstrapView);
    setActiveViewKey((current) => current ?? bootstrapViewKey);
  }, [bootstrapSelection, bootstrapViewKey, bootstrapPayload, taskId]);

  useEffect(() => {
    if (!requestedViewKey) {
      return;
    }

    const cachedView = viewCacheRef.current.get(requestedViewKey);
    if (cachedView) {
      setActiveViewSlice(cachedView);
      setActiveViewKey(requestedViewKey);
    }
  }, [requestedViewKey]);

  const shouldFetchView =
    enabled &&
    taskId !== null &&
    viewQueryInput !== undefined &&
    requestedViewKey !== null &&
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
      return undefined;
    }

    return composeSimulationResultExplorerPayload(bootstrapPayload, activeViewSlice);
  }, [activeViewSlice, bootstrapPayload]);
  const resolvedSelection = useMemo(
    () => (data ? buildEditableSelection(data.selection) : null),
    [data],
  );

  function updateSelection(
    updater: (
      current: EditableExplorerSelection,
      context: ExplorerSelectionUpdateContext,
    ) => EditableExplorerSelection,
  ) {
    if (!bootstrapPayload || !effectiveSelection) {
      return;
    }

    const context = buildExplorerSelectionUpdateContext(bootstrapPayload, resolvedSelection);
    if (!context) {
      return;
    }

    setSelection(
      updater(effectiveSelection, context),
    );
  }

  return {
    data,
    bootstrap: bootstrapPayload?.bootstrap,
    currentView: activeViewSlice,
    selection: effectiveSelection,
    resolvedSelection,
    selectedFamily,
    error: viewQuery.error ?? bootstrapQuery.error,
    isLoading:
      !data &&
      (bootstrapQuery.isLoading ||
        (enabled && taskId !== null && bootstrapPayload !== undefined && viewQuery.isLoading)),
    isValidating: bootstrapQuery.isValidating || viewQuery.isValidating,
    isRefreshingSelection,
    async mutate() {
      await Promise.all([bootstrapQuery.mutate(), viewQuery.mutate()]);
    },
    setFamily(nextFamily: string) {
      updateSelection((current, context) =>
        updateExplorerFamilySelection(current, context, nextFamily),
      );
    },
    setSource(nextSource: string) {
      updateSelection((current, context) =>
        updateExplorerSourceSelection(current, context, nextSource),
      );
    },
    setMetric(nextMetric: string) {
      updateSelection((current, context) =>
        updateExplorerMetricSelection(current, context, nextMetric),
      );
    },
    setSweepValue(axisIndex: number, nextValueIndex: number) {
      updateSelection((current, context) =>
        updateExplorerSweepValueSelection(current, context, axisIndex, nextValueIndex),
      );
    },
    setCompareAxis(nextAxisIndex: number) {
      updateSelection((current, context) =>
        updateExplorerCompareAxisSelection(current, context, nextAxisIndex),
      );
    },
    setZ0(nextZ0: number) {
      updateSelection((current) => updateExplorerZ0Selection(current, nextZ0));
    },
    setOutputPort(nextPort: number) {
      updateSelection((current, context) =>
        updateExplorerOutputPortSelection(current, context, nextPort),
      );
    },
    setInputPort(nextPort: number) {
      updateSelection((current, context) =>
        updateExplorerInputPortSelection(current, context, nextPort),
      );
    },
  };
}
