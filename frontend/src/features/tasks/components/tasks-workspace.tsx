"use client";

import Link from "next/link";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import { useEffect, useMemo, useState, type ComponentType } from "react";
import useSWR, { useSWRConfig } from "swr";
import {
  LoaderCircle,
  PlugZap,
  RefreshCw,
  RotateCcw,
  Search,
  ServerCog,
  SquareArrowOutUpRight,
  StopCircle,
  Workflow,
  XCircle,
} from "lucide-react";

import {
  AppInlineSelect,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
import { TaskEventHistoryPanel } from "@/features/shared/components/task-event-history-panel";
import { TaskLifecyclePanel, TaskResultPanel } from "@/features/shared/components/task-workflow-panels";
import {
  SurfacePanel,
  SurfaceStat,
  SurfaceTag,
  cx,
} from "@/features/shared/components/surface-kit";
import {
  buildTasksListKey,
  cancelTask,
  getTask,
  getTaskEvents,
  listTasks,
  retryTask,
  taskDetailKey,
  taskEventsKey,
  tasksListKey,
  terminateTask,
  type TaskDetail,
  type TaskEventHistoryReadModel,
  type TaskExecutionStatus,
  type TaskQueueReadModel,
  type TaskSummary,
} from "@/lib/api/tasks";
import { useAppSession } from "@/lib/app-state";
import {
  summarizeTaskActionGates,
  summarizeTaskLifecycle,
  summarizeTaskResultSurface,
} from "@/lib/task-surface";

import {
  buildTasksBrowseSearch,
  buildTasksListQueryFromBrowseState,
  buildWorkerLaneInspectionRows,
  parseTasksBrowseState,
  resolveSelectedTaskId,
  resolveTasksDefaultScope,
  summarizeTasksWorkspace,
  type TasksBrowseLaneFilter,
  type TasksBrowseScope,
  type TasksBrowseState,
  type TasksBrowseStatusFilter,
} from "../lib/tasks-browse-state";

type PendingControlAction = "cancel" | "terminate" | null;

function formatTaskStatusLabel(status: TaskExecutionStatus) {
  switch (status) {
    case "queued":
      return "Queued";
    case "dispatching":
      return "Dispatching";
    case "running":
      return "Running";
    case "cancellation_requested":
      return "Cancel Requested";
    case "cancelling":
      return "Cancelling";
    case "cancelled":
      return "Cancelled";
    case "termination_requested":
      return "Terminate Requested";
    case "terminated":
      return "Terminated";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

function formatLaneLabel(lane: string) {
  switch (lane) {
    case "simulation":
      return "Simulation";
    case "characterization":
      return "Characterization";
    default:
      return lane;
  }
}

function formatKindLabel(kind: TaskSummary["kind"]) {
  switch (kind) {
    case "post_processing":
      return "Post Processing";
    case "characterization":
      return "Characterization";
    case "simulation":
    default:
      return "Simulation";
  }
}

function formatResultAvailabilityLabel(value: TaskSummary["resultAvailability"]) {
  switch (value) {
    case "ready":
      return "Ready";
    case "pending":
      return "Pending";
    case "none":
      return "None";
    default:
      return "--";
  }
}

function formatScopeLabel(scope: string) {
  switch (scope) {
    case "local":
      return "Local";
    case "private":
      return "Private";
    case "owned":
      return "Mine";
    case "workspace":
    default:
      return "Workspace";
  }
}

function buildScopeOptions(
  scope: TasksBrowseScope,
  runtimeMode: "local" | "online" | undefined,
): readonly AppSelectOption[] {
  if (runtimeMode === "local") {
    return [{ value: "local", label: "Local", description: "Local Space queue authority" }];
  }

  return [
    {
      value: "workspace",
      label: "Workspace",
      description:
        scope === "workspace"
          ? "Current workspace-visible queue rows"
          : "Browse workspace-visible queue rows",
    },
    {
      value: "owned",
      label: "Mine",
      description: "Only your persisted tasks",
    },
  ];
}

const statusOptions: readonly AppSelectOption[] = [
  { value: "all", label: "All statuses", description: "Keep active and terminal tasks together" },
  { value: "queued", label: "Queued" },
  { value: "dispatching", label: "Dispatching" },
  { value: "running", label: "Running" },
  { value: "cancellation_requested", label: "Cancel Requested" },
  { value: "cancelling", label: "Cancelling" },
  { value: "cancelled", label: "Cancelled" },
  { value: "termination_requested", label: "Terminate Requested" },
  { value: "terminated", label: "Terminated" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

const laneOptions: readonly AppSelectOption[] = [
  { value: "all", label: "All lanes", description: "Keep the full queue visible" },
  { value: "simulation", label: "Simulation" },
  { value: "characterization", label: "Characterization" },
];

function ActionGateChip({
  label,
  enabled,
}: Readonly<{
  label: string;
  enabled: boolean;
}>) {
  return (
    <span
      className={cx(
        "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]",
        enabled
          ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          : "border-border bg-background text-muted-foreground",
      )}
    >
      {label}
    </span>
  );
}

function DetailActionButton({
  label,
  onClick,
  disabled = false,
  tone = "default",
  icon: Icon,
}: Readonly<{
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "warning";
  icon: ComponentType<{ className?: string }>;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-55",
        tone === "warning"
          ? "border-amber-500/30 bg-amber-500/10 text-amber-950 hover:bg-amber-500/15 dark:text-amber-100"
          : "border-border bg-background text-foreground hover:border-primary/35 hover:bg-primary/10",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function buildSetupSnapshot(detail: TaskDetail | null) {
  if (!detail) {
    return null;
  }

  if (detail.simulationSetup) {
    return {
      label: "Persisted Simulation Setup",
      value: JSON.stringify(detail.simulationSetup, null, 2),
    } as const;
  }

  if (detail.postProcessingSetup) {
    return {
      label: "Persisted Post-Processing Setup",
      value: JSON.stringify(detail.postProcessingSetup, null, 2),
    } as const;
  }

  return null;
}

function mergeTaskWithEventHistory(
  task: TaskDetail | null,
  history: TaskEventHistoryReadModel | undefined,
) {
  if (!task) {
    return undefined;
  }

  return {
    ...task,
    events: history?.events ?? task.events,
  } satisfies TaskDetail;
}

export function TasksWorkspace() {
  const pathname = usePathname() ?? "/tasks";
  const router = useRouter();
  const searchParams = useSearchParams();
  const { mutate } = useSWRConfig();
  const { session, status: sessionStatus } = useAppSession();
  const [searchDraft, setSearchDraft] = useState("");
  const [pendingControlAction, setPendingControlAction] = useState<PendingControlAction>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [isMutating, setIsMutating] = useState(false);

  const defaultScope = useMemo(
    () =>
      resolveTasksDefaultScope(
        session?.runtimeMode,
        session?.workspace.defaultTaskScope ?? null,
      ),
    [session?.runtimeMode, session?.workspace.defaultTaskScope],
  );
  const browseState = useMemo<TasksBrowseState>(
    () => parseTasksBrowseState(searchParams?.toString() ?? "", defaultScope),
    [defaultScope, searchParams],
  );
  const contextKey = `${session?.runtimeMode ?? "online"}:${session?.workspace.workspaceId ?? "none"}`;
  const queueQueryInput = useMemo(
    () => buildTasksListQueryFromBrowseState(browseState),
    [browseState],
  );
  const queueKey =
    sessionStatus === "loading" ? null : [buildTasksListKey(queueQueryInput), contextKey];
  const queueQuery = useSWR(
    queueKey,
    () => listTasks(queueQueryInput),
    {
      refreshInterval(currentData: TaskQueueReadModel | undefined) {
        return (currentData?.rows ?? []).some((task) =>
          task.status === "queued" ||
          task.status === "dispatching" ||
          task.status === "running" ||
          task.status === "cancellation_requested" ||
          task.status === "cancelling" ||
          task.status === "termination_requested",
        )
          ? 5_000
          : 0;
      },
    },
  );

  const selectedTaskId = resolveSelectedTaskId(browseState.taskId, queueQuery.data);
  const detailKey = selectedTaskId ? [taskDetailKey(selectedTaskId), contextKey] : null;
  const detailQuery = useSWR(
    detailKey,
    () => (selectedTaskId ? getTask(selectedTaskId) : Promise.resolve(undefined)),
    {
      refreshInterval(currentData: TaskDetail | undefined) {
        if (!currentData) {
          return 5_000;
        }

        return currentData.status === "queued" ||
          currentData.status === "dispatching" ||
          currentData.status === "running" ||
          currentData.status === "cancellation_requested" ||
          currentData.status === "cancelling" ||
          currentData.status === "termination_requested"
          ? 2_000
          : 0;
      },
    },
  );
  const eventHistoryKey = selectedTaskId ? [taskEventsKey(selectedTaskId, { order: "desc", limit: 50 }), contextKey] : null;
  const eventHistoryQuery = useSWR(
    eventHistoryKey,
    () =>
      selectedTaskId
        ? getTaskEvents(selectedTaskId, { order: "desc", limit: 50 })
        : Promise.resolve(undefined),
  );

  useEffect(() => {
    setSearchDraft(browseState.searchQuery);
  }, [browseState.searchQuery]);

  const selectedTask = detailQuery.data ?? null;
  const selectedTaskWithEvents = mergeTaskWithEventHistory(selectedTask, eventHistoryQuery.data);
  const tasksSummary = summarizeTasksWorkspace(queueQuery.data);
  const workerInspectionRows = useMemo(
    () =>
      buildWorkerLaneInspectionRows(
        queueQuery.data?.workerSummary ?? [],
        queueQuery.data?.rows ?? [],
      ),
    [queueQuery.data],
  );
  const selectedTaskLifecycle = summarizeTaskLifecycle(selectedTask ?? undefined);
  const selectedTaskResultSurface = summarizeTaskResultSurface(selectedTask ?? undefined);
  const selectedTaskActionGates = summarizeTaskActionGates(selectedTask ?? undefined);
  const setupSnapshot = buildSetupSnapshot(selectedTask);

  function replaceBrowseState(patch: Parameters<typeof buildTasksBrowseSearch>[1]) {
    const nextSearch = buildTasksBrowseSearch(
      searchParams?.toString() ?? "",
      patch,
      defaultScope,
    );
    router.replace(nextSearch.length > 0 ? `${pathname}${nextSearch}` : pathname, {
      scroll: false,
    });
  }

  async function revalidateTaskSurfaces(nextTaskId?: number) {
    const currentTaskId = typeof nextTaskId === "number" ? nextTaskId : selectedTaskId;
    await Promise.all([
      queueQuery.mutate(),
      currentTaskId ? detailQuery.mutate() : Promise.resolve(undefined),
      currentTaskId ? eventHistoryQuery.mutate() : Promise.resolve(undefined),
      mutate((key) => {
        if (typeof key === "string") {
          return key === tasksListKey || key.startsWith(tasksListKey);
        }
        if (Array.isArray(key)) {
          return typeof key[0] === "string" && key[0].startsWith(tasksListKey);
        }
        return false;
      }),
    ]);
  }

  async function runControlAction(action: "cancel" | "terminate" | "retry") {
    if (!selectedTaskId) {
      return;
    }

    setMutationError(null);
    setIsMutating(true);
    try {
      const response =
        action === "cancel"
          ? await cancelTask(selectedTaskId)
          : action === "terminate"
            ? await terminateTask(selectedTaskId)
            : await retryTask(selectedTaskId);

      if (action === "retry") {
        replaceBrowseState({ taskId: response.taskId });
        await revalidateTaskSurfaces(response.taskId);
      } else {
        await revalidateTaskSurfaces(selectedTaskId);
      }
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : "Task mutation failed.");
    } finally {
      setPendingControlAction(null);
      setIsMutating(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-[1.15rem] border border-border bg-card px-5 py-5 shadow-[0_12px_30px_rgba(0,0,0,0.08)]">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/80 pb-4">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Extended Queue Surface
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-foreground">Tasks</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              Browse longer queue history, inspect task detail and event timeline, and review lane
              runtime summary without pushing task dashboards back into workflow pages.
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <SurfaceStat label="Visible Tasks" value={String(tasksSummary.visibleCount)} tone="primary" />
          <SurfaceStat label="Active" value={String(tasksSummary.activeCount)} />
          <SurfaceStat label="Result Ready" value={String(tasksSummary.resultReadyCount)} />
          <SurfaceStat label="Failed" value={String(tasksSummary.failedCount)} />
          <SurfaceStat
            label="Worker Lanes"
            value={String(tasksSummary.workerLaneCount)}
            tone={tasksSummary.workerLaneCount > 0 ? "primary" : "default"}
          />
        </div>
      </section>

      <SurfacePanel
        title="Browse Filters"
        description="Keep queue browse state bound to the URL so refresh and shared links reopen the same task, scope, lane, and status context."
      >
        <form
          className="grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.75fr)_minmax(0,0.75fr)_minmax(0,0.75fr)]"
          onSubmit={(event) => {
            event.preventDefault();
            replaceBrowseState({ searchQuery: searchDraft, taskId: browseState.taskId });
          }}
        >
          <label className="rounded-[1rem] border border-border/80 bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
            <span className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              <Search className="h-3.5 w-3.5" />
              Search
            </span>
            <div className="flex gap-2">
              <input
                value={searchDraft}
                onChange={(event) => {
                  setSearchDraft(event.target.value);
                }}
                placeholder="Search summary, owner, or task id"
                className="min-h-11 w-full rounded-[1rem] border border-border/85 bg-background/90 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
              />
              <button
                type="submit"
                className="inline-flex min-h-11 shrink-0 items-center rounded-[1rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
              >
                Apply
              </button>
            </div>
          </label>

          <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
            <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Scope
            </p>
            <AppInlineSelect
              ariaLabel="Tasks scope"
              value={browseState.scope}
              onChange={(value) => {
                replaceBrowseState({
                  scope: value as TasksBrowseScope,
                  taskId: browseState.taskId,
                });
              }}
              options={buildScopeOptions(browseState.scope, session?.runtimeMode)}
              disabled={session?.runtimeMode === "local"}
            />
          </div>

          <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
            <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Status
            </p>
            <AppInlineSelect
              ariaLabel="Tasks status"
              value={browseState.status}
              onChange={(value) => {
                replaceBrowseState({
                  status: value as TasksBrowseStatusFilter,
                  taskId: browseState.taskId,
                });
              }}
              options={statusOptions}
            />
          </div>

          <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
            <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Lane
            </p>
            <AppInlineSelect
              ariaLabel="Tasks lane"
              value={browseState.lane}
              onChange={(value) => {
                replaceBrowseState({
                  lane: value as TasksBrowseLaneFilter,
                  taskId: browseState.taskId,
                });
              }}
              options={laneOptions}
            />
          </div>
        </form>
      </SurfacePanel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.95fr)]">
        <SurfacePanel
          title="Queue History"
          description="Recent persisted tasks stay sortable by backend authority, with current filters echoed in the URL instead of page-local memory."
          actions={
            <button
              type="button"
              onClick={() => {
                void queueQuery.mutate();
              }}
              className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              <RefreshCw className={cx("h-4 w-4", queueQuery.isValidating && "animate-spin")} />
              Refresh rows
            </button>
          }
        >
          <div className="overflow-hidden rounded-[1rem] border border-border/80">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-card">
                <tr className="text-left text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  <th className="px-4 py-3">Task</th>
                  <th className="px-4 py-3">Lane / Kind</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Context</th>
                  <th className="px-4 py-3">Owner</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">Allowed Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-surface">
                {queueQuery.data?.rows.length ? (
                  queueQuery.data.rows.map((task) => {
                    const isSelected = task.taskId === selectedTaskId;
                    return (
                      <tr
                        key={task.taskId}
                        className={cx(
                          "transition",
                          isSelected ? "bg-primary/[0.08]" : "hover:bg-background/80",
                        )}
                      >
                        <td className="px-4 py-3 align-top">
                          <button
                            type="button"
                            onClick={() => {
                              replaceBrowseState({ taskId: task.taskId });
                            }}
                            className="group text-left"
                          >
                            <span className="block font-semibold text-foreground group-hover:text-primary">
                              #{task.taskId} · {task.summary}
                            </span>
                            <span className="mt-1 block text-xs text-muted-foreground">
                              {isSelected ? "Selected in detail panel" : "Open detail"}
                            </span>
                          </button>
                        </td>
                        <td className="px-4 py-3 align-top text-muted-foreground">
                          <p className="font-medium text-foreground">{formatLaneLabel(task.lane)}</p>
                          <p className="mt-1 text-xs">{formatKindLabel(task.kind)}</p>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="flex flex-wrap gap-2">
                            <SurfaceTag tone={task.status === "completed" ? "success" : task.status === "failed" ? "warning" : "primary"}>
                              {formatTaskStatusLabel(task.status)}
                            </SurfaceTag>
                            {task.controlState && task.controlState !== "none" ? (
                              <SurfaceTag tone="warning">
                                {task.controlState === "cancellation_requested"
                                  ? "Cancel requested"
                                  : "Terminate requested"}
                              </SurfaceTag>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                          <p>Dataset {task.datasetId ?? "--"}</p>
                          <p className="mt-1">Definition {task.definitionId ?? "--"}</p>
                          <p className="mt-1 uppercase tracking-[0.12em]">{formatScopeLabel(task.visibilityScope)}</p>
                        </td>
                        <td className="px-4 py-3 align-top text-muted-foreground">
                          {task.ownerDisplayName}
                        </td>
                        <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                          {task.updatedAt ?? task.submittedAt ?? "--"}
                        </td>
                        <td className="px-4 py-3 align-top">
                          <SurfaceTag tone={task.resultAvailability === "ready" ? "success" : "default"}>
                            {formatResultAvailabilityLabel(task.resultAvailability)}
                          </SurfaceTag>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="flex flex-wrap gap-2">
                            <ActionGateChip label="Attach" enabled={task.allowedActions.attach} />
                            <ActionGateChip label="Cancel" enabled={task.allowedActions.cancel} />
                            <ActionGateChip label="Terminate" enabled={task.allowedActions.terminate} />
                            <ActionGateChip label="Retry" enabled={task.allowedActions.retry} />
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-sm text-muted-foreground">
                      {queueQuery.isLoading
                        ? "Loading persisted queue rows..."
                        : "No tasks match the current filter set."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </SurfacePanel>

        <div className="space-y-5">
          <SurfacePanel
            title="Task Detail"
            description="Inspect persisted lifecycle, lineage, result handoff, and setup snapshots for the selected task."
            actions={
              selectedTaskId ? (
                <Link
                  href={`/tasks?taskId=${selectedTaskId}`}
                  className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <SquareArrowOutUpRight className="h-4 w-4" />
                  Share selection
                </Link>
              ) : null
            }
          >
            {selectedTask ? (
              <div className="space-y-4">
                <div className="rounded-[1rem] border border-border bg-surface px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        Selected Task
                      </p>
                      <h2 className="mt-2 text-lg font-semibold text-foreground">
                        #{selectedTask.taskId} · {selectedTask.summary}
                      </h2>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <SurfaceTag tone={selectedTask.status === "completed" ? "success" : selectedTask.status === "failed" ? "warning" : "primary"}>
                        {formatTaskStatusLabel(selectedTask.status)}
                      </SurfaceTag>
                      <SurfaceTag tone="default">{formatKindLabel(selectedTask.kind)}</SurfaceTag>
                      <SurfaceTag tone="default">{formatLaneLabel(selectedTask.lane)}</SurfaceTag>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                      <p className="font-medium text-foreground">Result handoff</p>
                      <p className="mt-2">
                        {selectedTask.resultHandoff?.availability === "ready"
                          ? "Persisted result handoff is ready."
                          : selectedTask.resultHandoff?.availability === "pending"
                            ? "Persisted result handoff is still pending."
                            : "This task has no persisted result handoff."}
                      </p>
                    </div>
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                      <p className="font-medium text-foreground">Lineage</p>
                      <p className="mt-2">
                        Retry of {selectedTask.retryOfTaskId ?? "--"} · Upstream{" "}
                        {selectedTask.upstreamTaskId ?? "--"} · Downstream{" "}
                        {selectedTask.downstreamTaskIds?.length ?? 0}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <DetailActionButton
                      label={browseState.taskId === selectedTask.taskId ? "Attached" : "Attach"}
                      disabled={browseState.taskId === selectedTask.taskId}
                      onClick={() => {
                        replaceBrowseState({ taskId: selectedTask.taskId });
                      }}
                      icon={PlugZap}
                    />
                    <DetailActionButton
                      label="Cancel"
                      disabled={!selectedTaskActionGates.cancel.enabled || isMutating}
                      onClick={() => {
                        setPendingControlAction("cancel");
                      }}
                      icon={XCircle}
                      tone="warning"
                    />
                    <DetailActionButton
                      label="Terminate"
                      disabled={!selectedTaskActionGates.terminate.enabled || isMutating}
                      onClick={() => {
                        setPendingControlAction("terminate");
                      }}
                      icon={StopCircle}
                      tone="warning"
                    />
                    <DetailActionButton
                      label="Retry"
                      disabled={!selectedTaskActionGates.retry.enabled || isMutating}
                      onClick={() => {
                        void runControlAction("retry");
                      }}
                      icon={RotateCcw}
                    />
                  </div>

                  {pendingControlAction ? (
                    <div className="mt-4 rounded-[0.95rem] border border-amber-500/35 bg-amber-50/90 px-4 py-4 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-950/35 dark:text-amber-100">
                      <p className="font-medium">
                        {pendingControlAction === "cancel"
                          ? "Confirm graceful cancel"
                          : "Confirm force terminate"}
                      </p>
                      <p className="mt-2">
                        {pendingControlAction === "cancel"
                          ? "This will request graceful cancellation and wait for runtime acknowledgement."
                          : "This will request immediate termination for the selected task."}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <DetailActionButton
                          label={pendingControlAction === "cancel" ? "Confirm Cancel" : "Confirm Terminate"}
                          onClick={() => {
                            void runControlAction(pendingControlAction);
                          }}
                          icon={pendingControlAction === "cancel" ? XCircle : StopCircle}
                          tone="warning"
                          disabled={isMutating}
                        />
                        <DetailActionButton
                          label="Keep task running"
                          onClick={() => {
                            setPendingControlAction(null);
                          }}
                          icon={Workflow}
                          disabled={isMutating}
                        />
                      </div>
                    </div>
                  ) : null}

                  {mutationError ? (
                    <div className="mt-4 rounded-[0.95rem] border border-rose-500/35 bg-rose-50/90 px-4 py-4 text-sm text-rose-950 dark:border-rose-500/35 dark:bg-rose-950/35 dark:text-rose-100">
                      {mutationError}
                    </div>
                  ) : null}
                </div>

                <TaskLifecyclePanel task={selectedTask} summary={selectedTaskLifecycle} />

                {setupSnapshot ? (
                  <SurfacePanel
                    title={setupSnapshot.label}
                    description="Persisted setup snapshots stay visible here so task inspection does not depend on workflow-page local form state."
                  >
                    <pre className="overflow-x-auto rounded-[0.95rem] border border-border bg-background px-4 py-4 text-xs leading-6 text-foreground">
                      {setupSnapshot.value}
                    </pre>
                  </SurfacePanel>
                ) : null}

                <TaskResultPanel
                  task={selectedTask}
                  summary={selectedTaskResultSurface}
                  showTasksPageLink={false}
                />

                <TaskEventHistoryPanel
                  title="Event Timeline"
                  description="Append-only persisted task events, ordered for extended queue inspection."
                  task={selectedTaskWithEvents}
                  narrative="This timeline stays bound to persisted task events so queue recovery, retries, and runtime control requests remain auditable."
                  emptyMessage="No persisted task events were recorded for this task."
                />
              </div>
            ) : detailQuery.isLoading ? (
              <div className="flex items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Loading persisted task detail...
              </div>
            ) : (
              <div className="rounded-[0.95rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Select a queue row to inspect lifecycle, results, and event history.
              </div>
            )}
          </SurfacePanel>
        </div>
      </div>

      <SurfacePanel
        title="Worker / Lane Inspection"
        description="This extended surface goes deeper than the header by pairing lane summary with current queue bindings, while keeping unavailable processor-heartbeat detail honest."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {workerInspectionRows.length > 0 ? (
            workerInspectionRows.map((lane) => (
              <div
                key={lane.lane}
                className="rounded-[1rem] border border-border bg-surface px-4 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {formatLaneLabel(lane.lane)}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Lane authority
                    </p>
                  </div>
                  <ServerCog className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Healthy
                    </p>
                    <p className="mt-1 font-semibold text-foreground">{lane.healthyProcessors}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Busy
                    </p>
                    <p className="mt-1 font-semibold text-foreground">{lane.busyProcessors}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Degraded
                    </p>
                    <p className="mt-1 font-semibold text-foreground">{lane.degradedProcessors}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Draining
                    </p>
                    <p className="mt-1 font-semibold text-foreground">{lane.drainingProcessors}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Offline
                    </p>
                    <p className="mt-1 font-semibold text-foreground">{lane.offlineProcessors}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Latest Task
                    </p>
                    <p className="mt-1 font-semibold text-foreground">
                      {lane.latestTaskId ? `#${lane.latestTaskId}` : "--"}
                    </p>
                  </div>
                </div>
                <div className="mt-4 rounded-[0.9rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                  <p className="font-medium text-foreground">Current task binding</p>
                  <p className="mt-2">
                    {lane.activeTaskIds.length > 0
                      ? lane.activeTaskIds.map((taskId) => `#${taskId}`).join(", ")
                      : "No active persisted tasks are currently bound to this visible lane."}
                  </p>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-[0.95rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              Backend authority has not reported any worker lane rows yet.
            </div>
          )}
        </div>

        <div className="mt-4 rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Processor heartbeat detail</p>
          <p className="mt-2">
            The current backend `/tasks` contract only exposes lane summary, not per-processor
            heartbeat rows. This page keeps lane inspection truthful and backend-owned instead of
            inventing processor ids, runtime metadata, or heartbeat freshness in the frontend.
          </p>
        </div>
      </SurfacePanel>
    </div>
  );
}
