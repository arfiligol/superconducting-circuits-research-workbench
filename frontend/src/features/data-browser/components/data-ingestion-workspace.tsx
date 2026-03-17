"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowRight, Database, Upload } from "lucide-react";

import { useActiveDataset, useAppSession } from "@/lib/app-state";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceStat,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";

type IngestionScope = "measurement" | "layout_simulation";

const ingestionScopes: ReadonlyArray<
  Readonly<{
    id: IngestionScope;
    title: string;
    description: string;
    payloadSummary: string;
    blockedReason: string;
  }>
> = [
  {
    id: "measurement",
    title: "Measurement",
    description:
      "Bring lab-acquired raw traces into the active dataset. This path is for instrument exports and measured sweeps, not downstream analysis views.",
    payloadSummary: "Expected sources: lab exports, measurement sweeps, packaged trace batches.",
    blockedReason:
      "No measurement ingestion upload endpoint is exposed in the current frontend-visible backend contract.",
  },
  {
    id: "layout_simulation",
    title: "Layout Simulation",
    description:
      "Bring layout-simulation raw traces into the active dataset. This path is for EM or field-solver outputs before comparison and analysis.",
    payloadSummary: "Expected sources: layout solver exports, packaged field-solver trace batches.",
    blockedReason:
      "No layout-simulation ingestion upload endpoint is exposed in the current frontend-visible backend contract.",
  },
] as const;

export function DataIngestionWorkspace() {
  const [selectedScope, setSelectedScope] = useState<IngestionScope>("measurement");
  const { runtimeMode } = useAppSession();
  const { activeDataset, source } = useActiveDataset();
  const selectedScopeSummary = useMemo(
    () => ingestionScopes.find((scope) => scope.id === selectedScope) ?? ingestionScopes[0],
    [selectedScope],
  );

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw-Data Intake"
        title="Data Ingestion"
        description="Choose where raw data enters the product. This page is for ingestion only, separate from dataset profile management and downstream browsing."
        actions={
          <>
            <SurfaceTag tone="primary">{selectedScopeSummary.title}</SurfaceTag>
            <SurfaceTag>{activeDataset?.name ?? "No active dataset"}</SurfaceTag>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <SurfaceStat
          label="Runtime Mode"
          value={runtimeMode === "local" ? "Local Mode" : "Online Mode"}
          tone="primary"
        />
        <SurfaceStat label="Target Dataset" value={activeDataset?.name ?? "None selected"} />
        <SurfaceStat label="Upload Contract" value="Blocked" />
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)]">
        <SurfacePanel
          title="Ingestion Scope"
          description="Pick the raw-data source family first so the intake path is explicit before any upload contract is wired."
        >
          <div className="grid gap-4 md:grid-cols-2">
            {ingestionScopes.map((scope) => {
              const isSelected = scope.id === selectedScope;
              return (
                <button
                  key={scope.id}
                  type="button"
                  onClick={() => {
                    setSelectedScope(scope.id);
                  }}
                  aria-pressed={isSelected}
                  className={cx(
                    "w-full cursor-pointer rounded-[1rem] border px-4 py-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                    isSelected
                      ? "border-primary/40 bg-primary/10 shadow-[0_16px_34px_rgba(37,99,235,0.16)]"
                      : "border-border bg-surface hover:-translate-y-0.5 hover:border-primary/30 hover:bg-surface-elevated hover:shadow-[0_16px_32px_rgba(15,23,42,0.08)]",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">{scope.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        {scope.description}
                      </p>
                    </div>
                    <SurfaceTag tone={isSelected ? "primary" : "default"}>
                      {isSelected ? "Selected" : "Choose"}
                    </SurfaceTag>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mt-4 rounded-[1rem] border border-border bg-surface px-4 py-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Selected intake path
            </p>
            <p className="mt-2 text-sm font-medium text-foreground">{selectedScopeSummary.title}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {selectedScopeSummary.payloadSummary}
            </p>
          </div>
        </SurfacePanel>

        <div className="space-y-5">
          <SurfacePanel
            title="Ingestion Target"
            description="The active dataset remains the session-level target container. Use Dataset or Global Context if you need to change it."
          >
            <div className="rounded-[1rem] border border-border bg-surface px-4 py-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Database className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    {activeDataset?.name ?? "No active dataset selected"}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {activeDataset
                      ? `${activeDataset.datasetId} · ${activeDataset.visibilityScope} · ${activeDataset.status}`
                      : "Attach a dataset first so raw-data ingestion has a target container."}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Dataset source authority: {source === "none" ? "No selection" : source}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  href="/dataset"
                  className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <ArrowRight className="h-4 w-4" />
                  Open Dataset
                </Link>
                <Link
                  href="/raw-data"
                  className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <ArrowRight className="h-4 w-4" />
                  Open Raw Data
                </Link>
              </div>
            </div>
          </SurfacePanel>

          <SurfacePanel
            title="Ingestion Readiness"
            description="This page makes the intake workflow visible now without faking upload success or inventing missing persistence APIs."
          >
            <div className="rounded-[1rem] border border-amber-500/35 bg-amber-50 px-4 py-4 text-sm text-amber-950 dark:bg-amber-950/35 dark:text-amber-200">
              <p className="font-semibold text-current">Blocked by backend contract</p>
              <p className="mt-2 leading-6">{selectedScopeSummary.blockedReason}</p>
              <p className="mt-2 leading-6">
                The current frontend-visible contract exposes dataset catalog, profile, designs, traces,
                and preview reads, but no raw-data upload or ingestion mutation surface.
              </p>
            </div>

            <button
              type="button"
              disabled
              className="mt-4 inline-flex min-h-11 w-full cursor-not-allowed items-center justify-center gap-2 rounded-full border border-border bg-surface px-4 py-3 text-sm font-medium text-muted-foreground opacity-80"
            >
              <Upload className="h-4 w-4" />
              Upload unavailable
            </button>
          </SurfacePanel>
        </div>
      </section>
    </div>
  );
}
