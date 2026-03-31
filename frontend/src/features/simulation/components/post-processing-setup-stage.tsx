"use client";

import { LoaderCircle, Plus, Trash2, WandSparkles } from "lucide-react";
import type { UseFormReturn } from "react-hook-form";

import {
  CompactField,
  StageNotice,
  StageTaskActions,
  WorkflowStageSection,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { PostProcessingStepDraft, PostProcessingStepType } from "@/features/simulation/lib/post-processing-basis";
import { isPostProcessingStepTypeAvailable } from "@/features/simulation/lib/post-processing-basis";
import type { SimulationRequestValues } from "@/features/simulation/lib/request-form";
import {
  taskStatusTone,
  type WorkflowStageState,
} from "@/features/simulation/lib/stage-state";
import { formatSimulationTaskStatusLabel } from "@/features/simulation/lib/workflow";
import { AppInlineSelect, type AppSelectOption } from "@/features/shared/components/app-select";
import { SurfaceTag, cx } from "@/features/shared/components/surface-kit";
import type { TaskSummary } from "@/lib/api/tasks";

type PostProcessingStepContext = Readonly<{
  basisLabels: readonly string[];
  coordinatePortOptions: readonly AppSelectOption[];
  basisOptions: readonly AppSelectOption[];
}>;

export function PostProcessingSetupStage({
  state,
  blockedReason,
  displayedSimulationStageAuthority,
  latestPostProcessingStageAuthority,
  latestPostProcessingTaskDetail,
  postProcessingResultReady,
  postProcessingSteps,
  postProcessingPipelineContext,
  postProcessingStepContexts,
  initialPostProcessingStepContext,
  newPostProcessingStepType,
  setNewPostProcessingStepType,
  postProcessingStepTypeOptions,
  appendPostProcessingStep,
  removePostProcessingStep,
  updateCoordinateTransformStep,
  toggleKronReductionKeepLabel,
  updatePostProcessingStepType,
  postProcessingBuildError,
  taskMutationState,
  form,
  onSubmit,
  attachTask,
  resolvedTaskId,
}: Readonly<{
  state: WorkflowStageState;
  blockedReason: string | null;
  displayedSimulationStageAuthority: TaskSummary | undefined;
  latestPostProcessingStageAuthority: TaskSummary | undefined;
  latestPostProcessingTaskDetail: Readonly<{ progress: { summary: string } }> | undefined;
  postProcessingResultReady: boolean;
  postProcessingSteps: readonly PostProcessingStepDraft[];
  postProcessingPipelineContext: PostProcessingStepContext;
  postProcessingStepContexts: ReadonlyMap<string, PostProcessingStepContext>;
  initialPostProcessingStepContext: PostProcessingStepContext;
  newPostProcessingStepType: PostProcessingStepType;
  setNewPostProcessingStepType: (value: PostProcessingStepType) => void;
  postProcessingStepTypeOptions: readonly AppSelectOption[];
  appendPostProcessingStep: (value: PostProcessingStepType) => void;
  removePostProcessingStep: (stepId: string) => void;
  updateCoordinateTransformStep: (
    stepId: string,
    field: "portA" | "portB",
    value: string,
  ) => void;
  toggleKronReductionKeepLabel: (stepId: string, label: string) => void;
  updatePostProcessingStepType: (stepId: string, value: PostProcessingStepType) => void;
  postProcessingBuildError: string | null;
  taskMutationState: "idle" | "submitting" | "success" | "error";
  form: UseFormReturn<SimulationRequestValues>;
  onSubmit: () => void;
  attachTask: (taskId: number) => void;
  resolvedTaskId: number | null;
}>) {
  return (
    <WorkflowStageSection
      step={4}
      title="Post Processing Setup"
      description="Author the processing steps, keep their order intentional, and launch the next run."
      status={state}
      actions={
        displayedSimulationStageAuthority ? (
          <SurfaceTag tone="default">
            Simulation #{displayedSimulationStageAuthority.taskId}
          </SurfaceTag>
        ) : null
      }
    >
      {blockedReason ? (
        <StageNotice
          tone={state.tone}
          title={`Post Processing Setup · ${state.label}`}
          message={state.message}
        />
      ) : null}

      <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Steps
            </p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Choose a step type, then add it in the order it should run.
            </p>
          </div>
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <AppInlineSelect
              ariaLabel="Post-processing step type to add"
              value={newPostProcessingStepType}
              onChange={(nextValue) => {
                setNewPostProcessingStepType(nextValue as PostProcessingStepType);
              }}
              options={postProcessingStepTypeOptions}
              className="sm:min-w-[280px]"
            />
            <button
              type="button"
              onClick={() => {
                appendPostProcessingStep(newPostProcessingStepType);
              }}
              disabled={
                !isPostProcessingStepTypeAvailable(
                  newPostProcessingStepType,
                  postProcessingPipelineContext,
                )
              }
              className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Step
            </button>
          </div>
        </div>

        {postProcessingSteps.length === 0 ? (
          <div className="mt-4 rounded-[0.95rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
            No steps yet. Add the transformations you want to apply after the simulation result.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {postProcessingSteps.map((step, index) => {
              const stepContext =
                postProcessingStepContexts.get(step.id) ?? initialPostProcessingStepContext;
              const stepTypeOptions: readonly AppSelectOption[] = [
                {
                  value: "coordinate_transform",
                  label: "Coordinate Transformation",
                  disabled: !isPostProcessingStepTypeAvailable(
                    "coordinate_transform",
                    stepContext,
                  ),
                },
                {
                  value: "kron_reduction",
                  label: "Kron Reduction",
                  disabled: !isPostProcessingStepTypeAvailable("kron_reduction", stepContext),
                },
              ];

              return (
                <div
                  key={step.id}
                  className="rounded-[0.95rem] border border-border bg-surface px-4 py-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-foreground">Step {index + 1}</p>
                        <SurfaceTag tone="default">Step {index + 1}</SurfaceTag>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {step.type === "coordinate_transform"
                          ? "Build a common/differential transform from two ports."
                          : "Reduce the basis to the ports you want to keep."}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        removePostProcessingStep(step.id);
                      }}
                      className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-rose-300 hover:bg-rose-50 dark:hover:border-rose-400/40 dark:hover:bg-rose-500/10"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Remove
                    </button>
                  </div>

                  <div className="mt-4">
                    <CompactField label="Step Type">
                      <AppInlineSelect
                        ariaLabel={`Post-processing step ${index + 1} type`}
                        value={step.type}
                        onChange={(nextValue) => {
                          updatePostProcessingStepType(
                            step.id,
                            nextValue as PostProcessingStepType,
                          );
                        }}
                        options={stepTypeOptions}
                      />
                    </CompactField>
                  </div>

                  {step.type === "coordinate_transform" ? (
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <CompactField label="Port A">
                        <AppInlineSelect
                          ariaLabel={`Coordinate transform step ${index + 1} port A`}
                          value={step.portA}
                          onChange={(nextValue) => {
                            updateCoordinateTransformStep(step.id, "portA", nextValue);
                          }}
                          options={stepContext.coordinatePortOptions}
                        />
                      </CompactField>
                      <CompactField label="Port B">
                        <AppInlineSelect
                          ariaLabel={`Coordinate transform step ${index + 1} port B`}
                          value={step.portB}
                          onChange={(nextValue) => {
                            updateCoordinateTransformStep(step.id, "portB", nextValue);
                          }}
                          options={stepContext.coordinatePortOptions}
                        />
                      </CompactField>
                    </div>
                  ) : (
                    <div className="mt-4 space-y-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                        Keep Ports
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {stepContext.basisOptions.map((option) => {
                          const isSelected = step.keepLabels.includes(option.value);
                          return (
                            <button
                              key={`${step.id}:${option.value}`}
                              type="button"
                              onClick={() => {
                                toggleKronReductionKeepLabel(step.id, option.value);
                              }}
                              className={cx(
                                "inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition",
                                isSelected
                                  ? "border-primary/35 bg-primary text-primary-foreground"
                                  : "border-border bg-background text-foreground hover:border-primary/35 hover:bg-primary/10",
                              )}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <label className="block rounded-[0.95rem] border border-border bg-surface px-4 py-3">
        <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-muted-foreground">
          Note
        </span>
        <textarea
          {...form.register("postProcessingNote")}
          rows={4}
          placeholder="Optional context for this post-processing run."
          className="w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
        />
      </label>

      {form.formState.errors.postProcessingNote ? (
        <p className="text-sm text-rose-700 dark:text-rose-300">
          {form.formState.errors.postProcessingNote.message}
        </p>
      ) : null}
      {postProcessingBuildError ? (
        <p className="text-sm text-rose-700 dark:text-rose-300">
          {postProcessingBuildError}
        </p>
      ) : null}

      <button
        type="button"
        onClick={onSubmit}
        disabled={taskMutationState === "submitting" || blockedReason !== null}
        className="inline-flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {taskMutationState === "submitting" ? (
          <LoaderCircle className="h-4 w-4 animate-spin" />
        ) : (
          <WandSparkles className="h-4 w-4" />
        )}
        Run Post Processing
      </button>

      {latestPostProcessingStageAuthority ? (
        <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Latest Post Processing Run
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                {latestPostProcessingTaskDetail?.progress.summary ??
                  latestPostProcessingStageAuthority.summary}
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {postProcessingResultReady
                  ? "The processed result is attached and ready to review below."
                  : "The processed result appears below as soon as the downstream run finishes."}
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <SurfaceTag tone="default">
                Task #{latestPostProcessingStageAuthority.taskId}
              </SurfaceTag>
              <SurfaceTag tone={taskStatusTone(latestPostProcessingStageAuthority.status)}>
                {formatSimulationTaskStatusLabel(latestPostProcessingStageAuthority.status)}
              </SurfaceTag>
              <SurfaceTag tone={postProcessingResultReady ? "success" : "default"}>
                {postProcessingResultReady ? "Result ready" : "Processing"}
              </SurfaceTag>
              <StageTaskActions
                task={latestPostProcessingStageAuthority}
                resolvedTaskId={resolvedTaskId}
                onViewTask={attachTask}
              />
            </div>
          </div>
        </div>
      ) : null}
    </WorkflowStageSection>
  );
}
