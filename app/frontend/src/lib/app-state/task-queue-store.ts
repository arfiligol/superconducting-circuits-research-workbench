import { isTaskExecutionStatusActive, isTaskExecutionStatusPending } from "@/lib/task-presenters/presentation";

export type TaskQueueScope = "simulation" | "characterization";
export type TaskQueueStatus =
  | "queued"
  | "claimed"
  | "dispatching"
  | "running"
  | "staging_result"
  | "publishing"
  | "cancellation_requested"
  | "cancelling"
  | "cancelled"
  | "termination_requested"
  | "terminated"
  | "completed"
  | "failed";
export type TaskQueueExecutionMode = "run" | "probe";
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
  definitionId: string | null;
  summary: string;
  resultAvailability?: "pending" | "ready" | "none" | null;
  controlState?: "none" | "cancellation_requested" | "termination_requested" | null;
  reconcile?: Readonly<{
    required: boolean;
    reason: string | null;
    recordedAt: string | null;
  }> | null;
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
      pendingCount: summary.pendingCount + (isTaskExecutionStatusPending(task.status) ? 1 : 0),
      runningCount:
        summary.runningCount +
        (isTaskExecutionStatusActive(task.status) && !isTaskExecutionStatusPending(task.status)
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
  return isTaskExecutionStatusActive(task.status);
}

export function resolveLatestTask(tasks: readonly TaskQueueItem[]): TaskQueueItem | undefined {
  return tasks.find(isTaskQueueTaskActive) ?? tasks[0];
}

export function resolveTaskQueueRefreshInterval(tasks: readonly TaskQueueItem[]): number {
  return tasks.some(isTaskQueueTaskActive) ? 5_000 : 0;
}
