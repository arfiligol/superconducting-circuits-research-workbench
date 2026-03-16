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
import useSWR, { useSWRConfig } from "swr";
import {
  AlertTriangle,
  Database,
  FolderKanban,
  LoaderCircle,
  RefreshCw,
  ServerCog,
  Workflow,
} from "lucide-react";

import { ShellSidePanel } from "@/components/layout/shell-side-panel";
import {
  describeShellError,
  filterShellDatasets,
  resolveShellActiveDatasetSummary,
  resolveShellTaskHref,
  resolveShellTaskLabel,
  resolveShellWorkerSummary,
  resolveShellWorkspaceMemberships,
  resolveWorkspaceSwitchNotice,
} from "@/components/layout/workspace-shell-contract";
import { ShellNotice } from "@/components/layout/shell-notice";
import { cx } from "@/features/shared/components/surface-kit";
import { datasetCatalogKey, listDatasetCatalog } from "@/lib/api/datasets";
import {
  useActiveDataset,
  useActiveTask,
  useDeveloperMode,
  useAppSession,
  useTaskQueue,
} from "@/lib/app-state";

type WorkspaceStatusStripProps = Readonly<{
  open: boolean;
  onOpenChange: (nextOpen: boolean) => void;
  interactionBoundaryRef?: RefObject<HTMLElement | null>;
}>;

type ContextSectionId = "workspace" | "dataset" | "queue" | "worker";

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

function isRetryableError(error: Error | undefined): boolean {
  if (!error) {
    return false;
  }

  return !("retryable" in error) || (error as { retryable?: boolean | null }).retryable !== false;
}

