"use client";

import { useDeferredValue } from "react";

import { useRawDataBrowserData } from "@/features/data-browser/hooks/use-raw-data-browser-data";
import { AppSelectField } from "@/features/shared/components/app-select";
import { SurfaceHeader, SurfacePanel, SurfaceTag, cx } from "@/features/shared/components/surface-kit";

function readinessTone(value: "ready" | "inspect_only" | "blocked") {
  if (value === "ready") {
    return "success" as const;
  }
  if (value === "inspect_only") {
    return "primary" as const;
  }
  return "warning" as const;
}

function formatCoverage(coverage: Record<string, number>) {
  const entries = Object.entries(coverage);
  if (entries.length === 0) {
    return "No source coverage";
  }
  return entries.map(([key, value]) => `${key}: ${value}`).join(" · ");
}

export function RawDataBrowserWorkspace() {
  const browser = useRawDataBrowserData();
  const deferredDesignSearch = useDeferredValue(browser.designSearch);
  const deferredTraceSearch = useDeferredValue(browser.filters.search);
  const selectedDesign = browser.designs.find((row) => row.design_id === browser.selectedDesignId) ?? null;

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw Data Browser"
        title="Raw Data"
        description="Browse dataset-local design scopes, filter trace metadata, inspect compare readiness, and open one trace preview at a time without mixing metadata writes into this page."
        actions={
          <>
            <SurfaceTag tone="primary">
              {browser.activeDatasetState.activeDataset?.name ?? "No active dataset"}
            </SurfaceTag>
            <SurfaceTag>
              {browser.activeDatasetState.activeDataset?.datasetId ?? "Attach a dataset in the shell"}
            </SurfaceTag>
          </>
        }
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
        <SurfacePanel
          title="Design Scopes"
          description="Design selection stays page-local and is always scoped by the session-owned active dataset."
        >
          {browser.designsError ? (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
              Unable to load design scopes. {browser.designsError.message}
            </div>
          ) : null}
          <label className="block rounded-xl border border-border bg-surface px-4 py-3">
            <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Search Designs
            </span>
            <input
              value={browser.designSearch}
              onChange={(event) => {
                browser.setDesignSearch(event.target.value);
              }}
              className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              placeholder="Flux Scan"
            />
          </label>
          {browser.isDesignsLoading ? (
            <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              Loading designs for {deferredDesignSearch || "the active dataset"}...
            </div>
          ) : browser.designs.length > 0 ? (
            <div className="mt-4 space-y-3">
              {browser.designs.map((design) => (
                <button
                  key={design.design_id}
                  type="button"
                  onClick={() => {
                    browser.setSelectedDesignId(design.design_id);
                  }}
                  className={cx(
                    "w-full rounded-xl border px-4 py-4 text-left transition",
                    design.design_id === browser.selectedDesignId
                      ? "border-primary/40 bg-primary/10"
                      : "border-border bg-surface hover:border-primary/25",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-foreground">{design.name}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {formatCoverage(design.source_coverage)}
                      </p>
                    </div>
                    <SurfaceTag tone={readinessTone(design.compare_readiness)}>
                      {design.compare_readiness}
                    </SurfaceTag>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs uppercase tracking-[0.14em] text-muted-foreground">
                    <span>{design.trace_count} traces</span>
                    <span>{design.updated_at}</span>
                  </div>
                </button>
              ))}
              <div className="flex items-center justify-between gap-3 pt-1 text-sm">
                <button
                  type="button"
                  onClick={browser.goToPrevDesignPage}
                  disabled={!browser.designsMeta?.prev_cursor}
                  className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={browser.goToNextDesignPage}
                  disabled={!browser.designsMeta?.next_cursor}
                  className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              No design scopes are available for the active dataset.
            </div>
          )}
        </SurfacePanel>

        <div className="space-y-5">
          <SurfacePanel
            title="Selected Design Summary"
            description="Compare readiness and source coverage stay read-only here so raw-data browsing remains summary-first."
          >
            {selectedDesign ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Compare Readiness
                  </p>
                  <div className="mt-3">
                    <SurfaceTag tone={readinessTone(selectedDesign.compare_readiness)}>
                      {selectedDesign.compare_readiness}
                    </SurfaceTag>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    {selectedDesign.compare_readiness === "ready"
                      ? "The design has enough source coverage for cross-source comparison."
                      : selectedDesign.compare_readiness === "inspect_only"
                        ? "The design is suitable for single-source inspection but not comparison."
                        : "The design is blocked until additional traces arrive."}
                  </p>
                </div>
                <div className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Source Coverage
                  </p>
                  <p className="mt-3 font-medium text-foreground">
                    {formatCoverage(selectedDesign.source_coverage)}
                  </p>
                  <p className="mt-3 text-sm text-muted-foreground">
                    Active dataset: {selectedDesign.dataset_id}
                  </p>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Select a design scope to browse its trace summaries.
              </div>
            )}
          </SurfacePanel>

          <SurfacePanel
            title="Trace Summaries"
            description="Trace browsing stays metadata-only until one row is selected for preview."
          >
            {browser.tracesError ? (
              <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
                Unable to load trace summaries. {browser.tracesError.message}
              </div>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <label className="block rounded-xl border border-border bg-surface px-4 py-3 xl:col-span-2">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Search
                </span>
                <input
                  value={browser.filters.search}
                  onChange={(event) => {
                    browser.setFilters((current) => ({
                      ...current,
                      search: event.target.value,
                    }));
                  }}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="Y11"
                />
              </label>
              <FilterSelect
                label="Family"
                value={browser.filters.family}
                onChange={(value) => {
                  browser.setFilters((current) => ({ ...current, family: value }));
                }}
                options={["", "s_matrix", "y_matrix", "z_matrix"]}
              />
              <FilterSelect
                label="Representation"
                value={browser.filters.representation}
                onChange={(value) => {
                  browser.setFilters((current) => ({ ...current, representation: value }));
                }}
                options={["", "real", "imaginary", "magnitude", "phase"]}
              />
              <FilterSelect
                label="Source"
                value={browser.filters.sourceKind}
                onChange={(value) => {
                  browser.setFilters((current) => ({ ...current, sourceKind: value }));
                }}
                options={["", "measurement", "layout_simulation", "circuit_simulation"]}
              />
            </div>

            {browser.isTracesLoading ? (
              <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Loading trace summaries for {deferredTraceSearch || "the selected design"}...
              </div>
            ) : browser.traces.length > 0 ? (
              <div className="mt-4 overflow-hidden rounded-xl border border-border/80">
                <table className="min-w-full divide-y divide-border text-sm">
                  <thead className="bg-surface">
                    <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                      <th className="px-4 py-3">Parameter</th>
                      <th className="px-4 py-3">Family</th>
                      <th className="px-4 py-3">Representation</th>
                      <th className="px-4 py-3">Source</th>
                      <th className="px-4 py-3">Provenance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-card">
                    {browser.traces.map((trace) => (
                      <tr
                        key={trace.trace_id}
                        className={cx(
                          "cursor-pointer transition hover:bg-primary/5",
                          trace.trace_id === browser.selectedTraceId && "bg-primary/10",
                        )}
                        onClick={() => {
                          browser.setSelectedTraceId(trace.trace_id);
                        }}
                      >
                        <td className="px-4 py-3 font-medium text-foreground">{trace.parameter}</td>
                        <td className="px-4 py-3 text-muted-foreground">{trace.family}</td>
                        <td className="px-4 py-3 text-muted-foreground">{trace.representation}</td>
                        <td className="px-4 py-3 text-muted-foreground">{trace.source_kind}</td>
                        <td className="px-4 py-3 text-muted-foreground">{trace.provenance_summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="flex items-center justify-between gap-3 border-t border-border bg-surface px-4 py-3 text-sm">
                  <button
                    type="button"
                    onClick={browser.goToPrevTracePage}
                    disabled={!browser.tracesMeta?.prev_cursor}
                    className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={browser.goToNextTracePage}
                    disabled={!browser.tracesMeta?.next_cursor}
                    className="rounded-md border border-border px-3 py-2 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                No trace summaries match the current filters.
              </div>
            )}
          </SurfacePanel>

          <SurfacePanel
            title="Single Trace Preview"
            description="Only the selected trace triggers the detail path, including preview payload and provenance-bearing result handles."
          >
            {browser.traceDetailError ? (
              <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
                Unable to load trace preview. {browser.traceDetailError.message}
              </div>
            ) : null}
            {browser.isTraceDetailLoading ? (
              <div className="rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Loading single-trace preview...
              </div>
            ) : browser.traceDetail ? (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Axes
                    </p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {browser.traceDetail.axes.map((axis) => (
                        <li key={axis.name} className="flex items-center justify-between gap-4">
                          <span className="text-muted-foreground">{axis.name}</span>
                          <span className="font-medium text-foreground">
                            {axis.length} {axis.unit}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Payload Ref
                    </p>
                    <p className="mt-3 break-all text-sm font-medium text-foreground">
                      {browser.traceDetail.payload_ref?.store_key ?? "No payload ref"}
                    </p>
                    <p className="mt-3 text-sm text-muted-foreground">
                      {browser.traceDetail.payload_ref?.group_path ?? "No group path"}
                    </p>
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Preview Payload
                  </p>
                  <div className="mt-3 overflow-hidden rounded-lg border border-border/80">
                    <table className="min-w-full divide-y divide-border text-sm">
                      <thead className="bg-card">
                        <tr className="text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          <th className="px-4 py-3">Axis</th>
                          <th className="px-4 py-3">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border bg-surface">
                        {(browser.traceDetail.preview_payload.points ?? []).map((point, index) => (
                          <tr key={`${point[0]}-${index}`}>
                            <td className="px-4 py-3 text-muted-foreground">{point[0]}</td>
                            <td className="px-4 py-3 font-medium text-foreground">{point[1]}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Result Handles
                  </p>
                  {browser.traceDetail.result_handles.length > 0 ? (
                    <div className="mt-3 space-y-3">
                      {browser.traceDetail.result_handles.map((handle) => (
                        <div key={handle.handle_id} className="rounded-lg border border-border/80 bg-card px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-medium text-foreground">{handle.label}</span>
                            <SurfaceTag>{handle.kind}</SurfaceTag>
                          </div>
                          <p className="mt-2 break-all text-sm text-muted-foreground">
                            {handle.payload_locator ?? "No payload locator"}
                          </p>
                          <p className="mt-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                            provenance task: {handle.provenance_task_id ?? "n/a"} · source dataset:{" "}
                            {handle.provenance.source_dataset_id ?? "n/a"}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      No provenance-bearing result handles are attached to this trace preview.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Select one trace summary to load the single-trace preview path.
              </div>
            )}
          </SurfacePanel>
        </div>
      </section>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
}>) {
  return (
    <AppSelectField
      label={label}
      value={value}
      onChange={onChange}
      options={options.map((option) => ({
        value: option,
        label: option || "All",
      }))}
    />
  );
}
