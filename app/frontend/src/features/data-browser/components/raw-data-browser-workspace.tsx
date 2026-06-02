"use client";

import { useDeferredValue, useMemo, useState } from "react";

import { RawDataDesignScopesPanel } from "@/features/data-browser/components/raw-data-design-scopes-panel";
import { SearchField } from "@/features/data-browser/components/raw-data-browser-controls";
import { RawDataTracePreviewPanel } from "@/features/data-browser/components/raw-data-trace-preview-panel";
import { RawDataTraceSummariesPanel } from "@/features/data-browser/components/raw-data-trace-summaries-panel";
import { TraceEditDialog } from "@/features/data-browser/components/trace-edit-dialog";
import {
  formatCoverage,
  readinessTone,
} from "@/features/data-browser/lib/raw-data-browser-formatters";
import {
  useRawDataBrowserData,
  type RawDataBrowserState,
} from "@/features/data-browser/hooks/use-raw-data-browser-data";
import { useRawDataPreviewDrawer } from "@/features/data-browser/hooks/use-raw-data-preview-drawer";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";
import {
  SurfaceActionButton,
  SurfaceHeader,
  SurfacePanel,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";

import type { DesignBrowseRow } from "@/features/data-browser/lib/contracts";

function designLifecycleTone(state: DesignBrowseRow["lifecycle_state"]) {
  if (state === "active") {
    return "success" as const;
  }
  if (state === "archived") {
    return "warning" as const;
  }
  return "default" as const;
}

function DesignBrowserPanel({
  deferredDesignSearch,
  browser,
  selectedDesign,
  isDesignManagementOpen,
  toggleDesignManagement,
}: Readonly<{
  deferredDesignSearch: string;
  browser: RawDataBrowserState;
  selectedDesign: DesignBrowseRow | null;
  isDesignManagementOpen: boolean;
  toggleDesignManagement: () => void;
}>) {
  return (
    <SurfacePanel
      title="Design Browser"
      actions={
        <SurfaceActionButton
          aria-expanded={isDesignManagementOpen}
          onClick={toggleDesignManagement}
          shape="soft"
        >
          {isDesignManagementOpen ? "Hide Management" : "Manage Scopes"}
        </SurfaceActionButton>
      }
    >
      {browser.designsError ? (
        <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
          Unable to load designs. {browser.designsError.message}
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)] lg:items-start">
        <SearchField
          label="Search Design"
          placeholder="Search design name or id"
          value={browser.designSearch}
          onChange={browser.setDesignSearch}
        />
        <div className="min-w-0 rounded-[0.95rem] border border-border/80 bg-surface px-4 py-3">
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Current Design
          </p>
          {selectedDesign ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="min-w-0 break-words text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                {selectedDesign.name}
              </span>
              <SurfaceTag tone={readinessTone(selectedDesign.compare_readiness)}>
                {selectedDesign.compare_readiness}
              </SurfaceTag>
              <SurfaceTag tone={designLifecycleTone(selectedDesign.lifecycle_state)}>
                {selectedDesign.lifecycle_state}
              </SurfaceTag>
              <SurfaceTag tone="default">{selectedDesign.trace_count} traces</SurfaceTag>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">No design selected.</p>
          )}
        </div>
      </div>

      {browser.isDesignsLoading ? (
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          Loading designs for {deferredDesignSearch || "the active dataset"}...
        </div>
      ) : browser.designs.length > 0 ? (
        <>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {browser.designs.map((design) => (
              <button
                key={design.design_id}
                type="button"
                aria-pressed={design.design_id === browser.selectedDesignId}
                title={design.design_id}
                onClick={() => {
                  browser.setSelectedDesignId(design.design_id);
                }}
                className={cx(
                  "min-h-[6.5rem] cursor-pointer rounded-xl border px-4 py-3 text-left transition hover:border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                  design.design_id === browser.selectedDesignId
                    ? "border-primary/40 bg-primary/10"
                    : "border-border bg-background",
                )}
              >
                <div className="flex h-full flex-col justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="break-words text-sm font-semibold text-foreground [overflow-wrap:anywhere]">
                      {design.name}
                    </h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatCoverage(design.source_coverage)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SurfaceTag tone={readinessTone(design.compare_readiness)}>
                      {design.compare_readiness}
                    </SurfaceTag>
                    <SurfaceTag tone="default">{design.trace_count} traces</SurfaceTag>
                  </div>
                </div>
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/80 pt-4 text-sm">
            <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
              {browser.designsMeta?.limit ?? 6} designs per page
            </p>
            <div className="flex items-center gap-2">
              <SurfaceActionButton
                onClick={browser.goToPrevDesignPage}
                disabled={!browser.designsMeta?.prev_cursor}
                shape="soft"
              >
                Previous
              </SurfaceActionButton>
              <SurfaceActionButton
                onClick={browser.goToNextDesignPage}
                disabled={!browser.designsMeta?.next_cursor}
                shape="soft"
              >
                Next
              </SurfaceActionButton>
            </div>
          </div>
        </>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          No design scopes are available for this dataset.
        </div>
      )}
    </SurfacePanel>
  );
}

function DeleteScopeCard({
  title,
  items,
}: Readonly<{
  title: string;
  items: readonly Readonly<{
    label: string;
    value: string;
  }>[];
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-surface px-4 py-4">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <dl className="mt-3 space-y-2 text-sm">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col gap-1">
            <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              {item.label}
            </dt>
            <dd className="break-all text-muted-foreground">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function DeleteScopeList({
  traces,
  totalCount,
}: Readonly<{
  traces: readonly Readonly<{
    traceId: string;
    parameter: string;
    provenanceSummary: string;
  }>[];
  totalCount: number;
}>) {
  const visibleTraces = traces.slice(0, 4);
  const hiddenCount = Math.max(totalCount - visibleTraces.length, 0);

  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-surface px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        Delete Scope
      </p>
      <div className="mt-3 space-y-3">
        {visibleTraces.map((trace) => (
          <div
            key={trace.traceId}
            className="rounded-[0.85rem] border border-border/70 bg-background px-3 py-3"
          >
            <p className="text-sm font-medium text-foreground">{trace.parameter}</p>
            <p className="mt-1 break-all text-xs text-muted-foreground">{trace.traceId}</p>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {trace.provenanceSummary}
            </p>
          </div>
        ))}
        {hiddenCount > 0 ? (
          <p className="text-xs text-muted-foreground">
            +{hiddenCount} more selected traces in this delete request.
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function RawDataBrowserWorkspace() {
  const browser = useRawDataBrowserData();
  const deferredDesignSearch = useDeferredValue(browser.designSearch);
  const deferredTraceSearch = useDeferredValue(browser.filters.search);
  const [previewMode, setPreviewMode] = useState<"plot" | "table">("plot");
  const [isDesignManagementOpen, setIsDesignManagementOpen] = useState(false);

  const selectedDesign =
    browser.designs.find((row) => row.design_id === browser.selectedDesignId) ?? null;
  const focusedTraceSummary =
    browser.traces.find((row) => row.trace_id === browser.focusedTraceId) ?? null;

  const showDesktopPreviewRail = selectedDesign !== null;
  const {
    traceSummariesSectionRef,
    desktopPreviewRailRef,
    isDesktopPreviewDrawerPinned,
    desktopPreviewDrawerFrame,
    desktopPreviewDrawerTop,
  } = useRawDataPreviewDrawer({
    enabled: showDesktopPreviewRail && Boolean(browser.focusedTraceId),
  });

  const shouldShowDesktopPreviewDrawer =
    showDesktopPreviewRail && Boolean(browser.focusedTraceId) && isDesktopPreviewDrawerPinned;

  const previewPanelClassName =
    "border-border/90 shadow-[0_18px_42px_rgba(15,23,42,0.14)] transition-[box-shadow] duration-200";
  const previewDrawerPanelClassName = "border-border/90 shadow-none";

  const traceDeleteDialog = useMemo(() => {
    if (!browser.pendingDeleteRequest) {
      return null;
    }

    if (browser.pendingDeleteRequest.kind === "single") {
      return {
        title: "Delete Trace",
        description:
          "Delete this saved trace from the current design? This removes the summary row immediately and clears the preview if the focused trace is deleted.",
        confirmLabel: "Delete Trace",
        details: (
          <DeleteScopeCard
            title={browser.pendingDeleteRequest.trace.parameter}
            items={[
              {
                label: "Trace ID",
                value: browser.pendingDeleteRequest.trace.traceId,
              },
              {
                label: "Context",
                value: browser.pendingDeleteRequest.trace.provenanceSummary,
              },
            ]}
          />
        ),
      };
    }

    return {
      title: "Delete Selected Traces",
      description: `Delete ${browser.pendingDeleteRequest.traceIds.length} selected traces from this design? This removes each listed row immediately and safely resolves any deleted preview focus.`,
      confirmLabel: `Delete ${browser.pendingDeleteRequest.traceIds.length} Traces`,
      details: (
        <DeleteScopeList
          traces={browser.pendingDeleteRequest.traces}
          totalCount={browser.pendingDeleteRequest.traceIds.length}
        />
      ),
    };
  }, [browser.pendingDeleteRequest]);

  return (
    <div className="space-y-6">
      <SurfaceHeader
        eyebrow="Raw Data Browser"
        title="Raw Data"
        description="Choose a design, browse trace summaries, and preview one focused trace."
      />

      <DesignBrowserPanel
        deferredDesignSearch={deferredDesignSearch}
        browser={browser}
        selectedDesign={selectedDesign}
        isDesignManagementOpen={isDesignManagementOpen}
        toggleDesignManagement={() => {
          setIsDesignManagementOpen((current) => !current);
        }}
      />

      {isDesignManagementOpen ? (
        <RawDataDesignScopesPanel
          designsError={browser.designsError}
          isDesignsLoading={browser.isDesignsLoading}
          deferredDesignSearch={deferredDesignSearch}
          designSearch={browser.designSearch}
          setDesignSearch={browser.setDesignSearch}
          designs={browser.designs}
          selectedDesignId={browser.selectedDesignId}
          setSelectedDesignId={browser.setSelectedDesignId}
          selectedDesign={selectedDesign}
          designsMeta={browser.designsMeta}
          goToPrevDesignPage={browser.goToPrevDesignPage}
          goToNextDesignPage={browser.goToNextDesignPage}
          activeDesigns={browser.activeDesigns}
          designLifecycleState={browser.designLifecycleState}
          createDesignScope={browser.createDesignScope}
          renameSelectedDesignScope={browser.renameSelectedDesignScope}
          mergeSelectedDesignScope={browser.mergeSelectedDesignScope}
          archiveSelectedDesignScope={browser.archiveSelectedDesignScope}
          deleteSelectedDesignScope={browser.deleteSelectedDesignScope}
        />
      ) : null}

      <section
        ref={traceSummariesSectionRef}
        className={cx(
          "space-y-5",
          showDesktopPreviewRail &&
            "xl:grid xl:grid-cols-[minmax(0,1fr)_28rem] xl:items-start xl:gap-5 xl:space-y-0",
        )}
      >
        <RawDataTraceSummariesPanel
          notice={browser.notice}
          tracesError={browser.tracesError}
          deferredTraceSearch={deferredTraceSearch}
          filters={browser.filters}
          setFilters={browser.setFilters}
          isTracesLoading={browser.isTracesLoading}
          traces={browser.traces}
          selectedTraceCount={browser.selectedTraceCount}
          canSelectVisibleTraces={browser.canSelectVisibleTraces}
          allVisibleDeletableTracesSelected={browser.allVisibleDeletableTracesSelected}
          toggleSelectAllVisibleTraces={browser.toggleSelectAllVisibleTraces}
          clearSelectedTraceIds={browser.clearSelectedTraceIds}
          requestBatchDeleteSelectedTraces={browser.requestBatchDeleteSelectedTraces}
          tracesMeta={browser.tracesMeta}
          goToPrevTracePage={browser.goToPrevTracePage}
          goToNextTracePage={browser.goToNextTracePage}
          focusedTraceId={browser.focusedTraceId}
          isTraceSelected={browser.isTraceSelected}
          focusTrace={browser.focusTrace}
          toggleTraceSelection={browser.toggleTraceSelection}
          openEditDialog={browser.openEditDialog}
          requestSingleDelete={browser.requestSingleDelete}
        />

        {showDesktopPreviewRail ? (
          <div ref={desktopPreviewRailRef} className="hidden xl:block xl:self-start">
            <div
              aria-hidden={shouldShowDesktopPreviewDrawer}
              inert={shouldShowDesktopPreviewDrawer}
              className={cx(
                "transition-[opacity,transform] duration-200 ease-out",
                shouldShowDesktopPreviewDrawer
                  ? "pointer-events-none translate-y-1 opacity-0"
                  : "translate-y-0 opacity-100",
              )}
            >
              <RawDataTracePreviewPanel
                traceDetail={browser.traceDetail}
                traceDetailError={browser.traceDetailError}
                isTraceDetailLoading={browser.isTraceDetailLoading}
                focusedTraceSummary={focusedTraceSummary}
                previewMode={previewMode}
                setPreviewMode={setPreviewMode}
                className={previewPanelClassName}
              />
            </div>
          </div>
        ) : null}

        <div className="xl:hidden">
          <RawDataTracePreviewPanel
            traceDetail={browser.traceDetail}
            traceDetailError={browser.traceDetailError}
            isTraceDetailLoading={browser.isTraceDetailLoading}
            focusedTraceSummary={focusedTraceSummary}
            previewMode={previewMode}
            setPreviewMode={setPreviewMode}
            className={previewPanelClassName}
          />
        </div>
      </section>

      {showDesktopPreviewRail &&
      browser.focusedTraceId &&
      desktopPreviewDrawerFrame &&
      desktopPreviewDrawerTop !== null ? (
        <div
          aria-hidden={!shouldShowDesktopPreviewDrawer}
          inert={!shouldShowDesktopPreviewDrawer}
          className={cx(
            "pointer-events-none fixed z-30 hidden transition-[opacity,transform] duration-200 ease-out xl:block",
            shouldShowDesktopPreviewDrawer
              ? "translate-y-0 opacity-100"
              : "translate-y-3 opacity-0",
          )}
          style={{
            left: `${desktopPreviewDrawerFrame.left}px`,
            top: `${desktopPreviewDrawerTop}px`,
            width: `${desktopPreviewDrawerFrame.width}px`,
          }}
        >
          <div className="pointer-events-auto rounded-[1.1rem] shadow-[0_18px_42px_rgba(15,23,42,0.14)]">
            <div className="max-h-[calc(100vh-var(--shell-header-height)-2rem)] overflow-y-auto rounded-[1.1rem]">
              <RawDataTracePreviewPanel
                traceDetail={browser.traceDetail}
                traceDetailError={browser.traceDetailError}
                isTraceDetailLoading={browser.isTraceDetailLoading}
                focusedTraceSummary={focusedTraceSummary}
                previewMode={previewMode}
                setPreviewMode={setPreviewMode}
                className={previewDrawerPanelClassName}
              />
            </div>
          </div>
        </div>
      ) : null}

      <TraceEditDialog
        open={Boolean(browser.editTraceId)}
        detail={browser.traceEditDetail}
        isLoading={browser.isTraceEditDetailLoading}
        error={browser.traceEditDetailError}
        saveErrorMessage={browser.editSaveErrorMessage}
        isSaving={browser.isEditSavePending}
        onClose={browser.closeEditDialog}
        onSave={browser.saveEditedTrace}
      />

      <ConfirmActionDialog
        open={Boolean(browser.pendingDeleteRequest && traceDeleteDialog)}
        title={traceDeleteDialog?.title ?? "Delete Trace"}
        description={traceDeleteDialog?.description ?? "Delete the selected traces from this design."}
        details={traceDeleteDialog?.details}
        confirmLabel={traceDeleteDialog?.confirmLabel ?? "Delete Trace"}
        tone="destructive"
        isPending={browser.isDeletePending}
        onCancel={browser.closeDeleteDialog}
        onConfirm={() => {
          void browser.confirmDeleteRequest();
        }}
      />
    </div>
  );
}
