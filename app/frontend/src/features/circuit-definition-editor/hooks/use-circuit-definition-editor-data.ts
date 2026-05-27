"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import {
  circuitDefinitionsCatalogKey,
  circuitDefinitionDetailKey,
  circuitDefinitionCloneKey,
  circuitDefinitionsListKey,
  circuitDefinitionPublishKey,
  cloneCircuitDefinition,
  createCircuitDefinition,
  deleteCircuitDefinition,
  getCircuitDefinition,
  listCircuitDefinitionsCatalog,
  publishCircuitDefinition,
  updateCircuitDefinition,
} from "@/features/circuit-definition-editor/lib/api";
import type {
  CircuitDefinitionCloneDraft,
  CircuitDefinitionCreateDraft,
  CircuitDefinitionDetail,
  CircuitDefinitionUpdateDraft,
} from "@/features/circuit-definition-editor/lib/contracts";
import type {
  CircuitDefinitionId,
  CircuitDefinitionRouteId,
} from "@/features/circuit-definition-editor/lib/schema-identity";

type MutationStatus = Readonly<{
  state:
    | "idle"
    | "saving"
    | "publishing"
    | "cloning"
    | "deleting"
    | "success"
    | "error";
  message: string | null;
}>;

export function useCircuitDefinitionEditorData(
  selectedDefinitionId: CircuitDefinitionRouteId | null,
) {
  const { mutate } = useSWRConfig();
  const [mutationStatus, setMutationStatus] = useState<MutationStatus>({
    state: "idle",
    message: null,
  });

  const definitionsQuery = useSWR(circuitDefinitionsCatalogKey, listCircuitDefinitionsCatalog);
  const detailKey =
    selectedDefinitionId !== null && selectedDefinitionId !== "new"
      ? circuitDefinitionDetailKey(selectedDefinitionId)
      : null;

  const detailQuery = useSWR(detailKey, () =>
    selectedDefinitionId !== null && selectedDefinitionId !== "new"
      ? getCircuitDefinition(selectedDefinitionId)
      : Promise.resolve(undefined),
  );

  async function refreshDefinitionQueries(
    definitionId: CircuitDefinitionId,
    nextDetail?: CircuitDefinitionDetail,
  ) {
    await Promise.all([
      mutate(circuitDefinitionsListKey),
      mutate(circuitDefinitionsCatalogKey),
      mutate(
        circuitDefinitionDetailKey(definitionId),
        nextDetail,
        nextDetail ? { revalidate: false } : undefined,
      ),
    ]);
  }

  async function saveDefinition(
    draft: CircuitDefinitionCreateDraft,
    input: Readonly<{
      definitionId: CircuitDefinitionRouteId | null;
      activeDefinition?: CircuitDefinitionDetail;
    }>,
  ): Promise<CircuitDefinitionDetail> {
    setMutationStatus({ state: "saving", message: null });

    try {
      const detail =
        input.definitionId !== null && input.definitionId !== "new"
          ? await updateCircuitDefinition(input.definitionId, {
              source_text: draft.source_text,
              name: draft.name,
              concurrency_token: input.activeDefinition?.concurrency_token,
            } satisfies CircuitDefinitionUpdateDraft)
          : await createCircuitDefinition(draft);

      await refreshDefinitionQueries(detail.definition_id, detail);
      setMutationStatus({
        state: "success",
        message:
          input.definitionId !== null && input.definitionId !== "new"
            ? "Circuit definition updated."
            : "Circuit definition created.",
      });
      return detail;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to save the circuit definition.";
      setMutationStatus({ state: "error", message });
      throw error;
    }
  }

  async function removeDefinition(definitionId: CircuitDefinitionId) {
    const result = await removeDefinitions([definitionId]);
    if (result.failedIds.length > 0) {
      throw new Error("Unable to delete the circuit definition.");
    }
  }

  async function removeDefinitions(definitionIds: readonly CircuitDefinitionId[]) {
    const uniqueDefinitionIds = [...new Set(definitionIds)];
    if (uniqueDefinitionIds.length === 0) {
      return {
        deletedIds: [] as CircuitDefinitionId[],
        failedIds: [] as CircuitDefinitionId[],
      };
    }

    setMutationStatus({ state: "deleting", message: null });

    const settled = await Promise.allSettled(
      uniqueDefinitionIds.map(async (definitionId) => {
        await deleteCircuitDefinition(definitionId);
        return definitionId;
      }),
    );
    const deletedIds = settled
      .filter(
        (result): result is PromiseFulfilledResult<CircuitDefinitionId> =>
          result.status === "fulfilled",
      )
      .map((result) => result.value);
    const failedIds = uniqueDefinitionIds.filter(
      (definitionId) => !deletedIds.includes(definitionId),
    );

    await Promise.all([
      mutate(circuitDefinitionsListKey),
      mutate(circuitDefinitionsCatalogKey),
      ...uniqueDefinitionIds.map((definitionId) =>
        mutate(circuitDefinitionDetailKey(definitionId), undefined, { revalidate: false }),
      ),
    ]);

    if (failedIds.length === 0) {
      setMutationStatus({
        state: "success",
        message:
          deletedIds.length === 1
            ? "Circuit definition removed."
            : `Removed ${deletedIds.length} circuit definitions.`,
      });
    } else {
      setMutationStatus({
        state: "error",
        message:
          deletedIds.length > 0
            ? `Removed ${deletedIds.length} circuit definitions. ${failedIds.length} could not be deleted.`
            : uniqueDefinitionIds.length === 1
              ? "Unable to delete the circuit definition."
              : "Unable to delete the selected circuit definitions.",
      });
    }

    return {
      deletedIds,
      failedIds,
    };
  }

  async function publishDefinition(definitionId: CircuitDefinitionId) {
    setMutationStatus({ state: "publishing", message: null });

    try {
      const detail = await publishCircuitDefinition(definitionId);
      await refreshDefinitionQueries(detail.definition_id, detail);
      setMutationStatus({
        state: "success",
        message: "Circuit definition published to workspace visibility.",
      });
      return detail;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to publish the circuit definition.";
      setMutationStatus({ state: "error", message });
      throw error;
    }
  }

  async function cloneDefinition(
    definitionId: CircuitDefinitionId,
    cloneDraft?: CircuitDefinitionCloneDraft,
  ) {
    setMutationStatus({ state: "cloning", message: null });

    try {
      const detail = await cloneCircuitDefinition(definitionId, cloneDraft);
      await Promise.all([
        mutate(circuitDefinitionsListKey),
        mutate(circuitDefinitionsCatalogKey),
        mutate(circuitDefinitionDetailKey(detail.definition_id), detail, { revalidate: false }),
        mutate(circuitDefinitionCloneKey(definitionId), undefined, {
          revalidate: false,
        }),
        mutate(circuitDefinitionPublishKey(definitionId), undefined, {
          revalidate: false,
        }),
      ]);
      setMutationStatus({
        state: "success",
        message: "Private clone created from the persisted definition.",
      });
      return detail;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to clone the circuit definition.";
      setMutationStatus({ state: "error", message });
      throw error;
    }
  }

  function clearMutationStatus() {
    setMutationStatus({ state: "idle", message: null });
  }

  return {
    definitions: definitionsQuery.data?.catalog.rows,
    definitionsMeta: definitionsQuery.data?.meta,
    definitionsTotalCount: definitionsQuery.data?.catalog.total_count ?? 0,
    definitionsError: definitionsQuery.error as Error | undefined,
    isDefinitionsLoading: definitionsQuery.isLoading,
    activeDefinition: detailQuery.data,
    activeDefinitionError: detailQuery.error as Error | undefined,
    isActiveDefinitionLoading: detailQuery.isLoading,
    mutationStatus,
    saveDefinition,
    publishDefinition,
    cloneDefinition,
    removeDefinition,
    removeDefinitions,
    clearMutationStatus,
  };
}
