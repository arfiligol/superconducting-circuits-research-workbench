import { parseDefinitionIdParam } from "@/features/circuit-definition-editor/lib/definition-id";
import type { CircuitDefinitionSummary } from "@/features/circuit-definition-editor/lib/contracts";

export function parseSchemdrawDefinitionIdParam(value: string | null): number | null {
  const parsedValue = parseDefinitionIdParam(value);
  return typeof parsedValue === "number" ? parsedValue : null;
}

export function resolveSchemdrawDefinitionId(
  currentValue: string | null,
  definitions: readonly CircuitDefinitionSummary[] | undefined,
): number | null {
  if (currentValue === null) {
    return null;
  }

  if (!definitions || definitions.length === 0) {
    return parseSchemdrawDefinitionIdParam(currentValue);
  }

  const parsedValue = parseSchemdrawDefinitionIdParam(currentValue);
  if (typeof parsedValue === "number") {
    return definitions.some((definition) => definition.definition_id === parsedValue)
      ? parsedValue
      : definitions[0].definition_id;
  }

  return definitions[0].definition_id;
}
