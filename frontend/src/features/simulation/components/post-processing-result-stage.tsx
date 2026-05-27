"use client";

import { SimulationResultExplorer } from "@/features/simulation/components/simulation-result-explorer";
import {
  StageNotice,
  StageTaskActions,
  WorkflowStageSection,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import {
  taskStatusTone,
  type WorkflowStageState,
} from "@/features/simulation/lib/stage-state";
import { formatSimulationTaskStatusLabel, type SimulationTaskResultSummary } from "@/features/simulation/lib/workflow";
import { SurfaceTag } from "@/features/shared/components/surface-kit";
import type { TaskDetail, TaskSummary } from "@/lib/api/tasks";

export function PostProcessingResultStage({
  state,
  errorMessage,
  latestPostProcessingStageAuthority,
  latestPostProcessingTaskDetail,
  postProcessingResultReady,
  activeDatasetId,
  explicitUpstreamSimulationTaskId,
  displayedSimulationStageAuthority,
  postProcessingStepCount,
  postProcessingResultSummary,
  resolvedTaskId,
  attachTask,
}: Readonly<{
  state: WorkflowStageState;
  errorMessage: string | null;
  latestPostProcessingStageAuthority: TaskSummary | undefined;
  latestPostProcessingTaskDetail: TaskDetail | undefined;
  postProcessingResultReady: boolean;
  activeDatasetId: string | null;
  explicitUpstreamSimulationTaskId: number | null;
  displayedSimulationStageAuthority: TaskSummary | undefined;
  postProcessingStepCount: number;
  postProcessingResultSummary: SimulationTaskResultSummary;
  resolvedTaskId: number | null;
  attachTask: (taskId: number) => void;
}>) {
  return (
    <WorkflowStageSection
      step={5}
      title="Post Processing Result"
      description="Inspect processed output."
      status={state}
      actions={
        latestPostProcessingStageAuthority ? (
          <SurfaceTag tone="default">
            Task #{latestPostProcessingStageAuthority.taskId}
          </SurfaceTag>
        ) : explicitUpstreamSimulationTaskId !== null ? (
          <SurfaceTag tone="default">
            Simulation #{explicitUpstreamSimulationTaskId}
          </SurfaceTag>
        ) : displayedSimulationStageAuthority ? (
          <SurfaceTag tone="default">
            Simulation #{displayedSimulationStageAuthority.taskId}
          </SurfaceTag>
        ) : null
      }
    >
      {(errorMessage || (state.label !== "Completed" && state.label !== "Not started")) ? (
        <StageNotice
          tone={state.tone}
          title={`Post Processing Result · ${state.label}`}
          message={errorMessage ? `${state.message} ${errorMessage}` : state.message}
        />
      ) : null}

      {latestPostProcessingTaskDetail && postProcessingResultReady ? (
        <SimulationResultExplorer
          task={latestPostProcessingTaskDetail}
          activeDatasetId={activeDatasetId}
        />
      ) : null}

      {latestPostProcessingStageAuthority ? (
        <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Latest Result
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                {latestPostProcessingTaskDetail?.progress.summary ??
                  latestPostProcessingStageAuthority.summary}
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
                {postProcessingResultReady ? "Ready" : "Pending"}
              </SurfaceTag>
              <StageTaskActions
                task={latestPostProcessingStageAuthority}
                resolvedTaskId={resolvedTaskId}
                onViewTask={attachTask}
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <SurfaceTag tone="default">
              {postProcessingStepCount} step{postProcessingStepCount === 1 ? "" : "s"}
            </SurfaceTag>
            {explicitUpstreamSimulationTaskId !== null ? (
              <SurfaceTag tone="default">
                Simulation #{explicitUpstreamSimulationTaskId}
              </SurfaceTag>
            ) : displayedSimulationStageAuthority ? (
              <SurfaceTag tone="default">
                Simulation #{displayedSimulationStageAuthority.taskId}
              </SurfaceTag>
            ) : null}
            {postProcessingResultSummary.analysisRunId !== null ? (
              <SurfaceTag tone="success">
                Analysis Run {postProcessingResultSummary.analysisRunId}
              </SurfaceTag>
            ) : null}
          </div>

          <p className="mt-4 text-sm leading-6 text-muted-foreground">
            {postProcessingResultSummary.resultHandleCount} result handle
            {postProcessingResultSummary.resultHandleCount === 1 ? "" : "s"} ·{" "}
            {postProcessingResultSummary.materializedHandleCount} materialized ·{" "}
            {postProcessingResultSummary.hasTracePayload ? "trace payload attached" : "trace payload pending"}
          </p>
        </div>
      ) : null}
    </WorkflowStageSection>
  );
}
