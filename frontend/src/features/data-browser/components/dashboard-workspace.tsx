"use client";

import { useEffect, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, Save } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAppSession } from "@/lib/app-state";
import { useDashboardData } from "@/features/data-browser/hooks/use-dashboard-data";
import { AppSelectField } from "@/features/shared/components/app-select";
import { SurfaceHeader, SurfacePanel, SurfaceStat, SurfaceTag, cx } from "@/features/shared/components/surface-kit";

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

function readinessTone(count: number) {
  return count > 0 ? "success" : "warning";
}

export function DashboardWorkspace() {
  const { session } = useAppSession();
  const [saveState, setSaveState] = useState<{
    tone: "success" | "warning";
    message: string;
  } | null>(null);
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
        message: "Dataset profile saved through the canonical dashboard write surface.",
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
  const canSwitchDataset = session?.capabilities.canSwitchDataset ?? false;

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Workspace Dashboard"
        title="Dashboard"
        description="Use the session-backed active dataset to edit dataset profile metadata, review read-only tagged core metrics, and confirm the current dataset context before entering analysis surfaces."
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
          value={profile?.allowed_actions.update_profile ? "Writable" : "Read-only"}
          tone={profile?.allowed_actions.update_profile ? "primary" : "default"}
        />
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.72fr)_minmax(0,1.28fr)]">
        <SurfacePanel
          title="Active Dataset"
          description="Selecting a dataset here mutates the shared session context instead of creating page-local dataset state."
        >
          {catalogError ? (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-foreground">
              Unable to load the dataset catalog. {catalogError.message}
            </div>
          ) : null}

          <div className="space-y-4">
            <div className="flex items-end gap-3">
              <AppSelectField
                className="flex-1"
                label="Session Active Dataset"
                value={activeDatasetId}
                disabled={
                  !canSwitchDataset ||
                  isCatalogLoading ||
                  catalogRows.length === 0 ||
                  isSelectingDataset
                }
                placeholder={
                  isCatalogLoading ? "Loading visible datasets..." : "Select a dataset"
                }
                onChange={(nextValue) => {
                  setSaveState(null);
                  startDatasetTransition(() => {
                    void activeDatasetState.setActiveDataset(nextValue);
                  });
                }}
                options={catalogRows.map((row) => ({
                  value: row.dataset_id,
                  label: row.name,
                  description: `${row.family} · ${row.owner_display_name}`,
                }))}
              />
              {isSelectingDataset ? (
                <LoaderCircle className="mb-3 h-4 w-4 animate-spin text-muted-foreground" />
              ) : null}
            </div>

            {!canSwitchDataset ? (
              <div className="rounded-xl border border-amber-500/35 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:bg-amber-950/35 dark:text-amber-200">
                Dataset switching is disabled for the current session authority.
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
                </dl>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                {isCatalogLoading ? "Loading dataset context..." : "Attach a dataset from the shared shell or dashboard selector."}
              </div>
            )}
          </div>
        </SurfacePanel>

        <SurfacePanel
          title="Dataset Profile"
          description="This is the only metadata write surface. Raw-data and downstream analysis pages remain summary-only."
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

          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-3 xl:grid-cols-2">
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Device Type
                </span>
                <input
                  {...form.register("device_type")}
                  disabled={!profile || isProfileLoading}
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
                  disabled={!profile || isProfileLoading}
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
                disabled={!profile || isProfileLoading}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="characterization, simulation_review"
              />
            </label>

            <div className="flex items-center justify-between rounded-xl border border-border/80 bg-surface px-4 py-3 text-sm">
              <div>
                <p className="font-medium text-foreground">
                  {profile ? formatCapabilities(profile.capabilities) : "No dataset selected"}
                </p>
                <p className="mt-1 text-muted-foreground">
                  Dashboard remains the canonical write surface for device type, capabilities, and source.
                </p>
              </div>
              <button
                type="submit"
                disabled={!profile || isProfileLoading || !form.formState.isDirty}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save className="h-4 w-4" />
                Save Profile
              </button>
            </div>
          </form>
        </SurfacePanel>
      </section>

      <SurfacePanel
        title="Tagged Core Metrics"
        description="Read-only summaries follow the active dataset. Identification and tagging stay outside the dashboard write surface."
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
