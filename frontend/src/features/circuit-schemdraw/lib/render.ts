import { ApiError } from "@/lib/api/client";
import type { CircuitDefinitionDetail } from "@/features/circuit-definition-editor/lib/contracts";
import type {
  SchemdrawDiagnostic,
  SchemdrawLinkedSchemaSnapshot,
  SchemdrawRenderRequest,
  SchemdrawRenderResponse,
} from "@/features/circuit-schemdraw/lib/api";

export type SchemdrawEditorDraft = Readonly<{
  sourceText: string;
  relationText: string;
  documentVersion: number;
}>;

export type SchemdrawRenderPhase =
  | "idle"
  | "stale"
  | "validating"
  | "rendered"
  | "syntax_error"
  | "runtime_error"
  | "request_error";

export type SchemdrawFailureKind =
  | "relation_config"
  | "transport"
  | "backend_error"
  | "syntax_error"
  | "runtime_error";

export type SchemdrawFailureDetail = Readonly<{
  kind: SchemdrawFailureKind;
  title: string;
  userMessage: string;
  technicalMessage: string | null;
  source: SchemdrawDiagnostic["source"] | null;
  statusCode: number | null;
  errorCode: string | null;
  category: string | null;
  retryable: boolean | null;
  debugRef: string | null;
  line: number | null;
  column: number | null;
}>;

export type SchemdrawRenderSurface = Readonly<{
  phase: SchemdrawRenderPhase;
  statusLabel: string;
  diagnostics: readonly SchemdrawDiagnostic[];
  svg: string | null;
  previewMetadata: SchemdrawRenderResponse["preview_metadata"] | null;
  requestId: string | null;
  appliedDocumentVersion: number | null;
  isStale: boolean;
  failureDetail: SchemdrawFailureDetail | null;
}>;

type BuildRequestInput = Readonly<{
  activeDefinition: CircuitDefinitionDetail | undefined;
  draft: SchemdrawEditorDraft;
  renderMode: "debounced" | "manual";
  requestId: string;
}>;

export function createSchemdrawSourceTemplate(definitionName: string | null) {
  const safeName = definitionName ?? "linked_schema";
  return [
    "import schemdraw",
    "import schemdraw.elements as elm",
    "",
    "def build_drawing(relation):",
    `    title = relation.get("title", "${safeName}")`,
    "    drawing = schemdraw.Drawing()",
    "    drawing += elm.SourceSin().label(title)",
    "    drawing += elm.Line().right()",
    "    drawing += elm.Resistor().label(relation.get(\"primary_element\", \"R1\"))",
    "    drawing += elm.Line().right()",
    "    drawing += elm.Capacitor().down().label(relation.get(\"secondary_element\", \"C1\"))",
    "    return drawing",
    "",
  ].join("\n");
}

export function createRelationConfigTemplate(
  definition: CircuitDefinitionDetail | undefined,
) {
  return JSON.stringify(
    {
      title: definition?.name ?? "linked_schema",
      primary_element: definition?.normalized_output ? "Lj1" : "R1",
      secondary_element: "C1",
      labels: {},
    },
    null,
    2,
  );
}

export function ensureSchemdrawDraft(
  currentDraft: SchemdrawEditorDraft | undefined,
  definition: CircuitDefinitionDetail | undefined,
): SchemdrawEditorDraft {
  if (currentDraft) {
    return currentDraft;
  }

  return {
    sourceText: createSchemdrawSourceTemplate(definition?.name ?? null),
    relationText: createRelationConfigTemplate(definition),
    documentVersion: 1,
  };
}

export function updateSchemdrawDraft(
  draft: SchemdrawEditorDraft,
  patch: Readonly<Partial<Pick<SchemdrawEditorDraft, "sourceText" | "relationText">>>,
): SchemdrawEditorDraft {
  return {
    sourceText: patch.sourceText ?? draft.sourceText,
    relationText: patch.relationText ?? draft.relationText,
    documentVersion: draft.documentVersion + 1,
  };
}

export function parseRelationConfigText(relationText: string) {
  try {
    const parsed = JSON.parse(relationText) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {
        value: null,
        diagnostics: [
          buildClientDiagnostic(
            "schemdraw_relation_invalid",
            "Relation config must be a JSON object.",
            {
              line: 1,
              column: 1,
            },
          ),
        ],
      };
    }

    return {
      value: parsed as Record<string, unknown>,
      diagnostics: [] as readonly SchemdrawDiagnostic[],
    };
  } catch (error) {
    return {
      value: null,
      diagnostics: [
        buildClientDiagnostic("schemdraw_relation_invalid", buildRelationParseMessage(error), {
          ...resolveJsonParseLocation(relationText, error),
        }),
      ],
    };
  }
}

