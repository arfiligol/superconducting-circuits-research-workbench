import type {
  TaskAllowedActions,
  TaskDetail,
  TaskExecutionStatus,
  TaskResultHandleRef,
  TaskSummary,
} from "@/lib/api/tasks";

type SurfaceTone = "default" | "primary" | "success" | "warning";

export type TaskConnectionState = Readonly<{
  mode: "none" | "latest" | "explicit";
  latestTaskId: number | null;
  selectedTaskId: number | null;
  attachedTaskId: number | null;
  hasNewerLatestTask: boolean;
  isFollowingLatest: boolean;
  isAttached: boolean;
  isStaleSnapshot: boolean;
}>;

export type TaskRecoveryNotice = Readonly<{
  tone: "warning";
  title: string;
  message: string;
}> | null;

export type TaskLifecycleSummary = Readonly<{
  stage: "idle" | "accepted" | "running" | "completed" | "failed";
  statusLabel: string;
  tone: SurfaceTone;
  summary: string;
  progressPercent: number;
  progressSummary: string;
  backendStatusLabel: string;
  workerTaskName: string | null;
  submissionSourceLabel: string | null;
  acceptedAt: string | null;
  lastUpdatedAt: string | null;
  taskDatasetId: string | null;
  dispatchKey: string | null;
  requestReady: boolean;
  submittedFromActiveDataset: boolean;
  executionMode: TaskDetail["executionMode"] | null;
  visibilityScope: TaskDetail["visibilityScope"] | null;
  reconcileRequired: boolean;
  reconcileReason: string | null;
  reconcileRecordedAt: string | null;
}>;

export type TaskResultSurfaceSummary = Readonly<{
  metadataRecordCount: number;
  resultHandleCount: number;
  materializedHandleCount: number;
  pendingHandleCount: number;
  hasTracePayload: boolean;
  traceBatchId: number | null;
  analysisRunId: number | null;
  handleKindCounts: readonly Readonly<{
    kind: TaskResultHandleRef["kind"];
    count: number;
  }>[];
}>;

export type TaskResultHandleGroups = Readonly<{
  materialized: readonly TaskResultHandleRef[];
  pending: readonly TaskResultHandleRef[];
}>;

export type TaskActionGate = Readonly<{
  action: "attach" | "cancel" | "terminate" | "retry";
  enabled: boolean;
  reason: string;
}>;

export type TaskActionGateSummary = Readonly<{
  hasActionAuthority: boolean;
  attach: TaskActionGate;
  cancel: TaskActionGate;
  terminate: TaskActionGate;
  retry: TaskActionGate;
}>;

export type TaskResultHandoffSummary = Readonly<{
  tone: SurfaceTone;
  title: string;
  message: string;
  isReady: boolean;
}>;

type ActionAuthorityTask = Pick<
  TaskSummary,
  "hasActionAuthority" | "allowedActions" | "taskId" | "summary"
>;

function formatSubmissionSourceLabel(
  source: TaskDetail["dispatch"]["submissionSource"],
): string {
  switch (source) {
    case "active_dataset":
      return "Active dataset session";
    case "explicit_dataset":
      return "Explicit dataset binding";
    case "definition_only":
      return "Definition-only dispatch";
    default:
      return source;
  }
}

function formatExecutionStatusLabel(status: TaskExecutionStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "dispatching":
      return "Dispatching";
    case "running":
      return "Running";
    case "cancellation_requested":
      return "Cancel requested";
    case "cancelling":
      return "Cancelling";
    case "cancelled":
      return "Cancelled";
    case "termination_requested":
      return "Terminate requested";
    case "terminated":
      return "Terminated";
    case "completed":
      return "Completed";
    case "failed":
    default:
      return "Failed";
  }
}

export function formatTaskConnectionModeLabel(mode: TaskConnectionState["mode"]) {
  switch (mode) {
    case "explicit":
      return "Explicit attachment";
    case "latest":
      return "Follow latest";
    case "none":
    default:
      return "No task available";
  }
}

