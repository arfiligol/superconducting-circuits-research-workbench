import { describe, expect, it } from "vitest";

import {
  groupTaskResultHandles,
  resolveTaskConnectionState,
  resolveTaskRecoveryNotice,
  summarizeTaskActionGates,
  summarizeTaskLifecycle,
  summarizeTaskResultHandoff,
  summarizeTaskResultSurface,
} from "../src/lib/task-surface";

describe("shared task surface helpers", () => {
  const task = {
    taskId: 41,
    kind: "characterization",
    lane: "characterization",
    executionMode: "run",
    status: "running",
    submittedAt: "2026-03-13 09:20:00",
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
    workerTaskName: "characterization_run_task",
    requestReady: true,
    submittedFromActiveDataset: true,
    dispatch: {
      dispatchKey: "dispatch:41:characterization_run_task",
      status: "running",
      submissionSource: "active_dataset",
      acceptedAt: "2026-03-13 09:20:00",
      lastUpdatedAt: "2026-03-13 09:21:00",
      queueName: "characterization",
      enqueuedAt: "2026-03-13 09:20:01",
      runtimeJobId: "job-41",
      dispatchAttemptCount: 1,
      lastDispatchOutcome: "claimed",
      lastDispatchErrorCode: null,
    },
    reconcile: {
      required: false,
      reason: null,
      recordedAt: null,
    },
    events: [],
    progress: {
      phase: "running",
      percentComplete: 58,
      summary: "Fitting admittance curves",
      updatedAt: "2026-03-13 09:21:00",
    },
    resultRefs: {
      traceBatchId: 44,
      analysisRunId: 12,
      metadataRecords: [
        {
          backend: "sqlite_metadata",
          recordType: "analysis_run",
          recordId: "analysis-run-12",
          version: 1,
          schemaVersion: "analysis-run/v1",
        },
      ],
      tracePayload: {
        contractVersion: "trace-payload/v1",
        backend: "local_zarr",
        payloadRole: "analysis_projection",
        storeKey: "characterization-41",
        storeUri: "/data/characterization-41.zarr",
        groupPath: "/fits",
        arrayPath: "/quality_factor",
        dtype: "float64",
        shape: [128],
        chunkShape: [32],
        schemaVersion: "zarr/v2",
      },
      resultHandles: [
        {
          contractVersion: "result-handle/v1",
          handleId: "handle-fit-41",
          kind: "fit_summary",
          status: "materialized",
          label: "Quality factor fit",
          metadataRecord: {
            backend: "sqlite_metadata",
            recordType: "result_handle",
            recordId: "handle-fit-41",
            version: 1,
            schemaVersion: "result-handle/v1",
          },
          payloadBackend: "json_artifact",
          payloadFormat: "json",
          payloadRole: "report_artifact",
          payloadLocator: "/artifacts/fit-41.json",
          provenanceTaskId: 41,
          provenance: {
            sourceDatasetId: "fluxonium-2025-031",
            sourceTaskId: 41,
            traceBatchRecord: null,
            analysisRunRecord: null,
          },
        },
        {
          contractVersion: "result-handle/v1",
          handleId: "handle-report-41",
          kind: "characterization_report",
          status: "pending",
          label: "Research summary",
          metadataRecord: {
            backend: "sqlite_metadata",
            recordType: "result_handle",
            recordId: "handle-report-41",
            version: 1,
            schemaVersion: "result-handle/v1",
          },
          payloadBackend: "markdown_artifact",
          payloadFormat: "markdown",
          payloadRole: "report_artifact",
          payloadLocator: null,
          provenanceTaskId: 41,
          provenance: {
            sourceDatasetId: "fluxonium-2025-031",
            sourceTaskId: 41,
            traceBatchRecord: null,
            analysisRunRecord: null,
          },
        },
      ],
    },
    resultHandoff: {
      availability: "pending",
      primaryResultHandleId: "handle-fit-41",
      resultHandleCount: 2,
      tracePayloadAvailable: true,
    },
  } as const;

  it("resolves connection state for explicit and follow-latest attachments", () => {
    expect(
      resolveTaskConnectionState({
        requestedTaskId: 37,
        resolvedTaskId: 37,
        latestTaskId: 41,
        activeTask: task,
      }),
    ).toEqual({
      mode: "explicit",
      latestTaskId: 41,
      selectedTaskId: 37,
      attachedTaskId: 41,
      hasNewerLatestTask: true,
      isFollowingLatest: false,
      isAttached: false,
      isStaleSnapshot: true,
    });

    expect(
      resolveTaskConnectionState({
        requestedTaskId: null,
        resolvedTaskId: 41,
        latestTaskId: 41,
        activeTask: task,
      }).isFollowingLatest,
    ).toBe(true);
  });

  it("builds generic recovery notices and lifecycle summaries", () => {
    expect(resolveTaskRecoveryNotice(33, 41, new Error("not found"))).toEqual({
      tone: "warning",
      title: "Task reattach available",
      message: "Task #33 could not be attached. A newer task #41 is available instead.",
    });

    expect(summarizeTaskLifecycle(task)).toEqual({
      stage: "running",
      statusLabel: "Running",
      tone: "primary",
      summary:
        "Worker runtime is still active. Keep the attached task detail refreshed until the backend settles the request.",
      progressPercent: 58,
      progressSummary: "Fitting admittance curves",
      backendStatusLabel: "running",
      workerTaskName: "characterization_run_task",
      submissionSourceLabel: "Active dataset session",
      acceptedAt: "2026-03-13 09:20:00",
      lastUpdatedAt: "2026-03-13 09:21:00",
      taskDatasetId: "fluxonium-2025-031",
      dispatchKey: "dispatch:41:characterization_run_task",
      requestReady: true,
      submittedFromActiveDataset: true,
      executionMode: "run",
      visibilityScope: "workspace",
      reconcileRequired: false,
      reconcileReason: null,
      reconcileRecordedAt: null,
    });
  });

  it("summarizes and groups persisted result handles", () => {
    expect(summarizeTaskResultSurface(task)).toEqual({
      metadataRecordCount: 1,
      resultHandleCount: 2,
      materializedHandleCount: 1,
      pendingHandleCount: 1,
      hasTracePayload: true,
      traceBatchId: 44,
      analysisRunId: 12,
      handleKindCounts: [
        { kind: "characterization_report", count: 1 },
        { kind: "fit_summary", count: 1 },
      ],
    });

    expect(groupTaskResultHandles(task)).toEqual({
      materialized: [task.resultRefs.resultHandles[0]],
      pending: [task.resultRefs.resultHandles[1]],
    });
  });

  it("treats an unattached task as having no trace payload", () => {
    expect(summarizeTaskResultSurface(undefined).hasTracePayload).toBe(false);
  });

  it("summarizes backend-gated task actions and result handoff", () => {
    const completedTask = {
      ...task,
      status: "completed" as const,
      dispatch: {
        ...task.dispatch,
        status: "completed" as const,
      },
      progress: {
        ...task.progress,
        phase: "completed" as const,
        percentComplete: 100,
        summary: "Characterization complete",
      },
      resultHandoff: {
        availability: "ready" as const,
        primaryResultHandleId: "handle-fit-41",
        resultHandleCount: 2,
        tracePayloadAvailable: true,
      },
    };

    expect(summarizeTaskActionGates(task)).toEqual({
      hasActionAuthority: true,
      attach: {
        action: "attach",
        enabled: true,
        reason: "Allowed by the backend task contract.",
      },
      cancel: {
        action: "cancel",
        enabled: true,
        reason: "Allowed by the backend task contract.",
      },
      terminate: {
        action: "terminate",
        enabled: false,
        reason: "Blocked by backend allowed_actions for the current session.",
      },
      retry: {
        action: "retry",
        enabled: false,
        reason: "Blocked by backend allowed_actions for the current session.",
      },
    });

    expect(
      summarizeTaskResultHandoff(completedTask, summarizeTaskResultSurface(completedTask)),
    ).toEqual({
      tone: "success",
      title: "Persisted result ready",
      message:
        "The backend has marked the persisted result handoff ready. Result surfaces should use this as the readiness authority.",
      isReady: true,
    });
  });

  it("anchors lifecycle state on task status and handoff availability instead of dispatch fallbacks", () => {
    const mismatchTask = {
      ...task,
      status: "cancelled" as const,
      dispatch: {
        ...task.dispatch,
        status: "running" as const,
      },
      resultHandoff: {
        availability: "none" as const,
        primaryResultHandleId: null,
        resultHandleCount: 0,
        tracePayloadAvailable: false,
      },
    };

    expect(summarizeTaskLifecycle(mismatchTask)).toMatchObject({
      stage: "cancelled",
      statusLabel: "Cancelled",
      tone: "warning",
    });

    expect(
      summarizeTaskResultHandoff(mismatchTask, summarizeTaskResultSurface(mismatchTask)),
    ).toEqual({
      tone: "warning",
      title: "No persisted result handoff",
      message:
        "The backend reports no persisted result handoff for this task yet. Treat the attached task detail as the only authority.",
      isReady: false,
    });
  });
});
