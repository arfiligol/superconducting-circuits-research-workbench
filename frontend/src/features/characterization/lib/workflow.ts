import type {
  CharacterizationResultStatus,
  CharacterizationResultSummary,
} from "@/features/characterization/lib/contracts";
import type { DesignLifecycleState } from "@/features/data-browser/lib/contracts";
import type { TaskSummary } from "@/lib/api/tasks";

export type CharacterizationResultStatusFilter = "all" | CharacterizationResultStatus;
export type CharacterizationTaskScope = "all" | "dataset";
export type CharacterizationTaskStatusFilter = "all" | "active" | "completed" | "failed";
export type CharacterizationResultSelectionSource =
  | "route"
  | "user"
  | "completed_run"
  | "task_handoff"
  | "results_default"
  | "none";
type SelectableCharacterizationDesignRow = Readonly<{
  design_id: string;
  lifecycle_state?: DesignLifecycleState;
}>;

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

export type CharacterizationResultSelectionResolution = Readonly<{
  resultId: string | null;
  source: CharacterizationResultSelectionSource;
  isExplicitRoutePending: boolean;
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
  designs: readonly SelectableCharacterizationDesignRow[] | undefined,
) {
  const activeDesigns = (designs ?? []).filter(
    (design) => (design.lifecycle_state ?? "active") === "active",
  );

  if (activeDesigns.length === 0) {
    return null;
  }

  if (selectedDesignId && activeDesigns.some((design) => design.design_id === selectedDesignId)) {
    return selectedDesignId;
  }

  return activeDesigns[0]?.design_id ?? null;
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

function hasResultSummary(
  results: readonly CharacterizationResultSummary[] | undefined,
  resultId: string,
) {
  return results?.some((result) => result.resultId === resultId) ?? false;
}

export function resolveCharacterizationTaskHandoffResultId(input: Readonly<{
  primaryResultHandleId: string | null | undefined;
  results: readonly CharacterizationResultSummary[] | undefined;
}>) {
  if (!input.primaryResultHandleId) {
    return null;
  }

  return hasResultSummary(input.results, input.primaryResultHandleId)
    ? input.primaryResultHandleId
    : null;
}

export function resolveCharacterizationResultSelection(input: Readonly<{
  requestedResultId: string | null;
  userSelectedResultId: string | null;
  completedRunResultId?: string | null;
  taskHandoffResultId?: string | null;
  results: readonly CharacterizationResultSummary[] | undefined;
  hasResolvedResults: boolean;
  requestedResultUnavailable?: boolean;
}>): CharacterizationResultSelectionResolution {
  if (input.requestedResultId && !input.requestedResultUnavailable) {
    return {
      resultId: input.requestedResultId,
      source: "route",
      isExplicitRoutePending:
        !input.hasResolvedResults || !hasResultSummary(input.results, input.requestedResultId),
    };
  }

  if (input.userSelectedResultId) {
    return {
      resultId: input.userSelectedResultId,
      source: "user",
      isExplicitRoutePending: false,
    };
  }

  if (input.completedRunResultId) {
    return {
      resultId: input.completedRunResultId,
      source: "completed_run",
      isExplicitRoutePending: false,
    };
  }

  if (input.taskHandoffResultId) {
    return {
      resultId: input.taskHandoffResultId,
      source: "task_handoff",
      isExplicitRoutePending: false,
    };
  }

  if (input.results && input.results.length > 0) {
    return {
      resultId: input.results[0]?.resultId ?? null,
      source: "results_default",
      isExplicitRoutePending: false,
    };
  }

  return {
    resultId: null,
    source: "none",
    isExplicitRoutePending: false,
  };
}

export function resolveCharacterizationResultDetailId(input: Readonly<{
  selectedResultId: string | null;
  requestedResultId: string | null;
  results: readonly CharacterizationResultSummary[] | undefined;
  hasResolvedResults: boolean;
}>) {
  if (
    !input.requestedResultId &&
    input.hasResolvedResults &&
    (!input.results || input.results.length === 0)
  ) {
    return null;
  }

  return resolveCharacterizationResultSelection({
    requestedResultId: input.requestedResultId,
    userSelectedResultId: input.selectedResultId,
    results: input.results,
    hasResolvedResults: input.hasResolvedResults,
  }).resultId;
}

export function buildCharacterizationSearchHref(
  pathname: string,
  searchParamsValue: string,
  updates: Readonly<Record<string, string | null>>,
) {
  const params = new URLSearchParams(searchParamsValue);

  for (const [key, value] of Object.entries(updates)) {
    if (value === null) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  }

  const nextSearch = params.toString();
  return nextSearch ? `${pathname}?${nextSearch}` : pathname;
}

export function shouldSyncCharacterizationUrl(input: Readonly<{
  currentHref: string;
  nextHref: string;
  hasExplicitRouteResult: boolean;
  isExplicitRouteResultPending: boolean;
  resolvedResultSource: CharacterizationResultSelectionSource;
}>) {
  if (input.currentHref === input.nextHref) {
    return false;
  }

  return !(
    input.hasExplicitRouteResult &&
    input.isExplicitRouteResultPending &&
    input.resolvedResultSource !== "route"
  );
}

export function shouldHydrateCharacterizationSelectionFromTask(input: Readonly<{
  scopeDesignId: string | null;
  taskDesignId: string | null | undefined;
}>) {
  return Boolean(input.scopeDesignId) && input.taskDesignId === input.scopeDesignId;
}

export function resolveScopedCharacterizationTaskId(input: Readonly<{
  taskId: number | null;
  taskDesignId: string | null | undefined;
  selectedDesignId: string | null;
  hasTaskDetail: boolean;
}>) {
  if (!input.taskId) {
    return null;
  }

  if (!input.hasTaskDetail || !input.taskDesignId || !input.selectedDesignId) {
    return input.taskId;
  }

  return input.taskDesignId === input.selectedDesignId ? input.taskId : null;
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
