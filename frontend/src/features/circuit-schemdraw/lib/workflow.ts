import type {
  CircuitDefinitionDetail,
  CircuitDefinitionSummary,
  DefinitionValidationNotice,
} from "@/features/circuit-definition-editor/lib/contracts";
import {
  formatSchemaIdLabel,
  matchesSchemaIdQuery,
  type CircuitDefinitionId,
} from "@/features/circuit-definition-editor/lib/schema-identity";
import { parseSchemdrawDefinitionIdParam } from "@/features/circuit-schemdraw/lib/definition-id";

export type SchemdrawCatalogFilter = "all" | "ready" | "warning" | "artifacts";
export type SchemdrawCatalogSortMode = "recent" | "name" | "warnings";
export type SchemdrawPreviewMode = "structured" | "json";

export type SchemdrawCatalogSummary = Readonly<{
  total: number;
  readyCount: number;
  warningCount: number;
  artifactBackedCount: number;
}>;

export type SchemdrawSelectionRecovery = Readonly<{
  tone: "default" | "warning";
  title: string;
  message: string;
}> | null;

export type SchemdrawStructuredPreviewRow = Readonly<{
  key: string;
  value: string;
  tone: "default" | "primary" | "success";
}>;

export type SchemdrawStructuredPreview = Readonly<{
  rows: readonly SchemdrawStructuredPreviewRow[];
  topLevelCount: number;
  formattedJson: string;
  parseError: string | null;
}>;

export type PartitionedSchemdrawNotices = Readonly<{
  warnings: readonly DefinitionValidationNotice[];
  checks: readonly DefinitionValidationNotice[];
}>;

type FilterCatalogOptions = Readonly<{
  searchQuery: string;
  filter: SchemdrawCatalogFilter;
  sort: SchemdrawCatalogSortMode;
}>;

const previewPriorityKeys = [
  "schemdraw_ready",
  "circuit",
  "name",
  "family",
  "elements",
  "ports",
  "connections",
  "nodes",
] as const;

function compareDefinitionsByCreatedAt(
  left: CircuitDefinitionSummary,
  right: CircuitDefinitionSummary,
) {
  return right.created_at.localeCompare(left.created_at);
}

function compareDefinitionsByWarnings(
  left: CircuitDefinitionSummary,
  right: CircuitDefinitionSummary,
) {
  const leftScore = left.validation_status === "warning" ? 1 : 0;
  const rightScore = right.validation_status === "warning" ? 1 : 0;
  return rightScore - leftScore || compareDefinitionsByCreatedAt(left, right);
}

function summarizePreviewValue(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (value === null) {
    return "null";
  }

  if (Array.isArray(value)) {
    return `${value.length} items`;
  }

  if (value && typeof value === "object") {
    return `${Object.keys(value).length} keys`;
  }

  return "unknown";
}

function toneForPreviewValue(key: string, value: unknown): SchemdrawStructuredPreviewRow["tone"] {
  if (key === "schemdraw_ready" && value === true) {
    return "success";
  }

  if (key === "schemdraw_ready") {
    return "primary";
  }

  return "default";
}

function parseNormalizedObject(normalizedOutput: string): Record<string, unknown> | null {
  try {
    const parsedValue = JSON.parse(normalizedOutput) as unknown;
    if (parsedValue && typeof parsedValue === "object" && !Array.isArray(parsedValue)) {
      return parsedValue as Record<string, unknown>;
    }
  } catch {
    return null;
  }

  return null;
}

function matchesCatalogFilter(
  definition: CircuitDefinitionSummary,
  filter: SchemdrawCatalogFilter,
) {
  switch (filter) {
    case "ready":
      return (
        definition.validation_status === "ok" && definition.preview_artifact_count > 0
      );
    case "warning":
      return definition.validation_status === "warning";
    case "artifacts":
      return definition.preview_artifact_count > 0;
    case "all":
    default:
      return true;
  }
}

export function summarizeSchemdrawCatalog(
  definitions: readonly CircuitDefinitionSummary[] | undefined,
): SchemdrawCatalogSummary {
  const items = definitions ?? [];

  return {
    total: items.length,
    readyCount: items.filter(
      (definition) =>
        definition.validation_status === "ok" && definition.preview_artifact_count > 0,
    ).length,
    warningCount: items.filter((definition) => definition.validation_status === "warning").length,
    artifactBackedCount: items.filter((definition) => definition.preview_artifact_count > 0).length,
  };
}

