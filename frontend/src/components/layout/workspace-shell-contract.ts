"use client";

import type {
  RuntimeMode,
  SessionAuthMode,
  SessionSnapshot,
  SessionVisibilityScope,
  WorkspaceSwitchResult,
} from "@/lib/api/session";
import { resolveSessionConnectionTargetLabel as resolveConnectionTargetLabel } from "@/lib/api/session";
import type { DatasetCatalogRow } from "@/features/data-browser/lib/contracts";
import type { TaskSummary } from "@/lib/api/tasks";
import type {
  ActiveDatasetSnapshot,
  ActiveDatasetSource,
  ActiveDatasetStatus,
} from "@/lib/app-state/active-dataset";
import type { AppSessionStatus } from "@/lib/app-state/app-session";
import { ApiError } from "@/lib/api/client";

export type ShellAuthViewState =
  | "loading"
  | "local_bypass"
  | "authenticated"
  | "anonymous"
  | "degraded";
export type ShellGlobalContextSection = "runtime" | "workspace" | "dataset" | "tasks";

const openGlobalContextEventName = "workspace:open-global-context";

type ShellAuthSummaryInput = Readonly<{
  session: SessionSnapshot | undefined;
  status: AppSessionStatus;
  error: Error | undefined;
}>;

export function describeShellError(error: Error | undefined): string | null {
  if (!error) {
    return null;
  }

  if (error instanceof ApiError) {
    const errorCode = error.errorCode ? ` (${error.errorCode})` : "";
    const debugRef = error.debugRef ? ` · Ref ${error.debugRef}` : "";
    return `${error.message}${errorCode}${debugRef}`;
  }

  return error.message;
}

export function resolveShellAuthViewState({
  session,
  status,
  error,
}: ShellAuthSummaryInput): ShellAuthViewState {
  if (status === "loading" && !session && !error) {
    return "loading";
  }

  if (session?.authState === "degraded" || (status === "error" && !session)) {
    return "degraded";
  }

  if (session?.authState === "local_bypass") {
    return "local_bypass";
  }

  return session?.authState ?? "anonymous";
}

export function resolveShellAuthModeLabel(mode: SessionAuthMode | undefined) {
  switch (mode) {
    case "jwt_refresh_cookie":
      return "JWT refresh cookie";
    case "jwt_cookie":
      return "JWT cookie";
    case "local_bypass":
      return "Local bypass";
    case "local_stub":
    default:
      return "Local stub";
  }
}

export function resolveRuntimeModeLabel(mode: RuntimeMode | undefined) {
  return mode === "local" ? "Local Mode" : "Online Mode";
}

export function resolveSessionWorkspaceLabel(
  input:
    | SessionSnapshot
    | Readonly<{
        runtimeMode: RuntimeMode;
        workspace: SessionSnapshot["workspace"] | undefined;
      }>
    | undefined,
) {
  if (input?.runtimeMode === "local") {
    return "Local Space";
  }

  return input?.workspace?.displayName ?? "Workspace pending";
}

export function resolveShellConnectionTargetLabel(session: SessionSnapshot | undefined) {
  if (!session || session.runtimeMode === "local") {
    return "Local backend";
  }

  return resolveConnectionTargetLabel(session.connection) ?? "Server target pending";
}

export function resolveVisibilityScopeLabel(scope: SessionVisibilityScope | null | undefined) {
  if (!scope) {
    return "private";
  }

  return scope;
}

export function resolveShellAuthSummary(input: ShellAuthSummaryInput) {
  const state = resolveShellAuthViewState(input);
  const errorDetail = describeShellError(input.error);

  if (state === "loading") {
    return {
      state,
      tone: "info",
      badgeLabel: "Resolving",
      triggerName: "Session resolving",
      triggerDetail: "Checking session authority",
      menuTitle: "Resolving session",
      menuDescription: "The shell is still waiting for the backend session authority.",
      primaryActionHref: "/login",
      primaryActionLabel: "Go to login",
    } as const;
  }

  if (state === "local_bypass") {
    return {
      state,
      tone: "info",
      badgeLabel: "Local Mode",
      triggerName: input.session?.user?.displayName ?? "Local operator",
      triggerDetail: `${resolveSessionWorkspaceLabel(input.session)} · No sign-in required`,
      menuTitle: "Local Mode",
      menuDescription:
        "This shell is running in Local Mode. Local Space stays available without remote authentication.",
      primaryActionHref: "/login",
      primaryActionLabel: "Connect online",
    } as const;
  }

  if (state === "authenticated") {
    const displayName = input.session?.user?.displayName ?? "Authenticated User";
    const workspaceName = resolveSessionWorkspaceLabel(input.session);
    const targetLabel = resolveShellConnectionTargetLabel(input.session);

    return {
      state,
      tone: "success",
      badgeLabel: "Authenticated",
      triggerName: displayName,
      triggerDetail: `${workspaceName} · ${targetLabel}`,
      menuTitle: "Authenticated session",
      menuDescription: input.session?.user?.email
        ? `${displayName} is signed in as ${input.session.user.email}.`
        : `${displayName} is signed in and backed by the shared session surface.`,
      primaryActionHref: "/logout",
      primaryActionLabel: "Log out",
    } as const;
  }

  if (state === "anonymous") {
    return {
      state,
      tone: "warning",
      badgeLabel: "Auth required",
      triggerName: "Online mode",
      triggerDetail: "Sign in is required for the current server target",
      menuTitle: "Online authentication required",
      menuDescription:
        "This shell is currently targeting online authority without an authenticated session.",
      primaryActionHref: "/login",
      primaryActionLabel: "Sign in",
    } as const;
  }

  return {
    state,
    tone: "error",
    badgeLabel: "Connection warning",
    triggerName: "Online connection",
    triggerDetail: errorDetail ?? "The shell could not resolve a healthy session.",
    menuTitle: "Online mode unavailable",
    menuDescription:
      errorDetail ??
      "The shell could not confirm the current session. Retry session resolution before trusting auth or workspace context.",
    primaryActionHref: "/login",
    primaryActionLabel: "Recover session",
  } as const;
}

