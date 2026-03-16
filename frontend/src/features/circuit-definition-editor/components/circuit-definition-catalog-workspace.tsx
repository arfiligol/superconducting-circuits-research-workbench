"use client";

import { useMemo, useState, useTransition } from "react";
import {
  ArrowRight,
  Copy,
  Globe,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";

import { useCircuitDefinitionEditorData } from "@/features/circuit-definition-editor/hooks/use-circuit-definition-editor-data";
import {
  summarizeCatalogDefinitionActionState,
} from "@/features/circuit-definition-editor/lib/actions";
import {
  filterCircuitDefinitionCatalog,
  type CircuitDefinitionCatalogSort,
} from "@/features/circuit-definition-editor/lib/catalog";
import { isCircuitDefinitionMutationPending } from "@/features/circuit-definition-editor/lib/editor-state";
import { buildCircuitDefinitionEditorHref } from "@/features/circuit-definition-editor/lib/routes";
import { AppSelectField } from "@/features/shared/components/app-select";
import { cx, resolveSurfaceInsetToneClass } from "@/features/shared/components/surface-kit";
import { useAppSession } from "@/lib/app-state";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";

type PendingCatalogAction =
  | Readonly<{
      kind: "delete";
      definitionId: number;
      definitionName: string;
    }>
  | null;

function visibilityTone(scope: "local" | "private" | "workspace" | undefined) {
  if (scope === "local") {
    return "border-primary/30 bg-primary/10 text-foreground";
  }

  return scope === "workspace"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-950 dark:text-emerald-100"
    : "border-border bg-surface text-muted-foreground";
}

export function CircuitDefinitionCatalogWorkspace() {
  const { session } = useAppSession();
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<CircuitDefinitionCatalogSort>("recent");
  const [pendingAction, setPendingAction] = useState<PendingCatalogAction>(null);
  const {
    definitions,
    definitionsTotalCount,
    definitionsError,
    isDefinitionsLoading,
    removeDefinition,
    publishDefinition,
    cloneDefinition,
    mutationStatus,
  } = useCircuitDefinitionEditorData(null);
  const isMutationPending = isCircuitDefinitionMutationPending(mutationStatus.state);

  const visibleDefinitions = useMemo(
    () => filterCircuitDefinitionCatalog(definitions, searchQuery, sortMode),
    [definitions, searchQuery, sortMode],
  );

  function openEditor(definitionId: number | "new") {
    startTransition(() => {
      router.push(buildCircuitDefinitionEditorHref(definitionId));
    });
  }

  async function handleDelete() {
    if (!pendingAction || pendingAction.kind !== "delete") {
      return;
    }

    await removeDefinition(pendingAction.definitionId);
    setPendingAction(null);
  }

  async function handlePublish(definitionId: number) {
    await publishDefinition(definitionId);
  }

  async function handleClone(definitionId: number) {
    const clonedDetail = await cloneDefinition(definitionId);
    openEditor(clonedDetail.definition_id);
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[2.05rem] font-semibold tracking-tight text-foreground">Schemas</h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            Browse persisted circuit definitions, inspect backend action availability, then open a
            single definition in the editor route for authoring.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            openEditor("new");
          }}
          disabled={isMutationPending}
          title={
            session?.capabilities.canManageDefinitions
              ? "Create a new schema draft and continue authoring in the editor."
              : "Open a local schema draft. Persist actions stay gated until this session can create definitions."
          }
          className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Circuit
        </button>
      </section>

      {definitionsError ? (
        <div className={cx("rounded-[1rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
          Unable to load circuit schema catalog. {definitionsError.message}
        </div>
      ) : null}

      {mutationStatus.message ? (
        <div
          className={cx(
            "rounded-[1rem] border px-4 py-3 text-sm",
            mutationStatus.state === "error"
              ? resolveSurfaceInsetToneClass("error")
              : "border-primary/30 bg-primary/8 text-foreground",
          )}
        >
          {mutationStatus.message}
        </div>
      ) : null}

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="grid gap-3 border-b border-border/80 pb-4 md:grid-cols-[minmax(0,1fr)_200px]">
          <label className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
            <span className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
              <Search className="h-3.5 w-3.5" />
              Search
            </span>
            <input
              value={searchQuery}
              onChange={(event) => {
                setSearchQuery(event.target.value);
              }}
              placeholder="Find by name or id"
              className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </label>

          <AppSelectField
            label="Sort"
            value={sortMode}
            onChange={(nextValue) => {
              setSortMode(nextValue as CircuitDefinitionCatalogSort);
            }}
            options={[
              { value: "recent", label: "Newest first" },
              { value: "name", label: "Name A-Z" },
            ]}
          />
        </div>

        <div className="mt-4 flex items-center justify-between gap-3 rounded-[0.9rem] border border-border bg-surface px-4 py-3 text-xs text-muted-foreground">
          <span>
            Showing {visibleDefinitions.length} of {definitionsTotalCount} persisted schemas
          </span>
          <span className="rounded-full border border-border px-3 py-1">
            Persisted schema list
          </span>
        </div>

        {isDefinitionsLoading && !definitions ? (
          <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            Loading circuit schema catalog...
          </div>
        ) : null}

        {visibleDefinitions.length > 0 ? (
          <div className="mt-4 space-y-3">
            {visibleDefinitions.map((definition) => {
              const actionState = summarizeCatalogDefinitionActionState(definition);
              return (
                <article
                  key={definition.definition_id}
                  className="rounded-[1rem] border border-border bg-background px-4 py-4"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            openEditor(definition.definition_id);
                          }}
                          className="truncate text-left text-base font-semibold text-foreground transition hover:text-primary"
                        >
                          {definition.name}
                        </button>
                        <span
                          className={cx(
                            "rounded-full border px-3 py-1 text-[11px] font-medium",
                            visibilityTone(definition.visibility_scope),
                          )}
                        >
                          {definition.visibility_scope ?? "private"}
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                        <span className="rounded-full border border-border px-3 py-1">
                          Definition #{definition.definition_id}
                        </span>
                        <span className="rounded-full border border-border px-3 py-1">
                          Owner {definition.owner_display_name ?? "Unknown"}
                        </span>
                        <span
                          className={cx(
                            "rounded-full border px-3 py-1",
                            definition.visibility_scope === "local"
                              ? "border-primary/30 text-foreground"
                              : definition.allowed_actions?.publish
                                ? "border-emerald-500/30 text-emerald-950 dark:text-emerald-100"
                                : "border-border text-muted-foreground",
                          )}
                        >
                          {definition.visibility_scope === "local"
                            ? "Local only"
                            : definition.allowed_actions?.publish
                              ? "Publish allowed"
                              : "Publish blocked"}
                        </span>
                        <span
                          className={cx(
                            "rounded-full border px-3 py-1",
                            definition.allowed_actions?.clone
                              ? "border-primary/30 text-primary"
                              : "border-border text-muted-foreground",
                          )}
                        >
                          {definition.allowed_actions?.clone ? "Clone allowed" : "Clone blocked"}
                        </span>
                      </div>
                      <p className="mt-3 text-xs text-muted-foreground">
                        Created: {definition.created_at}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          openEditor(definition.definition_id);
                        }}
                        disabled={isMutationPending}
                        title={actionState.open.reason}
                        className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <ArrowRight className="h-4 w-4" />
                        Open
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          void handleClone(definition.definition_id);
                        }}
                        disabled={isMutationPending || !actionState.clone.enabled}
                        title={
                          isMutationPending
                            ? "Wait for the current catalog mutation to finish."
                            : actionState.clone.reason
                        }
                        className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Copy className="h-4 w-4" />
                        Clone
                      </button>
                      {session?.runtimeMode === "local" ? null : (
                        <button
                          type="button"
                          onClick={() => {
                            void handlePublish(definition.definition_id);
                          }}
                          disabled={isMutationPending || !actionState.publish.enabled}
                          title={
                            isMutationPending
                              ? "Wait for the current catalog mutation to finish."
                              : actionState.publish.reason
                          }
                          className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Globe className="h-4 w-4" />
                          Publish
                        </button>
                      )}
                      <button
                        type="button"
                        aria-label={`Delete ${definition.name}`}
                        onClick={() => {
                          setPendingAction({
                            kind: "delete",
                            definitionId: definition.definition_id,
                            definitionName: definition.name,
                          });
                        }}
                        disabled={isMutationPending || !actionState.delete.enabled}
                        title={
                          isMutationPending
                            ? "Wait for the current catalog mutation to finish."
                            : actionState.delete.reason
                        }
                        className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-rose-500/30 text-rose-700 transition hover:bg-rose-500/10 dark:text-rose-300 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}

        {!isDefinitionsLoading && visibleDefinitions.length === 0 ? (
          <div className="mt-4 rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
            No schemas match the current catalog controls.
          </div>
        ) : null}
      </section>

      <ConfirmActionDialog
        open={pendingAction?.kind === "delete"}
        title="Delete persisted definition?"
        description={
          pendingAction?.kind === "delete"
            ? `Delete "${pendingAction.definitionName}" from the persisted catalog. This action cannot be undone.`
            : ""
        }
        confirmLabel="Delete definition"
        tone="destructive"
        isPending={mutationStatus.state === "deleting"}
        onCancel={() => {
          setPendingAction(null);
        }}
        onConfirm={() => {
          void handleDelete();
        }}
      />
    </div>
  );
}