export function resolveTaskConnectionState(input: Readonly<{
  requestedTaskId: number | null;
  resolvedTaskId: number | null;
  latestTaskId: number | null;
  activeTask: TaskDetail | undefined;
}>): TaskConnectionState {
  const attachedTaskId = input.activeTask?.taskId ?? null;

  if (input.resolvedTaskId === null && input.latestTaskId === null) {
    return {
      mode: "none",
      latestTaskId: null,
      selectedTaskId: null,
      attachedTaskId,
      hasNewerLatestTask: false,
      isFollowingLatest: false,
      isAttached: false,
      isStaleSnapshot: false,
    };
  }

  const mode = input.requestedTaskId === null ? "latest" : "explicit";
  const isAttached =
    attachedTaskId !== null &&
    input.resolvedTaskId !== null &&
    attachedTaskId === input.resolvedTaskId;
  const isStaleSnapshot =
    attachedTaskId !== null &&
    input.resolvedTaskId !== null &&
    attachedTaskId !== input.resolvedTaskId;

  return {
    mode,
    latestTaskId: input.latestTaskId,
    selectedTaskId: input.resolvedTaskId,
    attachedTaskId,
    hasNewerLatestTask:
      input.latestTaskId !== null &&
      input.resolvedTaskId !== null &&
      input.latestTaskId !== input.resolvedTaskId,
    isFollowingLatest:
      input.requestedTaskId === null &&
      input.latestTaskId !== null &&
      input.resolvedTaskId === input.latestTaskId,
    isAttached,
    isStaleSnapshot,
  };
}

export function resolveTaskRecoveryNotice(
  requestedTaskId: number | null,
  latestTaskId: number | null,
  activeTaskError: Error | undefined,
): TaskRecoveryNotice {
  if (requestedTaskId === null || !activeTaskError) {
    return null;
  }

  if (latestTaskId !== null && latestTaskId !== requestedTaskId) {
    return {
      tone: "warning",
      title: "Task reattach available",
      message: `Task #${requestedTaskId} could not be attached. A newer task #${latestTaskId} is available instead.`,
    };
  }

  return {
    tone: "warning",
    title: "Task unavailable",
    message: `Task #${requestedTaskId} could not be attached. Refresh the task queue or submit a new request.`,
  };
}

export function summarizeTaskLifecycle(
  task: TaskDetail | undefined,
): TaskLifecycleSummary {
  if (!task) {
    return {
      stage: "idle",
      statusLabel: "Idle",
      tone: "default",
      summary:
        "Attach a task to inspect persisted dispatch state, progress, and backend execution metadata.",
      progressPercent: 0,
      progressSummary: "Select or submit a task to inspect its persisted execution state.",
      backendStatusLabel: "pending",
      workerTaskName: null,
      submissionSourceLabel: null,
      acceptedAt: null,
      lastUpdatedAt: null,
      taskDatasetId: null,
      dispatchKey: null,
      requestReady: false,
      submittedFromActiveDataset: false,
      executionMode: null,
      visibilityScope: null,
      reconcileRequired: false,
      reconcileReason: null,
      reconcileRecordedAt: null,
    };
  }

  const statusLabel = formatExecutionStatusLabel(task.status);
  const { stage, tone, summary } = (() => {
    switch (task.status) {
      case "failed":
        return {
          stage: "failed" as const,
          tone: "warning" as const,
          summary:
            "Execution failed. Inspect dispatch metadata, persisted events, and reconcile state before retrying.",
        };
      case "cancelled":
        return {
          stage: "failed" as const,
          tone: "warning" as const,
          summary:
            "Cancellation was acknowledged and persisted. The attached task remains the authority for follow-up review.",
        };
      case "terminated":
        return {
          stage: "failed" as const,
          tone: "warning" as const,
          summary:
            "Termination was acknowledged and persisted. Use the task detail and event trail for recovery.",
        };
      case "completed":
        return {
          stage: "completed" as const,
          tone: "success" as const,
          summary:
            "Execution completed. Result readiness now depends on the persisted result handoff, not queue state.",
        };
      case "running":
      case "dispatching":
      case "cancellation_requested":
      case "cancelling":
      case "termination_requested":
        return {
          stage: "running" as const,
          tone: "primary" as const,
          summary:
            "Worker runtime is still active. Keep the attached task detail refreshed until the backend settles the request.",
        };
      case "queued":
      default:
        return {
          stage: "accepted" as const,
          tone: "primary" as const,
          summary:
            "The request is queued and waiting for a worker claim. Dispatch metadata is supplemental to the task status authority.",
        };
    }
  })();

  return {
    stage,
    statusLabel,
    tone,
    summary,
    progressPercent: task.progress.percentComplete,
    progressSummary: task.progress.summary,
    backendStatusLabel: task.status,
    workerTaskName: task.workerTaskName,
    submissionSourceLabel: formatSubmissionSourceLabel(task.dispatch.submissionSource),
    acceptedAt: task.dispatch.acceptedAt,
    lastUpdatedAt: task.dispatch.lastUpdatedAt,
    taskDatasetId: task.datasetId,
    dispatchKey: task.dispatch.dispatchKey,
    requestReady: task.requestReady,
    submittedFromActiveDataset: task.submittedFromActiveDataset,
    executionMode: task.executionMode,
    visibilityScope: task.visibilityScope,
    reconcileRequired: task.reconcile?.required ?? false,
    reconcileReason: task.reconcile?.reason ?? null,
    reconcileRecordedAt: task.reconcile?.recordedAt ?? null,
  };
}

