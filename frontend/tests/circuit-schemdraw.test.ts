import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";

import { ApiError } from "../src/lib/api/client";
import {
  parseSchemdrawDefinitionIdParam,
  resolveSchemdrawDefinitionId,
} from "../src/features/circuit-schemdraw/lib/definition-id";
import { inferSchemdrawReadiness } from "../src/features/circuit-schemdraw/lib/readiness";
import {
  buildSchemdrawStructuredPreview,
  filterAndSortSchemdrawCatalog,
  partitionSchemdrawNotices,
  pinActiveSchemdrawDefinition,
  resolveSchemdrawAttachmentState,
  resolveSchemdrawSelectionRecovery,
  summarizeSchemdrawCatalog,
} from "../src/features/circuit-schemdraw/lib/workflow";
import {
  schemdrawRenderEndpoint,
  unwrapSchemdrawRenderEnvelope,
} from "../src/features/circuit-schemdraw/lib/api";
import {
  buildSchemdrawEditorDiagnostics,
  createSchemdrawDiagnosticsExtension,
  summarizeSchemdrawEditorNotice,
} from "../src/features/circuit-schemdraw/lib/editor-diagnostics";
import {
  buildRenderSurfaceFromError,
  buildSchemdrawRenderRequest,
  buildRenderSurfaceFromResponse,
  createInitialRenderSurface,
  createRelationConfigTemplate,
  createSchemdrawSourceTemplate,
  markSchemdrawPreviewStale,
  parseRelationConfigText,
  shouldApplySchemdrawResponse,
} from "../src/features/circuit-schemdraw/lib/render";

const schemdrawWorkspaceSource = readFileSync(
  fileURLToPath(
    new URL(
      "../src/features/circuit-schemdraw/components/circuit-schemdraw-workspace.tsx",
      import.meta.url,
    ),
  ),
  "utf8",
);

describe("circuit schemdraw routing helpers", () => {
  const definitions = [
    {
      definition_id: 18,
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08 18:19:42",
      element_count: 12,
      validation_status: "warning",
      preview_artifact_count: 2,
    },
    {
      definition_id: 12,
      name: "FluxoniumReadoutChain",
      created_at: "2026-03-05 11:14:03",
      element_count: 9,
      validation_status: "warning",
      preview_artifact_count: 1,
    },
  ] as const;

  it("parses numeric ids and rejects draft-only values for schemdraw", () => {
    expect(parseSchemdrawDefinitionIdParam("18")).toBe(18);
    expect(parseSchemdrawDefinitionIdParam("new")).toBeNull();
    expect(parseSchemdrawDefinitionIdParam("bad")).toBeNull();
    expect(parseSchemdrawDefinitionIdParam(null)).toBeNull();
  });

  it("falls back to the first definition when the selection is missing or invalid", () => {
    expect(resolveSchemdrawDefinitionId(null, definitions)).toBe(18);
    expect(resolveSchemdrawDefinitionId("999", definitions)).toBe(18);
    expect(resolveSchemdrawDefinitionId("new", definitions)).toBe(18);
  });

  it("preserves a valid selected definition", () => {
    expect(resolveSchemdrawDefinitionId("12", definitions)).toBe(12);
  });

  it("supports an explicitly cleared linked schema selection", () => {
    expect(resolveSchemdrawDefinitionId(null, undefined)).toBeNull();
  });
});

