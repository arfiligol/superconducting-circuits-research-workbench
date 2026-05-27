import type {
  TaskControlState,
  TaskDispatch,
  TaskEvent,
  TaskExecutionStatus,
  TaskKind,
  TaskResultAvailability,
  TaskVisibilityScope,
} from "@/lib/api/tasks";

export type TaskSurfaceTone = "default" | "primary" | "success" | "warning";

export type TaskLifecycleStage =
  | "idle"
  | "accepted"
  | "running"
  | "completed"
  | "cancelled"
  | "terminated"
  | "failed";

export function formatTaskExecutionStatusLabel(status: TaskExecutionStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "claimed":
      return "Claimed";
    case "dispatching":
      return "Dispatching";
    case "running":
      return "Running";
    case "staging_result":
      return "Staging Result";
    case "publishing":
      return "Publishing";
    case "cancellation_requested":
      return "Cancel Requested";
    case "cancelling":
      return "Cancelling";
    case "cancelled":
      return "Cancelled";
    case "termination_requested":
      return "Terminate Requested";
    case "terminated":
      return "Terminated";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
  }
}

export function resolveTaskExecutionStatusTone(
  status: TaskExecutionStatus,
): TaskSurfaceTone {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
    case "cancelled":
    case "terminated":
      return "warning";
    case "queued":
    case "claimed":
    case "dispatching":
    case "running":
    case "staging_result":
    case "publishing":
    case "cancellation_requested":
    case "cancelling":
    case "termination_requested":
      return "primary";
  }
}

export function resolveTaskLifecycleStage(
  status: TaskExecutionStatus,
): TaskLifecycleStage {
  switch (status) {
    case "queued":
    case "claimed":
    case "dispatching":
      return "accepted";
    case "running":
    case "staging_result":
    case "publishing":
    case "cancellation_requested":
    case "cancelling":
    case "termination_requested":
      return "running";
    case "completed":
      return "completed";
    case "cancelled":
      return "cancelled";
    case "terminated":
      return "terminated";
    case "failed":
      return "failed";
  }
}

export function isTaskExecutionStatusPending(status: TaskExecutionStatus): boolean {
  return status === "queued" || status === "claimed" || status === "dispatching";
}

export function isTaskExecutionStatusActive(status: TaskExecutionStatus): boolean {
  return (
    status === "queued" ||
    status === "claimed" ||
    status === "dispatching" ||
    status === "running" ||
    status === "staging_result" ||
    status === "publishing" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  );
}

export function formatTaskLaneLabel(lane: string): string {
  switch (lane) {
    case "simulation":
      return "Simulation";
    case "characterization":
      return "Characterization";
    default:
      return lane;
  }
}

