import type {
  CircuitDefinitionSummary,
} from "@/features/circuit-definition-editor/lib/contracts";
import {
  formatSchemaIdLabel,
  matchesSchemaIdQuery,
  type CircuitDefinitionId,
} from "@/features/circuit-definition-editor/lib/schema-identity";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import {
  normalizeTaskSummary,
  type TaskDetail,
  type TaskExecutionStatus,
  type TaskSummary,
} from "@/lib/api/tasks";

export type SimulationTaskScope = "all" | "definition" | "dataset";
export type SimulationTaskStatusFilter = "all" | "active" | "completed" | "failed";
export type SimulationStageKind = "simulation" | "post_processing";
export type SimulationPageContext = Readonly<{
  definitionId: CircuitDefinitionId | null;
  datasetId: string | null;
}>;

export type SimulationSelectionRecovery = Readonly<{
  tone: "default" | "warning";
  title: string;
  message: string;
}> | null;

export type SimulationTaskSummary = Readonly<{
  total: number;
  activeCount: number;
  completedCount: number;
  failedCount: number;
  resultBackedCount: number;
}>;

export type SimulationTaskAttachmentState = Readonly<{
  isAttached: boolean;
  isStaleSnapshot: boolean;
}>;

export type SimulationTaskResultSummary = Readonly<{
  metadataRecordCount: number;
  resultHandleCount: number;
  materializedHandleCount: number;
  hasTracePayload: boolean;
  traceBatchId: number | null;
  analysisRunId: number | null;
}>;

type FilterSimulationTasksOptions = Readonly<{
  searchQuery: string;
  scope: SimulationTaskScope;
  statusFilter: SimulationTaskStatusFilter;
  selectedDefinitionId: CircuitDefinitionId | null;
  activeDatasetId: string | null;
}>;

function isSimulationLaneTask(task: TaskSummary) {
  return task.kind === "simulation" || task.kind === "post_processing";
}

export function isSimulationTaskActive(status: TaskExecutionStatus) {
  return (
    status === "queued" ||
    status === "claimed" ||
    status === "dispatching" ||
    status === "running" ||
    status === "staging_result" ||
    status === "publishing" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  );
}

export function isSimulationTaskCompleted(status: TaskExecutionStatus) {
  return status === "completed";
}

export function isSimulationTaskTerminal(status: TaskExecutionStatus) {
  return (
    status === "completed" ||
    status === "failed" ||
    status === "cancelled" ||
    status === "terminated"
  );
}

export function formatSimulationTaskStatusLabel(status: TaskExecutionStatus) {
  switch (status) {
    case "queued":
    case "claimed":
    case "dispatching":
      return "Queued";
    case "running":
    case "staging_result":
    case "publishing":
    case "cancellation_requested":
    case "cancelling":
    case "termination_requested":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    case "terminated":
      return "Terminated";
  }
}

function isActiveTask(task: TaskSummary) {
  return isSimulationTaskActive(task.status);
}

function matchesTaskScope(
  task: TaskSummary,
  selectedDefinitionId: CircuitDefinitionId | null,
  activeDatasetId: string | null,
  scope: SimulationTaskScope,
) {
  if (scope === "definition") {
    return selectedDefinitionId === null || task.definitionId === selectedDefinitionId;
  }

  if (scope === "dataset") {
    return activeDatasetId === null || task.datasetId === activeDatasetId;
  }

  return true;
}

function matchesTaskStatus(task: TaskSummary, statusFilter: SimulationTaskStatusFilter) {
  switch (statusFilter) {
    case "active":
      return isActiveTask(task);
    case "completed":
      return task.status === "completed";
    case "failed":
      return task.status === "failed";
    case "all":
    default:
      return true;
  }
}

export function filterSimulationDefinitions(
  definitions: readonly CircuitDefinitionSummary[] | undefined,
  searchQuery: string,
) {
  const normalizedQuery = searchQuery.trim().toLowerCase();

  return (definitions ?? []).filter((definition) => {
    if (!normalizedQuery) {
      return true;
    }

    return (
      definition.name.toLowerCase().includes(normalizedQuery) ||
      matchesSchemaIdQuery(definition.definition_id, normalizedQuery)
    );
  });
}

