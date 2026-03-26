"use client";

import { SearchField } from "@/features/data-browser/components/raw-data-browser-controls";
import {
  formatCoverage,
  readinessTone,
} from "@/features/data-browser/lib/raw-data-browser-formatters";
import {
  SurfaceActionButton,
  SurfacePanel,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";

import type { CursorMeta, DesignBrowseRow } from "@/features/data-browser/lib/contracts";

function DesignSummaryTile({
  label,
  value,
}: Readonly<{
  label: string;
  value: string;
}>) {
  return (
    <div className="min-w-0 rounded-[0.85rem] border border-border/80 bg-background px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-sm font-medium text-foreground [overflow-wrap:anywhere]">
        {value}
      </p>
    </div>
  );
}

export function RawDataDesignScopesPanel({
  designsError,
  isDesignsLoading,
  deferredDesignSearch,
  designSearch,
  setDesignSearch,
  designs,
  selectedDesignId,
  setSelectedDesignId,
  selectedDesign,
  designsMeta,
  goToPrevDesignPage,
  goToNextDesignPage,
}: Readonly<{
  designsError: Error | undefined;
  isDesignsLoading: boolean;
  deferredDesignSearch: string;
  designSearch: string;
  setDesignSearch: (value: string) => void;
  designs: readonly DesignBrowseRow[];
  selectedDesignId: string | null;
  setSelectedDesignId: (designId: string) => void;
  selectedDesign: DesignBrowseRow | null;
  designsMeta: CursorMeta | undefined;
  goToPrevDesignPage: () => void;
  goToNextDesignPage: () => void;
}>) {
  return (
    <SurfacePanel
      title="Design Scopes"
      description="Start with a design here, then move straight into trace summaries and the preview path."
    >
      {designsError ? (
        <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
          Unable to load design scopes. {designsError.message}
        </div>
      ) : null}
      {isDesignsLoading ? (
        <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          Loading designs for {deferredDesignSearch || "the active dataset"}...
        </div>
      ) : designs.length > 0 ? (
        <div className="mt-4 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.42fr)] xl:items-start">
          <div className="space-y-4">
            <SearchField
              label="Search Design"
              placeholder="Search design name or id"
              value={designSearch}
              onChange={setDesignSearch}
            />
            <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
              <div className="space-y-3">
                {designs.map((design) => (
                  <button
                    key={design.design_id}
                    type="button"
                    onClick={() => {
                      setSelectedDesignId(design.design_id);
                    }}
                    className={cx(
                      "w-full cursor-pointer rounded-xl border px-4 py-4 text-left transition",
                      design.design_id === selectedDesignId
                        ? "border-primary/40 bg-primary/10"
                        : "border-border bg-background hover:border-primary/25",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-foreground">{design.name}</h3>
                        <p className="mt-1 break-words text-sm text-muted-foreground [overflow-wrap:anywhere]">
                          {formatCoverage(design.source_coverage)}
                        </p>
                      </div>
                      <SurfaceTag tone={readinessTone(design.compare_readiness)}>
                        {design.compare_readiness}
                      </SurfaceTag>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      <span>{design.trace_count} traces</span>
                      <span className="truncate">{design.updated_at}</span>
                    </div>
                  </button>
                ))}
              </div>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-border/80 pt-4 text-sm">
                <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  Up to {designsMeta?.limit ?? 6} design scopes per page
                </p>
                <div className="flex items-center gap-2">
                  <SurfaceActionButton
                    onClick={goToPrevDesignPage}
                    disabled={!designsMeta?.prev_cursor}
                    shape="soft"
                  >
                    Previous
                  </SurfaceActionButton>
                  <SurfaceActionButton
                    onClick={goToNextDesignPage}
                    disabled={!designsMeta?.next_cursor}
                    shape="soft"
                  >
                    Next
                  </SurfaceActionButton>
                </div>
              </div>
            </div>
          </div>

          {selectedDesign ? (
            <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)] xl:max-w-[22rem] xl:justify-self-end">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/80 pb-4">
                <div className="min-w-0">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Selected Design
                  </p>
                  <h3 className="mt-2 text-base font-semibold text-foreground">
                    {selectedDesign.name}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">{selectedDesign.design_id}</p>
                </div>
                <SurfaceTag tone={readinessTone(selectedDesign.compare_readiness)}>
                  {selectedDesign.compare_readiness}
                </SurfaceTag>
              </div>
              <div className="mt-4 flex flex-col gap-3">
                <DesignSummaryTile
                  label="Source Coverage"
                  value={formatCoverage(selectedDesign.source_coverage)}
                />
                <DesignSummaryTile
                  label="Browse State"
                  value={
                    selectedDesign.compare_readiness === "ready"
                      ? "Ready for compare-aware browsing"
                      : selectedDesign.compare_readiness === "inspect_only"
                        ? "Single-source inspection only"
                        : "Blocked until more traces arrive"
                  }
                />
                <DesignSummaryTile label="Trace Count" value={String(selectedDesign.trace_count)} />
                <DesignSummaryTile label="Updated" value={selectedDesign.updated_at} />
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground xl:max-w-[22rem] xl:justify-self-end">
              Select a design scope to browse its trace summaries.
            </div>
          )}
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          No design scopes are available for the active dataset.
        </div>
      )}
    </SurfacePanel>
  );
}