export function groupTaskResultHandles(
  task: TaskDetail | undefined,
): TaskResultHandleGroups {
  const handles = task?.resultRefs.resultHandles ?? [];

  return {
    materialized: handles.filter((handle) => handle.status === "materialized"),
    pending: handles.filter((handle) => handle.status !== "materialized"),
  };
}

export function summarizeTaskResultSurface(
  task: TaskDetail | undefined,
): TaskResultSurfaceSummary {
  const handles = task?.resultRefs.resultHandles ?? [];
  const countsByKind = new Map<TaskResultHandleRef["kind"], number>();

  for (const handle of handles) {
    countsByKind.set(handle.kind, (countsByKind.get(handle.kind) ?? 0) + 1);
  }

  return {
    metadataRecordCount: task?.resultRefs.metadataRecords.length ?? 0,
    resultHandleCount: handles.length,
    materializedHandleCount: handles.filter((handle) => handle.status === "materialized").length,
    pendingHandleCount: handles.filter((handle) => handle.status !== "materialized").length,
    hasTracePayload: task?.resultRefs.tracePayload != null,
    traceBatchId: task?.resultRefs.traceBatchId ?? null,
    analysisRunId: task?.resultRefs.analysisRunId ?? null,
    handleKindCounts: [...countsByKind.entries()]
      .map(([kind, count]) => ({ kind, count }))
      .sort((left, right) => right.count - left.count || left.kind.localeCompare(right.kind)),
  };
}

function resolveActionReason(
  action: keyof TaskAllowedActions,
  task: ActionAuthorityTask | undefined,
) {
  if (!task) {
    return "Attach a persisted task before reading backend action authority.";
  }

  if (!task.hasActionAuthority) {
    return "Backend allowed_actions are not available for this task yet.";
  }

  if (task.allowedActions[action]) {
    return "Allowed by the backend task contract.";
  }

  return task.allowedActions.rejectionReason ?? "Blocked by backend allowed_actions for the current session.";
}

export function summarizeTaskActionGates(
  task: ActionAuthorityTask | undefined,
): TaskActionGateSummary {
  return {
    hasActionAuthority: task?.hasActionAuthority ?? false,
    attach: {
      action: "attach",
      enabled: task?.allowedActions.attach ?? false,
      reason: resolveActionReason("attach", task),
    },
    cancel: {
      action: "cancel",
      enabled: task?.allowedActions.cancel ?? false,
      reason: resolveActionReason("cancel", task),
    },
    terminate: {
      action: "terminate",
      enabled: task?.allowedActions.terminate ?? false,
      reason: resolveActionReason("terminate", task),
    },
    retry: {
      action: "retry",
      enabled: task?.allowedActions.retry ?? false,
      reason: resolveActionReason("retry", task),
    },
  };
}

export function summarizeTaskResultHandoff(
  task: TaskDetail | undefined,
  _resultSummary: TaskResultSurfaceSummary,
): TaskResultHandoffSummary {
  if (!task) {
    return {
      tone: "default",
      title: "Awaiting task handoff",
      message: "Attach a persisted task before handing off to a persisted result surface.",
      isReady: false,
    };
  }

  if (task.resultHandoff?.availability === "ready") {
    return {
      tone: "success",
      title: "Persisted result ready",
      message:
        "The backend has marked the persisted result handoff ready. Result surfaces should use this as the readiness authority.",
      isReady: true,
    };
  }

  if (task.resultHandoff?.availability === "pending") {
    return {
      tone: "primary",
      title: "Result handoff pending",
      message:
        task.status === "completed"
          ? "Execution is complete, but the persisted result handoff is still pending."
          : "Execution is still active and the persisted result handoff is not ready yet.",
      isReady: false,
    };
  }

  return {
    tone: "warning",
    title: "No persisted result handoff",
    message:
      "The backend reports no persisted result handoff for this task yet. Treat the attached task detail as the only authority.",
    isReady: false,
  };
}