export function resolveSimulationSelectionRecovery(
  requestedDefinitionId: string | null,
  resolvedDefinitionId: CircuitDefinitionId | null,
  definitions: readonly CircuitDefinitionSummary[] | undefined,
): SimulationSelectionRecovery {
  if (!definitions || definitions.length === 0 || resolvedDefinitionId === null) {
    return null;
  }

  if (requestedDefinitionId === null) {
    return null;
  }

  const parsedDefinitionId = parseSimulationDefinitionIdParam(requestedDefinitionId);
  if (parsedDefinitionId === null) {
    return {
      tone: "warning",
      title: "Invalid URL selection",
      message: `The URL selection "${requestedDefinitionId}" is not a canonical schema ID. Showing ${formatSchemaIdLabel(resolvedDefinitionId)} instead.`,
    };
  }

  const definitionExists = definitions.some(
    (definition) => definition.definition_id === parsedDefinitionId,
  );

  if (!definitionExists) {
    return {
      tone: "warning",
      title: "Definition not found",
      message: `${formatSchemaIdLabel(parsedDefinitionId)} is not available in the current catalog. Reattached to ${formatSchemaIdLabel(resolvedDefinitionId)}.`,
    };
  }

  return null;
}

export function buildSimulationRequestSummary(input: Readonly<{
  kind: "simulation" | "post_processing";
  definitionId: CircuitDefinitionId | null;
  definitionName: string | null;
  datasetId: string | null;
  datasetName: string | null;
  note: string;
}>) {
  const baseLabel =
    input.kind === "simulation" ? "Simulation request" : "Post-processing request";
  const segments = [
    input.definitionName
      ? `${baseLabel} for ${input.definitionName}`
      : `${baseLabel} for ${formatSchemaIdLabel(input.definitionId)}`,
    input.datasetName
      ? `dataset ${input.datasetName}`
      : `dataset ${input.datasetId ?? "unbound"}`,
  ];

  if (input.note.trim().length > 0) {
    segments.push(input.note.trim());
  }

  return segments.join(" · ");
}

export function resolveLatestSimulationTask(
  tasks: readonly TaskSummary[],
): TaskSummary | undefined {
  const simulationTasks = tasks.filter(isSimulationLaneTask);
  return simulationTasks.find(isActiveTask) ?? simulationTasks[0];
}

export function matchesSimulationTaskContext(
  task: Pick<TaskSummary, "definitionId" | "datasetId">,
  context: SimulationPageContext,
) {
  if (typeof context.definitionId !== "string" || !context.datasetId) {
    return false;
  }

  return task.definitionId === context.definitionId && task.datasetId === context.datasetId;
}

export function filterSimulationTasksByContext(
  tasks: readonly TaskSummary[],
  context: SimulationPageContext,
) {
  return tasks.filter((task) => matchesSimulationTaskContext(task, context));
}

export function resolveLatestSimulationTaskInContext(
  tasks: readonly TaskSummary[],
  context: SimulationPageContext,
) {
  return resolveLatestSimulationTask(filterSimulationTasksByContext(tasks, context));
}

export function resolveLatestSimulationStageTask(
  tasks: readonly TaskSummary[],
  kind: SimulationStageKind,
): TaskSummary | undefined {
  const stageTasks = tasks.filter((task) => task.kind === kind);
  return stageTasks.find(isActiveTask) ?? stageTasks[0];
}

export function resolveLatestSimulationStageTaskInContext(
  tasks: readonly TaskSummary[],
  kind: SimulationStageKind,
  context: SimulationPageContext,
) {
  return resolveLatestSimulationStageTask(filterSimulationTasksByContext(tasks, context), kind);
}

export function resolveContextBoundAttachedTask(
  task: TaskDetail | undefined,
  context: SimulationPageContext,
  kind?: SimulationStageKind,
): TaskSummary | undefined {
  if (!task || !matchesSimulationTaskContext(task, context)) {
    return undefined;
  }

  if (kind && task.kind !== kind) {
    return undefined;
  }

  return normalizeTaskSummary(task);
}

export function resolveAuthoritativeSimulationTaskSummary(
  task: TaskSummary | undefined,
  detail: TaskDetail | undefined,
): TaskSummary | undefined {
  if (!detail) {
    return task;
  }

  if (!task) {
    return normalizeTaskSummary(detail);
  }

  return detail.taskId === task.taskId ? normalizeTaskSummary(detail) : task;
}

