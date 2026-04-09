import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  characterizationAnalysisRegistryKey,
  characterizationArtifactPayloadKey,
  characterizationResultDetailKey,
  characterizationResultsListKey,
  formatCharacterizationTraceAxesSummary,
  characterizationRunHistoryKey,
  characterizationTaggingsKey,
} from "../src/features/characterization/lib/api";
import {
  buildCharacterizationArtifactPayloadRequest,
  resolveCharacterizationArtifactCompareGroups,
  resolveCharacterizationArtifactCompatibilityPayload,
  resolveCharacterizationEmbeddedFallbackTable,
  resolveCharacterizationArtifactPresetId,
  resolveCharacterizationArtifactPlotSeries,
  resolveCharacterizationArtifactSelection,
  resolveCharacterizationArtifactTableColumns,
  resolveCharacterizationArtifactTableRows,
  resolveCharacterizationArtifactViewMode,
} from "../src/features/characterization/lib/result-explorer";
import {
  buildCharacterizationCollectionOptions,
  buildCharacterizationSweepAxisOptions,
  filterCharacterizationTraceRows,
} from "../src/features/characterization/lib/trace-selection";
import {
  filterCharacterizationTasks,
  resolveLatestCharacterizationTask,
  resolveCharacterizationSelectionRecovery,
  resolveSelectedCharacterizationDesignId,
  resolveSelectedCharacterizationResultId,
  summarizeCharacterizationResults,
  summarizeCharacterizationTasks,
} from "../src/features/characterization/lib/workflow";

const characterizationWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/characterization/components/characterization-workspace.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);
const characterizationHookSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/characterization/hooks/use-characterization-workflow-data.ts",
      import.meta.url,
    ),
  ),
  "utf8",
);
const characterizationExplorerHookSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/characterization/hooks/use-characterization-result-explorer.ts",
      import.meta.url,
    ),
  ),
  "utf8",
);
const characterizationExplorerSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/characterization/components/characterization-result-explorer.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);
const characterizationApiSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/characterization/lib/api.ts", import.meta.url),
  ),
  "utf8",
);
const taskApiSource = readFileSync(
  fileURLToPath(new URL("../src/lib/api/tasks.ts", import.meta.url)),
  "utf8",
);
const RELATED_SIMULATION_SCHEMA_ID = "51cfd0e2-1a2f-4c1e-86d9-33f6b2d91003";

describe("characterization api keys", () => {
  it("builds stable dataset, result detail, and nested tagging paths", () => {
    expect(
      characterizationResultsListKey("fluxonium-2025-031", "design_flux_scan_a"),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results",
    );
    expect(
      characterizationResultDetailKey(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "char-fit-flux-a-01",
      ),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results/char-fit-flux-a-01",
    );
    expect(
      characterizationTaggingsKey(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "char-fit-flux-a-01",
      ),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results/char-fit-flux-a-01/taggings",
    );
    expect(
      characterizationArtifactPayloadKey(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        "char-fit-flux-a-01",
        "artifact_resonance_frequency_matrix",
        {
          viewMode: "plot",
          presetId: "plot_mode_vs_frequency_by_ljun",
        },
      ),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results/char-fit-flux-a-01/artifacts/artifact_resonance_frequency_matrix?view_mode=plot&preset_id=plot_mode_vs_frequency_by_ljun",
    );
  });

  it("builds registry and run history paths with nested dataset/design context", () => {
    expect(
      characterizationAnalysisRegistryKey(
        "fluxonium-2025-031",
        "design_flux_scan_a",
        ["trace_flux_a_measurement", "trace_flux_a_layout"],
      ),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-analysis-registry?selected_trace_ids=trace_flux_a_measurement&selected_trace_ids=trace_flux_a_layout",
    );
    expect(
      characterizationRunHistoryKey("fluxonium-2025-031", "design_flux_scan_a", {
        analysisId: "admittance_extraction",
        cursor: "cursor:2",
      }),
    ).toBe(
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-run-history?analysis_id=admittance_extraction&cursor=cursor%3A2",
    );
  });

  it("encodes dataset, design, and result ids for nested routes", () => {
    expect(
      characterizationResultDetailKey("dataset/a", "design b", "result/c"),
    ).toBe(
      "/api/backend/datasets/dataset%2Fa/designs/design%20b/characterization-results/result%2Fc",
    );
  });
});

