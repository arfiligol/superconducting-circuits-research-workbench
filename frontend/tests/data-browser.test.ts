import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

import {
  datasetCatalogKey,
  datasetDesignsKey,
  datasetMetricsKey,
  datasetProfileKey,
  traceDetailKey,
  traceListKey,
} from "../src/features/data-browser/lib/api";
import { resolveTracePreviewSemantics } from "../src/features/data-browser/lib/trace-preview";
import { resolveSelectedDesignId, resolveSelectedTraceId } from "../src/features/data-browser/lib/selection";

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
  });

  it("encodes ids when building nested dataset and trace paths", () => {
    expect(datasetProfileKey("folder/a b")).toBe("/api/backend/datasets/folder%2Fa%20b/profile");
    expect(traceDetailKey("dataset/a", "design b", "trace/c")).toBe(
      "/api/backend/datasets/dataset%2Fa/designs/design%20b/traces/trace%2Fc",
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
});

describe("page-boundary source contracts", () => {
  it("keeps dashboard as the only metadata write surface", () => {
    expect(dashboardWorkspaceSource).toContain("saveProfile(");
    expect(dashboardWorkspaceSource).toContain("Save Profile");
    expect(dashboardWorkspaceSource).toContain("only metadata write surface");
    expect(rawDataWorkspaceSource).not.toContain("saveProfile(");
    expect(rawDataWorkspaceSource).not.toContain("Save Profile");
    expect(rawDataWorkspaceSource).not.toContain("Dataset Profile");
  });

  it("keeps raw-data summary-first and metadata-read-only", () => {
    expect(rawDataWorkspaceSource).toContain("summary-first");
    expect(rawDataWorkspaceSource).toContain("metadata-only until one row is selected for preview");
    expect(rawDataWorkspaceSource).toContain("Single Trace Preview");
    expect(rawDataWorkspaceSource).not.toContain("setActiveDataset(");
  });

  it("strengthens raw-data search affordance and keeps the wording consistent", () => {
    expect(rawDataWorkspaceSource).toContain("function SearchField");
    expect(rawDataWorkspaceSource).toContain('label="Search Design"');
    expect(rawDataWorkspaceSource).toContain('label="Search Trace Summaries"');
    expect(rawDataWorkspaceSource).toContain("<Search className=");
  });

  it("rebuilds single trace preview as plot and table views over one payload", () => {
    expect(rawDataWorkspaceSource).toContain("TracePreviewPlot");
    expect(rawDataWorkspaceSource).toContain("previewMode");
    expect(rawDataWorkspaceSource).toContain('aria-label="Single trace preview view"');
    expect(rawDataWorkspaceSource).toContain('mode === "plot" ? "Plot" : "Table"');
    expect(rawDataWorkspaceSource).toContain("same preview payload");
    expect(rawDataWorkspaceSource).not.toContain("Result Handles");
  });

  it("makes axis semantics explicit instead of mixing point count with units", () => {
    expect(rawDataWorkspaceSource).toContain("X Axis");
    expect(rawDataWorkspaceSource).toContain("Preview Series");
    expect(rawDataWorkspaceSource).toContain("Point Count");
    expect(rawDataWorkspaceSource).toContain("previewSemantics.xAxisPointCountLabel");
    expect(rawDataWorkspaceSource).toContain("previewSemantics.tableYAxisLabel");
    expect(rawDataWorkspaceSource).not.toContain("{axis.length} {axis.unit}");
    expect(rawDataWorkspaceSource).not.toContain(">Value<");
  });

  it("keeps dashboard and raw-data hooks bound to the shared active dataset", () => {
    expect(dashboardDataHookSource).toContain("const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null");
    expect(dashboardDataHookSource).toContain("activeDatasetId ? datasetProfileKey(activeDatasetId) : null");
    expect(dashboardDataHookSource).toContain("activeDatasetId ? datasetMetricsKey(activeDatasetId) : null");
    expect(rawDataHookSource).toContain("const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null");
    expect(rawDataHookSource).toContain("setSelectedDesignId(null);");
    expect(rawDataHookSource).toContain("setSelectedTraceId(null);");
    expect(rawDataHookSource).toContain("}, [activeDatasetId]);");
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
        },
      }),
    ).toEqual({
      xAxisName: "Frequency",
      xAxisUnit: "GHz",
      xAxisUnitLabel: "GHz",
      xAxisTitle: "Frequency (GHz)",
      xAxisPointCount: 51,
      xAxisPointCountLabel: "51 points",
      previewSeriesLabel: "Y11 · Imaginary",
      previewSeriesDetail: "Y Matrix",
      previewSeriesUnitLabel: "Unit unavailable",
      yAxisTitle: "Y11 · Imaginary",
      tableXAxisLabel: "Frequency (GHz)",
      tableYAxisLabel: "Y11 · Imaginary",
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
});
