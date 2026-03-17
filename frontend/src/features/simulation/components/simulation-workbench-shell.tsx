"use client";

import { useEffect, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  FileCode2,
  LoaderCircle,
  Play,
  Search,
  WandSparkles,
  Waypoints,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { CircuitDefinitionSummary } from "@/features/circuit-definition-editor/lib/contracts";
import { buildNormalizedOutputPreview } from "@/features/circuit-definition-editor/lib/preview";
import { useSimulationWorkflowData } from "@/features/simulation/hooks/use-simulation-workflow-data";
import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import {
  buildSimulationRequestSummary,
  filterSimulationDefinitions,
  filterSimulationTasks,
  resolveSimulationSelectionRecovery,
  summarizeSimulationTasks,
  type SimulationTaskScope,
  type SimulationTaskStatusFilter,
} from "@/features/simulation/lib/workflow";
import {
  ResearchTaskQueuePanel,
  ResearchWorkflowHero,
  ResearchWorkflowOverviewPanel,
} from "@/features/shared/components/research-workflow-panels";
import {
  SurfacePanel,
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import { TaskEventHistoryPanel } from "@/features/shared/components/task-event-history-panel";
import {
  TaskAttachmentPanel,
  TaskLifecyclePanel,
  TaskResultPanel,
} from "@/features/shared/components/task-workflow-panels";
import { ApiError } from "@/lib/api/client";
import type { TaskExecutionStatus } from "@/lib/api/tasks";
import { summarizeTaskEventHistory } from "@/lib/task-event-history";
import { summarizeResearchWorkflowSurface } from "@/lib/research-workflow-surface";
import {
  resolveTaskConnectionState,
  summarizeTaskActionGates,
  summarizeTaskContextBinding,
  resolveTaskRecoveryNotice,
  summarizeTaskLifecycle,
  summarizeTaskResultHandoff,
  summarizeTaskResultSurface,
} from "@/lib/task-surface";

const simulationRequestSchema = z.object({
  summaryNote: z.string().trim().max(180, "Keep the request note within 180 characters."),
});

type SimulationRequestValues = z.infer<typeof simulationRequestSchema>;

const defaultRequestValues: SimulationRequestValues = {
  summaryNote: "",
};

const simulationTaskScopeOptions = [
  { label: "Current definition", value: "definition" },
  { label: "Active dataset", value: "dataset" },
  { label: "All simulation tasks", value: "all" },
] as const satisfies readonly Readonly<{
  label: string;
  value: SimulationTaskScope;
}>[];

const simulationTaskStatusOptions = [
  { label: "All statuses", value: "all" },
  { label: "Queued or running", value: "active" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
] as const satisfies readonly Readonly<{
  label: string;
  value: SimulationTaskStatusFilter;
}>[];

function buildSimulationSearchHref(
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

function lineCount(value: string) {
  return value.split("\n").length;
}

function parseTaskIdParam(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function describeApiError(error: Error | undefined) {
  if (!error) {
    return null;
  }

  if (error instanceof ApiError) {
    const retryHint = error.retryable === true ? " Retry is available." : "";
    const debugHint = error.debugRef ? ` Ref: ${error.debugRef}.` : "";
    return `${error.message}${retryHint}${debugHint}`;
  }

  return error.message;
}

function taskStatusTone(status: TaskExecutionStatus) {
  if (status === "completed") {
    return "success" as const;
  }

  if (
    status === "running" ||
    status === "dispatching" ||
    status === "cancellation_requested" ||
    status === "cancelling" ||
    status === "termination_requested"
  ) {
    return "primary" as const;
  }

  if (status === "failed" || status === "cancelled" || status === "terminated") {
    return "warning" as const;
  }

  return "default" as const;
}

function definitionStatusTone(
  status: CircuitDefinitionSummary["validation_status"],
) {
  return status === "warning" ? ("warning" as const) : ("success" as const);
}

function taskKindLabel(kind: "simulation" | "post_processing" | "characterization") {
  if (kind === "post_processing") {
    return "Post Processing";
  }

  if (kind === "characterization") {
    return "Characterization";
  }

  return "Simulation";
}

type DefinitionCardProps = Readonly<{
  definition: CircuitDefinitionSummary;
  isActive: boolean;
  onSelect: (definitionId: number) => void;
  isPinned?: boolean;
}>;

function DefinitionCard({
  definition,
  isActive,
  onSelect,
  isPinned = false,
}: DefinitionCardProps) {
  return (
    <button
      type="button"
      onClick={() => {
        onSelect(definition.definition_id);
      }}
      className={cx(
        "w-full cursor-pointer rounded-[1rem] border px-4 py-4 text-left shadow-[0_10px_30px_rgba(0,0,0,0.08)] transition",
        isActive
          ? "border-primary/40 bg-card"
          : "border-border bg-card hover:border-primary/25 hover:bg-primary/5",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-foreground">{definition.name}</h2>
          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Definition #{definition.definition_id}
          </p>
        </div>
        <SurfaceTag tone={definitionStatusTone(definition.validation_status)}>
          {definition.validation_status === "warning" ? "Warnings" : "Ready"}
        </SurfaceTag>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        {isActive ? <SurfaceTag tone="primary">Selected</SurfaceTag> : null}
        {isPinned ? <SurfaceTag tone="warning">Pinned</SurfaceTag> : null}
        <SurfaceTag tone={definition.preview_artifact_count > 0 ? "primary" : "default"}>
          {definition.preview_artifact_count} artifacts
        </SurfaceTag>
      </div>

      <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <span>Created: {definition.created_at}</span>
        <span className="sm:text-right">{definition.element_count} elements</span>
      </div>
    </button>
  );
}

type TaskCardProps = Readonly<{
  isSelected: boolean;
  onAttach: (taskId: number) => void;
  task: ReturnType<typeof filterSimulationTasks>[number];
}>;

function TaskCard({ isSelected, onAttach, task }: TaskCardProps) {
  return (
    <div
      className={cx(
        "rounded-[1rem] border px-4 py-4 shadow-[0_10px_30px_rgba(0,0,0,0.08)] transition",
        isSelected
          ? "border-primary/40 bg-card"
          : "border-border bg-card hover:border-primary/25 hover:bg-primary/5",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground">
            {task.summary || `${taskKindLabel(task.kind)} task`}
          </h3>
          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Task #{task.taskId}
          </p>
        </div>
        <SurfaceTag tone={taskStatusTone(task.status)}>
          {task.status}
        </SurfaceTag>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <SurfaceTag tone="default">{taskKindLabel(task.kind)}</SurfaceTag>
        <SurfaceTag tone="default">{task.executionMode}</SurfaceTag>
        {task.definitionId !== null ? (
          <SurfaceTag tone="default">Definition #{task.definitionId}</SurfaceTag>
        ) : null}
        {task.datasetId ? <SurfaceTag tone="default">{task.datasetId}</SurfaceTag> : null}
      </div>

      <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <span>Submitted: {task.submittedAt}</span>
        <span className="sm:text-right">{task.ownerDisplayName}</span>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/80 pt-4">
        <p className="text-xs text-muted-foreground">
          {task.hasActionAuthority
            ? task.allowedActions.attach
              ? "Attach is allowed by backend task authority."
              : "Attach is blocked by backend task authority."
            : "Attach authority is not exposed by the backend yet."}
        </p>
        <button
          type="button"
          onClick={() => {
            onAttach(task.taskId);
          }}
          disabled={!task.allowedActions.attach}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Attach
        </button>
      </div>
    </div>
  );
}

export function SimulationWorkbenchShell() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const [definitionQuery, setDefinitionQuery] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [taskScope, setTaskScope] = useState<SimulationTaskScope>("definition");
  const [taskStatusFilter, setTaskStatusFilter] =
    useState<SimulationTaskStatusFilter>("all");
  const [isRefreshingWorkflow, setIsRefreshingWorkflow] = useState(false);

  const form = useForm<SimulationRequestValues>({
    resolver: zodResolver(simulationRequestSchema),
    defaultValues: defaultRequestValues,
  });

  const requestedDefinitionId = searchParams.get("definitionId");
  const requestedTaskId = parseTaskIdParam(searchParams.get("taskId"));
  const rawDefinitionId = parseSimulationDefinitionIdParam(requestedDefinitionId);
  const {
    session,
    activeDatasetState,
    definitions,
    definitionsError,
    isDefinitionsLoading,
    resolvedDefinitionId,
    selectedDefinitionSummary,
    activeDefinition,
    activeDefinitionError,
    isDefinitionTransitioning,
    simulationTasks,
    latestSimulationTask,
    resolvedTaskId,
    activeTask,
    activeTaskError,
    isTaskTransitioning,
    taskMutationStatus,
    submitSimulationTask,
    clearTaskMutationStatus,
    refreshSimulationWorkflow,
  } = useSimulationWorkflowData(rawDefinitionId, requestedTaskId);

  const filteredDefinitions = filterSimulationDefinitions(definitions, definitionQuery);
  const pinnedDefinition =
    resolvedDefinitionId !== null &&
    !filteredDefinitions.some(
      (definition) => definition.definition_id === resolvedDefinitionId,
    )
      ? definitions?.find((definition) => definition.definition_id === resolvedDefinitionId)
      : undefined;
  const taskSummary = summarizeSimulationTasks(simulationTasks);
  const filteredTasks = filterSimulationTasks(simulationTasks, {
    searchQuery: taskQuery,
    scope: taskScope,
    statusFilter: taskStatusFilter,
    selectedDefinitionId: resolvedDefinitionId,
    activeDatasetId: activeDatasetState.activeDataset?.datasetId ?? null,
  });
  const definitionRecovery = resolveSimulationSelectionRecovery(
    requestedDefinitionId,
    resolvedDefinitionId,
    definitions,
  );
  const taskConnectionState = resolveTaskConnectionState({
    requestedTaskId,
    resolvedTaskId,
    latestTaskId: latestSimulationTask?.taskId ?? null,
    activeTask,
  });
  const taskRecovery = resolveTaskRecoveryNotice(
    requestedTaskId,
    latestSimulationTask?.taskId ?? null,
    activeTaskError,
  );
  const taskLifecycleSummary = summarizeTaskLifecycle(activeTask);
  const taskResultSummary = summarizeTaskResultSurface(activeTask);
  const taskActionGates = summarizeTaskActionGates(activeTask);
  const taskContextBinding = summarizeTaskContextBinding({
    task: activeTask,
    activeDatasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    activeDefinitionId: resolvedDefinitionId,
  });
  const taskResultHandoff = summarizeTaskResultHandoff(activeTask, taskResultSummary);
  const eventHistorySummary = summarizeTaskEventHistory(activeTask);
  const workflowSurfaceSummary = summarizeResearchWorkflowSurface({
    connectionState: taskConnectionState,
    lifecycleSummary: taskLifecycleSummary,
    eventHistorySummary,
    resultSummary: taskResultSummary,
  });
  const normalizedPreview = buildNormalizedOutputPreview(
    activeDefinition?.normalized_output ?? "{\n  \"circuit\": \"pending\"\n}",
  );
  const requestSummaryPreview = buildSimulationRequestSummary({
    kind: "simulation",
    definitionId: resolvedDefinitionId,
    definitionName: selectedDefinitionSummary?.name ?? null,
    datasetId: activeDatasetState.activeDataset?.datasetId ?? null,
    datasetName: activeDatasetState.activeDataset?.name ?? null,
    note: form.watch("summaryNote"),
  });
  const definitionsErrorMessage = describeApiError(definitionsError);
  const activeDefinitionErrorMessage = describeApiError(activeDefinitionError);
  const activeTaskErrorMessage = describeApiError(activeTaskError);
  const eventHistoryNarrative = !activeTask
    ? "Attach or submit a simulation task to inspect its persisted dispatch trail."
    : taskConnectionState.isStaleSnapshot && resolvedTaskId !== null
      ? `Showing persisted events from task #${activeTask.taskId} while task #${resolvedTaskId} reattaches so the simulation surface stays readable during route switching.`
      : taskConnectionState.hasNewerLatestTask && taskConnectionState.latestTaskId !== null
        ? `Task #${taskConnectionState.selectedTaskId} remains attached for comparison while newer simulation activity exists on task #${taskConnectionState.latestTaskId}.`
        : latestSimulationTask && resolvedTaskId === latestSimulationTask.taskId
        ? `Following the latest simulation task #${latestSimulationTask.taskId}. Persisted events should advance here as dispatch, progress, and result publication change.`
        : `Task #${activeTask.taskId} keeps a persisted event trail alongside dispatch and progress so refreshes do not erase execution context.`;

  useEffect(() => {
    if (resolvedDefinitionId === null || resolvedDefinitionId === rawDefinitionId) {
      return;
    }

    startTransition(() => {
      router.replace(
        buildSimulationSearchHref(pathname, searchParams.toString(), {
          definitionId: String(resolvedDefinitionId),
        }),
        { scroll: false },
      );
    });
  }, [pathname, rawDefinitionId, resolvedDefinitionId, router, searchParams]);

  function replaceSearchState(updates: Readonly<Record<string, string | null>>) {
    startTransition(() => {
      router.replace(buildSimulationSearchHref(pathname, searchParams.toString(), updates), {
        scroll: false,
      });
    });
  }

  async function handleRefreshWorkflow() {
    setIsRefreshingWorkflow(true);
    try {
      await refreshSimulationWorkflow();
    } finally {
      setIsRefreshingWorkflow(false);
    }
  }

  async function handleSubmit(kind: "simulation" | "post_processing") {
    const values = await form.trigger();
    if (!values) {
      return;
    }

    const task = await submitSimulationTask({
      kind,
      note: form.getValues("summaryNote"),
    });

    replaceSearchState({
      definitionId: resolvedDefinitionId !== null ? String(resolvedDefinitionId) : null,
      taskId: String(task.taskId),
    });
  }

  return (
    <div className="space-y-8">
      <ResearchWorkflowHero
        eyebrow="Research Workflow"
        title="Circuit Simulation"
        description="Attach a canonical definition, submit persisted simulation work, and reattach to task, event, and result state without falling back to page-local placeholders."
        contextTags={[
          {
            label: selectedDefinitionSummary?.name ?? "Definition pending",
            tone: "primary",
          },
          {
            label: activeDatasetState.activeDataset?.name ?? "Dataset not attached",
            tone: activeDatasetState.activeDataset
              ? "success"
              : activeDatasetState.status === "error"
                ? "warning"
                : "default",
          },
          ...(resolvedTaskId !== null
            ? [
                {
                  label: `Task #${resolvedTaskId}`,
                  tone: taskConnectionState.isAttached ? "success" : "warning",
                } as const,
              ]
            : []),
          {
            label: taskLifecycleSummary.statusLabel,
            tone: taskLifecycleSummary.tone,
          },
          ...(taskConnectionState.isFollowingLatest
            ? [{ label: "Following latest queue task", tone: "success" as const }]
            : []),
        ]}
        submitAuthorityLabel={`Workspace submit authority: ${
          session?.canSubmitTasks ? "available" : "disabled for this session"
        }.`}
        stats={[
          { label: "Simulation Tasks", value: String(taskSummary.total) },
          { label: "Active", value: String(taskSummary.activeCount), tone: "primary" },
          { label: "Result-backed", value: String(taskSummary.resultBackedCount) },
        ]}
      />

      {definitionsError ? (
        <div className={cx("rounded-[1rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
          Unable to load circuit definitions. {definitionsErrorMessage}
        </div>
      ) : null}

      {taskMutationStatus.message ? (
        <div
          className={cx(
            "rounded-[1rem] border px-4 py-3 text-sm",
            taskMutationStatus.state === "error"
              ? resolveSurfaceInsetToneClass("error")
              : "border-primary/30 bg-primary/8 text-foreground",
          )}
        >
          {taskMutationStatus.message}
        </div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.82fr)_minmax(0,1.18fr)]">
        <div className="space-y-4">
          <SurfacePanel
            title="Canonical Definition"
            description="Simulation authority starts from the persisted circuit definition contract, not from page-local setup state."
          >
            <label className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
              <span className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                <Search className="h-3.5 w-3.5" />
                Search definitions
              </span>
              <input
                value={definitionQuery}
                onChange={(event) => {
                  setDefinitionQuery(event.target.value);
                }}
                placeholder="Find by name or id"
                className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </label>

            {definitionRecovery ? (
              <div
                className={cx(
                "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
                definitionRecovery.tone === "warning"
                    ? resolveSurfaceInsetToneClass("warning")
                    : "border-border bg-surface text-muted-foreground",
              )}
              >
                <p className="font-medium text-foreground">{definitionRecovery.title}</p>
                <p className="mt-1">{definitionRecovery.message}</p>
              </div>
            ) : null}

            {isDefinitionsLoading && !definitions ? (
              <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Loading canonical definitions...
              </div>
            ) : null}

            {pinnedDefinition ? (
              <div className="mt-4 space-y-2">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Selected definition
                </p>
                <DefinitionCard
                  definition={pinnedDefinition}
                  isActive
                  isPinned
                  onSelect={(definitionId) => {
                    clearTaskMutationStatus();
                    replaceSearchState({ definitionId: String(definitionId) });
                  }}
                />
              </div>
            ) : null}

            <div className="mt-4 space-y-3">
              {filteredDefinitions.map((definition) => (
                <DefinitionCard
                  key={definition.definition_id}
                  definition={definition}
                  isActive={definition.definition_id === resolvedDefinitionId}
                  onSelect={(definitionId) => {
                    clearTaskMutationStatus();
                    replaceSearchState({ definitionId: String(definitionId) });
                  }}
                />
              ))}
            </div>

            {filteredDefinitions.length === 0 && (definitions?.length ?? 0) > 0 ? (
              <div className="mt-4 rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                No canonical definitions match the current search.
              </div>
            ) : null}
          </SurfacePanel>

          <SurfacePanel
            title="Simulation Setup"
            description="Use the active dataset plus the selected canonical definition to submit persisted simulation or post-processing work."
          >
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Active Dataset
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDatasetState.activeDataset?.name ?? "Attach a dataset in the shell first"}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {activeDatasetState.activeDataset?.datasetId ?? "No dataset in session"}
                </p>
              </div>
              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Canonical Definition
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {selectedDefinitionSummary?.name ?? "Select a definition"}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {resolvedDefinitionId !== null
                    ? `Definition #${resolvedDefinitionId}`
                    : "No definition selected"}
                </p>
              </div>
            </div>

            <form
              className="mt-4 space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
              }}
            >
              <label className="block rounded-[0.9rem] border border-border bg-surface px-4 py-3">
                <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Request Note
                </span>
                <textarea
                  {...form.register("summaryNote")}
                  rows={4}
                  placeholder="Optional context for this run, for example basis check or cache verification."
                  className="w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
                />
              </label>
              {form.formState.errors.summaryNote ? (
                <p className="text-sm text-rose-700 dark:text-rose-300">
                  {form.formState.errors.summaryNote.message}
                </p>
              ) : null}

              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Submission Preview
                </p>
                <p className="mt-2 text-foreground">{requestSummaryPreview}</p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => {
                    void handleSubmit("simulation");
                  }}
                  disabled={
                    taskMutationStatus.state === "submitting" ||
                    !session?.canSubmitTasks ||
                    !activeDatasetState.activeDataset ||
                    resolvedDefinitionId === null
                  }
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Play className="h-4 w-4" />
                  Run Simulation
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleSubmit("post_processing");
                  }}
                  disabled={
                    taskMutationStatus.state === "submitting" ||
                    !session?.canSubmitTasks ||
                    !activeDatasetState.activeDataset ||
                    resolvedDefinitionId === null
                  }
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-surface px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <WandSparkles className="h-4 w-4" />
                  Run Post Processing
                </button>
              </div>
            </form>
          </SurfacePanel>

          <ResearchTaskQueuePanel
            title="Simulation Task Queue"
            description="Inspect recent simulation and post-processing tasks, then attach a task into the shared research workflow surface."
            searchValue={taskQuery}
            onSearchChange={setTaskQuery}
            searchPlaceholder="Find by task id, summary, or dataset"
            scopeValue={taskScope}
            onScopeChange={(value) => {
              setTaskScope(value as SimulationTaskScope);
            }}
            scopeOptions={simulationTaskScopeOptions}
            statusValue={taskStatusFilter}
            onStatusChange={(value) => {
              setTaskStatusFilter(value as SimulationTaskStatusFilter);
            }}
            statusOptions={simulationTaskStatusOptions}
            summaryLabel={`Showing ${filteredTasks.length} of ${simulationTasks.length} simulation tasks`}
            summaryTags={[
              ...(taskConnectionState.mode === "explicit" && resolvedTaskId !== null
                ? [{ label: `Locked to task #${resolvedTaskId}`, tone: "warning" as const }]
                : []),
              ...(taskConnectionState.isFollowingLatest && taskConnectionState.latestTaskId !== null
                ? [
                    {
                      label: `Following latest #${taskConnectionState.latestTaskId}`,
                      tone: "success" as const,
                    },
                  ]
                : []),
            ]}
            isRefreshing={isRefreshingWorkflow}
            onRefresh={() => {
              void handleRefreshWorkflow();
            }}
            isEmpty={filteredTasks.length === 0}
            emptyMessage="No simulation tasks match the current filters."
          >
            {filteredTasks.map((task) => (
              <TaskCard
                key={task.taskId}
                isSelected={task.taskId === resolvedTaskId}
                onAttach={(taskId) => {
                  replaceSearchState({ taskId: String(taskId) });
                }}
                task={task}
              />
            ))}
          </ResearchTaskQueuePanel>
        </div>

        <div className="space-y-4">
          <ResearchWorkflowOverviewPanel
            summary={workflowSurfaceSummary}
            narrative={eventHistoryNarrative}
          />

          <TaskAttachmentPanel
            task={activeTask}
            connectionState={taskConnectionState}
            recoveryNotice={taskRecovery}
            taskErrorMessage={activeTaskErrorMessage}
            isRefreshing={isRefreshingWorkflow}
            isTransitioning={isTaskTransitioning}
            onRefresh={() => {
              void handleRefreshWorkflow();
            }}
            onAttachLatest={
              latestSimulationTask
                ? () => {
                    replaceSearchState({ taskId: String(latestSimulationTask.taskId) });
                  }
                : null
            }
            onFollowLatest={() => {
              replaceSearchState({ taskId: null });
            }}
          />

          <TaskLifecyclePanel task={activeTask} summary={taskLifecycleSummary} />

          <SurfacePanel
            title="Task Controls / Result Handoff"
            description="Attach follows backend `allowed_actions.attach`. Cancel, terminate, and retry remain gated by backend action authority even before the control mutation adapter is wired."
          >
            <div className="grid gap-3 md:grid-cols-4">
              {[
                taskActionGates.attach,
                taskActionGates.cancel,
                taskActionGates.terminate,
                taskActionGates.retry,
              ].map((gate) => (
                <div
                  key={gate.action}
                  className={cx(
                    "rounded-[0.9rem] border px-4 py-4",
                    gate.enabled
                      ? "border-primary/25 bg-primary/10"
                      : "border-border bg-surface",
                  )}
                >
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    {gate.action}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-foreground">
                    {gate.enabled ? "Allowed" : "Blocked"}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">{gate.reason}</p>
                </div>
              ))}
            </div>

            {!taskActionGates.hasActionAuthority ? (
              <div className={cx("mt-4 rounded-[0.9rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("warning"))}>
                Backend `allowed_actions` are not present in the current task payload, so control
                buttons stay gated instead of guessing permissions in the page body.
              </div>
            ) : null}

            {taskContextBinding ? (
              <div
                className={cx(
                "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
                taskContextBinding.tone === "warning"
                    ? resolveSurfaceInsetToneClass("warning")
                    : resolveSurfaceInsetToneClass("success"),
              )}
              >
                <p className="font-medium">{taskContextBinding.title}</p>
                <p className="mt-1">{taskContextBinding.message}</p>
              </div>
            ) : null}

            <div
              className={cx(
                "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
                taskResultHandoff.tone === "success"
                  ? resolveSurfaceInsetToneClass("success")
                  : taskResultHandoff.tone === "warning"
                    ? resolveSurfaceInsetToneClass("warning")
                    : taskResultHandoff.tone === "primary"
                      ? "border-primary/30 bg-primary/8 text-foreground"
                      : "border-border bg-surface text-muted-foreground",
              )}
            >
              <p className="font-medium">{taskResultHandoff.title}</p>
              <p className="mt-1">{taskResultHandoff.message}</p>
              {taskResultHandoff.isReady ? (
                <p className="mt-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Persisted result refs stay available in the panel below after refresh or reattach.
                </p>
              ) : null}
            </div>
          </SurfacePanel>

          <TaskEventHistoryPanel
            title="Task Event History"
            description="Inspect persisted event records so dispatch changes, progress movement, and task outcomes remain readable after refresh or recovery."
            task={activeTask}
            narrative={eventHistoryNarrative}
            emptyMessage="No persisted simulation task events are attached yet. Submit or attach a task to inspect its backend event history."
          />

          <TaskResultPanel task={activeTask} summary={taskResultSummary} />

          <SurfacePanel
            title="Canonical Definition Snapshot"
            description="The simulation surface stays anchored to the selected backend definition detail, even while task state refreshes or reattaches."
          >
            {activeDefinitionError ? (
              <div className={cx("rounded-[0.9rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
                Unable to load definition detail. {activeDefinitionErrorMessage}
              </div>
            ) : null}

            {isDefinitionTransitioning && resolvedDefinitionId !== null ? (
              <div className="mb-4 flex items-center gap-3 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Refreshing canonical definition detail...
              </div>
            ) : null}

            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Definition
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDefinition?.name ?? "None selected"}
                </p>
              </div>
              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Validation
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDefinition?.validation_status ?? "pending"}
                </p>
              </div>
              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Preview Fields
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {normalizedPreview.fieldCount}
                </p>
              </div>
              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Source Lines
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDefinition ? lineCount(activeDefinition.source_text) : 0}
                </p>
              </div>
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <div className="space-y-3">
                {normalizedPreview.fields.slice(0, 6).map((field) => (
                  <div
                    key={field.key}
                    className="rounded-[0.9rem] border border-border bg-surface px-4 py-3"
                  >
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      {field.label}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-foreground">{field.value}</p>
                  </div>
                ))}
                {normalizedPreview.fields.length === 0 ? (
                  <div className="rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
                    No structured normalized output is available for the selected definition yet.
                  </div>
                ) : null}
              </div>

              <div className="rounded-[0.9rem] border border-border bg-background">
                <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <FileCode2 className="h-4 w-4" />
                    <span>source_text.yml</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Waypoints className="h-4 w-4" />
                    <span>simulation authority</span>
                  </div>
                </div>
                <pre className="max-h-[22rem] overflow-auto px-4 py-4 text-sm leading-6 text-foreground">
                  {activeDefinition?.source_text ?? "circuit:\n  name: pending_selection\n"}
                </pre>
              </div>
            </div>
          </SurfacePanel>
        </div>
      </section>
    </div>
  );
}
