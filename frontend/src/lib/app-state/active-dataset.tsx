"use client";

import { createContext, useContext, useEffect, useEffectEvent, useRef, useState } from "react";
import useSWR from "swr";

import {
  datasetProfileKey,
  getDatasetProfile,
} from "@/lib/api/datasets";
import { patchActiveDataset, type SessionVisibilityScope } from "@/lib/api/session";
import {
  canRetryRouteDatasetSync,
  parseDatasetIdFromSearch,
  resolveSearchWithDatasetId,
  resolveActiveDatasetId,
  resolveActiveDatasetSource,
  shouldAutoSyncRouteDataset,
  type RouteDatasetSyncState,
} from "@/lib/app-state/active-dataset-state";
import { useAppSession } from "@/lib/app-state/app-session";
import { useUrlState } from "@/lib/app-state/url-state";

export type ActiveDatasetSource = "url" | "session" | "none";
export type ActiveDatasetStatus = "loading" | "ready" | "empty" | "syncing-route" | "error";

export type ActiveDatasetSnapshot = Readonly<{
  datasetId: string;
  name: string | null;
  owner: string | null;
  family: string | null;
  status: "Ready" | "Queued" | "Review" | null;
  visibilityScope: SessionVisibilityScope | null;
  source: Exclude<ActiveDatasetSource, "none">;
}>;

type ActiveDatasetContextValue = Readonly<{
  activeDataset: ActiveDatasetSnapshot | null;
  routeDatasetId: string | null;
  sessionDatasetId: string | null;
  source: ActiveDatasetSource;
  status: ActiveDatasetStatus;
  isDatasetDetailLoading: boolean;
  datasetDetailError: Error | undefined;
  isUpdatingActiveDataset: boolean;
  isRouteSyncPending: boolean;
  canRetryRouteSync: boolean;
  activeDatasetError: Error | undefined;
  refreshActiveDataset: () => Promise<void>;
  retryRouteSync: () => Promise<void>;
  setActiveDataset: (datasetId: string | null) => Promise<void>;
  clearActiveDataset: () => Promise<void>;
  syncRouteDataset: (datasetId: string | null) => void;
}>;

const ActiveDatasetContext = createContext<ActiveDatasetContextValue | null>(null);

type ActiveDatasetProviderProps = Readonly<{
  children: React.ReactNode;
}>;

