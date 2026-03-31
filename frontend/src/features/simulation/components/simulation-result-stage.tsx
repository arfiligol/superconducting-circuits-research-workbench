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
      description="Browse the latest simulation result, inspect the current trace, and save it when you want to carry it forward."
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
          <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  {attachedSimulationStageTask ? "Attached Run" : "Latest Run"}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {displayedSimulationTaskDetail?.progress.summary ??
                    displayedSimulationStageAuthority.summary}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {simulationResultReady
                    ? "This persisted result stays attached to the current page context and is ready for Post Processing."
                    : "The explorer and save target appear as soon as the backend publishes the persisted result handoff."}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <SurfaceTag tone="default">
                  Task #{displayedSimulationStageAuthority.taskId}
                </SurfaceTag>
                <SurfaceTag tone={taskStatusTone(displayedSimulationStageAuthority.status)}>
                  {formatSimulationTaskStatusLabel(displayedSimulationStageAuthority.status)}
                </SurfaceTag>
                <SurfaceTag tone={simulationResultReady ? "success" : "default"}>
                  {simulationResultReady ? "Explorer ready" : "Preparing result"}
                </SurfaceTag>
                <StageTaskActions
                  task={displayedSimulationStageAuthority}
                  resolvedTaskId={resolvedTaskId}
                  onViewTask={attachTask}
                />
              </div>
            </div>
          </div>

          {displayedSimulationTaskDetail &&
          (displayedSimulationTaskDetail.status === "queued" ||
            displayedSimulationTaskDetail.status === "running") ? (
            <StageNotice
              tone="primary"
              title="Live result refresh"
              message="This stage refreshes every 2 seconds while the run is active, then attaches the saved result as soon as it is ready."
            />
          ) : null}

          {displayedSimulationTaskDetail && simulationResultReady ? (
            <SimulationResultExplorer
              task={displayedSimulationTaskDetail}
              activeDatasetId={activeDatasetId}
            />
          ) : null}

          {displayedSimulationTaskDetail && !simulationResultReady ? (
            <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
              Persisted refs and task result handles stay available after the result handoff is ready.
            </div>
          ) : null}
        </>
      ) : null}
    </WorkflowStageSection>
  );
}
