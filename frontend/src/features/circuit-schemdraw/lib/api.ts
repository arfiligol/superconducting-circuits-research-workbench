import { ApiError, apiRequest } from "@/lib/api/client";

export type SchemdrawDiagnostic = Readonly<{
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  source: "request" | "relation_config" | "python_syntax" | "render_runtime";
  blocking: boolean;
  line?: number | null;
  column?: number | null;
}>;

export type SchemdrawPreviewMetadata = Readonly<{
  width?: number | null;
  height?: number | null;
  view_box?: string | null;
}>;

export type SchemdrawLinkedSchemaSnapshot = Readonly<{
  definition_id: number;
  workspace_id?: string | null;
  name: string;
  source_hash?: string | null;
}>;

export type SchemdrawRenderRequest = Readonly<{
  source_text: string;
  relation_config: Record<string, unknown>;
  linked_schema?: SchemdrawLinkedSchemaSnapshot | null;
  document_version: number;
  request_id: string;
  render_mode?: "debounced" | "manual";
}>;

export type SchemdrawRenderResponse = Readonly<{
  request_id: string;
  document_version: number;
  status: "rendered" | "blocked" | "syntax_error" | "runtime_error";
  svg: string | null;
  diagnostics: readonly SchemdrawDiagnostic[];
  cursor_position?: Record<string, unknown> | null;
  probe_points?: readonly Record<string, unknown>[];
  render_time_ms?: number | null;
  preview_metadata?: SchemdrawPreviewMetadata | null;
}>;

type SchemdrawRenderEnvelope = Readonly<{
  ok: boolean;
  data?: SchemdrawRenderResponse;
  error?: Readonly<{
    code?: string;
    category?: string;
    message?: string;
    retryable?: boolean;
    details?: unknown;
    debug_ref?: string;
  }>;
}>;

export const schemdrawRenderEndpoint = "/api/backend/schemdraw/render";

export function unwrapSchemdrawRenderEnvelope(response: SchemdrawRenderEnvelope) {
  if (response.ok && response.data) {
    return response.data;
  }

  if (!response.ok && response.error) {
    throw new ApiError(
      response.error.message ?? "Schemdraw render failed.",
      200,
      {
        errorCode: response.error.code ?? "schemdraw_render_failed",
        category: response.error.category ?? "validation_error",
        retryable: response.error.retryable ?? false,
        details: response.error.details,
        debugRef: response.error.debug_ref ?? null,
      },
    );
  }

  throw new Error("Schemdraw render response did not include a data payload.");
}

export async function renderSchemdrawPreview(request: SchemdrawRenderRequest) {
  const response = await apiRequest<SchemdrawRenderEnvelope | SchemdrawRenderResponse>(
    schemdrawRenderEndpoint,
    {
      method: "POST",
      body: request,
    },
  );

  if (isSchemdrawRenderResponse(response)) {
    return response;
  }

  return unwrapSchemdrawRenderEnvelope(response);
}

function isSchemdrawRenderResponse(
  payload: SchemdrawRenderEnvelope | SchemdrawRenderResponse,
): payload is SchemdrawRenderResponse {
  return (
    typeof payload === "object" &&
    payload !== null &&
    "request_id" in payload &&
    "document_version" in payload &&
    "status" in payload
  );
}
