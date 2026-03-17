"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import useSWR from "swr";
import {
  CheckCircle2,
  Database,
  FileSpreadsheet,
  LoaderCircle,
  Upload,
  X,
} from "lucide-react";

import {
  datasetProfileKey,
  getDatasetProfile,
  ingestRawData,
} from "@/lib/api/datasets";
import { useActiveDataset } from "@/lib/app-state";
import {
  SurfaceHeader,
  SurfacePanel,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";
import {
  buildUploadFirstIngestionDraft,
  validateUploadFirstCsv,
  type UploadValidationResult,
} from "@/features/data-browser/lib/upload-first-ingestion";

type IngestionScope = "measurement" | "layout_simulation";

const ingestionScopes: ReadonlyArray<
  Readonly<{
    id: IngestionScope;
    title: string;
    description: string;
  }>
> = [
  {
    id: "measurement",
    title: "Measurement",
    description: "Import measured traces from a CSV file into the active dataset.",
  },
  {
    id: "layout_simulation",
    title: "Layout Simulation",
    description: "Import EM or layout-solver traces from a CSV file into the active dataset.",
  },
] as const;

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

type FileDraft = Readonly<{
  name: string;
  text: string;
}>;

type ValidationState = Readonly<{
  tone: "success" | "warning";
  message: string;
}> | null;

export function DataIngestionWorkspace() {
  const [selectedScope, setSelectedScope] = useState<IngestionScope>("measurement");
  const [designName, setDesignName] = useState("");
  const [provenanceLabel, setProvenanceLabel] = useState("");
  const [selectedFile, setSelectedFile] = useState<FileDraft | null>(null);
  const [validation, setValidation] = useState<UploadValidationResult | null>(null);
  const [validationState, setValidationState] = useState<ValidationState>(null);
  const [submitState, setSubmitState] = useState<SubmitState>(null);
  const [submitResult, setSubmitResult] = useState<IngestionResultState>(null);
  const [isParsingFile, setIsParsingFile] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const activeDatasetState = useActiveDataset();
  const activeDataset = activeDatasetState.activeDataset;
  const activeDatasetId = activeDataset?.datasetId ?? null;
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const lastSuggestedLabelsRef = useRef({
    designName: "",
    provenanceLabel: "",
  });
  const profileQuery = useSWR(
    activeDatasetId ? datasetProfileKey(activeDatasetId) : null,
    () => (activeDatasetId ? getDatasetProfile(activeDatasetId) : Promise.resolve(undefined)),
  );

  const selectedScopeSummary = useMemo(
    () => ingestionScopes.find((scope) => scope.id === selectedScope) ?? ingestionScopes[0],
    [selectedScope],
  );
  const canIngest = Boolean(profileQuery.data?.allowed_actions.ingest_raw_data);

  useEffect(() => {
    if (!selectedFile) {
      setValidation(null);
      setValidationState(null);
      lastSuggestedLabelsRef.current = {
        designName: "",
        provenanceLabel: "",
      };
      return;
    }

    setIsParsingFile(true);
    setSubmitState(null);
    setSubmitResult(null);

    try {
      const nextValidation = validateUploadFirstCsv({
        kind: selectedScope,
        fileName: selectedFile.name,
        fileText: selectedFile.text,
      });
      setValidation(nextValidation);
      setValidationState({
        tone: "success",
        message:
          "CSV contract looks valid. The frontend prepared a dataset-ingestion payload from the uploaded file.",
      });

      const previousSuggestions = lastSuggestedLabelsRef.current;
      setDesignName((current) =>
        !current || current === previousSuggestions.designName
          ? nextValidation.designNameSuggestion
          : current,
      );
      setProvenanceLabel((current) =>
        !current || current === previousSuggestions.provenanceLabel
          ? nextValidation.provenanceLabelSuggestion
          : current,
      );
      lastSuggestedLabelsRef.current = {
        designName: nextValidation.designNameSuggestion,
        provenanceLabel: nextValidation.provenanceLabelSuggestion,
      };
    } catch (error) {
      setValidation(null);
      setValidationState({
        tone: "warning",
        message:
          error instanceof Error
            ? error.message
            : "Unable to validate the uploaded CSV against the intake contract.",
      });
    } finally {
      setIsParsingFile(false);
    }
  }, [selectedFile, selectedScope]);

  const submitBlockedReason = !activeDataset
    ? "Attach an active dataset in the shell before importing raw data."
    : profileQuery.isLoading
      ? "Checking dataset ingestion authority..."
      : !canIngest
        ? "The current dataset authority does not allow raw-data ingestion."
        : !selectedFile
          ? "Choose a CSV file to validate and preprocess."
          : !validation
            ? "Resolve the CSV validation issue before importing."
            : designName.trim().length === 0
              ? "Design name is required."
              : provenanceLabel.trim().length === 0
                ? "Provenance label is required."
                : null;

  async function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setIsParsingFile(true);
    setSubmitState(null);
    setSubmitResult(null);

    try {
      const text = await file.text();
      setSelectedFile({
        name: file.name,
        text,
      });
    } catch (error) {
      setValidation(null);
      setValidationState({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to read the selected CSV file.",
      });
      setIsParsingFile(false);
    } finally {
      event.target.value = "";
    }
  }

  async function handleSubmit() {
    if (!activeDataset || !validation || submitBlockedReason) {
      setSubmitState({
        tone: "warning",
        message: submitBlockedReason ?? "Upload and validate a CSV file before importing.",
      });
      return;
    }

    setIsSubmitting(true);
    setSubmitState(null);
    setSubmitResult(null);

    try {
      const result = await ingestRawData(
        activeDataset.datasetId,
        buildUploadFirstIngestionDraft({
          kind: selectedScope,
          designName,
          provenanceLabel,
          validation,
        }),
      );
      setSubmitState({
        tone: "success",
        message: `Imported ${result.traces.length} trace(s) into design ${result.design.name}.`,
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
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw-Data Intake"
        title="Data Ingestion"
        description="Upload a CSV file, validate the intake contract, preprocess it into the current backend ingestion payload, and import it into the active dataset."
        actions={<SurfaceTag tone="primary">{selectedScopeSummary.title}</SurfaceTag>}
      />

      <SurfacePanel
        title="Upload-first intake"
        description="Choose the intake type, confirm the target dataset, upload a CSV file, and review the validation result before import."
      >
        <div className="space-y-5">
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
                      : "border-border bg-background hover:-translate-y-0.5 hover:border-primary/30 hover:bg-surface-elevated hover:shadow-[0_16px_32px_rgba(15,23,42,0.08)]",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-base font-semibold text-foreground">{scope.title}</p>
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

          <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Database className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Target Dataset
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDataset?.name ?? "No active dataset selected"}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {activeDataset
                    ? `${activeDataset.datasetId} · ${activeDataset.visibilityScope} · ${activeDataset.status}`
                    : "Attach a dataset in the header before importing raw data."}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  CSV File
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {selectedFile?.name ?? "Choose CSV file"}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Accepted contract: one frequency column plus one or more series columns named like
                  <span className="font-medium text-foreground"> Y11_imaginary</span> or
                  <span className="font-medium text-foreground"> S21_magnitude</span>.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    fileInputRef.current?.click();
                  }}
                  className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  {isParsingFile ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  Choose CSV file
                </button>
                {selectedFile ? (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFile(null);
                      setValidation(null);
                      setValidationState(null);
                      setSubmitState(null);
                      setSubmitResult(null);
                      lastSuggestedLabelsRef.current = {
                        designName: "",
                        provenanceLabel: "",
                      };
                    }}
                    className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    <X className="h-4 w-4" />
                    Clear file
                  </button>
                ) : null}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={handleFileSelection}
              />
            </div>
          </div>

          <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <FileSpreadsheet className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-foreground">Validation & Preprocess</p>
                  {validation ? <SurfaceTag tone="primary">Ready to import</SurfaceTag> : null}
                </div>
                {validationState ? (
                  <div
                    className={cx(
                      "mt-3 rounded-[0.95rem] border px-4 py-3 text-sm",
                      validationState.tone === "success"
                        ? "border-emerald-500/35 bg-emerald-500/10 text-foreground"
                        : "border-amber-500/35 bg-amber-500/10 text-foreground",
                    )}
                  >
                    {validationState.message}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Upload a CSV file to validate it against the fixed intake contract.
                  </p>
                )}

                {validation ? (
                  <div className="mt-4 space-y-4">
                    <div className="grid gap-3 md:grid-cols-4">
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Sweep Axis
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {validation.axisName} ({validation.axisUnit})
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Points
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {validation.pointCount}
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Preview Series
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {validation.traces.length}
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Intake Type
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {selectedScopeSummary.title}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {validation.traces.map((trace) => (
                        <div
                          key={`${trace.parameter}-${trace.representation}-${trace.headerLabel}`}
                          className="rounded-[0.95rem] border border-border bg-surface px-4 py-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-foreground">
                              {trace.parameter} · {trace.representation}
                            </p>
                            <SurfaceTag>{trace.family}</SurfaceTag>
                          </div>
                          <p className="mt-2 text-sm text-muted-foreground">
                            Column {trace.headerLabel} · {trace.pointCount} points prepared for preview
                            and import.
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          Design Name
                        </span>
                        <input
                          value={designName}
                          onChange={(event) => {
                            setDesignName(event.target.value);
                          }}
                          disabled={isSubmitting}
                          className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                          placeholder="Flux Scan A"
                        />
                      </label>
                      <label className="block rounded-xl border border-border bg-surface px-4 py-3">
                        <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          Provenance Label
                        </span>
                        <input
                          value={provenanceLabel}
                          onChange={(event) => {
                            setProvenanceLabel(event.target.value);
                          }}
                          disabled={isSubmitting}
                          className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                          placeholder="Measurement import · Flux Scan A"
                        />
                      </label>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          {submitBlockedReason ? (
            <div className="rounded-[1rem] border border-amber-500/35 bg-amber-50 px-4 py-4 text-sm text-amber-950 dark:bg-amber-950/35 dark:text-amber-200">
              {submitBlockedReason}
            </div>
          ) : null}

          <button
            type="button"
            onClick={() => {
              void handleSubmit();
            }}
            disabled={Boolean(submitBlockedReason) || isSubmitting}
            className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            Import {selectedScopeSummary.title} CSV
          </button>

          {submitState ? (
            <div
              className={cx(
                "rounded-[1rem] border px-4 py-4 text-sm",
                submitState.tone === "success"
                  ? "border-emerald-500/35 bg-emerald-500/10 text-foreground"
                  : "border-amber-500/35 bg-amber-500/10 text-foreground",
              )}
            >
              {submitState.message}
            </div>
          ) : null}

          {submitResult ? (
            <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/12 text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    Imported {submitResult.traceCount} trace(s) into {submitResult.designName}.
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Dataset {submitResult.datasetName} ({submitResult.datasetId}) now includes design{" "}
                    {submitResult.designId}. Review it from Raw Data when you are ready.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </SurfacePanel>
    </div>
  );
}
