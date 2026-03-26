"use client";

import { useDeferredValue, useMemo, useState } from "react";

import { RawDataDesignScopesPanel } from "@/features/data-browser/components/raw-data-design-scopes-panel";
import { RawDataTracePreviewPanel } from "@/features/data-browser/components/raw-data-trace-preview-panel";
import { RawDataTraceSummariesPanel } from "@/features/data-browser/components/raw-data-trace-summaries-panel";
import { TraceEditDialog } from "@/features/data-browser/components/trace-edit-dialog";
import { useRawDataBrowserData } from "@/features/data-browser/hooks/use-raw-data-browser-data";
import { useRawDataPreviewDrawer } from "@/features/data-browser/hooks/use-raw-data-preview-drawer";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";
import { SurfaceHeader, cx } from "@/features/shared/components/surface-kit";

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
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw Data Browser"
        title="Raw Data"
        description="Choose a design, narrow the trace summaries, edit or delete allowed rows, and keep the preview scoped to one focused trace."
      />

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
      />

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
