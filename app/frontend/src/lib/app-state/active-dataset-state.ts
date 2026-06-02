export function parseDatasetIdFromSearch(search: string): string | null {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const datasetId = params.get("datasetId")?.trim();
  return datasetId ? datasetId : null;
}

export function resolveSearchWithDatasetId(search: string, datasetId: string | null) {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);

  if (datasetId) {
    params.set("datasetId", datasetId);
  } else {
    params.delete("datasetId");
  }

  const nextSearch = params.toString();
  return nextSearch ? `?${nextSearch}` : "";
}

export function resolveActiveDatasetId(
  routeDatasetId: string | null,
  sessionDatasetId: string | null,
): string | null {
  return routeDatasetId ?? sessionDatasetId;
}

export function resolveActiveDatasetSource(
  routeDatasetId: string | null,
  sessionDatasetId: string | null,
): "url" | "session" | "none" {
  if (routeDatasetId) {
    return "url";
  }

  if (sessionDatasetId) {
    return "session";
  }

  return "none";
}

export type RouteDatasetSyncStatus = "idle" | "syncing" | "error";

export type RouteDatasetSyncState = Readonly<{
  targetDatasetId: string | null;
  status: RouteDatasetSyncStatus;
}>;

export function shouldAutoSyncRouteDataset(
  routeDatasetId: string | null,
  sessionDatasetId: string | null,
  syncState: RouteDatasetSyncState,
): boolean {
  if (!routeDatasetId || routeDatasetId === sessionDatasetId) {
    return false;
  }

  if (syncState.targetDatasetId !== routeDatasetId) {
    return true;
  }

  return syncState.status === "idle";
}

export function canRetryRouteDatasetSync(
  routeDatasetId: string | null,
  sessionDatasetId: string | null,
  syncState: RouteDatasetSyncState,
): boolean {
  return (
    !!routeDatasetId &&
    routeDatasetId !== sessionDatasetId &&
    syncState.status === "error" &&
    syncState.targetDatasetId === routeDatasetId
  );
}
