"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import {
  getSimulationResultExplorer,
  simulationResultExplorerKey,
  type SimulationResultExplorerFamily,
  type SimulationResultExplorerPayload,
  type SimulationResultExplorerQuery,
  type SimulationResultExplorerSelection,
} from "@/lib/api/tasks";

type EditableExplorerSelection = Readonly<{
  family: string;
  source: string;
  metric: string;
  traceKey: string | null;
  z0: number;
  outputPort: number;
  inputPort: number;
}>;

function buildEditableSelection(
  selection: SimulationResultExplorerSelection,
): EditableExplorerSelection {
  return {
    family: selection.family,
    source: selection.source,
    metric: selection.metric,
    traceKey: selection.traceKey,
    z0: selection.z0Ohm,
    outputPort: selection.outputPort,
    inputPort: selection.inputPort,
  };
}

function resolveAvailableFamily(
  families: readonly SimulationResultExplorerFamily[],
  familyKey: string,
) {
  return families.find((family) => family.key === familyKey) ?? families[0] ?? null;
}

function clampPort(
  nextPort: number,
  ports: readonly Readonly<{ port: number; label: string }>[],
) {
  return ports.some((portOption) => portOption.port === nextPort)
    ? nextPort
    : (ports[0]?.port ?? 1);
}

function buildExplorerQuery(
  selection: EditableExplorerSelection | null,
): SimulationResultExplorerQuery | undefined {
  if (!selection) {
    return undefined;
  }

  return {
    family: selection.family,
    source: selection.source,
    metric: selection.metric,
    z0: selection.z0,
    outputPort: selection.outputPort,
    inputPort: selection.inputPort,
  };
}

export function useSimulationResultExplorer(taskId: number | null, enabled: boolean) {
  const [selection, setSelection] = useState<EditableExplorerSelection | null>(null);

  useEffect(() => {
    setSelection(null);
  }, [taskId]);

  const query = useMemo(() => buildExplorerQuery(selection), [selection]);
  const explorerQuery = useSWR(
    enabled && taskId !== null ? simulationResultExplorerKey(taskId, query) : null,
    () =>
      taskId !== null
        ? getSimulationResultExplorer(taskId, query)
        : Promise.resolve(undefined),
    {
      keepPreviousData: true,
    },
  );

  useEffect(() => {
    const explorerData = explorerQuery.data;
    if (!explorerData) {
      return;
    }

    setSelection((current) =>
      current
        ? {
            ...current,
            traceKey: explorerData.selection.traceKey,
          }
        : buildEditableSelection(explorerData.selection),
    );
  }, [explorerQuery.data]);

  const payload = explorerQuery.data;
  const effectiveSelection =
    selection ?? (payload ? buildEditableSelection(payload.selection) : null);
  const selectedFamily =
    payload && effectiveSelection
      ? resolveAvailableFamily(payload.bootstrap.families, effectiveSelection.family)
      : null;

  function updateSelection(
    updater: (
      current: EditableExplorerSelection,
      payload: SimulationResultExplorerPayload,
    ) => EditableExplorerSelection,
  ) {
    if (!payload || !effectiveSelection) {
      return;
    }

    setSelection(updater(effectiveSelection, payload));
  }

  return {
    ...explorerQuery,
    selection: effectiveSelection,
    selectedFamily,
    setFamily(nextFamily: string) {
      updateSelection((current, nextPayload) => {
        const family = resolveAvailableFamily(nextPayload.bootstrap.families, nextFamily);
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
        };
      });
    },
    setSource(nextSource: string) {
      updateSelection((current, nextPayload) => {
        const family = resolveAvailableFamily(nextPayload.bootstrap.families, current.family);
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
        const family = resolveAvailableFamily(nextPayload.bootstrap.families, current.family);
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
        outputPort: clampPort(nextPort, nextPayload.bootstrap.traceSelector.outputPorts),
      }));
    },
    setInputPort(nextPort: number) {
      updateSelection((current, nextPayload) => ({
        ...current,
        inputPort: clampPort(nextPort, nextPayload.bootstrap.traceSelector.inputPorts),
      }));
    },
  };
}
