"use client";

import { useCallback, useState } from "react";
import type { UseFormReturn } from "react-hook-form";

import type { PostProcessingStepDraft } from "@/features/simulation/lib/post-processing-basis";
import { buildPostProcessingSetupDraft } from "@/features/simulation/lib/post-processing-setup";
import {
  simulationStageFieldNames,
  type SimulationRequestValues,
} from "@/features/simulation/lib/request-form";
import { buildSimulationSetupDraft } from "@/features/simulation/lib/setup-form";
import type { SubmitSimulationTaskInput } from "@/features/simulation/hooks/use-simulation-task-submit-mutation";
import type { SimulationStageKind } from "@/features/simulation/lib/workflow";

type UseSimulationSubmissionDraftBuilderOptions = Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  postProcessingSteps: readonly PostProcessingStepDraft[];
  displayedSimulationStageTaskId: number | null;
}>;

export function useSimulationSubmissionDraftBuilder({
  form,
  postProcessingSteps,
  displayedSimulationStageTaskId,
}: UseSimulationSubmissionDraftBuilderOptions) {
  const [simulationSetupBuildError, setSimulationSetupBuildError] = useState<string | null>(null);
  const [postProcessingBuildError, setPostProcessingBuildError] = useState<string | null>(null);

  const clearBuildErrors = useCallback(() => {
    setSimulationSetupBuildError(null);
    setPostProcessingBuildError(null);
  }, []);

  const buildSubmissionDraft = useCallback(
    async (kind: SimulationStageKind): Promise<SubmitSimulationTaskInput | null> => {
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

      try {
        return {
          kind,
          note: values[fieldName],
          simulationSetup: kind === "simulation" ? buildSimulationSetupDraft(values) : null,
          postProcessingSetup:
            kind === "post_processing"
              ? buildPostProcessingSetupDraft(postProcessingSteps)
              : null,
          upstreamTaskId: kind === "post_processing" ? displayedSimulationStageTaskId : null,
        };
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
    },
    [clearBuildErrors, displayedSimulationStageTaskId, form, postProcessingSteps],
  );

  return {
    simulationSetupBuildError,
    postProcessingBuildError,
    clearBuildErrors,
    buildSubmissionDraft,
  };
}
