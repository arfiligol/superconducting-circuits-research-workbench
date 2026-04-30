import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

import {
  buildRawDataBrowseHref,
  parseRawDataBrowseState,
  datasetCatalogKey,
  datasetDesignsKey,
  datasetMetricsKey,
  datasetProfileKey,
  traceBatchDeleteKey,
  traceDetailKey,
  traceEditDetailKey,
  traceListKey,
} from "../src/features/data-browser/lib/api";
import {
  resolveTracePreviewContextTags,
  resolveTracePreviewSemantics,
} from "../src/features/data-browser/lib/trace-preview";
import {
  emptyTraceRows,
  resolveSelectableTraceIds,
  resolveSelectedDesignId,
  resolveSelectedTraceId,
} from "../src/features/data-browser/lib/selection";
import {
  resolveEditableNumericGridModel,
  serializeEditableNumericGridModel,
} from "../src/features/data-browser/lib/trace-edit-grid";
import {
  buildUploadFirstIngestionDraft,
  validateUploadFirstCsv,
} from "../src/features/data-browser/lib/upload-first-ingestion";

const runHfssRealDataE2e = process.env.RUN_HFSS_REAL_DATA_E2E === "1";
const defaultPf6fqRawDataRoot =
  "/Users/arfiligol/Github/superconducting-circuits-tutorial/data/raw/layout_simulation/PF6FQ";
const pf6fqRawDataRoot = process.env.PF6FQ_RAW_DATA_ROOT ?? defaultPf6fqRawDataRoot;
const pf6fqRealFiles = {
  xyImY11: `${pf6fqRawDataRoot}/Q0/PF6FQ_Q0_XY_Im_Y11.csv`,
  readoutImY11: `${pf6fqRawDataRoot}/Q0/PF6FQ_Q0_Readout_Im_Y11.csv`,
  xyReYin: `${pf6fqRawDataRoot}/Q0/PF6FQ_Q0_XY_Re_Yin.csv`,
} as const;
const missingPf6fqRealFiles = runHfssRealDataE2e
  ? Object.values(pf6fqRealFiles).filter((path) => !existsSync(path))
  : [];

const dashboardWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/dashboard-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-browser-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataDesignScopesSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-design-scopes-panel.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataTraceSummariesSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-trace-summaries-panel.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataTracePreviewSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-trace-preview-panel.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataControlsSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/raw-data-browser-controls.tsx", import.meta.url),
  ),
  "utf8",
);
const rawDataPreviewDrawerHookSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/hooks/use-raw-data-preview-drawer.ts", import.meta.url),
  ),
  "utf8",
);
const rawDataUiSource = [
  rawDataWorkspaceSource,
  rawDataDesignScopesSource,
  rawDataTraceSummariesSource,
  rawDataTracePreviewSource,
  rawDataControlsSource,
  rawDataPreviewDrawerHookSource,
].join("\n");
const surfaceKitSource = readFileSync(
  fileURLToPath(new URL("../src/features/shared/components/surface-kit.tsx", import.meta.url)),
  "utf8",
);
const datasetWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/dataset-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const dataIngestionWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/components/data-ingestion-workspace.tsx", import.meta.url),
  ),
  "utf8",
);
const dashboardDataHookSource = readFileSync(
  fileURLToPath(new URL("../src/features/data-browser/hooks/use-dashboard-data.ts", import.meta.url)),
  "utf8",
);
const rawDataHookSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/data-browser/hooks/use-raw-data-browser-data.ts", import.meta.url),
  ),
  "utf8",
);

describe("data browser api keys", () => {
  it("keeps stable dashboard and raw-data endpoints", () => {
    expect(datasetCatalogKey).toBe("/api/backend/datasets");
    expect(datasetProfileKey("fluxonium-2025-031")).toBe(
      "/api/backend/datasets/fluxonium-2025-031/profile",
    );
    expect(datasetMetricsKey("fluxonium-2025-031")).toBe(
      "/api/backend/datasets/fluxonium-2025-031/metrics-summary",
    );
    expect(datasetDesignsKey("fluxonium-2025-031")).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs",
    );
    expect(traceListKey("fluxonium-2025-031", "design_flux_scan_a")).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/traces",
    );
    expect(
      traceDetailKey("fluxonium-2025-031", "design_flux_scan_a", "trace_flux_a_measurement"),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/traces/trace_flux_a_measurement",
    );
    expect(
      traceEditDetailKey("fluxonium-2025-031", "design_flux_scan_a", "trace_flux_a_measurement"),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/traces/trace_flux_a_measurement/edit",
    );
    expect(traceBatchDeleteKey("fluxonium-2025-031", "design_flux_scan_a")).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/traces/batch-delete",
    );
  });

  it("encodes ids when building nested dataset and trace paths", () => {
    expect(datasetProfileKey("folder/a b")).toBe("/api/backend/datasets/folder%2Fa%20b/profile");
    expect(traceDetailKey("dataset/a", "design b", "trace/c")).toBe(
      "/api/backend/datasets/dataset%2Fa/designs/design%20b/traces/trace%2Fc",
    );
    expect(traceEditDetailKey("dataset/a", "design b", "trace/c")).toBe(
      "/api/backend/datasets/dataset%2Fa/designs/design%20b/traces/trace%2Fc/edit",
    );
  });
});

