"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Database, LoaderCircle, Upload } from "lucide-react";
import { useForm } from "react-hook-form";
import useSWR from "swr";
import { z } from "zod";

import {
  datasetProfileKey,
  getDatasetProfile,
  ingestRawData,
} from "@/lib/api/datasets";
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
  }>
> = [
  {
    id: "measurement",
    title: "Measurement",
    description:
      "Bring lab-acquired traces into the active dataset as dataset-local design data.",
    payloadSummary:
      "Best for instrument exports and measured sweeps before browsing or comparison.",
  },
  {
    id: "layout_simulation",
    title: "Layout Simulation",
    description:
      "Bring EM or field-solver traces into the active dataset for downstream simulation comparison.",
    payloadSummary:
      "Best for layout solver exports that should become visible in Raw Data Browser.",
  },
] as const;

const ingestionSchema = z.object({
  design_name: z.string().trim().min(1, "Design name is required."),
  design_id: z.string().trim().optional(),
  provenance_label: z.string().trim().min(1, "Provenance label is required."),
  trace_id: z.string().trim().optional(),
  family: z.enum(["s_matrix", "y_matrix", "z_matrix"]),
  parameter: z.string().trim().min(1, "Parameter is required."),
  representation: z.string().trim().min(1, "Representation is required."),
  trace_mode_group: z.enum(["base", "sideband", "all"]),
  stage_kind: z.enum(["raw", "preprocess", "postprocess"]),
  provenance_summary: z.string().trim().min(1, "Trace provenance summary is required."),
  axis_name: z.string().trim().min(1, "Axis name is required."),
  axis_unit: z.string().trim().min(1, "Axis unit is required."),
  axis_length: z.number().int().min(1, "Axis length must be a positive integer."),
  preview_payload_json: z.string().trim().min(1, "Preview payload JSON is required."),
});

type IngestionValues = z.infer<typeof ingestionSchema>;

const defaultValues: IngestionValues = {
  design_name: "",
  design_id: "",
  provenance_label: "",
  trace_id: "",
  family: "y_matrix",
  parameter: "Y11",
  representation: "imaginary",
  trace_mode_group: "base",
  stage_kind: "raw",
  provenance_summary: "",
  axis_name: "frequency",
  axis_unit: "GHz",
  axis_length: 401,
  preview_payload_json: '{ "kind": "sampled_series", "points": [[1.0, 0.0], [1.1, 0.015]] }',
};

type SubmitState = Readonly<{
  tone: "success" | "warning";
  message: string;
}> | null;

type IngestionResultState = Readonly<{
  datasetId: string;
  datasetName: string;
  designId: string;
  designName: string;
  traceCount: number;
}> | null;

