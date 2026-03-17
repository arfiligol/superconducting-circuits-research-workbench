import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  buildSimulationSetupDraft,
  buildSimulationSetupFormValuesFromPersistedSetup,
  cloneSimulationSetupFormValues,
  defaultSimulationSetupFormValues,
  deriveSimulationPtcPortOptions,
  deriveSimulationSweepTargetOptions,
} from "../src/features/simulation/lib/setup-form";
import {
  createSavedSimulationSetupRecord,
  filterSavedSimulationSetupsByDefinition,
  readSavedSimulationSetupRecords,
  removeSavedSimulationSetupRecord,
  replaceSavedSimulationSetupRecord,
  serializeSavedSimulationSetupRecords,
} from "../src/features/simulation/lib/saved-setups";
import {
  mapTaskDetailResponse,
  taskDetailKey,
  unwrapTaskMutation,
} from "../src/lib/api/tasks";
import {
  parseSimulationDefinitionIdParam,
  resolveSimulationDefinitionId,
} from "../src/features/simulation/lib/definition-id";
import {
  buildSimulationRequestSummary,
  filterSimulationDefinitions,
  filterSimulationTasksByContext,
  filterSimulationTasks,
  formatSimulationTaskStatusLabel,
  hasSimulationTaskResult,
  resolveContextBoundAttachedTask,
  resolveLatestSimulationStageTask,
  resolveLatestSimulationStageTaskInContext,
  resolveLatestSimulationTask,
  resolveLatestSimulationTaskInContext,
  resolvePostProcessingUpstreamTaskId,
  resolveSimulationSelectionRecovery,
  resolveSimulationTaskAttachmentState,
  resolveSimulationTaskRecovery,
  summarizeSimulationTaskResults,
  summarizeSimulationTasks,
} from "../src/features/simulation/lib/workflow";

const simulationWorkbenchSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/components/simulation-workbench-shell.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);
const simulationWorkflowHookSource = readFileSync(
  fileURLToPath(
    new URL("../src/features/simulation/hooks/use-simulation-workflow-data.ts", import.meta.url),
  ),
  "utf8",
);

describe("simulation definition routing helpers", () => {
  const definitions = [
    {
      definition_id: 18,
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08 18:19:42",
      element_count: 12,
      validation_status: "warning",
      preview_artifact_count: 2,
    },
    {
      definition_id: 24,
      name: "TransmonControlReference",
      created_at: "2026-03-10 09:22:11",
      element_count: 7,
      validation_status: "ok",
      preview_artifact_count: 3,
    },
  ] as const;

  it("parses numeric simulation definition ids", () => {
    expect(parseSimulationDefinitionIdParam("24")).toBe(24);
    expect(parseSimulationDefinitionIdParam("new")).toBeNull();
    expect(parseSimulationDefinitionIdParam(null)).toBeNull();
  });

  it("falls back to the first definition when routing is missing or invalid", () => {
    expect(resolveSimulationDefinitionId(null, definitions)).toBe(18);
    expect(resolveSimulationDefinitionId("999", definitions)).toBe(18);
  });

  it("filters the simulation definition catalog and reports invalid route recovery", () => {
    expect(filterSimulationDefinitions(definitions, "trans")).toEqual([definitions[1]]);
    expect(resolveSimulationSelectionRecovery("bad", 18, definitions)?.title).toBe(
      "Invalid URL selection",
    );
  });
});

