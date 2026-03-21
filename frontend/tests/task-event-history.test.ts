import { describe, expect, it } from "vitest";

import {
  buildTaskEventHistoryEntries,
  summarizeTaskEventHistory,
} from "../src/lib/task-event-history";

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
    definitionId: 18,
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
    },
    events: [
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
      "Completed",
      "Running",
      "Submitted",
    ]);
    expect(entries[0]?.metadataEntries).toEqual([
      {
        key: "task_id",
        label: "Task Id",
        value: "58",
      },
      {
        key: "pending_checks",
        label: "Pending Checks",
        value: "plot_bundle, fit_summary",
      },
    ]);
    expect(entries[2]?.metadataEntries).toEqual([
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
      total: 3,
      infoCount: 2,
      warningCount: 1,
      errorCount: 0,
      latestEventLabel: "Completed",
      latestOccurredAt: "2026-03-13 08:07:00",
      dispatchStatusLabel: "Running",
      progressLabel: "running · 64%",
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
      dispatchStatusLabel: null,
      progressLabel: null,
      terminalStateLabel: "Awaiting events",
    });
  });
});
