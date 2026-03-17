"use client";

import {
  useEffect,
  useState,
  type ComponentType,
  type ReactNode,
  type RefObject,
} from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import {
  AlertTriangle,
  Database,
  FolderKanban,
  Globe,
  LoaderCircle,
  RefreshCw,
  ServerCog,
  Workflow,
} from "lucide-react";

import { ShellSidePanel } from "@/components/layout/shell-side-panel";
import {
  describeShellError,
  filterShellDatasets,
  resolveRuntimeModeLabel,
  resolveSessionWorkspaceLabel,
  resolveShellActiveDatasetSummary,
  resolveShellConnectionTargetLabel,
  resolveShellTaskHref,
  resolveShellTaskLabel,
  resolveShellWorkspaceMemberships,
  resolveWorkspaceSwitchNotice,
  subscribeToGlobalContextRequests,
  type ShellGlobalContextSection,
} from "@/components/layout/workspace-shell-contract";
import { ShellNotice } from "@/components/layout/shell-notice";
import { cx } from "@/features/shared/components/surface-kit";
import { datasetCatalogKey, listDatasetCatalog } from "@/lib/api/datasets";
import type { TaskExecutionStatus, WorkerLaneSummary } from "@/lib/api/tasks";
import { useActiveDataset, useActiveTask, useAppSession, useDeveloperMode, useTaskQueue } from "@/lib/app-state";
import type { RuntimeAuthTransition, RuntimeMode } from "@/lib/api/session";

type WorkspaceStatusStripProps = Readonly<{
  open: boolean;
  onOpenChange: (nextOpen: boolean) => void;
  interactionBoundaryRef?: RefObject<HTMLElement | null>;
}>;

type ContextSectionId = ShellGlobalContextSection;

type SurfaceNotice = Readonly<{
  tone: "success" | "info" | "warning" | "error";
  message: string;
}> | null;

function ActionButton({
  label,
  onClick,
  disabled = false,
  spinning = false,
}: Readonly<{
  label: string;
  onClick: () => void;
  disabled?: boolean;
  spinning?: boolean;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <RefreshCw className={cx("h-3.5 w-3.5", spinning && "animate-spin")} />
      {label}
    </button>
  );
}

function RuntimeModeCard({
  label,
  title,
  details,
  active = false,
  disabled = false,
  onClick,
}: Readonly<{
  label: string;
  title: string;
  details: readonly string[];
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "flex min-h-[188px] w-full cursor-pointer flex-col items-start justify-between rounded-[1.1rem] border px-4 py-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-60",
        active
          ? "border-primary/40 bg-primary/12 text-foreground shadow-[0_16px_34px_rgba(37,99,235,0.16)]"
          : "border-border bg-background text-foreground hover:border-primary/35 hover:bg-primary/10 hover:shadow-[0_16px_32px_rgba(15,23,42,0.08)]",
      )}
    >
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </p>
        <p className="mt-2 text-base font-semibold text-foreground">{title}</p>
      </div>
      <div className="space-y-2">
        {details.map((detail) => (
          <p key={detail} className="text-sm leading-6 text-foreground/74 dark:text-foreground/74">
            {detail}
          </p>
        ))}
      </div>
    </button>
  );
}