export function buildSchemdrawRenderRequest({
  activeDefinition,
  draft,
  renderMode,
  requestId,
}: BuildRequestInput) {
  const parsedRelation = parseRelationConfigText(draft.relationText);
  if (!parsedRelation.value) {
    return {
      request: null,
      diagnostics: parsedRelation.diagnostics,
    };
  }

  const linkedSchema: SchemdrawLinkedSchemaSnapshot | null = activeDefinition
    ? {
        definition_id: activeDefinition.definition_id,
        workspace_id: activeDefinition.workspace_id ?? null,
        name: activeDefinition.name,
        source_hash: activeDefinition.source_hash ?? null,
      }
    : null;

  const request: SchemdrawRenderRequest = {
    source_text: draft.sourceText,
    relation_config: parsedRelation.value,
    linked_schema: linkedSchema,
    document_version: draft.documentVersion,
    request_id: requestId,
    render_mode: renderMode,
  };

  return {
    request,
    diagnostics: [] as readonly SchemdrawDiagnostic[],
  };
}

export function buildRenderSurfaceFromResponse(
  response: SchemdrawRenderResponse,
  previousSurface: SchemdrawRenderSurface,
): SchemdrawRenderSurface {
  if (response.status === "rendered") {
    return {
      phase: "rendered",
      statusLabel: "Rendered",
      diagnostics: response.diagnostics,
      svg: response.svg ?? previousSurface.svg,
      previewMetadata: response.preview_metadata ?? null,
      requestId: response.request_id,
      appliedDocumentVersion: response.document_version,
      isStale: false,
      failureDetail: null,
    };
  }

  const primaryDiagnostic = response.diagnostics[0] ?? null;
  const isRelationConfigBlocked =
    response.status === "blocked" && primaryDiagnostic?.source === "relation_config";

  return {
    phase: response.status === "runtime_error" ? "runtime_error" : "syntax_error",
    statusLabel: isRelationConfigBlocked
      ? "Relation Invalid"
      : response.status === "runtime_error"
        ? "Runtime Error"
        : "Syntax Error",
    diagnostics: response.diagnostics,
    svg: previousSurface.svg,
    previewMetadata: previousSurface.previewMetadata,
    requestId: response.request_id,
    appliedDocumentVersion: previousSurface.appliedDocumentVersion,
    isStale: true,
    failureDetail: buildFailureDetailFromResponse(response),
  };
}

export function buildRenderSurfaceFromError(
  error: Error,
  previousSurface: SchemdrawRenderSurface,
): SchemdrawRenderSurface {
  const phase = resolveErrorPhase(error);

  return {
    phase,
    statusLabel: resolveErrorStatusLabel(phase),
    diagnostics: [buildDiagnosticFromError(error)],
    svg: previousSurface.svg,
    previewMetadata: previousSurface.previewMetadata,
    requestId: previousSurface.requestId,
    appliedDocumentVersion: previousSurface.appliedDocumentVersion,
    isStale: true,
    failureDetail: buildFailureDetailFromError(error),
  };
}

export function markSchemdrawPreviewStale(surface: SchemdrawRenderSurface): SchemdrawRenderSurface {
  return {
    ...surface,
    phase: surface.svg ? "stale" : "idle",
    statusLabel: surface.svg ? "Preview Stale" : "Editing",
    isStale: surface.svg !== null,
  };
}

export function createInitialRenderSurface(): SchemdrawRenderSurface {
  return {
    phase: "idle",
    statusLabel: "Idle",
    diagnostics: [],
    svg: null,
    previewMetadata: null,
    requestId: null,
    appliedDocumentVersion: null,
    isStale: false,
    failureDetail: null,
  };
}

export function buildRelationConfigFailureDetail(
  diagnostics: readonly SchemdrawDiagnostic[],
): SchemdrawFailureDetail {
  const primaryDiagnostic = diagnostics[0] ?? null;

  return {
    kind: "relation_config",
    title: "Advanced mapping is invalid",
    userMessage: "Fix the advanced relation mapping before requesting a backend render.",
    technicalMessage: primaryDiagnostic?.message ?? "Relation config validation failed.",
    source: primaryDiagnostic?.source ?? "relation_config",
    statusCode: null,
    errorCode: primaryDiagnostic?.code ?? "schemdraw_relation_invalid",
    category: "validation_error",
    retryable: false,
    debugRef: null,
    line: primaryDiagnostic?.line ?? null,
    column: primaryDiagnostic?.column ?? null,
  };
}

