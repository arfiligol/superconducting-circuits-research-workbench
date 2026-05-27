"use client";

import { Plus, Save, Trash2 } from "lucide-react";

import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";
import type { CircuitDefinitionSummary } from "@/features/circuit-definition-editor/lib/contracts";
import { OverlayDialog, SetupInputField, SetupTextInput } from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { SavedSimulationSetupRecord } from "@/features/simulation/lib/saved-setups";
import { SurfaceTag } from "@/features/shared/components/surface-kit";

function formatSavedSetupTimestamp(isoTimestamp: string) {
  const parsedTimestamp = new Date(isoTimestamp);
  if (Number.isNaN(parsedTimestamp.getTime())) {
    return isoTimestamp;
  }

  return parsedTimestamp.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function SimulationSavedSetupDialogs({
  activeSavedSetup,
  isManageDialogOpen,
  isSaveDialogOpen,
  openSaveAsNewFromManage,
  resolvedDefinitionId,
  saveDialogMode,
  saveDialogOverwriteTargetId,
  saveSetupNameDraft,
  selectedDefinitionDisplay,
  setIsManageDialogOpen,
  setIsSaveDialogOpen,
  setSaveSetupNameDraft,
  submitSaveDialog,
  visibleSavedSetups,
  applySavedSetup,
  deleteSavedSetup,
}: Readonly<{
  activeSavedSetup: SavedSimulationSetupRecord | null;
  isManageDialogOpen: boolean;
  isSaveDialogOpen: boolean;
  openSaveAsNewFromManage: () => void;
  resolvedDefinitionId: CircuitDefinitionId | null;
  saveDialogMode: "new-only" | "choose";
  saveDialogOverwriteTargetId: string | null;
  saveSetupNameDraft: string;
  selectedDefinitionDisplay: CircuitDefinitionSummary | { name: string } | null;
  setIsManageDialogOpen: (open: boolean) => void;
  setIsSaveDialogOpen: (open: boolean) => void;
  setSaveSetupNameDraft: (value: string) => void;
  submitSaveDialog: (action: "create" | "overwrite") => void;
  visibleSavedSetups: readonly SavedSimulationSetupRecord[];
  applySavedSetup: (setup: SavedSimulationSetupRecord) => void;
  deleteSavedSetup: (recordId: string) => void;
}>) {
  return (
    <>
      <OverlayDialog
        open={isSaveDialogOpen}
        title="Save Simulation Setup"
        description="Store the current Simulation Setup locally in this browser for the selected definition. This does not create a backend resource."
        onClose={() => {
          setIsSaveDialogOpen(false);
        }}
      >
        <div className="space-y-4">
          {saveDialogMode === "choose" && activeSavedSetup ? (
            <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3 text-sm text-muted-foreground">
              Saving from <span className="font-medium text-foreground">{activeSavedSetup.name}</span>.
              Choose whether to overwrite the current saved setup or create a new one.
            </div>
          ) : null}
          <SetupInputField label="Setup Name">
            <SetupTextInput
              value={saveSetupNameDraft}
              onChange={(event) => {
                setSaveSetupNameDraft(event.target.value);
              }}
              placeholder={selectedDefinitionDisplay?.name ?? "Simulation Setup"}
            />
          </SetupInputField>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setIsSaveDialogOpen(false);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              Cancel
            </button>
            {saveDialogMode === "choose" && saveDialogOverwriteTargetId ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    submitSaveDialog("create");
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
                >
                  <Plus className="h-4 w-4" />
                  Save as New
                </button>
                <button
                  type="button"
                  onClick={() => {
                    submitSaveDialog("overwrite");
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
                >
                  <Save className="h-4 w-4" />
                  Overwrite Current
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => {
                  submitSaveDialog("create");
                }}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
              >
                <Save className="h-4 w-4" />
                Save Setup
              </button>
            )}
          </div>
        </div>
      </OverlayDialog>

      <OverlayDialog
        open={isManageDialogOpen}
        title="Manage Saved Setups"
        description="Review browser-saved Simulation Setup drafts for the current definition, load one into Stage 2, or remove old drafts."
        onClose={() => {
          setIsManageDialogOpen(false);
        }}
      >
        <div className="space-y-4">
          {visibleSavedSetups.length > 0 ? (
            <div className="space-y-3">
              {visibleSavedSetups.map((setup) => {
                const isActive = setup.id === activeSavedSetup?.id;
                return (
                  <div
                    key={setup.id}
                    className="rounded-[0.95rem] border border-border bg-surface px-4 py-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-foreground">{setup.name}</p>
                          {isActive ? <SurfaceTag tone="success">Current</SurfaceTag> : null}
                        </div>
                        <p className="mt-2 text-xs leading-5 text-muted-foreground">
                          {setup.definitionName ?? "Definition"} · Updated{" "}
                          {formatSavedSetupTimestamp(setup.updatedAt)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            applySavedSetup(setup);
                          }}
                          className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
                        >
                          Load
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            deleteSavedSetup(setup.id);
                          }}
                          className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-rose-300 hover:bg-rose-50 dark:hover:border-rose-400/40 dark:hover:bg-rose-500/10"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-[0.95rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              No saved setups exist for the current definition yet.
            </div>
          )}

          <div className="flex flex-wrap justify-between gap-2">
            <button
              type="button"
              onClick={openSaveAsNewFromManage}
              disabled={resolvedDefinitionId === null}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              Save Current as New
            </button>
            <button
              type="button"
              onClick={() => {
                setIsManageDialogOpen(false);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              Done
            </button>
          </div>
        </div>
      </OverlayDialog>
    </>
  );
}
