"use client";

import { useMemo, useRef, useState, type ChangeEvent } from "react";
import useSWR from "swr";
import {
  AlertTriangle,
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
    description: "Import measured traces from CSV files into the active dataset.",
  },
  {
    id: "layout_simulation",
    title: "Layout Simulation",
    description: "Import EM or layout-solver traces from one or more CSV files.",
  },
] as const;

type UploadFileValidation = Readonly<{
  id: string;
  name: string;
  text: string;
  validation: UploadValidationResult | null;
  error: string | null;
}>;

type SubmitState = Readonly<{
  tone: "success" | "warning";
  message: string;
}> | null;

type FileImportStatus = Readonly<{
  state: "idle" | "submitting" | "success" | "error";
  message: string | null;
}>;

type BatchSummary = Readonly<{
  validFiles: readonly UploadFileValidation[];
  invalidFiles: readonly UploadFileValidation[];
  traceCount: number;
  ndFileCount: number;
  axisLabels: readonly string[];
  shapeLabels: readonly string[];
  sweepAxisLabels: readonly string[];
}>;

function fileImportIdle(): FileImportStatus {
  return { state: "idle", message: null };
}

function buildFileId(file: File, index: number) {
  return `${file.name}:${file.size}:${file.lastModified}:${index}`;
}

function formatAxisLabel(axis: Readonly<{ name: string; unit: string }>) {
  return axis.unit ? `${axis.name} (${axis.unit})` : axis.name;
}

function validationAxes(validation: UploadValidationResult) {
  return validation.draftTraces[0]?.axes ?? [];
}

function validationIsNd(validation: UploadValidationResult) {
  return validation.draftTraces.some((trace) => trace.preview_payload.kind === "nd_grid");
}

function validationShapeLabel(validation: UploadValidationResult) {
  const axes = validationAxes(validation);
  return axes.length > 0 ? axes.map((axis) => axis.length).join(" x ") : "Unknown";
}

function validationAxisLabel(validation: UploadValidationResult) {
  const axes = validationAxes(validation);
  return axes.length > 0 ? axes.map(formatAxisLabel).join(" / ") : "Axis unavailable";
}

function validationSweepAxisLabel(validation: UploadValidationResult) {
  const axes = validationAxes(validation);
  const sweepAxis = axes[1];
  return sweepAxis ? formatAxisLabel(sweepAxis) : "1D scalar";
}

function summarizeFiles(files: readonly UploadFileValidation[]): BatchSummary {
  const validFiles = files.filter((file) => file.validation);
  const invalidFiles = files.filter((file) => file.error);
  const traceCount = validFiles.reduce(
    (total, file) => total + (file.validation?.traces.length ?? 0),
    0,
  );
  const ndFileCount = validFiles.filter(
    (file) => file.validation && validationIsNd(file.validation),
  ).length;

  return {
    validFiles,
    invalidFiles,
    traceCount,
    ndFileCount,
    axisLabels: [...new Set(validFiles.map((file) => validationAxisLabel(file.validation!)))],
    shapeLabels: [...new Set(validFiles.map((file) => validationShapeLabel(file.validation!)))],
    sweepAxisLabels: [
      ...new Set(validFiles.map((file) => validationSweepAxisLabel(file.validation!))),
    ],
  };
}

function resolveBatchDesignSuggestion(files: readonly UploadFileValidation[]) {
  const suggestions = files
    .map((file) => file.validation?.designNameSuggestion)
    .filter((value): value is string => Boolean(value));
  if (suggestions.length === 0) {
    return "";
  }

  const [firstSuggestion] = suggestions;
  return suggestions.every((suggestion) => suggestion === firstSuggestion)
    ? firstSuggestion
    : firstSuggestion ?? "";
}

function buildBatchProvenanceLabel(
  scopeTitle: string,
  files: readonly UploadFileValidation[],
  designSuggestion: string,
) {
  const validFiles = files.filter((file) => file.validation);
  const fileCount = validFiles.length;
  const scopeLabel = `${scopeTitle} import`;
  if (fileCount <= 1) {
    return validFiles[0]?.validation?.provenanceLabelSuggestion ?? scopeLabel;
  }

  return designSuggestion
    ? `${scopeLabel} · ${designSuggestion} · ${fileCount} files`
    : `${scopeLabel} · ${fileCount} files`;
}

