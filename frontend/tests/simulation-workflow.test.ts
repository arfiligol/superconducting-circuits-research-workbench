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
  serializeSimulationSetupFormValues,
} from "../src/features/simulation/lib/setup-form";
import {
  JOSEPHSON_EXAMPLE_PREFIX,
  resolveOfficialSimulationExamplePreset,
} from "../src/features/simulation/lib/official-example";
import {
  createSavedSimulationSetupRecord,
  filterSavedSimulationSetupsByDefinition,
  readSavedSimulationSetupRecords,
  removeSavedSimulationSetupRecord,
  replaceSavedSimulationSetupRecord,
  serializeSavedSimulationSetupRecords,
} from "../src/features/simulation/lib/saved-setups";
import {
  mapSimulationResultExplorerResponse,
  mapTaskDetailResponse,
  simulationResultExplorerKey,
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
  resolveAuthoritativeSimulationTaskSummary,
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
const simulationTaskAttachmentHookSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/hooks/use-simulation-task-attachment.ts",
      import.meta.url,
    ),
  ),
  "utf8",
);
const simulationSubmissionHookSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/hooks/use-simulation-submission.ts",
      import.meta.url,
    ),
  ),
  "utf8",
);
const savedSimulationSetupsHookSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/hooks/use-saved-simulation-setups.ts",
      import.meta.url,
    ),
  ),
  "utf8",
);
const simulationResultExplorerHookSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/hooks/use-simulation-result-explorer.ts",
      import.meta.url,
    ),
  ),
  "utf8",
);
const simulationResultExplorerSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/components/simulation-result-explorer.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);
const currentTraceSaveControlSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/simulation/components/current-trace-save-control.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);
const tasksApiSource = readFileSync(
  fileURLToPath(new URL("../src/lib/api/tasks.ts", import.meta.url)),
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

  it("treats persisted task detail as the stage authority when it is newer than the queue row", () => {
    const staleQueueTask = {
      ...tasks[0],
      status: "running",
      resultAvailability: "pending",
    } as const;
    const completedDetail = {
      ...staleQueueTask,
      status: "completed",
      workerTaskName: "simulation_run_task",
      requestReady: true,
      submittedFromActiveDataset: true,
      dispatch: {
        dispatchKey: "dispatch:31:simulation_run_task",
        status: "completed",
        submissionSource: "active_dataset",
        acceptedAt: "2026-03-12 10:20:00",
        lastUpdatedAt: "2026-03-12 10:21:00",
      },
      events: [],
      progress: {
        phase: "completed",
        percentComplete: 100,
        summary: "simulation complete",
        updatedAt: "2026-03-12 10:21:00",
      },
      resultHandoff: {
        availability: "ready",
        primaryResultHandleId: "task-result:31:primary",
        resultHandleCount: 1,
        tracePayloadAvailable: true,
      },
      resultRefs: {
        traceBatchId: 44,
        analysisRunId: null,
        metadataRecords: [],
        tracePayload: null,
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
            provenanceTaskId: 31,
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

    expect(
      resolveAuthoritativeSimulationTaskSummary(staleQueueTask, completedDetail),
    ).toMatchObject({
      taskId: 31,
      status: "completed",
      resultAvailability: "pending",
    });
    expect(hasSimulationTaskResult(completedDetail)).toBe(true);
  });

  it("does not treat pending placeholder refs as a completed result", () => {
    expect(
      hasSimulationTaskResult({
        taskId: 374,
        kind: "simulation",
        lane: "simulation",
        executionMode: "probe",
        status: "completed",
        submittedAt: "2026-03-18 14:43:41",
        ownerUserId: "local-operator",
        ownerDisplayName: "Local Operator",
        workspaceId: "local-space",
        workspaceSlug: "local-space",
        visibilityScope: "local",
        datasetId: "local-dataset-001",
        definitionId: 3,
        summary: "Codex live execution verification",
        hasActionAuthority: true,
        allowedActions: {
          attach: true,
          cancel: false,
          terminate: false,
          retry: false,
        },
        workerTaskName: "simulation_probe_task",
        requestReady: false,
        submittedFromActiveDataset: false,
        dispatch: {
          dispatchKey: "dispatch:374:simulation_probe_task",
          status: "completed",
          submissionSource: "explicit_dataset",
          acceptedAt: "2026-03-18 14:43:41",
          lastUpdatedAt: "2026-03-18 14:43:42",
        },
        events: [],
        progress: {
          phase: "completed",
          percentComplete: 100,
          summary: "Task completed without persisted output.",
          updatedAt: "2026-03-18 14:43:42",
        },
        resultHandoff: {
          availability: "pending",
          primaryResultHandleId: "task-result:374:primary",
          resultHandleCount: 1,
          tracePayloadAvailable: false,
        },
        resultRefs: {
          traceBatchId: null,
          analysisRunId: null,
          metadataRecords: [
            {
              backend: "sqlite_metadata",
              recordType: "result_handle",
              recordId: "result_handle:pending:374",
              version: 1,
              schemaVersion: "sqlite_metadata.v1",
            },
          ],
          tracePayload: null,
          resultHandles: [
            {
              contractVersion: "sc_storage.v1",
              handleId: "task-result:374:primary",
              kind: "simulation_trace",
              status: "pending",
              label: "Pending simulation trace",
              metadataRecord: {
                backend: "sqlite_metadata",
                recordType: "result_handle",
                recordId: "result_handle:pending:374",
                version: 1,
                schemaVersion: "sqlite_metadata.v1",
              },
              payloadBackend: null,
              payloadFormat: null,
              payloadRole: null,
              payloadLocator: null,
              provenanceTaskId: 374,
              provenance: {
                sourceDatasetId: "local-dataset-001",
                sourceTaskId: 374,
                traceBatchRecord: null,
                analysisRunRecord: null,
              },
            },
          ],
        },
      }),
    ).toBe(false);
  });
});

describe("simulation workflow source contract", () => {
  it("exposes official example presets only for compatible josephson example definitions", () => {
    const jpaPreset = resolveOfficialSimulationExamplePreset(
      `${JOSEPHSON_EXAMPLE_PREFIX}Josephson Parametric Amplifier (JPA)`,
    );

    expect(jpaPreset).toMatchObject({
      name: "Official Example",
      exampleName: "Josephson Parametric Amplifier (JPA)",
    });
    expect(jpaPreset?.values).toMatchObject({
      simulationStartGhz: 4.5,
      simulationStopGhz: 5,
      simulationPointCount: 501,
      simulationHarmonicCount: 8,
      simulationOversampleFactor: 16,
      simulationPtcEnabled: false,
    });
    expect(jpaPreset?.values.simulationSources).toHaveLength(1);
    expect(jpaPreset?.values.simulationSources[0]).toMatchObject({
      port: "port_1",
      pumpFreqGhz: 4.75001,
      sourceMode: "1",
    });
    expect(resolveOfficialSimulationExamplePreset("FloatingQubitWithXYLine")).toBeNull();
  });

  it("serializes task-backed setup snapshots stably for anti-thrash resets", () => {
    const baseline = cloneSimulationSetupFormValues(defaultSimulationSetupFormValues);
    const baselineClone = cloneSimulationSetupFormValues(defaultSimulationSetupFormValues);
    const changed = cloneSimulationSetupFormValues({
      ...defaultSimulationSetupFormValues,
      simulationStartGhz: defaultSimulationSetupFormValues.simulationStartGhz + 0.5,
    });

    expect(serializeSimulationSetupFormValues(baseline)).toBe(
      serializeSimulationSetupFormValues(baselineClone),
    );
    expect(serializeSimulationSetupFormValues(baseline)).not.toBe(
      serializeSimulationSetupFormValues(changed),
    );
  });

  it("ignores disabled parameter sweep axis noise when serializing setup snapshots", () => {
    const baseline = cloneSimulationSetupFormValues(defaultSimulationSetupFormValues);
    const normalizedAxisNoise = cloneSimulationSetupFormValues({
      ...defaultSimulationSetupFormValues,
      simulationParameterSweepEnabled: false,
      simulationParameterSweepAxes: [
        {
          ...defaultSimulationSetupFormValues.simulationParameterSweepAxes[0],
          parameter: "source:port_1:current_amp",
          unit: "A",
        },
      ],
    });

    expect(serializeSimulationSetupFormValues(normalizedAxisNoise)).toBe(
      serializeSimulationSetupFormValues(baseline),
    );
  });

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
        ptc: {
          enabled: true,
          mode: "manual",
          compensatePorts: ["port_1", "port_2"],
        },
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
    expect(rehydrated.simulationPtcCompensatePorts).toBe("port_1, port_2");
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
    expect(simulationWorkbenchSource).toContain("const FREQUENCY_WHEEL_STEP_GHZ = 0.001");
    expect(simulationWorkbenchSource).toContain("step={String(FREQUENCY_WHEEL_STEP_GHZ)}");
    expect(simulationWorkbenchSource).toContain("Schema unit ·");
    expect(simulationWorkbenchSource).toContain("Add Axis");
    expect(simulationWorkbenchSource).toContain("Add Source");
    expect(simulationWorkbenchSource).toContain("Persisted on task");
    expect(simulationWorkbenchSource).toContain(
      "PTC is submitted with the simulation setup and restored from persisted task detail.",
    );
    expect(simulationWorkbenchSource).toContain("Source Current Ip (A)");
    expect(simulationWorkbenchSource).toContain("Source Mode");
    expect(simulationWorkbenchSource).toContain("Pump Source");
    expect(simulationWorkbenchSource).toContain("Run Simulation");
    expect(simulationWorkbenchSource).toContain("Run Post Processing");
    expect(simulationWorkbenchSource).toContain("Add Step");
    expect(simulationWorkbenchSource).toContain("Step Type");
    expect(simulationWorkbenchSource).toContain("updatePostProcessingStepType");
    expect(simulationWorkbenchSource).toContain("useSimulationSubmission");
    expect(simulationWorkbenchSource).toContain("useSimulationTaskAttachment");
    expect(simulationWorkbenchSource).toContain("useSavedSimulationSetups");
    expect(simulationWorkbenchSource).toContain("Load Official Example");
    expect(savedSimulationSetupsHookSource).toContain("Task-backed · #");
    expect(savedSimulationSetupsHookSource).toContain("Edited from task #");
    expect(savedSimulationSetupsHookSource).toContain("Official Example");
    expect(savedSimulationSetupsHookSource).toContain(
      "Browser-saved convenience draft for this definition.",
    );
    expect(simulationWorkbenchSource).toContain("Manage");
    expect(simulationWorkbenchSource).toContain("Save");
    expect(simulationWorkbenchSource).toContain('role="switch"');
    expect(simulationWorkbenchSource).toContain("AppNumberInput");
    expect(simulationWorkbenchSource).toContain("<AppNumberInput");
    expect(simulationWorkbenchSource).not.toContain("function SetupNumberInput");
    expect(simulationWorkbenchSource).not.toContain('type="checkbox"');
    expect(simulationSubmissionHookSource).toContain("buildSimulationSetupDraft");
    expect(savedSimulationSetupsHookSource).toContain(
      "buildSimulationSetupFormValuesFromPersistedSetup",
    );
    expect(simulationSubmissionHookSource).toContain("buildPostProcessingSetupDraft");
    expect(simulationWorkbenchSource).toContain('label="Expanded Netlist"');
    expect(simulationWorkbenchSource).not.toContain('detail="Read-only expanded netlist."');
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
    expect(simulationWorkbenchSource).not.toContain("Definition Binding");
    expect(simulationWorkbenchSource).not.toContain("Submit Authority");
    expect(simulationWorkbenchSource).not.toContain("Downstream Contract");
    expect(simulationWorkbenchSource).not.toContain("Operation Config JSON");
    expect(simulationWorkbenchSource).not.toContain("Operation Name");
    expect(simulationWorkbenchSource).not.toContain("Selection Design Id");
    expect(simulationWorkbenchSource).not.toContain("Submission Preview");
    expect(simulationWorkbenchSource).not.toContain("Dataset not attached");
    expect(simulationWorkbenchSource).not.toContain("Sweep Parameter (optional)");
    expect(simulationWorkbenchSource).not.toContain("Phase (deg)");
    expect(simulationWorkbenchSource).not.toContain("Browser-local only");
    expect(simulationWorkbenchSource).not.toContain("not submitted with the task");
    expect(simulationWorkbenchSource).toContain("deriveSimulationSweepTargetOptions");
    expect(simulationWorkbenchSource).toContain("deriveSimulationPtcPortOptions");
    expect(simulationWorkbenchSource).toContain("No sweep targets are currently available");
    expect(simulationWorkbenchSource).toContain("SimulationResultExplorer");
    expect(simulationWorkbenchSource).toContain("task={latestPostProcessingTaskDetail}");
    expect(simulationWorkbenchSource).toContain("Live result refresh");
    expect(simulationWorkbenchSource).toContain("Attach Run");
    expect(simulationWorkbenchSource).toContain("Attached to Page");
    expect(simulationWorkbenchSource).toContain("useAppToasts");
    expect(simulationWorkbenchSource).toContain('"Run submission failed"');
    expect(simulationWorkbenchSource).toContain("pushToast({");
    expect(simulationWorkbenchSource).not.toContain("Simulation Setup · ${simulationSetupState.label}");
    expect(simulationWorkbenchSource).toContain("Author the processing steps, keep their order intentional");
    expect(simulationWorkbenchSource).toContain("switch between available result sources");
    expect(simulationWorkbenchSource).not.toContain("Choose Raw or PTC");
    expect(simulationWorkbenchSource).not.toContain("postSourceSelection");
    expect(simulationWorkbenchSource).not.toContain("PTC source");
    expect(simulationWorkbenchSource).not.toContain("Trace Family");
    expect(simulationWorkbenchSource).not.toContain("Trace IDs");
    expect(simulationWorkbenchSource).not.toContain("View Task");
    expect(simulationWorkbenchSource).not.toContain("Result Availability");
    expect(simulationWorkbenchSource).not.toContain("Downstream State");
    expect(simulationResultExplorerSource).toContain("Simulation Result Explorer");
    expect(simulationResultExplorerSource).toContain("Post Processing Result Explorer");
    expect(simulationResultExplorerSource).toContain("Parameter Sweep Point");
    expect(simulationResultExplorerHookSource).toContain("setSweepValue(axisIndex: number, nextValueIndex: number)");
    expect(simulationResultExplorerSource).toContain(
      'task.kind === "post_processing" && sourceOptions.length <= 1',
    );
    expect(simulationResultExplorerSource).toContain("AppSegmentedControl");
    expect(simulationResultExplorerSource).toContain('ariaLabel="Simulation result family"');
    expect(simulationResultExplorerSource).toContain("Simulation result source");
    expect(simulationResultExplorerSource).toContain("Simulation result metric");
    expect(simulationResultExplorerSource).toContain("Simulation result output port");
    expect(simulationResultExplorerSource).toContain("PTC results appear when you switch to");
    expect(simulationResultExplorerSource).toContain("Z0 only applies to Y/Z derived explorer families.");
    expect(simulationResultExplorerSource).toContain("CurrentTraceSaveControl");
    expect(simulationWorkbenchSource).not.toContain("SimulationResultPublicationCard");
    expect(currentTraceSaveControlSource).toContain("Save Current Trace");
    expect(currentTraceSaveControlSource).toContain("Parameter");
    expect(currentTraceSaveControlSource).toContain("New Design");
    expect(currentTraceSaveControlSource).toContain("Open Saved Trace in Raw Data");
    expect(currentTraceSaveControlSource).toContain("createDatasetDesign");
    expect(currentTraceSaveControlSource).toContain("publishSimulationResultTrace");
    expect(currentTraceSaveControlSource).toContain("traceKey");
    expect(currentTraceSaveControlSource).toContain("parameterName");
    expect(tasksApiSource).toContain("/result-traces/publish");
    expect(tasksApiSource).toContain("parameter_name: payload.parameterName ?? undefined");
    expect(tasksApiSource).toContain("compare_axis_index");
    expect(currentTraceSaveControlSource).toContain("dataset_design_conflict");
    expect(currentTraceSaveControlSource).toContain("design_not_found");
    expect(currentTraceSaveControlSource).not.toContain("Active Dataset");
    expect(currentTraceSaveControlSource).not.toContain("Save to Dataset");
    expect(currentTraceSaveControlSource).not.toContain("Target Dataset");
  });

  it("binds stage authority to the current definition and dataset context", () => {
    expect(simulationWorkflowHookSource).toContain("resolveLatestSimulationTaskInContext(");
    expect(simulationWorkflowHookSource).toContain("resolveLatestSimulationStageTaskInContext(");
    expect(simulationWorkflowHookSource).toContain("const pageContext = {");
    expect(simulationWorkbenchSource).toContain("resolveAuthoritativeSimulationTaskSummary");
    expect(simulationWorkbenchSource).toContain(
      "const displayedSimulationStageTask =",
    );
    expect(simulationWorkbenchSource).toContain(
      "const displayedSimulationTaskDetail =",
    );
    expect(simulationWorkbenchSource).toContain("displayedSimulationStageAuthority");
    expect(savedSimulationSetupsHookSource).toContain("Sync Last Task Setup");
    expect(savedSimulationSetupsHookSource).toContain("resetForWorkflowContext");
    expect(savedSimulationSetupsHookSource).toContain("openSaveAsNewFromManage");
    expect(simulationSubmissionHookSource).toContain("task_enqueue_failed");
    expect(simulationSubmissionHookSource).toContain("onTaskAttached(task.taskId);");
    expect(simulationSubmissionHookSource).toContain("await Promise.all([");
    expect(simulationWorkbenchSource).toContain("latestPostProcessingStageAuthority");
    expect(simulationWorkbenchSource).toContain("Persisted result handoff:");
    expect(simulationWorkbenchSource).toContain("const workflowContextResetKey =");
    expect(savedSimulationSetupsHookSource).toContain(
      "form.reset(defaultRequestValues, { keepDefaultValues: true });",
    );
    expect(savedSimulationSetupsHookSource).toContain('setSimulationSetupSource({ kind: "default" });');
    expect(simulationWorkbenchSource).toContain("setPostProcessingSteps([]);");
    expect(simulationWorkbenchSource).not.toContain("summarizeTaskContextBinding");
    expect(simulationWorkbenchSource).not.toContain("taskContextBinding?.hasMismatch");
    expect(simulationSubmissionHookSource).toContain("simulation_setup: simulationSetup ?? null");
    expect(simulationSubmissionHookSource).toContain(
      "post_processing_setup: postProcessingSetup ?? null",
    );
    expect(simulationWorkflowHookSource).toContain("attachedContextTask");
    expect(simulationWorkflowHookSource).toContain("attachedSimulationTaskDetail");
    expect(simulationWorkflowHookSource).toContain("upstreamSimulationStageTask");
    expect(simulationSubmissionHookSource).toContain("const verifySelectedDefinition");
    expect(simulationSubmissionHookSource).toContain("await listCircuitDefinitions()");
    expect(simulationSubmissionHookSource).toContain(
      "await getCircuitDefinition(nextDefinitionId)",
    );
    expect(simulationWorkflowHookSource).not.toContain("keepPreviousData: true");
    expect(simulationWorkflowHookSource).toContain("shouldRefreshTaskDetail");
    expect(simulationWorkflowHookSource).toContain('task.status === "completed" && !hasSimulationTaskResult(task)');
    expect(simulationResultExplorerHookSource).toContain("simulationResultExplorerKey");
    expect(simulationResultExplorerHookSource).toContain("getSimulationResultExplorer");
    expect(simulationResultExplorerHookSource).toContain("setFamily(nextFamily: string)");
    expect(simulationResultExplorerHookSource).toContain("setZ0(nextZ0: number)");
    expect(simulationTaskAttachmentHookSource).toContain("simulation:attached-task:");
    expect(simulationTaskAttachmentHookSource).toContain("autoRestoredTaskIdRef");
    expect(simulationTaskAttachmentHookSource).toContain(
      "readStoredAttachedTaskId(attachedTaskStorageKey)",
    );
    expect(simulationTaskAttachmentHookSource).toContain(
      "window.sessionStorage.setItem(attachedTaskStorageKey",
    );
  });

  it("keeps saved setup overwrite and create-new paths explicitly separated", () => {
    expect(savedSimulationSetupsHookSource).toContain(
      'type SavedSetupSaveDialogMode = "new-only" | "choose";',
    );
    expect(savedSimulationSetupsHookSource).toContain(
      'type SavedSetupSaveAction = "create" | "overwrite";',
    );
    expect(savedSimulationSetupsHookSource).toContain('setSaveDialogMode("choose");');
    expect(savedSimulationSetupsHookSource).toContain(
      "setSaveDialogOverwriteTargetId(activeSavedSetup.id);",
    );
    expect(savedSimulationSetupsHookSource).toContain('setSaveDialogMode("new-only");');
    expect(savedSimulationSetupsHookSource).toContain("const submitSaveDialog = useCallback(");
    expect(savedSimulationSetupsHookSource).toContain(
      'action === "overwrite" ? saveDialogOverwriteTargetId : null',
    );
    expect(simulationWorkbenchSource).toContain('submitSaveDialog("create");');
    expect(simulationWorkbenchSource).toContain('submitSaveDialog("overwrite");');
    expect(simulationWorkbenchSource).toContain("Save Current as New");
    expect(simulationWorkbenchSource).toContain("Overwrite Current");
    expect(simulationWorkbenchSource).toContain("Save as New");
    expect(simulationWorkbenchSource).not.toContain(
      "persistSavedSetup(saveSetupNameDraft, activeSavedSetup?.id ?? null);",
    );
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
      worker_task_name: "simulation_run_task",
      request_ready: true,
      submitted_from_active_dataset: true,
      simulation_setup: {
        frequency_sweep: {
          start_ghz: 4,
          stop_ghz: 8,
          point_count: 801,
          spacing: "linear",
        },
        parameter_sweeps: [],
        solver: {
          solver_family: "harmonic_balance",
          max_iterations: 120,
          convergence_tolerance: 1e-7,
          harmonic_balance: {
            enabled: true,
            harmonic_count: 5,
            oversample_factor: 3,
          },
        },
        sources: [
          {
            source_id: "src_drive_1",
            kind: "pump",
            target: "port_1",
            amplitude: 0.9,
            frequency_ghz: 5.1,
            phase_deg: null,
          },
        ],
        ptc: {
          enabled: true,
          mode: "manual",
          compensate_ports: ["port_1", "port_2"],
        },
      },
      publication_summary: {
        state: "published",
        publish_allowed: false,
        publication_key: "simulation-publication:31:fluxonium-2025-031:design_fluxonium-save",
        target_dataset_id: "fluxonium-2025-031",
        target_design_id: "design_fluxonium-save",
        target_design_name: "Fluxonium Save",
        published_trace_ids: ["trace_31_s11_raw", "trace_31_y11_ptc"],
        published_at: "2026-03-19T12:32:00Z",
        source_task_id: 31,
        source_result_handle_ids: ["handle-44"],
      },
      downstream_source_capabilities: {
        raw: {
          available: true,
          enabled: true,
          mode: null,
          compensate_ports: [],
        },
        ptc: {
          available: true,
          enabled: true,
          mode: "manual",
          compensate_ports: ["port_1", "port_2"],
        },
      },
      dispatch: {
        dispatch_key: "dispatch:31:simulation_run_task",
        status: "running",
        submission_source: "active_dataset",
        accepted_at: "2026-03-12 10:20:00",
        last_updated_at: "2026-03-12 10:21:00",
        queue_name: "simulation",
        enqueued_at: "2026-03-12 10:20:01",
        runtime_job_id: "job-31",
        dispatch_attempt_count: 1,
        last_dispatch_outcome: "claimed",
        last_dispatch_error_code: null,
      },
      reconcile: {
        required: false,
        reason: null,
        recorded_at: null,
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
      result_handoff: {
        availability: "pending",
        primary_result_handle_id: null,
        result_handle_count: 1,
        trace_payload_available: true,
      },
    });

    expect(detail.resultRefs.traceBatchId).toBe(44);
    expect(detail.resultRefs.resultHandles[0]?.handleId).toBe("handle-44");
    expect(detail.publicationSummary).toEqual({
      state: "published",
      publishAllowed: false,
      publicationKey: "simulation-publication:31:fluxonium-2025-031:design_fluxonium-save",
      targetDatasetId: "fluxonium-2025-031",
      targetDesignId: "design_fluxonium-save",
      targetDesignName: "Fluxonium Save",
      publishedTraceIds: ["trace_31_s11_raw", "trace_31_y11_ptc"],
      publishedAt: "2026-03-19T12:32:00Z",
      sourceTaskId: 31,
      sourceResultHandleIds: ["handle-44"],
    });
    expect(detail.simulationSetup?.ptc).toEqual({
      enabled: true,
      mode: "manual",
      compensatePorts: ["port_1", "port_2"],
    });
    expect(detail.downstreamSourceCapabilities).toEqual({
      raw: {
        available: true,
        enabled: true,
        mode: null,
        compensatePorts: [],
      },
      ptc: {
        available: true,
        enabled: true,
        mode: "manual",
        compensatePorts: ["port_1", "port_2"],
      },
    });
    expect(detail.dispatch).toEqual({
      dispatchKey: "dispatch:31:simulation_run_task",
      status: "running",
      submissionSource: "active_dataset",
      acceptedAt: "2026-03-12 10:20:00",
      lastUpdatedAt: "2026-03-12 10:21:00",
      queueName: "simulation",
      enqueuedAt: "2026-03-12 10:20:01",
      runtimeJobId: "job-31",
      dispatchAttemptCount: 1,
      lastDispatchOutcome: "claimed",
      lastDispatchErrorCode: null,
    });
    expect(detail.resultHandoff).toEqual({
      availability: "pending",
      primaryResultHandleId: null,
      resultHandleCount: 1,
      tracePayloadAvailable: true,
    });
    expect(detail.reconcile).toEqual({
      required: false,
      reason: null,
      recordedAt: null,
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
          worker_task_name: "simulation_run_task",
          request_ready: true,
          submitted_from_active_dataset: true,
          dispatch: {
            dispatch_key: "dispatch:31:simulation_run_task",
            status: "running",
            submission_source: "active_dataset",
            accepted_at: "2026-03-12 10:20:00",
            last_updated_at: "2026-03-12 10:21:00",
            queue_name: "simulation",
            enqueued_at: "2026-03-12 10:20:01",
            runtime_job_id: "job-31",
            dispatch_attempt_count: 1,
            last_dispatch_outcome: "claimed",
            last_dispatch_error_code: null,
          },
          reconcile: {
            required: false,
            reason: null,
            recorded_at: null,
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
          result_handoff: {
            availability: "pending",
            primary_result_handle_id: null,
            result_handle_count: 0,
            trace_payload_available: false,
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

  it("maps simulation result explorer payloads and explorer keys", () => {
    expect(simulationResultExplorerKey(31)).toBe(
      "/api/backend/tasks/31/simulation-results/explorer",
    );
    expect(
      simulationResultExplorerKey(31, {
        family: "z_matrix",
        source: "ptc",
        metric: "real",
        sweepIndex: 3,
        z0: 75,
        outputPort: 2,
        inputPort: 1,
      }),
    ).toBe(
      "/api/backend/tasks/31/simulation-results/explorer?family=z_matrix&source=ptc&metric=real&sweep_index=3&z0=75&output_port=2&input_port=1",
    );

    const explorer = mapSimulationResultExplorerResponse({
      task_id: 31,
      task_status: "completed",
      runtime_mode: "local",
      bootstrap: {
        families: [
          {
            key: "s_matrix",
            label: "S Matrix",
            available_sources: [{ key: "raw", label: "Raw" }],
            available_metrics: [
              { key: "magnitude_db", label: "Magnitude (dB)", unit: "dB" },
            ],
          },
          {
            key: "z_matrix",
            label: "Z Matrix",
            available_sources: [
              { key: "raw", label: "Raw" },
              { key: "ptc", label: "PTC" },
            ],
            available_metrics: [{ key: "real", label: "Real", unit: "ohm" }],
          },
        ],
        trace_selector: {
          output_ports: [
            { port: 1, label: "port_1" },
            { port: 2, label: "port_2" },
          ],
          input_ports: [
            { port: 1, label: "port_1" },
            { port: 2, label: "port_2" },
          ],
          output_modes: [{ key: "mode_0", label: "Mode 0" }],
          input_modes: [{ key: "mode_0", label: "Mode 0" }],
        },
        parameter_sweep: {
          active: true,
          point_count: 6,
          axes: [
            {
              parameter: "L_jun",
              label: "L_jun",
              unit: "nH",
              values: [22, 24, 26],
              selected_value_index: 1,
            },
            {
              parameter: "C_q",
              label: "C_q",
              unit: "pF",
              values: [0.05, 0.06],
              selected_value_index: 0,
            },
          ],
        },
        default_selection: {
          family: "s_matrix",
          source: "raw",
          metric: "magnitude_db",
          sweep_index: 2,
          trace_key: "raw:s_matrix:1:1",
          z0_ohm: 50,
          output_port: 1,
          input_port: 1,
        },
      },
      selection: {
        family: "z_matrix",
        source: "ptc",
        metric: "real",
        sweep_index: 3,
        trace_key: "ptc:z_matrix:2:1",
        z0_ohm: 75,
        output_port: 2,
        input_port: 1,
        output_port_label: "port_2",
        input_port_label: "port_1",
        output_mode: "mode_0",
        input_mode: "mode_0",
      },
      plot: {
        x_axis: {
          label: "Frequency",
          unit: "GHz",
          values: [1, 2, 3],
        },
        y_axis: {
          label: "Real",
          unit: "ohm",
        },
        series: [
          {
            series_id: "z_matrix:ptc:real:2:1",
            label: "PTC Z21 Real",
            values: [0.1, 0.2, 0.3],
            unit: "ohm",
          },
        ],
        metadata: {
          family: "z_matrix",
          source: "ptc",
          metric: "real",
          sweep_index: 3,
          trace_key: "ptc:z_matrix:2:1",
          z0_ohm: 75,
          output_port: 2,
          input_port: 1,
          output_port_label: "port_2",
          input_port_label: "port_1",
          trace_payload_store_key: "trace-output-44",
        },
      },
      result_basis: {
        trace_payload_available: true,
        primary_result_handle_id: "handle-44",
        trace_batch_id: 44,
      },
    });

    expect(explorer.selection).toEqual({
      family: "z_matrix",
      source: "ptc",
      metric: "real",
      sweepIndex: 3,
      compareAxisIndex: null,
      traceKey: "ptc:z_matrix:2:1",
      z0Ohm: 75,
      outputPort: 2,
      inputPort: 1,
      outputPortLabel: "Port 2",
      inputPortLabel: "Port 1",
      outputMode: "mode_0",
      inputMode: "mode_0",
    });
    expect(explorer.bootstrap.traceSelector.outputPorts).toEqual([
      { port: 1, label: "Port 1" },
      { port: 2, label: "Port 2" },
    ]);
    expect(explorer.bootstrap.families[1]?.availableSources.map((source) => source.key)).toEqual([
      "raw",
      "ptc",
    ]);
    expect(explorer.bootstrap.defaultSelection.traceKey).toBe("raw:s_matrix:1:1");
    expect(explorer.bootstrap.defaultSelection.sweepIndex).toBe(2);
    expect(explorer.bootstrap.parameterSweep.pointCount).toBe(6);
    expect(explorer.bootstrap.parameterSweep.compareAxisIndex).toBeNull();
    expect(explorer.bootstrap.parameterSweep.axes[0]?.selectedValueIndex).toBe(1);
    expect(explorer.plot.metadata.outputPortLabel).toBe("Port 2");
    expect(explorer.plot.metadata.inputPortLabel).toBe("Port 1");
    expect(explorer.plot.metadata.sweepIndex).toBe(3);
    expect(explorer.plot.metadata.compareAxisIndex).toBeNull();
    expect(explorer.plot.metadata.traceKey).toBe("ptc:z_matrix:2:1");
    expect(explorer.plot.metadata.tracePayloadStoreKey).toBe("trace-output-44");
    expect(explorer.resultBasis.primaryResultHandleId).toBe("handle-44");
  });
});
