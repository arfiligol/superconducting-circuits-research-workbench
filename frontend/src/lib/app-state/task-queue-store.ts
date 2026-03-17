export type TaskQueueScope = "simulation" | "characterization";
export type TaskQueueStatus =
  | "queued"
  | "dispatching"
  | "running"
  | "cancellation_requested"
  | "cancelling"
  | "cancelled"
  | "termination_requested"
  | "terminated"
  | "completed"
  | "failed";
export type TaskQueueExecutionMode = "run" | "smoke";
export type TaskQueueVisibilityScope = "local" | "private" | "workspace" | "owned";

export type TaskQueueItem = Readonly<{
  taskId: number;
  kind: "simulation" | "post_processing" | "characterization";
  lane: TaskQueueScope;
  executionMode: TaskQueueExecutionMode | null;
  status: TaskQueueStatus;
  submittedAt: string | null;
  updatedAt?: string | null;
  ownerUserId: string | null;
  ownerDisplayName: string;
  workspaceId: string | null;
  workspaceSlug: string | null;
  visibilityScope: TaskQueueVisibilityScope;
  datasetId: string | null;
  definitionId: number | null;
  summary: string;
  resultAvailability?: "pending" | "ready" | "none" | null;
  controlState?: "none" | "cancellation_requested" | "termination_requested" | null;
}>;

export type TaskQueueSummary = Readonly<{
  total: number;
  pendingCount: number;
  runningCount: number;
  failedCount: number;
  completedCount: number;
  cancelledCount: number;
  terminatedCount: number;
}>;

export function summarizeTaskQueue(tasks: readonly TaskQueueItem[]): TaskQueueSummary {
  return tasks.reduce<TaskQueueSummary>(
    (summary, task) => ({
      total: summary.total + 1,
      pendingCount:
        summary.pendingCount + (task.status === "queued" || task.status === "dispatching" ? 1 : 0),
      runningCount:
        summary.runningCount +
        (task.status === "running" ||
        task.status === "cancellation_requested" ||
        task.status === "cancelling" ||
        task.status === "termination_requested"
          ? 1
          : 0),
      failedCount: summary.failedCount + (task.status === "failed" ? 1 : 0),
      completedCount: summary.completedCount + (task.status === "completed" ? 1 : 0),
      cancelledCount: summary.cancelledCount + (task.status === "cancelled" ? 1 : 0),
      terminatedCount: summary.terminatedCount + (task.status === "terminated" ? 1 : 0),
    }),
    {
      total: 0,
      pendingCount: 0,
      runningCount: 0,
      failedCount: 0,
      completedCount: 0,
      cancelledCount: 0,
      terminatedCount: 0,
    },
  );
}

export function isTaskQueueTaskActive(task: TaskQueueItem): boolean {
  return (
    task.status === "queued" ||
    task.status === "dispatching" ||
    task.status === "running" ||
    task.status === "cancellation_requested" ||
    task.status === "cancelling" ||
    task.status === "termination_requested"
  );
}

export function resolveLatestTask(tasks: readonly TaskQueueItem[]): TaskQueueItem | undefined {
  return tasks.find(isTaskQueueTaskActive) ?? tasks[0];
}

export function resolveTaskQueueRefreshInterval(tasks: readonly TaskQueueItem[]): number {
  return tasks.some(isTaskQueueTaskActive) ? 5_000 : 0;
}