describe("simulation task workflow helpers", () => {
  const tasks = [
    {
      taskId: 31,
      kind: "simulation",
      lane: "simulation",
      executionMode: "run",
      status: "running",
      submittedAt: "2026-03-12 10:20:00",
      ownerUserId: "user-dev-01",
      ownerDisplayName: "Device Lab",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "workspace",
      datasetId: "fluxonium-2025-031",
      definitionId: 18,
      summary: "Simulation request for FloatingQubitWithXYLine",
      hasActionAuthority: true,
      allowedActions: {
        attach: true,
        cancel: true,
        terminate: false,
        retry: false,
      },
    },
    {
      taskId: 29,
      kind: "post_processing",
      lane: "simulation",
      executionMode: "run",
      status: "completed",
      submittedAt: "2026-03-12 10:10:00",
      ownerUserId: "user-dev-01",
      ownerDisplayName: "Device Lab",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "workspace",
      datasetId: "fluxonium-2025-031",
      definitionId: 18,
      summary: "Post-processing request for FloatingQubitWithXYLine",
      hasActionAuthority: true,
      allowedActions: {
        attach: true,
        cancel: false,
        terminate: false,
        retry: true,
      },
    },
    {
      taskId: 28,
      kind: "characterization",
      lane: "characterization",
      executionMode: "run",
      status: "failed",
      submittedAt: "2026-03-12 09:55:00",
      ownerUserId: "user-dev-02",
      ownerDisplayName: "Analysis Team",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "owned",
      datasetId: "transmon-014",
      definitionId: null,
      summary: "Characterization task",
      hasActionAuthority: false,
      allowedActions: {
        attach: false,
        cancel: false,
        terminate: false,
        retry: false,
      },
    },
  ] as const;

  it("builds stable submission summaries and chooses the latest simulation task", () => {
    expect(
      buildSimulationRequestSummary({
        kind: "simulation",
        definitionId: 18,
        definitionName: "FloatingQubitWithXYLine",
        datasetId: "fluxonium-2025-031",
        datasetName: "Fluxonium sweep 031",
        note: "cache validation",
      }),
    ).toBe(
      "Simulation request for FloatingQubitWithXYLine · dataset Fluxonium sweep 031 · cache validation",
    );
    expect(resolveLatestSimulationTask(tasks)?.taskId).toBe(31);
    expect(resolveLatestSimulationStageTask(tasks, "simulation")?.taskId).toBe(31);
    expect(resolveLatestSimulationStageTask(tasks, "post_processing")?.taskId).toBe(29);
    expect(formatSimulationTaskStatusLabel("dispatching")).toBe("Queued");
    expect(formatSimulationTaskStatusLabel("running")).toBe("Running");
    expect(formatSimulationTaskStatusLabel("completed")).toBe("Completed");
    expect(formatSimulationTaskStatusLabel("failed")).toBe("Failed");
  });

  it("filters and summarizes simulation-lane tasks", () => {
    const filtered = filterSimulationTasks(tasks, {
      searchQuery: "floating",
      scope: "definition",
      statusFilter: "all",
      selectedDefinitionId: 18,
      activeDatasetId: "fluxonium-2025-031",
    });

    expect(filtered.map((task) => task.taskId)).toEqual([31, 29]);
    expect(summarizeSimulationTasks(filtered)).toEqual({
      total: 2,
      activeCount: 1,
      completedCount: 1,
      failedCount: 0,
      resultBackedCount: 1,
    });
  });

  it("binds the latest simulation and post-processing stages to the current definition and dataset", () => {
    const contextBoundTasks = [
      {
        taskId: 55,
        kind: "simulation",
        lane: "simulation",
        executionMode: "run",
        status: "completed",
        submittedAt: "2026-03-12 10:35:00",
        ownerUserId: "user-dev-01",
        ownerDisplayName: "Device Lab",
        workspaceId: "workspace-lab",
        workspaceSlug: "device-lab",
        visibilityScope: "workspace",
        datasetId: "fluxonium-2025-031",
        definitionId: 18,
        summary: "Simulation request for FloatingQubitWithXYLine",
        hasActionAuthority: true,
        allowedActions: {
          attach: true,
          cancel: false,
          terminate: false,
          retry: true,
        },
      },
      {
        taskId: 56,
        kind: "post_processing",
        lane: "simulation",
        executionMode: "run",
        status: "queued",
        submittedAt: "2026-03-12 10:40:00",
        ownerUserId: "user-dev-01",
        ownerDisplayName: "Device Lab",
        workspaceId: "workspace-lab",
        workspaceSlug: "device-lab",
        visibilityScope: "workspace",
        datasetId: "fluxonium-2025-031",
        definitionId: 18,
        summary: "Post-processing request for FloatingQubitWithXYLine",
        hasActionAuthority: true,
        allowedActions: {
          attach: true,
          cancel: true,
          terminate: false,
          retry: false,
        },
      },
      {
        taskId: 57,
        kind: "simulation",
        lane: "simulation",
        executionMode: "run",
        status: "running",
        submittedAt: "2026-03-12 10:50:00",
        ownerUserId: "user-dev-01",
        ownerDisplayName: "Device Lab",
        workspaceId: "workspace-lab",
        workspaceSlug: "device-lab",
        visibilityScope: "workspace",
        datasetId: "fluxonium-2025-999",
        definitionId: 18,
        summary: "Simulation request for another dataset",
        hasActionAuthority: true,
        allowedActions: {
          attach: true,
          cancel: true,
          terminate: false,
          retry: false,
        },
      },
      {
        taskId: 58,
        kind: "post_processing",
        lane: "simulation",
        executionMode: "run",
        status: "completed",
        submittedAt: "2026-03-12 10:55:00",
        ownerUserId: "user-dev-01",
        ownerDisplayName: "Device Lab",
        workspaceId: "workspace-lab",
        workspaceSlug: "device-lab",
        visibilityScope: "workspace",
        datasetId: "fluxonium-2025-031",
        definitionId: 24,
        summary: "Post-processing request for another definition",
        hasActionAuthority: true,
        allowedActions: {
          attach: true,
          cancel: false,
          terminate: false,
          retry: true,
        },
      },
    ] as const;
    const pageContext = {
      definitionId: 18,
      datasetId: "fluxonium-2025-031",
    } as const;

    expect(filterSimulationTasksByContext(contextBoundTasks, pageContext).map((task) => task.taskId)).toEqual([
      55,
      56,
    ]);
    expect(resolveLatestSimulationTask(contextBoundTasks)?.taskId).toBe(56);
    expect(resolveLatestSimulationTaskInContext(contextBoundTasks, pageContext)?.taskId).toBe(56);
    expect(
      resolveLatestSimulationStageTaskInContext(contextBoundTasks, "simulation", pageContext)
        ?.taskId,
    ).toBe(55);
    expect(
      resolveLatestSimulationStageTaskInContext(
        contextBoundTasks,
        "post_processing",
        pageContext,
      )?.taskId,
    ).toBe(56);
  });

  it("can recover stage authority from an explicitly attached task detail when queue rows omit context", () => {
    expect(
      resolveContextBoundAttachedTask(
        {
          taskId: 371,
          kind: "simulation",
          lane: "simulation",
          executionMode: "run",
          status: "queued",
          submittedAt: "2026-03-12 10:30:00",
          ownerUserId: "user-dev-01",
          ownerDisplayName: "Device Lab",
          workspaceId: "workspace-lab",
          workspaceSlug: "device-lab",
          visibilityScope: "workspace",
          datasetId: "fluxonium-2025-031",
          definitionId: 18,
          summary: "Simulation request for FloatingQubitWithXYLine",
          hasActionAuthority: true,
          allowedActions: {
            attach: true,
            cancel: true,
            terminate: false,
            retry: false,
          },
          queueBackend: "in_memory_scaffold",
          workerTaskName: "simulation_run_task",
          requestReady: true,
          submittedFromActiveDataset: true,
          dispatch: {
            dispatchKey: "dispatch:371:simulation_run_task",
            status: "accepted",
            submissionSource: "active_dataset",
            acceptedAt: "2026-03-12 10:30:00",
            lastUpdatedAt: "2026-03-12 10:30:00",
          },
          events: [],
          progress: {
            phase: "queued",
            percentComplete: 0,
            summary: "queued",
            updatedAt: "2026-03-12 10:30:00",
          },
          resultRefs: {
            traceBatchId: null,
            analysisRunId: null,
            metadataRecords: [],
            tracePayload: null,
            resultHandles: [],
          },
        },
        {
          definitionId: 18,
          datasetId: "fluxonium-2025-031",
        },
        "simulation",
      )?.taskId,
    ).toBe(371);

    expect(
      resolveContextBoundAttachedTask(
        {
          taskId: 910,
          kind: "simulation",
          lane: "simulation",
          executionMode: "run",
          status: "completed",
          submittedAt: "2026-03-12 10:40:00",
          ownerUserId: "user-dev-01",
          ownerDisplayName: "Device Lab",
          workspaceId: "workspace-lab",
          workspaceSlug: "device-lab",
          visibilityScope: "workspace",
          datasetId: "other-dataset",
          definitionId: 18,
          summary: "Simulation request for another dataset",
          hasActionAuthority: true,
          allowedActions: {
            attach: true,
            cancel: false,
            terminate: false,
            retry: true,
          },
          queueBackend: "in_memory_scaffold",
          workerTaskName: "simulation_run_task",
          requestReady: true,
          submittedFromActiveDataset: true,
          dispatch: {
            dispatchKey: "dispatch:910:simulation_run_task",
            status: "completed",
            submissionSource: "active_dataset",
            acceptedAt: "2026-03-12 10:40:00",
            lastUpdatedAt: "2026-03-12 10:45:00",
          },
          events: [],
          progress: {
            phase: "completed",
            percentComplete: 100,
            summary: "completed",
            updatedAt: "2026-03-12 10:45:00",
          },
          resultRefs: {
            traceBatchId: 12,
            analysisRunId: null,
            metadataRecords: [],
            tracePayload: null,
            resultHandles: [],
          },
        },
        {
          definitionId: 18,
          datasetId: "fluxonium-2025-031",
        },
        "simulation",
      ),
    ).toBeUndefined();
  });

  it("reports task recovery and attachment state", () => {
    expect(resolveSimulationTaskRecovery(91, 31, new Error("not found"))?.title).toBe(
      "Task reattach available",
    );
    expect(
      resolveSimulationTaskAttachmentState(
        {
          taskId: 29,
          kind: "post_processing",
          lane: "simulation",
          executionMode: "run",
          status: "completed",
          submittedAt: "2026-03-12 10:10:00",
          ownerUserId: "user-dev-01",
          ownerDisplayName: "Device Lab",
          workspaceId: "workspace-lab",
          workspaceSlug: "device-lab",
          visibilityScope: "workspace",
          datasetId: "fluxonium-2025-031",
          definitionId: 18,
          summary: "Post-processing request for FloatingQubitWithXYLine",
          hasActionAuthority: true,
          allowedActions: {
            attach: true,
            cancel: false,
            terminate: false,
            retry: true,
          },
          queueBackend: "in_memory_scaffold",
          workerTaskName: "post_processing_run_task",
          requestReady: true,
          submittedFromActiveDataset: true,
          dispatch: {
            dispatchKey: "dispatch:29:post_processing_run_task",
            status: "completed",
            submissionSource: "active_dataset",
            acceptedAt: "2026-03-12 10:10:00",
            lastUpdatedAt: "2026-03-12 10:11:00",
          },
          events: [
            {
              eventKey: "task-event-29-completed",
              eventType: "task_completed",
              level: "info",
              occurredAt: "2026-03-12 10:11:00",
              message: "Post-processing artifacts were materialized.",
              metadata: {
                task_id: 29,
                phase: "completed",
              },
            },
          ],
          progress: {
            phase: "completed",
            percentComplete: 100,
            summary: "Post-processing complete",
            updatedAt: "2026-03-12 10:11:00",
          },
          resultRefs: {
            traceBatchId: 44,
            analysisRunId: 9,
            metadataRecords: [],
            tracePayload: null,
            resultHandles: [],
          },
        },
        31,
      ),
    ).toEqual({
      isAttached: false,
      isStaleSnapshot: true,
    });
  });

  it("summarizes task result refs", () => {
    const completedPostProcessingTask = {
      taskId: 29,
      kind: "post_processing",
      lane: "simulation",
      executionMode: "run",
      status: "completed",
      submittedAt: "2026-03-12 10:10:00",
      ownerUserId: "user-dev-01",
      ownerDisplayName: "Device Lab",
      workspaceId: "workspace-lab",
      workspaceSlug: "device-lab",
      visibilityScope: "workspace",
      datasetId: "fluxonium-2025-031",
      definitionId: 18,
      summary: "Post-processing request for FloatingQubitWithXYLine",
      hasActionAuthority: true,
      allowedActions: {
        attach: true,
        cancel: false,
        terminate: false,
        retry: true,
      },
      queueBackend: "in_memory_scaffold",
      workerTaskName: "post_processing_run_task",
      requestReady: true,
      submittedFromActiveDataset: true,
      dispatch: {
        dispatchKey: "dispatch:29:post_processing_run_task",
        status: "completed",
        submissionSource: "active_dataset",
        acceptedAt: "2026-03-12 10:10:00",
        lastUpdatedAt: "2026-03-12 10:11:00",
      },
      events: [
        {
          eventKey: "task-event-29-completed",
          eventType: "task_completed",
          level: "info",
          occurredAt: "2026-03-12 10:11:00",
          message: "Post-processing artifacts were materialized.",
          metadata: {
            task_id: 29,
            phase: "completed",
          },
        },
      ],
      progress: {
        phase: "completed",
        percentComplete: 100,
        summary: "Post-processing complete",
        updatedAt: "2026-03-12 10:11:00",
      },
      resultRefs: {
        traceBatchId: 44,
        analysisRunId: 9,
        metadataRecords: [
          {
            backend: "sqlite_metadata",
            recordType: "trace_batch",
            recordId: "trace-batch-44",
            version: 1,
            schemaVersion: "trace-batch/v1",
          },
        ],
        tracePayload: {
          contractVersion: "trace-payload/v1",
          backend: "local_zarr",
          payloadRole: "task_output",
          storeKey: "trace-output-44",
          storeUri: "/data/trace-output-44.zarr",
          groupPath: "/",
          arrayPath: "/s11",
          dtype: "float64",
          shape: [801],
          chunkShape: [128],
          schemaVersion: "zarr/v2",
        },
        resultHandles: [
          {
            contractVersion: "result-handle/v1",
            handleId: "handle-44",
            kind: "simulation_trace",
            status: "materialized",
            label: "S11",
            metadataRecord: {
              backend: "sqlite_metadata",
              recordType: "result_handle",
              recordId: "handle-44",
              version: 1,
              schemaVersion: "result-handle/v1",
            },
            payloadBackend: "local_zarr",
            payloadFormat: "zarr",
            payloadRole: "trace_payload",
            payloadLocator: "/data/trace-output-44.zarr",
            provenanceTaskId: 29,
            provenance: {
              sourceDatasetId: "fluxonium-2025-031",
              sourceTaskId: 31,
              traceBatchRecord: null,
              analysisRunRecord: null,
            },
          },
        ],
      },
    } as const;

    expect(summarizeSimulationTaskResults(completedPostProcessingTask)).toEqual({
      metadataRecordCount: 1,
      resultHandleCount: 1,
      materializedHandleCount: 1,
      hasTracePayload: true,
      traceBatchId: 44,
      analysisRunId: 9,
    });
    expect(hasSimulationTaskResult(completedPostProcessingTask)).toBe(true);
    expect(resolvePostProcessingUpstreamTaskId(completedPostProcessingTask)).toBe(31);
  });
});

