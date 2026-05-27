export function parseTaskIdFromSearch(search: string): number | null {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const taskId = params.get("taskId")?.trim();
  if (!taskId) {
    return null;
  }
  const parsed = parseInt(taskId, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

export function resolveActiveTaskId(
  routeTaskId: number | null,
  latestActiveTaskId: number | null,
): number | null {
  return routeTaskId ?? latestActiveTaskId;
}