export function DataIngestionWorkspace() {
  const [selectedScope, setSelectedScope] = useState<IngestionScope>("measurement");
  const [designName, setDesignName] = useState("");
  const [provenanceLabel, setProvenanceLabel] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<readonly UploadFileValidation[]>([]);
  const [submitState, setSubmitState] = useState<SubmitState>(null);
  const [fileImportStatuses, setFileImportStatuses] = useState<
    Readonly<Record<string, FileImportStatus>>
  >({});
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
  const fileSummary = useMemo(() => summarizeFiles(selectedFiles), [selectedFiles]);
  const canIngest = Boolean(profileQuery.data?.allowed_actions.ingest_raw_data);

  const submitBlockedReason = !activeDataset
    ? "Attach an active dataset in the shell before importing raw data."
    : profileQuery.isLoading
      ? "Checking whether this dataset can accept imports..."
      : !canIngest
        ? "Raw-data import is unavailable for the current dataset."
        : selectedFiles.length === 0
          ? "Choose one or more CSV files to validate and preprocess."
          : fileSummary.validFiles.length === 0
            ? "Resolve at least one CSV validation issue before importing."
            : designName.trim().length === 0
              ? "Design name is required."
              : provenanceLabel.trim().length === 0
                ? "Provenance label is required."
                : null;

  async function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) {
      return;
    }

    setIsParsingFile(true);
    setSubmitState(null);
    setFileImportStatuses({});

    try {
      const parsedFiles = await Promise.all(
        files.map(async (file, index): Promise<UploadFileValidation> => {
          const text = await file.text();
          try {
            return {
              id: buildFileId(file, index),
              name: file.name,
              text,
              validation: validateUploadFirstCsv({
                kind: selectedScope,
                fileName: file.name,
                fileText: text,
              }),
              error: null,
            };
          } catch (error) {
            return {
              id: buildFileId(file, index),
              name: file.name,
              text,
              validation: null,
              error:
                error instanceof Error
                  ? error.message
                  : "Unable to validate the uploaded CSV against the intake contract.",
            };
          }
        }),
      );

      setSelectedFiles(parsedFiles);
      const designSuggestion = resolveBatchDesignSuggestion(parsedFiles);
      const provenanceSuggestion = buildBatchProvenanceLabel(
        selectedScopeSummary.title,
        parsedFiles,
        designSuggestion,
      );
      const previousSuggestions = lastSuggestedLabelsRef.current;
      setDesignName((current) =>
        !current || current === previousSuggestions.designName ? designSuggestion : current,
      );
      setProvenanceLabel((current) =>
        !current || current === previousSuggestions.provenanceLabel
          ? provenanceSuggestion
          : current,
      );
      lastSuggestedLabelsRef.current = {
        designName: designSuggestion,
        provenanceLabel: provenanceSuggestion,
      };
    } catch (error) {
      setSubmitState({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to read the selected CSV files.",
      });
    } finally {
      setIsParsingFile(false);
      event.target.value = "";
    }
  }

  function clearFiles() {
    setSelectedFiles([]);
    setSubmitState(null);
    setFileImportStatuses({});
    lastSuggestedLabelsRef.current = {
      designName: "",
      provenanceLabel: "",
    };
  }

  async function handleSubmit() {
    if (!activeDataset || submitBlockedReason) {
      setSubmitState({
        tone: "warning",
        message: submitBlockedReason ?? "Upload and validate CSV files before importing.",
      });
      return;
    }

    setIsSubmitting(true);
    setSubmitState(null);
    setFileImportStatuses(
      Object.fromEntries(selectedFiles.map((file) => [file.id, fileImportIdle()])),
    );

    let successCount = 0;
    let failureCount = 0;
    let traceCount = 0;

    for (const file of fileSummary.validFiles) {
      const validation = file.validation;
      if (!validation) {
        continue;
      }

      setFileImportStatuses((current) => ({
        ...current,
        [file.id]: { state: "submitting", message: "Importing..." },
      }));

      try {
        const result = await ingestRawData(
          activeDataset.datasetId,
          buildUploadFirstIngestionDraft({
            kind: selectedScope,
            designName,
            provenanceLabel:
              fileSummary.validFiles.length > 1
                ? `${provenanceLabel} · ${file.name}`
                : provenanceLabel,
            validation,
          }),
        );
        successCount += 1;
        traceCount += result.traces.length;
        setFileImportStatuses((current) => ({
          ...current,
          [file.id]: {
            state: "success",
            message: `Imported ${result.traces.length} trace(s) into ${result.design.name}.`,
          },
        }));
      } catch (error) {
        failureCount += 1;
        setFileImportStatuses((current) => ({
          ...current,
          [file.id]: {
            state: "error",
            message: error instanceof Error ? error.message : "Unable to submit ingestion.",
          },
        }));
      }
    }

    setSubmitState({
      tone: failureCount > 0 ? "warning" : "success",
      message:
        failureCount > 0
          ? `Imported ${successCount} file(s); ${failureCount} file(s) failed.`
          : `Imported ${successCount} file(s) and ${traceCount} trace(s).`,
    });
    setIsSubmitting(false);
  }

  return (
    <div className="space-y-8">
      <SurfaceHeader
        eyebrow="Raw-Data Intake"
        title="Data Ingestion"
        description="Upload CSV files, review parsed results, and import them into the active dataset."
        actions={<SurfaceTag tone="primary">{selectedScopeSummary.title}</SurfaceTag>}
      />

      <SurfacePanel
        title="Upload-first intake"
        description="Choose the trace type, confirm the target dataset, upload one or more CSV files, and review validation before import."
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
                    clearFiles();
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
                  CSV Files
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {selectedFiles.length > 0
                    ? `${selectedFiles.length} file(s) selected`
                    : "Choose CSV files"}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  HFSS sweeps can use three columns such as
                  <span className="font-medium text-foreground"> L_jun [nH]</span>,
                  <span className="font-medium text-foreground"> Freq [GHz]</span>, and
                  <span className="font-medium text-foreground"> im(Yt(...)) []</span>.
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
                  Choose CSV files
                </button>
                {selectedFiles.length > 0 ? (
                  <button
                    type="button"
                    onClick={clearFiles}
                    className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    <X className="h-4 w-4" />
                    Clear files
                  </button>
                ) : null}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                multiple
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
                  {fileSummary.validFiles.length > 0 ? (
                    <SurfaceTag tone="primary">
                      {fileSummary.validFiles.length} ready
                    </SurfaceTag>
                  ) : null}
                  {fileSummary.invalidFiles.length > 0 ? (
                    <SurfaceTag tone="warning">
                      {fileSummary.invalidFiles.length} error
                    </SurfaceTag>
                  ) : null}
                </div>

                {selectedFiles.length === 0 ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Upload CSV files to validate them against the fixed intake contract.
                  </p>
                ) : (
                  <div className="mt-4 space-y-4">
                    <div className="grid gap-3 md:grid-cols-4">
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Files
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {fileSummary.validFiles.length} valid / {selectedFiles.length} total
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Trace Count
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {fileSummary.traceCount}
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Shape
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {fileSummary.shapeLabels.join(", ") || "No valid shape"}
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          Sweep Axis
                        </p>
                        <p className="mt-2 text-sm font-semibold text-foreground">
                          {fileSummary.sweepAxisLabels.join(", ") || "No valid sweep"}
                        </p>
                      </div>
                    </div>

                    <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        Axes
                      </p>
                      <p className="mt-2 text-sm font-semibold text-foreground">
                        {fileSummary.axisLabels.join(", ") || "No valid axes"}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {fileSummary.ndFileCount} ND file(s),{" "}
                        {fileSummary.validFiles.length - fileSummary.ndFileCount} scalar file(s)
                      </p>
                    </div>

                    <div className="space-y-3">
                      {selectedFiles.map((file) => {
                        const validation = file.validation;
                        const importStatus = fileImportStatuses[file.id] ?? fileImportIdle();
                        return (
                          <div
                            key={file.id}
                            className="rounded-[0.95rem] border border-border bg-surface px-4 py-3"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-foreground">
                                  {file.name}
                                </p>
                                {validation ? (
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {validation.traces.length} trace(s) ·{" "}
                                    {validationShapeLabel(validation)} ·{" "}
                                    {validationSweepAxisLabel(validation)}
                                  </p>
                                ) : (
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    Validation failed
                                  </p>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <SurfaceTag tone={validation ? "success" : "warning"}>
                                  {validation ? "Ready" : "Error"}
                                </SurfaceTag>
                                {importStatus.state !== "idle" ? (
                                  <SurfaceTag
                                    tone={
                                      importStatus.state === "success"
                                        ? "success"
                                        : importStatus.state === "error"
                                          ? "warning"
                                          : "primary"
                                    }
                                  >
                                    {importStatus.state}
                                  </SurfaceTag>
                                ) : null}
                              </div>
                            </div>

                            {file.error ? (
                              <div className="mt-3 flex gap-2 rounded-xl border border-amber-500/35 bg-amber-500/10 px-3 py-3 text-sm text-foreground">
                                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-300" />
                                <span>{file.error}</span>
                              </div>
                            ) : null}

                            {validation ? (
                              <div className="mt-3 space-y-2">
                                {validation.traces.map((trace) => (
                                  <div
                                    key={`${file.id}-${trace.parameter}-${trace.representation}-${trace.headerLabel}`}
                                    className="rounded-xl border border-border bg-background px-3 py-3"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <p className="text-sm font-semibold text-foreground">
                                        {trace.parameter} · {trace.representation}
                                      </p>
                                      <SurfaceTag>{trace.family}</SurfaceTag>
                                    </div>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                      Column {trace.headerLabel} · {trace.pointCount} value(s)
                                    </p>
                                  </div>
                                ))}
                              </div>
                            ) : null}

                            {importStatus.message ? (
                              <p className="mt-3 text-sm text-muted-foreground">
                                {importStatus.message}
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
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
                          placeholder="PF6FQ Q0"
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
                          placeholder="Layout Simulation import · PF6FQ Q0"
                        />
                      </label>
                    </div>
                  </div>
                )}
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
            Import {fileSummary.validFiles.length || ""} {selectedScopeSummary.title} CSV
            {fileSummary.validFiles.length === 1 ? "" : "s"}
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

          {Object.values(fileImportStatuses).some((status) => status.state === "success") ? (
            <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/12 text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    Imported files stay listed with their individual status.
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Review the imported design from Raw Data when you are ready.
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