describe("raw-data selection helpers", () => {
  const designs = [
    {
      design_id: "design_flux_scan_a",
      dataset_id: "fluxonium-2025-031",
      name: "Flux Scan A",
      source_coverage: { measurement: 2 },
      compare_readiness: "ready",
      trace_count: 3,
      updated_at: "2026-03-14T10:24:00Z",
    },
    {
      design_id: "design_flux_scan_b",
      dataset_id: "fluxonium-2025-031",
      name: "Flux Scan B",
      source_coverage: { measurement: 1 },
      compare_readiness: "inspect_only",
      trace_count: 1,
      updated_at: "2026-03-14T09:50:00Z",
    },
  ] as const;

  const traces = [
    {
      trace_id: "trace_flux_a_measurement",
      dataset_id: "fluxonium-2025-031",
      design_id: "design_flux_scan_a",
      family: "y_matrix",
      parameter: "Y11",
      representation: "imaginary",
      trace_mode_group: "base",
      source_kind: "measurement",
      stage_kind: "postprocess",
      provenance_summary: "Measurement · Post-Processed · batch #4",
      allowed_actions: {
        edit: true,
        delete: true,
      },
      mutation_policy_summary: "Editable trace with dataset-local delete authority.",
    },
    {
      trace_id: "trace_flux_a_layout",
      dataset_id: "fluxonium-2025-031",
      design_id: "design_flux_scan_a",
      family: "y_matrix",
      parameter: "Y11",
      representation: "imaginary",
      trace_mode_group: "base",
      source_kind: "layout_simulation",
      stage_kind: "raw",
      provenance_summary: "Layout Simulation · Raw · batch #2",
      allowed_actions: {
        edit: true,
        delete: false,
      },
      mutation_policy_summary: "Delete blocked until dependent saved analyses are removed.",
    },
  ] as const;

  it("falls back to the first visible design or trace when selection is missing", () => {
    expect(resolveSelectedDesignId(null, designs)).toBe("design_flux_scan_a");
    expect(resolveSelectedTraceId(null, traces)).toBe("trace_flux_a_measurement");
  });

  it("preserves valid selections and clears invalid ones", () => {
    expect(resolveSelectedDesignId("design_flux_scan_b", designs)).toBe("design_flux_scan_b");
    expect(resolveSelectedTraceId("trace_flux_a_layout", traces)).toBe("trace_flux_a_layout");
    expect(resolveSelectedDesignId("missing", designs)).toBe("design_flux_scan_a");
    expect(resolveSelectedTraceId("missing", traces)).toBe("trace_flux_a_measurement");
    expect(resolveSelectedDesignId("missing", [])).toBeNull();
    expect(resolveSelectedTraceId("missing", [])).toBeNull();
  });

  it("keeps selected trace ids stable when the visible deletable set is unchanged", () => {
    const selectedTraceIds = ["trace_flux_a_measurement"];
    const emptySelectedTraceIds: readonly string[] = [];

    expect(resolveSelectableTraceIds(selectedTraceIds, traces)).toBe(selectedTraceIds);
    expect(resolveSelectableTraceIds(emptySelectedTraceIds, traces)).toBe(emptySelectedTraceIds);
  });

  it("drops missing or non-deletable selected trace ids only when needed", () => {
    expect(
      resolveSelectableTraceIds(
        ["trace_flux_a_measurement", "trace_flux_a_layout", "trace_missing"],
        traces,
      ),
    ).toEqual(["trace_flux_a_measurement"]);
    expect(resolveSelectableTraceIds(["trace_flux_a_measurement"], emptyTraceRows)).toEqual([]);
  });

  it("builds and parses raw-data browse hrefs for published research-data destinations", () => {
    const href = buildRawDataBrowseHref({
      designId: "design_published-explorer-design",
      traceId: "trace_701_y_raw",
      designQuery: "design_published-explorer-design",
    });
    const parsed = parseRawDataBrowseState(new URL(href, "http://localhost").searchParams);

    expect(href).toBe(
      "/raw-data?designId=design_published-explorer-design&traceId=trace_701_y_raw&designQuery=design_published-explorer-design",
    );
    expect(parsed).toEqual({
      designId: "design_published-explorer-design",
      traceId: "trace_701_y_raw",
      designQuery: "design_published-explorer-design",
    });
  });
});

