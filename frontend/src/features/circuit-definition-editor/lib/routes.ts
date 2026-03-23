import type { CircuitDefinitionRouteId } from "@/features/circuit-definition-editor/lib/schema-identity";

export function buildCircuitDefinitionEditorHref(definitionId: CircuitDefinitionRouteId) {
  return definitionId === "new"
    ? "/circuit-definition-editor?definitionId=new"
    : `/circuit-definition-editor?definitionId=${definitionId}`;
}

export function buildCircuitDefinitionCatalogHref() {
  return "/schemas";
}

export function buildCircuitSchemdrawHref(definitionId: string) {
  return `/circuit-schemdraw?definitionId=${definitionId}`;
}
