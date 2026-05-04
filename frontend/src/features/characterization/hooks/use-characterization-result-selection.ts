"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";

import {
  characterizationResultDetailKey,
  getCharacterizationResult,
} from "@/features/characterization/lib/api";
import type { CharacterizationResultSummary } from "@/features/characterization/lib/contracts";
import {
  resolveCharacterizationResultSelection,
  type CharacterizationResultSelectionSource,
} from "@/features/characterization/lib/workflow";

export type CharacterizationCompletedResultIntent = Readonly<{
  taskId: number;
  analysisId: string;
  resultId: string | null;
}>;

function isNotFoundError(error: unknown) {
  if (!(error instanceof Error)) {
    return false;
  }

  return (
    error.message.toLowerCase().includes("not found") ||
    error.message.toLowerCase().includes("not available")
  );
}

export function useCharacterizationResultSelection(input: Readonly<{
  activeDatasetId: string | null;
  resolvedDesignId: string | null;
  requestedResultId: string | null;
  results: readonly CharacterizationResultSummary[] | undefined;
  hasResolvedResults: boolean;
  completedRunIntent: CharacterizationCompletedResultIntent | null;
  taskHandoffResultId: string | null;
}>) {
  const [userSelectedResultId, setUserSelectedResultId] = useState<string | null>(null);
  const [invalidRequestedResultId, setInvalidRequestedResultId] = useState<string | null>(null);

  useEffect(() => {
    setUserSelectedResultId(null);
    setInvalidRequestedResultId(null);
  }, [input.activeDatasetId, input.resolvedDesignId, input.requestedResultId]);

  const hasUserRouteOverride =
    Boolean(userSelectedResultId) && userSelectedResultId !== input.requestedResultId;
  const routeResultId = hasUserRouteOverride ? null : input.requestedResultId;
  const completedRunResultId = routeResultId
    ? null
    : input.completedRunIntent?.resultId ?? null;
  const taskHandoffResultId =
    routeResultId || userSelectedResultId ? null : input.taskHandoffResultId;
  const selection = resolveCharacterizationResultSelection({
    requestedResultId: routeResultId,
    userSelectedResultId,
    completedRunResultId,
    taskHandoffResultId,
    results: input.results,
    hasResolvedResults: input.hasResolvedResults,
    requestedResultUnavailable:
      Boolean(routeResultId) &&
      routeResultId === invalidRequestedResultId,
  });
  const resolvedResultId = selection.resultId;
  const detailKey =
    input.activeDatasetId && input.resolvedDesignId && resolvedResultId
      ? characterizationResultDetailKey(
          input.activeDatasetId,
          input.resolvedDesignId,
          resolvedResultId,
        )
      : null;
  const detailQuery = useSWR(
    detailKey,
    () =>
      input.activeDatasetId && input.resolvedDesignId && resolvedResultId
        ? getCharacterizationResult(
            input.activeDatasetId,
            input.resolvedDesignId,
            resolvedResultId,
          )
        : Promise.resolve(undefined),
  );

  useEffect(() => {
    if (
      selection.source !== "route" ||
      !input.requestedResultId ||
      !detailQuery.error ||
      !isNotFoundError(detailQuery.error)
    ) {
      return;
    }

    setInvalidRequestedResultId(input.requestedResultId);
  }, [detailQuery.error, input.requestedResultId, selection.source]);

  return {
    requestedResultId: input.requestedResultId,
    selectedResultId: resolvedResultId,
    setSelectedResultId: setUserSelectedResultId,
    resultSelectionSource: selection.source as CharacterizationResultSelectionSource,
    isExplicitRouteResultPending: selection.isExplicitRoutePending,
    resultDetail: detailQuery.data,
    resultDetailError: detailQuery.error as Error | undefined,
    isResultDetailLoading: detailQuery.isLoading,
    resultDetailKey: detailKey,
    mutateResultDetail: detailQuery.mutate,
  };
}