describe("page-boundary source contracts", () => {
  it("moves dataset profile management into the dedicated dataset page while keeping dashboard summary-first", () => {
    expect(dashboardWorkspaceSource).toContain("overview-first");
    expect(dashboardWorkspaceSource).toContain('href="/dataset"');
    expect(dashboardWorkspaceSource).toContain('href="/data-ingestion"');
    expect(dashboardWorkspaceSource).not.toContain("Save Profile");
    expect(dashboardWorkspaceSource).not.toContain("saveProfile(");
    expect(datasetWorkspaceSource).toContain("saveProfile(");
    expect(datasetWorkspaceSource).toContain("Save Profile");
    expect(datasetWorkspaceSource).toContain("dedicated dataset management surface");
    expect(datasetWorkspaceSource).toContain("Create Dataset");
    expect(datasetWorkspaceSource).toContain("CreateDatasetDialog");
    expect(datasetWorkspaceSource).toContain('aria-labelledby="create-dataset-dialog-title"');
    expect(datasetWorkspaceSource).toContain("setIsCreateDialogOpen(true);");
    expect(datasetWorkspaceSource).toContain("Archive Dataset");
    expect(datasetWorkspaceSource).toContain("Delete Dataset");
    expect(datasetWorkspaceSource).toContain('title="Dataset Profile"');
    expect(datasetWorkspaceSource).toContain("cross-page navigation stays in the shell");
    expect(datasetWorkspaceSource).not.toContain('title="Dataset Lifecycle"');
    expect(datasetWorkspaceSource).not.toContain("Active Dataset Lifecycle");
    expect(datasetWorkspaceSource).not.toContain("Open Raw Data");
    expect(datasetWorkspaceSource).not.toContain("Open Data Ingestion");
    expect(datasetWorkspaceSource).toContain("activeDatasetState.activeDatasetError");
    expect(datasetWorkspaceSource).toContain("Unable to switch the active dataset.");
    expect(datasetWorkspaceSource).not.toContain("not exposed through the current frontend-visible backend contract");
    expect(rawDataUiSource).not.toContain("saveProfile(");
    expect(rawDataUiSource).not.toContain("Save Profile");
    expect(rawDataUiSource).not.toContain("Dataset Profile");
  });

  it("rebuilds data ingestion as an upload-first surface instead of exposing backend DTO fields", () => {
    expect(dataIngestionWorkspaceSource).toContain("Measurement");
    expect(dataIngestionWorkspaceSource).toContain("Layout Simulation");
    expect(dataIngestionWorkspaceSource).toContain("Upload-first intake");
    expect(dataIngestionWorkspaceSource).toContain("Choose CSV files");
    expect(dataIngestionWorkspaceSource).toContain("Validation & Preprocess");
    expect(dataIngestionWorkspaceSource).toContain("buildUploadFirstIngestionDraft(");
    expect(dataIngestionWorkspaceSource).toContain("validateUploadFirstCsv(");
    expect(dataIngestionWorkspaceSource).toContain("multiple");
    expect(dataIngestionWorkspaceSource).toContain("Promise.all(");
    expect(dataIngestionWorkspaceSource).toContain("selectedFiles");
    expect(dataIngestionWorkspaceSource).toContain("fileImportStatuses");
    expect(dataIngestionWorkspaceSource).toContain("for (const file of fileSummary.validFiles)");
    expect(dataIngestionWorkspaceSource).toContain("Trace Count");
    expect(dataIngestionWorkspaceSource).toContain("Sweep Axis");
    expect(dataIngestionWorkspaceSource).toContain("Shape");
    expect(dataIngestionWorkspaceSource).toContain("Axes");
    expect(dataIngestionWorkspaceSource).toContain("validFiles");
    expect(dataIngestionWorkspaceSource).not.toContain("Preview Payload JSON");
    expect(dataIngestionWorkspaceSource).not.toContain("Trace Mode Group");
    expect(dataIngestionWorkspaceSource).not.toContain("Axis Unit");
    expect(dataIngestionWorkspaceSource).not.toContain("preview_payload_json");
    expect(dataIngestionWorkspaceSource).not.toContain("Upload complete");
  });

  it("keeps raw-data summary-first and metadata-read-only", () => {
    expect(rawDataUiSource).toContain("Choose a design");
    expect(rawDataUiSource).toContain("Focused preview stays single-trace");
    expect(rawDataUiSource).toContain("Single Trace Preview");
    expect(rawDataUiSource).not.toContain('title="Selected Design Summary"');
    expect(rawDataUiSource).not.toContain("Active Dataset");
    expect(rawDataUiSource).not.toContain("setActiveDataset(");
  });

  it("reflows raw-data around extracted layout owners instead of one mega workspace file", () => {
    expect(rawDataWorkspaceSource).toContain("RawDataDesignScopesPanel");
    expect(rawDataWorkspaceSource).toContain("RawDataTraceSummariesPanel");
    expect(rawDataWorkspaceSource).toContain("RawDataTracePreviewPanel");
    expect(rawDataWorkspaceSource).toContain("useRawDataPreviewDrawer");
    expect(rawDataDesignScopesSource).toContain('title="Design Scopes"');
    expect(rawDataDesignScopesSource).toContain("Selected Design");
    expect(rawDataDesignScopesSource).toContain("Browse State");
    expect(rawDataDesignScopesSource).toContain(
      'xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.42fr)]',
    );
    expect(rawDataDesignScopesSource).toContain('xl:max-w-[22rem] xl:justify-self-end');
    expect(rawDataWorkspaceSource).toContain(
      '"xl:grid xl:grid-cols-[minmax(0,1fr)_28rem] xl:items-start xl:gap-5 xl:space-y-0"',
    );
    expect(rawDataWorkspaceSource.split("\n").length).toBeLessThan(400);
  });

  it("strengthens raw-data search affordance and keeps the wording consistent", () => {
    expect(rawDataControlsSource).toContain("function SearchField");
    expect(rawDataDesignScopesSource).toContain('label="Search Design"');
    expect(rawDataTraceSummariesSource).toContain("Parameter or note");
    expect(rawDataControlsSource).toContain("<Search className=");
  });

  it("keeps trace-summary filters in one dense unified block instead of fragmented mini cards", () => {
    expect(rawDataControlsSource).toContain("function TraceFilterSelect");
    expect(rawDataTraceSummariesSource).toContain(
      'space-y-4',
    );
    expect(rawDataTraceSummariesSource).toContain(
      'grid gap-4 md:grid-cols-3',
    );
    expect(rawDataTraceSummariesSource).toContain('label="Family"');
    expect(rawDataTraceSummariesSource).toContain('label="View"');
    expect(rawDataTraceSummariesSource).toContain('label="Source"');
    expect(rawDataControlsSource).toContain("AppInlineSelect");
    expect(rawDataUiSource).not.toContain("function FilterSelect");
  });

  it("shortens trace-summary table copy without hiding the browsing meaning", () => {
    expect(rawDataTraceSummariesSource).toContain(">View<");
    expect(rawDataTraceSummariesSource).toContain(">Origin<");
    expect(rawDataTraceSummariesSource).not.toContain(">Representation<");
    expect(rawDataTraceSummariesSource).not.toContain(">Provenance<");
  });

  it("adds row selection and CRUD actions without collapsing preview into batch state", () => {
    expect(rawDataTraceSummariesSource).toContain("Delete Selected");
    expect(rawDataWorkspaceSource).toContain("TraceEditDialog");
    expect(rawDataWorkspaceSource).toContain("ConfirmActionDialog");
    expect(rawDataWorkspaceSource).toContain("DeleteScopeCard");
    expect(rawDataWorkspaceSource).toContain("DeleteScopeList");
    expect(rawDataTraceSummariesSource).toContain("trace.allowed_actions.edit");
    expect(rawDataTraceSummariesSource).toContain("trace.allowed_actions.delete");
    expect(rawDataControlsSource).toContain("title={label}");
    expect(rawDataControlsSource).toContain("aria-label={label}");
    expect(rawDataHookSource).toContain("const [focusedTraceId, setFocusedTraceId] = useState<string | null>");
    expect(rawDataHookSource).toContain("const [selectedTraceIds, setSelectedTraceIds] = useState<readonly string[]>([])");
    expect(rawDataHookSource).toContain("focusTrace(traceId: string)");
    expect(rawDataHookSource).toContain("toggleTraceSelection(traceId: string)");
    expect(rawDataHookSource).toContain("requestBatchDeleteSelectedTraces()");
    expect(rawDataHookSource).toContain("openEditDialog(traceId: string)");
  });

  it("makes enabled delete affordances clearly destructive without changing gating", () => {
    expect(rawDataTraceSummariesSource).toContain("SurfaceActionButton");
    expect(surfaceKitSource).toContain("export function SurfaceActionButton");
    expect(surfaceKitSource).toContain("cursor-pointer");
    expect(surfaceKitSource).toContain("bg-rose-600 text-white");
    expect(surfaceKitSource).toContain("hover:bg-rose-700");
    expect(rawDataTraceSummariesSource).toContain("Edit unavailable");
    expect(rawDataTraceSummariesSource).toContain("Delete trace");
    expect(rawDataTraceSummariesSource).toContain("disabled={!trace.allowed_actions.edit}");
    expect(rawDataTraceSummariesSource).toContain("if (!trace.allowed_actions.edit) {");
    expect(rawDataTraceSummariesSource).toContain("trace.allowed_actions.delete ? (");
    expect(rawDataTraceSummariesSource).not.toContain('<p className="text-xs leading-5 text-muted-foreground">');
    expect(rawDataTraceSummariesSource).toContain("title={trace.mutation_policy_summary}");
  });

  it("keeps batch actions in a stable trailing action group instead of shifting with helper copy", () => {
    expect(rawDataTraceSummariesSource).toContain("md:grid-cols-[minmax(0,1fr)_auto] md:items-end");
    expect(rawDataTraceSummariesSource).toContain("md:justify-end");
  });

  it("makes pagination limits explicit for design scopes and trace summaries", () => {
    expect(rawDataDesignScopesSource).toContain("Up to {designsMeta?.limit ?? 6} design scopes per page");
    expect(rawDataTraceSummariesSource).toContain("Up to {tracesMeta?.limit ?? 12} traces per page");
    expect(rawDataHookSource).toContain("const DESIGN_SCOPE_PAGE_LIMIT = 6;");
    expect(rawDataHookSource).toContain("const TRACE_SUMMARY_PAGE_LIMIT = 12;");
    expect(rawDataHookSource).toContain("limit: DESIGN_SCOPE_PAGE_LIMIT");
    expect(rawDataHookSource).toContain("limit: TRACE_SUMMARY_PAGE_LIMIT");
  });

  it("keeps focused preview separate from selected rows and cleans up deleted focus safely", () => {
    expect(rawDataTracePreviewSource).toContain("Focused Trace");
    expect(rawDataUiSource).not.toContain("Preview Source");
    expect(rawDataUiSource).not.toContain("Preview Series");
    expect(rawDataHookSource).toContain("setFocusedTraceId((current) =>");
    expect(rawDataHookSource).toContain("setSelectedTraceIds((current) =>");
    expect(rawDataHookSource).toContain("deletedTraceIds.has(current) ? null : current");
  });

  it("rebinds the updated backend design row immediately after delete", () => {
    expect(rawDataHookSource).toContain("await designsQuery.mutate(");
    expect(rawDataHookSource).toContain("current && result.design");
    expect(rawDataHookSource).toContain("row.design_id === result.design?.design_id ? result.design : row");
    expect(rawDataDesignScopesSource).toContain("selectedDesign.trace_count");
    expect(rawDataDesignScopesSource).toContain("selectedDesign.compare_readiness");
  });

  it("shows destructive delete scope context for single and batch delete", () => {
    expect(rawDataWorkspaceSource).toContain("Trace ID");
    expect(rawDataWorkspaceSource).toContain("Context");
    expect(rawDataWorkspaceSource).toContain("Delete Scope");
    expect(rawDataWorkspaceSource).toContain("+{hiddenCount} more selected traces");
    expect(rawDataHookSource).toContain("trace: {");
    expect(rawDataHookSource).toContain("traces: selectedTraceRows.map");
  });

  it("rebuilds single trace preview as plot and table views over one payload", () => {
    expect(rawDataTracePreviewSource).toContain("TracePreviewPlot");
    expect(rawDataWorkspaceSource).toContain("previewMode");
    expect(rawDataTracePreviewSource).toContain("AppSegmentedControl");
    expect(rawDataTracePreviewSource).toContain('ariaLabel="Single trace preview view"');
    expect(rawDataTracePreviewSource).toContain('{ value: "plot", label: "Plot" }');
    expect(rawDataTracePreviewSource).toContain("Focused Trace");
    expect(rawDataTracePreviewSource).toContain("resolveTracePreviewContextTags");
    expect(rawDataTracePreviewSource).toContain("resolvePreviewHistory");
    expect(rawDataTracePreviewSource).toContain("History");
    expect(rawDataTracePreviewSource).toContain("Context");
    expect(rawDataTracePreviewSource).toContain("Process");
    expect(rawDataUiSource).not.toContain("Preview Source");
    expect(rawDataUiSource).not.toContain("Preview Series");
    expect(rawDataUiSource).not.toContain(
      "Only the selected trace triggers the detail path, so plot and table stay tied to one persisted preview payload at a time.",
    );
    expect(rawDataUiSource).not.toContain("Result Handles");
    expect(rawDataTracePreviewSource).toContain('hasSampledPreview ? "Preview" : "Point Count"');
  });

  it("keeps preview semantics tied to the saved payload instead of extra axis cards", () => {
    expect(rawDataTracePreviewSource).toContain("X Axis");
    expect(rawDataTracePreviewSource).toContain("Point Count");
    expect(rawDataTracePreviewSource).toContain("previewSemantics.tableYAxisLabel");
    expect(rawDataTracePreviewSource).toContain("previewSemantics.yAxisTitle");
    expect(rawDataTracePreviewSource).not.toContain("{axis.length} {axis.unit}");
    expect(rawDataTracePreviewSource).not.toContain(">Value<");
  });

  it("switches the desktop single-trace preview into a fixed drawer only after the trace section is reached", () => {
    expect(rawDataPreviewDrawerHookSource).toContain(
      'const traceSummariesSectionRef = useRef<HTMLElement | null>(null);',
    );
    expect(rawDataPreviewDrawerHookSource).toContain(
      'const desktopPreviewRailRef = useRef<HTMLDivElement | null>(null);',
    );
    expect(rawDataPreviewDrawerHookSource).toContain("const [isDesktopPreviewDrawerPinned, setIsDesktopPreviewDrawerPinned] = useState(false);");
    expect(rawDataPreviewDrawerHookSource).toContain("const [desktopPreviewDrawerFrame, setDesktopPreviewDrawerFrame] =");
    expect(rawDataWorkspaceSource).toContain("desktopPreviewDrawerTop,");
    expect(rawDataPreviewDrawerHookSource).toContain("resolvePreviewDrawerTopOffset()");
    expect(rawDataPreviewDrawerHookSource).toContain("const PREVIEW_DRAWER_MIN_VISIBLE_HEIGHT = 220;");
    expect(rawDataPreviewDrawerHookSource).toContain("const PREVIEW_DRAWER_EXIT_HYSTERESIS = 12;");
    expect(rawDataWorkspaceSource).toContain('ref={traceSummariesSectionRef}');
    expect(rawDataWorkspaceSource).toContain('ref={desktopPreviewRailRef}');
    expect(rawDataWorkspaceSource).toContain("shouldShowDesktopPreviewDrawer");
    expect(rawDataWorkspaceSource).toContain("transition-[opacity,transform] duration-200 ease-out");
    expect(rawDataWorkspaceSource).toContain("pointer-events-none translate-y-1 opacity-0");
    expect(rawDataWorkspaceSource).toContain("translate-y-3 opacity-0");
    expect(rawDataWorkspaceSource).toContain("inert={shouldShowDesktopPreviewDrawer}");
    expect(rawDataWorkspaceSource).toContain("inert={!shouldShowDesktopPreviewDrawer}");
    expect(rawDataWorkspaceSource).toContain("left: `${desktopPreviewDrawerFrame.left}px`");
    expect(rawDataWorkspaceSource).toContain("top: `${desktopPreviewDrawerTop}px`");
    expect(rawDataWorkspaceSource).toContain("width: `${desktopPreviewDrawerFrame.width}px`");
    expect(rawDataWorkspaceSource).toContain(
      'pointer-events-none fixed z-30 hidden transition-[opacity,transform] duration-200 ease-out xl:block',
    );
    expect(rawDataWorkspaceSource).toContain(
      'className="pointer-events-auto rounded-[1.1rem] shadow-[0_18px_42px_rgba(15,23,42,0.14)]"',
    );
    expect(rawDataWorkspaceSource).toContain(
      'className="max-h-[calc(100vh-var(--shell-header-height)-2rem)] overflow-y-auto rounded-[1.1rem]"',
    );
    expect(rawDataWorkspaceSource).toContain('className="xl:hidden"');
    expect(rawDataHookSource).toContain("function clearFocusedTrace()");
    expect(rawDataHookSource).toContain("clearFocusedTrace,");
  });

  it("keeps dashboard and raw-data hooks bound to the shared active dataset", () => {
    expect(dashboardDataHookSource).toContain("const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null");
    expect(dashboardDataHookSource).toContain("activeDatasetId ? datasetProfileKey(activeDatasetId) : null");
    expect(dashboardDataHookSource).toContain("activeDatasetId ? datasetMetricsKey(activeDatasetId) : null");
    expect(rawDataHookSource).toContain("const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null");
    expect(rawDataHookSource).toContain("parseRawDataBrowseState(searchParams)");
    expect(rawDataHookSource).toContain("setSelectedDesignId(browseState.designId);");
    expect(rawDataHookSource).toContain("setFocusedTraceId(browseState.traceId);");
    expect(rawDataHookSource).toContain("setDesignSearch(browseState.designQuery ?? \"\");");
    expect(rawDataHookSource).toContain("const traces = tracesQuery.data?.rows ?? emptyTraceRows");
    expect(rawDataHookSource).toContain("resolveSelectableTraceIds(current, traces)");
    expect(rawDataHookSource).toContain("getTraceDetail(activeDatasetId, resolvedDesignId, resolvedFocusedTraceId)");
    expect(rawDataHookSource).toContain("getTraceEditDetail(activeDatasetId, resolvedDesignId, editTraceId)");
    expect(rawDataHookSource).toContain("updateTrace(activeDatasetId, resolvedDesignId, editTraceId, draft)");
    expect(rawDataHookSource).toContain("deleteTrace(");
    expect(rawDataHookSource).toContain("batchDeleteTraces(");
  });
});

