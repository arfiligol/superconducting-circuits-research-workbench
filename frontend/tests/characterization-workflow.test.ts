import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  characterizationAnalysisRegistryKey,
  characterizationArtifactPayloadKey,
  characterizationResultDetailKey,
  characterizationResultsListKey,
  characterizationRunHistoryKey,
  characterizationTaggingsKey,
} from "../src/features/characterization/lib/api";
import {
  buildCharacterizationArtifactPayloadRequest,
  resolveCharacterizationArtifactPresetId,
  resolveCharacterizationArtifactSelection,
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
      "/api/backend/datasets/fluxonium-2025-031/designs/design_flux_scan_a/characterization-results/char-fit-flux-a-01/artifacts/artifact_resonance_frequency_matrix/payload?view_mode=plot&preset_id=plot_mode_vs_frequency_by_ljun",
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
  const artifactManifest = [
    {
      artifactId: "artifact_resonance_frequency_matrix",
      category: "matrix",
      viewKind: "preset_query",
      title: "Resonance Matrix",
      summary: "Mode-index by input-axis frequency grid.",
      payloadFormat: "json",
      payloadLocator: null,
      supportedViewModes: ["table", "plot"],
      supportedPresetIds: [
        "table_mode_by_input_axis",
        "plot_mode_profile",
        "plot_sweep_profile",
      ],
      defaultPresetId: "table_mode_by_input_axis",
      axisSummary: {
        inputAxes: [{ key: "input_axis", label: "Input Axis", unit: "nH", family: "input_axis" }],
        derivedAxes: [{ key: "mode_index", label: "Mode Index", unit: null, family: "derived_axis" }],
        metrics: [{ key: "frequency_ghz", label: "Frequency", unit: "GHz", family: "metric" }],
      },
      presetViews: [
        {
          presetId: "table_mode_by_input_axis",
          label: "Matrix",
          description: "Rows mode index, columns input axis.",
          viewMode: "table",
          isDefault: true,
          axisContract: {
            rowAxis: "mode_index",
            columnAxis: "input_axis",
            xAxis: null,
            yAxis: null,
            seriesAxis: null,
            metric: "frequency_ghz",
          },
        },
        {
          presetId: "plot_mode_profile",
          label: "Mode Profile",
          description: "x mode index, series input axis.",
          viewMode: "plot",
          isDefault: false,
          axisContract: {
            rowAxis: null,
            columnAxis: null,
            xAxis: "mode_index",
            yAxis: "frequency_ghz",
            seriesAxis: "input_axis",
            metric: "frequency_ghz",
          },
        },
        {
          presetId: "plot_sweep_profile",
          label: "Sweep Profile",
          description: "x input axis, series mode index.",
          viewMode: "plot",
          isDefault: false,
          axisContract: {
            rowAxis: null,
            columnAxis: null,
            xAxis: "input_axis",
            yAxis: "frequency_ghz",
            seriesAxis: "mode_index",
            metric: "frequency_ghz",
          },
        },
      ],
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
    },
  ] as const;

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
    const artifact = resolveCharacterizationArtifactSelection(artifactManifest, null);
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
    expect(characterizationWorkspaceSource).toContain('title="Select Data Scope"');
    expect(characterizationWorkspaceSource).toContain('title="Choose Analysis & Setup"');
    expect(characterizationWorkspaceSource).toContain('title="Inspect Result"');
    expect(characterizationWorkspaceSource).toContain('<div className="space-y-6">');
    expect(characterizationWorkspaceSource).toContain("Trace Selection");
    expect(characterizationWorkspaceSource).toContain("Sweep Axis");
    expect(characterizationWorkspaceSource).toContain("Collection Hint");
    expect(characterizationWorkspaceSource).toContain("Results");
    expect(characterizationWorkspaceSource).toContain("Result Detail");
    expect(characterizationWorkspaceSource).toContain("CharacterizationResultExplorer");
    expect(characterizationWorkspaceSource).toContain("Debug Payload");
    expect(characterizationWorkspaceSource).toContain("Identify & Tag");
    expect(characterizationWorkspaceSource).toContain("Validation Explanation");
    expect(characterizationWorkspaceSource).toContain("None available");
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
    expect(characterizationWorkspaceSource).not.toContain("artifactRefs");
    expect(characterizationWorkspaceSource).not.toContain("SummaryTile");
    expect(characterizationWorkspaceSource).not.toContain('title="Run Analysis"');
    expect(characterizationWorkspaceSource).not.toContain('title="Latest Analysis"');
    expect(characterizationWorkspaceSource).not.toContain('title="Recent Runs"');
    expect(characterizationWorkspaceSource).not.toContain(
      'xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.9fr)]',
    );
    expect(characterizationExplorerSource).toContain("Result Explorer");
    expect(characterizationExplorerSource).toContain("supportedViewModes");
    expect(characterizationExplorerSource).toContain("availablePresetViews");
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
    expect(characterizationHookSource).toContain(
      "listCharacterizationRunHistory(activeDatasetId, resolvedDesignId",
    );
    expect(characterizationHookSource).toContain(
      "listCharacterizationResults(activeDatasetId, resolvedDesignId",
    );
    expect(characterizationHookSource).toContain(
      "getCharacterizationResult(activeDatasetId, resolvedDesignId, resolvedResultId)",
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
    expect(characterizationExplorerHookSource).toContain("resolveCharacterizationArtifactPresetId");
    expect(characterizationExplorerHookSource).toContain(
      '"characterization-artifact-payload"',
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