export function filterAndSortSchemdrawCatalog(
  definitions: readonly CircuitDefinitionSummary[] | undefined,
  options: FilterCatalogOptions,
) {
  const normalizedQuery = options.searchQuery.trim().toLowerCase();
  const items = (definitions ?? []).filter((definition) => {
    if (!matchesCatalogFilter(definition, options.filter)) {
      return false;
    }

    if (!normalizedQuery) {
      return true;
    }

    return (
      definition.name.toLowerCase().includes(normalizedQuery) ||
      matchesSchemaIdQuery(definition.definition_id, normalizedQuery)
    );
  });

  const sortedItems = [...items];
  sortedItems.sort((left, right) => {
    switch (options.sort) {
      case "name":
        return left.name.localeCompare(right.name) || compareDefinitionsByCreatedAt(left, right);
      case "warnings":
        return compareDefinitionsByWarnings(left, right);
      case "recent":
      default:
        return compareDefinitionsByCreatedAt(left, right);
    }
  });

  return sortedItems;
}

export function resolveSchemdrawSelectionRecovery(
  requestedDefinitionId: string | null,
  resolvedDefinitionId: CircuitDefinitionId | null,
  definitions: readonly CircuitDefinitionSummary[] | undefined,
): SchemdrawSelectionRecovery {
  if (!definitions || definitions.length === 0 || resolvedDefinitionId === null) {
    return null;
  }

  if (requestedDefinitionId === null) {
    return null;
  }

  const parsedDefinitionId = parseSchemdrawDefinitionIdParam(requestedDefinitionId);
  if (parsedDefinitionId === null) {
    return {
      tone: "warning",
      title: "Invalid URL selection",
      message: `The URL selection "${requestedDefinitionId}" is not a canonical schema ID. Showing ${formatSchemaIdLabel(resolvedDefinitionId)} instead.`,
    };
  }

  const definitionExists = definitions.some(
    (definition) => definition.definition_id === parsedDefinitionId,
  );
  if (!definitionExists) {
    return {
      tone: "warning",
      title: "Definition not found",
      message: `${formatSchemaIdLabel(parsedDefinitionId)} is not available in the current catalog. Reattached to ${formatSchemaIdLabel(resolvedDefinitionId)}.`,
    };
  }

  return null;
}

export function partitionSchemdrawNotices(
  notices: readonly DefinitionValidationNotice[],
): PartitionedSchemdrawNotices {
  return {
    warnings: notices.filter((notice) => notice.level === "warning"),
    checks: notices.filter((notice) => notice.level === "ok"),
  };
}

export function buildSchemdrawStructuredPreview(
  normalizedOutput: string,
): SchemdrawStructuredPreview {
  const parsedObject = parseNormalizedObject(normalizedOutput);
  if (!parsedObject) {
    return {
      rows: [],
      topLevelCount: 0,
      formattedJson: normalizedOutput,
      parseError: "Normalized output is not valid JSON.",
    };
  }

  const prioritizedKeys = previewPriorityKeys.filter((key) => key in parsedObject);
  const remainingKeys = Object.keys(parsedObject)
    .filter((key) => !previewPriorityKeys.includes(key as (typeof previewPriorityKeys)[number]))
    .sort((left, right) => left.localeCompare(right));
  const orderedKeys = [...prioritizedKeys, ...remainingKeys];
  const rows = orderedKeys.slice(0, 8).map((key) => ({
    key,
    value: summarizePreviewValue(parsedObject[key]),
    tone: toneForPreviewValue(key, parsedObject[key]),
  }));

  return {
    rows,
    topLevelCount: Object.keys(parsedObject).length,
    formattedJson: JSON.stringify(parsedObject, null, 2),
    parseError: null,
  };
}

export function pinActiveSchemdrawDefinition(
  filteredDefinitions: readonly CircuitDefinitionSummary[],
  activeDefinitionId: CircuitDefinitionId | null,
) {
  if (activeDefinitionId === null) {
    return null;
  }

  return filteredDefinitions.some((definition) => definition.definition_id === activeDefinitionId)
    ? null
    : activeDefinitionId;
}

export function resolveSchemdrawAttachmentState(
  activeDefinition: CircuitDefinitionDetail | undefined,
  resolvedDefinitionId: CircuitDefinitionId | null,
) {
  if (resolvedDefinitionId === null) {
    return {
      isAttached: false,
      isStaleSnapshot: false,
    };
  }

  return {
    isAttached: activeDefinition?.definition_id === resolvedDefinitionId,
    isStaleSnapshot:
      typeof activeDefinition?.definition_id === "string" &&
      activeDefinition.definition_id !== resolvedDefinitionId,
  };
}
