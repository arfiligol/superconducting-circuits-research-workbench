"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";

import {
  circuitDefinitionDetailKey,
  circuitDefinitionsListKey,
  getCircuitDefinition,
  listCircuitDefinitions,
} from "@/features/circuit-definition-editor/lib/api";
import { resolveSchemdrawDefinitionId } from "@/features/circuit-schemdraw/lib/definition-id";
import { renderSchemdrawPreview } from "@/features/circuit-schemdraw/lib/api";
import {
  buildRelationConfigFailureDetail,
  buildRenderSurfaceFromError,
  buildRenderSurfaceFromResponse,
  buildSchemdrawRenderRequest,
  createInitialRenderSurface,
  ensureSchemdrawDraft,
  markSchemdrawPreviewStale,
  shouldApplySchemdrawResponse,
  updateSchemdrawDraft,
  type SchemdrawEditorDraft,
} from "@/features/circuit-schemdraw/lib/render";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

type RenderMode = "debounced" | "manual";

export function useCircuitSchemdrawData(selectedDefinitionId: CircuitDefinitionId | null) {
  const definitionsQuery = useSWR(circuitDefinitionsListKey, listCircuitDefinitions);
  const resolvedDefinitionId = resolveSchemdrawDefinitionId(
    selectedDefinitionId,
    definitionsQuery.data,
  );
  const selectedDefinitionSummary =
    resolvedDefinitionId !== null
      ? definitionsQuery.data?.find(
          (definition) => definition.definition_id === resolvedDefinitionId,
        )
      : undefined;
  const detailKey =
    resolvedDefinitionId !== null
      ? circuitDefinitionDetailKey(resolvedDefinitionId)
      : null;

  const detailQuery = useSWR(
    detailKey,
    () =>
      resolvedDefinitionId !== null
        ? getCircuitDefinition(resolvedDefinitionId)
        : Promise.resolve(undefined),
    {
      keepPreviousData: true,
    },
  );

  const [draftsByKey, setDraftsByKey] = useState<Record<string, SchemdrawEditorDraft>>({});
  const [renderSurface, setRenderSurface] = useState(createInitialRenderSurface);
  const [isRendering, setIsRendering] = useState(false);
  const latestRequestRef = useRef<Readonly<{
    requestId: string;
    documentVersion: number;
  }> | null>(null);

  const draftKey = String(resolvedDefinitionId ?? "unlinked");
  const activeDraft = useMemo(
    () => ensureSchemdrawDraft(draftsByKey[draftKey], detailQuery.data),
    [detailQuery.data, draftKey, draftsByKey],
  );

  useEffect(() => {
    setDraftsByKey((currentDrafts) => {
      if (currentDrafts[draftKey]) {
        return currentDrafts;
      }

      return {
        ...currentDrafts,
        [draftKey]: ensureSchemdrawDraft(undefined, detailQuery.data),
      };
    });
  }, [detailQuery.data, draftKey]);

  useEffect(() => {
    setRenderSurface((currentSurface) => markSchemdrawPreviewStale(currentSurface));
  }, [activeDraft.documentVersion]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void requestRender("debounced");
    }, 700);

    return () => {
      window.clearTimeout(timer);
    };
  }, [activeDraft.documentVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  async function requestRender(renderMode: RenderMode) {
    const requestId = `${draftKey}-${activeDraft.documentVersion}-${Date.now()}`;
    const nextRequest = {
      requestId,
      documentVersion: activeDraft.documentVersion,
    } as const;
    latestRequestRef.current = nextRequest;

    const request = buildSchemdrawRenderRequest({
      activeDefinition: detailQuery.data,
      draft: activeDraft,
      renderMode,
      requestId,
    });
    if (!request.request) {
      setRenderSurface((currentSurface) => ({
        ...currentSurface,
        phase: "syntax_error",
        statusLabel: "Relation Invalid",
        diagnostics: request.diagnostics,
        isStale: currentSurface.svg !== null,
        failureDetail: buildRelationConfigFailureDetail(request.diagnostics),
      }));
      return;
    }

    setIsRendering(true);
    setRenderSurface((currentSurface) => ({
      ...currentSurface,
      phase: "validating",
      statusLabel: renderMode === "manual" ? "Manual Render" : "Validating",
      diagnostics: [],
      isStale: currentSurface.svg !== null,
      failureDetail: null,
    }));

    try {
      const response = await renderSchemdrawPreview(request.request);
      if (
        !latestRequestRef.current ||
        !shouldApplySchemdrawResponse(
          response,
          latestRequestRef.current.requestId,
          latestRequestRef.current.documentVersion,
        )
      ) {
        return;
      }

      setRenderSurface((currentSurface) => buildRenderSurfaceFromResponse(response, currentSurface));
    } catch (error) {
      if (
        !latestRequestRef.current ||
        latestRequestRef.current.requestId !== requestId
      ) {
        return;
      }

      setRenderSurface((currentSurface) =>
        buildRenderSurfaceFromError(
          error instanceof Error ? error : new Error("Schemdraw render failed."),
          currentSurface,
        ),
      );
    } finally {
      if (latestRequestRef.current?.requestId === requestId) {
        setIsRendering(false);
      }
    }
  }

  function updateSourceText(sourceText: string) {
    setDraftsByKey((currentDrafts) => ({
      ...currentDrafts,
      [draftKey]: updateSchemdrawDraft(activeDraft, { sourceText }),
    }));
  }

  function updateRelationText(relationText: string) {
    setDraftsByKey((currentDrafts) => ({
      ...currentDrafts,
      [draftKey]: updateSchemdrawDraft(activeDraft, { relationText }),
    }));
  }

  function resetDraft() {
    setDraftsByKey((currentDrafts) => ({
      ...currentDrafts,
      [draftKey]: ensureSchemdrawDraft(undefined, detailQuery.data),
    }));
    setRenderSurface((currentSurface) => markSchemdrawPreviewStale(currentSurface));
  }

  return {
    definitions: definitionsQuery.data,
    definitionsError: definitionsQuery.error as Error | undefined,
    isDefinitionsLoading: definitionsQuery.isLoading,
    resolvedDefinitionId,
    selectedDefinitionSummary,
    activeDefinition: detailQuery.data,
    activeDefinitionError: detailQuery.error as Error | undefined,
    isDefinitionTransitioning:
      resolvedDefinitionId !== null &&
      (detailQuery.isLoading || detailQuery.data?.definition_id !== resolvedDefinitionId),
    refreshDefinitions: definitionsQuery.mutate,
    refreshActiveDefinition: detailQuery.mutate,
    draft: activeDraft,
    renderSurface,
    isRendering,
    updateSourceText,
    updateRelationText,
    resetDraft,
    renderNow: () => requestRender("manual"),
  };
}
