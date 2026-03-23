"use client";

import useSWR from "swr";

import {
  getCircuitDefinition,
  listCircuitDefinitions,
  circuitDefinitionDetailKey,
  circuitDefinitionsListKey,
} from "@/features/circuit-definition-editor/lib/api";
import { resolveSimulationDefinitionId } from "@/features/simulation/lib/definition-id";
import {
  filterSimulationTasksByContext,
  hasSimulationTaskResult,
  resolveContextBoundAttachedTask,
  resolveLatestSimulationStageTaskInContext,
  resolveLatestSimulationTaskInContext,
} from "@/features/simulation/lib/workflow";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { useAppSession } from "@/lib/app-state/app-session";
import { useTaskQueue } from "@/lib/app-state/task-queue";
import {
  getTask,
  normalizeTaskSummary,
  taskDetailKey,
  type TaskDetail,
} from "@/lib/api/tasks";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

export function useSimulationWorkflowData(
  selectedDefinitionId: CircuitDefinitionId | null,
  selectedTaskId: number | null,
) {
  const { session } = useAppSession();
  const activeDatasetState = useActiveDataset();
  const taskQueueState = useTaskQueue();

  const definitionsQuery = useSWR(circuitDefinitionsListKey, listCircuitDefinitions);
  const resolvedDefinitionId = resolveSimulationDefinitionId(
    selectedDefinitionId,
    definitionsQuery.data,
  );
  const selectedDefinitionSummary =
    resolvedDefinitionId !== null
      ? definitionsQuery.data?.find(
          (definition) => definition.definition_id === resolvedDefinitionId,
        )
      : undefined;
  const definitionDetailKey =
    resolvedDefinitionId !== null
      ? circuitDefinitionDetailKey(resolvedDefinitionId)
      : null;
  const definitionDetailQuery = useSWR(
    definitionDetailKey,
    () =>
      resolvedDefinitionId !== null
        ? getCircuitDefinition(resolvedDefinitionId)
        : Promise.resolve(undefined),
  );
  const activeDefinition = definitionDetailQuery.data;
  const hasAttachedDefinition =
    resolvedDefinitionId !== null &&
    activeDefinition?.definition_id === resolvedDefinitionId;
  const activeDatasetId = activeDatasetState.activeDataset?.datasetId ?? null;
  const pageContext = {
    definitionId: resolvedDefinitionId,
    datasetId: activeDatasetId,
  } as const;

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
  const resolvedTaskId = selectedTaskId ?? latestSimulationTaskFromQueue?.taskId ?? null;
  const taskKey = resolvedTaskId ? taskDetailKey(resolvedTaskId) : null;
  const taskDetailQuery = useSWR(
    taskKey,
    () => (resolvedTaskId ? getTask(resolvedTaskId) : Promise.resolve(undefined)),
    {
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return shouldRefreshTaskDetail(currentData) ? 2_000 : 0;
      },
    },
  );
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
  const upstreamSimulationTaskKey = upstreamSimulationTaskId
    ? taskDetailKey(upstreamSimulationTaskId)
    : null;
  const upstreamSimulationTaskQuery = useSWR(
    upstreamSimulationTaskKey,
    () =>
      upstreamSimulationTaskId
        ? getTask(upstreamSimulationTaskId)
        : Promise.resolve(undefined),
    {
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return shouldRefreshTaskDetail(currentData) ? 2_000 : 0;
      },
    },
  );
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
  const simulationStageTaskKey = latestSimulationStageTask
    ? taskDetailKey(latestSimulationStageTask.taskId)
    : null;
  const simulationStageTaskQuery = useSWR(
    simulationStageTaskKey,
    () =>
      latestSimulationStageTask
        ? getTask(latestSimulationStageTask.taskId)
        : Promise.resolve(undefined),
    {
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return shouldRefreshTaskDetail(currentData) ? 2_000 : 0;
      },
    },
  );
  const latestSimulationTaskDetail =
    activeTask?.taskId === latestSimulationStageTask?.taskId
      ? activeTask
      : upstreamSimulationTaskQuery.data?.taskId === latestSimulationStageTask?.taskId
        ? upstreamSimulationTaskQuery.data
        : simulationStageTaskQuery.data;
  const postProcessingStageTaskKey = latestPostProcessingTask
    ? taskDetailKey(latestPostProcessingTask.taskId)
    : null;
  const postProcessingStageTaskQuery = useSWR(
    postProcessingStageTaskKey,
    () =>
      latestPostProcessingTask
        ? getTask(latestPostProcessingTask.taskId)
        : Promise.resolve(undefined),
    {
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return shouldRefreshTaskDetail(currentData) ? 2_000 : 0;
      },
    },
  );
  const latestPostProcessingTaskDetail =
    activeTask?.taskId === latestPostProcessingTask?.taskId
      ? activeTask
      : postProcessingStageTaskQuery.data;

  async function refreshSimulationWorkflow() {
    await Promise.all([
      definitionsQuery.mutate(),
      definitionDetailQuery.mutate(),
      taskQueueState.refreshTaskQueue().then(() => undefined),
      taskDetailQuery.mutate(),
      upstreamSimulationTaskQuery.mutate(),
      simulationStageTaskQuery.mutate(),
      postProcessingStageTaskQuery.mutate(),
      activeDatasetState.refreshActiveDataset(),
    ]);
  }

  return {
    session,
    activeDatasetState,
    taskQueueState,
    definitions: definitionsQuery.data,
    definitionsError: definitionsQuery.error as Error | undefined,
    isDefinitionsLoading: definitionsQuery.isLoading,
    resolvedDefinitionId,
    selectedDefinitionSummary,
    activeDefinition,
    activeDefinitionError: definitionDetailQuery.error as Error | undefined,
    isDefinitionTransitioning:
      resolvedDefinitionId !== null &&
      (!hasAttachedDefinition || definitionDetailQuery.isLoading),
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
    refreshSimulationWorkflow,
    refreshDefinitions: definitionsQuery.mutate,
    refreshTaskQueue: taskQueueState.refreshTaskQueue,
    refreshActiveTask: taskDetailQuery.mutate,
  };
}

function shouldRefreshTaskDetail(task: TaskDetail) {
  return (
    task.status === "queued" ||
    task.status === "running" ||
    (task.status === "completed" && !hasSimulationTaskResult(task))
  );
}