describe("circuit schemdraw readiness inference", () => {
  it("marks definitions ready when normalized output advertises schemdraw readiness and warnings are absent", () => {
    const readiness = inferSchemdrawReadiness({
      definition_id: 18,
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08 18:19:42",
      element_count: 12,
      validation_status: "ok",
      preview_artifact_count: 2,
      source_text: "circuit:\n  name: fluxonium_reference_a\n",
      normalized_output:
        '{ "circuit": "fluxonium_reference_a", "elements": 3, "ports": "pending", "schemdraw_ready": true }',
      validation_notices: [{ level: "ok", message: "Canonical schema matches rewrite draft v1." }],
      validation_summary: {
        status: "ok",
        notice_count: 1,
        warning_count: 0,
      },
      preview_artifacts: ["definition.normalized.json", "schematic-input.yaml"],
    });

    expect(readiness.status).toBe("ready");
    expect(readiness.warningCount).toBe(0);
    expect(readiness.artifactCount).toBe(2);
    expect(readiness.normalizedOutput?.schemdraw_ready).toBe(true);
  });

  it("marks definitions warning when validation notices contain warnings", () => {
    const readiness = inferSchemdrawReadiness({
      definition_id: 12,
      name: "FluxoniumReadoutChain",
      created_at: "2026-03-05 11:14:03",
      element_count: 9,
      validation_status: "warning",
      preview_artifact_count: 1,
      source_text: "circuit:\n  name: fluxonium_readout_chain\n",
      normalized_output: '{ "schemdraw_ready": true }',
      validation_notices: [{ level: "warning", message: "Port mapping metadata still needs migration." }],
      validation_summary: {
        status: "warning",
        notice_count: 1,
        warning_count: 1,
      },
      preview_artifacts: ["definition.normalized.json"],
    });

    expect(readiness.status).toBe("warning");
    expect(readiness.warningCount).toBe(1);
  });

  it("returns a pending state when no definition is selected", () => {
    const readiness = inferSchemdrawReadiness(undefined);

    expect(readiness.status).toBe("pending");
    expect(readiness.label).toBe("Waiting for Definition");
  });
});

describe("circuit schemdraw workflow helpers", () => {
  const definitions = [
    {
      definition_id: 18,
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08 18:19:42",
      element_count: 12,
      validation_status: "warning",
      preview_artifact_count: 2,
    },
    {
      definition_id: 12,
      name: "FluxoniumReadoutChain",
      created_at: "2026-03-05 11:14:03",
      element_count: 9,
      validation_status: "warning",
      preview_artifact_count: 0,
    },
    {
      definition_id: 24,
      name: "TransmonControlReference",
      created_at: "2026-03-10 09:22:11",
      element_count: 7,
      validation_status: "ok",
      preview_artifact_count: 3,
    },
  ] as const;

  it("summarizes catalog readiness and artifact coverage", () => {
    expect(summarizeSchemdrawCatalog(definitions)).toEqual({
      total: 3,
      readyCount: 1,
      warningCount: 2,
      artifactBackedCount: 2,
    });
  });

  it("filters and sorts the schemdraw catalog", () => {
    const results = filterAndSortSchemdrawCatalog(definitions, {
      searchQuery: "flux",
      filter: "warning",
      sort: "name",
    });

    expect(results.map((definition) => definition.definition_id)).toEqual([12]);
  });

  it("pins the active definition when it falls out of the filtered catalog", () => {
    const filtered = filterAndSortSchemdrawCatalog(definitions, {
      searchQuery: "",
      filter: "ready",
      sort: "recent",
    });

    expect(filtered.map((definition) => definition.definition_id)).toEqual([24]);
    expect(pinActiveSchemdrawDefinition(filtered, 18)).toBe(18);
    expect(pinActiveSchemdrawDefinition(filtered, 24)).toBeNull();
  });

  it("reports invalid or missing routed selections", () => {
    expect(resolveSchemdrawSelectionRecovery("abc", 18, definitions)?.title).toBe(
      "Invalid URL selection",
    );
    expect(resolveSchemdrawSelectionRecovery("999", 18, definitions)?.title).toBe(
      "Definition not found",
    );
    expect(resolveSchemdrawSelectionRecovery(null, 18, definitions)).toBeNull();
  });

  it("builds a structured normalized output preview", () => {
    const preview = buildSchemdrawStructuredPreview(
      JSON.stringify({
        circuit: "transmon_control_reference",
        schemdraw_ready: true,
        ports: ["drive", "readout"],
        metadata: { family: "transmon" },
      }),
    );

    expect(preview.parseError).toBeNull();
    expect(preview.topLevelCount).toBe(4);
    expect(preview.rows).toEqual([
      { key: "schemdraw_ready", value: "true", tone: "success" },
      { key: "circuit", value: "transmon_control_reference", tone: "default" },
      { key: "ports", value: "2 items", tone: "default" },
      { key: "metadata", value: "1 keys", tone: "default" },
    ]);
  });

  it("partitions notices and resolves attachment state", () => {
    const notices = partitionSchemdrawNotices([
      { level: "warning", message: "Port mapping still needs migration." },
      { level: "ok", message: "Canonical schema parsed successfully." },
    ]);

    expect(notices.warnings).toHaveLength(1);
    expect(notices.checks).toHaveLength(1);
    expect(
      resolveSchemdrawAttachmentState(
        {
          definition_id: 12,
          name: "FluxoniumReadoutChain",
          created_at: "2026-03-05 11:14:03",
          element_count: 9,
          validation_status: "warning",
          preview_artifact_count: 1,
          source_text: "circuit:\n  name: fluxonium_readout_chain\n",
          normalized_output: '{ "schemdraw_ready": true }',
          validation_notices: [{ level: "warning", message: "Port mapping still needs migration." }],
          validation_summary: {
            status: "warning",
            notice_count: 1,
            warning_count: 1,
          },
          preview_artifacts: ["definition.normalized.json"],
        },
        18,
      ),
    ).toEqual({
      isAttached: false,
      isStaleSnapshot: true,
    });
  });
});

