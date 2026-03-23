import {
  parseCircuitDefinitionId,
  type CircuitDefinitionRouteId,
} from "@/features/circuit-definition-editor/lib/schema-identity";
import type { CircuitDefinitionSummary } from "@/features/circuit-definition-editor/lib/contracts";

export function parseDefinitionIdParam(value: string | null): CircuitDefinitionRouteId | null {
  if (!value) {
    return null;
  }

  if (value === "new") {
    return "new";
  }

  return parseCircuitDefinitionId(value);
}

export function resolveSelectedDefinitionId(
  currentValue: string | null,
  definitions: readonly CircuitDefinitionSummary[] | undefined,
): string | null {
  if (!definitions || definitions.length === 0) {
    return currentValue;
  }

  const parsedValue = parseDefinitionIdParam(currentValue);
  if (parsedValue === "new") {
    return "new";
  }

  if (parsedValue !== null) {
    return definitions.some((definition) => definition.definition_id === parsedValue)
      ? parsedValue
      : String(definitions[0].definition_id);
  }

  return String(definitions[0].definition_id);
}
