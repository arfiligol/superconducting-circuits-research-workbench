import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  circuitDefinitionCloneKey,
  circuitDefinitionsCatalogKey,
  circuitDefinitionDetailKey,
  circuitDefinitionsListKey,
  circuitDefinitionPublishKey,
  mapCircuitDefinitionDetailResponse,
  mapCircuitDefinitionSummaryResponse,
  unwrapCircuitDefinitionMutation,
} from "../src/features/circuit-definition-editor/lib/api";
import {
  summarizeCatalogDefinitionActionState,
  summarizeEditorDefinitionActionState,
} from "../src/features/circuit-definition-editor/lib/actions";
import {
  filterCircuitDefinitionCatalog,
} from "../src/features/circuit-definition-editor/lib/catalog";
import {
  parseDefinitionIdParam,
  resolveSelectedDefinitionId,
} from "../src/features/circuit-definition-editor/lib/definition-id";
import {
  buildCircuitDefinitionCatalogHref,
  buildCircuitDefinitionEditorHref,
} from "../src/features/circuit-definition-editor/lib/routes";
import {
  buildCircuitDefinitionDraftSurface,
  buildCircuitDefinitionPersistedPreviewSurface,
  isCircuitDefinitionMutationPending,
} from "../src/features/circuit-definition-editor/lib/editor-state";
import {
  buildCircuitDefinitionDraft,
  formatCircuitNetlistSource,
  summarizeCircuitDefinitionSerializerBoundary,
  summarizeCircuitNetlistDocument,
} from "../src/features/circuit-definition-editor/lib/netlist";
import {
  buildNormalizedOutputPreview,
  partitionValidationNotices,
  resolvePrioritizedValidationLane,
  resolvePersistedPreviewState,
} from "../src/features/circuit-definition-editor/lib/preview";

const editorWorkspaceSource = readFileSync(
  new URL("../src/features/circuit-definition-editor/components/circuit-definition-editor-workspace.tsx", import.meta.url),
  "utf8",
);
const catalogWorkspaceSource = readFileSync(
  new URL("../src/features/circuit-definition-editor/components/circuit-definition-catalog-workspace.tsx", import.meta.url),
  "utf8",
);

describe("circuit definition editor routing helpers", () => {
  const definitions = [
    {
      definition_id: 18,
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08T18:19:42Z",
      visibility_scope: "private",
      owner_display_name: "Ari",
      allowed_actions: {
        update: true,
        delete: true,
        publish: true,
        clone: true,
      },
      element_count: 0,
      validation_status: "ok",
      preview_artifact_count: 0,
    },
    {
      definition_id: 12,
      name: "FluxoniumReadoutChain",
      created_at: "2026-03-05T11:14:03Z",
      visibility_scope: "workspace",
      owner_display_name: "Ari",
      allowed_actions: {
        update: false,
        delete: false,
        publish: false,
        clone: true,
      },
      element_count: 0,
      validation_status: "ok",
      preview_artifact_count: 0,
    },
  ] as const;

  it("parses numeric and new definition query params", () => {
    expect(parseDefinitionIdParam("18")).toBe(18);
    expect(parseDefinitionIdParam("new")).toBe("new");
    expect(parseDefinitionIdParam("bad")).toBeNull();
    expect(parseDefinitionIdParam(null)).toBeNull();
  });

  it("falls back to the first definition when the selection is missing or invalid", () => {
    expect(resolveSelectedDefinitionId(null, definitions)).toBe("18");
    expect(resolveSelectedDefinitionId("999", definitions)).toBe("18");
  });

  it("preserves explicit new-draft selection and editor routes", () => {
    expect(resolveSelectedDefinitionId("new", definitions)).toBe("new");
    expect(buildCircuitDefinitionCatalogHref()).toBe("/schemas");
    expect(buildCircuitDefinitionEditorHref("new")).toBe(
      "/circuit-definition-editor?definitionId=new",
    );
    expect(buildCircuitDefinitionEditorHref(18)).toBe(
      "/circuit-definition-editor?definitionId=18",
    );
  });

  it("filters the catalog for the dedicated schemas page", () => {
    expect(
      filterCircuitDefinitionCatalog(definitions, "flux", "name").map(
        (definition) => definition.definition_id,
      ),
    ).toEqual([12]);
  });
});