describe("simulation workflow source contract", () => {
  it("stores saved simulation setups as definition-scoped local browser drafts", () => {
    const baselineRecord = createSavedSimulationSetupRecord({
      id: "setup-local-1",
      definitionId: 18,
      definitionName: "FloatingQubitWithXYLine",
      name: "Baseline sweep",
      createdAt: "2026-03-18T12:00:00Z",
      updatedAt: "2026-03-18T12:00:00Z",
      values: cloneSimulationSetupFormValues(defaultSimulationSetupFormValues),
    });
    const updatedRecord = createSavedSimulationSetupRecord({
      ...baselineRecord,
      updatedAt: "2026-03-18T13:00:00Z",
      values: cloneSimulationSetupFormValues({
        ...defaultSimulationSetupFormValues,
        simulationStartGhz: 3,
      }),
    });
    const otherDefinitionRecord = createSavedSimulationSetupRecord({
      id: "setup-local-2",
      definitionId: 24,
      definitionName: "TransmonControlReference",
      name: "Alt definition setup",
      createdAt: "2026-03-18T12:30:00Z",
      updatedAt: "2026-03-18T12:30:00Z",
      values: cloneSimulationSetupFormValues(defaultSimulationSetupFormValues),
    });

    const savedRecords = replaceSavedSimulationSetupRecord([baselineRecord], updatedRecord);
    const allRecords = replaceSavedSimulationSetupRecord(savedRecords, otherDefinitionRecord);
    const serialized = serializeSavedSimulationSetupRecords(allRecords);
    const parsedRecords = readSavedSimulationSetupRecords(serialized);

    expect(filterSavedSimulationSetupsByDefinition(parsedRecords, 18).map((record) => record.name)).toEqual([
      "Baseline sweep",
    ]);
    expect(filterSavedSimulationSetupsByDefinition(parsedRecords, 18)[0]?.values.simulationStartGhz).toBe(3);
    expect(removeSavedSimulationSetupRecord(parsedRecords, "setup-local-1")).toHaveLength(1);
  });

  it("maps persisted simulation setup while leaving local-only drafts outside backend authority", () => {
    const draft = buildSimulationSetupDraft({
      ...defaultSimulationSetupFormValues,
      simulationStartGhz: 4,
      simulationStopGhz: 9,
      simulationPointCount: 801,
      simulationParameterSweepEnabled: true,
      simulationParameterSweepAxes: [
        {
          parameter: "L_q",
          mode: "range",
          start: 1,
          stop: 1.2,
          pointCount: 3,
          explicitValues: "",
          unit: "nH",
        },
        {
          parameter: "C_q",
          mode: "explicit",
          start: 0,
          stop: 0,
          pointCount: 1,
          explicitValues: "12, 14, 16",
          unit: "fF",
        },
      ],
      simulationSources: [
        {
          sourceId: "src_drive_1",
          port: "port_1",
          currentAmp: 1,
          pumpFreqGhz: 5,
          sourceMode: "1",
        },
        {
          sourceId: "src_probe_2",
          port: "port_2",
          currentAmp: 0.15,
          pumpFreqGhz: 6.2,
          sourceMode: "1, 0",
        },
      ],
    });

    expect(draft.parameter_sweeps).toEqual([
      {
        parameter: "L_q",
        values: [1, 1.1, 1.2],
        unit: "nH",
      },
      {
        parameter: "C_q",
        values: [12, 14, 16],
        unit: "fF",
      },
    ]);
    expect(draft.sources).toEqual([
      {
        source_id: "src_drive_1",
        kind: "pump",
        target: "port_1",
        amplitude: 1,
        frequency_ghz: 5,
        phase_deg: null,
      },
      {
        source_id: "src_probe_2",
        kind: "pump",
        target: "port_2",
        amplitude: 0.15,
        frequency_ghz: 6.2,
        phase_deg: null,
      },
    ]);

    const rehydrated = buildSimulationSetupFormValuesFromPersistedSetup(
      {
        ...defaultSimulationSetupFormValues,
        simulationPtcEnabled: true,
        simulationPtcMode: "manual",
        simulationPtcCompensatePorts: "port_1, port_2",
        simulationPtcManualNotes: "manual offsets",
        simulationAdvancedDampingStrategy: "adaptive",
        simulationAdvancedLineSearchEnabled: true,
        simulationAdvancedResidualClamp: "1e-6",
        simulationAdvancedNewtonRelaxation: "0.85",
        simulationAdvancedNotes: "local-only advanced draft",
      },
      {
        frequencySweep: {
          startGhz: 5,
          stopGhz: 8,
          pointCount: 501,
          spacing: "log",
        },
        parameterSweeps: [
          {
            parameter: "L_q",
            values: [1, 1.1, 1.2],
            unit: "nH",
          },
        ],
        solver: {
          solverFamily: "harmonic_balance",
          maxIterations: 120,
          convergenceTolerance: 1e-7,
          harmonicBalance: {
            enabled: true,
            harmonicCount: 5,
            oversampleFactor: 3,
          },
        },
        sources: [
          {
            sourceId: "src_drive_1",
            kind: "pump",
            target: "port_1",
            amplitude: 1,
            frequencyGhz: 5,
            phaseDeg: null,
          },
          {
            sourceId: "src_probe_2",
            kind: "pump",
            target: "port_2",
            amplitude: 0.15,
            frequencyGhz: 6.2,
            phaseDeg: null,
          },
        ],
      },
    );

    expect(rehydrated.simulationParameterSweepEnabled).toBe(true);
    expect(rehydrated.simulationParameterSweepAxes).toEqual([
      {
        parameter: "L_q",
        mode: "explicit",
        start: 1,
        stop: 1.2,
        pointCount: 3,
        explicitValues: "1, 1.1, 1.2",
        unit: "nH",
      },
    ]);
    expect(rehydrated.simulationSources).toHaveLength(2);
    expect(rehydrated.simulationSources[0]).toMatchObject({
      port: "port_1",
      currentAmp: 1,
      pumpFreqGhz: 5,
      sourceMode: "1",
    });
    expect(rehydrated.simulationPtcEnabled).toBe(true);
    expect(rehydrated.simulationPtcManualNotes).toBe("manual offsets");
    expect(rehydrated.simulationAdvancedNotes).toBe("local-only advanced draft");
  });

  it("derives schema-backed sweep targets and ptc ports from the selected definition", () => {
    const definitionSource = `{
      "name": "SweepableSeriesLC",
      "parameters": [
        {"name": "Lj", "default": 1000.0, "unit": "pH"},
        {"name": "Cj", "default": 1000.0, "unit": "fF"}
      ],
      "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
        {"name": "C2", "value_ref": "Cj", "unit": "fF"}
      ],
      "topology": [
        ("P1", "1", "0", 1),
        ("P2", "2", "0", 2),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
      ]
    }`;

    expect(
      deriveSimulationSweepTargetOptions(definitionSource, [
        {
          sourceId: "src_drive_1",
          port: "port_1",
          currentAmp: 1,
          pumpFreqGhz: 5,
          sourceMode: "1",
        },
      ]),
    ).toEqual([
      { value: "Lj", label: "Lj (pH)", unit: "pH", source: "schema" },
      { value: "Cj", label: "Cj (fF)", unit: "fF", source: "schema" },
      {
        value: "sources[1].current_amp",
        label: "Port 1 · Source current (A)",
        unit: "A",
        source: "source",
      },
      {
        value: "sources[1].pump_freq_ghz",
        label: "Port 1 · Pump freq (GHz)",
        unit: "GHz",
        source: "source",
      },
    ]);

    expect(deriveSimulationPtcPortOptions(definitionSource)).toEqual([
      { value: "port_1", label: "Port 1", sourceElement: "P1" },
      { value: "port_2", label: "Port 2", sourceElement: "P2" },
    ]);
  });

  it("keeps the page organized around the five-stage workflow instead of task dashboards", () => {
    expect(simulationWorkbenchSource).toContain("Definition / Netlist Context");
    expect(simulationWorkbenchSource).toContain("Simulation Setup");
    expect(simulationWorkbenchSource).toContain("Simulation Result");
    expect(simulationWorkbenchSource).toContain("Post Processing Setup");
    expect(simulationWorkbenchSource).toContain("Post Processing Result");
    expect(simulationWorkbenchSource).toContain("Signal Frequency Sweep Range");
    expect(simulationWorkbenchSource).toContain("Parameter Sweep Setup");
    expect(simulationWorkbenchSource).toContain("HB Solving");
    expect(simulationWorkbenchSource).toContain("Sources");
    expect(simulationWorkbenchSource).toContain("PTC");
    expect(simulationWorkbenchSource).toContain("Advanced hbsolve Options");
    expect(simulationWorkbenchSource).toContain("Add Axis");
    expect(simulationWorkbenchSource).toContain("Add Source");
    expect(simulationWorkbenchSource).toContain("Local draft only");
    expect(simulationWorkbenchSource).toContain("Source Current Ip (A)");
    expect(simulationWorkbenchSource).toContain("Source Mode");
    expect(simulationWorkbenchSource).toContain("Pump Source");
    expect(simulationWorkbenchSource).toContain("Run Simulation");
    expect(simulationWorkbenchSource).toContain("Run Post Processing");
    expect(simulationWorkbenchSource).toContain("Open in Global Context");
    expect(simulationWorkbenchSource).toContain("Browser-saved per selected definition");
    expect(simulationWorkbenchSource).toContain("Manage");
    expect(simulationWorkbenchSource).toContain("Save");
    expect(simulationWorkbenchSource).toContain('role="switch"');
    expect(simulationWorkbenchSource).toContain('addEventListener("wheel"');
    expect(simulationWorkbenchSource).toContain("resolveWheelStep");
    expect(simulationWorkbenchSource).toContain("stepUp()");
    expect(simulationWorkbenchSource).not.toContain('type="checkbox"');
    expect(simulationWorkbenchSource).toContain("buildSimulationSetupDraft");
    expect(simulationWorkbenchSource).toContain("buildSimulationSetupFormValuesFromPersistedSetup");
    expect(simulationWorkbenchSource).toContain("buildPostProcessingSetupDraft");
    expect(simulationWorkbenchSource).toContain("Operation Config JSON");
    expect(simulationWorkbenchSource).toContain("Rehydrated from task #");
    expect(simulationWorkbenchSource).toContain('label="Expanded Netlist"');
    expect(simulationWorkbenchSource).not.toContain('label="Canonical Source"');
    expect(simulationWorkbenchSource).not.toContain('title="Workflow boundary"');
    expect(simulationWorkbenchSource).not.toContain("Open Schemas");
    expect(simulationWorkbenchSource).not.toContain("Open Schema Editor");
    expect(simulationWorkbenchSource).not.toContain("Open Schemdraw");
    expect(simulationWorkbenchSource).not.toContain('label="Visibility"');
    expect(simulationWorkbenchSource).not.toContain("Summary-bound");
    expect(simulationWorkbenchSource).not.toContain("Simulation Task Queue");
    expect(simulationWorkbenchSource).not.toContain("Research Workflow State");
    expect(simulationWorkbenchSource).not.toContain("Task Attachment / Recovery");
    expect(simulationWorkbenchSource).not.toContain("Dispatch / Execution Status");
    expect(simulationWorkbenchSource).not.toContain("Task Event History");
    expect(simulationWorkbenchSource).not.toContain("Persisted Result Surface");
    expect(simulationWorkbenchSource).not.toContain("Definition Binding");
    expect(simulationWorkbenchSource).not.toContain("Sweep Parameter (optional)");
    expect(simulationWorkbenchSource).not.toContain("Phase (deg)");
    expect(simulationWorkbenchSource).toContain("deriveSimulationSweepTargetOptions");
    expect(simulationWorkbenchSource).toContain("deriveSimulationPtcPortOptions");
    expect(simulationWorkbenchSource).toContain("No sweep targets are currently available");
  });

  it("binds stage authority to the current definition and dataset context", () => {
    expect(simulationWorkflowHookSource).toContain("resolveLatestSimulationTaskInContext(");
    expect(simulationWorkflowHookSource).toContain("resolveLatestSimulationStageTaskInContext(");
    expect(simulationWorkflowHookSource).toContain("const pageContext = {");
    expect(simulationWorkbenchSource).toContain("summarizeTaskContextBinding");
    expect(simulationWorkbenchSource).toContain("taskContextBinding?.hasMismatch");
    expect(simulationWorkbenchSource).toContain("title={taskContextBinding.title}");
    expect(simulationWorkbenchSource).toContain("message={taskContextBinding.message}");
    expect(simulationWorkflowHookSource).toContain("simulation_setup: simulationSetup ?? null");
    expect(simulationWorkflowHookSource).toContain("post_processing_setup: postProcessingSetup ?? null");
    expect(simulationWorkflowHookSource).toContain("attachedContextTask");
    expect(simulationWorkflowHookSource).toContain("upstreamSimulationStageTask");
  });
});

