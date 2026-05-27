import type {
  CircuitDefinitionDetail,
  DefinitionValidationNotice,
} from "@/features/circuit-definition-editor/lib/contracts";

type NormalizedOutputSnapshot = Readonly<{
  circuit?: string;
  elements?: number;
  ports?: string;
  schemdraw_ready?: boolean;
}>;

export type SchemdrawReadiness = Readonly<{
  status: "ready" | "warning" | "pending";
  label: string;
  summary: string;
  warningCount: number;
  noticeCount: number;
  artifactCount: number;
  normalizedOutput: NormalizedOutputSnapshot | null;
}>;

function countWarnings(notices: readonly DefinitionValidationNotice[]) {
  return notices.filter((notice) => notice.level === "warning").length;
}

function parseNormalizedOutput(value: string): NormalizedOutputSnapshot | null {
  try {
    const parsedValue = JSON.parse(value) as unknown;
    if (parsedValue && typeof parsedValue === "object" && !Array.isArray(parsedValue)) {
      return parsedValue as NormalizedOutputSnapshot;
    }
  } catch {
    // keep null when normalized output is not valid JSON
  }

  return null;
}

export function inferSchemdrawReadiness(
  definition: CircuitDefinitionDetail | undefined,
): SchemdrawReadiness {
  if (!definition) {
    return {
      status: "pending",
      label: "Waiting for Definition",
      summary: "Select a canonical circuit definition to inspect schemdraw readiness.",
      warningCount: 0,
      noticeCount: 0,
      artifactCount: 0,
      normalizedOutput: null,
    };
  }

  const normalizedOutput = parseNormalizedOutput(definition.normalized_output);
  const warningCount = countWarnings(definition.validation_notices);
  const noticeCount = definition.validation_notices.length;
  const artifactCount = definition.preview_artifacts.length;
  const schematicReady = normalizedOutput?.schemdraw_ready === true;

  if (warningCount > 0) {
    return {
      status: "warning",
      label: "Migration Warnings",
      summary:
        "Validation notices still block a clean schemdraw handoff. Review the warning panel before trusting the preview contract.",
      warningCount,
      noticeCount,
      artifactCount,
      normalizedOutput,
    };
  }

  if (schematicReady) {
    return {
      status: "ready",
      label: "Schematic-Ready",
      summary:
        "The normalized output advertises schemdraw readiness and no validation warnings are present in the canonical definition.",
      warningCount,
      noticeCount,
      artifactCount,
      normalizedOutput,
    };
  }

  return {
    status: "pending",
    label: "Readiness Pending",
    summary:
      "The current detail contract does not yet confirm a schemdraw-ready state. Use the normalized output and artifacts as the migration source of truth.",
    warningCount,
    noticeCount,
    artifactCount,
    normalizedOutput,
  };
}