describe("circuit definition editor api adapters", () => {
  it("keeps stable list, detail, publish, and clone paths", () => {
    expect(circuitDefinitionsListKey).toBe("/api/backend/circuit-definitions");
    expect(circuitDefinitionsCatalogKey).toBe(
      "/api/backend/circuit-definitions?view=authoring-catalog",
    );
    expect(circuitDefinitionDetailKey(18)).toBe("/api/backend/circuit-definitions/18");
    expect(circuitDefinitionPublishKey(18)).toBe(
      "/api/backend/circuit-definitions/18/publish",
    );
    expect(circuitDefinitionCloneKey(18)).toBe("/api/backend/circuit-definitions/18/clone");
  });

  it("maps backend summary rows without inventing preview placeholders", () => {
    expect(
      mapCircuitDefinitionSummaryResponse({
        definition_id: 18,
        name: "FloatingQubitWithXYLine",
        created_at: "2026-03-08T18:19:42Z",
        element_count: 3,
        validation_status: "warning",
        preview_artifact_count: 2,
        visibility_scope: "workspace",
        owner_display_name: "Ari",
        allowed_actions: {
          update: true,
          delete: false,
          publish: false,
          clone: true,
        },
      }),
    ).toEqual({
      definition_id: 18,
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08T18:19:42Z",
      element_count: 3,
      validation_status: "warning",
      preview_artifact_count: 2,
      visibility_scope: "workspace",
      owner_display_name: "Ari",
      allowed_actions: {
        update: true,
        delete: false,
        publish: false,
        clone: true,
      },
    });
  });

  it("maps backend detail fields and compatibility shims", () => {
    const detail = mapCircuitDefinitionDetailResponse({
      definition_id: 18,
      workspace_id: "ws_lab_a",
      visibility_scope: "private",
      lifecycle_state: "active",
      owner_user_id: "user-ari",
      owner_display_name: "Ari",
      allowed_actions: {
        update: true,
        delete: true,
        publish: true,
        clone: true,
      },
      name: "FloatingQubitWithXYLine",
      created_at: "2026-03-08T18:19:42Z",
      element_count: 2,
      validation_status: "warning",
      preview_artifact_count: 2,
      updated_at: "2026-03-15T08:10:00Z",
      concurrency_token: "etag_18_v3",
      source_hash: "sha256:definition18",
      source_text: `{
  "name": "FloatingQubitWithXYLine",
  "components": [
    { "name": "R1", "default": 50, "unit": "Ohm" },
    { "name": "C1", "default": 100, "unit": "fF" }
  ],
  "topology": [
    ["P1", "1", "0", 1],
    ["R1", "1", "0", "R1"],
    ["C1", "1", "2", "C1"]
  ]
}`,
      normalized_output:
        '{\n  "circuit": "floating_xy",\n  "elements": 2,\n  "schemdraw_ready": true\n}',
      validation_notices: [
        {
          level: "warning",
          severity: "error",
          code: "definition_source_invalid",
          message: "Topology still needs one more shunt resistor.",
          source: "backend_validator",
          blocking: true,
        },
        {
          level: "ok",
          severity: "info",
          code: "definition_ok",
          message: "Canonical serializer succeeded.",
          source: "backend_validator",
          blocking: false,
        },
      ],
      validation_summary: {
        status: "invalid",
        notice_count: 2,
        warning_count: 0,
        blocking_notice_count: 1,
      },
      preview_artifacts: ["definition.normalized.json", "definition.preview.svg"],
      lineage_parent_id: 7,
    });

    expect(detail.allowed_actions?.publish).toBe(true);
    expect(detail.validation_status).toBe("warning");
    expect(detail.preview_artifact_count).toBe(2);
    expect(detail.element_count).toBe(2);
    expect(detail.validation_notices[0]).toEqual({
      severity: "error",
      level: "warning",
      code: "definition_source_invalid",
      message: "Topology still needs one more shunt resistor.",
      source: "backend_validator",
      blocking: true,
    });
  });

  it("unwraps mutation responses into persisted detail payloads", () => {
    const detail = mapCircuitDefinitionDetailResponse({
      definition_id: 24,
      workspace_id: "ws_lab_a",
      visibility_scope: "workspace",
      lifecycle_state: "active",
      owner_user_id: "user-ari",
      owner_display_name: "Ari",
      allowed_actions: {
        update: false,
        delete: false,
        publish: false,
        clone: true,
      },
      name: "WorkspacePublishedDefinition",
      created_at: "2026-03-09T08:00:00Z",
      element_count: 0,
      validation_status: "ok",
      preview_artifact_count: 0,
      updated_at: "2026-03-15T09:00:00Z",
      concurrency_token: "etag_24_v1",
      source_hash: "sha256:definition24",
      source_text: '{\n  "name": "WorkspacePublishedDefinition",\n  "components": [],\n  "topology": []\n}',
      normalized_output: "{}",
      validation_notices: [],
      validation_summary: {
        status: "valid",
        notice_count: 0,
        warning_count: 0,
        blocking_notice_count: 0,
      },
      preview_artifacts: [],
      lineage_parent_id: null,
    });

    expect(
      unwrapCircuitDefinitionMutation({
        operation: "published",
        definition: detail,
      }),
    ).toMatchObject({
      definition_id: 24,
      visibility_scope: "workspace",
    });
  });
});

