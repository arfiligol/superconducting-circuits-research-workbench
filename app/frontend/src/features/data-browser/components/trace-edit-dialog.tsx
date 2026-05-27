"use client";

import { useEffect, useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { LoaderCircle, Save } from "lucide-react";
import { z } from "zod";

import { ShellSidePanel } from "@/components/layout/shell-side-panel";
import { TraceEditNumericGrid } from "@/features/data-browser/components/trace-edit-numeric-grid";
import {
  humanizeTraceLabel,
} from "@/features/data-browser/lib/trace-preview";
import {
  resolveEditableNumericGridModel,
  serializeEditableNumericGridModel,
  updateEditableNumericGridCell,
} from "@/features/data-browser/lib/trace-edit-grid";
import { AppSelectField } from "@/features/shared/components/app-select";
import {
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";

import type {
  TraceEditDetail,
  TraceUpdateDraft,
} from "@/features/data-browser/lib/contracts";

const traceEditSchema = z.object({
  parameter: z.string().trim().min(1, "Parameter is required."),
  representation: z.string().trim().min(1, "View is required."),
  provenance_summary: z.string().trim().min(1, "Notes are required."),
});

type TraceEditValues = z.infer<typeof traceEditSchema>;

const emptyEditValues: TraceEditValues = {
  parameter: "",
  representation: "",
  provenance_summary: "",
};

const representationOptions = [
  { value: "real", label: "Real" },
  { value: "imaginary", label: "Imaginary" },
  { value: "magnitude", label: "Magnitude" },
  { value: "phase", label: "Phase" },
] as const;

export function TraceEditDialog({
  open,
  detail,
  isLoading,
  error,
  saveErrorMessage,
  isSaving,
  onClose,
  onSave,
}: Readonly<{
  open: boolean;
  detail: TraceEditDetail | null;
  isLoading: boolean;
  error?: Error;
  saveErrorMessage?: string | null;
  isSaving: boolean;
  onClose: () => void;
  onSave: (draft: TraceUpdateDraft) => Promise<void>;
}>) {
  const form = useForm<TraceEditValues>({
    resolver: zodResolver(traceEditSchema),
    defaultValues: emptyEditValues,
  });
  const gridModel = useMemo(
    () => (detail ? resolveEditableNumericGridModel(detail.editable_numeric_payload) : null),
    [detail],
  );
  const [gridRows, setGridRows] = useState<readonly string[][]>([]);

  useEffect(() => {
    if (!detail) {
      form.reset(emptyEditValues);
      setGridRows([]);
      return;
    }

    form.reset({
      parameter: detail.editable_metadata.parameter,
      representation: detail.editable_metadata.representation,
      provenance_summary: detail.editable_metadata.provenance_summary,
    });
    setGridRows(gridModel?.rows ?? []);
  }, [detail, form, gridModel]);

  async function handleSubmit(values: TraceEditValues) {
    await onSave({
      parameter: values.parameter.trim(),
      representation: values.representation.trim(),
      provenance_summary: values.provenance_summary.trim(),
      numeric_payload: gridModel
        ? serializeEditableNumericGridModel(gridModel, gridRows)
        : undefined,
    });
  }

  return (
    <ShellSidePanel
      open={open}
      onClose={onClose}
      variant="context"
      eyebrow="RAW DATA"
      title={detail ? `Edit ${detail.trace_id}` : "Edit Trace"}
      subtitle="Edit trace metadata and numeric payload through the dedicated edit-authority path."
      className="max-w-[min(1180px,calc(100vw-1.5rem))]"
    >
      {isLoading ? (
        <div className="rounded-[1rem] border border-border bg-background px-4 py-6 text-sm text-muted-foreground">
          Loading editable trace detail...
        </div>
      ) : error ? (
        <div className="rounded-[1rem] border border-amber-500/30 bg-amber-500/10 px-4 py-4 text-sm text-foreground">
          Unable to load the edit-authority trace detail. {error.message}
        </div>
      ) : detail ? (
        <form className="space-y-6" onSubmit={form.handleSubmit(handleSubmit)}>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
            <div className="space-y-4">
              <div className="rounded-[1rem] border border-border bg-surface px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Immutable Context
                </p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <SummaryChip
                    label="Family"
                    value={humanizeTraceLabel(detail.immutable_summary.family)}
                  />
                  <SummaryChip
                    label="Mode"
                    value={humanizeTraceLabel(detail.immutable_summary.trace_mode_group)}
                  />
                  <SummaryChip
                    label="Source"
                    value={humanizeTraceLabel(detail.immutable_summary.source_kind)}
                  />
                  <SummaryChip
                    label="Stage"
                    value={humanizeTraceLabel(detail.immutable_summary.stage_kind)}
                  />
                </div>
              </div>

              <div className="rounded-[1rem] border border-border bg-surface px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Mutation Policy
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {detail.mutation_policy_summary}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SurfaceTag tone={detail.allowed_actions.edit ? "success" : "warning"}>
                      {detail.allowed_actions.edit ? "Editable" : "Inspect only"}
                    </SurfaceTag>
                    <SurfaceTag tone={detail.allowed_actions.delete ? "warning" : "default"}>
                      {detail.allowed_actions.delete ? "Deletable" : "Delete blocked"}
                    </SurfaceTag>
                  </div>
                </div>
              </div>

              {saveErrorMessage ? (
                <div
                  className={cx(
                    "rounded-[1rem] border px-4 py-4 text-sm",
                    resolveSurfaceInsetToneClass("error"),
                  )}
                >
                  {saveErrorMessage}
                </div>
              ) : null}
            </div>

            <div className="space-y-4">
              <label className="block rounded-[1rem] border border-border bg-surface px-4 py-4">
                <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Parameter
                </p>
                <input
                  {...form.register("parameter")}
                  className="w-full rounded-[0.95rem] border border-border/85 bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                  placeholder="Enter the trace parameter"
                />
                {form.formState.errors.parameter ? (
                  <p className="mt-2 text-sm text-rose-700">
                    {form.formState.errors.parameter.message}
                  </p>
                ) : null}
              </label>

              <Controller
                control={form.control}
                name="representation"
                render={({ field }) => (
                  <AppSelectField
                    label="View"
                    value={field.value}
                    onChange={field.onChange}
                    options={representationOptions}
                    placeholder="Select a view"
                  />
                )}
              />
              {form.formState.errors.representation ? (
                <p className="text-sm text-rose-700">
                  {form.formState.errors.representation.message}
                </p>
              ) : null}

              <label className="block rounded-[1rem] border border-border bg-surface px-4 py-4">
                <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Notes
                </p>
                <textarea
                  {...form.register("provenance_summary")}
                  rows={4}
                  className="w-full rounded-[0.95rem] border border-border/85 bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                  placeholder="Summarize where this trace came from"
                />
                {form.formState.errors.provenance_summary ? (
                  <p className="mt-2 text-sm text-rose-700">
                    {form.formState.errors.provenance_summary.message}
                  </p>
                ) : null}
              </label>
            </div>
          </div>

          <TraceEditNumericGrid
            model={gridModel}
            rows={gridRows}
            disabled={isSaving || !detail.allowed_actions.edit}
            onCellChange={(rowIndex, columnIndex, value) => {
              setGridRows((current) =>
                updateEditableNumericGridCell(current, rowIndex, columnIndex, value),
              );
            }}
          />

          <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-5">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving || !detail.allowed_actions.edit}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSaving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {isSaving ? "Saving..." : "Save Trace"}
            </button>
          </div>
        </form>
      ) : (
        <div className="rounded-[1rem] border border-dashed border-border bg-background px-4 py-6 text-sm text-muted-foreground">
          Choose one trace to open the edit flow.
        </div>
      )}
    </ShellSidePanel>
  );
}

function SummaryChip({
  label,
  value,
}: Readonly<{
  label: string;
  value: string;
}>) {
  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}
