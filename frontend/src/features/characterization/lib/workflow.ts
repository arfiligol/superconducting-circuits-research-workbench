import type {
  CharacterizationDesignBrowseRow,
  CharacterizationResultStatus,
  CharacterizationResultSummary,
} from "@/features/characterization/lib/contracts";
import type { TaskSummary } from "@/lib/api/tasks";

export type CharacterizationResultStatusFilter = "all" | CharacterizationResultStatus;
export type CharacterizationTaskScope = "all" | "dataset";
export type CharacterizationTaskStatusFilter = "all" | "active" | "completed" | "failed";

export type CharacterizationSelectionRecovery = Readonly<{
  tone: "default" | "warning";
  title: string;
  message: string;
}> | null;

export type CharacterizationResultSummaryCounts = Readonly<{
  total: number;
  completedCount: number;
  failedCount: number;
  blockedCount: number;
  artifactCount: number;
}>;

export type CharacterizationTaskSummaryCounts = Readonly<{
  total: number;
  activeCount: number;
  completedCount: number;
  failedCount: number;
  resultBackedCount: number;
}>;

type FilterCharacterizationTasksOptions = Readonly<{
  searchQuery: string;
  scope: CharacterizationTaskScope;
  statusFilter: CharacterizationTaskStatusFilter;
  activeDatasetId: string | null;
}>;

function isCharacterizationTask(task: TaskSummary) {
  return task.kind === "characterization" && task.lane === "characterization";
}

function isActiveTask(task: TaskSummary) {
  return task.status === "queued" || task.status === "running";
}

export function resolveSelectedCharacterizationDesignId(
  selectedDesignId: string | null,
  designs: readonly CharacterizationDesignBrowseRow[] | undefined,
) {
  if (!designs || designs.length === 0) {
    return null;
  }

  if (selectedDesignId && designs.some((design) => design.design_id === selectedDesignId)) {
    return selectedDesignId;
  }

  return designs[0]?.design_id ?? null;
}

export function resolveSelectedCharacterizationResultId(
  selectedResultId: string | null,
  results: readonly CharacterizationResultSummary[] | undefined,
) {
  if (!results || results.length === 0) {
    return null;
  }

  if (selectedResultId && results.some((result) => result.resultId === selectedResultId)) {
    return selectedResultId;
  }

  return results[0]?.resultId ?? null;
}

export function summarizeCharacterizationResults(
  results: readonly CharacterizationResultSummary[],
): CharacterizationResultSummaryCounts {
  return results.reduce<CharacterizationResultSummaryCounts>(
    (summary, result) => ({
      total: summary.total + 1,
      completedCount: summary.completedCount + (result.status === "completed" ? 1 : 0),
      failedCount: summary.failedCount + (result.status === "failed" ? 1 : 0),
      blockedCount: summary.blockedCount + (result.status === "blocked" ? 1 : 0),
      artifactCount: summary.artifactCount + result.artifactCount,
    }),
    {
      total: 0,
      completedCount: 0,
      failedCount: 0,
      blockedCount: 0,
      artifactCount: 0,
    },
  );
}

export function resolveLatestCharacterizationTask(
  tasks: readonly TaskSummary[],
): TaskSummary | undefined {
  const characterizationTasks = tasks.filter(isCharacterizationTask);
  return characterizationTasks.find(isActiveTask) ?? characterizationTasks[0];
}

export function filterCharacterizationTasks(
  tasks: readonly TaskSummary[],
  options: FilterCharacterizationTasksOptions,
) {
  const normalizedQuery = options.searchQuery.trim().toLowerCase();

  return tasks.filter((task) => {
    if (!isCharacterizationTask(task)) {
      return false;
    }

    if (
      options.scope === "dataset" &&
      options.activeDatasetId !== null &&
      task.datasetId !== options.activeDatasetId
    ) {
      return false;
    }

    if (options.statusFilter === "active" && !isActiveTask(task)) {
      return false;
    }

    if (options.statusFilter === "completed" && task.status !== "completed") {
      return false;
    }

    if (options.statusFilter === "failed" && task.status !== "failed") {
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

export function summarizeCharacterizationTasks(
  tasks: readonly TaskSummary[],
): CharacterizationTaskSummaryCounts {
  return tasks.reduce<CharacterizationTaskSummaryCounts>(
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

export function resolveCharacterizationSelectionRecovery(input: Readonly<{
  activeDatasetName: string | null;
  requestedDesignId: string | null;
  resolvedDesignId: string | null;
  requestedResultId: string | null;
  resolvedResultId: string | null;
}>): CharacterizationSelectionRecovery {
  if (
    input.requestedDesignId &&
    input.resolvedDesignId &&
    input.requestedDesignId !== input.resolvedDesignId
  ) {
    return {
      tone: "warning",
      title: "Design scope rebound",
      message: `The active dataset now exposes ${input.resolvedDesignId} instead of ${input.requestedDesignId}. Browse state was rebound to stay within ${input.activeDatasetName ?? "the current dataset"}.`,
    };
  }

  if (
    input.requestedResultId &&
    input.resolvedResultId &&
    input.requestedResultId !== input.resolvedResultId
  ) {
    return {
      tone: "warning",
      title: "Result selection rebound",
      message: `Result ${input.requestedResultId} is no longer available for this design. The detail surface switched to ${input.resolvedResultId}.`,
    };
  }

  if (input.requestedDesignId && !input.resolvedDesignId) {
    return {
      tone: "warning",
      title: "No visible design scope",
      message: "The current dataset does not expose a design that can anchor characterization results.",
    };
  }

  if (input.requestedResultId && !input.resolvedResultId && input.resolvedDesignId) {
    return {
      tone: "default",
      title: "No saved result selected",
      message: "Choose another saved result to inspect its details, diagnostics, and files.",
    };
  }

  return null;
}

export function characterizationStatusTone(status: CharacterizationResultStatus) {
  if (status === "completed") {
    return "success" as const;
  }

  if (status === "failed") {
    return "warning" as const;
  }

  return "default" as const;
}
