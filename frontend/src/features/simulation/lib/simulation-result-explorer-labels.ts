export function formatExplorerAxisTitle(label: string, unit: string) {
  const normalizedLabel = label.trim();
  const normalizedUnit = unit.trim();

  if (!normalizedUnit) {
    return normalizedLabel;
  }

  const lowerLabel = normalizedLabel.toLowerCase();
  const lowerUnit = normalizedUnit.toLowerCase();

  if (
    lowerLabel.endsWith(`(${lowerUnit})`) ||
    lowerLabel.endsWith(`[${lowerUnit}]`)
  ) {
    return normalizedLabel;
  }

  return `${normalizedLabel} (${normalizedUnit})`;
}