describe("task api detail mapping", () => {
  it("maps task detail responses, detail keys, and mutation envelopes", () => {
    expect(taskDetailKey(31)).toBe("/api/backend/tasks/31");

    const detail = mapTaskDetailResponse({
      task_id: 31,
      kind: "simulation",
      lane: "simulation",
      execution_mode: "run",
      status: "running",
      submitted_at: "2026-03-12 10:20:00",
      owner_user_id: "user-dev-01",
      owner_display_name: "Device Lab",
      workspace_id: "workspace-lab",
      workspace_slug: "device-lab",
      visibility_scope: "workspace",
      dataset_id: "fluxonium-2025-031",
      definition_id: 18,
      summary: "Simulation request for FloatingQubitWithXYLine",
      queue_backend: "in_memory_scaffold",
      worker_task_name: "simulation_run_task",
      request_ready: true,
      submitted_from_active_dataset: true,
      dispatch: {
        dispatch_key: "dispatch:31:simulation_run_task",
        status: "running",
        submission_source: "active_dataset",
        accepted_at: "2026-03-12 10:20:00",
        last_updated_at: "2026-03-12 10:21:00",
      },
      events: [
        {
          event_key: "task-event-31-submitted",
          event_type: "task_submitted",
          level: "info",
          occurred_at: "2026-03-12 10:20:00",
          message: "Simulation task submitted.",
          metadata: {
            task_id: 31,
            lane: "simulation",
          },
        },
        {
          event_key: "task-event-31-running",
          event_type: "task_running",
          level: "info",
          occurred_at: "2026-03-12 10:21:00",
          message: "Simulation is running.",
          metadata: {
            progress_percent_complete: 62,
          },
        },
      ],
      progress: {
        phase: "running",
        percent_complete: 62,
        summary: "point 5/8",
        updated_at: "2026-03-12 10:21:00",
      },
      result_refs: {
        trace_batch_id: 44,
        analysis_run_id: null,
        metadata_records: [
          {
            backend: "sqlite_metadata",
            record_type: "trace_batch",
            record_id: "trace-batch-44",
            version: 1,
            schema_version: "trace-batch/v1",
          },
        ],
        trace_payload: {
          contract_version: "trace-payload/v1",
          backend: "local_zarr",
          payload_role: "task_output",
          store_key: "trace-output-44",
          store_uri: "/data/trace-output-44.zarr",
          group_path: "/",
          array_path: "/s11",
          dtype: "float64",
          shape: [801],
          chunk_shape: [128],
          schema_version: "zarr/v2",
        },
        result_handles: [
          {
            contract_version: "result-handle/v1",
            handle_id: "handle-44",
            kind: "simulation_trace",
            status: "materialized",
            label: "S11",
            metadata_record: {
              backend: "sqlite_metadata",
              record_type: "result_handle",
              record_id: "handle-44",
              version: 1,
              schema_version: "result-handle/v1",
            },
            payload_backend: "local_zarr",
            payload_format: "zarr",
            payload_role: "trace_payload",
            payload_locator: "/data/trace-output-44.zarr",
            provenance_task_id: 31,
            provenance: {
              source_dataset_id: "fluxonium-2025-031",
              source_task_id: 31,
              trace_batch_record: null,
              analysis_run_record: null,
            },
          },
        ],
      },
    });

    expect(detail.resultRefs.traceBatchId).toBe(44);
    expect(detail.resultRefs.resultHandles[0]?.handleId).toBe("handle-44");
    expect(detail.dispatch).toEqual({
      dispatchKey: "dispatch:31:simulation_run_task",
      status: "running",
      submissionSource: "active_dataset",
      acceptedAt: "2026-03-12 10:20:00",
      lastUpdatedAt: "2026-03-12 10:21:00",
    });
    expect(detail.events).toEqual([
      {
        eventKey: "task-event-31-submitted",
        eventType: "task_submitted",
        level: "info",
        occurredAt: "2026-03-12 10:20:00",
        message: "Simulation task submitted.",
        metadata: {
          task_id: 31,
          lane: "simulation",
        },
      },
      {
        eventKey: "task-event-31-running",
        eventType: "task_running",
        level: "info",
        occurredAt: "2026-03-12 10:21:00",
        message: "Simulation is running.",
        metadata: {
          progress_percent_complete: 62,
        },
      },
    ]);
    expect(
      unwrapTaskMutation({
        operation: "submitted",
        task: {
          task_id: 31,
          kind: "simulation",
          lane: "simulation",
          execution_mode: "run",
          status: "running",
          submitted_at: "2026-03-12 10:20:00",
          owner_user_id: "user-dev-01",
          owner_display_name: "Device Lab",
          workspace_id: "workspace-lab",
          workspace_slug: "device-lab",
          visibility_scope: "workspace",
          dataset_id: "fluxonium-2025-031",
          definition_id: 18,
          summary: "Simulation request for FloatingQubitWithXYLine",
          queue_backend: "in_memory_scaffold",
          worker_task_name: "simulation_run_task",
          request_ready: true,
          submitted_from_active_dataset: true,
          dispatch: {
            dispatch_key: "dispatch:31:simulation_run_task",
            status: "running",
            submission_source: "active_dataset",
            accepted_at: "2026-03-12 10:20:00",
            last_updated_at: "2026-03-12 10:21:00",
          },
          events: [
            {
              event_key: "task-event-31-submitted",
              event_type: "task_submitted",
              level: "info",
              occurred_at: "2026-03-12 10:20:00",
              message: "Simulation task submitted.",
              metadata: {
                task_id: 31,
              },
            },
          ],
          progress: {
            phase: "running",
            percent_complete: 62,
            summary: "point 5/8",
            updated_at: "2026-03-12 10:21:00",
          },
          result_refs: {
            trace_batch_id: 44,
            analysis_run_id: null,
            metadata_records: [],
            trace_payload: null,
            result_handles: [],
          },
        },
      }),
    ).toMatchObject({
      taskId: 31,
      dispatch: {
        dispatchKey: "dispatch:31:simulation_run_task",
        status: "running",
        submissionSource: "active_dataset",
      },
    });
  });
});
