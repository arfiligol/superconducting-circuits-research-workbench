"use client";

import {
  useEffect,
  useMemo,
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
  resolveShellWorkerSummary,
  resolveShellWorkspaceMemberships,
  resolveWorkspaceSwitchNotice,
} from "@/components/layout/workspace-shell-contract";
import { ShellNotice } from "@/components/layout/shell-notice";
import { cx } from "@/features/shared/components/surface-kit";
import { datasetCatalogKey, listDatasetCatalog } from "@/lib/api/datasets";
import { useActiveDataset, useActiveTask, useAppSession, useDeveloperMode, useTaskQueue } from "@/lib/app-state";
import type { RuntimeAuthTransition, RuntimeMode } from "@/lib/api/session";

type WorkspaceStatusStripProps = Readonly<{
  open: boolean;
  onOpenChange: (nextOpen: boolean) => void;
  interactionBoundaryRef?: RefObject<HTMLElement | null>;
}>;

type ContextSectionId = "runtime" | "workspace" | "dataset" | "queue" | "worker";

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

function ModeButton({
  label,
  active = false,
  disabled = false,
  onClick,
}: Readonly<{
  label: string;
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
        "inline-flex min-h-10 cursor-pointer items-center justify-center rounded-full border px-4 py-2 text-xs font-medium uppercase tracking-[0.16em] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-60",
        active
          ? "border-primary/40 bg-primary/12 text-foreground"
          : "border-border bg-background text-foreground hover:border-primary/35 hover:bg-primary/10",
      )}
    >
      {label}
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
  const workerSummary = resolveShellWorkerSummary(workspace, runtimeMode);
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
      ? "Loading queue..."
      : activeTasks.length > 0
        ? `${activeTasks.length} active`
        : summary.total > 0
          ? `${summary.completedCount} done · ${summary.failedCount} failed`
          : "Idle";
  const queueDetail = activeTaskDetail
    ? `Attached #${activeTaskDetail.taskId} · ${activeTaskDetail.progress.phase}`
    : latestTask
      ? `Latest #${latestTask.taskId} · ${latestTask.status}`
      : runtimeMode === "local"
        ? "No Local Space task attached"
        : "No attached online task";
  const contextWarning =
    sessionError ?? taskQueueError ?? activeTaskError ?? activeDatasetError ?? undefined;
  const triggerLabel = runtimeValue;
  const triggerDetail = `${workspaceValue} · ${datasetSummary.value} · ${queueValue}`;
  const modeTargetValue =
    runtimeMode === "local"
      ? "Local backend"
      : ((session?.connection.label ?? session?.connection.origin ?? runtimeTargetInput.trim()) ||
          "Server target pending");
  const runtimeStatusCopy =
    runtimeMode === "local"
      ? "Mode switch rebuilds queue, dataset, and task context for Local Space."
      : "Switching to online validates the target, clears stale shell context, and requires a fresh auth step.";

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
          message: "Active dataset cleared for the current runtime context.",
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

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
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
              id="queue"
              selected={selectedSection === "queue"}
              onSelect={setSelectedSection}
              icon={Workflow}
              label="Tasks Queue"
              value={queueValue}
              detail={queueDetail}
            />
            <ContextSectionCard
              id="worker"
              selected={selectedSection === "worker"}
              onSelect={setSelectedSection}
              icon={ServerCog}
              label={workerSummary.label}
              value={workerSummary.value}
              detail={workerSummary.detail}
            />
          </div>

          {selectedSection === "runtime" ? (
            <SectionFrame
              icon={Globe}
              title="Runtime Mode"
              description="Runtime mode is the outer shell boundary. Switching modes rebuilds context and never bridges local and online resources automatically."
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
              {runtimeNotice ? (
                <ShellNotice className="mb-4" tone={runtimeNotice.tone}>
                  {runtimeNotice.message}
                </ShellNotice>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    <ModeButton
                      label="Local Mode"
                      active={runtimeMode === "local"}
                      disabled={!canSwitchRuntimeMode || runtimeSwitchingTo !== null}
                      onClick={() => {
                        void handleRuntimeModeSwitch("local");
                      }}
                    />
                    <ModeButton
                      label={runtimeSwitchingTo === "online" ? "Connecting..." : "Online Mode"}
                      active={runtimeMode === "online"}
                      disabled={!canSwitchRuntimeMode || runtimeSwitchingTo !== null}
                      onClick={() => {
                        void handleRuntimeModeSwitch("online");
                      }}
                    />
                    {runtimeMode === "online" ? (
                      <Link
                        href="/login"
                        className="inline-flex min-h-10 items-center rounded-full border border-border bg-background px-4 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                      >
                        Open Auth Entry
                      </Link>
                    ) : null}
                  </div>

                  <label className="block rounded-[0.95rem] border border-border bg-background px-4 py-3">
                    <span className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Server Target (IP:Port or origin)
                    </span>
                    <input
                      value={runtimeTargetInput}
                      onChange={(event) => {
                        setRuntimeTargetInput(event.target.value);
                        setServerTargetDraft(event.target.value);
                      }}
                      className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="http://127.0.0.1:8000"
                    />
                  </label>

                  <p className="text-sm leading-6 text-muted-foreground">
                    {runtimeStatusCopy}
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-1">
                  <CompactContextCard
                    icon={Globe}
                    label="Active Mode"
                    value={runtimeValue}
                    detail={
                      runtimeMode === "local"
                        ? "Local Mode stays in Local Space and bypasses online auth."
                        : "Online Mode validates the target, then re-enters auth if needed."
                    }
                  />
                  <CompactContextCard
                    icon={FolderKanban}
                    label="Context Target"
                    value={modeTargetValue}
                    detail={
                      runtimeMode === "local"
                        ? "Local backend pairing is fixed in this mode."
                        : "Switching back from local never silently restores a previous remote login."
                    }
                  />
                  <CompactContextCard
                    icon={Workflow}
                    label="Context Reset"
                    value="No data bridge"
                    detail="Datasets, schemas, results, and tasks stay mode-scoped until explicit import or export."
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

                  {activeDataset ? (
                    <button
                      type="button"
                      onClick={() => {
                        void handleDatasetSelection(null);
                      }}
                      disabled={selectingDatasetId !== null || !canSwitchDataset}
                      className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/35 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Clear active dataset
                    </button>
                  ) : null}

                  {datasetCatalogQuery.isLoading || isDatasetDetailLoading ? (
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      Loading {runtimeMode === "local" ? "Local Space" : "workspace-visible"} datasets...
                    </div>
                  ) : filteredDatasetRows.length > 0 ? (
                    filteredDatasetRows.map((row) => {
                      const isSelected = row.dataset_id === activeDataset?.datasetId;
                      const isBusy = selectingDatasetId === row.dataset_id;

                      return (
                        <button
                          key={row.dataset_id}
                          type="button"
                          disabled={
                            isSelected || isBusy || !row.allowed_actions.select || !canSwitchDataset
                          }
                          onClick={() => {
                            void handleDatasetSelection(row.dataset_id);
                          }}
                          className={cx(
                            "w-full rounded-[0.95rem] border px-4 py-4 text-left transition",
                            isSelected
                              ? "border-primary/35 bg-primary/10"
                              : "border-border bg-background hover:border-primary/25 hover:bg-surface-elevated",
                            (!row.allowed_actions.select || isBusy || !canSwitchDataset) &&
                              "cursor-not-allowed opacity-70",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-foreground">
                                {row.name}
                              </p>
                              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                {row.dataset_id}
                              </p>
                              <p className="mt-2 text-sm text-muted-foreground">
                                {row.family} · {row.device_type} · {row.owner_display_name}
                              </p>
                            </div>
                            <span className="inline-flex items-center gap-2">
                              {isBusy ? (
                                <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                              ) : null}
                              <span className="rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                                {isSelected ? "active" : row.lifecycle_state}
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

          {selectedSection === "queue" ? (
            <SectionFrame
              icon={Workflow}
              title="Tasks Queue"
              description={
                runtimeMode === "local"
                  ? "Local Mode queue rows are isolated to Local Space and rebuilt on every mode switch."
                  : "Online queue rows come from the active workspace authority and never merge with local task rows."
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
              <div className="grid gap-4 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
                <div className="space-y-3">
                  <CompactContextCard
                    icon={Workflow}
                    label="Attached Task"
                    value={activeTaskDetail ? `#${activeTaskDetail.taskId}` : "No attached task"}
                    detail={
                      activeTaskDetail
                        ? `${activeTaskDetail.progress.phase} · ${Math.round(activeTaskDetail.progress.percentComplete)}%`
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
                              {task.status} · {task.summary}
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

          {selectedSection === "worker" ? (
            <SectionFrame
              icon={ServerCog}
              title="Worker Summary"
              description={
                runtimeMode === "local"
                  ? "Local processors are summarized from the active local runtime."
                  : "Server-side worker summary stays tied to the active online workspace."
              }
            >
              <div className="grid gap-3 md:grid-cols-2">
                <CompactContextCard
                  icon={ServerCog}
                  label={workerSummary.label}
                  value={workerSummary.value}
                  detail={workerSummary.detail}
                />
                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm leading-6 text-muted-foreground">
                  {runtimeMode === "local"
                    ? "Local Mode keeps worker/runtime summary in the same shell surface without online governance or collaboration controls."
                    : workerSummary.tone === "success"
                      ? "Worker runtime authority is available for the active workspace."
                      : "The backend has not materialized a worker summary payload for this workspace yet."}
                </div>
              </div>
            </SectionFrame>
          ) : null}
        </div>
      </ShellSidePanel>
    </>
  );
}