export function filterSimulationTasks(
  tasks: readonly TaskSummary[],
  options: FilterSimulationTasksOptions,
) {
  const normalizedQuery = options.searchQuery.trim().toLowerCase();

  return tasks.filter((task) => {
    if (!isSimulationLaneTask(task)) {
      return false;
    }

    if (
      !matchesTaskScope(
        task,
        options.selectedDefinitionId,
        options.activeDatasetId,
        options.scope,
      )
    ) {
      return false;
    }

    if (!matchesTaskStatus(task, options.statusFilter)) {
      return false;
    }

    if (!normalizedQuery) {
      return true;
    }

    return (
      task.summary.toLowerCase().includes(normalizedQuery) ||
      String(task.taskId).includes(normalizedQuery) ||
      (task.datasetId?.toLowerCase().includes(normalizedQuery) ?? false)
    );
  });
}

export function summarizeSimulationTasks(
  tasks: readonly TaskSummary[],
): SimulationTaskSummary {
  return tasks.reduce<SimulationTaskSummary>(
    (summary, task) => ({
      total: summary.total + 1,
      activeCount: summary.activeCount + (isActiveTask(task) ? 1 : 0),
      completedCount: summary.completedCount + (task.status === "completed" ? 1 : 0),
      failedCount: summary.failedCount + (task.status === "failed" ? 1 : 0),
      resultBackedCount:
        summary.resultBackedCount + (task.status === "completed" ? 1 : 0),
    }),
    {
      total: 0,
      activeCount: 0,
      completedCount: 0,
      failedCount: 0,
      resultBackedCount: 0,
    },
  );
}

export function resolveSimulationTaskAttachmentState(
  activeTask: TaskDetail | undefined,
  resolvedTaskId: number | null,
): SimulationTaskAttachmentState {
  if (resolvedTaskId === null) {
    return {
      isAttached: false,
      isStaleSnapshot: false,
    };
  }

  return {
    isAttached: activeTask?.taskId === resolvedTaskId,
    isStaleSnapshot:
      typeof activeTask?.taskId === "number" && activeTask.taskId !== resolvedTaskId,
  };
}

export function resolveSimulationTaskRecovery(
  requestedTaskId: number | null,
  latestTaskId: number | null,
  activeTaskError: Error | undefined,
): SimulationSelectionRecovery {
  if (requestedTaskId === null || !activeTaskError) {
    return null;
  }

  if (latestTaskId !== null && latestTaskId !== requestedTaskId) {
    return {
      tone: "warning",
      title: "Task reattach available",
      message: `Task #${requestedTaskId} could not be attached. A newer simulation task #${latestTaskId} is available to inspect instead.`,
    };
  }

  return {
    tone: "warning",
    title: "Task unavailable",
    message: `Task #${requestedTaskId} could not be attached. Refresh the queue or submit a new request.`,
  };
}

export function summarizeSimulationTaskResults(
  task: TaskDetail | undefined,
): SimulationTaskResultSummary {
  return {
    metadataRecordCount: task?.resultRefs.metadataRecords.length ?? 0,
    resultHandleCount: task?.resultRefs.resultHandles.length ?? 0,
    materializedHandleCount:
      task?.resultRefs.resultHandles.filter((handle) => handle.status === "materialized").length ??
      0,
    hasTracePayload: task?.resultRefs.tracePayload !== null,
    traceBatchId: task?.resultRefs.traceBatchId ?? null,
    analysisRunId: task?.resultRefs.analysisRunId ?? null,
  };
}

export function hasSimulationTaskResult(task: TaskDetail | undefined) {
  if (!task || task.status !== "completed") {
    return false;
  }

  const resultAvailability = task.resultHandoff?.availability ?? null;

  if (resultAvailability === "ready") {
    return true;
  }

  if (resultAvailability === "none" || resultAvailability === "pending") {
    return false;
  }

  return (
    task.resultRefs.tracePayload !== null ||
    task.resultRefs.resultHandles.some((handle) => handle.status === "materialized")
  );
}

export function resolvePostProcessingUpstreamTaskId(
  task: (Pick<TaskDetail, "taskId" | "resultRefs"> & { upstreamTaskId?: number | null }) | undefined,
): number | null {
  if (!task) {
    return null;
  }

  if (typeof task.upstreamTaskId === "number") {
    return task.upstreamTaskId;
  }

  for (const handle of task.resultRefs.resultHandles) {
    const sourceTaskId = handle.provenance.sourceTaskId ?? handle.provenanceTaskId;
    if (sourceTaskId !== null && sourceTaskId !== task.taskId) {
      return sourceTaskId;
    }
  }

  if (task.resultRefs.tracePayload === null) {
    return null;
  }

  return null;
}