describe("upload-first ingestion helpers", () => {
  it("validates a frequency-column CSV and derives a backend ingestion draft", () => {
    const validation = validateUploadFirstCsv({
      kind: "measurement",
      fileName: "flux_scan_a.csv",
      fileText: `frequency_ghz,Y11_imaginary,S21_magnitude
4.000,0.11,0.91
4.001,0.12,0.92
4.002,0.13,0.93`,
    });

    expect(validation.designNameSuggestion).toBe("Flux Scan A");
    expect(validation.provenanceLabelSuggestion).toBe("Measurement import · Flux Scan A");
    expect(validation.axisName).toBe("frequency");
    expect(validation.axisUnit).toBe("GHz");
    expect(validation.pointCount).toBe(3);
    expect(validation.traces).toMatchObject([
      {
        family: "y_matrix",
        parameter: "Y11",
        representation: "imaginary",
        pointCount: 3,
      },
      {
        family: "s_matrix",
        parameter: "S21",
        representation: "magnitude",
        pointCount: 3,
      },
    ]);

    expect(
      buildUploadFirstIngestionDraft({
        kind: "measurement",
        designName: "Flux Scan A",
        provenanceLabel: "Measurement import · Flux Scan A",
        validation,
      }),
    ).toMatchObject({
      kind: "measurement",
      design_name: "Flux Scan A",
      provenance_label: "Measurement import · Flux Scan A",
      traces: [
        {
          family: "y_matrix",
          parameter: "Y11",
          representation: "imaginary",
          axes: [{ name: "frequency", unit: "GHz", length: 3 }],
        },
        {
          family: "s_matrix",
          parameter: "S21",
          representation: "magnitude",
          axes: [{ name: "frequency", unit: "GHz", length: 3 }],
        },
      ],
    });
  });

  it("keeps scalar CSV columns with units as 1D uploads", () => {
    const validation = validateUploadFirstCsv({
      kind: "layout_simulation",
      fileName: "hfss_Y11.csv",
      fileText: `Freq [GHz],Y11 [S]
4.000,0.11
4.001,0.12`,
    });

    expect(validation.axisName).toBe("frequency");
    expect(validation.axisUnit).toBe("GHz");
    expect(validation.traces).toMatchObject([
      {
        family: "y_matrix",
        parameter: "Y11",
        representation: "magnitude",
        pointCount: 2,
        previewPointCount: 2,
      },
    ]);
    expect(validation.draftTraces[0]?.axes).toEqual([
      { name: "frequency", unit: "GHz", length: 2 },
    ]);
    expect(validation.draftTraces[0]?.preview_payload).toEqual({
      kind: "sampled_series",
      points: [
        [4, 0.11],
        [4.001, 0.12],
      ],
    });
  });

  it("validates a 3-column HFSS sweep and emits an nd_grid payload", () => {
    const validation = validateUploadFirstCsv({
      kind: "layout_simulation",
      fileName: "PF6FQ_Q0_XY_Im_Y11.csv",
      fileText: `"L_jun [nH]","Freq [GHz]","im(Yt(Rectangle5_T1,Rectangle5_T1)) []"
5.0,4.0,-100.0
5.0,4.1,-105.0
10.0,4.0,-90.0
10.0,4.1,-95.0`,
    });

    expect(validation.axisName).toBe("frequency");
    expect(validation.axisUnit).toBe("GHz");
    expect(validation.designNameSuggestion).toBe("PF6FQ Q0");
    expect(validation.traces[0]).toMatchObject({
      family: "y_matrix",
      parameter: "Y11",
      representation: "imaginary",
      pointCount: 4,
      previewPointCount: 4,
    });

    const draft = validation.draftTraces[0];
    expect(draft?.axes).toEqual([
      { name: "frequency", unit: "GHz", length: 2 },
      { name: "L_jun", unit: "nH", length: 2 },
    ]);
    expect(draft?.provenance_summary).toContain("PF6FQ_Q0_XY_Im_Y11.csv");
    expect(draft?.provenance_summary).toContain("im(Yt(Rectangle5_T1,Rectangle5_T1)) []");
    expect(draft?.provenance_summary).toContain("Y11 imaginary");
    expect(draft?.preview_payload).toEqual({
      kind: "nd_grid",
      axes: [
        { name: "frequency", unit: "GHz", values: [4, 4.1] },
        { name: "L_jun", unit: "nH", values: [5, 10] },
      ],
      values: [
        [-100, -90],
        [-105, -95],
      ],
    });
  });

  it("infers HFSS formula metadata with filename parameter fallback", () => {
    const cases = [
      {
        fileName: "hfss_Im_Y11.csv",
        header: "im(Yt(Rectangle5_T1,Rectangle5_T1)) []",
        family: "y_matrix",
        parameter: "Y11",
        representation: "imaginary",
      },
      {
        fileName: "hfss_Re_Y21.csv",
        header: "re(Yt(Rectangle5_T2,Rectangle5_T1)) []",
        family: "y_matrix",
        parameter: "Y21",
        representation: "real",
      },
      {
        fileName: "hfss_Im_S21.csv",
        header: "im(St(Rectangle5_T2,Rectangle5_T1)) []",
        family: "s_matrix",
        parameter: "S21",
        representation: "imaginary",
      },
      {
        fileName: "hfss_Re_S21.csv",
        header: "re(St(Rectangle5_T2,Rectangle5_T1)) []",
        family: "s_matrix",
        parameter: "S21",
        representation: "real",
      },
      {
        fileName: "hfss_Phase_S21.csv",
        header: "ang_rad(St(Rectangle5_T2,Rectangle5_T1)) []",
        family: "s_matrix",
        parameter: "S21",
        representation: "phase",
      },
    ] as const;

    for (const testCase of cases) {
      const validation = validateUploadFirstCsv({
        kind: "layout_simulation",
        fileName: testCase.fileName,
        fileText: `Freq [GHz],"${testCase.header}"
4.0,0.01
4.1,0.012`,
      });

      expect(validation.traces[0]).toMatchObject({
        family: testCase.family,
        parameter: testCase.parameter,
        representation: testCase.representation,
      });
    }
  });

  it("infers Yin family and representation from formula and filename", () => {
    const validation = validateUploadFirstCsv({
      kind: "layout_simulation",
      fileName: "PF6FQ_Q0_XY_Re_Yin.csv",
      fileText: `"Freq [GHz]","0.02 * (1 - mag(St(Rectangle5_T1,Rectangle5_T1))**2) / (1 + mag(St(Rectangle5_T1,Rectangle5_T1))**2) []"
4.0,0.01
4.1,0.012`,
    });

    expect(validation.traces[0]).toMatchObject({
      family: "y_matrix",
      parameter: "Yin",
      representation: "real",
    });
    expect(validation.draftTraces[0]?.provenance_summary).toContain(
      "PF6FQ_Q0_XY_Re_Yin.csv",
    );
    expect(validation.draftTraces[0]?.provenance_summary).toContain("Yin real");
  });

  it.skipIf(
    !runHfssRealDataE2e || missingPf6fqRealFiles.length > 0,
  )("validates real PF6FQ HFSS files from the read-only raw-data tree", () => {
    for (const [path, expectedHeader] of [
      [pf6fqRealFiles.xyImY11, "PF6FQ_Q0_XY_Im_Y11.csv"],
      [pf6fqRealFiles.readoutImY11, "PF6FQ_Q0_Readout_Im_Y11.csv"],
    ] as const) {
      const validation = validateUploadFirstCsv({
        kind: "layout_simulation",
        fileName: expectedHeader,
        fileText: readFileSync(path, "utf8"),
      });
      const draft = validation.draftTraces[0];

      expect(validation.designNameSuggestion).toBe("PF6FQ Q0");
      expect(validation.traces[0]).toMatchObject({
        family: "y_matrix",
        parameter: "Y11",
        representation: "imaginary",
        pointCount: 250000,
        previewPointCount: 250000,
      });
      expect(draft?.axes).toEqual([
        { name: "frequency", unit: "GHz", length: 25000 },
        { name: "L_jun", unit: "nH", length: 10 },
      ]);
      expect(draft?.preview_payload.kind).toBe("nd_grid");
      expect(draft?.preview_payload.axes).toEqual([
        {
          name: "frequency",
          unit: "GHz",
          values: expect.arrayContaining([0, 20]),
        },
        {
          name: "L_jun",
          unit: "nH",
          values: [0, 5, 10, 15, 18, 20, 22, 24, 26, 28],
        },
      ]);
      const values = draft?.preview_payload.values as unknown[][] | undefined;
      expect(values).toHaveLength(25000);
      expect(values?.[0]).toHaveLength(10);
    }

    const yinValidation = validateUploadFirstCsv({
      kind: "layout_simulation",
      fileName: "PF6FQ_Q0_XY_Re_Yin.csv",
      fileText: readFileSync(pf6fqRealFiles.xyReYin, "utf8"),
    });

    expect(yinValidation.designNameSuggestion).toBe("PF6FQ Q0");
    expect(yinValidation.traces[0]).toMatchObject({
      family: "y_matrix",
      parameter: "Yin",
      representation: "real",
      pointCount: 8,
      previewPointCount: 8,
    });
    expect(yinValidation.draftTraces[0]?.preview_payload.kind).toBe("sampled_series");
  });

  it("rejects unsupported complex series columns", () => {
    expect(() =>
      validateUploadFirstCsv({
        kind: "layout_simulation",
        fileName: "layout_probe.csv",
        fileText: `frequency_ghz,Y11_complex
4.000,0.11
4.001,0.12`,
      }),
    ).toThrow("scalar series columns only");
  });
});

