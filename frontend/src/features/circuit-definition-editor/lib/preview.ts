import type {
  CircuitDefinitionPersistedPreview,
  DefinitionValidationNotice,
} from "@/features/circuit-definition-editor/lib/contracts";
import { formatSchemaIdLabel } from "@/features/circuit-definition-editor/lib/schema-identity";

export type PersistedPreviewState = Readonly<{
  label: string;
  detail: string;
  tone: "default" | "warning" | "accent";
}>;

export type ValidationNoticeGroups = Readonly<{
  blocking: readonly DefinitionValidationNotice[];
  warnings: readonly DefinitionValidationNotice[];
  checks: readonly DefinitionValidationNotice[];
}>;

export type PrioritizedValidationLane = Readonly<{
  kind: "blocking" | "warning" | "checks" | "empty";
  title: string;
  tone: "error" | "warning" | "success" | "default";
  notices: readonly DefinitionValidationNotice[];
  detail: string;
}>;

export type NormalizedOutputField = Readonly<{
  key: string;
  label: string;
  value: string;
}>;

export type NormalizedOutputPreview = Readonly<{
  formattedOutput: string;
  lineCount: number;
  fieldCount: number;
  fields: readonly NormalizedOutputField[];
  isStructured: boolean;
}>;

type PreviewStateInput = Readonly<{
  selectedDefinitionId: string | "new" | null;
  isDirty: boolean;
  isSaving: boolean;
  activeDefinition: CircuitDefinitionPersistedPreview | undefined;
}>;

export function resolvePersistedPreviewState({
  selectedDefinitionId,
  isDirty,
  isSaving,
  activeDefinition,
}: PreviewStateInput): PersistedPreviewState {
  if (isSaving) {
    return {
      label: "Refreshing Preview",
      detail: "Saving the current draft and waiting for backend validation output.",
      tone: "accent",
    };
  }

  if (selectedDefinitionId === "new") {
    return {
      label: "Draft Preview",
      detail: "Save this draft to create a persisted normalized preview and validation report.",
      tone: "default",
    };
  }

  if (isDirty) {
    return {
      label: "Preview Out Of Date",
      detail: "Panels below still show the last persisted definition. Save to refresh them.",
      tone: "warning",
    };
  }

  if (activeDefinition) {
    const lineageLabel =
      typeof activeDefinition.lineage_parent_id === "string"
        ? ` Derived from ${formatSchemaIdLabel(activeDefinition.lineage_parent_id)}.`
        : "";
    return {
      label: "Persisted Preview",
      detail: `Backend validation is attached to ${formatSchemaIdLabel(activeDefinition.definition_id)} in ${activeDefinition.visibility_scope} visibility. Last updated at ${activeDefinition.updated_at}.${lineageLabel}`,
      tone: "accent",
    };
  }

  return {
    label: "Preview Pending",
    detail: "Select or save a definition to inspect its persisted preview state.",
    tone: "default",
  };
}

export function partitionValidationNotices(
  notices: readonly DefinitionValidationNotice[],
): ValidationNoticeGroups {
  return {
    blocking: notices.filter((notice) => notice.blocking || notice.severity === "error"),
    warnings: notices.filter(
      (notice) =>
        !notice.blocking &&
        (notice.severity === "warning" || notice.level === "warning"),
    ),
    checks: notices.filter(
      (notice) =>
        (!notice.severity || notice.severity === "info") &&
        (notice.level === undefined || notice.level === "ok"),
    ),
  };
}

export function resolvePrioritizedValidationLane(input: Readonly<{
  selectedDefinitionId: string | "new" | null;
  isDirty: boolean;
  groups: ValidationNoticeGroups;
}>): PrioritizedValidationLane {
  if (input.groups.blocking.length > 0) {
    return {
      kind: "blocking",
      title: "Persisted Errors",
      tone: "error",
      notices: input.groups.blocking,
      detail: "Blocking backend notices are preventing this persisted schema from being treated as valid.",
    };
  }

  if (input.groups.warnings.length > 0) {
    return {
      kind: "warning",
      title: "Persisted Warnings",
      tone: "warning",
      notices: input.groups.warnings,
      detail: "No blocking errors were returned, but backend warnings still need review.",
    };
  }

  if (input.groups.checks.length > 0) {
    return {
      kind: "checks",
      title: "Persisted Checks",
      tone: "success",
      notices: input.groups.checks,
      detail: "Persisted backend checks are currently clean.",
    };
  }

  if (input.selectedDefinitionId === "new") {
    return {
      kind: "empty",
      title: "Persisted Notices",
      tone: "default",
      notices: [],
      detail: "Save the draft to generate persisted backend validation notices.",
    };
  }

  if (input.isDirty) {
    return {
      kind: "empty",
      title: "Persisted Notices",
      tone: "default",
      notices: [],
      detail: "Save the current draft to refresh the persisted validation report.",
    };
  }

  return {
    kind: "empty",
    title: "Persisted Notices",
    tone: "default",
    notices: [],
    detail: "No persisted validation notices were returned for this definition.",
  };
}

export function buildNormalizedOutputPreview(
  normalizedOutput: string,
): NormalizedOutputPreview {
  const formattedOutput = normalizedOutput.trim().length > 0 ? normalizedOutput : "{}";
  const lineCount = formattedOutput.split(/\r?\n/).length;

  try {
    const parsed = JSON.parse(formattedOutput) as Record<string, unknown>;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error("normalized output is not a JSON object");
    }

    const visiblePreviewObject = omitPreviewOnlyKeys(parsed);
    const fields = Object.entries(visiblePreviewObject).map(([key, value]) => ({
      key,
      label: humanizePreviewKey(key),
      value: formatPreviewValue(value),
    }));
    const sanitizedOutput = JSON.stringify(visiblePreviewObject, null, 2);

    return {
      formattedOutput: sanitizedOutput,
      lineCount: sanitizedOutput.split(/\r?\n/).length,
      fieldCount: fields.length,
      fields,
      isStructured: true,
    };
  } catch {
    return {
      formattedOutput,
      lineCount,
      fieldCount: 0,
      fields: [],
      isStructured: false,
    };
  }
}

function formatPreviewValue(value: unknown): string {
  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`;
  }

  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function humanizePreviewKey(key: string): string {
  return key
    .split("_")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function omitPreviewOnlyKeys(
  parsed: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(parsed).filter(([key]) => key !== "source"),
  );
}
