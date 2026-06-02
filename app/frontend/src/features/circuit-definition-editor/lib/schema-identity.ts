export type CircuitDefinitionId = string;
export type CircuitDefinitionRouteId = CircuitDefinitionId | "new";

const circuitDefinitionIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function parseCircuitDefinitionId(
  value: string | null | undefined,
): CircuitDefinitionId | null {
  if (!value) {
    return null;
  }

  const normalizedValue = value.trim().toLowerCase();
  if (!circuitDefinitionIdPattern.test(normalizedValue)) {
    return null;
  }

  return normalizedValue;
}

export function formatSchemaIdShort(definitionId: CircuitDefinitionId | null | undefined) {
  return definitionId ? definitionId.slice(0, 8) : "--";
}

export function formatSchemaIdLabel(definitionId: CircuitDefinitionId | null | undefined) {
  return `Schema ID ${formatSchemaIdShort(definitionId)}`;
}

export function matchesSchemaIdQuery(
  definitionId: CircuitDefinitionId,
  normalizedQuery: string,
) {
  if (!normalizedQuery) {
    return true;
  }

  const normalizedId = definitionId.toLowerCase();
  return (
    normalizedId.includes(normalizedQuery) ||
    formatSchemaIdShort(definitionId).toLowerCase().includes(normalizedQuery)
  );
}

export function buildSchemaIdentityDescription(input: Readonly<{
  definitionId: CircuitDefinitionId;
  createdAt?: string | null;
  extra?: string | null;
}>) {
  const segments = [formatSchemaIdLabel(input.definitionId)];

  if (input.createdAt) {
    segments.push(input.createdAt);
  }

  if (input.extra) {
    segments.push(input.extra);
  }

  return segments.join(" · ");
}
