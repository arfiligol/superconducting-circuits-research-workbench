"use client";

import useSWR from "swr";

import {
  listCharacterizationAnalysisRegistry,
  listCharacterizationResults,
  listCharacterizationRunHistory,
  listCharacterizationTraceSelectionRows,
} from "@/features/characterization/lib/api";
import {
  resolveSelectedCharacterizationDesignId,
  type CharacterizationResultStatusFilter,
} from "@/features/characterization/lib/workflow";
import { listDesignBrowseRows } from "@/lib/api/datasets";

export function useCharacterizationScopeData(input: Readonly<{
  activeDatasetId: string | null;
  selectedDesignId: string | null;
  selectedTraceIds: readonly string[];
  selectedAnalysisId: string | null;
  runHistoryCursor: string | null;
  resultSearch: string;
  statusFilter: CharacterizationResultStatusFilter;
}>) {
  const designsQuery = useSWR(
    input.activeDatasetId ? ["characterization-designs", input.activeDatasetId] : null,
    () =>
      input.activeDatasetId
        ? listDesignBrowseRows(input.activeDatasetId)
      : Promise.resolve(undefined),
  );
  const resolvedDesignId = resolveSelectedCharacterizationDesignId(
    input.selectedDesignId,
    designsQuery.data?.rows,
  );

  const tracesQuery = useSWR(
    input.activeDatasetId && resolvedDesignId
      ? ["characterization-traces", input.activeDatasetId, resolvedDesignId]
      : null,
    () =>
      input.activeDatasetId && resolvedDesignId
        ? listCharacterizationTraceSelectionRows(input.activeDatasetId, resolvedDesignId)
        : Promise.resolve(undefined),
  );

  const analysisRegistryQuery = useSWR(
    input.activeDatasetId && resolvedDesignId
      ? [
          "characterization-analysis-registry",
          input.activeDatasetId,
          resolvedDesignId,
          ...input.selectedTraceIds,
        ]
      : null,
    () =>
      input.activeDatasetId && resolvedDesignId
        ? listCharacterizationAnalysisRegistry(input.activeDatasetId, resolvedDesignId, {
            selectedTraceIds: input.selectedTraceIds,
          })
        : Promise.resolve(undefined),
  );

  const runHistoryQuery = useSWR(
    input.activeDatasetId && resolvedDesignId
      ? [
          "characterization-run-history",
          input.activeDatasetId,
          resolvedDesignId,
          input.selectedAnalysisId,
          input.runHistoryCursor,
        ]
      : null,
    () =>
      input.activeDatasetId && resolvedDesignId
        ? listCharacterizationRunHistory(input.activeDatasetId, resolvedDesignId, {
            analysisId: input.selectedAnalysisId,
            cursor: input.runHistoryCursor,
          })
        : Promise.resolve(undefined),
  );

  const resultsQuery = useSWR(
    input.activeDatasetId && resolvedDesignId
      ? [
          "characterization-results",
          input.activeDatasetId,
          resolvedDesignId,
          input.resultSearch,
          input.statusFilter,
        ]
      : null,
    () =>
      input.activeDatasetId && resolvedDesignId
        ? listCharacterizationResults(input.activeDatasetId, resolvedDesignId, {
            search: input.resultSearch || null,
            status: input.statusFilter === "all" ? null : input.statusFilter,
          })
        : Promise.resolve(undefined),
  );

  return {
    resolvedDesignId,
    designsQuery,
    tracesQuery,
    analysisRegistryQuery,
    runHistoryQuery,
    resultsQuery,
  };
}
