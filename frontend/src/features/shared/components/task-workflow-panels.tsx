import Link from "next/link";
import { LoaderCircle, RefreshCcw } from "lucide-react";

import type { TaskDetail, TaskExecutionStatus, TaskResultHandleRef } from "@/lib/api/tasks";
import {
  formatTaskConnectionModeLabel,
  groupTaskResultHandles,
  type TaskConnectionState,
  type TaskLifecycleSummary,
  type TaskRecoveryNotice,
  type TaskResultSurfaceSummary,
} from "@/lib/task-surface";

import {
  SurfacePanel,
  SurfaceStat,
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "./surface-kit";

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

function formatHandleKindLabel(kind: TaskResultHandleRef["kind"]) {
  return kind.split("_").map((segment) => segment[0]?.toUpperCase() + segment.slice(1)).join(" ");
}

type TaskAttachmentPanelProps = Readonly<{
  task: TaskDetail | undefined;
  connectionState: TaskConnectionState;
  recoveryNotice: TaskRecoveryNotice;
  taskErrorMessage: string | null;
  isRefreshing: boolean;
  isTransitioning: boolean;
  onRefresh: () => void;
  onAttachLatest?: (() => void) | null;
  onFollowLatest?: (() => void) | null;
}>;

export function TaskAttachmentPanel({
  task,
  connectionState,
  recoveryNotice,
  taskErrorMessage,
  isRefreshing,
  isTransitioning,
  onRefresh,
  onAttachLatest = null,
  onFollowLatest = null,
}: TaskAttachmentPanelProps) {
  return (
    <SurfacePanel
      title="Task Attachment / Recovery"
      description="Attach task detail safely, refresh it in place, and recover from stale URL state without leaving the persisted task/result workflow."
      actions={
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCcw className={cx("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
          Refresh surface
        </button>
      }
    >
      <div className="grid gap-3 md:grid-cols-5">
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Selected Task
          </p>
          <p className="mt-2 text-lg font-semibold text-foreground">
            {connectionState.selectedTaskId ?? "--"}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Attached Snapshot
          </p>
          <p className="mt-2 text-lg font-semibold text-foreground">
            {connectionState.attachedTaskId ?? "--"}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Latest Queue Task
          </p>
          <p className="mt-2 text-lg font-semibold text-foreground">
            {connectionState.latestTaskId ?? "--"}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Connection Mode
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {formatTaskConnectionModeLabel(connectionState.mode)}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Worker Task
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {task?.workerTaskName ?? "--"}
          </p>
        </div>
      </div>

      {recoveryNotice ? (
        <div
          className={cx(
            "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass("warning"),
          )}
        >
          <p className="font-medium">{recoveryNotice.title}</p>
          <p className="mt-1">{recoveryNotice.message}</p>
          {connectionState.latestTaskId !== null && onAttachLatest ? (
            <button
              type="button"
              onClick={onAttachLatest}
              className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-full border border-amber-500/30 px-3 py-1.5 text-xs font-medium transition hover:bg-amber-500/10"
            >
              Attach latest task #{connectionState.latestTaskId}
            </button>
          ) : null}
        </div>
      ) : null}

      {connectionState.isFollowingLatest && connectionState.latestTaskId !== null ? (
        <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-3 text-sm text-muted-foreground">
          This surface is following the latest persisted task for the current workspace state. Add
          a `taskId` to the URL only when you want to pin an older task for comparison.
        </div>
      ) : null}

      {connectionState.hasNewerLatestTask && connectionState.latestTaskId !== null ? (
        <div className={cx("mt-4 rounded-[0.9rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("primary"))}>
          <p className="font-medium">Newer task available</p>
          <p className="mt-1">
            You are inspecting task #{connectionState.selectedTaskId}, while newer persisted
            activity exists on task #{connectionState.latestTaskId}. Keep the current attachment
            for comparison, or switch back to the latest task.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {onAttachLatest ? (
              <button
                type="button"
                onClick={onAttachLatest}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 px-3 py-1.5 text-xs font-medium transition hover:bg-primary/10"
              >
                Attach latest #{connectionState.latestTaskId}
              </button>
            ) : null}
            {onFollowLatest ? (
              <button
                type="button"
                onClick={onFollowLatest}
                className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/10"
              >
                Follow latest automatically
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {taskErrorMessage ? (
        <div
          className={cx(
            "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass("error"),
          )}
        >
          Unable to load task detail. {taskErrorMessage}
        </div>
      ) : null}

      {connectionState.isStaleSnapshot &&
      connectionState.attachedTaskId !== null &&
      connectionState.selectedTaskId !== null ? (
        <div
          className={cx(
            "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass("warning"),
          )}
        >
          Retaining task #{connectionState.attachedTaskId} while task #
          {connectionState.selectedTaskId} attaches so the task/result surface stays readable
          during refresh or route switching.
        </div>
      ) : null}

      {isTransitioning && connectionState.selectedTaskId !== null ? (
        <div className="mt-4 flex items-center gap-3 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Reattaching task detail...
        </div>
      ) : null}
    </SurfacePanel>
  );
}

type TaskLifecyclePanelProps = Readonly<{
  task: TaskDetail | undefined;
  summary: TaskLifecycleSummary;
}>;

export function TaskLifecyclePanel({ task, summary }: TaskLifecyclePanelProps) {
  return (
    <SurfacePanel
      title="Dispatch / Execution Status"
      description="Track persisted dispatch authority, worker progress, and request readiness using the same task contract across workflow surfaces."
    >
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Dispatch</p>
          <p className="mt-2 text-lg font-semibold text-foreground">{summary.statusLabel}</p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Backend Status
          </p>
          <p className="mt-2 text-lg font-semibold text-foreground">
            {summary.backendStatusLabel}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Progress</p>
          <p className="mt-2 text-lg font-semibold text-foreground">{summary.progressPercent}%</p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Worker Task
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {summary.workerTaskName ?? "--"}
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">{summary.summary}</p>
        <p className="mt-2">{summary.progressSummary}</p>
      </div>

      <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4">
        <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
          <span>Progress meter</span>
          <span>{summary.progressPercent}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-background">
          <div
            className={cx(
              "h-full rounded-full transition-[width]",
              summary.tone === "warning"
                ? "bg-amber-400"
                : summary.tone === "success"
                  ? "bg-emerald-400"
                  : "bg-primary",
            )}
            style={{ width: `${summary.progressPercent}%` }}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Submission Source
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {summary.submissionSourceLabel ?? "--"}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Accepted At
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {summary.acceptedAt ?? "--"}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Last Updated
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {summary.lastUpdatedAt ?? "--"}
          </p>
        </div>
        <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Task Dataset
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {summary.taskDatasetId ?? "--"}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
        {task ? (
          <>
            <SurfaceTag tone={summary.requestReady ? "success" : "warning"}>
              {summary.requestReady ? "Request ready" : "Request not ready"}
            </SurfaceTag>
            <SurfaceTag tone={summary.submittedFromActiveDataset ? "success" : "warning"}>
              {summary.submittedFromActiveDataset
                ? "Submitted from active dataset"
                : "Dataset detached from session"}
            </SurfaceTag>
            {summary.dispatchKey ? <SurfaceTag tone={summary.tone}>{summary.dispatchKey}</SurfaceTag> : null}
            {summary.executionMode ? <SurfaceTag tone="default">{summary.executionMode}</SurfaceTag> : null}
            {summary.visibilityScope ? <SurfaceTag tone="default">{summary.visibilityScope}</SurfaceTag> : null}
          </>
        ) : (
          <SurfaceTag tone="default">No task attached</SurfaceTag>
        )}
      </div>
    </SurfacePanel>
  );
}

type TaskResultPanelProps = Readonly<{
  task: TaskDetail | undefined;
  summary: TaskResultSurfaceSummary;
  showTasksPageLink?: boolean;
}>;

export function TaskResultPanel({
  task,
  summary,
  showTasksPageLink = true,
}: TaskResultPanelProps) {
  const groupedHandles = groupTaskResultHandles(task);

  return (
    <SurfacePanel
      title="Persisted Result Surface"
      description="Inspect trace payloads, metadata records, and result handles directly from the persisted task contract."
      actions={
        task && showTasksPageLink ? (
          <Link
            href={`/tasks?taskId=${task.taskId}`}
            className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
          >
            Open Tasks Page
          </Link>
        ) : null
      }
    >
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <SurfaceStat
          label="Trace Batch"
          value={summary.traceBatchId !== null ? String(summary.traceBatchId) : "--"}
        />
        <SurfaceStat
          label="Analysis Run"
          value={summary.analysisRunId !== null ? String(summary.analysisRunId) : "--"}
        />
        <SurfaceStat
          label="Materialized"
          value={String(summary.materializedHandleCount)}
          tone="primary"
        />
        <SurfaceStat label="Pending" value={String(summary.pendingHandleCount)} />
        <SurfaceStat label="Metadata" value={String(summary.metadataRecordCount)} />
        <SurfaceStat label="Trace Payload" value={summary.hasTracePayload ? "present" : "none"} />
      </div>

      <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
        {task ? (
          <>
            <p className="font-medium text-foreground">
              {summary.materializedHandleCount > 0
                ? "Persisted task outputs are available for reattachment."
                : "This task has not materialized outputs yet."}
            </p>
            <p className="mt-2">
              Trace payload authority:{" "}
              {summary.hasTracePayload
                ? "present and linked from task result refs"
                : "not yet materialized in the task result refs"}
              .
            </p>
            {summary.handleKindCounts.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                {summary.handleKindCounts.map((entry) => (
                  <SurfaceTag key={entry.kind} tone="default">
                    {formatHandleKindLabel(entry.kind)} {entry.count}
                  </SurfaceTag>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          "Attach a task to inspect its persisted result surface."
        )}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Trace Payload
            </p>
            <SurfaceTag tone={task?.resultRefs.tracePayload ? "success" : "default"}>
              {task?.resultRefs.tracePayload ? "attached" : "pending"}
            </SurfaceTag>
          </div>
          {task?.resultRefs.tracePayload ? (
            <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">
                {task.resultRefs.tracePayload.backend} · {task.resultRefs.tracePayload.payloadRole}
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <p>Store key: {task.resultRefs.tracePayload.storeKey}</p>
                <p className="sm:text-right">
                  Schema: {task.resultRefs.tracePayload.schemaVersion}
                </p>
                <p>Group: {task.resultRefs.tracePayload.groupPath}</p>
                <p className="sm:text-right">Array: {task.resultRefs.tracePayload.arrayPath}</p>
                <p>
                  {task.resultRefs.tracePayload.dtype} · shape{" "}
                  {task.resultRefs.tracePayload.shape.join(" × ")}
                </p>
                <p className="sm:text-right">
                  Chunks {task.resultRefs.tracePayload.chunkShape.join(" × ")}
                </p>
              </div>
              <p className="mt-3 break-all">{task.resultRefs.tracePayload.storeUri}</p>
            </div>
          ) : (
            <div className="rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              No trace payload ref is attached to the current task yet.
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Metadata Records
              </p>
              <SurfaceTag tone={summary.metadataRecordCount > 0 ? "primary" : "default"}>
                {summary.metadataRecordCount}
              </SurfaceTag>
            </div>
            {task?.resultRefs.metadataRecords.length ? (
              task.resultRefs.metadataRecords.map((record) => (
                <div
                  key={`${record.recordType}-${record.recordId}`}
                  className="rounded-[0.9rem] border border-border bg-surface px-4 py-3 text-sm"
                >
                  <p className="font-medium text-foreground">
                    {record.recordType} · {record.recordId}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {record.backend} · v{record.version} · {record.schemaVersion}
                  </p>
                </div>
              ))
            ) : (
              <div className="rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
                No metadata records have been surfaced for this task yet.
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <TaskResultHandleGroup
            title="Materialized Handles"
            handles={groupedHandles.materialized}
            emptyMessage="No materialized result handles are attached to the current task yet."
          />
          <TaskResultHandleGroup
            title="Pending Handles"
            handles={groupedHandles.pending}
            emptyMessage="No pending result handles remain on the current task."
          />
        </div>
      </div>
    </SurfacePanel>
  );
}

type TaskResultHandleGroupProps = Readonly<{
  title: string;
  handles: readonly TaskResultHandleRef[];
  emptyMessage: string;
}>;

function TaskResultHandleGroup({
  title,
  handles,
  emptyMessage,
}: TaskResultHandleGroupProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{title}</p>
        <SurfaceTag tone={handles.length > 0 ? "primary" : "default"}>{handles.length}</SurfaceTag>
      </div>
      {handles.length > 0 ? (
        handles.map((handle) => (
          <div
            key={handle.handleId}
            className="rounded-[0.9rem] border border-border bg-surface px-4 py-4"
          >
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <SurfaceTag
                tone={taskStatusTone(handle.status === "materialized" ? "completed" : "queued")}
              >
                {handle.status}
              </SurfaceTag>
              <SurfaceTag tone="default">{formatHandleKindLabel(handle.kind)}</SurfaceTag>
              {handle.payloadFormat ? <SurfaceTag tone="default">{handle.payloadFormat}</SurfaceTag> : null}
              {handle.payloadBackend ? (
                <SurfaceTag tone="default">{handle.payloadBackend}</SurfaceTag>
              ) : null}
            </div>
            <p className="mt-3 text-sm font-semibold text-foreground">{handle.label}</p>
            <p className="mt-1 break-all text-xs text-muted-foreground">
              {handle.payloadLocator ?? handle.handleId}
            </p>
            <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
              <span>
                Metadata: {handle.metadataRecord.recordType} · {handle.metadataRecord.recordId}
              </span>
              <span className="sm:text-right">Schema: {handle.metadataRecord.schemaVersion}</span>
              <span>Source task: {handle.provenance.sourceTaskId ?? "--"}</span>
              <span className="sm:text-right">
                Dataset: {handle.provenance.sourceDatasetId ?? "--"}
              </span>
            </div>
          </div>
        ))
      ) : (
        <div className="rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
          {emptyMessage}
        </div>
      )}
    </div>
  );
}
