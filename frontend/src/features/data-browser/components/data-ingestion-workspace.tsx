"use client";

import { useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import useSWR from "swr";
import {
  AlertTriangle,
  ChevronDown,
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
  listDesignBrowseRows,
} from "@/lib/api/datasets";
import { useActiveDataset } from "@/lib/app-state";
import { AppSelectField, type AppSelectOption } from "@/features/shared/components/app-select";
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
import type { DesignBrowseRow } from "@/features/data-browser/lib/contracts";

type IngestionScope = "measurement" | "layout_simulation";
type TargetDesignMode = "existing" | "create";

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

type TargetDesignDecision = Readonly<{
  mode: TargetDesignMode;
  designId: string | null;
  designName: string;
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

function isActiveDesign(design: DesignBrowseRow) {
  return design.lifecycle_state === "active";
}

function buildDesignOptions(designs: readonly DesignBrowseRow[]): readonly AppSelectOption[] {
  return designs.filter(isActiveDesign).map((design) => ({
    value: design.design_id,
    label: design.name,
    description: `${design.trace_count} traces · ${design.design_id}`,
  }));
}

export function DataIngestionWorkspace() {
  const [selectedScope, setSelectedScope] = useState<IngestionScope>("measurement");
  const [targetDesignMode, setTargetDesignMode] = useState<TargetDesignMode>("create");
  const [selectedDesignId, setSelectedDesignId] = useState("");
  const [createDesignName, setCreateDesignName] = useState("");
  const [provenanceLabel, setProvenanceLabel] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<readonly UploadFileValidation[]>([]);
  const [submitState, setSubmitState] = useState<SubmitState>(null);
  const [fileImportStatuses, setFileImportStatuses] = useState<
    Readonly<Record<string, FileImportStatus>>
  >({});
  const [isParsingFile, setIsParsingFile] = useState(false);
  const [isDropActive, setIsDropActive] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const activeDatasetState = useActiveDataset();
  const activeDataset = activeDatasetState.activeDataset;
  const activeDatasetId = activeDataset?.datasetId ?? null;
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const lastSuggestedLabelsRef = useRef({
    createDesignName: "",
    provenanceLabel: "",
  });
  const profileQuery = useSWR(
    activeDatasetId ? datasetProfileKey(activeDatasetId) : null,
    () => (activeDatasetId ? getDatasetProfile(activeDatasetId) : Promise.resolve(undefined)),
  );
  const designsQuery = useSWR(
    activeDatasetId ? ["data-ingestion-designs", activeDatasetId] : null,
    () =>
      activeDatasetId
        ? listDesignBrowseRows(activeDatasetId, { limit: 50 })
        : Promise.resolve(undefined),
  );

  const selectedScopeSummary = useMemo(
    () => ingestionScopes.find((scope) => scope.id === selectedScope) ?? ingestionScopes[0],
    [selectedScope],
  );
  const fileSummary = useMemo(() => summarizeFiles(selectedFiles), [selectedFiles]);
  const targetDesignOptions = useMemo(
    () => buildDesignOptions(designsQuery.data?.rows ?? []),
    [designsQuery.data?.rows],
  );
  const canIngest = Boolean(profileQuery.data?.allowed_actions.ingest_raw_data);
  const targetDesignDecision: TargetDesignDecision = useMemo(() => {
    if (targetDesignMode === "existing") {
      const selectedDesign = (designsQuery.data?.rows ?? []).find(
        (design) => design.design_id === selectedDesignId && isActiveDesign(design),
      );
      return {
        mode: "existing",
        designId: selectedDesign?.design_id ?? null,
        designName: selectedDesign?.name ?? "",
      };
    }

    return {
      mode: "create",
      designId: null,
      designName: createDesignName.trim(),
    };
  }, [createDesignName, designsQuery.data?.rows, selectedDesignId, targetDesignMode]);

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
            : designsQuery.isLoading
              ? "Loading target design scopes..."
              : targetDesignMode === "existing" && !targetDesignDecision.designId
                ? "Choose an active target design scope."
                : targetDesignMode === "create" && targetDesignDecision.designName.length === 0
                  ? "Enter a new target design scope name."
              : provenanceLabel.trim().length === 0
                ? "Provenance label is required."
                : null;

  async function parseSelectedFiles(files: readonly File[]) {
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
      setCreateDesignName((current) =>
        !current || current === previousSuggestions.createDesignName
          ? designSuggestion
          : current,
      );
      setProvenanceLabel((current) =>
        !current || current === previousSuggestions.provenanceLabel
          ? provenanceSuggestion
          : current,
      );
      lastSuggestedLabelsRef.current = {
        createDesignName: designSuggestion,
        provenanceLabel: provenanceSuggestion,
      };
    } catch (error) {
      setSubmitState({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to read the selected CSV files.",
      });
    } finally {
      setIsParsingFile(false);
    }
  }

  async function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    await parseSelectedFiles(files);
    event.currentTarget.value = "";
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setIsDropActive(true);
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    const nextTarget = event.relatedTarget;
    if (!nextTarget || !event.currentTarget.contains(nextTarget as Node)) {
      setIsDropActive(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDropActive(false);
    const csvFiles = Array.from(event.dataTransfer.files).filter(
      (file) => file.type === "text/csv" || file.name.toLowerCase().endsWith(".csv"),
    );

    if (csvFiles.length === 0) {
      setSubmitState({
        tone: "warning",
        message: "Drop one or more CSV files to validate before importing.",
      });
      return;
    }

    void parseSelectedFiles(csvFiles);
  }

  function clearFiles() {
    setSelectedFiles([]);
    setSubmitState(null);
    setFileImportStatuses({});
    lastSuggestedLabelsRef.current = {
      createDesignName: "",
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
    let batchCreatedDesignId: string | null = null;

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
        const ingestionDesignId =
          targetDesignDecision.mode === "existing"
            ? targetDesignDecision.designId
            : batchCreatedDesignId;
        const result = await ingestRawData(
          activeDataset.datasetId,
          buildUploadFirstIngestionDraft({
            kind: selectedScope,
            designName: targetDesignDecision.designName,
            designId: ingestionDesignId,
            provenanceLabel:
              fileSummary.validFiles.length > 1
                ? `${provenanceLabel} · ${file.name}`
                : provenanceLabel,
            validation,
          }),
        );
        successCount += 1;
        traceCount += result.traces.length;
        if (targetDesignDecision.mode === "create" && !batchCreatedDesignId) {
          batchCreatedDesignId = result.design.design_id;
        }
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

  const hasSelectedFiles = selectedFiles.length > 0;
  const validationSummaryTone =
    fileSummary.invalidFiles.length > 0
      ? "warning"
      : fileSummary.validFiles.length > 0
        ? "success"
        : "default";
  const validationSummaryLabel = isParsingFile
    ? "Validating files..."
    : hasSelectedFiles
      ? `${fileSummary.validFiles.length} ready / ${selectedFiles.length} total`
      : "Awaiting CSV upload";
  const importTargetSummary =
    targetDesignMode === "existing"
      ? targetDesignDecision.designName || "Choose an existing scope"
      : targetDesignDecision.designName || "New scope from filename";
  const importDetailNeedsAttention = Boolean(
    hasSelectedFiles &&
      ((targetDesignMode === "existing" && !targetDesignDecision.designId) ||
        (targetDesignMode === "create" && targetDesignDecision.designName.length === 0) ||
        provenanceLabel.trim().length === 0),
  );
  const shouldShowSubmitBlockedReason = Boolean(
    submitBlockedReason &&
      (submitBlockedReason !== "Choose one or more CSV files to validate and preprocess." ||
        hasSelectedFiles),
  );
  const successfulImportCount = Object.values(fileImportStatuses).filter(
    (status) => status.state === "success",
  ).length;
  const importActionCount = fileSummary.validFiles.length
    ? `${fileSummary.validFiles.length} `
    : "";

  return (
    <div className="space-y-6">
      <SurfaceHeader
        eyebrow="Raw-Data Intake"
        title="Data Ingestion"
        description="Upload CSV files, validate the batch, and import ready traces into the active dataset."
        actions={<SurfaceTag tone="primary">{selectedScopeSummary.title}</SurfaceTag>}
      />

      <SurfacePanel
        title="Upload-first intake"
        description="Start with files. Validation and import details stay compact unless the batch needs attention."
      >
        <div className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Trace Type
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Choose the parser contract before selecting files.
              </p>
            </div>
            <div
              role="group"
              aria-label="Trace type"
              className="inline-flex w-full rounded-full border border-border bg-background p-1 sm:w-auto"
            >
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
                    title={scope.description}
                    className={cx(
                      "min-h-9 flex-1 cursor-pointer rounded-full px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 sm:flex-none",
                      isSelected
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-primary/10 hover:text-foreground",
                    )}
                  >
                    {scope.title}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            aria-busy={isParsingFile}
            className={cx(
              "rounded-[1rem] border border-dashed px-5 py-6 transition",
              isDropActive
                ? "border-primary/60 bg-primary/10"
                : "border-border bg-background hover:border-primary/35 hover:bg-surface",
            )}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex min-w-0 gap-4">
                <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  {isParsingFile ? (
                    <LoaderCircle className="h-5 w-5 animate-spin" />
                  ) : (
                    <Upload className="h-5 w-5" />
                  )}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    {hasSelectedFiles
                      ? `${selectedFiles.length} file(s) selected`
                      : "Drop CSV files here"}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    CSV Files validate immediately. HFSS sweeps can include frequency,
                    parameter, and response columns.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    fileInputRef.current?.click();
                  }}
                  disabled={isParsingFile || isSubmitting}
                  className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Upload className="h-4 w-4" />
                  Choose CSV files
                </button>
                {selectedFiles.length > 0 ? (
                  <button
                    type="button"
                    onClick={clearFiles}
                    disabled={isSubmitting}
                    className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
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

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                Validation
              </p>
              <div className="mt-2 flex items-center gap-2">
                <SurfaceTag tone={validationSummaryTone}>{validationSummaryLabel}</SurfaceTag>
              </div>
            </div>
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                Trace Count
              </p>
              <p className="mt-2 text-sm font-semibold text-foreground">
                {fileSummary.traceCount}
              </p>
            </div>
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                Import Target
              </p>
              <p className="mt-2 truncate text-sm font-semibold text-foreground">
                {importTargetSummary}
              </p>
            </div>
          </div>

          <details className="group rounded-[1rem] border border-border bg-background">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <FileSpreadsheet className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">
                    Validation & Preprocess
                  </span>
                  <SurfaceTag tone={validationSummaryTone}>{validationSummaryLabel}</SurfaceTag>
                  {fileSummary.invalidFiles.length > 0 ? (
                    <SurfaceTag tone="warning">{fileSummary.invalidFiles.length} error</SurfaceTag>
                  ) : null}
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  Open for per-file, per-trace, axes, shape, and sweep-axis details.
                </span>
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition group-open:rotate-180" />
            </summary>

            <div className="border-t border-border px-4 py-4">
              {selectedFiles.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Upload CSV files to validate them against the fixed intake contract.
                </p>
              ) : (
                <div className="space-y-4">
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
                            <details className="group mt-3 rounded-xl border border-border bg-background">
                              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 [&::-webkit-details-marker]:hidden">
                                <span className="text-sm font-medium text-foreground">
                                  Trace details
                                </span>
                                <ChevronDown className="h-4 w-4 text-muted-foreground transition group-open:rotate-180" />
                              </summary>
                              <div className="space-y-2 border-t border-border px-3 py-3">
                                {validation.traces.map((trace) => (
                                  <div
                                    key={`${file.id}-${trace.parameter}-${trace.representation}-${trace.headerLabel}`}
                                    className="rounded-xl border border-border bg-surface px-3 py-3"
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
                            </details>
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
                </div>
              )}
            </div>
          </details>

          <details className="group rounded-[1rem] border border-border bg-background">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Database className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">Import Details</span>
                  <SurfaceTag tone={importDetailNeedsAttention ? "warning" : "default"}>
                    {importDetailNeedsAttention ? "Needs input" : importTargetSummary}
                  </SurfaceTag>
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  Target Dataset, Target Design Scope, and Provenance Label are ready to adjust.
                </span>
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition group-open:rotate-180" />
            </summary>

            <div className="space-y-4 border-t border-border px-4 py-4">
              <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
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

              <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Target Design Scope
                    </p>
                    <p className="mt-2 text-sm font-semibold text-foreground">
                      Choose an existing active scope or create a new one
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Existing targets submit an explicit design_id. New-scope names are create defaults only.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(["existing", "create"] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => {
                          setTargetDesignMode(mode);
                        }}
                        aria-pressed={targetDesignMode === mode}
                        className={cx(
                          "inline-flex min-h-10 cursor-pointer items-center rounded-full border px-4 py-2 text-sm font-medium transition",
                          targetDesignMode === mode
                            ? "border-primary/35 bg-primary/10 text-foreground"
                            : "border-border bg-background text-muted-foreground hover:border-primary/30 hover:text-foreground",
                        )}
                      >
                        {mode === "existing" ? "Use Existing" : "Create New"}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-4">
                  {targetDesignMode === "existing" ? (
                    <>
                      <AppSelectField
                        label="Existing Target Design Scope"
                        value={selectedDesignId}
                        onChange={setSelectedDesignId}
                        options={targetDesignOptions}
                        placeholder={
                          targetDesignOptions.length > 0
                            ? "Select an active design scope"
                            : "No active design scopes"
                        }
                        disabled={isSubmitting || designsQuery.isLoading}
                      />
                      {designsQuery.error ? (
                        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
                          Unable to load target design scopes. {String(designsQuery.error.message)}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <label className="block rounded-xl border border-border bg-background px-4 py-3">
                      <span className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        New Target Design Scope Name
                      </span>
                      <input
                        value={createDesignName}
                        onChange={(event) => {
                          setCreateDesignName(event.target.value);
                        }}
                        disabled={isSubmitting}
                        className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                        placeholder="PF6FQ Q0"
                      />
                      <p className="mt-2 text-xs text-muted-foreground">
                        Filename-derived suggestions prefill this field, but they never select an existing scope implicitly.
                      </p>
                    </label>
                  )}
                </div>
              </div>

              <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
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
          </details>

          {shouldShowSubmitBlockedReason ? (
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
            Import {importActionCount}
            {selectedScopeSummary.title} CSV
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

          {successfulImportCount > 0 ? (
            <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/12 text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    {successfulImportCount} file(s) imported.
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Open validation details for individual file status, then review the imported design from Raw Data when you are ready.
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
