"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ExternalLink, Save } from "lucide-react";
import { useSWRConfig } from "swr";

import { buildRawDataBrowseHref } from "@/features/data-browser/lib/browse-state";
import {
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import { ApiError } from "@/lib/api/client";
import {
  publishSimulationResult,
  taskDetailKey,
  tasksListKey,
  type TaskDetail,
  type TaskPublicationSummary,
} from "@/lib/api/tasks";

type SimulationResultPublicationCardProps = Readonly<{
  task: TaskDetail;
  definitionName: string | null;
  activeDatasetId: string | null;
}>;

type PublicationMutationState = Readonly<{
  state: "idle" | "saving" | "success" | "error";
  message: string | null;
}>;

const josephsonExamplePrefix = "JosephsonCircuits Examples: ";

function derivePublicationDesignName(definitionName: string | null, taskId: number) {
  if (definitionName) {
    const trimmed = definitionName.startsWith(josephsonExamplePrefix)
      ? definitionName.slice(josephsonExamplePrefix.length)
      : definitionName;
    const normalized = trimmed.trim();
    if (normalized) {
      return normalized;
    }
  }

  return `Simulation Result ${taskId}`;
}

function describePublicationError(error: unknown) {
  if (error instanceof ApiError) {
    switch (error.errorCode) {
      case "simulation_result_publish_not_ready":
        return "This task result is not publishable yet. Wait for a completed task with ready persisted results.";
      case "simulation_result_publish_task_invalid":
        return "Only completed simulation runs can be promoted into research data from this stage.";
      default:
        break;
    }

    switch (error.category) {
      case "validation_error":
        return "Review the research-data target before saving this result.";
      case "not_found":
        return "The research-data destination is no longer available in the current dataset context.";
      case "conflict":
        return "This task result cannot be published in its current lifecycle state.";
      case "persistence_error":
      case "trace_store_error":
        return error.retryable
          ? "The save failed while writing research data. Retry is available."
          : "The save failed while writing research data.";
      default:
        break;
    }
  }

  return "Unable to save this task result as research data right now.";
}

function publicationTone(summary: TaskPublicationSummary) {
  if (summary.state === "published") {
    return "success" as const;
  }
  if (summary.publishAllowed) {
    return "primary" as const;
  }
  return "default" as const;
}

export function SimulationResultPublicationCard({
  task,
  definitionName,
  activeDatasetId,
}: SimulationResultPublicationCardProps) {
  const { mutate } = useSWRConfig();
  const publicationSummary =
    task.publicationSummary ??
    ({
      state: "not_published",
      publishAllowed: false,
      publicationKey: null,
      targetDatasetId: null,
      targetDesignId: null,
      targetDesignName: null,
      publishedTraceIds: [],
      publishedAt: null,
      sourceTaskId: task.taskId,
      sourceResultHandleIds: task.resultRefs.resultHandles.map((handle) => handle.handleId),
    } satisfies TaskPublicationSummary);
  const [designNameDraft, setDesignNameDraft] = useState(() =>
    publicationSummary.targetDesignName ??
    derivePublicationDesignName(definitionName, task.taskId),
  );
  const [mutationState, setMutationState] = useState<PublicationMutationState>({
    state: "idle",
    message: null,
  });

  useEffect(() => {
    setDesignNameDraft(
      publicationSummary.targetDesignName ??
        derivePublicationDesignName(definitionName, task.taskId),
    );
  }, [definitionName, publicationSummary.targetDesignName, task.taskId]);

  useEffect(() => {
    setMutationState({ state: "idle", message: null });
  }, [task.taskId]);

  const publishedTraceCount = publicationSummary.publishedTraceIds.length;
  const rawDataHref = useMemo(() => {
    if (
      publicationSummary.state !== "published" ||
      !publicationSummary.targetDesignId
    ) {
      return null;
    }

    return buildRawDataBrowseHref({
      designId: publicationSummary.targetDesignId,
      traceId: publicationSummary.publishedTraceIds[0] ?? null,
      designQuery: publicationSummary.targetDesignId,
    });
  }, [
    publicationSummary.publishedTraceIds,
    publicationSummary.state,
    publicationSummary.targetDesignId,
  ]);
  const canOpenRawDataBrowser =
    rawDataHref !== null &&
    publicationSummary.targetDatasetId !== null &&
    publicationSummary.targetDatasetId === activeDatasetId;

  async function handlePublish() {
    const nextDesignName = designNameDraft.trim();
    if (!nextDesignName) {
      setMutationState({
        state: "error",
        message: "Research design name is required before saving this result.",
      });
      return;
    }

    setMutationState({ state: "saving", message: null });
    try {
      const result = await publishSimulationResult(task.taskId, {
        datasetId: task.datasetId,
        designName: nextDesignName,
      });
      await mutate(taskDetailKey(task.taskId), result.task, { revalidate: false });
      await mutate(tasksListKey);
      setMutationState({
        state: "success",
        message:
          result.operation === "already_published"
            ? "This task result was already published to the same research-data destination."
            : "Saved this task result into durable research data.",
      });
    } catch (error) {
      setMutationState({
        state: "error",
        message: describePublicationError(error),
      });
    }
  }

  return (
    <div className="rounded-[0.95rem] border border-border/80 bg-background px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Task Result to Research Data
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            The explorer is task-scoped. Save Result promotes this output into durable
            dataset-owned research data.
          </p>
        </div>
        <SurfaceTag tone={publicationTone(publicationSummary)}>
          {publicationSummary.state === "published"
            ? "Research Data published"
            : publicationSummary.publishAllowed
              ? "Ready to save"
              : "Task Result only"}
        </SurfaceTag>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,0.88fr)_auto_minmax(0,1.12fr)]">
        <div className="rounded-[0.95rem] border border-border bg-card px-4 py-4">
          <div className="flex items-center gap-2">
            <SurfaceTag tone="primary">Task Result</SurfaceTag>
            <p className="text-xs text-muted-foreground">Execution-scoped</p>
          </div>
          <p className="mt-3 text-sm font-medium text-foreground">Explorer attached to task #{task.taskId}</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Inspect, compare, and validate the persisted result handles before deciding whether
            this run should become durable research data.
          </p>
        </div>

        <div className="hidden items-center justify-center lg:flex">
          <ArrowRight className="h-4 w-4 text-muted-foreground" />
        </div>

        <div className="rounded-[0.95rem] border border-border bg-card px-4 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <SurfaceTag tone={publicationSummary.state === "published" ? "success" : "default"}>
              Research Data
            </SurfaceTag>
            <p className="text-xs text-muted-foreground">Dataset / design owned</p>
          </div>

          {publicationSummary.state === "published" ? (
            <>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-[0.85rem] border border-border/80 bg-background px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Dataset
                  </p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {publicationSummary.targetDatasetId ?? "--"}
                  </p>
                </div>
                <div className="rounded-[0.85rem] border border-border/80 bg-background px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Design
                  </p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {publicationSummary.targetDesignName ??
                      publicationSummary.targetDesignId ??
                      "--"}
                  </p>
                </div>
                <div className="rounded-[0.85rem] border border-border/80 bg-background px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Published
                  </p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {publishedTraceCount} trace{publishedTraceCount === 1 ? "" : "s"}
                  </p>
                </div>
              </div>

              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                This task result is already durable research data. Browse the target design in
                Raw Data when you want to inspect the published traces directly.
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                {canOpenRawDataBrowser && rawDataHref ? (
                  <Link
                    href={rawDataHref}
                    className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Open in Raw Data Browser
                  </Link>
                ) : null}
                {!canOpenRawDataBrowser && publicationSummary.targetDatasetId ? (
                  <p className="text-xs leading-5 text-muted-foreground">
                    Activate dataset {publicationSummary.targetDatasetId} in the shell before
                    opening the published destination in Raw Data Browser.
                  </p>
                ) : null}
              </div>
            </>
          ) : publicationSummary.publishAllowed ? (
            <>
              <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_200px]">
                <label className="min-w-0">
                  <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Research Design Name
                  </p>
                  <input
                    value={designNameDraft}
                    onChange={(event) => {
                      setDesignNameDraft(event.target.value);
                    }}
                    placeholder="Published design name"
                    className="w-full rounded-[0.9rem] border border-border/85 bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15"
                  />
                </label>
                <div className="rounded-[0.9rem] border border-border/80 bg-background px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    Target Dataset
                  </p>
                  <p className="mt-2 text-sm font-medium text-foreground">
                    {task.datasetId ?? activeDatasetId ?? "--"}
                  </p>
                </div>
              </div>

              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Save Result creates durable research-data traces from this task result without
                changing the task-backed explorer itself.
              </p>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={handlePublish}
                  disabled={mutationState.state === "saving"}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/45 hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Save className="h-3.5 w-3.5" />
                  {mutationState.state === "saving" ? "Saving Result..." : "Save Result"}
                </button>
              </div>
            </>
          ) : (
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              This output is still only a task result. Save Result appears once the backend marks
              the current simulation result publishable.
            </p>
          )}
        </div>
      </div>

      {mutationState.message ? (
        <div
          className={cx(
            "mt-4 rounded-[0.9rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass(
              mutationState.state === "error"
                ? "error"
                : mutationState.state === "success"
                  ? "success"
                  : "primary",
            ),
          )}
        >
          {mutationState.message}
        </div>
      ) : null}
    </div>
  );
}
