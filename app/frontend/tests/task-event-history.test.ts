import { describe, expect, it } from "vitest";

import {
  buildTaskEventHistoryEntries,
  summarizeTaskEventHistory,
} from "../src/lib/task-event-history";

const SIMULATION_SCHEMA_ID = "7f3a2c91-1d7f-4a55-9cfd-0f0b7d5c1001";

describe("task event history helpers", () => {
  const task = {
    taskId: 58,
    kind: "simulation",
    lane: "simulation",
    executionMode: "run",
    status: "running",
    submittedAt: "2026-03-13 08:00:00",
    ownerUserId: "user-dev-01",
    ownerDisplayName: "Device Lab",
    workspaceId: "workspace-lab",
    workspaceSlug: "device-lab",
    visibilityScope: "workspace",
    datasetId: "fluxonium-2025-031",
    definitionId: SIMULATION_SCHEMA_ID,
    summary: "Simulation request for Fluxonium sweep 031",
    hasActionAuthority: true,
    allowedActions: {
      attach: true,
      cancel: false,
      terminate: false,
      retry: false,
    },
    workerTaskName: "simulation_run_task",
    requestReady: true,
    submittedFromActiveDataset: true,
    dispatch: {
      dispatchKey: "dispatch:58:simulation_run_task",
      status: "running",
      submissionSource: "active_dataset",
      acceptedAt: "2026-03-13 08:00:00",
      lastUpdatedAt: "2026-03-13 08:04:00",
      queueName: "simulation",
      enqueuedAt: "2026-03-13 08:00:01",
      runtimeJobId: "job-58",
      dispatchAttemptCount: 2,
      lastDispatchOutcome: "requeued",
      lastDispatchErrorCode: "queue_job_missing",
    },
    events: [
      {
        eventKey: "task-event-58-requeued",
        eventType: "task_requeued",
        level: "warning",
        occurredAt: "2026-03-13 08:08:00",
        message: "Task was requeued after the worker job went missing.",
        metadata: {
          reconcile_reason: "queue_job_missing",
          dispatch_attempt_count: 2,
        },
      },
      {
        eventKey: "task-event-58-completed",
        eventType: "task_completed",
        level: "warning",
        occurredAt: "2026-03-13 08:07:00",
        message: "Worker completed with follow-up review flags.",
        metadata: {
          task_id: 58,
          pending_checks: ["plot_bundle", "fit_summary"],
        },
      },
      {
        eventKey: "task-event-58-running",
        eventType: "task_running",
        level: "info",
        occurredAt: "2026-03-13 08:04:00",
        message: "The solver entered the running state.",
        metadata: {
          progress_percent_complete: 64,
          retryable: false,
        },
      },
      {
        eventKey: "task-event-58-submitted",
        eventType: "task_submitted",
        level: "info",
        occurredAt: "2026-03-13 08:00:00",
        message: "Task accepted by the backend queue.",
        metadata: {
          dataset_id: "fluxonium-2025-031",
          notes: null,
        },
      },
    ],
    progress: {
      phase: "running",
      percentComplete: 64,
      summary: "Running solver sweep",
      updatedAt: "2026-03-13 08:04:00",
    },
    resultHandoff: {
      availability: "pending",
      primaryResultHandleId: null,
      resultHandleCount: 0,
      tracePayloadAvailable: false,
    },
    resultRefs: {
      traceBatchId: null,
      analysisRunId: null,
      metadataRecords: [],
      tracePayload: null,
      resultHandles: [],
    },
  } as const;

  it("sorts persisted task events newest-first and formats metadata", () => {
    const entries = buildTaskEventHistoryEntries(task);

    expect(entries.map((entry) => entry.eventTypeLabel)).toEqual([
      "Requeued",
      "Completed",
      "Running",
      "Submitted",
    ]);
    expect(entries[0]?.metadataEntries).toEqual([
      {
        key: "reconcile_reason",
        label: "Reconcile Reason",
        value: "queue_job_missing",
      },
      {
        key: "dispatch_attempt_count",
        label: "Dispatch Attempt Count",
        value: "2",
      },
    ]);
    expect(entries[3]?.metadataEntries).toEqual([
      {
        key: "dataset_id",
        label: "Dataset Id",
        value: "fluxonium-2025-031",
      },
      {
        key: "notes",
        label: "Notes",
        value: "null",
      },
    ]);
  });

  it("summarizes task events alongside dispatch and progress state", () => {
    expect(summarizeTaskEventHistory(task)).toEqual({
      total: 4,
      infoCount: 2,
      warningCount: 2,
      errorCount: 0,
      latestEventLabel: "Requeued",
      latestOccurredAt: "2026-03-13 08:08:00",
      taskStatusLabel: "Running",
      dispatchStatusLabel: "Running",
      progressLabel: "Running · 64%",
      terminalStateLabel: "Execution active",
    });
  });

  it("returns empty defaults when no task is attached", () => {
    expect(summarizeTaskEventHistory(undefined)).toEqual({
      total: 0,
      infoCount: 0,
      warningCount: 0,
      errorCount: 0,
      latestEventLabel: null,
      latestOccurredAt: null,
      taskStatusLabel: null,
      dispatchStatusLabel: null,
      progressLabel: null,
      terminalStateLabel: "Awaiting events",
    });
  });
});
