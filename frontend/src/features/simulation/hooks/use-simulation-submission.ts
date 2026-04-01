"use client";

import type { UseFormReturn } from "react-hook-form";

import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";
import type { PostProcessingStepDraft } from "@/features/simulation/lib/post-processing-basis";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import { useSimulationSubmissionDraftBuilder } from "@/features/simulation/hooks/use-simulation-submission-draft-builder";
import {
  useSimulationTaskSubmitMutation,
  type SimulationTaskMutationStatus,
} from "@/features/simulation/hooks/use-simulation-task-submit-mutation";
import type { TaskDetail } from "@/lib/api/tasks";
import type { SimulationStageKind } from "@/features/simulation/lib/workflow";

type UseSimulationSubmissionOptions = Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  postProcessingSteps: readonly PostProcessingStepDraft[];
  resolvedDefinitionId: CircuitDefinitionId | null;
  selectedDefinitionName: string | null;
  activeDefinitionName: string | null;
  displayedSimulationStageTaskId: number | null;
  onTaskAttached: (taskId: number) => void;
}>;

export function useSimulationSubmission({
  form,
  postProcessingSteps,
  resolvedDefinitionId,
  selectedDefinitionName,
  activeDefinitionName,
  displayedSimulationStageTaskId,
  onTaskAttached,
}: UseSimulationSubmissionOptions) {
  const taskSubmitMutation = useSimulationTaskSubmitMutation({
    resolvedDefinitionId,
    selectedDefinitionName,
    activeDefinitionName,
    onTaskAttached,
  });
  const submissionDraftBuilder = useSimulationSubmissionDraftBuilder({
    form,
    postProcessingSteps,
    displayedSimulationStageTaskId,
  });

  async function submit(kind: SimulationStageKind): Promise<TaskDetail | null> {
    const submissionDraft = await submissionDraftBuilder.buildSubmissionDraft(kind);
    if (!submissionDraft) {
      return null;
    }

    return taskSubmitMutation.submitTaskDraft(submissionDraft);
  }

  return {
    taskMutationStatus: taskSubmitMutation.taskMutationStatus satisfies SimulationTaskMutationStatus,
    simulationSetupBuildError: submissionDraftBuilder.simulationSetupBuildError,
    postProcessingBuildError: submissionDraftBuilder.postProcessingBuildError,
    clearTaskMutationStatus: taskSubmitMutation.clearTaskMutationStatus,
    clearBuildErrors: submissionDraftBuilder.clearBuildErrors,
    submit,
  };
}
