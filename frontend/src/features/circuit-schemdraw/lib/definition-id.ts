import { parseDefinitionIdParam } from "@/features/circuit-definition-editor/lib/definition-id";
import type { CircuitDefinitionSummary } from "@/features/circuit-definition-editor/lib/contracts";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

export function parseSchemdrawDefinitionIdParam(
  value: string | null,
): CircuitDefinitionId | null {
  const parsedValue = parseDefinitionIdParam(value);
  return parsedValue === "new" ? null : parsedValue;
}

export function resolveSchemdrawDefinitionId(
  currentValue: string | null,
  definitions: readonly CircuitDefinitionSummary[] | undefined,
): CircuitDefinitionId | null {
  if (currentValue === null) {
    return null;
  }

  if (!definitions || definitions.length === 0) {
    return parseSchemdrawDefinitionIdParam(currentValue);
  }

  const parsedValue = parseSchemdrawDefinitionIdParam(currentValue);
  if (parsedValue !== null) {
    return definitions.some((definition) => definition.definition_id === parsedValue)
      ? parsedValue
      : definitions[0].definition_id;
  }

  return definitions[0].definition_id;
}