export function shouldApplySchemdrawResponse(
  response: SchemdrawRenderResponse,
  latestRequestId: string,
  latestDocumentVersion: number,
) {
  return (
    response.request_id === latestRequestId &&
    response.document_version === latestDocumentVersion
  );
}

function buildClientDiagnostic(
  code: string,
  message: string,
  location?: Readonly<{
    line?: number | null;
    column?: number | null;
  }>,
): SchemdrawDiagnostic {
  return {
    severity: "error",
    code,
    message,
    source: "relation_config",
    blocking: true,
    line: location?.line ?? null,
    column: location?.column ?? null,
  };
}

function buildRelationParseMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Relation config must be valid JSON before render can proceed.";
}

function buildFailureDetailFromResponse(
  response: SchemdrawRenderResponse,
): SchemdrawFailureDetail {
  const primaryDiagnostic = response.diagnostics[0] ?? null;
  const isRuntimeError = response.status === "runtime_error";
  const isRelationConfigBlocked =
    response.status === "blocked" && primaryDiagnostic?.source === "relation_config";

  return {
    kind: isRelationConfigBlocked
      ? "relation_config"
      : isRuntimeError
        ? "runtime_error"
        : "syntax_error",
    title: isRelationConfigBlocked
      ? "Backend render blocked the advanced mapping"
      : isRuntimeError
        ? "Backend render hit a runtime failure"
        : "Backend render found syntax issues",
    userMessage: isRelationConfigBlocked
      ? "The backend rejected the advanced mapping. Fix the relation config and request a new preview."
      : isRuntimeError
        ? "The backend could not complete this render. Update the source or mapping and request a new preview."
        : "The backend rejected the current source. Fix the source issues and request a new preview.",
    technicalMessage:
      primaryDiagnostic?.message ??
      (isRelationConfigBlocked
        ? "Schemdraw relation validation failed."
        : isRuntimeError
          ? "Schemdraw runtime execution failed."
          : "Schemdraw source parsing failed."),
    source:
      primaryDiagnostic?.source ??
      (isRelationConfigBlocked
        ? "relation_config"
        : isRuntimeError
          ? "render_runtime"
          : "python_syntax"),
    statusCode: null,
    errorCode:
      primaryDiagnostic?.code ??
      (isRelationConfigBlocked
        ? "schemdraw_relation_invalid"
        : isRuntimeError
          ? "schemdraw_runtime_error"
          : "schemdraw_syntax_error"),
    category: isRuntimeError ? "task_execution_failed" : "validation_error",
    retryable: false,
    debugRef: response.request_id,
    line: primaryDiagnostic?.line ?? null,
    column: primaryDiagnostic?.column ?? null,
  };
}

function buildDiagnosticFromError(error: Error): SchemdrawDiagnostic {
  if (error instanceof ApiError) {
    const details = parseApiErrorLocation(error.details);

    return {
      severity: "error",
      code: error.errorCode ?? "schemdraw_request_failed",
      message: error.message,
      source: resolveDiagnosticSourceFromErrorCode(error.errorCode),
      blocking: true,
      line: details?.line ?? null,
      column: details?.column ?? null,
    };
  }

  return {
    severity: "error",
    code: "schemdraw_request_failed",
    message: error.message,
    source: "request",
    blocking: true,
  };
}

