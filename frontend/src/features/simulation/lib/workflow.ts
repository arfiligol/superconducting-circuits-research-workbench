import type {
  CircuitDefinitionSummary,
} from "@/features/circuit-definition-editor/lib/contracts";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import type { TaskDetail, TaskExecutionStatus, TaskSummary } from "@/lib/api/tasks";

export type SimulationTaskScope = "all" | "definition" | "dataset";
export type SimulationTaskStatusFilter = "all" | "active" | "completed" | "failed";
export type SimulationStageKind = "simulation" | "post_processing";

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
  selectedDefinitionId: number | null;
  activeDatasetId: string | null;
}>;

function isSimulationLaneTask(task: TaskSummary) {
  return task.kind === "simulation" || task.kind === "post_processing";
}

export function isSimulationTaskActive(status: TaskExecutionStatus) {
  return (
    status === "queued" ||
    status === "dispatching" ||
    status === "running" ||
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
    case "dispatching":
      return "Queued";
    case "running":
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
  selectedDefinitionId: number | null,
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
      String(definition.definition_id).includes(normalizedQuery)
    );
  });
}

export function resolveSimulationSelectionRecovery(
  requestedDefinitionId: string | null,
  resolvedDefinitionId: number | null,
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
      message: `The URL selection "${requestedDefinitionId}" is not a canonical definition id. Showing definition #${resolvedDefinitionId} instead.`,
    };
  }

  const definitionExists = definitions.some(
    (definition) => definition.definition_id === parsedDefinitionId,
  );

  if (!definitionExists) {
    return {
      tone: "warning",
      title: "Definition not found",
      message: `Definition #${parsedDefinitionId} is not available in the current catalog. Reattached to definition #${resolvedDefinitionId}.`,
    };
  }

  return null;
}

export function buildSimulationRequestSummary(input: Readonly<{
  kind: "simulation" | "post_processing";
  definitionId: number | null;
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
      : `${baseLabel} for definition #${input.definitionId ?? "--"}`,
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

export function resolveLatestSimulationStageTask(
  tasks: readonly TaskSummary[],
  kind: SimulationStageKind,
): TaskSummary | undefined {
  const stageTasks = tasks.filter((task) => task.kind === kind);
  return stageTasks.find(isActiveTask) ?? stageTasks[0];
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

  return (
    task.resultRefs.traceBatchId !== null ||
    task.resultRefs.analysisRunId !== null ||
    task.resultRefs.tracePayload !== null ||
    task.resultRefs.metadataRecords.length > 0 ||
    task.resultRefs.resultHandles.length > 0
  );
}

export function resolvePostProcessingUpstreamTaskId(
  task: Pick<TaskDetail, "taskId" | "resultRefs"> | undefined,
): number | null {
  if (!task) {
    return null;
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
