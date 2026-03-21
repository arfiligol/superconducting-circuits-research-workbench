"use client";

import { useCallback, useState } from "react";
import { useSWRConfig } from "swr";
import type { UseFormReturn } from "react-hook-form";

import {
  circuitDefinitionDetailKey,
  circuitDefinitionsListKey,
  getCircuitDefinition,
  listCircuitDefinitions,
} from "@/features/circuit-definition-editor/lib/api";
import {
  buildSimulationRequestSummary,
  type SimulationStageKind,
} from "@/features/simulation/lib/workflow";
import {
  buildSimulationSetupDraft,
} from "@/features/simulation/lib/setup-form";
import {
  simulationStageFieldNames,
  type SimulationRequestValues,
} from "@/features/simulation/lib/request-form";
import type {
  PostProcessingStepDraft,
} from "@/features/simulation/lib/post-processing-basis";
import {
  getTask,
  submitTask,
  taskDetailKey,
  tasksListKey,
  type PostProcessingSetupDraft,
  type SimulationSetupDraft,
  type TaskDetail,
} from "@/lib/api/tasks";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { useAppSession } from "@/lib/app-state/app-session";
import { useTaskQueue } from "@/lib/app-state/task-queue";
import { ApiError } from "@/lib/api/client";

export type SimulationTaskMutationStatus = Readonly<{
  state: "idle" | "submitting" | "success" | "error";
  message: string | null;
}>;

type SubmitSimulationTaskInput = Readonly<{
  kind: SimulationStageKind;
  note: string;
  simulationSetup?: SimulationSetupDraft | null;
  postProcessingSetup?: PostProcessingSetupDraft | null;
  upstreamTaskId?: number | null;
}>;

type UseSimulationSubmissionOptions = Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  postProcessingSteps: readonly PostProcessingStepDraft[];
  resolvedDefinitionId: number | null;
  selectedDefinitionName: string | null;
  activeDefinitionName: string | null;
  displayedSimulationStageTaskId: number | null;
  buildPostProcessingSetupDraft: (
    steps: readonly PostProcessingStepDraft[],
  ) => PostProcessingSetupDraft;
  onTaskAttached: (taskId: number) => void;
}>;

function describeSubmitError(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const retryHint = error.retryable === true ? " Retry is available." : "";
    const debugHint = error.debugRef ? ` Ref: ${error.debugRef}.` : "";
    return `${error.message}${retryHint}${debugHint}`;
  }

  return error instanceof Error ? error.message : fallback;
}