describe("characterization browse helpers", () => {
  const designs = [
    {
      design_id: "design_flux_scan_a",
      dataset_id: "fluxonium-2025-031",
      name: "Flux Scan A",
      source_coverage: { measurement: 2 },
      compare_readiness: "ready",
      trace_count: 3,
      updated_at: "2026-03-15T08:20:00Z",
    },
    {
      design_id: "design_flux_scan_b",
      dataset_id: "fluxonium-2025-031",
      name: "Flux Scan B",
      source_coverage: { layout_simulation: 1 },
      compare_readiness: "inspect_only",
      trace_count: 1,
      updated_at: "2026-03-15T07:55:00Z",
    },
  ] as const;

  const results = [
    {
      resultId: "char-fit-flux-a-01",
      datasetId: "fluxonium-2025-031",
      designId: "design_flux_scan_a",
      analysisId: "admittance_extraction",
      title: "Admittance Fit",
      status: "completed",
      freshnessSummary: "Fresh",
      provenanceSummary: "Measurement · Postprocess batch #4",
      traceCount: 2,
      artifactCount: 3,
      updatedAt: "2026-03-15T08:22:00Z",
    },
    {
      resultId: "char-sideband-flux-a-02",
      datasetId: "fluxonium-2025-031",
      designId: "design_flux_scan_a",
      analysisId: "sideband_identification",
      title: "Sideband Identification",
      status: "failed",
      freshnessSummary: "Input scope needs review",
      provenanceSummary: "Measurement · Sideband batch #7",
      traceCount: 1,
      artifactCount: 1,
      updatedAt: "2026-03-15T08:25:00Z",
    },
  ] as const;

  it("resolves visible design and result selections", () => {
    expect(resolveSelectedCharacterizationDesignId(null, designs)).toBe("design_flux_scan_a");
    expect(
      resolveSelectedCharacterizationDesignId("design_flux_scan_b", designs),
    ).toBe("design_flux_scan_b");
    expect(resolveSelectedCharacterizationDesignId("missing", designs)).toBe(
      "design_flux_scan_a",
    );
    expect(resolveSelectedCharacterizationDesignId("missing", [])).toBeNull();

    expect(resolveSelectedCharacterizationResultId(null, results)).toBe("char-fit-flux-a-01");
    expect(
      resolveSelectedCharacterizationResultId("char-sideband-flux-a-02", results),
    ).toBe("char-sideband-flux-a-02");
    expect(resolveSelectedCharacterizationResultId("missing", results)).toBe(
      "char-fit-flux-a-01",
    );
    expect(resolveSelectedCharacterizationResultId("missing", [])).toBeNull();
  });

  it("summarizes persisted results and emits recovery notices for stale browse state", () => {
    expect(summarizeCharacterizationResults(results)).toEqual({
      total: 2,
      completedCount: 1,
      failedCount: 1,
      blockedCount: 0,
      artifactCount: 4,
    });

    expect(
      resolveCharacterizationSelectionRecovery({
        activeDatasetName: "Fluxonium sweep 031",
        requestedDesignId: "design_old",
        resolvedDesignId: "design_flux_scan_a",
        requestedResultId: null,
        resolvedResultId: null,
      }),
    ).toEqual({
      tone: "warning",
      title: "Design scope rebound",
      message:
        "The active dataset now exposes design_flux_scan_a instead of design_old. Browse state was rebound to stay within Fluxonium sweep 031.",
    });

    expect(
      resolveCharacterizationSelectionRecovery({
        activeDatasetName: "Fluxonium sweep 031",
        requestedDesignId: "design_flux_scan_a",
        resolvedDesignId: "design_flux_scan_a",
        requestedResultId: "missing-result",
        resolvedResultId: "char-fit-flux-a-01",
      }),
    ).toEqual({
      tone: "warning",
      title: "Result selection rebound",
      message:
        "Result missing-result is no longer available for this design. The detail surface switched to char-fit-flux-a-01.",
    });
  });
});

