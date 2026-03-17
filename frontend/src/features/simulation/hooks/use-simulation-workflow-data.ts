"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import {
  circuitDefinitionDetailKey,
  circuitDefinitionsListKey,
  getCircuitDefinition,
  listCircuitDefinitions,
} from "@/features/circuit-definition-editor/lib/api";
import { resolveSimulationDefinitionId } from "@/features/simulation/lib/definition-id";
import {
  buildSimulationRequestSummary,
  filterSimulationTasksByContext,
  resolveLatestSimulationStageTaskInContext,
  resolveLatestSimulationTaskInContext,
} from "@/features/simulation/lib/workflow";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { useAppSession } from "@/lib/app-state/app-session";
import { useTaskQueue } from "@/lib/app-state/task-queue";
import {
  getTask,
  normalizeTaskSummary,
  submitTask,
  taskDetailKey,
  tasksListKey,
  type TaskDetail,
} from "@/lib/api/tasks";

type TaskMutationStatus = Readonly<{
  state: "idle" | "submitting" | "success" | "error";
  message: string | null;
}>;

type SubmitSimulationTaskInput = Readonly<{
  kind: "simulation" | "post_processing";
  note: string;
}>;

export function useSimulationWorkflowData(
  selectedDefinitionId: number | null,
  selectedTaskId: number | null,
) {
  const { mutate } = useSWRConfig();
  const { session } = useAppSession();
  const activeDatasetState = useActiveDataset();
  const taskQueueState = useTaskQueue();
  const [taskMutationStatus, setTaskMutationStatus] = useState<TaskMutationStatus>({
    state: "idle",
    message: null,
  });

  const definitionsQuery = useSWR(circuitDefinitionsListKey, listCircuitDefinitions);
  const resolvedDefinitionId = resolveSimulationDefinitionId(
    selectedDefinitionId === null ? null : String(selectedDefinitionId),
    definitionsQuery.data,
  );
  const selectedDefinitionSummary =
    typeof resolvedDefinitionId === "number"
      ? definitionsQuery.data?.find(
          (definition) => definition.definition_id === resolvedDefinitionId,
        )
      : undefined;
  const definitionDetailKey =
    typeof resolvedDefinitionId === "number"
      ? circuitDefinitionDetailKey(resolvedDefinitionId)
      : null;
  const definitionDetailQuery = useSWR(
    definitionDetailKey,
    () =>
      typeof resolvedDefinitionId === "number"
        ? getCircuitDefinition(resolvedDefinitionId)
        : Promise.resolve(undefined),
    {
      keepPreviousData: true,
    },
  );
  const activeDefinition = definitionDetailQuery.data;
  const hasAttachedDefinition =
    typeof resolvedDefinitionId === "number" &&
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
  const latestSimulationTask = resolveLatestSimulationTaskInContext(simulationTasks, pageContext);
  const latestSimulationStageTask = resolveLatestSimulationStageTaskInContext(
    simulationTasks,
    "simulation",
    pageContext,
  );
  const latestPostProcessingTask = resolveLatestSimulationStageTaskInContext(
    simulationTasks,
    "post_processing",
    pageContext,
  );
  const resolvedTaskId = selectedTaskId ?? latestSimulationTask?.taskId ?? null;
  const taskKey = resolvedTaskId ? taskDetailKey(resolvedTaskId) : null;
  const taskDetailQuery = useSWR(
    taskKey,
    () => (resolvedTaskId ? getTask(resolvedTaskId) : Promise.resolve(undefined)),
    {
      keepPreviousData: true,
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return currentData.status === "queued" || currentData.status === "running" ? 2_000 : 0;
      },
    },
  );
  const activeTask = taskDetailQuery.data;
  const hasAttachedTask =
    typeof resolvedTaskId === "number" && activeTask?.taskId === resolvedTaskId;
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
      keepPreviousData: true,
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return currentData.status === "queued" || currentData.status === "running" ? 2_000 : 0;
      },
    },
  );
  const latestSimulationTaskDetail =
    activeTask?.taskId === latestSimulationStageTask?.taskId
      ? activeTask
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
      keepPreviousData: true,
      refreshInterval(currentData) {
        if (!currentData) {
          return 5_000;
        }

        return currentData.status === "queued" || currentData.status === "running" ? 2_000 : 0;
      },
    },
  );
  const latestPostProcessingTaskDetail =
    activeTask?.taskId === latestPostProcessingTask?.taskId
      ? activeTask
      : postProcessingStageTaskQuery.data;

  async function submitSimulationTask({
    kind,
    note,
  }: SubmitSimulationTaskInput): Promise<TaskDetail> {
    if (!session?.canSubmitTasks) {
      const error = new Error("This session cannot submit tasks.");
      setTaskMutationStatus({ state: "error", message: error.message });
      throw error;
    }

    if (resolvedDefinitionId === null) {
      const error = new Error("Select a canonical definition before submitting a task.");
      setTaskMutationStatus({ state: "error", message: error.message });
      throw error;
    }

    const datasetId = activeDatasetState.activeDataset?.datasetId ?? null;
    if (!datasetId) {
      const error = new Error("Attach an active dataset before submitting a task.");
      setTaskMutationStatus({ state: "error", message: error.message });
      throw error;
    }

    setTaskMutationStatus({ state: "submitting", message: null });

    try {
      const task = await submitTask({
        kind,
        dataset_id: datasetId,
        definition_id: resolvedDefinitionId,
        summary: buildSimulationRequestSummary({
          kind,
          definitionId: resolvedDefinitionId,
          definitionName: selectedDefinitionSummary?.name ?? null,
          datasetId,
          datasetName: activeDatasetState.activeDataset?.name ?? null,
          note,
        }),
      });

      await Promise.all([
        mutate(tasksListKey),
        mutate(taskDetailKey(task.taskId), task, { revalidate: false }),
        taskQueueState.refreshTaskQueue(),
      ]);

      setTaskMutationStatus({
        state: "success",
        message:
          kind === "simulation"
            ? `Simulation task #${task.taskId} submitted.`
            : `Post-processing task #${task.taskId} submitted.`,
      });

      return task;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to submit the simulation task.";
      setTaskMutationStatus({ state: "error", message });
      throw error;
    }
  }

  function clearTaskMutationStatus() {
    setTaskMutationStatus({ state: "idle", message: null });
  }

  async function refreshSimulationWorkflow() {
    await Promise.all([
      definitionsQuery.mutate(),
      definitionDetailQuery.mutate(),
      taskQueueState.refreshTaskQueue().then(() => undefined),
      taskDetailQuery.mutate(),
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
      typeof resolvedDefinitionId === "number" &&
      (!hasAttachedDefinition || definitionDetailQuery.isLoading),
    simulationTasks,
    currentContextSimulationTasks,
    latestSimulationTask,
    latestSimulationStageTask,
    latestSimulationTaskDetail,
    latestSimulationTaskError: simulationStageTaskQuery.error as Error | undefined,
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
    taskMutationStatus,
    submitSimulationTask,
    clearTaskMutationStatus,
    refreshSimulationWorkflow,
    refreshDefinitions: definitionsQuery.mutate,
    refreshTaskQueue: taskQueueState.refreshTaskQueue,
    refreshActiveTask: taskDetailQuery.mutate,
  };
}
