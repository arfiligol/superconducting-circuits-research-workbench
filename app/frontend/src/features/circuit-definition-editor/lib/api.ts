import { apiRequest, apiRequestEnvelope } from "@/lib/api/client";

import type {
  CircuitDefinitionCatalogEnvelopeResponse,
  CircuitDefinitionCatalogMeta,
  CircuitDefinitionCatalogResponse,
  CircuitDefinitionCloneDraft,
  CircuitDefinitionCompatibilityValidationStatus,
  CircuitDefinitionCreateDraft,
  CircuitDefinitionDeleteResponse,
  CircuitDefinitionDetail,
  CircuitDefinitionDetailResponse,
  CircuitDefinitionMutationResponse,
  CircuitDefinitionMutationEnvelopeResponse,
  CircuitDefinitionSummary,
  CircuitDefinitionSummaryResponse,
  CircuitDefinitionUpdateDraft,
  DefinitionValidationNotice,
  DefinitionValidationNoticeResponse,
} from "@/features/circuit-definition-editor/lib/contracts";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

function toCompatibilityValidationStatus(
  status: CircuitDefinitionDetailResponse["validation_summary"]["status"],
): CircuitDefinitionCompatibilityValidationStatus {
  return status === "warning" || status === "invalid" ? "warning" : "ok";
}

function mapValidationNotice(
  notice: DefinitionValidationNoticeResponse,
): DefinitionValidationNotice {
  return {
    severity: notice.severity,
    level: notice.severity === "warning" || notice.severity === "error" ? "warning" : "ok",
    code: notice.code,
    message: notice.message,
    source: notice.source,
    blocking: notice.blocking,
  };
}

export function mapCircuitDefinitionSummaryResponse(
  response: CircuitDefinitionSummaryResponse,
): CircuitDefinitionSummary {
  return {
    definition_id: response.definition_id,
    name: response.name,
    created_at: response.created_at,
    visibility_scope: response.visibility_scope,
    owner_display_name: response.owner_display_name,
    allowed_actions: {
      update: response.allowed_actions.update,
      delete: response.allowed_actions.delete,
      publish: response.allowed_actions.publish,
      clone: response.allowed_actions.clone,
    },
    element_count: response.element_count,
    validation_status: response.validation_status,
    preview_artifact_count: response.preview_artifact_count,
  };
}

export function mapCircuitDefinitionDetailResponse(
  response: CircuitDefinitionDetailResponse,
): CircuitDefinitionDetail {
  return {
    ...mapCircuitDefinitionSummaryResponse(response),
    workspace_id: response.workspace_id,
    lifecycle_state: response.lifecycle_state,
    owner_user_id: response.owner_user_id,
    updated_at: response.updated_at,
    concurrency_token: response.concurrency_token,
    source_hash: response.source_hash,
    source_text: response.source_text,
    normalized_output: response.normalized_output,
    validation_notices: response.validation_notices.map(mapValidationNotice),
    validation_summary: {
      status: response.validation_summary.status,
      notice_count: response.validation_summary.notice_count,
      warning_count: response.validation_summary.warning_count,
      blocking_notice_count: response.validation_summary.blocking_notice_count,
    },
    preview_artifacts: [...response.preview_artifacts],
    lineage_parent_id: response.lineage_parent_id,
    validation_status: toCompatibilityValidationStatus(response.validation_summary.status),
  };
}

export const circuitDefinitionsListKey = "/api/backend/circuit-definitions";
export const circuitDefinitionsCatalogKey = `${circuitDefinitionsListKey}?view=authoring-catalog`;

export function circuitDefinitionDetailKey(definitionId: CircuitDefinitionId) {
  return `/api/backend/circuit-definitions/${definitionId}`;
}

export function circuitDefinitionPublishKey(definitionId: CircuitDefinitionId) {
  return `${circuitDefinitionDetailKey(definitionId)}/publish`;
}

export function circuitDefinitionCloneKey(definitionId: CircuitDefinitionId) {
  return `${circuitDefinitionDetailKey(definitionId)}/clone`;
}

export function unwrapCircuitDefinitionMutation(
  response: CircuitDefinitionMutationResponse,
): CircuitDefinitionDetail {
  return response.definition;
}

export async function listCircuitDefinitionsCatalog(): Promise<
  Readonly<{
    catalog: CircuitDefinitionCatalogResponse;
    meta: CircuitDefinitionCatalogMeta | undefined;
  }>
> {
  const response = await apiRequestEnvelope<
    CircuitDefinitionCatalogEnvelopeResponse,
    CircuitDefinitionCatalogMeta
  >(circuitDefinitionsListKey);

  return {
    catalog: {
      rows: response.data.rows.map(mapCircuitDefinitionSummaryResponse),
      total_count: response.data.total_count,
    },
    meta: response.meta,
  };
}

export async function listCircuitDefinitions(): Promise<readonly CircuitDefinitionSummary[]> {
  const response = await listCircuitDefinitionsCatalog();
  return response.catalog.rows;
}

export async function getCircuitDefinition(definitionId: CircuitDefinitionId) {
  const response = await apiRequest<CircuitDefinitionDetailResponse>(
    circuitDefinitionDetailKey(definitionId),
  );
  return mapCircuitDefinitionDetailResponse(response);
}

export async function createCircuitDefinition(payload: CircuitDefinitionCreateDraft) {
  const response = await apiRequest<CircuitDefinitionMutationEnvelopeResponse>(
    circuitDefinitionsListKey,
    {
      method: "POST",
      body: payload,
    },
  );

  return unwrapCircuitDefinitionMutation({
    operation: response.operation,
    definition: mapCircuitDefinitionDetailResponse(response.definition),
  });
}

export async function updateCircuitDefinition(
  definitionId: CircuitDefinitionId,
  payload: CircuitDefinitionUpdateDraft,
) {
  const response = await apiRequest<CircuitDefinitionMutationEnvelopeResponse>(
    circuitDefinitionDetailKey(definitionId),
    {
      method: "PUT",
      body: payload,
    },
  );

  return unwrapCircuitDefinitionMutation({
    operation: response.operation,
    definition: mapCircuitDefinitionDetailResponse(response.definition),
  });
}

export async function publishCircuitDefinition(definitionId: CircuitDefinitionId) {
  const response = await apiRequest<CircuitDefinitionMutationEnvelopeResponse>(
    circuitDefinitionPublishKey(definitionId),
    {
      method: "POST",
    },
  );

  return unwrapCircuitDefinitionMutation({
    operation: response.operation,
    definition: mapCircuitDefinitionDetailResponse(response.definition),
  });
}

export async function cloneCircuitDefinition(
  definitionId: CircuitDefinitionId,
  payload?: CircuitDefinitionCloneDraft,
) {
  const response = await apiRequest<CircuitDefinitionMutationEnvelopeResponse>(
    circuitDefinitionCloneKey(definitionId),
    {
      method: "POST",
      body: payload ?? null,
    },
  );

  return unwrapCircuitDefinitionMutation({
    operation: response.operation,
    definition: mapCircuitDefinitionDetailResponse(response.definition),
  });
}

export async function deleteCircuitDefinition(definitionId: CircuitDefinitionId) {
  return apiRequest<CircuitDefinitionDeleteResponse>(circuitDefinitionDetailKey(definitionId), {
    method: "DELETE",
  });
}