describe("trace edit grid helpers", () => {
  it("normalizes tabular payloads and serializes edited cells back into the backend payload shape", () => {
    const model = resolveEditableNumericGridModel({
      columns: ["frequency_ghz", "y11_imag"],
      rows: [
        [4, 0.11],
        [4.001, 0.12],
      ],
      unit: "GHz",
    });

    expect(model).not.toBeNull();
    expect(model?.columns).toEqual(["frequency_ghz", "y11_imag"]);
    expect(model?.rows).toEqual([
      ["4", "0.11"],
      ["4.001", "0.12"],
    ]);

    expect(
      serializeEditableNumericGridModel(model!, [
        ["4.005", "0.21"],
        ["4.010", "0.24"],
      ]),
    ).toEqual({
      columns: ["frequency_ghz", "y11_imag"],
      rows: [
        [4.005, 0.21],
        [4.01, 0.24],
      ],
      unit: "GHz",
    });
  });
});

describe("legacy data-browser route", () => {
  it("redirects to /raw-data", async () => {
    const redirect = vi.fn();
    vi.doMock("next/navigation", () => ({ redirect }));

    const module = await import("../src/app/(workspace)/data-browser/page");
    module.default();

    expect(redirect).toHaveBeenCalledWith("/raw-data");
    vi.doUnmock("next/navigation");
  });
});

