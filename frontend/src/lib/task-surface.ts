import type {
  TaskAllowedActions,
  TaskDetail,
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

export type TaskContextBindingSummary = Readonly<{
  tone: SurfaceTone;
  title: string;
  message: string;
  hasMismatch: boolean;
}> | null;

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
    };
  }

  const stage =
    task.dispatch.status === "failed" || task.status === "failed" || task.progress.phase === "failed"
      ? "failed"
      : task.dispatch.status === "completed" ||
          task.status === "completed" ||
          task.progress.phase === "completed"
        ? "completed"
        : task.dispatch.status === "running" ||
            task.status === "running" ||
            task.progress.phase === "running"
          ? "running"
          : "accepted";

  if (stage === "failed") {
    return {
      stage,
      statusLabel: "Dispatch failed",
      tone: "warning",
      summary:
        "The backend accepted the request but execution failed. Persisted dispatch, events, and result refs still anchor recovery.",
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
    };
  }

  if (stage === "completed") {
    return {
      stage,
      statusLabel: "Dispatch completed",
      tone: "success",
      summary:
        "The task completed. Persisted result handles, metadata records, and event history can be reattached after refresh.",
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
    };
  }

  if (stage === "running") {
    return {
      stage,
      statusLabel: "Dispatch running",
      tone: "primary",
      summary:
        "Worker execution is active. Progress, events, and result refs remain recoverable from the persisted task contract.",
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
    };
  }

  return {
    stage,
    statusLabel: "Dispatch accepted",
    tone: "primary",
    summary:
      "The request is queued and ready to be reattached once worker execution advances.",
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

export function summarizeTaskContextBinding(input: Readonly<{
  task: TaskDetail | undefined;
  activeDatasetId: string | null;
  activeDefinitionId?: number | null;
}>): TaskContextBindingSummary {
  if (!input.task) {
    return null;
  }

  if (input.activeDatasetId && input.task.datasetId && input.task.datasetId !== input.activeDatasetId) {
    return {
      tone: "warning",
      title: "Dataset context mismatch",
      message: `Task #${input.task.taskId} is bound to dataset ${input.task.datasetId}, while the current shell dataset is ${input.activeDatasetId}. Keep the task attached for recovery, but do not treat it as the active dataset authority.`,
      hasMismatch: true,
    };
  }

  if (
    typeof input.activeDefinitionId === "number" &&
    typeof input.task.definitionId === "number" &&
    input.task.definitionId !== input.activeDefinitionId
  ) {
    return {
      tone: "warning",
      title: "Definition context mismatch",
      message: `Task #${input.task.taskId} is bound to definition #${input.task.definitionId}, while the page currently targets definition #${input.activeDefinitionId}. Attached task state stays visible for comparison, but definition context has diverged.`,
      hasMismatch: true,
    };
  }

  return {
    tone: "success",
    title: "Task context aligned",
    message: "Attached task context matches the current shell and page context.",
    hasMismatch: false,
  };
}

export function summarizeTaskResultHandoff(
  task: TaskDetail | undefined,
  resultSummary: TaskResultSurfaceSummary,
): TaskResultHandoffSummary {
  if (!task) {
    return {
      tone: "default",
      title: "Awaiting task handoff",
      message: "Attach a persisted task before handing off to a persisted result surface.",
      isReady: false,
    };
  }

  const isTerminal = task.status === "completed" || task.status === "failed";
  const hasPersistedResult =
    resultSummary.materializedHandleCount > 0 ||
    resultSummary.hasTracePayload ||
    resultSummary.analysisRunId !== null ||
    resultSummary.traceBatchId !== null;

  if (isTerminal && hasPersistedResult) {
    return {
      tone: "success",
      title: "Persisted result ready",
      message:
        "This terminal task has enough persisted result authority to hand off into the result surface without relying on in-memory execution state.",
      isReady: true,
    };
  }

  if (isTerminal) {
    return {
      tone: "warning",
      title: "Terminal without persisted result",
      message:
        "The task is terminal, but no persisted result handle or trace payload is attached yet.",
      isReady: false,
    };
  }

  return {
    tone: "primary",
    title: "Execution still active",
    message:
      "Stay on the attached task surface until the task reaches a terminal state and materializes persisted outputs.",
    isReady: false,
  };
}