export function ActiveDatasetProvider({ children }: ActiveDatasetProviderProps) {
  const {
    session,
    refreshSession,
    sessionError,
    replaceSession,
    hasResolvedSession,
  } = useAppSession();
  const urlState = useUrlState();
  const [mutationError, setMutationError] = useState<Error | undefined>(undefined);
  const [isUpdatingActiveDataset, setIsUpdatingActiveDataset] = useState(false);
  const [routeSyncError, setRouteSyncError] = useState<Error | undefined>(undefined);
  const [routeSyncState, setRouteSyncState] = useState<RouteDatasetSyncState>({
    targetDatasetId: null,
    status: "idle",
  });
  const previousContextKeyRef = useRef(
    `${session?.runtimeMode ?? "online"}:${session?.workspace.workspaceId ?? "none"}`,
  );
  const routeDatasetId = parseDatasetIdFromSearch(urlState.search);
  const sessionDatasetId = session?.activeDataset?.datasetId ?? null;
  const resolvedDatasetId = resolveActiveDatasetId(routeDatasetId, sessionDatasetId);
  const source = resolveActiveDatasetSource(routeDatasetId, sessionDatasetId);
  const detailKey = resolvedDatasetId ? datasetProfileKey(resolvedDatasetId) : null;
  const detailQuery = useSWR(detailKey, () =>
    resolvedDatasetId ? getDatasetProfile(resolvedDatasetId) : Promise.resolve(undefined),
  );
  const isRouteSyncPending = routeSyncState.status === "syncing";
  const canRetryRouteSyncNow = canRetryRouteDatasetSync(
    routeDatasetId,
    sessionDatasetId,
    routeSyncState,
  );

  function syncRouteDatasetSelection(datasetId: string | null) {
    if (typeof window === "undefined") {
      return;
    }

    const nextSearch = resolveSearchWithDatasetId(window.location.search, datasetId);
    if (nextSearch === window.location.search) {
      return;
    }

    const nextUrl = `${window.location.pathname}${nextSearch}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", nextUrl);
  }

  async function syncActiveDataset(
    datasetId: string | null,
    options?: Readonly<{ isRouteSync?: boolean }>,
  ) {
    const isRouteSync = options?.isRouteSync ?? false;
    const targetDatasetId = datasetId ?? null;

    if (isRouteSync) {
      setRouteSyncError(undefined);
      setRouteSyncState({
        targetDatasetId,
        status: "syncing",
      });
    } else {
      setMutationError(undefined);
      setIsUpdatingActiveDataset(true);
    }

    try {
      const nextSession = await patchActiveDataset(datasetId);
      await replaceSession(nextSession);
      syncRouteDatasetSelection(targetDatasetId);

      if (isRouteSync) {
        setRouteSyncState({
          targetDatasetId,
          status: "idle",
        });
      }
    } catch (error) {
      const resolvedError =
        error instanceof Error ? error : new Error("Unable to update active dataset.");

      if (isRouteSync) {
        setRouteSyncError(resolvedError);
        setRouteSyncState({
          targetDatasetId,
          status: "error",
        });
      } else {
        setMutationError(resolvedError);
      }

      throw resolvedError;
    } finally {
      if (!isRouteSync) {
        setIsUpdatingActiveDataset(false);
      }
    }
  }

  const syncRouteDatasetToSession = useEffectEvent((datasetId: string) => {
    void syncActiveDataset(datasetId, { isRouteSync: true }).catch(() => undefined);
  });

  useEffect(() => {
    if (routeDatasetId !== routeSyncState.targetDatasetId) {
      setRouteSyncError(undefined);
      setRouteSyncState({
        targetDatasetId: routeDatasetId,
        status: "idle",
      });
    }
  }, [routeDatasetId, routeSyncState.targetDatasetId]);

  useEffect(() => {
    if (routeDatasetId && routeDatasetId === sessionDatasetId) {
      setRouteSyncError(undefined);
      setRouteSyncState({
        targetDatasetId: routeDatasetId,
        status: "idle",
      });
    }
  }, [routeDatasetId, sessionDatasetId]);

  useEffect(() => {
    const currentContextKey = `${session?.runtimeMode ?? "online"}:${session?.workspace.workspaceId ?? "none"}`;
    const previousContextKey = previousContextKeyRef.current;

    if (
      previousContextKey &&
      previousContextKey !== currentContextKey &&
      routeDatasetId !== sessionDatasetId
    ) {
      syncRouteDatasetSelection(sessionDatasetId);
    }

    previousContextKeyRef.current = currentContextKey;
  }, [routeDatasetId, session?.runtimeMode, sessionDatasetId, session?.workspace.workspaceId]);

  useEffect(() => {
    if (
      !routeDatasetId ||
      isUpdatingActiveDataset ||
      !shouldAutoSyncRouteDataset(routeDatasetId, sessionDatasetId, routeSyncState)
    ) {
      return;
    }

    syncRouteDatasetToSession(routeDatasetId);
  }, [routeDatasetId, routeSyncState, sessionDatasetId, isUpdatingActiveDataset]);

  const activeDataset =
    resolvedDatasetId && source !== "none"
      ? {
          datasetId: resolvedDatasetId,
          name:
            session?.activeDataset?.datasetId === resolvedDatasetId
              ? session.activeDataset.name
              : (detailQuery.data?.name ?? null),
          owner:
            session?.activeDataset?.datasetId === resolvedDatasetId
              ? session.activeDataset.owner
              : (detailQuery.data?.owner_display_name ?? null),
          family:
            session?.activeDataset?.datasetId === resolvedDatasetId
              ? session.activeDataset.family
              : (detailQuery.data?.family ?? null),
          status:
            session?.activeDataset?.datasetId === resolvedDatasetId
              ? session.activeDataset.status
              : (detailQuery.data?.status ?? null),
          visibilityScope:
            session?.activeDataset?.datasetId === resolvedDatasetId
              ? session.activeDataset.visibilityScope
              : (detailQuery.data?.visibility_scope ?? null),
          source,
        }
      : null;
  const activeDatasetError =
    routeSyncError ?? mutationError ?? (detailQuery.error as Error | undefined) ?? sessionError;
  const status: ActiveDatasetStatus = !hasResolvedSession && !activeDataset
    ? "loading"
    : isRouteSyncPending
      ? "syncing-route"
      : activeDatasetError && !activeDataset
        ? "error"
        : activeDataset
          ? "ready"
          : "empty";

  return (
    <ActiveDatasetContext.Provider
      value={{
        activeDataset,
        routeDatasetId,
        sessionDatasetId,
        source,
        status,
        isDatasetDetailLoading: detailQuery.isLoading,
        datasetDetailError: detailQuery.error as Error | undefined,
        isUpdatingActiveDataset,
        isRouteSyncPending,
        canRetryRouteSync: canRetryRouteSyncNow,
        activeDatasetError,
        async refreshActiveDataset() {
          await Promise.all([
            refreshSession().then(() => undefined),
            detailQuery.mutate().then(() => undefined),
          ]);
        },
        async retryRouteSync() {
          if (!routeDatasetId) {
            return;
          }

          await syncActiveDataset(routeDatasetId, { isRouteSync: true });
        },
        async setActiveDataset(datasetId) {
          await syncActiveDataset(datasetId);
        },
        async clearActiveDataset() {
          await syncActiveDataset(null);
        },
        syncRouteDataset(datasetId) {
          syncRouteDatasetSelection(datasetId);
        },
      }}
    >
      {children}
    </ActiveDatasetContext.Provider>
  );
}

export function useActiveDataset() {
  const context = useContext(ActiveDatasetContext);

  if (!context) {
    throw new Error("useActiveDataset must be used within an ActiveDatasetProvider.");
  }

  return context;
}
