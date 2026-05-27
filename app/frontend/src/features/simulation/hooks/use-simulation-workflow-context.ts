"use client";

import useSWR from "swr";

import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";
import {
  circuitDefinitionDetailKey,
  circuitDefinitionsListKey,
  getCircuitDefinition,
  listCircuitDefinitions,
} from "@/features/circuit-definition-editor/lib/api";
import { resolveSimulationDefinitionId } from "@/features/simulation/lib/definition-id";
import { useActiveDataset } from "@/lib/app-state/active-dataset";
import { useAppSession } from "@/lib/app-state/app-session";

export function useSimulationWorkflowContext(
  selectedDefinitionId: CircuitDefinitionId | null,
) {
  const { session } = useAppSession();
  const activeDatasetState = useActiveDataset();

  const definitionsQuery = useSWR(circuitDefinitionsListKey, listCircuitDefinitions);
  const resolvedDefinitionId = resolveSimulationDefinitionId(
    selectedDefinitionId,
    definitionsQuery.data,
  );
  const selectedDefinitionSummary =
    resolvedDefinitionId !== null
      ? definitionsQuery.data?.find(
          (definition) => definition.definition_id === resolvedDefinitionId,
        )
      : undefined;
  const definitionDetailQuery = useSWR(
    resolvedDefinitionId !== null ? circuitDefinitionDetailKey(resolvedDefinitionId) : null,
    () =>
      resolvedDefinitionId !== null
        ? getCircuitDefinition(resolvedDefinitionId)
        : Promise.resolve(undefined),
  );
  const activeDefinition = definitionDetailQuery.data;
  const hasAttachedDefinition =
    resolvedDefinitionId !== null &&
    activeDefinition?.definition_id === resolvedDefinitionId;

  return {
    session,
    activeDatasetState,
    definitions: definitionsQuery.data,
    definitionsError: definitionsQuery.error as Error | undefined,
    isDefinitionsLoading: definitionsQuery.isLoading,
    resolvedDefinitionId,
    selectedDefinitionSummary,
    activeDefinition,
    activeDefinitionError: definitionDetailQuery.error as Error | undefined,
    isDefinitionTransitioning:
      resolvedDefinitionId !== null &&
      (!hasAttachedDefinition || definitionDetailQuery.isLoading),
    refreshDefinitions: definitionsQuery.mutate,
    refreshActiveDefinition: definitionDetailQuery.mutate,
  };
}