export function resolveShellUserInitials(displayName: string | null | undefined) {
  const normalized = displayName?.trim();
  if (!normalized) {
    return "AN";
  }

  const parts = normalized.split(/\s+/).slice(0, 2);
  return parts
    .map((part) => part.charAt(0).toUpperCase())
    .join("")
    .slice(0, 2);
}

export function requestOpenGlobalContext(section: ShellGlobalContextSection = "tasks") {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(
    new CustomEvent(openGlobalContextEventName, {
      detail: {
        section,
      },
    }),
  );
}

export function subscribeToGlobalContextRequests(
  listener: (section: ShellGlobalContextSection) => void,
) {
  if (typeof window === "undefined") {
    return () => {};
  }

  const handleOpenRequest = (event: Event) => {
    const section =
      event instanceof CustomEvent &&
      event.detail &&
      typeof event.detail === "object" &&
      "section" in event.detail &&
      typeof event.detail.section === "string"
        ? (event.detail.section as ShellGlobalContextSection)
        : "tasks";

    listener(section);
  };

  window.addEventListener(openGlobalContextEventName, handleOpenRequest);
  return () => {
    window.removeEventListener(openGlobalContextEventName, handleOpenRequest);
  };
}

export function resolveShellTaskHref(task: Pick<TaskSummary, "lane" | "taskId">) {
  const basePath = task.lane === "characterization" ? "/characterization" : "/circuit-simulation";
  return `${basePath}?taskId=${task.taskId}`;
}

export function resolveShellTaskLabel(task: Pick<TaskSummary, "kind" | "executionMode">) {
  const kindLabel =
    task.kind === "post_processing"
      ? "Post-processing"
      : task.kind === "characterization"
        ? "Characterization"
        : "Simulation";

  return `${kindLabel} · ${task.executionMode === "smoke" ? "Smoke" : task.executionMode === "run" ? "Run" : "Task"}`;
}

export function resolveShellActiveDatasetSummary(
  dataset: ActiveDatasetSnapshot | null,
  options: Readonly<{
    status: ActiveDatasetStatus;
    source: ActiveDatasetSource;
    errorDetail?: string | null;
    isUpdating: boolean;
  }>,
) {
  if (options.status === "syncing-route" || options.isUpdating) {
    return {
      value: "Syncing active dataset...",
      detail: "Session authority is updating the dataset selection.",
      badge: "Syncing",
    } as const;
  }

  if (options.errorDetail && !dataset) {
    return {
      value: "No active dataset",
      detail: options.errorDetail,
      badge: "Error",
    } as const;
  }

  if (!dataset) {
    return {
      value: "No active dataset",
      detail: "Select one from Raw Data to attach it to the session.",
      badge: null,
    } as const;
  }

  return {
    value: dataset.name ?? dataset.datasetId,
    detail: null,
    badge:
      dataset.status ??
      (options.source === "url" ? "Attached" : options.source === "session" ? "Session" : null),
  } as const;
}

export function resolveShellWorkspaceMemberships(
  memberships: SessionSnapshot["memberships"] | undefined,
) {
  if (!memberships) {
    return [];
  }

  const switchableMemberships = memberships.filter(
    (membership) => membership.allowedActions.switchTo || membership.isActive,
  );

  return [...switchableMemberships].sort((left, right) => {
    if (left.isActive === right.isActive) {
      return (left.displayName ?? left.workspaceId).localeCompare(
        right.displayName ?? right.workspaceId,
      );
    }
    return left.isActive ? -1 : 1;
  });
}

export function filterShellDatasets(
  rows: readonly DatasetCatalogRow[],
  query: string,
  activeDatasetId: string | null,
) {
  const normalizedQuery = query.trim().toLowerCase();
  const filteredRows =
    normalizedQuery.length === 0
      ? rows
      : rows.filter((row) =>
          [row.name, row.dataset_id, row.family, row.owner_display_name, row.device_type]
            .filter(Boolean)
            .some((value) => value.toLowerCase().includes(normalizedQuery)),
        );

  return [...filteredRows].sort((left, right) => {
    const leftActive = left.dataset_id === activeDatasetId;
    const rightActive = right.dataset_id === activeDatasetId;
    if (leftActive === rightActive) {
      return left.name.localeCompare(right.name);
    }
    return leftActive ? -1 : 1;
  });
}

export function resolveWorkspaceSwitchNotice(result: WorkspaceSwitchResult) {
  const detachedCount = result.detachedTaskIds.length;
  const detachedSuffix =
    detachedCount > 0
      ? ` ${detachedCount} task${detachedCount === 1 ? "" : "s"} detached from queue visibility.`
      : "";

  if (result.activeDatasetResolution === "preserved" && result.session.activeDataset) {
    return {
      tone: "success",
      message: `Workspace switched. Active dataset stayed on ${result.session.activeDataset.name}.${detachedSuffix}`,
    } as const;
  }

  if (result.activeDatasetResolution === "rebound" && result.session.activeDataset) {
    return {
      tone: "primary",
      message: `Workspace switched. Active dataset rebound to ${result.session.activeDataset.name}.${detachedSuffix}`,
    } as const;
  }

  return {
    tone: "warning",
    message: `Workspace switched. Active dataset was cleared for this workspace.${detachedSuffix}`,
  } as const;
}
