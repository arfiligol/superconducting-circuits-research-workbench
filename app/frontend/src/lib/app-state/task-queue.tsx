"use client";

import { createContext, useContext } from "react";
import useSWR from "swr";

import {
  resolveLatestTask,
  resolveTaskQueueRefreshInterval,
  summarizeTaskQueue,
  isTaskQueueTaskActive,
  type TaskQueueItem,
} from "@/lib/app-state/task-queue-store";
import { listTasks, tasksListKey, type TaskQueueReadModel, type WorkerLaneSummary } from "@/lib/api/tasks";
import { useAppSession } from "@/lib/app-state/app-session";

export type TaskQueueStatus = "loading" | "ready" | "error" | "refreshing";

type TaskQueueContextValue = Readonly<{
  contextKey: string;
  tasks: readonly TaskQueueItem[];
  activeTasks: readonly TaskQueueItem[];
  workerSummary: readonly WorkerLaneSummary[];
  summary: ReturnType<typeof summarizeTaskQueue>;
  latestTask: TaskQueueItem | undefined;
  status: TaskQueueStatus;
  isTaskQueueLoading: boolean;
  isTaskQueueRefreshing: boolean;
  hasResolvedTaskQueue: boolean;
  taskQueueError: Error | undefined;
  refreshIntervalMs: number;
  refreshTaskQueue: () => Promise<TaskQueueReadModel | undefined>;
}>;

const TaskQueueContext = createContext<TaskQueueContextValue | null>(null);

type TaskQueueProviderProps = Readonly<{
  children: React.ReactNode;
}>;

export function TaskQueueProvider({ children }: TaskQueueProviderProps) {
  const { session, status: sessionStatus } = useAppSession();
  const contextKey = `${session?.runtimeMode ?? "online"}:${session?.workspace.workspaceId ?? "none"}`;
  const swrKey = sessionStatus === "loading" ? null : [tasksListKey, contextKey];
  const tasksQuery = useSWR(swrKey, () => listTasks(), {
    refreshInterval(currentData) {
      return resolveTaskQueueRefreshInterval(currentData?.rows ?? []);
    },
  });
  const taskQueue = tasksQuery.data;
  const tasks = taskQueue?.rows ?? [];
  const workerSummary = taskQueue?.workerSummary ?? [];
  const activeTasks = tasks.filter(isTaskQueueTaskActive);
  const status: TaskQueueStatus =
    tasksQuery.isLoading && tasks.length === 0
      ? "loading"
      : tasksQuery.error && tasks.length === 0
        ? "error"
        : tasksQuery.isValidating && tasks.length > 0
          ? "refreshing"
          : "ready";
  const refreshIntervalMs = resolveTaskQueueRefreshInterval(tasks);

  return (
    <TaskQueueContext.Provider
      value={{
        contextKey,
        tasks,
        activeTasks,
        workerSummary,
        summary: summarizeTaskQueue(tasks),
        latestTask: resolveLatestTask(tasks),
        status,
        isTaskQueueLoading: tasksQuery.isLoading,
        isTaskQueueRefreshing: status === "refreshing",
        hasResolvedTaskQueue: !!tasksQuery.data || !!tasksQuery.error,
        taskQueueError: tasksQuery.error as Error | undefined,
        refreshIntervalMs,
        async refreshTaskQueue() {
          return tasksQuery.mutate();
        },
      }}
    >
      {children}
    </TaskQueueContext.Provider>
  );
}

export function useTaskQueue() {
  const context = useContext(TaskQueueContext);

  if (!context) {
    throw new Error("useTaskQueue must be used within a TaskQueueProvider.");
  }

  return context;
}