describe("circuit schemdraw render helpers", () => {
  it("keeps the documented request endpoint stable", () => {
    expect(schemdrawRenderEndpoint).toBe("/api/backend/schemdraw/render");
  });

  it("unwraps successful and failed render envelopes into the canonical frontend contract", () => {
    expect(
      unwrapSchemdrawRenderEnvelope({
        ok: true,
        data: {
          request_id: "req-9",
          document_version: 9,
          status: "rendered",
          svg: "<svg />",
          diagnostics: [],
        },
      }),
    ).toMatchObject({
      request_id: "req-9",
      document_version: 9,
    });

    expect(() =>
      unwrapSchemdrawRenderEnvelope({
        ok: false,
        error: {
          code: "schemdraw_syntax_error",
          category: "validation_error",
          message: "The Schemdraw source cannot be parsed.",
          retryable: false,
          details: {
            line: 12,
            column: 8,
          },
          debug_ref: "req-9",
        },
      }),
    ).toThrowError(ApiError);
  });

  it("builds render requests from editor drafts and linked schema context", () => {
    const request = buildSchemdrawRenderRequest({
      activeDefinition: {
        definition_id: 18,
        name: "FloatingQubitWithXYLine",
        created_at: "2026-03-08 18:19:42",
        element_count: 12,
        validation_status: "ok",
        preview_artifact_count: 2,
        source_text: "{}",
        normalized_output: "{}",
        validation_notices: [],
        validation_summary: {
          status: "ok",
          notice_count: 0,
          warning_count: 0,
        },
        preview_artifacts: [],
      },
      draft: {
        sourceText: createSchemdrawSourceTemplate("FloatingQubitWithXYLine"),
        relationText: createRelationConfigTemplate(undefined),
        documentVersion: 4,
      },
      renderMode: "manual",
      requestId: "req-4",
    });

    expect(request.diagnostics).toEqual([]);
    expect(request.request).toMatchObject({
      request_id: "req-4",
      document_version: 4,
      render_mode: "manual",
      linked_schema: {
        definition_id: 18,
        name: "FloatingQubitWithXYLine",
      },
    });
  });

  it("derives relation-config line and column for local JSON parse failures", () => {
    const relationParse = parseRelationConfigText('{\n  "title": "bad",\n  secondary_element: "C1"\n}');

    expect(relationParse.value).toBeNull();
    expect(relationParse.diagnostics).toEqual([
      expect.objectContaining({
        source: "relation_config",
        line: 3,
        blocking: true,
      }),
    ]);
  });

  it("marks the preview stale and accepts latest-only render responses", () => {
    const staleSurface = markSchemdrawPreviewStale({
      ...createInitialRenderSurface(),
      svg: "<svg />",
    });

    expect(staleSurface).toMatchObject({
      phase: "stale",
      statusLabel: "Preview Stale",
      isStale: true,
    });
    expect(shouldApplySchemdrawResponse(
      {
        request_id: "req-7",
        document_version: 7,
        status: "rendered",
        svg: "<svg />",
        diagnostics: [],
      },
      "req-7",
      7,
    )).toBe(true);
    expect(shouldApplySchemdrawResponse(
      {
        request_id: "req-6",
        document_version: 6,
        status: "rendered",
        svg: "<svg />",
        diagnostics: [],
      },
      "req-7",
      7,
    )).toBe(false);
  });

  it("keeps the previous svg when a newer response is not rendered", () => {
    expect(
      buildRenderSurfaceFromResponse(
        {
          request_id: "req-8",
          document_version: 8,
          status: "syntax_error",
          svg: null,
          diagnostics: [
            {
              severity: "error",
              code: "schemdraw_syntax_error",
              message: "Bad source",
              source: "python_syntax",
              blocking: true,
              line: 12,
              column: 4,
            },
          ],
        },
        {
          ...createInitialRenderSurface(),
          svg: "<svg>old</svg>",
          requestId: "req-5",
          appliedDocumentVersion: 5,
        },
      ),
    ).toMatchObject({
      phase: "syntax_error",
      svg: "<svg>old</svg>",
      isStale: true,
      appliedDocumentVersion: 5,
      failureDetail: {
        kind: "syntax_error",
        errorCode: "schemdraw_syntax_error",
        debugRef: "req-8",
      },
    });
  });

  it("maps api errors into diagnostics with latest backend locations", () => {
    expect(
      buildRenderSurfaceFromError(
        new ApiError("The Schemdraw source cannot be parsed.", 200, {
          errorCode: "schemdraw_syntax_error",
          category: "validation_error",
          retryable: false,
          details: {
            line: 12,
            column: 8,
          },
          debugRef: "req-14",
        }),
        {
          ...createInitialRenderSurface(),
          svg: "<svg>old</svg>",
          requestId: "req-12",
          appliedDocumentVersion: 12,
        },
      ),
    ).toMatchObject({
      phase: "syntax_error",
      statusLabel: "Syntax Error",
      svg: "<svg>old</svg>",
      failureDetail: {
        kind: "syntax_error",
        statusCode: 200,
        errorCode: "schemdraw_syntax_error",
        debugRef: "req-14",
      },
      diagnostics: [
        {
          code: "schemdraw_syntax_error",
          source: "python_syntax",
          line: 12,
          column: 8,
          blocking: true,
        },
      ],
    });
  });

  it("classifies transport failures so developer mode can surface request-level detail", () => {
    expect(
      buildRenderSurfaceFromError(
        new ApiError("Not Found", 404, {
          errorCode: null,
          category: null,
          retryable: false,
        }),
        {
          ...createInitialRenderSurface(),
          svg: "<svg>old</svg>",
          requestId: "req-18",
          appliedDocumentVersion: 18,
        },
      ),
    ).toMatchObject({
      phase: "request_error",
      failureDetail: {
        kind: "transport",
        statusCode: 404,
        title: "Render endpoint is unavailable",
      },
    });
  });

  it("splits diagnostics by editor target and summarizes editor notices", () => {
    const editorDiagnostics = buildSchemdrawEditorDiagnostics([
      {
        severity: "error",
        code: "schemdraw_syntax_error",
        message: "Bad source",
        source: "python_syntax",
        blocking: true,
        line: 12,
        column: 4,
      },
      {
        severity: "error",
        code: "schemdraw_relation_invalid",
        message: "Relation config must be valid JSON before render can proceed.",
        source: "relation_config",
        blocking: true,
        line: 3,
        column: 3,
      },
    ]);

    expect(editorDiagnostics.sourceDiagnostics).toHaveLength(1);
    expect(editorDiagnostics.relationDiagnostics).toHaveLength(1);
    expect(
      summarizeSchemdrawEditorNotice({
        diagnostics: editorDiagnostics.sourceDiagnostics,
        failureDetail: null,
        target: "source",
        developerModeEnabled: false,
      }),
    ).toEqual({
      tone: "error",
      title: "Source diagnostics",
      message: "Highlighted lines in the editor block the next backend render.",
    });
    expect(createSchemdrawDiagnosticsExtension({
      diagnostics: editorDiagnostics.sourceDiagnostics,
      developerModeEnabled: true,
    })).toBeDefined();
  });

  it("builds editor state without unsorted decoration crashes", () => {
    const extension = createSchemdrawDiagnosticsExtension({
      diagnostics: [
        {
          id: "python_syntax-line-4",
          target: "source",
          severity: "error",
          code: "schemdraw_syntax_error",
          message: "Python syntax error near the build_drawing function body.",
          source: "python_syntax",
          blocking: true,
          line: 4,
          column: 5,
        },
        {
          id: "render_runtime-line-4",
          target: "source",
          severity: "warning",
          code: "schemdraw_runtime_warning",
          message: "Secondary warning on the same line.",
          source: "render_runtime",
          blocking: false,
          line: 4,
          column: 12,
        },
      ],
      developerModeEnabled: true,
    });

    expect(() =>
      EditorState.create({
        doc: ["line 1", "line 2", "line 3", "def build_drawing(relation):", "return relation"].join("\n"),
        extensions: [extension],
      }),
    ).not.toThrow();
  });
});

