import type { CircuitDefinitionPersistedPreview } from "@/features/circuit-definition-editor/lib/contracts";
import {
  formatCircuitNetlistSource,
  parseCircuitNetlistSource,
  summarizeCircuitDefinitionSerializerBoundary,
  summarizeCircuitNetlistDocument,
} from "@/features/circuit-definition-editor/lib/netlist";
import {
  buildNormalizedOutputPreview,
  partitionValidationNotices,
  resolvePrioritizedValidationLane,
  resolvePersistedPreviewState,
} from "@/features/circuit-definition-editor/lib/preview";

export type CircuitDefinitionMutationPhase =
  | "idle"
  | "saving"
  | "publishing"
  | "cloning"
  | "deleting"
  | "success"
  | "error";

export type CircuitDefinitionDraftSurface = Readonly<{
  formattedSource: string;
  localSummary: Readonly<{
    componentCount: number;
    topologyCount: number;
    parameterCount: number;
  }>;
  localDiagnostics: ReturnType<typeof parseCircuitNetlistSource>["diagnostics"];
  blockingLocalDiagnostics: ReturnType<typeof parseCircuitNetlistSource>["diagnostics"];
  serializerBoundary: ReturnType<typeof summarizeCircuitDefinitionSerializerBoundary>;
}>;

export type CircuitDefinitionPersistedPreviewSurface = Readonly<{
  persistedPreviewState: ReturnType<typeof resolvePersistedPreviewState>;
  normalizedPreview: ReturnType<typeof buildNormalizedOutputPreview>;
  validationGroups: ReturnType<typeof partitionValidationNotices>;
  prioritizedNoticeLane: ReturnType<typeof resolvePrioritizedValidationLane>;
  normalizedOutput: string;
  validationNotices: CircuitDefinitionPersistedPreview["validation_notices"];
  validationSummary: CircuitDefinitionPersistedPreview["validation_summary"] | null;
  previewArtifacts: CircuitDefinitionPersistedPreview["preview_artifacts"];
}>;

export function isCircuitDefinitionMutationPending(
  phase: CircuitDefinitionMutationPhase,
) {
  return (
    phase === "saving" ||
    phase === "publishing" ||
    phase === "cloning" ||
    phase === "deleting"
  );
}

export function buildCircuitDefinitionDraftSurface(input: Readonly<{
  name: string;
  sourceText: string;
}>): CircuitDefinitionDraftSurface {
  const formatted = formatCircuitNetlistSource(input.sourceText, {
    canonicalName: input.name,
  });
  const localDiagnostics = formatted.diagnostics;
  const blockingLocalDiagnostics = localDiagnostics.filter(
    (diagnostic) => diagnostic.severity === "error",
  );

  return {
    formattedSource: formatted.formattedSource,
    localSummary: summarizeCircuitNetlistDocument(formatted.document),
    localDiagnostics,
    blockingLocalDiagnostics,
    serializerBoundary: summarizeCircuitDefinitionSerializerBoundary({
      name: input.name,
      sourceText: input.sourceText,
    }),
  };
}

export function buildCircuitDefinitionPersistedPreviewSurface(input: Readonly<{
  selectedDefinitionId: string | "new" | null;
  isDirty: boolean;
  mutationPhase: CircuitDefinitionMutationPhase;
  activeDefinition: CircuitDefinitionPersistedPreview | undefined;
}>): CircuitDefinitionPersistedPreviewSurface {
  const normalizedOutput = input.activeDefinition?.normalized_output ?? "{\n  \"circuit\": \"pending\"\n}";
  const validationNotices = input.activeDefinition?.validation_notices ?? [];
  const validationSummary = input.activeDefinition?.validation_summary ?? null;
  const previewArtifacts = input.activeDefinition?.preview_artifacts ?? [];
  const validationGroups = partitionValidationNotices(validationNotices);

  return {
    persistedPreviewState: resolvePersistedPreviewState({
      selectedDefinitionId: input.selectedDefinitionId,
      isDirty: input.isDirty,
      isSaving: input.mutationPhase === "saving",
      activeDefinition: input.activeDefinition,
    }),
    normalizedPreview: buildNormalizedOutputPreview(normalizedOutput),
    validationGroups,
    prioritizedNoticeLane: resolvePrioritizedValidationLane({
      selectedDefinitionId: input.selectedDefinitionId,
      isDirty: input.isDirty,
      groups: validationGroups,
    }),
    normalizedOutput,
    validationNotices,
    validationSummary,
    previewArtifacts,
  };
}
