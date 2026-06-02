"use client";

import type {
  TaskExecutionStatus,
  TaskLane,
  TaskQueueReadModel,
  TaskSummary,
  WorkerLaneSummary,
} from "@/lib/api/tasks";
import type { RuntimeMode, SessionDefaultTaskScope } from "@/lib/api/session";

export type TasksBrowseScope = "local" | "workspace" | "owned";
export type TasksBrowseStatusFilter = TaskExecutionStatus | "all";
export type TasksBrowseLaneFilter = TaskLane | "all";

export type TasksBrowseState = Readonly<{
  taskId: number | null;
  scope: TasksBrowseScope;
  status: TasksBrowseStatusFilter;
  lane: TasksBrowseLaneFilter;
  searchQuery: string;
}>;

export type TasksBrowsePatch = Readonly<{
  taskId?: number | null;
  scope?: TasksBrowseScope;
  status?: TasksBrowseStatusFilter;
  lane?: TasksBrowseLaneFilter;
  searchQuery?: string;
}>;

export type TasksWorkspaceSummary = Readonly<{
  visibleCount: number;
  activeCount: number;
  resultReadyCount: number;
  failedCount: number;
  workerLaneCount: number;
}>;

export type WorkerLaneInspectionRow = Readonly<{
  lane: string;
  idleProcessors: number;
  runningProcessors: number;
  degradedProcessors: number;
  drainingProcessors: number;
  offlineProcessors: number;
  activeTaskIds: readonly number[];
  latestTaskId: number | null;
}>;

export function resolveTasksDefaultScope(
  runtimeMode: RuntimeMode | undefined,
  defaultTaskScope: SessionDefaultTaskScope | null | undefined,
): TasksBrowseScope {
  if (runtimeMode === "local") {
    return "local";
  }

  if (defaultTaskScope === "owned" || defaultTaskScope === "workspace") {
    return defaultTaskScope;
  }

  return "workspace";
}

function parseTaskId(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

export function parseTasksBrowseState(
  search: string,
  defaultScope: TasksBrowseScope,
): TasksBrowseState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const scope = params.get("scope");
  const status = params.get("status");
  const lane = params.get("lane");

  return {
    taskId: parseTaskId(params.get("taskId")),
    scope:
      scope === "local" || scope === "workspace" || scope === "owned"
        ? scope
        : defaultScope,
    status: isTaskExecutionStatus(status) ? status : "all",
    lane: lane === "simulation" || lane === "characterization" ? lane : "all",
    searchQuery: params.get("q")?.trim() ?? "",
  };
}

export function buildTasksBrowseSearch(
  currentSearch: string,
  patch: TasksBrowsePatch,
  defaultScope: TasksBrowseScope,
): string {
  const params = new URLSearchParams(currentSearch.startsWith("?") ? currentSearch.slice(1) : currentSearch);

  if ("taskId" in patch) {
    if (typeof patch.taskId === "number") {
      params.set("taskId", String(patch.taskId));
    } else {
      params.delete("taskId");
    }
  }

  if ("scope" in patch) {
    if (patch.scope && patch.scope !== defaultScope) {
      params.set("scope", patch.scope);
    } else {
      params.delete("scope");
    }
  }

  if ("status" in patch) {
    if (patch.status && patch.status !== "all") {
      params.set("status", patch.status);
    } else {
      params.delete("status");
    }
  }

  if ("lane" in patch) {
    if (patch.lane && patch.lane !== "all") {
      params.set("lane", patch.lane);
    } else {
      params.delete("lane");
    }
  }

  if ("searchQuery" in patch) {
    const normalized = (patch.searchQuery ?? "").trim();
    if (normalized.length > 0) {
      params.set("q", normalized);
    } else {
      params.delete("q");
    }
  }

  const nextSearch = params.toString();
  return nextSearch.length > 0 ? `?${nextSearch}` : "";
}

export function buildTasksListQueryFromBrowseState(state: TasksBrowseState) {
  return {
    scope: state.scope,
    status: state.status === "all" ? undefined : state.status,
    lane: state.lane === "all" ? undefined : state.lane,
    searchQuery: state.searchQuery.length > 0 ? state.searchQuery : undefined,
    limit: 50,
  } as const;
}

export function resolveSelectedTaskId(
  taskId: number | null,
  queue: TaskQueueReadModel | undefined,
): number | null {
  if (typeof taskId === "number") {
    return taskId;
  }

  return queue?.rows[0]?.taskId ?? null;
}

export function summarizeTasksWorkspace(
  queue: TaskQueueReadModel | undefined,
): TasksWorkspaceSummary {
  const rows = queue?.rows ?? [];
  return {
    visibleCount: rows.length,
    activeCount: rows.filter((task) => isTaskActive(task.status)).length,
    resultReadyCount: rows.filter((task) => task.resultAvailability === "ready").length,
    failedCount: rows.filter((task) => task.status === "failed").length,
    workerLaneCount: queue?.workerSummary.length ?? 0,
  };
}

export function buildWorkerLaneInspectionRows(
  workerSummary: readonly WorkerLaneSummary[],
  rows: readonly TaskSummary[],
): readonly WorkerLaneInspectionRow[] {
  return workerSummary.map((laneSummary) => {
    const laneTasks = rows.filter((task) => task.lane === laneSummary.lane);
    const activeTaskIds = laneTasks
      .filter((task) => isTaskActive(task.status))
      .map((task) => task.taskId);

    return {
      lane: laneSummary.lane,
      idleProcessors: laneSummary.idleProcessors,
      runningProcessors: laneSummary.runningProcessors,
      degradedProcessors: laneSummary.degradedProcessors,
      drainingProcessors: laneSummary.drainingProcessors,
      offlineProcessors: laneSummary.offlineProcessors,
      activeTaskIds,
      latestTaskId: laneTasks[0]?.taskId ?? null,
    };
  });
}

function isTaskExecutionStatus(value: string | null): value is TaskExecutionStatus {
  return (
    value === "queued" ||
    value === "dispatching" ||
    value === "running" ||
    value === "cancellation_requested" ||
    value === "cancelling" ||
    value === "cancelled" ||
    value === "termination_requested" ||
    value === "terminated" ||
    value === "completed" ||
    value === "failed"
  );
}

function isTaskActive(status: TaskExecutionStatus) {
  return (
    status === "queued" ||
    status === "dispatching" ||
    status === "running" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  );
}