describe("circuit definition action helpers", () => {
  const persistedDefinition = {
    definition_id: 18,
    name: "FloatingQubitWithXYLine",
    created_at: "2026-03-08T18:19:42Z",
    visibility_scope: "private",
    owner_display_name: "Ari",
    allowed_actions: {
      update: true,
      delete: true,
      publish: true,
      clone: true,
    },
    element_count: 2,
    validation_status: "warning",
    preview_artifact_count: 2,
    workspace_id: "ws_lab_a",
    lifecycle_state: "active",
    owner_user_id: "user-ari",
    updated_at: "2026-03-15T09:00:00Z",
    concurrency_token: "etag_18_v3",
    source_hash: "sha256:definition18",
    source_text: '{\n  "name": "FloatingQubitWithXYLine",\n  "components": [],\n  "topology": []\n}',
    normalized_output: "{}",
    validation_notices: [],
    validation_summary: {
      status: "valid",
      notice_count: 0,
      warning_count: 0,
      blocking_notice_count: 0,
    },
    preview_artifacts: [],
    lineage_parent_id: null,
  } as const;

  it("uses backend action authority for catalog action gating", () => {
    expect(
      summarizeCatalogDefinitionActionState({
        ...persistedDefinition,
        allowed_actions: {
          update: false,
          delete: false,
          publish: false,
          clone: true,
        },
      }),
    ).toEqual({
      open: {
        enabled: true,
        reason: "Open navigates to the single active editor route.",
      },
      clone: {
        enabled: true,
        reason: "Clone is allowed by the persisted definition authority.",
      },
      publish: {
        enabled: false,
        reason: "Publish is blocked by backend definition authority.",
      },
      delete: {
        enabled: false,
        reason: "Delete is blocked by backend definition authority.",
      },
    });
  });

  it("keeps publish online-only for local definitions even when other actions remain available", () => {
    expect(
      summarizeCatalogDefinitionActionState({
        ...persistedDefinition,
        visibility_scope: "local",
        allowed_actions: {
          update: true,
          delete: true,
          publish: true,
          clone: true,
        },
      }),
    ).toMatchObject({
      publish: {
        enabled: false,
        reason:
          "Publish stays online-only. Local definitions must move through an explicit upload or import flow.",
      },
      clone: {
        enabled: true,
      },
    });

    expect(
      summarizeEditorDefinitionActionState({
        selectedDefinitionId: 18,
        activeDefinition: {
          ...persistedDefinition,
          visibility_scope: "local",
        },
        isDirty: false,
        isMutationPending: false,
        isNavigating: false,
        hasBlockingLocalDiagnostics: false,
        canManageDefinitions: true,
        runtimeMode: "local",
      }),
    ).toMatchObject({
      publish: {
        enabled: false,
        reason:
          "Publish stays online-only. Local definitions must move through an explicit upload or import flow.",
      },
    });
  });

  it("keeps draft persistence gated by backend definition capability instead of local-mode assumptions", () => {
    expect(
      summarizeEditorDefinitionActionState({
        selectedDefinitionId: "new",
        activeDefinition: undefined,
        isDirty: true,
        isMutationPending: false,
        isNavigating: false,
        hasBlockingLocalDiagnostics: false,
        canManageDefinitions: false,
        runtimeMode: "local",
      }),
    ).toMatchObject({
      save: {
        enabled: false,
        reason: "Persisting this draft is blocked by backend definition authority.",
      },
      format: {
        enabled: true,
      },
    });
  });

  it("keeps save/publish/clone/delete states distinct from format and draft state", () => {
    expect(
      summarizeEditorDefinitionActionState({
        selectedDefinitionId: 18,
        activeDefinition: persistedDefinition,
        isDirty: true,
        isMutationPending: false,
        isNavigating: false,
        hasBlockingLocalDiagnostics: false,
        canManageDefinitions: true,
        runtimeMode: "online",
      }),
    ).toMatchObject({
      format: {
        enabled: true,
      },
      save: {
        enabled: true,
      },
      publish: {
        enabled: false,
        reason: "Save or discard local edits before publishing the persisted definition.",
      },
      clone: {
        enabled: false,
        reason: "Save or discard local edits before cloning the persisted definition.",
      },
      delete: {
        enabled: true,
      },
    });

    expect(
      summarizeEditorDefinitionActionState({
        selectedDefinitionId: "new",
        activeDefinition: undefined,
        isDirty: false,
        isMutationPending: false,
        isNavigating: false,
        hasBlockingLocalDiagnostics: false,
        canManageDefinitions: true,
        runtimeMode: "online",
      }),
    ).toMatchObject({
      save: {
        enabled: false,
        reason: "Make a local change before creating a persisted definition.",
      },
      publish: {
        enabled: false,
      },
      clone: {
        enabled: false,
      },
    });
  });
});

