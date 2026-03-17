"use client";

import Link from "next/link";
import { ArrowRight, Database, Upload } from "lucide-react";

import { useDashboardData } from "@/features/data-browser/hooks/use-dashboard-data";
import { SurfaceHeader, SurfacePanel, SurfaceStat, SurfaceTag, cx } from "@/features/shared/components/surface-kit";

function formatCapabilities(values: readonly string[]) {
  return values.length > 0 ? values.join(", ") : "None tagged";
}

function readinessTone(count: number) {
  return count > 0 ? "success" : "warning";
}

export function DashboardWorkspace() {
  const {
    activeDatasetState,
    catalog,
    catalogError,
    isCatalogLoading,
    profile,
    profileError,
    isProfileLoading,
    metrics,
    metricsError,
    isMetricsLoading,
  } = useDashboardData();
  const catalogRows = catalog?.rows ?? [];

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Workspace Dashboard"
        title="Dashboard"
        description="Keep the dashboard overview-first. Use it to confirm the current dataset context, tagged metrics, and workflow entry points before moving into dedicated management or ingestion pages."
        actions={
          <>
            <SurfaceTag tone="primary">
              {activeDatasetState.activeDataset?.name ?? "No active dataset"}
            </SurfaceTag>
            <SurfaceTag>{activeDatasetState.activeDataset?.family ?? "Awaiting selection"}</SurfaceTag>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <SurfaceStat label="Visible Datasets" value={String(catalogRows.length)} />
        <SurfaceStat
          label="Tagged Metrics"
          value={String(metrics.length)}
          tone="primary"
        />
        <SurfaceStat
          label="Profile Status"
          value={profile?.allowed_actions.update_profile ? "Managed in Dataset" : "Read-only"}
          tone="default"
        />
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
        <SurfacePanel
          title="Current Dataset Context"
          description="Dashboard now summarizes the active dataset instead of carrying the full dataset workflow."
        >
          {catalogError ? (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
              Unable to load the dataset catalog. {catalogError.message}
            </div>
          ) : null}

          {profile ? (
            <div className="rounded-xl border border-border/80 bg-surface px-4 py-4 text-sm">
              <div className="flex flex-wrap gap-2">
                <SurfaceTag tone="primary">{profile.visibility_scope}</SurfaceTag>
                <SurfaceTag>{profile.lifecycle_state}</SurfaceTag>
                <SurfaceTag>{profile.status}</SurfaceTag>
              </div>
              <dl className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Owner
                  </dt>
                  <dd className="mt-1 font-medium text-foreground">{profile.owner_display_name}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Updated
                  </dt>
                  <dd className="mt-1 font-medium text-foreground">{profile.updated_at}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Device Type
                  </dt>
                  <dd className="mt-1 font-medium text-foreground">{profile.device_type}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Capabilities
                  </dt>
                  <dd className="mt-1 font-medium text-foreground">
                    {formatCapabilities(profile.capabilities)}
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              {isCatalogLoading
                ? "Loading dataset context..."
                : "Attach a dataset from Global Context or open the Dataset page to manage dataset state."}
            </div>
          )}
        </SurfacePanel>

        <SurfacePanel
          title="Workflow Entry Points"
          description="Move from dashboard overview into the dedicated pages that now own dataset management and raw-data intake."
        >
          {profileError ? (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
              Unable to load the dataset profile. {profileError.message}
            </div>
          ) : null}
          {metricsError ? (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
              Unable to load tagged core metrics. {metricsError.message}
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-3">
            <Link
              href="/dataset"
              className="rounded-xl border border-border bg-surface px-4 py-4 transition hover:border-primary/30 hover:bg-surface-elevated"
            >
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Database className="h-5 w-5" />
                </span>
                <div>
                  <p className="font-semibold text-foreground">Dataset</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Primary browse, active-selection, and dataset profile management surface.
                  </p>
                </div>
              </div>
            </Link>

            <Link
              href="/data-ingestion"
              className="rounded-xl border border-border bg-surface px-4 py-4 transition hover:border-primary/30 hover:bg-surface-elevated"
            >
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Upload className="h-5 w-5" />
                </span>
                <div>
                  <p className="font-semibold text-foreground">Data Ingestion</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Explicit entry for raw measurement and layout-simulation intake.
                  </p>
                </div>
              </div>
            </Link>

            <Link
              href="/raw-data"
              className="rounded-xl border border-border bg-surface px-4 py-4 transition hover:border-primary/30 hover:bg-surface-elevated"
            >
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <ArrowRight className="h-5 w-5" />
                </span>
                <div>
                  <p className="font-semibold text-foreground">Raw Data Browser</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Inspect design scopes, trace summaries, and single-trace previews after ingestion.
                  </p>
                </div>
              </div>
            </Link>
          </div>
        </SurfacePanel>
      </section>

      <SurfacePanel
        title="Tagged Core Metrics"
        description="Read-only summaries follow the active dataset. Dashboard stays summary-first and no longer owns dataset profile edits."
      >
        {isMetricsLoading ? (
          <div className="rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            Loading tagged core metrics...
          </div>
        ) : metrics.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {metrics.map((metric) => (
              <article key={metric.metric_id} className="rounded-xl border border-border/80 bg-surface px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold text-foreground">{metric.label}</h3>
                  <SurfaceTag tone={readinessTone(1)}>{metric.designated_metric}</SurfaceTag>
                </div>
                <dl className="mt-4 space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-4">
                    <dt className="text-muted-foreground">Source Parameter</dt>
                    <dd className="font-medium text-foreground">{metric.source_parameter}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <dt className="text-muted-foreground">Tagged At</dt>
                    <dd className="font-medium text-foreground">{metric.tagged_at}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            No tagged core metrics are available yet. Use characterization and identify-mode flows to create them, then return here for the read-only summary.
          </div>
        )}
      </SurfacePanel>
    </div>
  );
}