describe("characterization explorer helpers", () => {
  const artifactRefs = [
    {
      artifactId: "artifact_resonance_frequency_matrix",
      category: "matrix",
      viewKind: "preset_query",
      title: "Resonance Matrix",
      payloadFormat: "json",
      payloadLocator: null,
      axes: [
        { axisKey: "input_axis", label: "Input Axis", role: "input", unit: "nH", length: 3 },
        { axisKey: "member_key", label: "Collection Member", role: "member", unit: null, length: 2 },
        { axisKey: "mode_index", label: "Mode Index", role: "derived", unit: null, length: 2 },
      ],
      metric: { metricKey: "frequency_ghz", label: "Frequency", unit: "GHz" },
      presets: [
        {
          presetId: "table_mode_by_input_axis",
          label: "Matrix",
          viewKind: "table",
          rowsAxis: "mode_index",
          columnsAxis: "input_axis",
          cellMetric: "frequency_ghz",
          xAxis: null,
          yMetric: null,
          seriesAxis: null,
          compareAxis: "member_key",
        },
        {
          presetId: "plot_mode_profile",
          label: "Mode Profile",
          viewKind: "plot",
          rowsAxis: null,
          columnsAxis: null,
          cellMetric: null,
          xAxis: "mode_index",
          yMetric: "frequency_ghz",
          seriesAxis: "input_axis",
          compareAxis: "member_key",
        },
        {
          presetId: "plot_sweep_profile",
          label: "Sweep Profile",
          viewKind: "plot",
          rowsAxis: null,
          columnsAxis: null,
          cellMetric: null,
          xAxis: "input_axis",
          yMetric: "frequency_ghz",
          seriesAxis: "mode_index",
          compareAxis: "member_key",
        },
      ],
      defaultPresetId: "table_mode_by_input_axis",
      querySpec: {
        queryStyle: "preset_driven",
        supportedQueryFields: ["view_mode", "preset_id"],
        supportedViewModes: ["table", "plot"],
        supportedPresetIds: [
          "table_mode_by_input_axis",
          "plot_mode_profile",
          "plot_sweep_profile",
        ],
        defaultPresetId: "table_mode_by_input_axis",
        defaultPresetsByViewMode: [
          {
            viewMode: "table",
            presetId: "table_mode_by_input_axis",
          },
          {
            viewMode: "plot",
            presetId: "plot_mode_profile",
          },
        ],
      },
      identifySource: false,
    },
  ] as const;

  const compareAwarePayload = {
    artifactId: "artifact_resonance_frequency_matrix",
    title: "Mode frequency grid",
    presetId: "mode_by_input_table",
    viewKind: "table",
    axes: artifactRefs[0].axes,
    metric: artifactRefs[0].metric,
    diagnostics: [],
    embeddedFallbackTable: null,
    compatibilityFallback: null,
    payload: {
      layout: {
        rows_axis: "mode_index",
        columns_axis: "input_axis",
        cell_metric: "frequency_ghz",
        compare_axis: "member_key",
      },
      rows: [
        { axis_value: 0, label: "Mode 0", unit: null },
        { axis_value: 1, label: "Mode 1", unit: null },
      ],
      columns: [
        { axis_value: 850, label: "850 nH", unit: "nH" },
        { axis_value: 1000, label: "1000 nH", unit: "nH" },
      ],
      compare_groups: [
        {
          compare_key: "measurement:trace_a",
          compare_label: "Measured member",
          member: {
            member_key: "measurement:trace_a",
            label: "Measured member",
            trace_id: "trace_a",
            source_kind: "measurement",
            trace_mode_group: "base",
            parameter: "Y11",
            representation: "real",
            provenance_summary: "Measurement batch #1",
          },
          cells: [
            [5.61, 5.58],
            [5.84, null],
          ],
          mask: [
            [false, false],
            [false, true],
          ],
        },
        {
          compare_key: "layout_simulation:trace_b",
          compare_label: "Layout member",
          member: {
            member_key: "layout_simulation:trace_b",
            label: "Layout member",
            trace_id: "trace_b",
            source_kind: "layout_simulation",
            trace_mode_group: "base",
            parameter: "Y11",
            representation: "real",
            provenance_summary: "Layout batch #2",
          },
          cells: [
            [5.63, 5.6],
            [5.86, null],
          ],
          mask: [
            [false, false],
            [false, true],
          ],
        },
      ],
      series: [
        {
          series_key: "input_axis:0",
          series_label: "850 nH",
          series_value: 850,
          x_values: [0, 1],
          y_values: [5.61, 5.84],
          mask: [false, false],
          compare_key: "measurement:trace_a",
          compare_label: "Measured member",
          member: {
            member_key: "measurement:trace_a",
            label: "Measured member",
            trace_id: "trace_a",
            source_kind: "measurement",
            trace_mode_group: "base",
            parameter: "Y11",
            representation: "real",
            provenance_summary: "Measurement batch #1",
          },
        },
      ],
    },
  } as const;

  const legacyPersistedResultDetail = {
    resultId: "char-admittance-run-24",
    datasetId: "local-floatingqubit-100",
    designId: "design_floatingqubitwithxy",
    analysisId: "admittance_extraction",
    title: "FloatingQubitWithXY admittance resonance extraction",
    status: "completed",
    freshnessSummary: "Persisted admittance resonance extraction completed from saved design traces.",
    provenanceSummary: "Published from post-processing task 484 (PTC Y11)",
    traceCount: 20,
    updatedAt: "2026-03-27T16:41:26.885905Z",
    inputTraceIds: [],
    inputResultRefs: [],
    payload: {
      analysis_run_id: 24,
      fit_window: [3.0, 5.0],
      analysis_config: {
        fit_window: [3, 5],
        residual_tolerance: 0.02,
      },
      fit_table: [
        {
          parameter: "f01",
          value: 4.996044,
          unit: "GHz",
        },
        {
          parameter: "residual_rms",
          value: 0.0,
          unit: "S",
        },
      ],
    },
    diagnostics: [],
    artifactRefs: [
      {
        artifactId: "char-admittance-run-24:fit-table",
        category: "fit_table",
        viewKind: "table",
        title: "Admittance fit table",
        payloadFormat: "json",
        payloadLocator: "characterization/char-admittance-run-24/fit-table.json",
        axes: [],
        metric: null,
        presets: [],
        defaultPresetId: null,
        querySpec: null,
        identifySource: false,
      },
      {
        artifactId: "char-admittance-run-24:report",
        category: "report",
        viewKind: "json",
        title: "Characterization report",
        payloadFormat: "json",
        payloadLocator: "characterization/char-admittance-run-24/fit-report.json",
        axes: [],
        metric: null,
        presets: [],
        defaultPresetId: null,
        querySpec: null,
        identifySource: false,
      },
    ],
    identifySurface: {
      sourceParameters: [],
      designatedMetrics: [],
      appliedTags: [],
    },
    downstreamUnlockAnalysisIds: [],
  } as const;

  const traceRows = [
    {
      trace_id: "trace_a",
      dataset_id: "ds",
      design_id: "design_a",
      family: "y_matrix",
      parameter: "Y11",
      representation: "real",
      trace_mode_group: "base",
      source_kind: "measurement",
      stage_kind: "raw",
      provenance_summary: "Measurement batch #1",
      allowed_actions: { edit: false, delete: false },
      mutation_policy_summary: "",
      axesSummary: "Shared axis L_jun",
      axisSignature: "axis:l_jun",
      availableSweepAxes: ["L_jun"],
      collectionProjection: {
        collectionId: "collection_a",
        label: "Flux sweep A",
        summary: "Same sweep axis and lineage",
        traceCount: 3,
      },
    },
    {
      trace_id: "trace_b",
      dataset_id: "ds",
      design_id: "design_a",
      family: "y_matrix",
      parameter: "Y21",
      representation: "imag",
      trace_mode_group: "sideband",
      source_kind: "measurement",
      stage_kind: "raw",
      provenance_summary: "Measurement batch #2",
      allowed_actions: { edit: false, delete: false },
      mutation_policy_summary: "",
      axesSummary: "Shared axis C_q",
      axisSignature: "axis:c_q",
      availableSweepAxes: ["C_q"],
      collectionProjection: {
        collectionId: "collection_b",
        label: "Coupler sweep B",
        summary: "Same coupler sweep",
        traceCount: 2,
      },
    },
  ] as const;

  it("keeps artifact selection and preset resolution manifest-driven", () => {
    const artifact = resolveCharacterizationArtifactSelection(artifactRefs, null);
    expect(artifact?.artifactId).toBe("artifact_resonance_frequency_matrix");
    expect(artifact?.viewKind).toBe("preset_query");
    expect(resolveCharacterizationArtifactViewMode(artifact ?? null, null)).toBe("table");
    expect(resolveCharacterizationArtifactPresetId(artifact ?? null, "table", null)).toBe(
      "table_mode_by_input_axis",
    );
    expect(resolveCharacterizationArtifactPresetId(artifact ?? null, "plot", null)).toBe(
      "plot_mode_profile",
    );
    expect(
      buildCharacterizationArtifactPayloadRequest({
        artifact: artifact ?? null,
        viewMode: "plot",
        presetId: "plot_sweep_profile",
      }),
    ).toEqual({
      viewMode: "plot",
      presetId: "plot_sweep_profile",
    });
  });

  it("parses compare-aware member payloads without collapsing identity", () => {
    expect(resolveCharacterizationArtifactTableRows(compareAwarePayload)).toEqual([
      { axisValue: 0, label: "Mode 0", unit: null },
      { axisValue: 1, label: "Mode 1", unit: null },
    ]);
    expect(resolveCharacterizationArtifactTableColumns(compareAwarePayload)).toEqual([
      { axisValue: 850, label: "850 nH", unit: "nH" },
      { axisValue: 1000, label: "1000 nH", unit: "nH" },
    ]);
    expect(resolveCharacterizationArtifactCompareGroups(compareAwarePayload)).toHaveLength(2);
    expect(resolveCharacterizationArtifactCompareGroups(compareAwarePayload)[0]?.member?.traceId).toBe(
      "trace_a",
    );
    expect(resolveCharacterizationArtifactPlotSeries(compareAwarePayload)[0]?.compareKey).toBe(
      "measurement:trace_a",
    );
  });

  it("falls back to embedded persisted result payload when legacy artifact routes are unavailable", () => {
    const fallbackPayload = resolveCharacterizationArtifactCompatibilityPayload({
      resultDetail: legacyPersistedResultDetail,
      artifact: legacyPersistedResultDetail.artifactRefs[0],
    });

    expect(fallbackPayload?.viewKind).toBe("table");
    expect(fallbackPayload?.compatibilityFallback?.source).toBe("embedded_result_payload");
    expect(resolveCharacterizationEmbeddedFallbackTable(fallbackPayload ?? null)).toEqual({
      columns: [
        { key: "parameter", label: "Parameter" },
        { key: "value", label: "Value" },
        { key: "unit", label: "Unit" },
      ],
      rows: [
        { parameter: "f01", value: 4.996044, unit: "GHz" },
        { parameter: "residual_rms", value: 0, unit: "S" },
      ],
    });

    const reportFallback = resolveCharacterizationArtifactCompatibilityPayload({
      resultDetail: legacyPersistedResultDetail,
      artifact: legacyPersistedResultDetail.artifactRefs[1],
    });
    expect(reportFallback?.viewKind).toBe("json");
    expect(reportFallback?.payload.fit_window).toEqual([3.0, 5.0]);
  });

  it("builds sweep-aware and collection-aware filters without parsing provenance strings", () => {
    expect(buildCharacterizationSweepAxisOptions(traceRows)).toEqual(["C_q", "L_jun"]);
    expect(buildCharacterizationCollectionOptions(traceRows)).toEqual([
      { value: "collection_b", label: "Coupler sweep B" },
      { value: "collection_a", label: "Flux sweep A" },
    ]);
    expect(
      filterCharacterizationTraceRows(traceRows, {
        sweepAxis: "L_jun",
        collection: null,
      }).map((trace) => trace.trace_id),
    ).toEqual(["trace_a"]);
    expect(
      filterCharacterizationTraceRows(traceRows, {
        sweepAxis: null,
        collection: "collection_b",
      }).map((trace) => trace.trace_id),
    ).toEqual(["trace_b"]);
  });

  it("formats structured trace axes summaries from the dataset trace browse contract", () => {
    expect(
      formatCharacterizationTraceAxesSummary({
        rank: 2,
        axis_names: ["frequency", "L_jun"],
        axis_units: ["GHz", "nH"],
        axis_lengths: [401, 5],
      }),
    ).toBe("frequency (GHz) × L_jun (nH) · 401 × 5");
    expect(formatCharacterizationTraceAxesSummary("Shared axis L_jun")).toBe(
      "Shared axis L_jun",
    );
    expect(formatCharacterizationTraceAxesSummary(null)).toBe("Axis summary unavailable");
  });
});