function buildFailureDetailFromError(error: Error): SchemdrawFailureDetail {
  if (!(error instanceof ApiError)) {
    return {
      kind: "transport",
      title: "Render request could not reach the backend",
      userMessage: "The preview request did not complete. Try again when the render service is available.",
      technicalMessage: error.message,
      source: "request",
      statusCode: null,
      errorCode: null,
      category: null,
      retryable: null,
      debugRef: null,
      line: null,
      column: null,
    };
  }

  const location = parseApiErrorLocation(error.details);
  if (error.errorCode === "schemdraw_syntax_error" || error.errorCode === "schemdraw_runtime_error") {
    const isRuntimeError = error.errorCode === "schemdraw_runtime_error";
    return {
      kind: isRuntimeError ? "runtime_error" : "syntax_error",
      title: isRuntimeError ? "Backend render hit a runtime failure" : "Backend render found syntax issues",
      userMessage: isRuntimeError
        ? "The backend could not complete this render. Update the source or mapping and request a new preview."
        : "The backend rejected the current source. Fix the source issues and request a new preview.",
      technicalMessage: error.message,
      source: isRuntimeError ? "render_runtime" : "python_syntax",
      statusCode: error.status,
      errorCode: error.errorCode,
      category: error.category,
      retryable: error.retryable,
      debugRef: error.debugRef,
      line: location?.line ?? null,
      column: location?.column ?? null,
    };
  }

  if (error.status >= 400) {
    return {
      kind: "transport",
      title:
        error.status === 404
          ? "Render endpoint is unavailable"
          : "Render request could not reach the backend",
      userMessage:
        error.status === 404
          ? "The preview service is unavailable right now. Check backend availability and try again."
          : "The preview request did not complete. Try again when the render service is available.",
      technicalMessage: error.message,
      source: "request",
      statusCode: error.status,
      errorCode: error.errorCode,
      category: error.category,
      retryable: error.retryable,
      debugRef: error.debugRef,
      line: location?.line ?? null,
      column: location?.column ?? null,
    };
  }

  return {
    kind: "backend_error",
    title: "Backend rejected the render request",
    userMessage:
      error.errorCode === "schemdraw_linked_schema_not_visible"
        ? "The linked schema is not visible to the current session."
        : "The backend rejected this render request before producing a preview.",
    technicalMessage: error.message,
    source: resolveDiagnosticSourceFromErrorCode(error.errorCode),
    statusCode: error.status,
    errorCode: error.errorCode,
    category: error.category,
    retryable: error.retryable,
    debugRef: error.debugRef,
    line: location?.line ?? null,
    column: location?.column ?? null,
  };
}

function resolveErrorPhase(error: Error): SchemdrawRenderPhase {
  if (!(error instanceof ApiError)) {
    return "request_error";
  }

  if (error.errorCode === "schemdraw_syntax_error") {
    return "syntax_error";
  }

  if (error.errorCode === "schemdraw_runtime_error") {
    return "runtime_error";
  }

  return "request_error";
}

function resolveErrorStatusLabel(phase: SchemdrawRenderPhase) {
  switch (phase) {
    case "syntax_error":
      return "Syntax Error";
    case "runtime_error":
      return "Runtime Error";
    case "request_error":
    default:
      return "Render Request Failed";
  }
}

function resolveDiagnosticSourceFromErrorCode(
  errorCode: string | null,
): SchemdrawDiagnostic["source"] {
  switch (errorCode) {
    case "schemdraw_relation_invalid":
      return "relation_config";
    case "schemdraw_syntax_error":
      return "python_syntax";
    case "schemdraw_runtime_error":
      return "render_runtime";
    default:
      return "request";
  }
}

function parseApiErrorLocation(details: unknown) {
  if (!details || typeof details !== "object") {
    return null;
  }

  const candidate = details as Record<string, unknown>;
  const line = typeof candidate.line === "number" ? candidate.line : null;
  const column = typeof candidate.column === "number" ? candidate.column : null;

  if (line === null && column === null) {
    return null;
  }

  return {
    line,
    column,
  };
}

function resolveJsonParseLocation(relationText: string, error: unknown) {
  if (!(error instanceof Error)) {
    return {
      line: null,
      column: null,
    };
  }

  const lineColumnMatch = error.message.match(/line\s+(\d+)\s+column\s+(\d+)/i);
  if (lineColumnMatch) {
    return {
      line: Number.parseInt(lineColumnMatch[1] ?? "0", 10) || null,
      column: Number.parseInt(lineColumnMatch[2] ?? "0", 10) || null,
    };
  }

  const positionMatch = error.message.match(/position\s+(\d+)/i);
  if (!positionMatch) {
    return {
      line: 1,
      column: 1,
    };
  }

  const position = Number.parseInt(positionMatch[1] ?? "0", 10);
  if (!Number.isFinite(position) || position < 0) {
    return {
      line: 1,
      column: 1,
    };
  }

  const clampedText = relationText.slice(0, position);
  const lines = clampedText.split("\n");
  return {
    line: lines.length,
    column: (lines.at(-1)?.length ?? 0) + 1,
  };
}
