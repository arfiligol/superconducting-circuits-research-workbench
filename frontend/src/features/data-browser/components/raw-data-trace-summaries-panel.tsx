"use client";

import {
  SelectionCheckbox,
  TraceFilterSelect,
  TraceRowActionButton,
  Search,
  Pencil,
  Trash2,
} from "@/features/data-browser/components/raw-data-browser-controls";
import {
  formatTraceSource,
  formatTraceValue,
} from "@/features/data-browser/lib/raw-data-browser-formatters";
import {
  SurfaceActionButton,
  SurfacePanel,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";

import type {
  CursorMeta,
  TraceMetadataRow,
} from "@/features/data-browser/lib/contracts";

const TRACE_FAMILY_OPTIONS = ["", "s_matrix", "y_matrix", "z_matrix"] as const;
const TRACE_VIEW_OPTIONS = ["", "real", "imaginary", "magnitude", "phase"] as const;
const TRACE_SOURCE_OPTIONS = ["", "measurement", "layout_simulation", "circuit_simulation"] as const;

function TraceSummaryRow({
  trace,
  isFocused,
  isSelected,
  onFocus,
  onToggleSelected,
  onEdit,
  onDelete,
}: Readonly<{
  trace: TraceMetadataRow;
  isFocused: boolean;
  isSelected: boolean;
  onFocus: (traceId: string) => void;
  onToggleSelected: (traceId: string) => void;
  onEdit: (traceId: string) => void;
  onDelete: (trace: TraceMetadataRow) => void;
}>) {
  const hasRowActions = trace.allowed_actions.edit || trace.allowed_actions.delete;

  return (
    <tr
      className={cx("cursor-pointer transition hover:bg-primary/5", isFocused && "bg-primary/10")}
      onClick={() => {
        onFocus(trace.trace_id);
      }}
    >
      <td className="px-3 py-3 align-top">
        <div
          onClick={(event) => {
            event.stopPropagation();
          }}
        >
          <SelectionCheckbox
            ariaLabel={`Select ${trace.trace_id}`}
            checked={isSelected}
            disabled={!trace.allowed_actions.delete}
            onChange={() => {
              onToggleSelected(trace.trace_id);
            }}
          />
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        <p className="font-medium text-foreground">{trace.parameter}</p>
        <p className="mt-1 break-all text-xs text-muted-foreground">{trace.trace_id}</p>
        <p className="mt-2 text-xs text-muted-foreground">{trace.provenance_summary}</p>
      </td>
      <td className="px-4 py-3 align-top text-muted-foreground">{formatTraceValue(trace.family)}</td>
      <td className="px-4 py-3 align-top text-muted-foreground">
        {formatTraceValue(trace.representation)}
      </td>
      <td className="px-4 py-3 align-top text-muted-foreground">
        {formatTraceSource(trace.source_kind)}
      </td>
      <td className="px-4 py-3 align-top">
        {hasRowActions ? (
          <div className="flex min-h-9 flex-wrap items-center gap-2">
            <TraceRowActionButton
              label={trace.allowed_actions.edit ? "Edit trace" : "Edit unavailable"}
              disabled={!trace.allowed_actions.edit}
              icon={<Pencil className="h-3.5 w-3.5" />}
              onClick={() => {
                if (!trace.allowed_actions.edit) {
                  return;
                }
                onEdit(trace.trace_id);
              }}
            />
            {trace.allowed_actions.delete ? (
              <TraceRowActionButton
                label="Delete trace"
                tone="destructive"
                icon={<Trash2 className="h-3.5 w-3.5" />}
                onClick={() => {
                  onDelete(trace);
                }}
              />
            ) : null}
          </div>
        ) : (
          <div className="flex min-h-9 items-center">
            <span
              title={trace.mutation_policy_summary}
              aria-label={`Locked: ${trace.mutation_policy_summary}`}
              className="inline-flex items-center rounded-full border border-border/80 bg-muted/40 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground"
            >
              Locked
            </span>
          </div>
        )}
      </td>
    </tr>
  );
}

export function RawDataTraceSummariesPanel({
  notice,
  tracesError,
  deferredTraceSearch,
  filters,
  setFilters,
  isTracesLoading,
  traces,
  selectedTraceCount,
  canSelectVisibleTraces,
  allVisibleDeletableTracesSelected,
  toggleSelectAllVisibleTraces,
  clearSelectedTraceIds,
  requestBatchDeleteSelectedTraces,
  tracesMeta,
  goToPrevTracePage,
  goToNextTracePage,
  focusedTraceId,
  isTraceSelected,
  focusTrace,
  toggleTraceSelection,
  openEditDialog,
  requestSingleDelete,
}: Readonly<{
  notice: Readonly<{ tone: "success" | "warning"; message: string }> | null;
  tracesError: Error | undefined;
  deferredTraceSearch: string;
  filters: Readonly<{
    search: string;
    family: string;
    representation: string;
    sourceKind: string;
  }>;
  setFilters: (updater: (current: {
    search: string;
    family: string;
    representation: string;
    sourceKind: string;
    traceModeGroup: string;
  }) => {
    search: string;
    family: string;
    representation: string;
    sourceKind: string;
    traceModeGroup: string;
  }) => void;
  isTracesLoading: boolean;
  traces: readonly TraceMetadataRow[];
  selectedTraceCount: number;
  canSelectVisibleTraces: boolean;
  allVisibleDeletableTracesSelected: boolean;
  toggleSelectAllVisibleTraces: () => void;
  clearSelectedTraceIds: () => void;
  requestBatchDeleteSelectedTraces: () => void;
  tracesMeta: CursorMeta | undefined;
  goToPrevTracePage: () => void;
  goToNextTracePage: () => void;
  focusedTraceId: string | null;
  isTraceSelected: (traceId: string) => boolean;
  focusTrace: (traceId: string) => void;
  toggleTraceSelection: (traceId: string) => void;
  openEditDialog: (traceId: string) => void;
  requestSingleDelete: (trace: TraceMetadataRow) => void;
}>) {
  const hasAnySelections = selectedTraceCount > 0;

  return (
    <SurfacePanel
      title="Trace Summaries"
      description="Focused preview stays single-trace, while selected rows drive batch delete only."
    >
      {notice ? (
        <div
          className={cx(
            "mb-4 rounded-[1rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass(notice.tone === "success" ? "success" : "warning"),
          )}
        >
          {notice.message}
        </div>
      ) : null}
      {tracesError ? (
        <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
          Unable to load trace summaries. {tracesError.message}
        </div>
      ) : null}
      <div className="rounded-[1rem] border border-border bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
        <div className="space-y-4">
          <div className="min-w-0">
            <p className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              <Search className="h-3.5 w-3.5" />
              Search
            </p>
            <div className="flex items-center gap-3 rounded-[0.95rem] border border-border/80 bg-background px-3 py-3">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                value={filters.search}
                onChange={(event) => {
                  setFilters((current) => ({
                    ...current,
                    search: event.target.value,
                  }));
                }}
                placeholder="Parameter or note"
                className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <TraceFilterSelect
              label="Family"
              value={filters.family}
              onChange={(value) => {
                setFilters((current) => ({ ...current, family: value }));
              }}
              options={TRACE_FAMILY_OPTIONS}
            />
            <TraceFilterSelect
              label="View"
              value={filters.representation}
              onChange={(value) => {
                setFilters((current) => ({ ...current, representation: value }));
              }}
              options={TRACE_VIEW_OPTIONS}
            />
            <TraceFilterSelect
              label="Source"
              value={filters.sourceKind}
              onChange={(value) => {
                setFilters((current) => ({ ...current, sourceKind: value }));
              }}
              options={TRACE_SOURCE_OPTIONS}
            />
          </div>
        </div>
      </div>

      {isTracesLoading ? (
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          Loading trace summaries for {deferredTraceSearch || "the selected design"}...
        </div>
      ) : traces.length > 0 ? (
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 rounded-[1rem] border border-border bg-surface px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                Batch Selection
              </p>
              <p className="mt-2 text-sm text-foreground">
                {hasAnySelections
                  ? `${selectedTraceCount} traces selected for delete.`
                  : "Select deletable rows without affecting the single-trace preview."}
              </p>
            </div>
            <div className="flex flex-wrap justify-start gap-2 md:justify-end">
              <SurfaceActionButton
                onClick={toggleSelectAllVisibleTraces}
                disabled={!canSelectVisibleTraces}
              >
                {allVisibleDeletableTracesSelected ? "Clear Visible" : "Select Visible"}
              </SurfaceActionButton>
              <SurfaceActionButton onClick={clearSelectedTraceIds} disabled={!hasAnySelections}>
                Clear
              </SurfaceActionButton>
              <SurfaceActionButton
                onClick={requestBatchDeleteSelectedTraces}
                disabled={!hasAnySelections}
                tone="destructive"
                icon={<Trash2 className="h-4 w-4" />}
              >
                Delete Selected
              </SurfaceActionButton>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-border/80">
            <table className="min-w-full table-fixed divide-y divide-border text-sm">
              <thead className="bg-surface">
                <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <th className="w-14 px-3 py-3">
                    <SelectionCheckbox
                      ariaLabel="Select visible deletable traces"
                      checked={allVisibleDeletableTracesSelected}
                      indeterminate={hasAnySelections && !allVisibleDeletableTracesSelected}
                      disabled={!canSelectVisibleTraces}
                      onChange={toggleSelectAllVisibleTraces}
                    />
                  </th>
                  <th className="w-[30%] px-4 py-3">Trace</th>
                  <th className="w-[15%] px-4 py-3">Family</th>
                  <th className="w-[14%] px-4 py-3">View</th>
                  <th className="w-[14%] px-4 py-3">Origin</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {traces.map((trace) => (
                  <TraceSummaryRow
                    key={trace.trace_id}
                    trace={trace}
                    isFocused={trace.trace_id === focusedTraceId}
                    isSelected={isTraceSelected(trace.trace_id)}
                    onFocus={focusTrace}
                    onToggleSelected={toggleTraceSelection}
                    onEdit={openEditDialog}
                    onDelete={requestSingleDelete}
                  />
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between gap-3 border-t border-border bg-surface px-4 py-3 text-sm">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                Up to {tracesMeta?.limit ?? 12} traces per page
              </p>
              <div className="flex items-center gap-2">
                <SurfaceActionButton
                  onClick={goToPrevTracePage}
                  disabled={!tracesMeta?.prev_cursor}
                  shape="soft"
                >
                  Previous
                </SurfaceActionButton>
                <SurfaceActionButton
                  onClick={goToNextTracePage}
                  disabled={!tracesMeta?.next_cursor}
                  shape="soft"
                >
                  Next
                </SurfaceActionButton>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          No trace summaries match the current filters.
        </div>
      )}
    </SurfacePanel>
  );
}