function SectionFrame({
  icon: Icon,
  title,
  description,
  actions,
  children,
}: Readonly<{
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
}>) {
  return (
    <section className="rounded-[1rem] border border-border bg-surface px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 pb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Icon className="h-4 w-4" />
            </span>
            <p className="text-sm font-semibold text-foreground">{title}</p>
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function CompactContextCard({
  label,
  value,
  detail,
  icon: Icon,
}: Readonly<{
  label: string;
  value: string;
  detail: string;
  icon: ComponentType<{ className?: string }>;
}>) {
  return (
    <div className="rounded-[1rem] border border-border/90 bg-background px-4 py-3 shadow-[0_8px_22px_rgba(15,23,42,0.06)]">
      <div className="flex items-start gap-3">
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-foreground">{value}</p>
          <p className="mt-1 text-xs leading-5 text-foreground/74 dark:text-foreground/74">{detail}</p>
        </div>
      </div>
    </div>
  );
}

function ContextSectionCard({
  id,
  label,
  value,
  detail,
  icon: Icon,
  selected,
  onSelect,
}: Readonly<{
  id: ContextSectionId;
  label: string;
  value: string;
  detail: string;
  icon: ComponentType<{ className?: string }>;
  selected: boolean;
  onSelect: (section: ContextSectionId) => void;
}>) {
  return (
    <button
      type="button"
      onClick={() => {
        onSelect(id);
      }}
      aria-pressed={selected}
      className={cx(
        "relative cursor-pointer rounded-[1rem] border px-4 py-3 text-left transition hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card active:translate-y-0",
        selected
          ? "border-primary/45 bg-primary/12 shadow-[0_16px_34px_rgba(37,99,235,0.16)]"
          : "border-border/90 bg-background shadow-[0_10px_24px_rgba(15,23,42,0.06)] hover:border-primary/25 hover:bg-surface-elevated hover:shadow-[0_16px_32px_rgba(15,23,42,0.1)]",
      )}
    >
      <span
        className={cx(
          "absolute left-3 top-3 h-2.5 w-2.5 rounded-full border border-background/80 transition",
          selected ? "bg-primary shadow-[0_0_0_3px_rgba(37,99,235,0.16)]" : "bg-border",
        )}
      />
      <div className="flex items-start gap-3 pl-3.5">
        <span
          className={cx(
            "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
            selected ? "bg-primary/14 text-primary" : "bg-primary/8 text-primary/90",
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-foreground">{value}</p>
          <p className="mt-1 text-xs leading-5 text-foreground/74 dark:text-foreground/74">{detail}</p>
        </div>
      </div>
    </button>
  );
}

function buildContextResetSearch(
  pathname: string,
  searchParams: URLSearchParams,
): string {
  const params = new URLSearchParams(searchParams.toString());
  for (const key of ["datasetId", "taskId", "definitionId"]) {
    params.delete(key);
  }
  const nextSearch = params.toString();
  return nextSearch.length > 0 ? `${pathname}?${nextSearch}` : pathname;
}

function formatTaskStatusLabel(status: TaskExecutionStatus) {
  switch (status) {
    case "queued":
    case "dispatching":
      return "Pending";
    case "running":
    case "cancellation_requested":
    case "cancelling":
    case "termination_requested":
      return "Running";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
    case "terminated":
      return "Terminated";
    case "failed":
      return "Failed";
  }
}

function formatWorkerLaneLabel(lane: string) {
  return lane
    .split("_")
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function summarizeWorkerRuntime(workerSummary: readonly WorkerLaneSummary[]) {
  if (workerSummary.length === 0) {
    return {
      value: "Runtime summary pending",
      detail: "Backend authority has not reported any worker lanes yet.",
    } as const;
  }

  const totals = workerSummary.reduce(
    (summary, lane) => ({
      healthy: summary.healthy + lane.healthyProcessors,
      busy: summary.busy + lane.busyProcessors,
      degraded: summary.degraded + lane.degradedProcessors,
      draining: summary.draining + lane.drainingProcessors,
      offline: summary.offline + lane.offlineProcessors,
    }),
    {
      healthy: 0,
      busy: 0,
      degraded: 0,
      draining: 0,
      offline: 0,
    },
  );

  return {
    value: `${workerSummary.length} lane${workerSummary.length === 1 ? "" : "s"} reported`,
    detail: `${totals.healthy} healthy · ${totals.busy} busy · ${totals.degraded} degraded · ${totals.draining} draining · ${totals.offline} offline`,
  } as const;
}

function isRetryableError(error: Error | undefined): boolean {
  if (!error) {
    return false;
  }

  return !("retryable" in error) || (error as { retryable?: boolean | null }).retryable !== false;
}

function buildRuntimeModeNotice(input: Readonly<{
  runtimeMode: RuntimeMode;
  authTransition: RuntimeAuthTransition;
  targetLabel: string;
  detachedTaskIds: readonly string[];
}>) {
  const detachedSuffix =
    input.detachedTaskIds.length > 0
      ? ` ${input.detachedTaskIds.length} attached task reference${input.detachedTaskIds.length === 1 ? "" : "s"} reset.`
      : "";

  if (input.authTransition === "entered_local_bypass") {
    return {
      tone: "success" as const,
      message: `Switched to Local Mode. Local Space is now the active shell context.${detachedSuffix}`,
    };
  }

  if (input.authTransition === "online_auth_required") {
    return {
      tone: "info" as const,
      message: `Connected to ${input.targetLabel}. Online Mode now requires sign-in before workspace context can be restored.${detachedSuffix}`,
    };
  }

  if (input.authTransition === "online_session_dropped") {
    return {
      tone: "warning" as const,
      message: `Connected to ${input.targetLabel}, but the previous online session was dropped. Sign in again to rebuild workspace context.${detachedSuffix}`,
    };
  }

  return {
    tone: "info" as const,
    message: `Runtime mode switched. ${detachedSuffix}`.trim(),
  };
}

export function WorkspaceStatusStrip({
  open,
  onOpenChange,
  interactionBoundaryRef,
}: WorkspaceStatusStripProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { mutate } = useSWRConfig();
  const [datasetSearch, setDatasetSearch] = useState("");
  const [selectedSection, setSelectedSection] = useState<ContextSectionId>("runtime");
  const [switchingWorkspaceId, setSwitchingWorkspaceId] = useState<string | null>(null);
  const [selectingDatasetId, setSelectingDatasetId] = useState<string | null>(null);
  const [runtimeSwitchingTo, setRuntimeSwitchingTo] = useState<RuntimeMode | null>(null);
  const [runtimeTargetInput, setRuntimeTargetInput] = useState("");
  const [runtimeNotice, setRuntimeNotice] = useState<SurfaceNotice>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<SurfaceNotice>(null);
  const [datasetNotice, setDatasetNotice] = useState<SurfaceNotice>(null);
  const {
    session,
    workspace,
    sessionError,
    status: sessionStatus,
    isSessionLoading,
    isSessionRefreshing,
    refreshSession,
    switchWorkspace,
    switchRuntimeMode,
    runtimeMode,
    serverTargetDraft,
    setServerTargetDraft,
  } = useAppSession();
  const {
    activeDataset,
    source,
    status: activeDatasetStatus,
    routeDatasetId,
    sessionDatasetId,
    isDatasetDetailLoading,
    isUpdatingActiveDataset,
    isRouteSyncPending,
    canRetryRouteSync,
    activeDatasetError,
    refreshActiveDataset,
    retryRouteSync,
    setActiveDataset,
    clearActiveDataset,
    syncRouteDataset,
  } = useActiveDataset();
  const { enabled: developerModeEnabled } = useDeveloperMode();
  const {
    tasks,
    activeTasks,
    workerSummary,
    latestTask,
    summary,
    taskQueueError,
    isTaskQueueLoading,
    isTaskQueueRefreshing,
    refreshTaskQueue,
  } = useTaskQueue();
  const { activeTaskDetail, activeTaskError, resolvedTaskId, isActiveTaskLoading, refreshActiveTask } =
    useActiveTask();
  const datasetCatalogQuery = useSWR(datasetCatalogKey, listDatasetCatalog);

  useEffect(() => {
    if (!open) {
      setRuntimeNotice(null);
      setWorkspaceNotice(null);
      setDatasetNotice(null);
    }
  }, [open]);

  useEffect(() => {
    return subscribeToGlobalContextRequests((section) => {
      setSelectedSection(section);
      onOpenChange(true);
    });
  }, [onOpenChange]);

  useEffect(() => {
    setRuntimeTargetInput(serverTargetDraft);
  }, [serverTargetDraft]);

  const datasetRows = datasetCatalogQuery.data?.rows ?? [];
  const filteredDatasetRows = filterShellDatasets(
    datasetRows,
    datasetSearch,
    activeDataset?.datasetId ?? null,
  );
  const workspaceMemberships = resolveShellWorkspaceMemberships(session?.memberships);
  const queueRows = (activeTasks.length > 0 ? activeTasks : tasks).slice(0, 6);
  const canSwitchDataset = session?.capabilities.canSwitchDataset ?? false;
  const canSwitchRuntimeMode = session?.capabilities.canSwitchRuntimeMode ?? true;
  const workerRuntimeSummary = summarizeWorkerRuntime(workerSummary);
  const datasetSummary = resolveShellActiveDatasetSummary(activeDataset, {
    status: activeDatasetStatus,
    source,
    errorDetail: activeDatasetError
      ? developerModeEnabled
        ? describeShellError(activeDatasetError)
        : "The dataset attachment is unavailable right now."
      : null,
    isUpdating: isUpdatingActiveDataset,
  });
  const runtimeValue = resolveRuntimeModeLabel(runtimeMode);
  const runtimeDetail =
    runtimeMode === "local"
      ? "Local Space · No remote sign-in required"
      : `${resolveShellConnectionTargetLabel(session)} · ${session?.authState === "authenticated" ? "Authenticated" : session?.authState === "degraded" ? "Recover" : "Auth required"}`;
  const workspaceValue =
    sessionStatus === "loading" ? "Loading workspace..." : resolveSessionWorkspaceLabel(session);
  const workspaceDetail =
    runtimeMode === "local"
      ? "Fixed implicit local workspace"
      : sessionError
        ? developerModeEnabled
          ? (describeShellError(sessionError) ?? sessionError.message)
          : "Session authority is unavailable."
        : workspace?.displayName
          ? `${workspace.role ?? "Pending"} role · ${session?.memberships.length ?? 0} memberships`
          : "Workspace selection is pending online auth.";
  const queueValue =
    isTaskQueueLoading && summary.total === 0
      ? "Loading tasks..."
      : summary.runningCount > 0 || summary.pendingCount > 0
        ? `${summary.runningCount} Running · ${summary.pendingCount} Pending`
        : summary.total > 0
          ? `${summary.completedCount} Completed · ${summary.failedCount} Failed`
          : "No active tasks";
  const queueDetail = activeTaskDetail
    ? `Attached #${activeTaskDetail.taskId} · ${formatTaskStatusLabel(activeTaskDetail.progress.phase)}`
    : latestTask
      ? `Latest #${latestTask.taskId} · ${formatTaskStatusLabel(latestTask.status)}`
      : runtimeMode === "local"
        ? "No Local Space task attached"
        : "No online task attached";
  const contextWarning =
    sessionError ?? taskQueueError ?? activeTaskError ?? activeDatasetError ?? undefined;
  const triggerLabel = runtimeValue;
  const triggerDetail = `${workspaceValue} · ${datasetSummary.value} · ${queueValue}`;
  const modeTargetValue =
    (session?.connection.target?.kind === "remote"
      ? (session.connection.label ?? session.connection.origin)
      : runtimeTargetInput.trim()) || "Server target pending";
  const runtimeRefreshCopy =
    runtimeMode === "local"
      ? "Refresh only re-fetches the Local Space session envelope. It does not call online auth refresh."
      : "Refresh revalidates the current online session and target summary without switching modes.";

  async function handleWorkspaceSwitch(workspaceId: string) {
    setWorkspaceNotice(null);
    setDatasetNotice(null);
    setSwitchingWorkspaceId(workspaceId);

    try {
      const result = await switchWorkspace(workspaceId);
      syncRouteDataset(result.session.activeDataset?.datasetId ?? null);
      await Promise.all([
        mutate(datasetCatalogKey),
        refreshTaskQueue().then(() => undefined),
        refreshActiveTask(),
      ]);
      const nextNotice = resolveWorkspaceSwitchNotice(result);
      setWorkspaceNotice({
        tone: nextNotice.tone === "primary" ? "info" : nextNotice.tone,
        message: nextNotice.message,
      });
      setDatasetSearch("");
    } catch (error) {
      setWorkspaceNotice({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to switch workspace.",
      });
    } finally {
      setSwitchingWorkspaceId(null);
    }
  }

  async function handleDatasetSelection(datasetId: string | null) {
    setDatasetNotice(null);
    setSelectingDatasetId(datasetId ?? "__clear__");

    try {
      if (datasetId === null) {
        await clearActiveDataset();
        setDatasetNotice({
          tone: "success",
          message: "No active dataset is selected for the current runtime context.",
        });
      } else {
        await setActiveDataset(datasetId);
        const selectedDataset = datasetRows.find((row) => row.dataset_id === datasetId)?.name ?? datasetId;
        setDatasetNotice({
          tone: "success",
          message: `Active dataset switched to ${selectedDataset}.`,
        });
      }
      await mutate(datasetCatalogKey);
    } catch (error) {
      setDatasetNotice({
        tone: "warning",
        message: error instanceof Error ? error.message : "Unable to update the active dataset.",
      });
    } finally {
      setSelectingDatasetId(null);
    }
  }

  async function handleRuntimeModeSwitch(nextMode: RuntimeMode) {
    setRuntimeNotice(null);
    setWorkspaceNotice(null);
    setDatasetNotice(null);
    setRuntimeSwitchingTo(nextMode);

    try {
      const outcome = await switchRuntimeMode({
        mode: nextMode,
        serverOrigin: nextMode === "online" ? runtimeTargetInput.trim() : null,
      });
      const nextSearch = buildContextResetSearch(pathname, new URLSearchParams(searchParams.toString()));
      router.replace(nextSearch, { scroll: false });
      syncRouteDataset(outcome.session?.activeDataset?.datasetId ?? null);
      await Promise.all([
        mutate(datasetCatalogKey),
        refreshTaskQueue().then(() => undefined),
        refreshActiveTask(),
        refreshActiveDataset(),
      ]);
      setRuntimeNotice(
        buildRuntimeModeNotice({
          runtimeMode: outcome.result.runtimeMode,
          authTransition: outcome.result.authTransition,
          targetLabel:
            outcome.result.connection.label ??
            outcome.result.connection.origin ??
            (nextMode === "local" ? "local" : runtimeTargetInput.trim() || "the server target"),
          detachedTaskIds: outcome.result.detachedTaskIds,
        }),
      );
      setSelectedSection("runtime");
    } catch (error) {
      setRuntimeNotice({
        tone: "error",
        message:
          describeShellError(error instanceof Error ? error : undefined) ??
          "Unable to switch runtime mode.",
      });
    } finally {
      setRuntimeSwitchingTo(null);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          onOpenChange(!open);
        }}
        className={cx(
          "inline-flex min-h-11 cursor-pointer items-center gap-3 rounded-full border px-3 py-1.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-header",
          open
            ? "border-primary/35 bg-primary/10"
            : "border-border bg-background hover:border-primary/25 hover:bg-surface",
          "max-w-[292px]",
        )}
        aria-expanded={open}
        aria-label="Open global context panel"
      >
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          {contextWarning ? <AlertTriangle className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
        </span>
        <span className="hidden min-w-0 xl:block">
          <span className="block truncate text-sm font-medium text-foreground">{triggerLabel}</span>
          <span className="block truncate text-[11px] text-muted-foreground">{triggerDetail}</span>
        </span>
      </button>

      <ShellSidePanel
        open={open}
        onClose={() => {
          onOpenChange(false);
        }}
        title="Global Context"
        subtitle="Runtime mode, workspace, dataset, queue, and worker state live here as one selected-section shell surface."
        variant="context"
        interactionBoundaryRef={interactionBoundaryRef}
      >
        <div className="space-y-4">
          {contextWarning ? (
            <ShellNotice tone="warning" title="Context warning">
              {developerModeEnabled
                ? (describeShellError(contextWarning) ??
                  "The shell could not fully resolve the current global context.")
                : "Some shared context data is unavailable. Open Account > Developer Mode for technical detail."}
            </ShellNotice>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <ContextSectionCard
              id="runtime"
              selected={selectedSection === "runtime"}
              onSelect={setSelectedSection}
              icon={Globe}
              label="Runtime Mode"
              value={runtimeValue}
              detail={runtimeDetail}
            />
            <ContextSectionCard
              id="workspace"
              selected={selectedSection === "workspace"}
              onSelect={setSelectedSection}
              icon={FolderKanban}
              label="Active Workspace"
              value={workspaceValue}
              detail={workspaceDetail}
            />
            <ContextSectionCard
              id="dataset"
              selected={selectedSection === "dataset"}
              onSelect={setSelectedSection}
              icon={Database}
              label="Active Dataset"
              value={datasetSummary.value}
              detail={datasetSummary.detail ?? datasetSummary.badge ?? "No attached dataset"}
            />
            <ContextSectionCard
              id="tasks"
              selected={selectedSection === "tasks"}
              onSelect={setSelectedSection}
              icon={Workflow}
              label="Tasks & Runtime"
              value={queueValue}
              detail={`${queueDetail} · ${workerRuntimeSummary.value}`}
            />
          </div>

          {selectedSection === "runtime" ? (
            <SectionFrame
              icon={Globe}
              title="Runtime Mode"
              description="Runtime mode is the outer shell boundary. Choose the backend-owned context you want to operate in, then manage the server target beneath it."
            >
              {runtimeNotice ? (
                <ShellNotice className="mb-4" tone={runtimeNotice.tone}>
                  {runtimeNotice.message}
                </ShellNotice>
              ) : null}

              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <RuntimeModeCard
                    label="Mode"
                    title="Local Mode"
                    details={[
                      "Workspace: Local Space · no remote sign-in required.",
                      "Datasets, schemas, results, and tasks stay local until you explicitly import or export them.",
                      "Queue and dataset context rebuild for Local Space on every mode switch.",
                    ]}
                    active={runtimeMode === "local"}
                    disabled={!canSwitchRuntimeMode || runtimeSwitchingTo !== null}
                    onClick={() => {
                      void handleRuntimeModeSwitch("local");
                    }}
                  />
                  <RuntimeModeCard
                    label={runtimeSwitchingTo === "online" ? "Connecting..." : "Mode"}
                    title="Online Mode"
                    details={[
                      `Target: ${modeTargetValue}.`,
                      "Validates the server target before rebuilding the online shell context.",
                      "Requires sign-in when auth is missing and never silently carries a previous remote session across mode switches.",
                      "Context reset is mode-only. Switching online never bridges local datasets, schemas, results, or tasks.",
                    ]}
                    active={runtimeMode === "online"}
                    disabled={!canSwitchRuntimeMode || runtimeSwitchingTo !== null}
                    onClick={() => {
                      void handleRuntimeModeSwitch("online");
                    }}
                  />
                </div>

                <div className="rounded-[1rem] border border-border bg-background px-4 py-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Server Target (IP:Port or origin)
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <input
                      value={runtimeTargetInput}
                      onChange={(event) => {
                        setRuntimeTargetInput(event.target.value);
                        setServerTargetDraft(event.target.value);
                      }}
                      className="min-w-[240px] flex-1 rounded-[0.85rem] border border-border/80 bg-surface px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="http://127.0.0.1:8000"
                    />
                    {runtimeMode === "online" ? (
                      <Link
                        href="/login"
                        className="inline-flex min-h-10 items-center rounded-full border border-border bg-surface px-4 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                      >
                        Open Auth Entry
                      </Link>
                    ) : null}
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border border-border bg-background px-4 py-3">
                  <p className="text-sm text-muted-foreground">{runtimeRefreshCopy}</p>
                  <ActionButton
                    label="Refresh session"
                    spinning={isSessionRefreshing}
                    disabled={isSessionLoading}
                    onClick={() => {
                      void refreshSession();
                    }}
                  />
                </div>
              </div>
            </SectionFrame>
          ) : null}

          {selectedSection === "workspace" ? (
            <SectionFrame
              icon={FolderKanban}
              title="Active Workspace"
              description={
                runtimeMode === "local"
                  ? "Local Mode keeps one implicit workspace. Collaboration and membership switching stay online-only."
                  : "Session-backed workspace switching."
              }
              actions={
                <ActionButton
                  label="Refresh session"
                  spinning={isSessionRefreshing}
                  disabled={isSessionLoading}
                  onClick={() => {
                    void refreshSession();
                  }}
                />
              }
            >
              {workspaceNotice ? (
                <ShellNotice className="mb-4" tone={workspaceNotice.tone}>
                  {workspaceNotice.message}
                </ShellNotice>
              ) : null}

              {runtimeMode === "local" ? (
                <div className="grid gap-3 md:grid-cols-3">
                  <CompactContextCard
                    icon={FolderKanban}
                    label="Workspace"
                    value="Local Space"
                    detail="Local Mode always binds the shell to one implicit workspace."
                  />
                  <CompactContextCard
                    icon={Workflow}
                    label="Task Scope"
                    value={workspace?.defaultTaskScope ?? "local"}
                    detail="Queue, dataset, and attached-task context rebuild from Local Space."
                  />
                  <CompactContextCard
                    icon={ServerCog}
                    label="Collaboration"
                    value="Online-only"
                    detail="Invitations, membership management, and governance do not apply in local mode."
                  />
                </div>
              ) : (
                <div className="grid gap-3 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
                  <div className="space-y-3">
                    {workspaceMemberships.length > 0 ? (
                      workspaceMemberships.map((membership) => {
                        const isSwitching = switchingWorkspaceId === membership.workspaceId;

                        return (
                          <button
                            key={membership.workspaceId}
                            type="button"
                            disabled={
                              membership.isActive ||
                              !membership.allowedActions.switchTo ||
                              isSwitching ||
                              isSessionLoading
                            }
                            onClick={() => {
                              if (!membership.isActive) {
                                void handleWorkspaceSwitch(membership.workspaceId);
                              }
                            }}
                            className={cx(
                              "w-full rounded-[0.95rem] border px-4 py-4 text-left transition",
                              membership.isActive
                                ? "border-primary/35 bg-primary/10"
                                : "border-border bg-background hover:border-primary/25 hover:bg-surface-elevated",
                              (!membership.allowedActions.switchTo || isSwitching || isSessionLoading) &&
                                "cursor-not-allowed opacity-70",
                            )}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-foreground">
                                  {membership.displayName ?? membership.workspaceId}
                                </p>
                                <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                  {membership.role ?? "pending"} role · {membership.defaultTaskScope ?? "workspace"} tasks
                                </p>
                              </div>
                              <span className="inline-flex items-center gap-2">
                                {isSwitching ? (
                                  <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                                ) : null}
                                <span className="rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                                  {membership.isActive ? "active" : "switch"}
                                </span>
                              </span>
                            </div>
                          </button>
                        );
                      })
                    ) : (
                      <div className="rounded-[0.9rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                        No switchable workspace memberships are available in this session.
                      </div>
                    )}
                  </div>

                  <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-1">
                    <CompactContextCard
                      icon={FolderKanban}
                      label="Workspace"
                      value={workspace?.displayName ?? "Unavailable"}
                      detail={`${workspace?.role ?? "Pending"} role`}
                    />
                    <CompactContextCard
                      icon={Workflow}
                      label="Task Scope"
                      value={workspace?.defaultTaskScope ?? "Pending"}
                      detail="Switching workspaces rebinds datasets, queue visibility, and capabilities."
                    />
                    <CompactContextCard
                      icon={ServerCog}
                      label="Allowed Actions"
                      value={workspace?.allowedActions.switchTo ? "Switchable" : "Pinned"}
                      detail="Workspace switching is always decided by backend allowed_actions."
                    />
                  </div>
                </div>
              )}
            </SectionFrame>
          ) : null}

          {selectedSection === "dataset" ? (
            <SectionFrame
              icon={Database}
              title="Active Dataset"
              description={
                runtimeMode === "local"
                  ? "Single-select dataset context for Local Space."
                  : "Single-select dataset context from active online workspace authority."
              }
              actions={
                <div className="flex flex-wrap gap-2">
                  <ActionButton
                    label="Refresh dataset"
                    spinning={
                      isUpdatingActiveDataset || isRouteSyncPending || datasetCatalogQuery.isLoading
                    }
                    disabled={isUpdatingActiveDataset}
                    onClick={() => {
                      void Promise.all([refreshActiveDataset(), mutate(datasetCatalogKey)]);
                    }}
                  />
                  {canRetryRouteSync && isRetryableError(activeDatasetError) ? (
                    <ActionButton
                      label="Retry attach"
                      onClick={() => {
                        void retryRouteSync();
                      }}
                    />
                  ) : null}
                  <Link
                    href="/dataset"
                    className="inline-flex min-h-10 items-center rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    Open Dataset
                  </Link>
                  <Link
                    href="/raw-data"
                    className="inline-flex min-h-10 items-center rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                  >
                    Open Raw Data
                  </Link>
                </div>
              }
            >
              {datasetNotice ? (
                <ShellNotice className="mb-4" tone={datasetNotice.tone}>
                  {datasetNotice.message}
                </ShellNotice>
              ) : null}

              {!canSwitchDataset ? (
                <ShellNotice className="mb-4" tone="warning" title="Dataset switching unavailable">
                  The current session authority does not allow switching the active dataset from the shell.
                </ShellNotice>
              ) : null}

              {datasetCatalogQuery.error ? (
                <ShellNotice className="mb-4" tone="error" title="Dataset visibility error">
                  {developerModeEnabled
                    ? `Unable to load visible datasets. ${(datasetCatalogQuery.error as Error).message}`
                    : runtimeMode === "local"
                      ? "Unable to load Local Space datasets right now."
                      : "Unable to load visible datasets for the current workspace."}
                </ShellNotice>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
                <div className="space-y-3">
                  <label className="block rounded-[0.95rem] border border-border bg-background px-4 py-3">
                    <span className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Search Datasets
                    </span>
                    <input
                      value={datasetSearch}
                      onChange={(event) => {
                        setDatasetSearch(event.target.value);
                      }}
                      className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="Search by name, id, family, owner, or device"
                    />
                  </label>

                  {datasetCatalogQuery.isLoading || isDatasetDetailLoading ? (
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      Loading {runtimeMode === "local" ? "Local Space" : "workspace-visible"} datasets...
                    </div>
                  ) : filteredDatasetRows.length > 0 ? (
                    [
                      {
                        dataset_id: "__none__",
                        name: "No active dataset",
                        family: "Session context",
                        device_type: "Dataset detached",
                        owner_display_name: runtimeMode === "local" ? "Local Space" : "Current workspace",
                        lifecycle_state: "active",
                        allowed_actions: { select: canSwitchDataset, update_profile: false, publish: false, archive: false },
                      },
                      ...filteredDatasetRows,
                    ].map((row) => {
                      const isNullOption = row.dataset_id === "__none__";
                      const isSelected = row.dataset_id === activeDataset?.datasetId;
                      const isNullSelected = !activeDataset && isNullOption;
                      const isBusy = selectingDatasetId === (isNullOption ? "__clear__" : row.dataset_id);
                      const isUnavailable = isBusy || !row.allowed_actions.select || !canSwitchDataset;

                      return (
                        <button
                          key={row.dataset_id}
                          type="button"
                          disabled={isUnavailable}
                          aria-pressed={isSelected || isNullSelected}
                          onClick={() => {
                            if (isSelected || isNullSelected) {
                              return;
                            }
                            void handleDatasetSelection(isNullOption ? null : row.dataset_id);
                          }}
                          className={cx(
                            "w-full cursor-pointer rounded-[0.95rem] border px-4 py-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                            isSelected || isNullSelected
                              ? "border-primary/35 bg-primary/10 shadow-[0_14px_28px_rgba(37,99,235,0.14)]"
                              : "border-border bg-background hover:-translate-y-0.5 hover:border-primary/25 hover:bg-surface-elevated hover:shadow-[0_16px_32px_rgba(15,23,42,0.08)]",
                            isUnavailable &&
                              "cursor-not-allowed opacity-70",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-foreground">
                                {row.name}
                              </p>
                              <p className="mt-2 text-sm text-muted-foreground">
                                {isNullOption
                                  ? "Keep the shell attached to the current runtime without selecting a dataset."
                                  : `${row.family} · ${row.device_type} · ${row.owner_display_name}`}
                              </p>
                            </div>
                            <span className="inline-flex items-center gap-2">
                              {isBusy ? (
                                <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                              ) : null}
                              <span className="rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                                {isSelected || isNullSelected ? "active" : isNullOption ? "detach" : row.lifecycle_state}
                              </span>
                            </span>
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="rounded-[0.9rem] border border-dashed border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      {datasetSearch.trim().length > 0
                        ? `No datasets match “${datasetSearch.trim()}”.`
                        : runtimeMode === "local"
                          ? "No Local Space datasets are available."
                          : "No workspace-visible datasets are available."}
                    </div>
                  )}
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1">
                  <CompactContextCard
                    icon={Database}
                    label="Dataset"
                    value={activeDataset?.name ?? "None selected"}
                    detail={activeDataset?.status ?? "Pending"}
                  />
                  <CompactContextCard
                    icon={Database}
                    label="Source"
                    value={source === "none" ? "No selection" : source}
                    detail={
                      source === "url" && routeDatasetId !== sessionDatasetId
                        ? "Route selection is waiting on session attach."
                        : "The active runtime session remains the canonical dataset authority."
                    }
                  />
                  <CompactContextCard
                    icon={Database}
                    label="Visibility"
                    value={activeDataset?.visibilityScope ?? "Pending"}
                    detail={
                      runtimeMode === "local"
                        ? "Local persisted resources use the local visibility scope."
                        : "Online datasets stay scoped to the active workspace visibility model."
                    }
                  />
                </div>
              </div>
            </SectionFrame>
          ) : null}

          {selectedSection === "tasks" ? (
            <SectionFrame
              icon={Workflow}
              title="Tasks & Runtime"
              description={
                runtimeMode === "local"
                  ? "Local tasks and runtime status are isolated to Local Space and rebuilt on every mode switch."
                  : "Online task rows and runtime status come from active workspace authority and never merge with local task context."
              }
              actions={
                <ActionButton
                  label="Refresh queue"
                  spinning={isTaskQueueRefreshing || isActiveTaskLoading}
                  disabled={isTaskQueueLoading}
                  onClick={() => {
                    void refreshTaskQueue();
                    void refreshActiveTask();
                  }}
                />
              }
            >
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <CompactContextCard
                    icon={Workflow}
                    label="Attached Task"
                    value={activeTaskDetail ? `#${activeTaskDetail.taskId}` : "No attached task"}
                    detail={
                      activeTaskDetail
                        ? `${formatTaskStatusLabel(activeTaskDetail.progress.phase)} · ${Math.round(activeTaskDetail.progress.percentComplete)}%`
                        : resolvedTaskId
                          ? `Waiting for task #${resolvedTaskId} detail`
                          : runtimeMode === "local"
                            ? "Open a workflow surface to attach a Local Space task."
                            : "Open a workflow surface or queue row to attach a persisted online task."
                    }
                  />
                  <CompactContextCard
                    icon={Workflow}
                    label="Queue Summary"
                    value={queueValue}
                    detail={
                      taskQueueError
                        ? developerModeEnabled
                          ? (describeShellError(taskQueueError) ?? taskQueueError.message)
                          : "Task queue detail is unavailable right now."
                        : queueDetail
                    }
                  />
                  <CompactContextCard
                    icon={ServerCog}
                    label="Worker Runtime"
                    value={workerRuntimeSummary.value}
                    detail={
                      taskQueueError
                        ? developerModeEnabled
                          ? (describeShellError(taskQueueError) ?? taskQueueError.message)
                          : "Runtime summary is unavailable right now."
                        : workerRuntimeSummary.detail
                    }
                  />
                </div>

                <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                  <CompactContextCard
                    icon={Workflow}
                    label="Pending"
                    value={String(summary.pendingCount)}
                    detail="Queued or dispatching tasks."
                  />
                  <CompactContextCard
                    icon={Workflow}
                    label="Running"
                    value={String(summary.runningCount)}
                    detail="Running or draining tasks."
                  />
                  <CompactContextCard
                    icon={Workflow}
                    label="Completed"
                    value={String(summary.completedCount)}
                    detail="Tasks finished successfully."
                  />
                  <CompactContextCard
                    icon={AlertTriangle}
                    label="Failed"
                    value={String(summary.failedCount)}
                    detail="Tasks that need review or retry."
                  />
                  <CompactContextCard
                    icon={AlertTriangle}
                    label="Cancelled"
                    value={String(summary.cancelledCount)}
                    detail="Tasks stopped through graceful cancellation."
                  />
                  <CompactContextCard
                    icon={AlertTriangle}
                    label="Terminated"
                    value={String(summary.terminatedCount)}
                    detail="Tasks force-stopped by runtime control."
                  />
                </div>

                <div className="space-y-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Worker lanes
                  </p>
                  {workerSummary.length > 0 ? (
                    <div className="grid gap-3 md:grid-cols-2">
                      {workerSummary.map((laneSummary) => (
                        <div
                          key={laneSummary.lane}
                          className="rounded-[0.9rem] border border-border bg-background px-4 py-4 shadow-[0_8px_22px_rgba(15,23,42,0.06)]"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-foreground">
                                {formatWorkerLaneLabel(laneSummary.lane)}
                              </p>
                              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                Lane runtime summary
                              </p>
                            </div>
                            <span className="rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                              {laneSummary.healthyProcessors > 0 ? "Healthy" : "Needs attention"}
                            </span>
                          </div>
                          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                            <div>
                              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                Healthy
                              </p>
                              <p className="mt-1 font-semibold text-foreground">
                                {laneSummary.healthyProcessors}
                              </p>
                            </div>
                            <div>
                              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                Busy
                              </p>
                              <p className="mt-1 font-semibold text-foreground">
                                {laneSummary.busyProcessors}
                              </p>
                            </div>
                            <div>
                              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                Degraded
                              </p>
                              <p className="mt-1 font-semibold text-foreground">
                                {laneSummary.degradedProcessors}
                              </p>
                            </div>
                            <div>
                              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                Draining
                              </p>
                              <p className="mt-1 font-semibold text-foreground">
                                {laneSummary.drainingProcessors}
                              </p>
                            </div>
                            <div>
                              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                Offline
                              </p>
                              <p className="mt-1 font-semibold text-foreground">
                                {laneSummary.offlineProcessors}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      Backend authority has not reported any lane runtime rows yet.
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  {queueRows.length > 0 ? (
                    queueRows.map((task) => (
                      <Link
                        key={task.taskId}
                        href={resolveShellTaskHref(task)}
                        className="block rounded-[0.9rem] border border-border bg-background px-4 py-3 transition hover:border-primary/25 hover:bg-surface-elevated"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-foreground">
                              #{task.taskId} · {resolveShellTaskLabel(task)}
                            </p>
                            <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-muted-foreground">
                              {formatTaskStatusLabel(task.status)} · {task.summary}
                            </p>
                          </div>
                          <span className="rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                            {task.visibilityScope}
                          </span>
                        </div>
                      </Link>
                    ))
                  ) : (
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      {runtimeMode === "local"
                        ? "No Local Space tasks are available yet."
                        : "No workspace-visible tasks are available yet."}
                    </div>
                  )}
                </div>
              </div>
            </SectionFrame>
          ) : null}
        </div>
      </ShellSidePanel>
    </>
  );
}
