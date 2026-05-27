export function parseCharacterizationTaskIdParam(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

export function resolveCharacterizationTaskId(
  requestedTaskId: number | null,
  latestTaskId: number | null,
): number | null {
  return requestedTaskId ?? latestTaskId ?? null;
}