describe("trace preview semantics helpers", () => {
  it("separates axis unit metadata from point count and derives explicit plot labels", () => {
    expect(
      resolveTracePreviewSemantics({
        axes: [
          {
            name: "frequency",
            unit: "GHz",
            length: 51,
          },
        ],
        previewPayload: {
          y_axis: {
            label: "Imaginary",
            unit: "S",
          },
          context: {
            family_label: "Y Matrix",
            metric_label: "Imaginary",
            metric_unit: "S",
          },
        },
        traceSummary: {
          trace_id: "trace_flux_a_measurement",
          dataset_id: "fluxonium-2025-031",
          design_id: "design_flux_scan_a",
          family: "y_matrix",
          parameter: "Y11",
          representation: "imaginary",
          trace_mode_group: "base",
          source_kind: "measurement",
          stage_kind: "postprocess",
          provenance_summary: "Measurement · Post-Processed · batch #4",
          allowed_actions: {
            edit: true,
            delete: true,
          },
          mutation_policy_summary: "Editable trace with dataset-local delete authority.",
        },
      }),
    ).toEqual({
      xAxisName: "Frequency",
      xAxisUnit: "GHz",
      xAxisUnitLabel: "GHz",
      xAxisTitle: "Frequency (GHz)",
      xAxisPointCount: 51,
      xAxisPointCountLabel: "51 points",
      previewSeriesLabel: "Imaginary",
      previewSeriesDetail: "Y Matrix",
      previewSeriesUnitLabel: "S",
      yAxisTitle: "Imaginary (S)",
      tableXAxisLabel: "Frequency (GHz)",
      tableYAxisLabel: "Imaginary (S)",
    });
  });

  it("keeps unit text honest when preview metadata does not provide one", () => {
    expect(
      resolveTracePreviewSemantics({
        axes: [
          {
            name: "flux_bias",
            unit: "",
            length: 4001,
          },
        ],
        previewPayload: null,
        traceSummary: null,
        fallbackSeriesLabel: "trace_flux_a_measurement",
      }),
    ).toMatchObject({
      xAxisName: "Flux Bias",
      xAxisUnit: null,
      xAxisUnitLabel: "Unit unavailable",
      xAxisTitle: "Flux Bias",
      xAxisPointCountLabel: "4001 points",
      previewSeriesLabel: "Trace Flux A Measurement",
      previewSeriesUnitLabel: "Unit unavailable",
    });
  });

  it("derives history context tags from saved preview payload metadata", () => {
    expect(
      resolveTracePreviewContextTags({
        previewPayload: {
          context: {
            origin_label: "Circuit sim",
            source_label: "PTC",
            metric_label: "Imaginary",
            metric_unit: "S",
            port_label: "Port 1 -> Port 1",
          },
        },
        traceSummary: null,
      }),
    ).toEqual([
      { label: "Origin", value: "Circuit sim" },
      { label: "Source", value: "PTC" },
      { label: "Metric", value: "Imaginary (S)" },
      { label: "Ports", value: "Port 1 -> Port 1" },
    ]);
  });
});
