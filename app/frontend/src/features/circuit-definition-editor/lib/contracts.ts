import type { components } from "@/lib/api/generated/schema";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

export type CircuitDefinitionAllowedActions = Readonly<{
  update: boolean;
  delete: boolean;
  publish: boolean;
  clone: boolean;
}>;

export type CircuitDefinitionVisibilityScope = "local" | "private" | "workspace";
export type CircuitDefinitionLifecycleState = "active" | "archived" | "deleted";
export type CircuitDefinitionValidationStatus = "valid" | "warning" | "invalid" | "ok";
export type CircuitDefinitionCompatibilityValidationStatus =
  components["schemas"]["CircuitDefinitionSummaryResponse"]["validation_status"];

type GeneratedCircuitDefinitionCreateRequest =
  components["schemas"]["CircuitDefinitionCreateRequest"];
type GeneratedCircuitDefinitionUpdateRequest =
  components["schemas"]["CircuitDefinitionUpdateRequest"];
type GeneratedCircuitDefinitionSummaryResponse =
  components["schemas"]["CircuitDefinitionSummaryResponse"];
type GeneratedCircuitDefinitionDetailResponse =
  components["schemas"]["CircuitDefinitionDetailResponse"];
type GeneratedValidationNoticeResponse = components["schemas"]["ValidationNoticeResponse"];
type GeneratedValidationSummaryResponse =
  components["schemas"]["CircuitDefinitionValidationSummaryResponse"];

export type CircuitDefinitionSummaryResponse = GeneratedCircuitDefinitionSummaryResponse &
  Readonly<{
    visibility_scope: CircuitDefinitionVisibilityScope;
    owner_display_name: string;
    allowed_actions: CircuitDefinitionAllowedActions;
  }>;

export type DefinitionValidationNoticeResponse = Omit<
  GeneratedValidationNoticeResponse,
  never
> &
  Readonly<{
    severity: "error" | "warning" | "info";
    code: string;
    source: string;
    blocking: boolean;
  }>;

export type CircuitDefinitionValidationSummaryResponse = Omit<
  GeneratedValidationSummaryResponse,
  "status"
> &
  Readonly<{
    status: CircuitDefinitionValidationStatus;
    blocking_notice_count?: number;
  }>;

export type CircuitDefinitionDetailResponse = Omit<
  GeneratedCircuitDefinitionDetailResponse,
  "validation_notices" | "validation_summary" | "preview_artifacts"
> &
  Readonly<{
    workspace_id: string;
    visibility_scope: CircuitDefinitionVisibilityScope;
    lifecycle_state: CircuitDefinitionLifecycleState;
    owner_user_id: string;
    owner_display_name: string;
    updated_at: string;
    concurrency_token: string;
    source_hash: string;
    allowed_actions: CircuitDefinitionAllowedActions;
    validation_notices: readonly DefinitionValidationNoticeResponse[];
    validation_summary: CircuitDefinitionValidationSummaryResponse;
    preview_artifacts: readonly string[];
    lineage_parent_id: CircuitDefinitionId | null;
  }>;

export type DefinitionValidationNotice = Readonly<{
  level?: GeneratedValidationNoticeResponse["level"];
  message: string;
  severity?: DefinitionValidationNoticeResponse["severity"];
  code?: string;
  source?: string;
  blocking?: boolean;
}>;

export type CircuitDefinitionValidationSummary = Readonly<{
  status: CircuitDefinitionValidationStatus;
  notice_count: number;
  warning_count: number;
  blocking_notice_count?: number;
}>;

export type CircuitDefinitionSummary = GeneratedCircuitDefinitionSummaryResponse &
  Readonly<{
    visibility_scope?: CircuitDefinitionVisibilityScope;
    owner_display_name?: string;
    allowed_actions?: CircuitDefinitionAllowedActions;
  }>;

export type CircuitDefinitionDetail = CircuitDefinitionSummary &
  Readonly<{
    workspace_id?: string;
    lifecycle_state?: CircuitDefinitionLifecycleState;
    owner_user_id?: string;
    updated_at?: string;
    concurrency_token?: string;
    source_hash?: string;
    source_text: string;
    normalized_output: string;
    validation_notices: readonly DefinitionValidationNotice[];
    validation_summary: CircuitDefinitionValidationSummary;
    preview_artifacts: readonly string[];
    lineage_parent_id?: CircuitDefinitionId | null;
  }>;

export type CircuitDefinitionPersistedPreview = Pick<
  CircuitDefinitionDetail,
  | "definition_id"
  | "visibility_scope"
  | "updated_at"
  | "normalized_output"
  | "validation_notices"
  | "validation_summary"
  | "preview_artifacts"
  | "preview_artifact_count"
  | "lineage_parent_id"
>;

export type CircuitDefinitionCreateDraft = GeneratedCircuitDefinitionCreateRequest &
  Readonly<{
    visibility_scope?: CircuitDefinitionVisibilityScope;
  }>;

export type CircuitDefinitionUpdateDraft = Readonly<{
  source_text: GeneratedCircuitDefinitionUpdateRequest["source_text"];
  name?: GeneratedCircuitDefinitionUpdateRequest["name"];
  concurrency_token?: string;
}>;

export type CircuitDefinitionCloneDraft = Readonly<{
  name?: string;
}>;

export type CircuitDefinitionDraft = CircuitDefinitionCreateDraft;

export type CircuitDefinitionMutationOperation =
  | "created"
  | "updated"
  | "published"
  | "cloned";

export type CircuitDefinitionMutationResponse = Readonly<{
  operation: CircuitDefinitionMutationOperation;
  definition: CircuitDefinitionDetail;
}>;

export type CircuitDefinitionMutationEnvelopeResponse = Readonly<{
  operation: CircuitDefinitionMutationOperation;
  definition: CircuitDefinitionDetailResponse;
}>;

export type CircuitDefinitionDeleteResponse = Readonly<{
  operation: "deleted";
  definition_id: CircuitDefinitionId;
}>;

export type CircuitDefinitionCatalogResponse = Readonly<{
  rows: readonly CircuitDefinitionSummary[];
  total_count: number;
}>;

export type CircuitDefinitionCatalogEnvelopeResponse = Readonly<{
  rows: readonly CircuitDefinitionSummaryResponse[];
  total_count: number;
}>;

export type CircuitDefinitionCatalogMeta = Readonly<{
  generated_at?: string;
  limit?: number;
  next_cursor?: string | null;
  prev_cursor?: string | null;
  has_more?: boolean;
  filter_echo?: Readonly<Record<string, unknown>>;
}>;
