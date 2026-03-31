"use client";

import useSWR from "swr";

import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";
import type { SimulationPageContext } from "@/features/simulation/lib/workflow";
import {
  filterSimulationTasksByContext,
  resolveContextBoundAttachedTask,
  resolveLatestSimulationStageTaskInContext,
  resolveLatestSimulationTaskInContext,
} from "@/features/simulation/lib/workflow";
import { shouldRefreshSimulationTaskDetail } from "@/features/simulation/lib/stage-state";
import { useTaskQueue } from "@/lib/app-state/task-queue";
import {
  getTask,
  normalizeTaskSummary,
  taskDetailKey,
} from "@/lib/api/tasks";

function usePolledTaskDetail(taskId: number | null) {
  return useSWR(
    taskId ? taskDetailKey(taskId) : null,
    () => (taskId ? getTask(taskId) : Promise.resolve(undefined)),
    {
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return shouldRefreshSimulationTaskDetail(currentData) ? 2_000 : 0;
      },
    },
  );
}

export function useSimulationStageTaskData(input: Readonly<{
  selectedTaskId: number | null;
  definitionId: CircuitDefinitionId | null;
  datasetId: string | null;
}>) {
  const taskQueueState = useTaskQueue();
  const pageContext: SimulationPageContext = {
    definitionId: input.definitionId,
    datasetId: input.datasetId,
  };

  const simulationTasks = taskQueueState.tasks
    .map(normalizeTaskSummary)
    .filter((task) => task.kind === "simulation" || task.kind === "post_processing");
  const currentContextSimulationTasks = filterSimulationTasksByContext(
    simulationTasks,
    pageContext,
  );
  const latestSimulationTaskFromQueue = resolveLatestSimulationTaskInContext(
    simulationTasks,
    pageContext,
  );
  const latestSimulationStageTaskFromQueue = resolveLatestSimulationStageTaskInContext(
    simulationTasks,
    "simulation",
    pageContext,
  );
  const latestPostProcessingTaskFromQueue = resolveLatestSimulationStageTaskInContext(
    simulationTasks,
    "post_processing",
    pageContext,
  );
  const resolvedTaskId = input.selectedTaskId ?? latestSimulationTaskFromQueue?.taskId ?? null;
  const taskDetailQuery = usePolledTaskDetail(resolvedTaskId);
  const activeTask = taskDetailQuery.data;
  const hasAttachedTask =
    typeof resolvedTaskId === "number" && activeTask?.taskId === resolvedTaskId;
  const attachedContextTask = resolveContextBoundAttachedTask(activeTask, pageContext);
  const attachedSimulationStageTask = resolveContextBoundAttachedTask(
    activeTask,
    pageContext,
    "simulation",
  );
  const attachedSimulationTaskDetail =
    activeTask?.kind === "simulation" && attachedSimulationStageTask ? activeTask : undefined;
  const attachedPostProcessingStageTask = resolveContextBoundAttachedTask(
    activeTask,
    pageContext,
    "post_processing",
  );
  const upstreamSimulationTaskId =
    activeTask?.kind === "post_processing" && attachedPostProcessingStageTask
      ? activeTask.upstreamTaskId ?? null
      : null;
  const upstreamSimulationTaskQuery = usePolledTaskDetail(upstreamSimulationTaskId);
  const upstreamSimulationStageTask = resolveContextBoundAttachedTask(
    upstreamSimulationTaskQuery.data,
    pageContext,
    "simulation",
  );
  const latestSimulationTask =
    latestSimulationTaskFromQueue ?? attachedContextTask ?? upstreamSimulationStageTask;
  const latestSimulationStageTask =
    latestSimulationStageTaskFromQueue ??
    attachedSimulationStageTask ??
    upstreamSimulationStageTask;
  const latestPostProcessingTask =
    latestPostProcessingTaskFromQueue ?? attachedPostProcessingStageTask;
  const simulationStageTaskQuery = usePolledTaskDetail(
    latestSimulationStageTask?.taskId ?? null,
  );
  const latestSimulationTaskDetail =
    activeTask?.taskId === latestSimulationStageTask?.taskId
      ? activeTask
      : upstreamSimulationTaskQuery.data?.taskId === latestSimulationStageTask?.taskId
        ? upstreamSimulationTaskQuery.data
        : simulationStageTaskQuery.data;
  const postProcessingStageTaskQuery = usePolledTaskDetail(
    latestPostProcessingTask?.taskId ?? null,
  );
  const latestPostProcessingTaskDetail =
    activeTask?.taskId === latestPostProcessingTask?.taskId
      ? activeTask
      : postProcessingStageTaskQuery.data;

  return {
    taskQueueState,
    pageContext,
    simulationTasks,
    currentContextSimulationTasks,
    latestSimulationTask,
    latestSimulationStageTask,
    latestSimulationTaskDetail,
    attachedSimulationStageTask,
    attachedSimulationTaskDetail,
    latestSimulationTaskError:
      (simulationStageTaskQuery.error as Error | undefined) ??
      (upstreamSimulationTaskQuery.error as Error | undefined),
    isLatestSimulationTaskLoading:
      Boolean(latestSimulationStageTask) && !latestSimulationTaskDetail,
    latestPostProcessingTask,
    latestPostProcessingTaskDetail,
    latestPostProcessingTaskError: postProcessingStageTaskQuery.error as Error | undefined,
    isLatestPostProcessingTaskLoading:
      Boolean(latestPostProcessingTask) && !latestPostProcessingTaskDetail,
    resolvedTaskId,
    activeTask,
    activeTaskError: taskDetailQuery.error as Error | undefined,
    isTaskTransitioning:
      typeof resolvedTaskId === "number" && (!hasAttachedTask || taskDetailQuery.isLoading),
    refreshTaskQueue: taskQueueState.refreshTaskQueue,
    refreshActiveTask: taskDetailQuery.mutate,
    refreshLatestSimulationTask: simulationStageTaskQuery.mutate,
    refreshLatestPostProcessingTask: postProcessingStageTaskQuery.mutate,
    refreshUpstreamSimulationTask: upstreamSimulationTaskQuery.mutate,
  };
}