export function formatWorkerLaneLabel(lane: string): string {
  return lane
    .split("_")
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

export function formatTaskKindLabel(kind: TaskKind): string {
  switch (kind) {
    case "post_processing":
      return "Post Processing";
    case "characterization":
      return "Characterization";
    case "simulation":
      return "Simulation";
  }
}

export function formatTaskResultAvailabilityLabel(
  availability: TaskResultAvailability | null | undefined,
): string {
  switch (availability) {
    case "ready":
      return "Ready";
    case "pending":
      return "Pending";
    case "none":
      return "None";
    default:
      return "--";
  }
}

export function resolveTaskResultAvailabilityTone(
  availability: TaskResultAvailability | null | undefined,
): TaskSurfaceTone {
  switch (availability) {
    case "ready":
      return "success";
    case "pending":
      return "primary";
    default:
      return "default";
  }
}

export function formatTaskVisibilityScopeLabel(scope: TaskVisibilityScope): string {
  switch (scope) {
    case "local":
      return "Local";
    case "private":
      return "Private";
    case "owned":
      return "Mine";
    case "workspace":
      return "Workspace";
  }
}

export function formatTaskControlStateLabel(
  controlState: TaskControlState | null | undefined,
): string | null {
  switch (controlState) {
    case "cancellation_requested":
      return "Cancel requested";
    case "termination_requested":
      return "Terminate requested";
    default:
      return null;
  }
}

export function formatTaskSubmissionSourceLabel(
  source: TaskDispatch["submissionSource"],
): string {
  switch (source) {
    case "active_dataset":
      return "Active dataset session";
    case "explicit_dataset":
      return "Explicit dataset binding";
    case "definition_only":
      return "Definition-only dispatch";
  }
}

export function formatTaskEventTypeLabel(eventType: TaskEvent["eventType"]): string {
  switch (eventType) {
    case "task_submitted":
      return "Submitted";
    case "task_dispatch_claimed":
      return "Dispatch Claimed";
    case "task_running":
      return "Running";
    case "task_completed":
      return "Completed";
    case "task_failed":
      return "Failed";
    case "task_cancel_requested":
      return "Cancel Requested";
    case "task_cancel_acknowledged":
      return "Cancel Acknowledged";
    case "task_terminate_requested":
      return "Terminate Requested";
    case "task_terminate_acknowledged":
      return "Terminate Acknowledged";
    case "task_requeued":
      return "Requeued";
    case "task_retried":
      return "Retried";
    default:
      return toTitleCase(eventType);
  }
}

export function resolveTaskEventTone(
  event: Pick<TaskEvent, "eventType" | "level">,
): TaskSurfaceTone {
  if (event.level === "error" || event.eventType === "task_failed") {
    return "warning";
  }

  if (event.eventType === "task_completed") {
    return "success";
  }

  if (
    event.eventType === "task_running" ||
    event.eventType === "task_submitted" ||
    event.eventType === "task_dispatch_claimed" ||
    event.eventType === "task_requeued"
  ) {
    return "primary";
  }

  return "default";
}

export function resolveTaskEventLevelTone(
  level: TaskEvent["level"],
): TaskSurfaceTone {
  if (level === "error" || level === "warning") {
    return "warning";
  }

  return "default";
}

export function summarizeTaskLifecycleCopy(status: TaskExecutionStatus): Readonly<{
  stage: TaskLifecycleStage;
  statusLabel: string;
  tone: TaskSurfaceTone;
  summary: string;
  terminalStateLabel: string;
}> {
  switch (status) {
    case "queued":
    case "claimed":
      return {
        stage: "accepted",
        statusLabel: formatTaskExecutionStatusLabel(status),
        tone: "primary",
        summary:
          "The request is waiting for the runner to begin active execution. Dispatch metadata is supplemental to the task status authority.",
        terminalStateLabel: "Dispatch pending",
      };
    case "dispatching":
    case "running":
    case "staging_result":
    case "publishing":
    case "cancellation_requested":
    case "cancelling":
    case "termination_requested":
      return {
        stage: "running",
        statusLabel: formatTaskExecutionStatusLabel(status),
        tone: "primary",
        summary:
          "Worker runtime is still active. Keep the attached task detail refreshed until the backend settles the request.",
        terminalStateLabel: "Execution active",
      };
    case "completed":
      return {
        stage: "completed",
        statusLabel: formatTaskExecutionStatusLabel(status),
        tone: "success",
        summary:
          "Execution completed. Result readiness now depends on the persisted result handoff, not queue state.",
        terminalStateLabel: "Completion persisted",
      };
    case "cancelled":
      return {
        stage: "cancelled",
        statusLabel: formatTaskExecutionStatusLabel(status),
        tone: "warning",
        summary:
          "Cancellation was acknowledged and persisted. The attached task remains the authority for follow-up review.",
        terminalStateLabel: "Cancellation persisted",
      };
    case "terminated":
      return {
        stage: "terminated",
        statusLabel: formatTaskExecutionStatusLabel(status),
        tone: "warning",
        summary:
          "Termination was acknowledged and persisted. Use the task detail and event trail for recovery.",
        terminalStateLabel: "Termination persisted",
      };
    case "failed":
      return {
        stage: "failed",
        statusLabel: formatTaskExecutionStatusLabel(status),
        tone: "warning",
        summary:
          "Execution failed. Inspect dispatch metadata, persisted events, and reconcile state before retrying.",
        terminalStateLabel: "Failure persisted",
      };
    default:
      return {
        stage: "idle",
        statusLabel: "Idle",
        tone: "default",
        summary:
          "Attach a task to inspect persisted execution state, progress, and backend execution metadata.",
        terminalStateLabel: "Awaiting events",
      };
  }
}

function toTitleCase(value: string): string {
  return value
    .split("_")
    .filter((segment) => segment.length > 0)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}
