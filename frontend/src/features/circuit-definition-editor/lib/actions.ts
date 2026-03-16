import type {
  CircuitDefinitionDetail,
  CircuitDefinitionSummary,
} from "@/features/circuit-definition-editor/lib/contracts";

export type CircuitDefinitionActionState = Readonly<{
  enabled: boolean;
  reason: string;
}>;

export type CircuitDefinitionCatalogActionState = Readonly<{
  open: CircuitDefinitionActionState;
  clone: CircuitDefinitionActionState;
  publish: CircuitDefinitionActionState;
  delete: CircuitDefinitionActionState;
}>;

export type CircuitDefinitionEditorActionState = Readonly<{
  format: CircuitDefinitionActionState;
  save: CircuitDefinitionActionState;
  discard: CircuitDefinitionActionState;
  delete: CircuitDefinitionActionState;
  publish: CircuitDefinitionActionState;
  clone: CircuitDefinitionActionState;
}>;

function allowed(message: string): CircuitDefinitionActionState {
  return {
    enabled: true,
    reason: message,
  };
}

function blocked(message: string): CircuitDefinitionActionState {
  return {
    enabled: false,
    reason: message,
  };
}

export function summarizeCatalogDefinitionActionState(
  definition: CircuitDefinitionSummary,
): CircuitDefinitionCatalogActionState {
  const allowedActions = definition.allowed_actions;
  return {
    open: allowed("Open navigates to the single active editor route."),
    clone: allowedActions?.clone
      ? allowed("Clone is allowed by the persisted definition authority.")
      : blocked("Clone is blocked by backend definition authority."),
    publish: definition.visibility_scope === "local"
      ? blocked("Publish stays online-only. Local definitions must move through an explicit upload or import flow.")
      : allowedActions?.publish
      ? allowed("Publish is allowed for this persisted definition.")
      : blocked("Publish is blocked by backend definition authority."),
    delete: allowedActions?.delete
      ? allowed("Delete is allowed for this persisted definition.")
      : blocked("Delete is blocked by backend definition authority."),
  };
}

export function summarizeEditorDefinitionActionState(input: Readonly<{
  selectedDefinitionId: number | "new" | null;
  activeDefinition: CircuitDefinitionDetail | undefined;
  isDirty: boolean;
  isMutationPending: boolean;
  isNavigating: boolean;
  hasBlockingLocalDiagnostics: boolean;
  canManageDefinitions: boolean;
  runtimeMode: "local" | "online";
}>): CircuitDefinitionEditorActionState {
  const isBusy = input.isMutationPending || input.isNavigating;

  const format = isBusy
    ? blocked("Format waits until the current save or route transition finishes.")
    : allowed("Format rewrites the local draft only. It never saves implicitly.");

  const discard =
    input.isDirty && !isBusy
      ? allowed("Discard rebinds the editor back to the last persisted source.")
      : blocked("Discard is only available when the local draft differs from persisted source.");

  if (input.selectedDefinitionId === "new" || !input.activeDefinition) {
    return {
      format,
      save:
        isBusy
          ? blocked("Save waits until the current save or route transition finishes.")
          : !input.canManageDefinitions
            ? blocked("Persisting this draft is blocked by backend definition authority.")
          : input.hasBlockingLocalDiagnostics
            ? blocked("Fix blocking local diagnostics before creating a persisted definition.")
            : input.isDirty
              ? allowed("Create persists this draft as a new definition and binds preview to it.")
              : blocked("Make a local change before creating a persisted definition."),
      discard,
      delete: blocked("Delete is unavailable until this draft has been persisted."),
      publish: blocked("Publish is unavailable until this draft has been persisted."),
      clone: blocked("Clone is unavailable until this draft has been persisted."),
    };
  }

  const allowedActions = input.activeDefinition.allowed_actions ?? {
    update: false,
    delete: false,
    publish: false,
    clone: false,
  };

  const save =
    isBusy
      ? blocked("Save waits until the current save or route transition finishes.")
      : !allowedActions.update
        ? blocked("Update is blocked by backend definition authority.")
        : input.hasBlockingLocalDiagnostics
          ? blocked("Fix blocking local diagnostics before saving.")
          : input.isDirty
            ? allowed("Save updates the persisted definition and refreshes preview authority.")
            : blocked("Save is only available when the editor has unsaved changes.");

  const publish =
    isBusy
      ? blocked("Publish waits until the current mutation or route transition finishes.")
      : input.runtimeMode === "local" || input.activeDefinition.visibility_scope === "local"
        ? blocked("Publish stays online-only. Local definitions must move through an explicit upload or import flow.")
      : input.isDirty
        ? blocked("Save or discard local edits before publishing the persisted definition.")
        : allowedActions.publish
          ? allowed("Publish promotes this persisted private definition to workspace visibility.")
          : blocked("Publish is blocked by backend definition authority.");

  const clone =
    isBusy
      ? blocked("Clone waits until the current mutation or route transition finishes.")
      : input.isDirty
        ? blocked("Save or discard local edits before cloning the persisted definition.")
        : allowedActions.clone
          ? allowed("Clone creates a new persisted private copy and redirects the editor to it.")
          : blocked("Clone is blocked by backend definition authority.");

  const deleteAction =
    isBusy
      ? blocked("Delete waits until the current mutation or route transition finishes.")
      : allowedActions.delete
        ? allowed("Delete removes the persisted definition and exits this editor identity.")
        : blocked("Delete is blocked by backend definition authority.");

  return {
    format,
    save,
    discard,
    delete: deleteAction,
    publish,
    clone,
  };
}