describe("circuit schemdraw workspace source contracts", () => {
  it("keeps linked schema context first, editor/preview as the primary row, then diagnostics and snapshot", () => {
    const linkedIndex = schemdrawWorkspaceSource.indexOf("Linked Schema Context");
    const editorIndex = schemdrawWorkspaceSource.indexOf("Schemdraw Source Editor");
    const previewIndex = schemdrawWorkspaceSource.indexOf("SVG Live Preview");
    const diagnosticsIndex = schemdrawWorkspaceSource.indexOf("Backend Diagnostics");
    const snapshotIndex = schemdrawWorkspaceSource.indexOf("Linked Schema Snapshot");

    expect(linkedIndex).toBeGreaterThan(-1);
    expect(editorIndex).toBeGreaterThan(linkedIndex);
    expect(previewIndex).toBeGreaterThan(editorIndex);
    expect(diagnosticsIndex).toBeGreaterThan(previewIndex);
    expect(snapshotIndex).toBeGreaterThan(diagnosticsIndex);
  });

  it("demotes relation config into an advanced disclosure instead of a primary workspace card", () => {
    expect(schemdrawWorkspaceSource).toContain("Advanced relation mapping");
    expect(schemdrawWorkspaceSource).not.toContain("Relation Config Editor");
    expect(schemdrawWorkspaceSource).toContain("<details");
  });
});

describe("circuit schemdraw workspace boundaries", () => {
  const workspaceSource = readFileSync(
    new URL(
      "../src/features/circuit-schemdraw/components/circuit-schemdraw-workspace.tsx",
      import.meta.url,
    ),
    "utf8",
  );

  it("keeps schemdraw as a request-response assist surface with a clear linked-schema path", () => {
    expect(workspaceSource).toContain("No linked schema");
    expect(workspaceSource).toContain("request/response authoring assist surface");
    expect(workspaceSource).toContain("Stale preview");
    expect(workspaceSource).toContain("showDebugDisclosure");
    expect(workspaceSource).toContain("Transport failure");
    expect(workspaceSource).toContain("Debug detail");
    expect(workspaceSource).toContain("EditorHintNotice");
    expect(workspaceSource).toContain("sourceEditorExtensions");
    expect(workspaceSource).toContain("relationEditorExtensions");
    expect(workspaceSource).toContain("extensions={[sourceEditorExtensions]}");
    expect(workspaceSource).toContain("extensions={[relationEditorExtensions]}");
    expect(workspaceSource).not.toContain("Tasks Queue");
  });
});
