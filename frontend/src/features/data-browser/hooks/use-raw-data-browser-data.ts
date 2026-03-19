"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import {
  getTraceDetail,
  listDesignBrowseRows,
  listTraceMetadata,
} from "@/lib/api/datasets";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { parseRawDataBrowseState } from "@/features/data-browser/lib/browse-state";
import { resolveSelectedDesignId, resolveSelectedTraceId } from "@/features/data-browser/lib/selection";

type TraceFilters = Readonly<{
  search: string;
  family: string;
  representation: string;
  sourceKind: string;
  traceModeGroup: string;
}>;

const defaultFilters: TraceFilters = {
  search: "",
  family: "",
  representation: "",
  sourceKind: "",
  traceModeGroup: "",
};

export function useRawDataBrowserData() {
  const searchParams = useSearchParams();
  const activeDatasetState = useActiveDataset();
  const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null;
  const browseState = useMemo(
    () => parseRawDataBrowseState(searchParams),
    [searchParams],
  );
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(browseState.designId);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(browseState.traceId);
  const [designCursor, setDesignCursor] = useState<string | null>(null);
  const [traceCursor, setTraceCursor] = useState<string | null>(null);
  const [designSearch, setDesignSearch] = useState(browseState.designQuery ?? "");
  const [filters, setFilters] = useState<TraceFilters>(defaultFilters);

  const designsQuery = useSWR(
    activeDatasetId
      ? ["designs", activeDatasetId, designSearch, designCursor]
      : null,
    () =>
      activeDatasetId
        ? listDesignBrowseRows(activeDatasetId, {
            search: designSearch || null,
            cursor: designCursor,
          })
        : Promise.resolve(undefined),
  );

  const resolvedDesignId = resolveSelectedDesignId(selectedDesignId, designsQuery.data?.rows);

  const tracesQuery = useSWR(
    activeDatasetId && resolvedDesignId
      ? [
          "traces",
          activeDatasetId,
          resolvedDesignId,
          filters.search,
          filters.family,
          filters.representation,
          filters.sourceKind,
          filters.traceModeGroup,
          traceCursor,
        ]
      : null,
    () =>
      activeDatasetId && resolvedDesignId
        ? listTraceMetadata(activeDatasetId, resolvedDesignId, {
            cursor: traceCursor,
            search: filters.search || null,
            family: filters.family || null,
            representation: filters.representation || null,
            sourceKind: filters.sourceKind || null,
            traceModeGroup: filters.traceModeGroup || null,
          })
        : Promise.resolve(undefined),
  );

  const resolvedTraceId = resolveSelectedTraceId(selectedTraceId, tracesQuery.data?.rows);

  const traceDetailQuery = useSWR(
    activeDatasetId && resolvedDesignId && resolvedTraceId
      ? ["trace-detail", activeDatasetId, resolvedDesignId, resolvedTraceId]
      : null,
    () =>
      activeDatasetId && resolvedDesignId && resolvedTraceId
        ? getTraceDetail(activeDatasetId, resolvedDesignId, resolvedTraceId)
        : Promise.resolve(undefined),
  );

  useEffect(() => {
    setSelectedDesignId((current) =>
      resolveSelectedDesignId(current, designsQuery.data?.rows),
    );
  }, [designsQuery.data?.rows]);

  useEffect(() => {
    setSelectedTraceId((current) =>
      resolveSelectedTraceId(current, tracesQuery.data?.rows),
    );
  }, [tracesQuery.data?.rows]);

  useEffect(() => {
    setSelectedDesignId(browseState.designId);
    setSelectedTraceId(browseState.traceId);
    setDesignCursor(null);
    setTraceCursor(null);
    setDesignSearch(browseState.designQuery ?? "");
    setFilters(defaultFilters);
  }, [activeDatasetId, browseState.designId, browseState.designQuery, browseState.traceId]);

  useEffect(() => {
    setTraceCursor(null);
    setSelectedTraceId(null);
  }, [resolvedDesignId]);

  return {
    activeDatasetState,
    designSearch,
    setDesignSearch,
    filters,
    setFilters,
    designs: designsQuery.data?.rows ?? [],
    designsMeta: designsQuery.data?.meta,
    designsError: designsQuery.error as Error | undefined,
    isDesignsLoading: designsQuery.isLoading,
    selectedDesignId: resolvedDesignId,
    setSelectedDesignId,
    goToNextDesignPage() {
      setDesignCursor(designsQuery.data?.meta?.next_cursor ?? null);
    },
    goToPrevDesignPage() {
      setDesignCursor(designsQuery.data?.meta?.prev_cursor ?? null);
    },
    traces: tracesQuery.data?.rows ?? [],
    tracesMeta: tracesQuery.data?.meta,
    tracesError: tracesQuery.error as Error | undefined,
    isTracesLoading: tracesQuery.isLoading,
    selectedTraceId: resolvedTraceId,
    setSelectedTraceId,
    goToNextTracePage() {
      setTraceCursor(tracesQuery.data?.meta?.next_cursor ?? null);
    },
    goToPrevTracePage() {
      setTraceCursor(tracesQuery.data?.meta?.prev_cursor ?? null);
    },
    traceDetail: traceDetailQuery.data,
    traceDetailError: traceDetailQuery.error as Error | undefined,
    isTraceDetailLoading: traceDetailQuery.isLoading,
  };
}