describe("characterization task helpers", () => {
  const tasks = [
    {
      taskId: 81,
      kind: "characterization",
      lane: "characterization",
      executionMode: "run",
      status: "running",
      submittedAt: "2026-03-15 09:10:00",
      ownerUserId: "user-dev-01",
      ownerDisplayName: "Device Lab",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "workspace",
      datasetId: "fluxonium-2025-031",
      definitionId: null,
      summary: "Characterization request for Fluxonium sweep 031",
      hasActionAuthority: true,
      allowedActions: {
        attach: true,
        cancel: true,
        terminate: false,
        retry: false,
      },
    },
    {
      taskId: 79,
      kind: "characterization",
      lane: "characterization",
      executionMode: "run",
      status: "completed",
      submittedAt: "2026-03-15 08:50:00",
      ownerUserId: "user-dev-01",
      ownerDisplayName: "Device Lab",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "workspace",
      datasetId: "fluxonium-2025-031",
      definitionId: null,
      summary: "Completed characterization sweep",
      hasActionAuthority: true,
      allowedActions: {
        attach: true,
        cancel: false,
        terminate: false,
        retry: true,
      },
    },
    {
      taskId: 77,
      kind: "simulation",
      lane: "simulation",
      executionMode: "run",
      status: "failed",
      submittedAt: "2026-03-15 08:40:00",
      ownerUserId: "user-dev-02",
      ownerDisplayName: "Analysis Team",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "owned",
      datasetId: "transmon-014",
      definitionId: RELATED_SIMULATION_SCHEMA_ID,
      summary: "Simulation task",
      hasActionAuthority: false,
      allowedActions: {
        attach: false,
        cancel: false,
        terminate: false,
        retry: false,
      },
    },
  ] as const;

  it("filters characterization task rows by scope and summarizes shared queue counts", () => {
    expect(resolveLatestCharacterizationTask(tasks)?.taskId).toBe(81);
    expect(
      filterCharacterizationTasks(tasks, {
        searchQuery: "fluxonium",
        scope: "dataset",
        statusFilter: "all",
        activeDatasetId: "fluxonium-2025-031",
      }).map((task) => task.taskId),
    ).toEqual([81, 79]);

    expect(
      summarizeCharacterizationTasks(
        filterCharacterizationTasks(tasks, {
          searchQuery: "",
          scope: "all",
          statusFilter: "all",
          activeDatasetId: "fluxonium-2025-031",
        }),
      ),
    ).toEqual({
      total: 2,
      activeCount: 1,
      completedCount: 1,
      failedCount: 0,
      resultBackedCount: 1,
    });
  });
});

