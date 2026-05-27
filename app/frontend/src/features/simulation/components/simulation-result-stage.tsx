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
import { formatSimulationTaskStatusLabel } from "@/features/simulation/lib/workflow";
import { SurfaceTag } from "@/features/shared/components/surface-kit";
import type { TaskDetail, TaskSummary } from "@/lib/api/tasks";

export function SimulationResultStage({
  state,
  errorMessage,
  displayedSimulationStageAuthority,
  displayedSimulationTaskDetail,
  attachedSimulationStageTask,
  simulationResultReady,
  activeDatasetId,
  resolvedTaskId,
  attachTask,
}: Readonly<{
  state: WorkflowStageState;
  errorMessage: string | null;
  displayedSimulationStageAuthority: TaskSummary | undefined;
  displayedSimulationTaskDetail: TaskDetail | undefined;
  attachedSimulationStageTask: TaskSummary | undefined;
  simulationResultReady: boolean;
  activeDatasetId: string | null;
  resolvedTaskId: number | null;
  attachTask: (taskId: number) => void;
}>) {
  return (
    <WorkflowStageSection
      step={3}
      title="Simulation Result"
      description="Inspect saved simulation output."
      status={state}
    >
      {(errorMessage || (state.label !== "Completed" && state.label !== "Not started")) ? (
        <StageNotice
          tone={state.tone}
          title={`Simulation Result · ${state.label}`}
          message={errorMessage ? `${state.message} ${errorMessage}` : state.message}
        />
      ) : null}

      {displayedSimulationStageAuthority ? (
        <>
          <div className="rounded-[0.95rem] border border-border bg-background px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="min-w-0 text-sm leading-6 text-muted-foreground">
                {displayedSimulationTaskDetail?.progress.summary ??
                  displayedSimulationStageAuthority.summary}
              </p>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <SurfaceTag tone="default">
                  {attachedSimulationStageTask ? "Attached" : "Latest"} · Task #
                  {displayedSimulationStageAuthority.taskId}
                </SurfaceTag>
                <SurfaceTag tone={taskStatusTone(displayedSimulationStageAuthority.status)}>
                  {formatSimulationTaskStatusLabel(displayedSimulationStageAuthority.status)}
                </SurfaceTag>
                <SurfaceTag tone={simulationResultReady ? "success" : "default"}>
                  {simulationResultReady ? "Ready" : "Pending"}
                </SurfaceTag>
                <StageTaskActions
                  task={displayedSimulationStageAuthority}
                  resolvedTaskId={resolvedTaskId}
                  onViewTask={attachTask}
                />
              </div>
            </div>
          </div>

          {displayedSimulationTaskDetail && simulationResultReady ? (
            <SimulationResultExplorer
              task={displayedSimulationTaskDetail}
              activeDatasetId={activeDatasetId}
            />
          ) : null}

          {displayedSimulationTaskDetail && !simulationResultReady ? (
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
              Result pending for task #{displayedSimulationTaskDetail.taskId}.
            </div>
          ) : null}
        </>
      ) : null}
      {!displayedSimulationStageAuthority ? (
        <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
          No simulation result yet.
        </div>
      ) : null}
    </WorkflowStageSection>
  );
}
