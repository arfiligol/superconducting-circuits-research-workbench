"use client";

import { LoaderCircle, Play } from "lucide-react";

import { StageTaskActions } from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { SimulationTaskMutationStatus } from "@/features/simulation/hooks/use-simulation-task-submit-mutation";
import {
  taskStatusTone,
  type WorkflowStageState,
} from "@/features/simulation/lib/stage-state";
import { formatSimulationTaskStatusLabel } from "@/features/simulation/lib/workflow";
import { SurfaceTag } from "@/features/shared/components/surface-kit";
import type { TaskDetail, TaskSummary } from "@/lib/api/tasks";

export function SimulationRunStatusPanel({
  state,
  blockedReason,
  buildError,
  taskMutationStatus,
  displayedSimulationStageAuthority,
  displayedSimulationTaskDetail,
  simulationResultReady,
  resolvedTaskId,
  onSubmit,
  attachTask,
}: Readonly<{
  state: WorkflowStageState;
  blockedReason: string | null;
  buildError: string | null;
  taskMutationStatus: SimulationTaskMutationStatus;
  displayedSimulationStageAuthority: TaskSummary | undefined;
  displayedSimulationTaskDetail: TaskDetail | undefined;
  simulationResultReady: boolean;
  resolvedTaskId: number | null;
  onSubmit: () => void;
  attachTask: (taskId: number) => void;
}>) {
  const taskStatusLabel = displayedSimulationStageAuthority
    ? formatSimulationTaskStatusLabel(displayedSimulationStageAuthority.status)
    : null;
  const taskStatusToneValue = displayedSimulationStageAuthority
    ? taskStatusTone(displayedSimulationStageAuthority.status)
    : "default";
  const progressLabel =
    displayedSimulationTaskDetail !== undefined
      ? `${Math.round(displayedSimulationTaskDetail.progress.percentComplete)}%`
      : null;
  const statusMessage =
    buildError ??
    blockedReason ??
    displayedSimulationTaskDetail?.progress.summary ??
    displayedSimulationStageAuthority?.summary ??
    "No simulation run has been submitted for this setup.";

  return (
    <section
      aria-labelledby="simulation-submit-status-title"
      className="rounded-[1rem] border border-border bg-card px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.06)]"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="simulation-submit-status-title" className="text-sm font-semibold text-foreground">
              Submit / Status
            </h2>
            <SurfaceTag tone={state.tone}>{state.label}</SurfaceTag>
            {displayedSimulationStageAuthority ? (
              <SurfaceTag tone="default">
                Task #{displayedSimulationStageAuthority.taskId}
              </SurfaceTag>
            ) : null}
            {taskStatusLabel ? (
              <SurfaceTag tone={taskStatusToneValue}>{taskStatusLabel}</SurfaceTag>
            ) : null}
            {simulationResultReady ? <SurfaceTag tone="success">Result ready</SurfaceTag> : null}
          </div>
          <p
            role={taskMutationStatus.state === "submitting" ? "status" : undefined}
            className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground"
          >
            {statusMessage}
          </p>
          {progressLabel ? (
            <p className="mt-1 text-xs text-muted-foreground">Progress {progressLabel}</p>
          ) : null}
          {taskMutationStatus.state === "error" && taskMutationStatus.message ? (
            <p className="mt-2 text-sm text-rose-700 dark:text-rose-300">
              {taskMutationStatus.message}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {displayedSimulationStageAuthority ? (
            <StageTaskActions
              task={displayedSimulationStageAuthority}
              resolvedTaskId={resolvedTaskId}
              onViewTask={attachTask}
            />
          ) : null}
          <button
            type="button"
            onClick={onSubmit}
            disabled={taskMutationStatus.state === "submitting" || blockedReason !== null}
            className="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {taskMutationStatus.state === "submitting" ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Simulation
          </button>
        </div>
      </div>
    </section>
  );
}