describe("circuit definition preview helpers", () => {
  it("formats canonical netlist source and builds a save payload from it", () => {
    const formatted = formatCircuitNetlistSource(`{
      "name": "Scratch",
      "components": [
        {"name": "R1", "default": 50, "unit": "Ohm"},
        {"name": "C1", "value_ref": "Cj", "unit": "fF"}
      ],
      "parameters": [
        {"name": "Cj", "default": 100, "unit": "fF"}
      ],
      "topology": [
        ["P1", "1", "0", 1],
        ["R1", "1", "0", "R1"],
        ["C1", "1", "2", "C1"]
      ]
    }`, {
      canonicalName: "RenamedCircuit",
    });

    expect(formatted.diagnostics).toEqual([]);
    expect(summarizeCircuitNetlistDocument(formatted.document)).toEqual({
      componentCount: 2,
      topologyCount: 3,
      parameterCount: 1,
    });
    expect(
      buildCircuitDefinitionDraft({
        name: "RenamedCircuit",
        sourceText: formatted.formattedSource,
      }),
    ).toMatchObject({
      formattedSource: expect.stringContaining('"name": "RenamedCircuit"'),
      draft: {
        name: "RenamedCircuit",
      },
    });

    expect(
      buildCircuitDefinitionDraftSurface({
        name: "RenamedCircuit",
        sourceText: formatted.formattedSource,
      }),
    ).toMatchObject({
      localSummary: {
        componentCount: 2,
        topologyCount: 3,
        parameterCount: 1,
      },
      blockingLocalDiagnostics: [],
      serializerBoundary: {
        definitionName: "RenamedCircuit",
        willRewriteSourceName: false,
      },
    });
  });

  it("describes serializer rewrite, persisted preview state, validation grouping, and normalized output", () => {
    expect(
      summarizeCircuitDefinitionSerializerBoundary({
        name: "RenamedCircuit",
        sourceText:
          '{\n  "name": "LegacyName",\n  "components": [],\n  "topology": []\n}',
      }),
    ).toEqual({
      definitionName: "RenamedCircuit",
      sourceDocumentName: "LegacyName",
      canonicalSourceText:
        '{\n  "name": "RenamedCircuit",\n  "components": [],\n  "topology": []\n}',
      willRewriteSourceName: true,
      detail:
        'Format and Save will rewrite the netlist document name from "LegacyName" to "RenamedCircuit".',
    });

    expect(
      resolvePersistedPreviewState({
        selectedDefinitionId: 18,
        isDirty: false,
        isSaving: false,
        activeDefinition: {
          definition_id: 18,
          visibility_scope: "workspace",
          preview_artifact_count: 2,
          updated_at: "2026-03-15T09:00:00Z",
          normalized_output: "{\n  \"circuit\": \"floating_xy\"\n}",
          validation_notices: [],
          validation_summary: {
            status: "valid",
            notice_count: 0,
            warning_count: 0,
            blocking_notice_count: 0,
          },
          preview_artifacts: ["definition.preview.svg"],
          lineage_parent_id: 9,
        },
      }),
    ).toEqual({
      label: "Persisted Preview",
      detail:
        "Backend validation is attached to definition #18 in workspace visibility. Last updated at 2026-03-15T09:00:00Z. Derived from definition #9.",
      tone: "accent",
    });

    expect(
      buildCircuitDefinitionPersistedPreviewSurface({
        selectedDefinitionId: 18,
        isDirty: true,
        mutationPhase: "idle",
        activeDefinition: {
          definition_id: 18,
          visibility_scope: "workspace",
          updated_at: "2026-03-15T09:00:00Z",
          normalized_output: "{\n  \"circuit\": \"floating_xy\"\n}",
          validation_notices: [],
          validation_summary: {
            status: "valid",
            notice_count: 0,
            warning_count: 0,
            blocking_notice_count: 0,
          },
          preview_artifacts: ["definition.preview.svg"],
          preview_artifact_count: 1,
          lineage_parent_id: 9,
        },
      }).persistedPreviewState,
    ).toEqual({
      label: "Preview Out Of Date",
      detail: "Panels below still show the last persisted definition. Save to refresh them.",
      tone: "warning",
    });

    expect(
      partitionValidationNotices([
        {
          severity: "error",
          level: "warning",
          code: "definition_source_invalid",
          message: "Topology row is invalid.",
          source: "backend_validator",
          blocking: true,
        },
        {
          severity: "warning",
          level: "warning",
          code: "definition_warning",
          message: "Workspace publish will remove private-only state.",
          source: "backend_validator",
          blocking: false,
        },
        {
          severity: "info",
          level: "ok",
          code: "definition_ok",
          message: "Canonical serializer succeeded.",
          source: "backend_validator",
          blocking: false,
        },
      ]),
    ).toEqual({
      blocking: [
        {
          severity: "error",
          level: "warning",
          code: "definition_source_invalid",
          message: "Topology row is invalid.",
          source: "backend_validator",
          blocking: true,
        },
      ],
      warnings: [
        {
          severity: "warning",
          level: "warning",
          code: "definition_warning",
          message: "Workspace publish will remove private-only state.",
          source: "backend_validator",
          blocking: false,
        },
      ],
      checks: [
        {
          severity: "info",
          level: "ok",
          code: "definition_ok",
          message: "Canonical serializer succeeded.",
          source: "backend_validator",
          blocking: false,
        },
      ],
    });

    expect(
      resolvePrioritizedValidationLane({
        selectedDefinitionId: 18,
        isDirty: false,
        groups: {
          blocking: [
            {
              severity: "error",
              level: "warning",
              code: "definition_source_invalid",
              message: "Topology row is invalid.",
              source: "backend_validator",
              blocking: true,
            },
          ],
          warnings: [],
          checks: [],
        },
      }),
    ).toEqual({
      kind: "blocking",
      title: "Persisted Errors",
      tone: "error",
      notices: [
        {
          severity: "error",
          level: "warning",
          code: "definition_source_invalid",
          message: "Topology row is invalid.",
          source: "backend_validator",
          blocking: true,
        },
      ],
      detail:
        "Blocking backend notices are preventing this persisted schema from being treated as valid.",
    });

    expect(
      resolvePrioritizedValidationLane({
        selectedDefinitionId: "new",
        isDirty: false,
        groups: {
          blocking: [],
          warnings: [],
          checks: [],
        },
      }),
    ).toEqual({
      kind: "empty",
      title: "Persisted Notices",
      tone: "default",
      notices: [],
      detail: "Save the draft to generate persisted backend validation notices.",
    });

    expect(
      buildNormalizedOutputPreview(
        '{\n  "circuit": "fluxonium_reference_a",\n  "family": "fluxonium",\n  "elements": 12,\n  "schemdraw_ready": true\n}',
      ),
    ).toEqual({
      formattedOutput:
        '{\n  "circuit": "fluxonium_reference_a",\n  "family": "fluxonium",\n  "elements": 12,\n  "schemdraw_ready": true\n}',
      lineCount: 6,
      fieldCount: 4,
      isStructured: true,
      fields: [
        { key: "circuit", label: "Circuit", value: "fluxonium_reference_a" },
        { key: "family", label: "Family", value: "fluxonium" },
        { key: "elements", label: "Elements", value: "12" },
        { key: "schemdraw_ready", label: "Schemdraw Ready", value: "true" },
      ],
    });

    expect(
      buildNormalizedOutputPreview(
        '{\n  "source": "{\\"name\\": \\"Duplicated\\"}",\n  "expanded": {"components": 4},\n  "preview_artifacts": 2\n}',
      ),
    ).toEqual({
      formattedOutput: '{\n  "expanded": {\n    "components": 4\n  },\n  "preview_artifacts": 2\n}',
      lineCount: 6,
      fieldCount: 2,
      isStructured: true,
      fields: [
        { key: "expanded", label: "Expanded", value: '{"components":4}' },
        { key: "preview_artifacts", label: "Preview Artifacts", value: "2" },
      ],
    });

    expect(isCircuitDefinitionMutationPending("publishing")).toBe(true);
    expect(isCircuitDefinitionMutationPending("success")).toBe(false);
  });
});

