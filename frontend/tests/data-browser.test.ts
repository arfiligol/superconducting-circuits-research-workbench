import { readFileSync } from "node:fs";
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
import { resolveSelectedDesignId, resolveSelectedTraceId } from "../src/features/data-browser/lib/selection";
import {
  resolveEditableNumericGridModel,
  serializeEditableNumericGridModel,
} from "../src/features/data-browser/lib/trace-edit-grid";
import {
  buildUploadFirstIngestionDraft,
  validateUploadFirstCsv,
} from "../src/features/data-browser/lib/upload-first-ingestion";

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
    expect(datasetWorkspaceSource).toContain("Archive Dataset");
    expect(datasetWorkspaceSource).toContain("Delete Dataset");
    expect(datasetWorkspaceSource).toContain("cross-page navigation stays in the shell");
    expect(datasetWorkspaceSource).not.toContain("Open Raw Data");
    expect(datasetWorkspaceSource).not.toContain("Open Data Ingestion");
    expect(datasetWorkspaceSource).toContain("activeDatasetState.activeDatasetError");
    expect(datasetWorkspaceSource).toContain("Unable to switch the active dataset.");
    expect(datasetWorkspaceSource).not.toContain("not exposed through the current frontend-visible backend contract");
    expect(rawDataWorkspaceSource).not.toContain("saveProfile(");
    expect(rawDataWorkspaceSource).not.toContain("Save Profile");
    expect(rawDataWorkspaceSource).not.toContain("Dataset Profile");
  });

  it("rebuilds data ingestion as an upload-first surface instead of exposing backend DTO fields", () => {
    expect(dataIngestionWorkspaceSource).toContain("Measurement");
    expect(dataIngestionWorkspaceSource).toContain("Layout Simulation");
    expect(dataIngestionWorkspaceSource).toContain("Upload-first intake");
    expect(dataIngestionWorkspaceSource).toContain("Choose CSV file");
    expect(dataIngestionWorkspaceSource).toContain("Validation & Preprocess");
    expect(dataIngestionWorkspaceSource).toContain("buildUploadFirstIngestionDraft(");
    expect(dataIngestionWorkspaceSource).toContain("validateUploadFirstCsv(");
    expect(dataIngestionWorkspaceSource).toContain("Import {selectedScopeSummary.title} CSV");
    expect(dataIngestionWorkspaceSource).not.toContain("Preview Payload JSON");
    expect(dataIngestionWorkspaceSource).not.toContain("Trace Mode Group");
    expect(dataIngestionWorkspaceSource).not.toContain("Axis Unit");
    expect(dataIngestionWorkspaceSource).not.toContain("preview_payload_json");
    expect(dataIngestionWorkspaceSource).not.toContain("Upload complete");
  });

  it("keeps raw-data summary-first and metadata-read-only", () => {
    expect(rawDataWorkspaceSource).toContain("Choose a design");
    expect(rawDataWorkspaceSource).toContain("Focused preview stays single-trace");
    expect(rawDataWorkspaceSource).toContain("Single Trace Preview");
    expect(rawDataWorkspaceSource).not.toContain('title="Selected Design Summary"');
    expect(rawDataWorkspaceSource).not.toContain("Active Dataset");
    expect(rawDataWorkspaceSource).not.toContain("setActiveDataset(");
  });

  it("reflows raw-data around a top design owner and lower master-detail preview", () => {
    expect(rawDataWorkspaceSource).toContain('title="Design Scopes"');
    expect(rawDataWorkspaceSource).toContain("Selected Design");
    expect(rawDataWorkspaceSource).toContain("Browse State");
    expect(rawDataWorkspaceSource).toContain(
      'grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.82fr)] xl:items-start',
    );
    expect(rawDataWorkspaceSource).toContain('className="xl:sticky xl:top-5"');
  });

  it("strengthens raw-data search affordance and keeps the wording consistent", () => {
    expect(rawDataWorkspaceSource).toContain("function SearchField");
    expect(rawDataWorkspaceSource).toContain('label="Search Design"');
    expect(rawDataWorkspaceSource).toContain("Parameter or note");
    expect(rawDataWorkspaceSource).toContain("<Search className=");
  });

  it("keeps trace-summary filters in one dense unified block instead of fragmented mini cards", () => {
    expect(rawDataWorkspaceSource).toContain("function TraceFilterSelect");
    expect(rawDataWorkspaceSource).toContain(
      'grid gap-4 md:grid-cols-2 2xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.9fr)_minmax(0,0.95fr)_minmax(0,0.95fr)]',
    );
    expect(rawDataWorkspaceSource).toContain('label="Family"');
    expect(rawDataWorkspaceSource).toContain('label="View"');
    expect(rawDataWorkspaceSource).toContain('label="Source"');
    expect(rawDataWorkspaceSource).toContain("AppInlineSelect");
    expect(rawDataWorkspaceSource).not.toContain("function FilterSelect");
  });

  it("shortens trace-summary table copy without hiding the browsing meaning", () => {
    expect(rawDataWorkspaceSource).toContain(">View<");
    expect(rawDataWorkspaceSource).toContain(">Origin<");
    expect(rawDataWorkspaceSource).not.toContain(">History<");
    expect(rawDataWorkspaceSource).not.toContain(">Representation<");
    expect(rawDataWorkspaceSource).not.toContain(">Provenance<");
  });

  it("adds row selection and CRUD actions without collapsing preview into batch state", () => {
    expect(rawDataWorkspaceSource).toContain("Delete Selected");
    expect(rawDataWorkspaceSource).toContain("TraceEditDialog");
    expect(rawDataWorkspaceSource).toContain("ConfirmActionDialog");
    expect(rawDataWorkspaceSource).toContain("DeleteScopeCard");
    expect(rawDataWorkspaceSource).toContain("DeleteScopeList");
    expect(rawDataWorkspaceSource).toContain("trace.allowed_actions.edit");
    expect(rawDataWorkspaceSource).toContain("trace.allowed_actions.delete");
    expect(rawDataWorkspaceSource).toContain("title={label}");
    expect(rawDataWorkspaceSource).toContain("aria-label={label}");
    expect(rawDataHookSource).toContain("const [focusedTraceId, setFocusedTraceId] = useState<string | null>");
    expect(rawDataHookSource).toContain("const [selectedTraceIds, setSelectedTraceIds] = useState<readonly string[]>([])");
    expect(rawDataHookSource).toContain("focusTrace(traceId: string)");
    expect(rawDataHookSource).toContain("toggleTraceSelection(traceId: string)");
    expect(rawDataHookSource).toContain("requestBatchDeleteSelectedTraces()");
    expect(rawDataHookSource).toContain("openEditDialog(traceId: string)");
  });

  it("makes enabled delete affordances clearly destructive without changing gating", () => {
    expect(rawDataWorkspaceSource).toContain("bg-rose-600 text-white");
    expect(rawDataWorkspaceSource).toContain("hover:bg-rose-700");
    expect(rawDataWorkspaceSource).toContain("Edit unavailable");
    expect(rawDataWorkspaceSource).toContain("Delete trace");
    expect(rawDataWorkspaceSource).toContain("disabled={!trace.allowed_actions.edit}");
    expect(rawDataWorkspaceSource).toContain("if (!trace.allowed_actions.edit) {");
    expect(rawDataWorkspaceSource).toContain("trace.allowed_actions.delete ? (");
    expect(rawDataWorkspaceSource).not.toContain('<p className="text-xs leading-5 text-muted-foreground">');
    expect(rawDataWorkspaceSource).toContain("title={trace.mutation_policy_summary}");
  });

  it("keeps focused preview separate from selected rows and cleans up deleted focus safely", () => {
    expect(rawDataWorkspaceSource).toContain("Focused Trace");
    expect(rawDataWorkspaceSource).not.toContain("Preview Source");
    expect(rawDataWorkspaceSource).not.toContain("Preview Series");
    expect(rawDataHookSource).toContain("setFocusedTraceId((current) =>");
    expect(rawDataHookSource).toContain("setSelectedTraceIds((current) =>");
    expect(rawDataHookSource).toContain("deletedTraceIds.has(current) ? null : current");
  });

  it("rebinds the updated backend design row immediately after delete", () => {
    expect(rawDataHookSource).toContain("await designsQuery.mutate(");
    expect(rawDataHookSource).toContain("current && result.design");
    expect(rawDataHookSource).toContain("row.design_id === result.design?.design_id ? result.design : row");
    expect(rawDataWorkspaceSource).toContain("selectedDesign.trace_count");
    expect(rawDataWorkspaceSource).toContain("selectedDesign.compare_readiness");
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
    expect(rawDataWorkspaceSource).toContain("TracePreviewPlot");
    expect(rawDataWorkspaceSource).toContain("previewMode");
    expect(rawDataWorkspaceSource).toContain("AppSegmentedControl");
    expect(rawDataWorkspaceSource).toContain('ariaLabel="Single trace preview view"');
    expect(rawDataWorkspaceSource).toContain('{ value: "plot", label: "Plot" }');
    expect(rawDataWorkspaceSource).toContain("Focused Trace");
    expect(rawDataWorkspaceSource).toContain("resolveTracePreviewContextTags");
    expect(rawDataWorkspaceSource).toContain("resolvePreviewHistory");
    expect(rawDataWorkspaceSource).toContain("History");
    expect(rawDataWorkspaceSource).not.toContain("Preview Source");
    expect(rawDataWorkspaceSource).not.toContain("Preview Series");
    expect(rawDataWorkspaceSource).not.toContain(
      "Only the selected trace triggers the detail path, so plot and table stay tied to one persisted preview payload at a time.",
    );
    expect(rawDataWorkspaceSource).not.toContain("Result Handles");
    expect(rawDataWorkspaceSource).toContain('hasSampledPreview ? "Preview" : "Point Count"');
  });

  it("keeps preview semantics tied to the saved payload instead of extra axis cards", () => {
    expect(rawDataWorkspaceSource).toContain("X Axis");
    expect(rawDataWorkspaceSource).toContain("Point Count");
    expect(rawDataWorkspaceSource).toContain("previewSemantics.tableYAxisLabel");
    expect(rawDataWorkspaceSource).toContain("previewSemantics.yAxisTitle");
    expect(rawDataWorkspaceSource).not.toContain("{axis.length} {axis.unit}");
    expect(rawDataWorkspaceSource).not.toContain(">Value<");
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
