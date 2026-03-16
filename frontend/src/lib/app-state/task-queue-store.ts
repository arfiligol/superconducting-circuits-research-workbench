export type TaskQueueScope = "simulation" | "characterization";
export type TaskQueueStatus = "queued" | "running" | "completed" | "failed";
export type TaskQueueExecutionMode = "run" | "smoke";
export type TaskQueueVisibilityScope = "local" | "private" | "workspace" | "owned";

export type TaskQueueItem = Readonly<{
  taskId: number;
  kind: "simulation" | "post_processing" | "characterization";
  lane: TaskQueueScope;
  executionMode: TaskQueueExecutionMode;
  status: TaskQueueStatus;
  submittedAt: string;
  ownerUserId: string;
  ownerDisplayName: string;
  workspaceId: string;
  workspaceSlug: string;
  visibilityScope: TaskQueueVisibilityScope;
  datasetId: string | null;
  definitionId: number | null;
  summary: string;
}>;

export type TaskQueueSummary = Readonly<{
  total: number;
  queuedCount: number;
  runningCount: number;
  failedCount: number;
  completedCount: number;
}>;

export function summarizeTaskQueue(tasks: readonly TaskQueueItem[]): TaskQueueSummary {
  return tasks.reduce<TaskQueueSummary>(
    (summary, task) => ({
      total: summary.total + 1,
      queuedCount: summary.queuedCount + (task.status === "queued" ? 1 : 0),
      runningCount: summary.runningCount + (task.status === "running" ? 1 : 0),
      failedCount: summary.failedCount + (task.status === "failed" ? 1 : 0),
      completedCount: summary.completedCount + (task.status === "completed" ? 1 : 0),
    }),
    {
      total: 0,
      queuedCount: 0,
      runningCount: 0,
      failedCount: 0,
      completedCount: 0,
    },
  );
}

export function isTaskQueueTaskActive(task: TaskQueueItem): boolean {
  return task.status === "queued" || task.status === "running";
}

export function resolveLatestTask(tasks: readonly TaskQueueItem[]): TaskQueueItem | undefined {
  return tasks.find(isTaskQueueTaskActive) ?? tasks[0];
}

export function resolveTaskQueueRefreshInterval(tasks: readonly TaskQueueItem[]): number {
  return tasks.some(isTaskQueueTaskActive) ? 5_000 : 0;
}
