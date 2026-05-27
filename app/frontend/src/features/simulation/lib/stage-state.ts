import {
  formatSimulationTaskStatusLabel,
  hasSimulationTaskResult,
} from "@/features/simulation/lib/workflow";
import type {
  TaskDetail,
  TaskExecutionStatus,
  TaskSummary,
} from "@/lib/api/tasks";

export type StageTone = "default" | "primary" | "success" | "warning" | "error";

export type WorkflowStageState = Readonly<{
  label: string;
  tone: StageTone;
  message: string;
}>;

export function taskStatusTone(status: TaskExecutionStatus): StageTone {
  if (status === "completed") {
    return "success";
  }

  if (
    status === "queued" ||
    status === "dispatching" ||
    status === "running" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  ) {
    return "primary";
  }

  if (status === "failed" || status === "cancelled" || status === "terminated") {
    return "warning";
  }

  return "default";
}

export function resolveSetupStageState(input: Readonly<{
  stageLabel: string;
  blockedReason: string | null;
  latestTask: TaskSummary | undefined;
}>): WorkflowStageState {
  if (input.blockedReason) {
    return {
      label: "Blocked",
      tone: "warning",
      message: input.blockedReason,
    };
  }

  if (!input.latestTask) {
    return {
      label: "Not started",
      tone: "default",
      message: `${input.stageLabel} has not been submitted yet.`,
    };
  }

  if (input.latestTask.status === "completed") {
    return {
      label: "Completed",
      tone: "success",
      message: `Latest ${input.stageLabel.toLowerCase()} run completed successfully. You can review the result or launch another run.`,
    };
  }

  const statusLabel = formatSimulationTaskStatusLabel(input.latestTask.status);
  return {
    label: statusLabel,
    tone: taskStatusTone(input.latestTask.status),
    message: `Latest ${input.stageLabel.toLowerCase()} task #${input.latestTask.taskId} is ${statusLabel.toLowerCase()}.`,
  };
}

export function resolveResultStageState(input: Readonly<{
  stageLabel: string;
  blockedReason?: string | null;
  latestTask: TaskSummary | undefined;
  detail: TaskDetail | undefined;
  hasResult: boolean;
}>): WorkflowStageState {
  if (input.blockedReason) {
    return {
      label: "Blocked",
      tone: "warning",
      message: input.blockedReason,
    };
  }

  if (!input.latestTask) {
    return {
      label: "Not started",
      tone: "default",
      message: `${input.stageLabel} is still waiting for its first run.`,
    };
  }

  if (input.latestTask.status === "completed") {
    if (input.hasResult) {
      return {
        label: "Completed",
        tone: "success",
        message: `Latest ${input.stageLabel.toLowerCase()} output is ready to inspect.`,
      };
    }

    return {
      label: "Completed",
      tone: "warning",
      message: `Latest ${input.stageLabel.toLowerCase()} task completed, but persisted outputs are not available yet.`,
    };
  }

  const statusLabel = formatSimulationTaskStatusLabel(input.latestTask.status);
  const progressSummary =
    input.detail?.progress.summary ?? input.detail?.dispatch?.status ?? input.latestTask.summary;

  return {
    label: statusLabel,
    tone: taskStatusTone(input.latestTask.status),
    message: `Latest ${input.stageLabel.toLowerCase()} task #${input.latestTask.taskId} is ${statusLabel.toLowerCase()}. ${progressSummary}`,
  };
}

export function shouldRefreshSimulationTaskDetail(task: TaskDetail) {
  return (
    task.status === "queued" ||
    task.status === "claimed" ||
    task.status === "running" ||
    task.status === "staging_result" ||
    task.status === "publishing" ||
    (task.status === "completed" && !hasSimulationTaskResult(task))
  );
}