describe("circuit definition workspace boundaries", () => {
  const catalogWorkspaceSource = readFileSync(
    new URL(
      "../src/features/circuit-definition-editor/components/circuit-definition-catalog-workspace.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const editorWorkspaceSource = readFileSync(
    new URL(
      "../src/features/circuit-definition-editor/components/circuit-definition-editor-workspace.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const schemasPageSource = readFileSync(
    new URL("../src/app/(workspace)/schemas/page.tsx", import.meta.url),
    "utf8",
  );
  const editorPageSource = readFileSync(
    new URL("../src/app/(workspace)/circuit-definition-editor/page.tsx", import.meta.url),
    "utf8",
  );

  it("keeps the schemas route mounted on the catalog workspace only and shows action availability", () => {
    expect(schemasPageSource).toContain("CircuitDefinitionCatalogWorkspace");
    expect(schemasPageSource).not.toContain("CircuitDefinitionEditorWorkspace");
    expect(catalogWorkspaceSource).toContain("New Circuit");
    expect(catalogWorkspaceSource).toContain("Persisted schema list");
    expect(catalogWorkspaceSource).toContain("Open");
    expect(catalogWorkspaceSource).toContain("Clone");
    expect(catalogWorkspaceSource).toContain("Publish");
    expect(catalogWorkspaceSource).toContain("ConfirmActionDialog");
    expect(catalogWorkspaceSource).not.toContain("window.confirm");
    expect(catalogWorkspaceSource).not.toContain("CodeMirror");
    expect(catalogWorkspaceSource).not.toContain("Validation & Preview");
    expect(catalogWorkspaceSource).not.toContain("disabled={isMutationPending || !canCreateDefinition}");
    expect(catalogWorkspaceSource).not.toContain("Catalog authority only");
    expect(catalogWorkspaceSource).toContain('openEditor("new")');
  });

  it("keeps the editor route responsible for source editing, serializer binding, and persisted preview", () => {
    expect(editorPageSource).toContain("CircuitDefinitionEditorWorkspace");
    expect(editorPageSource).not.toContain("CircuitDefinitionCatalogWorkspace");
    expect(editorWorkspaceSource).toContain("Active Schema");
    expect(editorWorkspaceSource).toContain("Canonical Source");
    expect(editorWorkspaceSource).toContain("Canonical Source Name");
    expect(editorWorkspaceSource).toContain("Validation & Preview");
    expect(editorWorkspaceSource).toContain("Circuit Netlist Quick Reference");
    expect(editorWorkspaceSource).toContain("Back to Schemas");
    expect(editorWorkspaceSource).toContain("Format JSON");
    expect(editorWorkspaceSource).toContain("Save");
    expect(editorWorkspaceSource).toContain("Discard");
    expect(editorWorkspaceSource).toContain("Publish");
    expect(editorWorkspaceSource).toContain("Clone");
    expect(editorWorkspaceSource).toContain("Persisted Notices");
    expect(editorWorkspaceSource).toContain("Normalized Output");
    expect(editorWorkspaceSource).toContain("Expanded");
    expect(editorWorkspaceSource).toContain("ConfirmActionDialog");
    expect(editorWorkspaceSource).not.toContain("window.confirm");
    expect(editorWorkspaceSource).not.toContain("Catalog Rail");
    expect(editorWorkspaceSource).not.toContain("Open another schema without leaving the editor workflow.");
    expect(editorWorkspaceSource).not.toContain("Local Contract Diagnostics");
    expect(editorWorkspaceSource).toContain("extensions={[json()]}");
    expect(editorWorkspaceSource).toContain("normalized JSON");
  });
});