export function useSimulationSubmission({
  form,
  postProcessingSteps,
  resolvedDefinitionId,
  selectedDefinitionName,
  activeDefinitionName,
  displayedSimulationStageTaskId,
  buildPostProcessingSetupDraft,
  onTaskAttached,
}: UseSimulationSubmissionOptions) {
  const { mutate } = useSWRConfig();
  const { session } = useAppSession();
  const activeDatasetState = useActiveDataset();
  const taskQueueState = useTaskQueue();
  const [taskMutationStatus, setTaskMutationStatus] = useState<SimulationTaskMutationStatus>({
    state: "idle",
    message: null,
  });
  const [simulationSetupBuildError, setSimulationSetupBuildError] = useState<string | null>(null);
  const [postProcessingBuildError, setPostProcessingBuildError] = useState<string | null>(null);

  const clearTaskMutationStatus = useCallback(() => {
    setTaskMutationStatus({ state: "idle", message: null });
  }, []);

  const clearBuildErrors = useCallback(() => {
    setSimulationSetupBuildError(null);
    setPostProcessingBuildError(null);
  }, []);

  const verifySelectedDefinition = useCallback(
    async (nextDefinitionId: number) => {
      const refreshedDefinitions = await listCircuitDefinitions();
      await mutate(circuitDefinitionsListKey, refreshedDefinitions, { revalidate: false });

      if (!refreshedDefinitions.some((definition) => definition.definition_id === nextDefinitionId)) {
        throw new Error(
          `Definition #${nextDefinitionId} is no longer available. Refresh the workflow and choose a visible definition before submitting a run.`,
        );
      }

      try {
        const refreshedDefinition = await getCircuitDefinition(nextDefinitionId);
        await mutate(circuitDefinitionDetailKey(nextDefinitionId), refreshedDefinition, {
          revalidate: false,
        });
        return refreshedDefinition;
      } catch {
        throw new Error(
          `Definition #${nextDefinitionId} is unavailable right now. Refresh the workflow and choose a visible definition before submitting a run.`,
        );
      }
    },
    [mutate],
  );

  const submitSimulationTask = useCallback(
    async ({
      kind,
      note,
      simulationSetup,
      postProcessingSetup,
      upstreamTaskId,
    }: SubmitSimulationTaskInput): Promise<TaskDetail> => {
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

      let verifiedDefinitionName = selectedDefinitionName ?? activeDefinitionName ?? null;
      try {
        const verifiedDefinition = await verifySelectedDefinition(resolvedDefinitionId);
        verifiedDefinitionName = verifiedDefinition.name;
      } catch (error) {
        const message = describeSubmitError(
          error,
          "Unable to verify the selected definition.",
        );
        setTaskMutationStatus({ state: "error", message });
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
            definitionName: verifiedDefinitionName,
            datasetId,
            datasetName: activeDatasetState.activeDataset?.name ?? null,
            note,
          }),
          simulation_setup: simulationSetup ?? null,
          post_processing_setup: postProcessingSetup ?? null,
          upstream_task_id: upstreamTaskId ?? null,
        });

        await Promise.all([
          mutate(tasksListKey),
          mutate(taskDetailKey(task.taskId), task, { revalidate: false }),
          taskQueueState.refreshTaskQueue(),
        ]);

        onTaskAttached(task.taskId);
        setTaskMutationStatus({
          state: "success",
          message:
            kind === "simulation"
              ? `Simulation task #${task.taskId} submitted.`
              : `Post-processing task #${task.taskId} submitted.`,
        });

        return task;
      } catch (error) {
        if (error instanceof ApiError && error.errorCode === "task_enqueue_failed") {
          const taskId =
            typeof (error.details as { task_id?: unknown } | undefined)?.task_id === "number"
              ? (error.details as { task_id: number }).task_id
              : null;

          if (taskId !== null) {
            await Promise.all([
              taskQueueState.refreshTaskQueue(),
              getTask(taskId)
                .then((task) => mutate(taskDetailKey(taskId), task, { revalidate: false }))
                .catch(() => undefined),
            ]);
            onTaskAttached(taskId);
          }
        }

        const message = describeSubmitError(error, "Unable to submit the simulation task.");
        setTaskMutationStatus({ state: "error", message });
        throw error;
      }
    },
    [
      activeDatasetState.activeDataset,
      activeDefinitionName,
      mutate,
      onTaskAttached,
      resolvedDefinitionId,
      selectedDefinitionName,
      session?.canSubmitTasks,
      taskQueueState,
      verifySelectedDefinition,
    ],
  );

  const submit = useCallback(
    async (kind: SimulationStageKind) => {
      const fieldNames =
        kind === "simulation"
          ? simulationStageFieldNames
          : (["postProcessingNote"] as const);
      const fieldName = kind === "simulation" ? "simulationNote" : "postProcessingNote";
      const isValid = await form.trigger(fieldNames);
      if (!isValid) {
        return null;
      }

      clearBuildErrors();
      const values = form.getValues();
      let simulationSetup = null;
      let postProcessingSetup = null;
      try {
        simulationSetup = kind === "simulation" ? buildSimulationSetupDraft(values) : null;
        postProcessingSetup =
          kind === "post_processing"
            ? buildPostProcessingSetupDraft(postProcessingSteps)
            : null;
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to build and submit workflow setup.";
        if (kind === "simulation") {
          setSimulationSetupBuildError(message);
        } else {
          setPostProcessingBuildError(message);
        }
        return null;
      }

      return submitSimulationTask({
        kind,
        note: values[fieldName],
        simulationSetup,
        postProcessingSetup,
        upstreamTaskId: kind === "post_processing" ? displayedSimulationStageTaskId : null,
      });
    },
    [
      buildPostProcessingSetupDraft,
      clearBuildErrors,
      displayedSimulationStageTaskId,
      form,
      postProcessingSteps,
      submitSimulationTask,
    ],
  );

  return {
    taskMutationStatus,
    simulationSetupBuildError,
    postProcessingBuildError,
    clearTaskMutationStatus,
    clearBuildErrors,
    submit,
  };
}
