"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import {
  batchDeleteTraces,
  deleteTrace,
  getTraceDetail,
  getTraceEditDetail,
  listDesignBrowseRows,
  listTraceMetadata,
  traceDetailKey,
  traceEditDetailKey,
  traceListKey,
  updateTrace,
} from "@/lib/api/datasets";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { parseRawDataBrowseState } from "@/features/data-browser/lib/browse-state";
import {
  emptyTraceRows,
  resolveSelectableTraceIds,
  resolveSelectedDesignId,
  resolveSelectedTraceId,
} from "@/features/data-browser/lib/selection";

import type {
  TraceMetadataRow,
  TraceUpdateDraft,
} from "@/features/data-browser/lib/contracts";

type TraceFilters = Readonly<{
  search: string;
  family: string;
  representation: string;
  sourceKind: string;
  traceModeGroup: string;
}>;

type BrowserNotice = Readonly<{
  tone: "success" | "warning";
  message: string;
}> | null;

type PendingDeleteRequest =
  | Readonly<{
      kind: "single";
      traceIds: readonly string[];
      trace: Readonly<{
        traceId: string;
        parameter: string;
        provenanceSummary: string;
      }>;
    }>
  | Readonly<{
      kind: "batch";
      traceIds: readonly string[];
      traces: readonly Readonly<{
        traceId: string;
        parameter: string;
        provenanceSummary: string;
      }>[];
    }>
  | null;

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
  const browseState = useMemo(() => parseRawDataBrowseState(searchParams), [searchParams]);
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(browseState.designId);
  const [focusedTraceId, setFocusedTraceId] = useState<string | null>(browseState.traceId);
  const [selectedTraceIds, setSelectedTraceIds] = useState<readonly string[]>([]);
  const [designCursor, setDesignCursor] = useState<string | null>(null);
  const [traceCursor, setTraceCursor] = useState<string | null>(null);
  const [designSearch, setDesignSearch] = useState(browseState.designQuery ?? "");
  const [filters, setFilters] = useState<TraceFilters>(defaultFilters);
  const [notice, setNotice] = useState<BrowserNotice>(null);
  const [editTraceId, setEditTraceId] = useState<string | null>(null);
  const [isEditSavePending, setIsEditSavePending] = useState(false);
  const [editSaveErrorMessage, setEditSaveErrorMessage] = useState<string | null>(null);
  const [pendingDeleteRequest, setPendingDeleteRequest] = useState<PendingDeleteRequest>(null);
  const [isDeletePending, setIsDeletePending] = useState(false);

  const designsQuery = useSWR(
    activeDatasetId ? ["designs", activeDatasetId, designSearch, designCursor] : null,
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
      ? traceListKey(activeDatasetId, resolvedDesignId, {
          cursor: traceCursor,
          search: filters.search || null,
          family: filters.family || null,
          representation: filters.representation || null,
          sourceKind: filters.sourceKind || null,
          traceModeGroup: filters.traceModeGroup || null,
        })
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

  const resolvedFocusedTraceId = resolveSelectedTraceId(focusedTraceId, tracesQuery.data?.rows);

  const traceDetailQuery = useSWR(
    activeDatasetId && resolvedDesignId && resolvedFocusedTraceId
      ? traceDetailKey(activeDatasetId, resolvedDesignId, resolvedFocusedTraceId)
      : null,
    () =>
      activeDatasetId && resolvedDesignId && resolvedFocusedTraceId
        ? getTraceDetail(activeDatasetId, resolvedDesignId, resolvedFocusedTraceId)
        : Promise.resolve(undefined),
  );

  const traceEditDetailQuery = useSWR(
    activeDatasetId && resolvedDesignId && editTraceId
      ? traceEditDetailKey(activeDatasetId, resolvedDesignId, editTraceId)
      : null,
    () =>
      activeDatasetId && resolvedDesignId && editTraceId
        ? getTraceEditDetail(activeDatasetId, resolvedDesignId, editTraceId)
        : Promise.resolve(undefined),
  );

  const traces = tracesQuery.data?.rows ?? emptyTraceRows;
  const deletableVisibleTraceIds = useMemo(
    () =>
      traces
        .filter((trace) => trace.allowed_actions.delete)
        .map((trace) => trace.trace_id),
    [traces],
  );
  const allVisibleDeletableTracesSelected =
    deletableVisibleTraceIds.length > 0 &&
    deletableVisibleTraceIds.every((traceId) => selectedTraceIds.includes(traceId));
  const focusedTraceSummary =
    traces.find((trace) => trace.trace_id === resolvedFocusedTraceId) ?? null;

  useEffect(() => {
    setSelectedDesignId((current) => resolveSelectedDesignId(current, designsQuery.data?.rows));
  }, [designsQuery.data?.rows]);

  useEffect(() => {
    setFocusedTraceId((current) => resolveSelectedTraceId(current, tracesQuery.data?.rows));
  }, [tracesQuery.data?.rows]);

  useEffect(() => {
    setSelectedTraceIds((current) => resolveSelectableTraceIds(current, traces));
  }, [traces]);

  useEffect(() => {
    setSelectedDesignId(browseState.designId);
    setFocusedTraceId(browseState.traceId);
    setSelectedTraceIds([]);
    setDesignCursor(null);
    setTraceCursor(null);
    setDesignSearch(browseState.designQuery ?? "");
    setFilters(defaultFilters);
    setEditTraceId(null);
    setPendingDeleteRequest(null);
    setEditSaveErrorMessage(null);
    setNotice(null);
  }, [activeDatasetId, browseState.designId, browseState.designQuery, browseState.traceId]);

  useEffect(() => {
    setTraceCursor(null);
    setFocusedTraceId(null);
    setSelectedTraceIds([]);
    setEditTraceId(null);
    setPendingDeleteRequest(null);
    setEditSaveErrorMessage(null);
  }, [resolvedDesignId]);

  function isTraceSelected(traceId: string) {
    return selectedTraceIds.includes(traceId);
  }

  function focusTrace(traceId: string) {
    setFocusedTraceId(traceId);
  }

  function toggleTraceSelection(traceId: string) {
    const trace = traces.find((row) => row.trace_id === traceId);
    if (!trace?.allowed_actions.delete) {
      return;
    }

    setSelectedTraceIds((current) =>
      current.includes(traceId)
        ? current.filter((currentTraceId) => currentTraceId !== traceId)
        : [...current, traceId],
    );
  }

  function toggleSelectAllVisibleTraces() {
    setSelectedTraceIds(
      allVisibleDeletableTracesSelected ? [] : [...deletableVisibleTraceIds],
    );
  }

  function clearSelectedTraceIds() {
    setSelectedTraceIds([]);
  }

  function openEditDialog(traceId: string) {
    setEditTraceId(traceId);
    setEditSaveErrorMessage(null);
    setNotice(null);
  }

  function closeEditDialog() {
    if (isEditSavePending) {
      return;
    }
    setEditTraceId(null);
    setEditSaveErrorMessage(null);
  }

  function requestSingleDelete(trace: TraceMetadataRow) {
    if (!trace.allowed_actions.delete) {
      return;
    }
    setNotice(null);
    setPendingDeleteRequest({
      kind: "single",
      traceIds: [trace.trace_id],
      trace: {
        traceId: trace.trace_id,
        parameter: trace.parameter,
        provenanceSummary: trace.provenance_summary,
      },
    });
  }

  function requestBatchDeleteSelectedTraces() {
    const selectedTraceRows = traces.filter(
      (trace) => trace.allowed_actions.delete && selectedTraceIds.includes(trace.trace_id),
    );
    const traceIds = selectedTraceRows.map((trace) => trace.trace_id);
    if (traceIds.length === 0) {
      return;
    }
    setNotice(null);
    setPendingDeleteRequest({
      kind: "batch",
      traceIds,
      traces: selectedTraceRows.map((trace) => ({
        traceId: trace.trace_id,
        parameter: trace.parameter,
        provenanceSummary: trace.provenance_summary,
      })),
    });
  }

  function closeDeleteDialog() {
    if (isDeletePending) {
      return;
    }
    setPendingDeleteRequest(null);
  }

  async function saveEditedTrace(draft: TraceUpdateDraft) {
    if (!activeDatasetId || !resolvedDesignId || !editTraceId) {
      return;
    }

    setIsEditSavePending(true);
    setEditSaveErrorMessage(null);
    try {
      const result = await updateTrace(activeDatasetId, resolvedDesignId, editTraceId, draft);

      await tracesQuery.mutate(
        (current) =>
          current
            ? {
                ...current,
                rows: current.rows.map((row) =>
                  row.trace_id === result.trace.trace_id ? result.trace : row,
                ),
              }
            : current,
        { revalidate: false },
      );

      if (resolvedFocusedTraceId === result.trace.trace_id) {
        await traceDetailQuery.mutate();
      }

      setEditTraceId(null);
      setNotice({
        tone: "success",
        message: `Trace ${result.trace.parameter} was updated.`,
      });
    } catch (error) {
      setEditSaveErrorMessage(
        error instanceof Error ? error.message : "Unable to save the trace changes.",
      );
    } finally {
      setIsEditSavePending(false);
    }
  }

  async function confirmDeleteRequest() {
    if (!activeDatasetId || !resolvedDesignId || !pendingDeleteRequest) {
      return;
    }

    setIsDeletePending(true);
    try {
      const result =
        pendingDeleteRequest.kind === "single"
          ? await deleteTrace(
              activeDatasetId,
              resolvedDesignId,
              pendingDeleteRequest.traceIds[0] ?? "",
            )
          : await batchDeleteTraces(
              activeDatasetId,
              resolvedDesignId,
              pendingDeleteRequest.traceIds,
            );
      const deletedTraceIds = new Set(result.deleted_trace_ids);

      await tracesQuery.mutate(
        (current) =>
          current
            ? {
                ...current,
                rows: current.rows.filter((row) => !deletedTraceIds.has(row.trace_id)),
              }
            : current,
        { revalidate: false },
      );

      await designsQuery.mutate(
        (current) =>
          current && result.design
            ? {
                ...current,
                rows: current.rows.map((row) =>
                  row.design_id === result.design?.design_id ? result.design : row,
                ),
              }
            : current,
        { revalidate: false },
      );

      setSelectedTraceIds((current) =>
        current.filter((traceId) => !deletedTraceIds.has(traceId)),
      );
      setFocusedTraceId((current) =>
        current && deletedTraceIds.has(current) ? null : current,
      );
      setEditTraceId((current) =>
        current && deletedTraceIds.has(current) ? null : current,
      );
      setPendingDeleteRequest(null);
      setNotice({
        tone: "success",
        message:
          result.deleted_trace_ids.length === 1
            ? "The trace was deleted from this design."
            : `${result.deleted_trace_ids.length} traces were deleted from this design.`,
      });

      if (resolvedFocusedTraceId && deletedTraceIds.has(resolvedFocusedTraceId)) {
        await traceDetailQuery.mutate(undefined, { revalidate: false });
      }
    } catch (error) {
      setNotice({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to delete the selected traces.",
      });
    } finally {
      setIsDeletePending(false);
    }
  }

  return {
    activeDatasetState,
    notice,
    clearNotice() {
      setNotice(null);
    },
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
    traces,
    tracesMeta: tracesQuery.data?.meta,
    tracesError: tracesQuery.error as Error | undefined,
    isTracesLoading: tracesQuery.isLoading,
    focusedTraceId: resolvedFocusedTraceId,
    focusedTraceSummary,
    focusTrace,
    goToNextTracePage() {
      setTraceCursor(tracesQuery.data?.meta?.next_cursor ?? null);
    },
    goToPrevTracePage() {
      setTraceCursor(tracesQuery.data?.meta?.prev_cursor ?? null);
    },
    selectedTraceIds,
    selectedTraceCount: selectedTraceIds.length,
    isTraceSelected,
    toggleTraceSelection,
    toggleSelectAllVisibleTraces,
    clearSelectedTraceIds,
    canSelectVisibleTraces: deletableVisibleTraceIds.length > 0,
    allVisibleDeletableTracesSelected,
    traceDetail: traceDetailQuery.data,
    traceDetailError: traceDetailQuery.error as Error | undefined,
    isTraceDetailLoading: traceDetailQuery.isLoading,
    editTraceId,
    openEditDialog,
    closeEditDialog,
    traceEditDetail: traceEditDetailQuery.data ?? null,
    traceEditDetailError: traceEditDetailQuery.error as Error | undefined,
    isTraceEditDetailLoading: traceEditDetailQuery.isLoading,
    saveEditedTrace,
    isEditSavePending,
    editSaveErrorMessage,
    pendingDeleteRequest,
    requestSingleDelete,
    requestBatchDeleteSelectedTraces,
    closeDeleteDialog,
    confirmDeleteRequest,
    isDeletePending,
  };
}
