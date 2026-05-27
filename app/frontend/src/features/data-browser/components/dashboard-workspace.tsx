"use client";

import { useDashboardData } from "@/features/data-browser/hooks/use-dashboard-data";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceStat,
  SurfaceTag,
} from "@/features/shared/components/surface-kit";

export function DashboardWorkspace() {
  const {
    catalog,
    catalogError,
    isCatalogLoading,
    profileError,
    metrics,
    metricsError,
    isMetricsLoading,
  } = useDashboardData();
  const catalogRows = catalog?.rows ?? [];

  return (
    <div className="space-y-6">
      <SurfaceHeader
        eyebrow="Workspace Dashboard"
        title="Dashboard"
        description="Dashboard keeps an overview-first summary of dataset availability and tagged core metrics."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <SurfaceStat
          label="Visible Datasets"
          value={isCatalogLoading ? "Loading" : String(catalogRows.length)}
        />
        <SurfaceStat
          label="Tagged Metrics"
          value={isMetricsLoading ? "Loading" : String(metrics.length)}
          tone="primary"
        />
      </div>

      {catalogError || profileError || metricsError ? (
        <div className="space-y-2" role="status" aria-live="polite">
          {catalogError ? (
            <p className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-foreground">
              <span className="font-medium">Dataset catalog unavailable.</span> {catalogError.message}
            </p>
          ) : null}
          {profileError ? (
            <p className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-foreground">
              <span className="font-medium">Dataset profile unavailable.</span> {profileError.message}
            </p>
          ) : null}
          {metricsError ? (
            <p className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-foreground">
              <span className="font-medium">Tagged metrics unavailable.</span> {metricsError.message}
            </p>
          ) : null}
        </div>
      ) : null}

      <SurfacePanel title="Tagged Core Metrics">
        {isMetricsLoading ? (
          <div className="rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            Loading tagged core metrics...
          </div>
        ) : metrics.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-border bg-surface">
            {metrics.map((metric) => (
              <article
                key={metric.metric_id}
                className="grid gap-3 border-b border-border px-4 py-3 last:border-b-0 md:grid-cols-[minmax(0,1fr)_minmax(160px,0.45fr)_minmax(140px,0.35fr)] md:items-center"
              >
                <div className="min-w-0">
                  <h3 className="font-semibold text-foreground">{metric.label}</h3>
                  <div className="mt-1">
                    <SurfaceTag tone="primary">{metric.designated_metric}</SurfaceTag>
                  </div>
                </div>
                <dl className="contents text-sm">
                  <div className="min-w-0">
                    <dt className="text-muted-foreground">Source Parameter</dt>
                    <dd className="mt-1 break-words font-medium text-foreground">
                      {metric.source_parameter}
                    </dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-muted-foreground">Tagged At</dt>
                    <dd className="mt-1 break-words font-medium text-foreground">
                      {metric.tagged_at}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            No tagged core metrics are available yet.
          </div>
        )}
      </SurfacePanel>
    </div>
  );
}
