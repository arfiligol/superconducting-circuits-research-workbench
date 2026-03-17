"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle, Save, Search, Upload } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAppSession } from "@/lib/app-state";
import { useDashboardData } from "@/features/data-browser/hooks/use-dashboard-data";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceStat,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";

const profileSchema = z.object({
  device_type: z.string().trim().min(1, "Device type is required."),
  capabilities_text: z.string().trim(),
  source: z.string().trim().min(1, "Source is required."),
});

type ProfileValues = z.infer<typeof profileSchema>;

const emptyForm: ProfileValues = {
  device_type: "",
  capabilities_text: "",
  source: "",
};

function parseCapabilities(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function formatCapabilities(values: readonly string[]) {
  return values.length > 0 ? values.join(", ") : "None tagged";
}

function filterDatasetRows<
  TRow extends {
    dataset_id: string;
    name: string;
    family: string;
    owner_display_name: string;
    device_type: string;
    visibility_scope: string;
    lifecycle_state: string;
  },
>(rows: readonly TRow[], search: string) {
  const query = search.trim().toLowerCase();
  if (!query) {
    return rows;
  }

  return rows.filter((row) =>
    [
      row.dataset_id,
      row.name,
      row.family,
      row.owner_display_name,
      row.device_type,
      row.visibility_scope,
      row.lifecycle_state,
    ].some((value) => value.toLowerCase().includes(query)),
  );
}

export function DatasetWorkspace() {
  const { session } = useAppSession();
  const [saveState, setSaveState] = useState<{
    tone: "success" | "warning";
    message: string;
  } | null>(null);
  const [datasetSearch, setDatasetSearch] = useState("");
  const [isSelectingDataset, startDatasetTransition] = useTransition();
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
    saveProfile,
  } = useDashboardData();
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: emptyForm,
  });

  useEffect(() => {
    if (!profile) {
      form.reset(emptyForm);
      return;
    }
    form.reset({
      device_type: profile.device_type,
      capabilities_text: profile.capabilities.join(", "),
      source: profile.source,
    });
  }, [form, profile]);

  async function onSubmit(values: ProfileValues) {
    try {
      const result = await saveProfile({
        device_type: values.device_type.trim(),
        capabilities: parseCapabilities(values.capabilities_text),
        source: values.source.trim(),
      });
      form.reset({
        device_type: result.dataset.device_type,
        capabilities_text: result.dataset.capabilities.join(", "),
        source: result.dataset.source,
      });
      setSaveState({
        tone: "success",
        message: "Dataset profile saved through the dedicated dataset management surface.",
      });
    } catch (error) {
      setSaveState({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to save dataset profile.",
      });
    }
  }

  const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? "";
  const catalogRows = catalog?.rows ?? [];
  const filteredRows = useMemo(
    () => filterDatasetRows(catalogRows, datasetSearch),
    [catalogRows, datasetSearch],
  );
  const canSwitchDataset = session?.capabilities.canSwitchDataset ?? false;

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Dataset Workspace"
        title="Dataset"
        description="Browse visible datasets, switch the active session dataset, and manage dataset profile metadata without overloading the dashboard."
        actions={
          <>
            <SurfaceTag tone="primary">
              {activeDatasetState.activeDataset?.name ?? "No active dataset"}
            </SurfaceTag>
            <SurfaceTag>
              {activeDatasetState.activeDataset?.visibilityScope ?? "visibility pending"}
            </SurfaceTag>
          </>
        }
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <SurfaceStat label="Visible Datasets" value={String(catalogRows.length)} />
        <SurfaceStat
          label="Active Dataset"
          value={activeDatasetState.activeDataset?.name ?? "None selected"}
          tone="primary"
        />
        <SurfaceStat
          label="Profile Status"
          value={
            profile?.allowed_actions.update_profile
              ? "Writable"
              : activeDatasetState.activeDataset
                ? "Read-only"
                : "Awaiting dataset"
          }
          tone={profile?.allowed_actions.update_profile ? "primary" : "default"}
        />
        <SurfaceStat
          label="Tagged Metrics"
          value={String(metrics.length)}
          tone="primary"
        />
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.86fr)_minmax(0,1.14fr)]">
        <SurfacePanel
          title="Visible Datasets"
          description="This is the primary dataset browse and active-selection surface. Dashboard now stays summary-first."
          actions={
            <>
              <Link
                href="/raw-data"
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                <ArrowRight className="h-4 w-4" />
                Open Raw Data
              </Link>
              <Link
                href="/data-ingestion"
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                <Upload className="h-4 w-4" />
                Open Data Ingestion
              </Link>
            </>
          }
        >
          {catalogError ? (
            <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
              Unable to load visible datasets. {catalogError.message}
            </div>
          ) : null}

          <label className="block rounded-[1rem] border border-border bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
            <span className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
              <Search className="h-3.5 w-3.5" />
              Search Dataset
            </span>
            <div className="flex items-center gap-3 rounded-[0.85rem] border border-border/80 bg-background px-3 py-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                value={datasetSearch}
                onChange={(event) => {
                  setDatasetSearch(event.target.value);
                }}
                className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="Search by name, id, family, owner, or device type"
              />
            </div>
          </label>

          {!canSwitchDataset ? (
            <div className="mt-4 rounded-xl border border-amber-500/35 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:bg-amber-950/35 dark:text-amber-200">
              Dataset switching is disabled for the current session authority.
            </div>
          ) : null}

          {isCatalogLoading ? (
            <div className="mt-4 rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              Loading visible datasets...
            </div>
          ) : filteredRows.length > 0 ? (
            <div className="mt-4 space-y-3">
              {filteredRows.map((row) => {
                const isActive = row.dataset_id === activeDatasetId;
                const isBusy = isSelectingDataset && isActive;

                return (
                  <button
                    key={row.dataset_id}
                    type="button"
                    onClick={() => {
                      if (!canSwitchDataset || isActive) {
                        return;
                      }
                      setSaveState(null);
                      startDatasetTransition(() => {
                        void activeDatasetState.setActiveDataset(row.dataset_id);
                      });
                    }}
                    disabled={!canSwitchDataset}
                    aria-pressed={isActive}
                    className={cx(
                      "w-full cursor-pointer rounded-[1rem] border px-4 py-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                      isActive
                        ? "border-primary/40 bg-primary/10 shadow-[0_16px_34px_rgba(37,99,235,0.16)]"
                        : "border-border bg-surface hover:-translate-y-0.5 hover:border-primary/30 hover:bg-surface-elevated hover:shadow-[0_16px_32px_rgba(15,23,42,0.08)]",
                      !canSwitchDataset && "cursor-not-allowed opacity-70",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-foreground">{row.name}</h3>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {row.family} · {row.device_type} · {row.owner_display_name}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin text-primary" /> : null}
                        <SurfaceTag tone={isActive ? "primary" : "default"}>
                          {isActive ? "Active dataset" : row.visibility_scope}
                        </SurfaceTag>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <SurfaceTag>{row.lifecycle_state}</SurfaceTag>
                      <SurfaceTag>{row.dataset_id}</SurfaceTag>
                      <SurfaceTag>{row.updated_at}</SurfaceTag>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              {datasetSearch.trim().length > 0
                ? `No datasets match “${datasetSearch.trim()}”.`
                : "No visible datasets are available in the current runtime context."}
            </div>
          )}
        </SurfacePanel>

        <div className="space-y-5">
          <SurfacePanel
            title="Dataset Profile"
            description="Edit device type, capability tags, and source metadata here when backend authority allows profile updates."
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
            {saveState ? (
              <div
                className={cx(
                  "mb-4 rounded-xl border px-4 py-3 text-sm",
                  saveState.tone === "success"
                    ? "border-emerald-500/30 bg-emerald-500/10 text-foreground"
                    : "border-amber-500/30 bg-amber-500/10 text-foreground",
                )}
              >
                {saveState.message}
              </div>
            ) : null}

            {profile ? (
              <>
                <div className="mb-4 rounded-xl border border-border/80 bg-surface px-4 py-4 text-sm">
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
                  </dl>
                </div>

                <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
                  <div className="grid gap-3 xl:grid-cols-2">
                    <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                      <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Device Type
                      </span>
                      <input
                        {...form.register("device_type")}
                        disabled={isProfileLoading || !profile.allowed_actions.update_profile}
                        className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                        placeholder="Fluxonium"
                      />
                      {form.formState.errors.device_type?.message ? (
                        <p className="mt-2 text-xs text-amber-600">
                          {form.formState.errors.device_type.message}
                        </p>
                      ) : null}
                    </label>

                    <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                      <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Source
                      </span>
                      <input
                        {...form.register("source")}
                        disabled={isProfileLoading || !profile.allowed_actions.update_profile}
                        className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                        placeholder="manual"
                      />
                      {form.formState.errors.source?.message ? (
                        <p className="mt-2 text-xs text-amber-600">
                          {form.formState.errors.source.message}
                        </p>
                      ) : null}
                    </label>
                  </div>

                  <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                    <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Capabilities
                    </span>
                    <input
                      {...form.register("capabilities_text")}
                      disabled={isProfileLoading || !profile.allowed_actions.update_profile}
                      className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="characterization, simulation_review"
                    />
                  </label>

                  <div className="flex items-center justify-between rounded-xl border border-border/80 bg-surface px-4 py-3 text-sm">
                    <div>
                      <p className="font-medium text-foreground">
                        {formatCapabilities(profile.capabilities)}
                      </p>
                      <p className="mt-1 text-muted-foreground">
                        Dataset profile editing is backend-owned and stays on this page.
                      </p>
                    </div>
                    <button
                      type="submit"
                      disabled={
                        isProfileLoading ||
                        !profile.allowed_actions.update_profile ||
                        !form.formState.isDirty
                      }
                      className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <Save className="h-4 w-4" />
                      Save Profile
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Select or attach a dataset before editing its profile metadata.
              </div>
            )}
          </SurfacePanel>

          <SurfacePanel
            title="Dataset Lifecycle"
            description="This page manages session selection and profile metadata, but it does not fake lifecycle mutations that the backend has not exposed."
          >
            <div className="rounded-xl border border-amber-500/35 bg-amber-50 px-4 py-4 text-sm text-amber-950 dark:bg-amber-950/35 dark:text-amber-200">
              Create, archive, and delete dataset actions are not exposed through the current frontend-visible backend contract. Use the existing backend lifecycle surface once those endpoints are materialized.
            </div>
          </SurfacePanel>
        </div>
      </section>

      <SurfacePanel
        title="Tagged Core Metrics"
        description="Tagged core metrics stay read-only here and follow the current active dataset."
      >
        {isMetricsLoading ? (
          <div className="rounded-xl border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            Loading tagged core metrics...
          </div>
        ) : metrics.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {metrics.map((metric) => (
              <article
                key={metric.metric_id}
                className="rounded-xl border border-border/80 bg-surface px-4 py-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold text-foreground">{metric.label}</h3>
                  <SurfaceTag tone="success">{metric.designated_metric}</SurfaceTag>
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
            No tagged core metrics are available yet for the current active dataset.
          </div>
        )}
      </SurfacePanel>
    </div>
  );
}
