"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import { getCharacterizationArtifactPayload } from "@/features/characterization/lib/api";
import type {
  CharacterizationArtifactPayload,
  CharacterizationArtifactViewMode,
  CharacterizationResultDetail,
} from "@/features/characterization/lib/contracts";
import {
  buildCharacterizationArtifactPayloadRequest,
  resolveCharacterizationArtifactPresetId,
  resolveCharacterizationArtifactPresetViews,
  resolveCharacterizationArtifactSelection,
  resolveCharacterizationArtifactViewMode,
} from "@/features/characterization/lib/result-explorer";

type UseCharacterizationResultExplorerInput = Readonly<{
  datasetId: string | null;
  designId: string | null;
  resultDetail: CharacterizationResultDetail | null;
}>;

export function useCharacterizationResultExplorer({
  datasetId,
  designId,
  resultDetail,
}: UseCharacterizationResultExplorerInput) {
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [selectedViewMode, setSelectedViewMode] =
    useState<CharacterizationArtifactViewMode | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);

  const artifactManifest = resultDetail?.artifactManifest ?? [];
  const selectedArtifact = useMemo(
    () => resolveCharacterizationArtifactSelection(artifactManifest, selectedArtifactId),
    [artifactManifest, selectedArtifactId],
  );
  const resolvedViewMode = useMemo(
    () => resolveCharacterizationArtifactViewMode(selectedArtifact, selectedViewMode),
    [selectedArtifact, selectedViewMode],
  );
  const availablePresetViews = useMemo(
    () => resolveCharacterizationArtifactPresetViews(selectedArtifact, resolvedViewMode),
    [selectedArtifact, resolvedViewMode],
  );
  const resolvedPresetId = useMemo(
    () =>
      resolveCharacterizationArtifactPresetId(
        selectedArtifact,
        resolvedViewMode,
        selectedPresetId,
      ),
    [selectedArtifact, resolvedViewMode, selectedPresetId],
  );
  const payloadRequest = useMemo(
    () =>
      buildCharacterizationArtifactPayloadRequest({
        artifact: selectedArtifact,
        viewMode: resolvedViewMode,
        presetId: resolvedPresetId,
      }),
    [resolvedPresetId, resolvedViewMode, selectedArtifact],
  );

  useEffect(() => {
    const nextArtifactId = selectedArtifact?.artifactId ?? null;
    setSelectedArtifactId((current) => (current === nextArtifactId ? current : nextArtifactId));
  }, [selectedArtifact?.artifactId]);

  useEffect(() => {
    setSelectedViewMode((current) => (current === resolvedViewMode ? current : resolvedViewMode));
  }, [resolvedViewMode]);

  useEffect(() => {
    setSelectedPresetId((current) => (current === resolvedPresetId ? current : resolvedPresetId));
  }, [resolvedPresetId]);

  const payloadQuery = useSWR(
    datasetId &&
      designId &&
      resultDetail?.resultId &&
      selectedArtifact?.artifactId &&
      payloadRequest
      ? [
          "characterization-artifact-payload",
          datasetId,
          designId,
          resultDetail.resultId,
          selectedArtifact.artifactId,
          payloadRequest.viewMode,
          payloadRequest.presetId,
        ]
      : null,
    () =>
      datasetId &&
      designId &&
      resultDetail?.resultId &&
      selectedArtifact?.artifactId &&
      payloadRequest
        ? getCharacterizationArtifactPayload(
            datasetId,
            designId,
            resultDetail.resultId,
            selectedArtifact.artifactId,
            payloadRequest,
          )
        : Promise.resolve(undefined),
    {
      keepPreviousData: true,
    },
  );

  return {
    selectedArtifact,
    selectedArtifactId: selectedArtifact?.artifactId ?? null,
    setSelectedArtifactId,
    resolvedViewMode,
    setSelectedViewMode,
    availablePresetViews,
    resolvedPresetId,
    setSelectedPresetId,
    payload: (payloadQuery.data as CharacterizationArtifactPayload | undefined) ?? null,
    payloadError: payloadQuery.error as Error | undefined,
    isPayloadLoading: payloadQuery.isLoading,
    isPayloadRefreshing: payloadQuery.isValidating && !payloadQuery.isLoading,
  };
}

export type UseCharacterizationResultExplorerResult = ReturnType<
  typeof useCharacterizationResultExplorer
>;