describe("characterization source contracts", () => {
  it("keeps characterization run-first without duplicating task-management walls", () => {
    expect(characterizationWorkspaceSource).toContain('title="Design / Source Scope"');
    expect(characterizationWorkspaceSource).toContain('title="Data Collection Review"');
    expect(characterizationWorkspaceSource).toContain('title="Analysis Pipeline"');
    expect(characterizationWorkspaceSource).toContain('title="Active Analysis Run"');
    expect(characterizationWorkspaceSource).toContain('title="Result Preview"');
    expect(characterizationWorkspaceSource).toContain('title="Downstream Analysis / Next Step"');
    expect(characterizationWorkspaceSource).toContain('<div className="space-y-6">');
    expect(characterizationWorkspaceSource).toContain("Trace Selection");
    expect(characterizationWorkspaceSource).toContain("Sweep Axis");
    expect(characterizationWorkspaceSource).toContain("Collection Hint");
    expect(characterizationWorkspaceSource).toContain("Review Summary");
    expect(characterizationWorkspaceSource).toContain("Collection Members");
    expect(characterizationWorkspaceSource).toContain("Runnable Analyses");
    expect(characterizationWorkspaceSource).toContain("Blocked Analyses");
    expect(characterizationWorkspaceSource).toContain("Results");
    expect(characterizationWorkspaceSource).toContain("Result Detail");
    expect(characterizationWorkspaceSource).toContain("CharacterizationResultExplorer");
    expect(characterizationWorkspaceSource).toContain("Debug Payload");
    expect(characterizationWorkspaceSource).toContain("Identify & Tag");
    expect(characterizationWorkspaceSource).toContain("Pipeline Guidance");
    expect(characterizationWorkspaceSource).toContain("Run History");
    expect(characterizationWorkspaceSource).toContain("No downstream step unlocked yet");
    expect(characterizationWorkspaceSource).toContain("SurfaceActionButton");
    expect(characterizationWorkspaceSource).not.toContain("This registry does not submit or attach analyses.");
    expect(characterizationWorkspaceSource).not.toContain("Characterization Task Queue");
    expect(characterizationWorkspaceSource).not.toContain("TaskLifecyclePanel");
    expect(characterizationWorkspaceSource).not.toContain("ResearchTaskQueuePanel");
    expect(characterizationWorkspaceSource).not.toContain("ResearchWorkflowHero");
    expect(characterizationWorkspaceSource).not.toContain("Queue browsing and task management stay in Global Context.");
    expect(characterizationWorkspaceSource).not.toContain("Compact page-local run state for the attached characterization task.");
    expect(characterizationWorkspaceSource).not.toContain("Queue a run to follow its latest task state here.");
    expect(characterizationWorkspaceSource).not.toContain("latest persisted result in view");
    expect(characterizationWorkspaceSource).not.toContain("Persisted characterization outputs for the current design.");
    expect(characterizationWorkspaceSource).not.toContain("Materialized payload references.");
    expect(characterizationWorkspaceSource).not.toContain("SummaryTile");
    expect(characterizationWorkspaceSource).not.toContain('title="Run Analysis"');
    expect(characterizationWorkspaceSource).not.toContain('title="Latest Analysis"');
    expect(characterizationWorkspaceSource).not.toContain('title="Recent Runs"');
    expect(characterizationWorkspaceSource).not.toContain(
      'xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.9fr)]',
    );
    expect(characterizationExplorerSource).toContain("Result Explorer");
    expect(characterizationExplorerSource).toContain("compareGroups");
    expect(characterizationExplorerSource).toContain("availablePresetViews");
    expect(characterizationExplorerSource).toContain("MemberBadge");
    expect(characterizationExplorerSource).toContain("compatibilityFallback");
    expect(characterizationExplorerSource).toContain("resolveCharacterizationEmbeddedFallbackTable");
  });

  it("binds trace browse, characterization submit, and result continuity to shared app authority", () => {
    expect(characterizationHookSource).toContain(
      "const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null",
    );
    expect(characterizationHookSource).toContain("const { session } = useAppSession();");
    expect(characterizationHookSource).toContain("const taskQueueState = useTaskQueue();");
    expect(characterizationHookSource).toContain("const characterizationTasks = taskQueueState.tasks");
    expect(characterizationHookSource).toContain(".map(normalizeTaskSummary)");
    expect(characterizationHookSource).toContain(
      "listCharacterizationTraceSelectionRows(activeDatasetId, resolvedDesignId)",
    );
    expect(characterizationHookSource).toContain("const taskKey = resolvedTaskId ? taskDetailKey(resolvedTaskId) : null;");
    expect(characterizationHookSource).toContain("() => (resolvedTaskId ? getTask(resolvedTaskId) : Promise.resolve(undefined))");
    expect(characterizationHookSource).toContain("listDesignBrowseRows(activeDatasetId)");
    expect(characterizationHookSource).toContain(
      "listCharacterizationAnalysisRegistry(activeDatasetId, resolvedDesignId",
    );
    expect(characterizationHookSource).toContain("analysisRegistryQuery.data?.inputCollectionPayload");
    expect(characterizationHookSource).toContain("analysisRegistryQuery.data?.dataCollectionReview");
    expect(characterizationHookSource).toContain(
      "listCharacterizationRunHistory(activeDatasetId, resolvedDesignId",
    );
    expect(characterizationHookSource).toContain(
      "listCharacterizationResults(activeDatasetId, resolvedDesignId",
    );
    expect(characterizationHookSource).toContain(
      "getCharacterizationResult(activeDatasetId, resolvedDesignId, resolvedResultId)",
    );
    expect(characterizationHookSource).toContain(
      "resultsQuery.data?.rows && resultsQuery.data.rows.length > 0",
    );
    expect(characterizationHookSource).toContain(
      "if (!rows || rows.length === 0) {",
    );
    expect(characterizationHookSource).toContain("const characterization_setup: CharacterizationSetupDraft");
    expect(characterizationHookSource).toContain('kind: "characterization"');
    expect(characterizationHookSource).toContain("selected_trace_ids: selectedTraceIds");
    expect(characterizationHookSource).toContain("submitCharacterizationTask()");
    expect(characterizationHookSource).toContain("getTaskEnqueueFailureDetails");
    expect(characterizationHookSource).toContain('task?.status === "dispatching"');
    expect(characterizationHookSource).toContain('task?.status === "cancellation_requested"');
    expect(characterizationHookSource).toContain('task?.status === "termination_requested"');
    expect(characterizationHookSource).toContain('task.resultHandoff?.availability === "pending"');
    expect(characterizationHookSource).toContain("activeTask?.characterizationSetup");
    expect(characterizationHookSource).toContain("setSelectedTraceIds([...activeTask.characterizationSetup.selected_trace_ids]);");
    expect(characterizationHookSource).toContain("setCompletedRunSync({");
    expect(characterizationHookSource).toContain("selectBaseTraces()");
    expect(characterizationHookSource).toContain("toggleTraceSelection(traceId");
    expect(characterizationHookSource).toContain("setRunHistoryCursor(null);");
    expect(characterizationHookSource).toContain("focusRunHistoryResult(resultId");
    expect(characterizationHookSource).toContain("applyCharacterizationTagging(");
    expect(characterizationHookSource).toContain("This session cannot start analyses.");
    expect(characterizationExplorerHookSource).toContain("getCharacterizationArtifactPayload(");
    expect(characterizationExplorerHookSource).toContain("keepPreviousData: true");
    expect(characterizationExplorerHookSource).toContain(
      "resolveCharacterizationArtifactCompatibilityPayload",
    );
    expect(characterizationExplorerHookSource).toContain("compatibilityPayload");
    expect(characterizationExplorerHookSource).toContain("resolveCharacterizationArtifactPresetId");
    expect(characterizationExplorerHookSource).toContain("const artifactRefs = resultDetail?.artifactRefs ?? [];");
    expect(characterizationExplorerHookSource).toContain(
      '"characterization-artifact-payload"',
    );
    expect(characterizationApiSource).toContain(
      "payload.prerequisite_state ??",
    );
    expect(characterizationApiSource).toContain(
      "[...(payload.downstream_unlock_analysis_ids ?? [])]",
    );
    expect(characterizationApiSource).toContain(
      "(payload.input_result_refs ?? []).map",
    );
    expect(characterizationApiSource).toContain(
      "(payload.diagnostics ?? []).map",
    );
    expect(characterizationApiSource).toContain(
      "(payload.artifact_refs ?? []).map",
    );
    expect(characterizationApiSource).toContain(
      "(payload?.source_parameters ?? []).map",
    );
    expect(characterizationHookSource).not.toContain("This session cannot submit tasks.");
    expect(characterizationHookSource).not.toContain("listTraceMetadata(");
    expect(characterizationHookSource).not.toContain("rows[0]?.analysisId");
    expect(characterizationHookSource).not.toContain(
      "Select a persisted characterization result before applying identify tags.",
    );
    expect(taskApiSource).toContain("export type CharacterizationSetupDraft");
    expect(taskApiSource).toContain("characterizationSetup?: CharacterizationSetupDraft | null");
    expect(taskApiSource).toContain("characterization_setup?: CharacterizationSetupDraft");
  });
});