export function WorkspaceStatusStrip({
  open,
  onOpenChange,
  interactionBoundaryRef,
}: WorkspaceStatusStripProps) {
  const { mutate } = useSWRConfig();
  const [datasetSearch, setDatasetSearch] = useState("");
  const [selectedSection, setSelectedSection] = useState<ContextSectionId>("workspace");
  const [switchingWorkspaceId, setSwitchingWorkspaceId] = useState<string | null>(null);
  const [selectingDatasetId, setSelectingDatasetId] = useState<string | null>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<{
    tone: "success" | "primary" | "warning";
    message: string;
  } | null>(null);
  const [datasetNotice, setDatasetNotice] = useState<{
    tone: "success" | "warning";
    message: string;
  } | null>(null);
  const {
    session,
    workspace,
    sessionError,
    status: sessionStatus,
    isSessionLoading,
    isSessionRefreshing,
    refreshSession,
    switchWorkspace,
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
  const {
    activeTaskDetail,
    activeTaskError,
    resolvedTaskId,
    isActiveTaskLoading,
    refreshActiveTask,
  } = useActiveTask();
  const datasetCatalogQuery = useSWR(datasetCatalogKey, listDatasetCatalog);

  useEffect(() => {
    if (!open) {
      setWorkspaceNotice(null);
      setDatasetNotice(null);
    }
  }, [open]);

  const canSwitchDataset = session?.capabilities.canSwitchDataset ?? false;
  const workerSummary = resolveShellWorkerSummary(workspace);
  const datasetRows = datasetCatalogQuery.data?.rows ?? [];
  const filteredDatasetRows = filterShellDatasets(
    datasetRows,
    datasetSearch,
    activeDataset?.datasetId ?? null,
  );
  const workspaceMemberships = resolveShellWorkspaceMemberships(session?.memberships);
  const queueRows = (activeTasks.length > 0 ? activeTasks : tasks).slice(0, 6);
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
  const workspaceValue =
    sessionStatus === "loading"
      ? "Loading workspace..."
      : workspace?.displayName ?? "Workspace unavailable";
  const workspaceDetail = sessionError
    ? developerModeEnabled
      ? (describeShellError(sessionError) ?? sessionError.message)
      : "Session authority is unavailable."
    : workspace
      ? `${workspace.role} role · ${session?.memberships.length ?? 0} memberships`
      : "Session authority pending";
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
      : "No attached task";
  const triggerLabel = useMemo(() => {
    if (sessionStatus === "loading") {
      return "Context";
    }

    if (sessionError || taskQueueError || activeTaskError || activeDatasetError) {
      return "Context";
    }

    return "Context";
  }, [sessionStatus, sessionError, taskQueueError, activeTaskError, activeDatasetError]);
  const contextWarning =
    sessionError ?? taskQueueError ?? activeTaskError ?? activeDatasetError ?? undefined;

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
      setWorkspaceNotice(resolveWorkspaceSwitchNotice(result));
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
          message: "Active dataset cleared for the current workspace.",
        });
      } else {
        await setActiveDataset(datasetId);
        const selectedDataset =
          datasetRows.find((row) => row.dataset_id === datasetId)?.name ?? datasetId;
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

  const selectedSectionTitle =
    selectedSection === "workspace"
      ? "Active Workspace"
      : selectedSection === "dataset"
        ? "Active Dataset"
        : selectedSection === "queue"
          ? "Tasks Queue"
          : "Worker Summary";

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
          "max-w-[248px]",
        )}
        aria-expanded={open}
        aria-label="Open global context panel"
      >
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          {sessionError || taskQueueError || activeDatasetError || activeTaskError ? (
            <AlertTriangle className="h-4 w-4" />
          ) : (
            <Workflow className="h-4 w-4" />
          )}
        </span>
        <span className="hidden min-w-0 xl:block">
          <span className="block truncate text-sm font-medium text-foreground">{triggerLabel}</span>
          <span className="block truncate text-[11px] text-muted-foreground">
            {workspace?.displayName ?? "Workspace pending"} · {datasetSummary.value} · {queueValue}
          </span>
        </span>
      </button>

      <ShellSidePanel
        open={open}
        onClose={() => {
          onOpenChange(false);
        }}
        title="Global Context"
        subtitle="Global context for header-owned workspace, dataset, queue, and worker state."
        variant="context"
        interactionBoundaryRef={interactionBoundaryRef}
      >
        <div className="space-y-4">
          {contextWarning && (
            <ShellNotice tone="warning" title="Context warning">
              {developerModeEnabled
                ? (describeShellError(contextWarning) ??
                  "The shell could not fully resolve the current global context.")
                : "Some shared context data is unavailable. Open Account > Developer Mode for technical detail."}
            </ShellNotice>
          )}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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

          <div className="rounded-[1rem] border border-border/80 bg-surface px-4 py-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Focused Section
              </p>
              <p className="mt-1 text-sm font-medium text-foreground">{selectedSectionTitle}</p>
            </div>
          </div>

          {selectedSection === "workspace" ? (
            <SectionFrame
              icon={FolderKanban}
              title="Active Workspace"
              description="Session-backed workspace switching."
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
                <ShellNotice
                  className="mb-4"
                  tone={
                    workspaceNotice.tone === "success"
                      ? "success"
                      : workspaceNotice.tone === "primary"
                        ? "info"
                        : "warning"
                  }
                >
                  {workspaceNotice.message}
                </ShellNotice>
              ) : null}

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
                                {membership.displayName}
                              </p>
                              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                {membership.role} role · {membership.defaultTaskScope} tasks
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
                    detail={
                      session?.capabilities.canSwitchWorkspace
                        ? "Switching rebinds dataset and queue state."
                        : "This session currently exposes a single workspace context."
                    }
                  />
                  <CompactContextCard
                    icon={ServerCog}
                    label="Allowed Actions"
                    value={workspace?.allowedActions.switchTo ? "Switchable" : "Pinned"}
                    detail="Backend workspace allowed_actions are the only switch authority."
                  />
                </div>
              </div>
            </SectionFrame>
          ) : null}

          {selectedSection === "dataset" ? (
            <SectionFrame
              icon={Database}
              title="Active Dataset"
              description="Single-select dataset context from session authority."
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
                <ShellNotice
                  className="mb-4"
                  tone={datasetNotice.tone === "success" ? "success" : "warning"}
                >
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

                  {datasetCatalogQuery.isLoading ? (
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      Loading workspace-visible datasets...
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
                        : "The session remains the canonical dataset authority."
                    }
                  />
                  <CompactContextCard
                    icon={Database}
                    label="Family"
                    value={activeDataset?.family ?? "Pending"}
                    detail={
                      activeDataset
                        ? "Dashboard and raw-data surfaces rebind from this session selection."
                        : "Attach a dataset only when a workflow needs a canonical context."
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
              description="Queue visibility and latest attachment summary."
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
                          : "Open a workflow surface or use queue links below to attach a task."
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
                            {task.lane}
                          </span>
                        </div>
                      </Link>
                    ))
                  ) : (
                    <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4 text-sm text-muted-foreground">
                      No workspace-visible tasks are available yet.
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
              description="Runtime summary for the active workspace."
            >
              <div className="grid gap-3 md:grid-cols-2">
                <CompactContextCard
                  icon={ServerCog}
                  label={workerSummary.label}
                  value={workerSummary.value}
                  detail={workerSummary.detail}
                />
                <div className="rounded-[0.95rem] border border-border bg-background px-4 py-4 text-sm leading-6 text-muted-foreground">
                  {workerSummary.tone === "success"
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