export function DataIngestionWorkspace() {
  const [selectedScope, setSelectedScope] = useState<IngestionScope>("measurement");
  const [submitState, setSubmitState] = useState<SubmitState>(null);
  const [submitResult, setSubmitResult] = useState<IngestionResultState>(null);
  const { runtimeMode } = useAppSession();
  const activeDatasetState = useActiveDataset();
  const activeDataset = activeDatasetState.activeDataset;
  const activeDatasetId = activeDataset?.datasetId ?? null;
  const profileQuery = useSWR(
    activeDatasetId ? datasetProfileKey(activeDatasetId) : null,
    () => (activeDatasetId ? getDatasetProfile(activeDatasetId) : Promise.resolve(undefined)),
  );
  const form = useForm<IngestionValues>({
    resolver: zodResolver(ingestionSchema),
    defaultValues,
  });

  const selectedScopeSummary = useMemo(
    () => ingestionScopes.find((scope) => scope.id === selectedScope) ?? ingestionScopes[0],
    [selectedScope],
  );
  const canIngest = Boolean(profileQuery.data?.allowed_actions.ingest_raw_data);
  const submitBlockedReason = !activeDataset
    ? "Attach a dataset first so ingestion has a target container."
    : profileQuery.isLoading
      ? "Checking dataset ingestion authority..."
      : !canIngest
        ? "The current backend authority does not allow ingestion for this dataset."
        : null;

  async function handleSubmit(values: IngestionValues) {
    if (!activeDataset) {
      setSubmitState({
        tone: "warning",
        message: "Attach a dataset before submitting ingestion.",
      });
      return;
    }

    let previewPayload: Record<string, unknown>;
    try {
      const parsed = JSON.parse(values.preview_payload_json);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Preview payload must be a JSON object.");
      }
      previewPayload = parsed as Record<string, unknown>;
    } catch {
      setSubmitState({
        tone: "warning",
        message: "Preview payload must be valid JSON object text.",
      });
      return;
    }

    setSubmitState(null);
    setSubmitResult(null);

    try {
      const result = await ingestRawData(activeDataset.datasetId, {
        kind: selectedScope,
        design_name: values.design_name.trim(),
        design_id: values.design_id?.trim() || undefined,
        provenance_label: values.provenance_label.trim(),
        traces: [
          {
            trace_id: values.trace_id?.trim() || undefined,
            family: values.family,
            parameter: values.parameter.trim(),
            representation: values.representation.trim(),
            trace_mode_group: values.trace_mode_group,
            stage_kind: values.stage_kind,
            provenance_summary: values.provenance_summary.trim(),
            axes: [
              {
                name: values.axis_name.trim(),
                unit: values.axis_unit.trim(),
                length: values.axis_length,
              },
            ],
            preview_payload: previewPayload,
          },
        ],
      });
      setSubmitState({
        tone: "success",
        message: `Ingestion succeeded: ${result.traces.length} trace(s) materialized for design ${result.design.name}.`,
      });
      setSubmitResult({
        datasetId: result.dataset.dataset_id,
        datasetName: result.dataset.name,
        designId: result.design.design_id,
        designName: result.design.name,
        traceCount: result.traces.length,
      });
    } catch (error) {
      setSubmitState({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to submit ingestion.",
      });
    }
  }

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw-Data Intake"
        title="Data Ingestion"
        description="Submit measurement or layout-simulation intake into the active dataset. This page owns ingestion submission only."
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
        <SurfaceStat
          label="Submit Authority"
          value={
            !activeDataset
              ? "Dataset required"
              : profileQuery.isLoading
                ? "Checking"
                : canIngest
                  ? "Allowed"
                  : "Blocked"
          }
          tone={canIngest ? "primary" : "default"}
        />
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)]">
        <SurfacePanel
          title="Ingestion Scope"
          description="Choose the source family, then submit one concrete ingestion payload bound to the active dataset."
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

          <form className="mt-4 space-y-4" onSubmit={form.handleSubmit(handleSubmit)}>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Design Name
                </span>
                <input
                  {...form.register("design_name")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="Flux Scan A"
                />
              </label>
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Design Id (optional)
                </span>
                <input
                  {...form.register("design_id")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="design_flux_scan_a"
                />
              </label>
            </div>

            <label className="block rounded-xl border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Ingestion Provenance Label
              </span>
              <input
                {...form.register("provenance_label")}
                disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="Measurement import · Lab-4 · March run"
              />
            </label>

            <div className="grid gap-3 md:grid-cols-3">
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Family
                </span>
                <select
                  {...form.register("family")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                >
                  <option value="s_matrix">s_matrix</option>
                  <option value="y_matrix">y_matrix</option>
                  <option value="z_matrix">z_matrix</option>
                </select>
              </label>
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Trace Mode Group
                </span>
                <select
                  {...form.register("trace_mode_group")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                >
                  <option value="base">base</option>
                  <option value="sideband">sideband</option>
                  <option value="all">all</option>
                </select>
              </label>
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Stage Kind
                </span>
                <select
                  {...form.register("stage_kind")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none"
                >
                  <option value="raw">raw</option>
                  <option value="preprocess">preprocess</option>
                  <option value="postprocess">postprocess</option>
                </select>
              </label>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Parameter
                </span>
                <input
                  {...form.register("parameter")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="Y11"
                />
              </label>
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Representation
                </span>
                <input
                  {...form.register("representation")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="imaginary"
                />
              </label>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Axis Name
                </span>
                <input
                  {...form.register("axis_name")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="frequency"
                />
              </label>
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Axis Unit
                </span>
                <input
                  {...form.register("axis_unit")}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                  placeholder="GHz"
                />
              </label>
              <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Axis Length
                </span>
                <input
                  {...form.register("axis_length", { valueAsNumber: true })}
                  type="number"
                  min={1}
                  disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                  className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
              </label>
            </div>

            <label className="block rounded-xl border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Trace Provenance Summary
              </span>
              <input
                {...form.register("provenance_summary")}
                disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="Measurement · Raw · batch #4"
              />
            </label>

            <label className="block rounded-xl border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Trace Id (optional)
              </span>
              <input
                {...form.register("trace_id")}
                disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="trace_flux_a_measurement"
              />
            </label>

            <label className="block rounded-xl border border-border bg-surface px-4 py-3">
              <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Preview Payload JSON
              </span>
              <textarea
                {...form.register("preview_payload_json")}
                rows={4}
                disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
                className="mt-2 w-full resize-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </label>

            <button
              type="submit"
              disabled={Boolean(submitBlockedReason) || form.formState.isSubmitting}
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-60"
            >
              {form.formState.isSubmitting ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Upload className="h-4 w-4" />
              )}
              Submit {selectedScopeSummary.title} Ingestion
            </button>
          </form>
        </SurfacePanel>

        <div className="space-y-5">
          <SurfacePanel
            title="Ingestion Target"
            description="The active dataset is the target authority for this ingestion request."
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
                      : "Attach a dataset first so ingestion has a target container."}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Dataset source authority: {activeDatasetState.source === "none" ? "No selection" : activeDatasetState.source}
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
            title="Submit Outcome"
            description="Submission success and handoff are driven by backend response; no optimistic upload completion is faked."
          >
            {submitBlockedReason ? (
              <div className="rounded-[1rem] border border-amber-500/35 bg-amber-50 px-4 py-4 text-sm text-amber-950 dark:bg-amber-950/35 dark:text-amber-200">
                {submitBlockedReason}
              </div>
            ) : null}

            {submitState ? (
              <div
                className={cx(
                  "mt-3 rounded-[1rem] border px-4 py-4 text-sm",
                  submitState.tone === "success"
                    ? "border-emerald-500/35 bg-emerald-500/10 text-foreground"
                    : "border-amber-500/35 bg-amber-500/10 text-foreground",
                )}
              >
                {submitState.message}
              </div>
            ) : null}

            {submitResult ? (
              <div className="mt-3 rounded-[1rem] border border-border bg-surface px-4 py-4 text-sm">
                <p className="font-semibold text-foreground">
                  {submitResult.traceCount} trace(s) are now attached to {submitResult.designName}.
                </p>
                <p className="mt-2 text-muted-foreground">
                  Dataset {submitResult.datasetName} ({submitResult.datasetId}) · Design{" "}
                  {submitResult.designId}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href={`/dataset?datasetId=${encodeURIComponent(submitResult.datasetId)}`}
                    className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    <ArrowRight className="h-4 w-4" />
                    Handoff to Dataset
                  </Link>
                  <Link
                    href={`/raw-data?datasetId=${encodeURIComponent(submitResult.datasetId)}`}
                    className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    <ArrowRight className="h-4 w-4" />
                    Handoff to Raw Data Browser
                  </Link>
                </div>
              </div>
            ) : null}
          </SurfacePanel>
        </div>
      </section>
    </div>
  );
}
