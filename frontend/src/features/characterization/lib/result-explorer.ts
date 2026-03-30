import type {
  CharacterizationArtifactManifestEntry,
  CharacterizationArtifactPresetView,
  CharacterizationArtifactViewMode,
} from "@/features/characterization/lib/contracts";

export function resolveCharacterizationArtifactSelection(
  manifest: readonly CharacterizationArtifactManifestEntry[],
  selectedArtifactId: string | null,
) {
  if (manifest.length === 0) {
    return null;
  }

  if (selectedArtifactId) {
    const selectedArtifact = manifest.find(
      (artifact) => artifact.artifactId === selectedArtifactId,
    );
    if (selectedArtifact) {
      return selectedArtifact;
    }
  }

  return manifest[0] ?? null;
}

export function resolveCharacterizationArtifactViewMode(
  artifact: CharacterizationArtifactManifestEntry | null,
  selectedViewMode: CharacterizationArtifactViewMode | null,
): CharacterizationArtifactViewMode | null {
  if (!artifact) {
    return null;
  }

  const supportedViewModes =
    artifact.querySpec.supportedViewModes.length > 0
      ? artifact.querySpec.supportedViewModes
      : artifact.supportedViewModes;

  if (selectedViewMode && supportedViewModes.includes(selectedViewMode)) {
    return selectedViewMode;
  }

  const defaultViewModes = artifact.querySpec.defaultPresetsByViewMode
    .map((item) => item.viewMode)
    .filter((viewMode, index, values) => values.indexOf(viewMode) === index);
  const firstDefaultViewMode = defaultViewModes.find((viewMode) =>
    supportedViewModes.includes(viewMode),
  );
  if (firstDefaultViewMode) {
    return firstDefaultViewMode;
  }

  if (artifact.viewKind !== "preset_query" && supportedViewModes.includes(artifact.viewKind)) {
    return artifact.viewKind;
  }

  if (supportedViewModes.length > 0) {
    return supportedViewModes[0] ?? null;
  }

  return artifact.viewKind === "preset_query" ? null : artifact.viewKind;
}

export function resolveCharacterizationArtifactPresetViews(
  artifact: CharacterizationArtifactManifestEntry | null,
  viewMode: CharacterizationArtifactViewMode | null,
) {
  if (!artifact || !viewMode) {
    return [] as readonly CharacterizationArtifactPresetView[];
  }

  const supportedPresetIds =
    artifact.querySpec.supportedPresetIds.length > 0
      ? new Set(artifact.querySpec.supportedPresetIds)
      : null;

  return artifact.presetViews.filter((preset) => {
    if (preset.viewMode !== viewMode) {
      return false;
    }

    if (!supportedPresetIds) {
      return true;
    }

    return supportedPresetIds.has(preset.presetId);
  });
}

export function resolveCharacterizationArtifactPresetId(
  artifact: CharacterizationArtifactManifestEntry | null,
  viewMode: CharacterizationArtifactViewMode | null,
  selectedPresetId: string | null,
) {
  const presetViews = resolveCharacterizationArtifactPresetViews(artifact, viewMode);
  if (presetViews.length === 0) {
    return null;
  }

  if (selectedPresetId && presetViews.some((preset) => preset.presetId === selectedPresetId)) {
    return selectedPresetId;
  }

  if (
    artifact?.querySpec.defaultPresetId &&
    presetViews.some((preset) => preset.presetId === artifact.querySpec.defaultPresetId)
  ) {
    return artifact.querySpec.defaultPresetId;
  }

  const defaultPresetForViewMode = artifact?.querySpec.defaultPresetsByViewMode.find(
    (defaultPreset) => defaultPreset.viewMode === viewMode,
  );
  if (
    defaultPresetForViewMode &&
    presetViews.some((preset) => preset.presetId === defaultPresetForViewMode.presetId)
  ) {
    return defaultPresetForViewMode.presetId;
  }

  return (
    presetViews.find((preset) => preset.isDefault)?.presetId ??
    presetViews[0]?.presetId ??
    null
  );
}

export function buildCharacterizationArtifactPayloadRequest(input: Readonly<{
  artifact: CharacterizationArtifactManifestEntry | null;
  viewMode: CharacterizationArtifactViewMode | null;
  presetId: string | null;
}>) {
  if (!input.artifact || !input.viewMode) {
    return null;
  }

  return {
    viewMode: input.viewMode,
    presetId:
      input.presetId &&
      resolveCharacterizationArtifactPresetViews(input.artifact, input.viewMode).some(
        (preset) => preset.presetId === input.presetId,
      )
        ? input.presetId
        : null,
  };
}
