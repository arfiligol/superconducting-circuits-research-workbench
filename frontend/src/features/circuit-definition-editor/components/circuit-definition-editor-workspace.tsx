"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Copy,
  FileCode2,
  Globe,
  LoaderCircle,
  Save,
  Shapes,
  Sparkles,
  Trash2,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import CodeMirror from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { z } from "zod";

import { useCircuitDefinitionEditorData } from "@/features/circuit-definition-editor/hooks/use-circuit-definition-editor-data";
import {
  summarizeEditorDefinitionActionState,
} from "@/features/circuit-definition-editor/lib/actions";
import {
  parseDefinitionIdParam,
  resolveSelectedDefinitionId,
} from "@/features/circuit-definition-editor/lib/definition-id";
import {
  buildCircuitDefinitionCatalogHref,
  buildCircuitSchemdrawHref,
} from "@/features/circuit-definition-editor/lib/routes";
import {
  buildCircuitDefinitionDraft,
  formatCircuitNetlistSource,
} from "@/features/circuit-definition-editor/lib/netlist";
import {
  buildCircuitDefinitionDraftSurface,
  buildCircuitDefinitionPersistedPreviewSurface,
  isCircuitDefinitionMutationPending,
} from "@/features/circuit-definition-editor/lib/editor-state";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";
import { cx, resolveSurfaceInsetToneClass } from "@/features/shared/components/surface-kit";

import type { CircuitDefinitionDetail } from "@/features/circuit-definition-editor/lib/contracts";

const quickReferenceRows = [
  ["Port", "P*", "-", '["P1", "1", "0", 1]'],
  ["Resistor", "R*", "Ohm / kOhm / MOhm", '["R1", "1", "0", "R1"]'],
  ["Inductor", "L*", "H / mH / uH / nH / pH", '["L1", "1", "2", "L1"]'],
  ["Capacitor", "C*", "F / mF / uF / nF / pF / fF", '["C1", "1", "2", "C1"]'],
  ["Josephson Junction", "Lj*", "H / mH / uH / nH / pH", '["Lj1", "2", "0", "Lj1"]'],
  ["Mutual Coupling", "K*", "project-specific", '["K1", "L1", "L2", "K1"]'],
] as const;

const authoringRules = [
  "`components` and `topology` are required.",
  "Each component must declare exactly one of `default` or `value_ref`.",
  "`value_ref` must point at an existing parameter with the same unit.",
  "Ground token is always the string `0`.",
  "Port rows use an integer in topology position 4.",
  "Non-Port rows must reference an existing component name in topology position 4.",
] as const;

const definitionFormSchema = z.object({
  name: z.string().trim().min(1, "Name is required."),
  source_text: z.string().trim().min(1, "Circuit netlist source is required."),
});

type DefinitionFormValues = z.infer<typeof definitionFormSchema>;

const emptyDefinitionForm: DefinitionFormValues = {
  name: "NewCircuitDefinition",
  source_text: `{
  "name": "NewCircuitDefinition",
  "components": [
    { "name": "R1", "default": 50.0, "unit": "Ohm" },
    { "name": "C1", "default": 100.0, "unit": "fF" },
    { "name": "Lj1", "default": 1000.0, "unit": "pH" }
  ],
  "topology": [
    ["P1", "1", "0", 1],
    ["R1", "1", "0", "R1"],
    ["C1", "1", "2", "C1"],
    ["Lj1", "2", "0", "Lj1"]
  ]
}`,
};

function definitionSearchHref(pathname: string, searchParamsValue: string, definitionId: string) {
  const params = new URLSearchParams(searchParamsValue);
  params.set("definitionId", definitionId);
  return `${pathname}?${params.toString()}`;
}

type PendingEditorIntent =
  | Readonly<{
      kind: "delete";
      definition: Pick<CircuitDefinitionDetail, "definition_id" | "name">;
      discardDraft: boolean;
    }>
  | Readonly<{
      kind: "switch-definition";
      nextDefinitionId: string;
    }>
  | null;

export function CircuitDefinitionEditorWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isNavigating, startTransition] = useTransition();
  const [catalogQuery, setCatalogQuery] = useState("");
  const [pendingIntent, setPendingIntent] = useState<PendingEditorIntent>(null);

  const selectedDefinitionId = parseDefinitionIdParam(searchParams.get("definitionId"));
  const {
    definitions,
    definitionsTotalCount,
    definitionsError,
    isDefinitionsLoading,
    activeDefinition,
    activeDefinitionError,
    mutationStatus,
    saveDefinition,
    publishDefinition,
    cloneDefinition,
    removeDefinition,
    clearMutationStatus,
  } = useCircuitDefinitionEditorData(selectedDefinitionId);

  const form = useForm<DefinitionFormValues>({
    resolver: zodResolver(definitionFormSchema),
    defaultValues: emptyDefinitionForm,
  });

  useEffect(() => {
    const nextSelection = resolveSelectedDefinitionId(searchParams.get("definitionId"), definitions);
    if (!nextSelection || nextSelection === searchParams.get("definitionId")) {
      return;
    }

    startTransition(() => {
      router.replace(definitionSearchHref(pathname, searchParams.toString(), nextSelection), {
        scroll: false,
      });
    });
  }, [definitions, pathname, router, searchParams]);

  useEffect(() => {
    if (selectedDefinitionId === "new") {
      form.reset(emptyDefinitionForm);
      return;
    }

    if (activeDefinition) {
      const parsedSource = formatCircuitNetlistSource(activeDefinition.source_text, {
        canonicalName: activeDefinition.name,
      });
      form.reset({
        name: activeDefinition.name,
        source_text: parsedSource.formattedSource || activeDefinition.source_text,
      });
    }
  }, [activeDefinition, form, selectedDefinitionId]);

  useEffect(() => {
    function handleFormatShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "f") {
        event.preventDefault();
        void handleFormat();
      }
    }

    window.addEventListener("keydown", handleFormatShortcut);
    return () => {
      window.removeEventListener("keydown", handleFormatShortcut);
    };
  }, [form]);

  const definitionName = form.watch("name");
  const sourceText = form.watch("source_text");
  const draftSurface = useMemo(
    () =>
      buildCircuitDefinitionDraftSurface({
        name: definitionName,
        sourceText,
      }),
    [definitionName, sourceText],
  );
  const isMutationPending = isCircuitDefinitionMutationPending(mutationStatus.state);
  const isIdentityTransitionLocked = isMutationPending || isNavigating;
  const filteredDefinitions = (definitions ?? []).filter((definition) => {
    const normalizedQuery = catalogQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return true;
    }

    return (
      definition.name.toLowerCase().includes(normalizedQuery) ||
      String(definition.definition_id).includes(normalizedQuery)
    );
  });
  const persistedPreviewSurface = useMemo(
    () =>
      buildCircuitDefinitionPersistedPreviewSurface({
        selectedDefinitionId,
        isDirty: form.formState.isDirty,
        mutationPhase: mutationStatus.state,
        activeDefinition,
      }),
    [activeDefinition, form.formState.isDirty, mutationStatus.state, selectedDefinitionId],
  );
  const editorActionState = summarizeEditorDefinitionActionState({
    selectedDefinitionId,
    activeDefinition,
    isDirty: form.formState.isDirty,
    isMutationPending,
    isNavigating,
    hasBlockingLocalDiagnostics: draftSurface.blockingLocalDiagnostics.length > 0,
  });

  const activeDefinitionLabel =
    selectedDefinitionId === "new" ? "New Circuit Definition" : activeDefinition?.name ?? "Loading";

  async function onSubmit(values: DefinitionFormValues) {
    const nextDraft = buildCircuitDefinitionDraft({
      name: values.name,
      sourceText: values.source_text,
    });

    if (!nextDraft.draft) {
      form.setError("source_text", {
        type: "validate",
        message: nextDraft.diagnostics[0]?.message ?? "Source does not match the circuit-netlist contract.",
      });
      return;
    }

    const detail = await saveDefinition(nextDraft.draft, {
      definitionId: selectedDefinitionId,
      activeDefinition,
    });
    replaceDefinitionId(String(detail.definition_id));
    form.reset({
      name: detail.name,
      source_text: nextDraft.formattedSource,
    });
  }

  async function handleConfirmedIntent() {
    if (!pendingIntent) {
      return;
    }

    if (pendingIntent.kind === "switch-definition") {
      clearMutationStatus();
      replaceDefinitionId(pendingIntent.nextDefinitionId);
      setPendingIntent(null);
      return;
    }

    await removeDefinition(pendingIntent.definition.definition_id);
    const remainingDefinitions = (definitions ?? []).filter(
      (definition) => definition.definition_id !== pendingIntent.definition.definition_id,
    );
    const fallbackSelection = remainingDefinitions[0]
      ? String(remainingDefinitions[0].definition_id)
      : "new";
    setPendingIntent(null);
    replaceDefinitionId(fallbackSelection);
  }

  async function handleFormat() {
    const formatted = formatCircuitNetlistSource(form.getValues("source_text"), {
      canonicalName: form.getValues("name"),
    });
    form.setValue("source_text", formatted.formattedSource, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    });
    if (formatted.diagnostics.length > 0) {
      form.setError("source_text", {
        type: "validate",
        message: formatted.diagnostics[0]?.message,
      });
    } else {
      form.clearErrors("source_text");
    }
  }

  function handleReplaceDefinitionIdRequest(nextId: string) {
    if (nextId === String(selectedDefinitionId)) {
      return;
    }

    if (form.formState.isDirty) {
      setPendingIntent({
        kind: "switch-definition",
        nextDefinitionId: nextId,
      });
      return;
    }

    clearMutationStatus();
    replaceDefinitionId(nextId);
  }

  function discardChanges() {
    if (selectedDefinitionId === "new") {
      form.reset(emptyDefinitionForm);
      return;
    }

    if (activeDefinition) {
      const parsedSource = formatCircuitNetlistSource(activeDefinition.source_text, {
        canonicalName: activeDefinition.name,
      });
      form.reset({
        name: activeDefinition.name,
        source_text: parsedSource.formattedSource || activeDefinition.source_text,
      });
    }
  }

  async function handlePublish() {
    if (!activeDefinition) {
      return;
    }

    const detail = await publishDefinition(activeDefinition.definition_id);
    form.reset({
      name: detail.name,
      source_text: formatCircuitNetlistSource(detail.source_text, {
        canonicalName: detail.name,
      }).formattedSource,
    });
  }

  async function handleClone() {
    if (!activeDefinition) {
      return;
    }

    const detail = await cloneDefinition(activeDefinition.definition_id);
    replaceDefinitionId(String(detail.definition_id));
    form.reset({
      name: detail.name,
      source_text: formatCircuitNetlistSource(detail.source_text, {
        canonicalName: detail.name,
      }).formattedSource,
    });
  }

  function requestDelete(definition: Pick<CircuitDefinitionDetail, "definition_id" | "name">) {
    setPendingIntent({
      kind: "delete",
      definition,
      discardDraft: form.formState.isDirty,
    });
  }

  function replaceDefinitionId(definitionId: string) {
    startTransition(() => {
      router.replace(definitionSearchHref(pathname, searchParams.toString(), definitionId), {
        scroll: false,
      });
    });
  }

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[2.05rem] font-semibold tracking-tight text-foreground">
            Schema Editor
          </h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            Author canonical circuit-netlist source, format it explicitly, and compare local draft
            diagnostics against the last persisted backend preview.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              router.push(buildCircuitDefinitionCatalogHref());
            }}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-4 py-2.5 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Schemas
          </button>
          {typeof selectedDefinitionId === "number" ? (
            <button
              type="button"
              onClick={() => {
                router.push(buildCircuitSchemdrawHref(selectedDefinitionId));
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-4 py-2.5 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              <Shapes className="h-4 w-4" />
              Open Schemdraw
            </button>
          ) : null}
        </div>
      </section>

      {definitionsError ? (
        <div
          className={cx(
            "rounded-[1rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass("error"),
          )}
        >
          Unable to load circuit definitions. {definitionsError.message}
        </div>
      ) : null}

      {activeDefinitionError ? (
        <div
          className={cx(
            "rounded-[1rem] border px-4 py-3 text-sm",
            resolveSurfaceInsetToneClass("error"),
          )}
        >
          Unable to load the selected definition. {activeDefinitionError.message}
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

      <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.72fr)_minmax(0,1.28fr)]">
        <div className="space-y-4">
          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex items-center justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Catalog Rail
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Open another schema without leaving the editor workflow.
                </p>
              </div>
              <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                {definitionsTotalCount} total
              </span>
            </div>

            <label className="mt-4 block rounded-[0.9rem] border border-border bg-surface px-4 py-3">
              <span className="mb-2 block text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Search
              </span>
              <input
                value={catalogQuery}
                onChange={(event) => {
                  setCatalogQuery(event.target.value);
                }}
                placeholder="Find by name or id"
                className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </label>

            {isDefinitionsLoading && !definitions ? (
              <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                Loading schema rail...
              </div>
            ) : null}

            <div className="mt-4 space-y-3">
              <button
                type="button"
                onClick={() => {
                  handleReplaceDefinitionIdRequest("new");
                }}
                disabled={isIdentityTransitionLocked}
                title={
                  isIdentityTransitionLocked
                    ? "Wait for the current route transition or mutation to finish."
                    : "Create a new draft in the single editor workspace."
                }
                className={cx(
                  "w-full rounded-[0.9rem] border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-60",
                  selectedDefinitionId === "new"
                    ? "border-primary/40 bg-primary/10"
                    : "border-border bg-surface hover:border-primary/30 hover:bg-primary/5",
                )}
              >
                <p className="text-sm font-semibold text-foreground">New Schema Draft</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Start a new circuit-netlist document from the canonical template.
                </p>
              </button>

              {filteredDefinitions.map((definition) => (
                <button
                  key={definition.definition_id}
                  type="button"
                  onClick={() => {
                    handleReplaceDefinitionIdRequest(String(definition.definition_id));
                  }}
                  disabled={isIdentityTransitionLocked}
                  title={
                    isIdentityTransitionLocked
                      ? "Wait for the current route transition or mutation to finish."
                      : "Rebind the editor to this persisted definition."
                  }
                  className={cx(
                    "w-full rounded-[0.9rem] border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-60",
                    definition.definition_id === selectedDefinitionId
                      ? "border-primary/40 bg-primary/10"
                      : "border-border bg-surface hover:border-primary/30 hover:bg-primary/5",
                  )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">
                          {definition.name}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Definition #{definition.definition_id}
                        </p>
                      </div>
                      <span
                        className={cx(
                          "rounded-full border px-2.5 py-1 text-[11px]",
                          definition.visibility_scope === "workspace"
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-950 dark:text-emerald-100"
                            : "border-border bg-background text-muted-foreground",
                        )}
                      >
                        {definition.visibility_scope}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                      <span className="rounded-full border border-border px-3 py-1">
                        Owner {definition.owner_display_name}
                      </span>
                      <span className="rounded-full border border-border px-3 py-1">
                        {definition.allowed_actions?.clone ? "Clone allowed" : "Clone blocked"}
                      </span>
                    </div>
                  </button>
              ))}
            </div>
          </section>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="border-b border-border/80 pb-4">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Circuit Netlist Quick Reference
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Use the canonical contract while editing; the source editor and saved payload are
                expected to match this structure.
              </p>
            </div>

            <div className="mt-4 overflow-x-auto rounded-[0.9rem] border border-border">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-surface text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Component</th>
                    <th className="px-4 py-3">Prefix</th>
                    <th className="px-4 py-3">Units</th>
                    <th className="px-4 py-3">Topology Example</th>
                  </tr>
                </thead>
                <tbody>
                  {quickReferenceRows.map((row) => (
                    <tr key={row[0]} className="border-t border-border bg-background">
                      <td className="px-4 py-3 text-foreground">{row[0]}</td>
                      <td className="px-4 py-3 text-muted-foreground">{row[1]}</td>
                      <td className="px-4 py-3 text-muted-foreground">{row[2]}</td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                        {row[3]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 space-y-2 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              {authoringRules.map((rule) => (
                <p key={rule}>{rule}</p>
              ))}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex flex-col gap-4 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Active Schema
                </h2>
                <p className="mt-2 text-lg font-semibold text-foreground">{activeDefinitionLabel}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-primary">
                    {selectedDefinitionId === "new"
                      ? "Draft"
                      : `Definition #${activeDefinition?.definition_id ?? "--"}`}
                  </span>
                  {activeDefinition ? (
                    <>
                      <span className="rounded-full bg-surface px-3 py-1">
                        {activeDefinition.visibility_scope}
                      </span>
                      <span className="rounded-full bg-surface px-3 py-1">
                        {activeDefinition.lifecycle_state}
                      </span>
                    </>
                  ) : null}
                  <span className="rounded-full bg-surface px-3 py-1">
                    {draftSurface.localSummary.componentCount} components
                  </span>
                  <span className="rounded-full bg-surface px-3 py-1">
                    {draftSurface.localSummary.topologyCount} topology rows
                  </span>
                  <span className="rounded-full bg-surface px-3 py-1">
                    {draftSurface.localSummary.parameterCount} parameters
                  </span>
                  {typeof activeDefinition?.lineage_parent_id === "number" ? (
                    <span className="rounded-full bg-surface px-3 py-1">
                      Cloned from #{activeDefinition.lineage_parent_id}
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {typeof selectedDefinitionId === "number" ? (
                  <button
                    type="button"
                    onClick={() => {
                      requestDelete({
                        definition_id: selectedDefinitionId,
                        name: activeDefinition?.name ?? activeDefinitionLabel,
                      });
                    }}
                    disabled={isMutationPending || !editorActionState.delete.enabled}
                    title={
                      isMutationPending
                        ? "Wait for the current definition mutation to finish."
                        : editorActionState.delete.reason
                    }
                    className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-rose-500/30 px-3 py-2 text-sm text-rose-700 transition hover:bg-rose-500/10 dark:text-rose-200 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </button>
                ) : null}
                {typeof selectedDefinitionId === "number" ? (
                  <button
                    type="button"
                    onClick={() => {
                      void handlePublish();
                    }}
                    disabled={isMutationPending || !editorActionState.publish.enabled}
                    title={
                      isMutationPending
                        ? "Wait for the current definition mutation to finish."
                        : editorActionState.publish.reason
                    }
                    className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Globe className="h-4 w-4" />
                    Publish
                  </button>
                ) : null}
                {typeof selectedDefinitionId === "number" ? (
                  <button
                    type="button"
                    onClick={() => {
                      void handleClone();
                    }}
                    disabled={isMutationPending || !editorActionState.clone.enabled}
                    title={
                      isMutationPending
                        ? "Wait for the current definition mutation to finish."
                        : editorActionState.clone.reason
                    }
                    className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Copy className="h-4 w-4" />
                    Clone
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => {
                    void handleFormat();
                  }}
                  disabled={!editorActionState.format.enabled}
                  title={editorActionState.format.reason}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Sparkles className="h-4 w-4" />
                  Format
                </button>
                {form.formState.isDirty ? (
                  <button
                    type="button"
                    onClick={discardChanges}
                    disabled={!editorActionState.discard.enabled}
                    title={editorActionState.discard.reason}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-muted-foreground transition hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Discard
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => {
                    void form.handleSubmit(onSubmit)();
                  }}
                  disabled={!editorActionState.save.enabled}
                  title={editorActionState.save.reason}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {form.formState.isSubmitting ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  Save
                </button>
              </div>
            </div>

            <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-3 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Action Authority</p>
              <p className="mt-1">
                Save: {editorActionState.save.reason}
              </p>
              <p className="mt-1">
                Publish: {editorActionState.publish.reason}
              </p>
              <p className="mt-1">
                Clone: {editorActionState.clone.reason}
              </p>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Local Contract
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {draftSurface.blockingLocalDiagnostics.length > 0 ? "Needs fixes" : "Aligned"}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Local Diagnostics
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {draftSurface.localDiagnostics.length}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Persisted Notices
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {persistedPreviewSurface.validationSummary?.notice_count ?? 0}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Preview Artifacts
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {activeDefinition?.preview_artifact_count ??
                    persistedPreviewSurface.previewArtifacts.length}
                </p>
              </div>
            </div>
          </section>

          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void form.handleSubmit(onSubmit)();
            }}
          >
            <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
              <div className="border-b border-border/80 pb-4">
                <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Canonical Source
                  {form.formState.isDirty ? (
                    <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold normal-case tracking-normal text-amber-500">
                      Unsaved Changes
                    </span>
                  ) : null}
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  The editor accepts JSON or Python-literal netlist source, but `Format` and `Save`
                  always normalize outgoing payloads to the canonical circuit-netlist shape.
                </p>
              </div>

              <div className="mt-4 grid gap-4">
                <label className="grid gap-2 text-sm">
                  <span className="font-medium text-foreground">Name</span>
                  <input
                    type="text"
                    className="rounded-[0.8rem] border border-border bg-background px-4 py-3 text-sm text-foreground outline-none"
                    {...form.register("name")}
                  />
                  {form.formState.errors.name ? (
                    <span className="text-xs text-rose-700 dark:text-rose-300">
                      {form.formState.errors.name.message}
                    </span>
                  ) : null}
                </label>

                <div className="grid gap-2 text-sm">
                  <span className="font-medium text-foreground">Source Text</span>
                  <div className="overflow-hidden rounded-[0.8rem] border border-border bg-background">
                    <Controller
                      name="source_text"
                      control={form.control}
                      render={({ field }) => (
                        <CodeMirror
                          value={field.value}
                          height="420px"
                          theme="dark"
                          extensions={[yaml()]}
                          onChange={(value) => field.onChange(value)}
                          className="text-sm leading-6"
                        />
                      )}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    `Cmd/Ctrl + Shift + F` runs explicit format only. It does not save.
                  </p>
                  {form.formState.errors.source_text ? (
                    <span className="text-xs text-rose-700 dark:text-rose-300">
                      {form.formState.errors.source_text.message}
                    </span>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-4 text-sm">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Serializer Boundary
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Definition Identity
                    </p>
                    <p className="mt-2 font-medium text-foreground">
                      {draftSurface.serializerBoundary.definitionName}
                    </p>
                  </div>
                  <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Source Document Name
                    </p>
                    <p className="mt-2 font-medium text-foreground">
                      {draftSurface.serializerBoundary.sourceDocumentName ?? "Unavailable"}
                    </p>
                  </div>
                  <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Persisted Source Hash
                    </p>
                    <p className="mt-2 font-medium text-foreground">
                      {activeDefinition?.source_hash ?? "Draft only"}
                    </p>
                  </div>
                </div>
                <p
                  className={cx(
                    "mt-3",
                    draftSurface.serializerBoundary.willRewriteSourceName
                      ? "text-amber-700 dark:text-amber-300"
                      : "text-muted-foreground",
                  )}
                >
                  {draftSurface.serializerBoundary.detail}
                </p>
              </div>
            </section>
          </form>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Local Contract Diagnostics
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  These checks guard the outgoing payload before save; persisted backend notices stay
                  separate below.
                </p>
              </div>
              <div className="rounded-full bg-surface px-3 py-1 text-xs text-muted-foreground">
                {draftSurface.localDiagnostics.length} items
              </div>
            </div>

            {draftSurface.localDiagnostics.length > 0 ? (
              <div className="mt-4 space-y-3">
                {draftSurface.localDiagnostics.map((diagnostic) => (
                  <div
                    key={`${diagnostic.path}-${diagnostic.message}`}
                    className={cx(
                      "rounded-[0.8rem] border px-4 py-3 text-sm",
                      diagnostic.severity === "error"
                        ? resolveSurfaceInsetToneClass("error")
                        : resolveSurfaceInsetToneClass("warning"),
                    )}
                  >
                    <p className="font-medium">{diagnostic.path}</p>
                    <p className="mt-1">{diagnostic.message}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div
                className={cx(
                  "mt-4 rounded-[0.8rem] border px-4 py-3 text-sm",
                  resolveSurfaceInsetToneClass("success"),
                )}
              >
                Local source currently matches the canonical circuit-netlist contract.
              </div>
            )}
          </section>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Validation & Preview
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Persisted backend validation, normalized output, and preview artifacts remain
                  bound to the last successful save.
                </p>
              </div>
              <div
                className={cx(
                  "rounded-full px-3 py-1 text-xs font-medium",
                  persistedPreviewSurface.persistedPreviewState.tone === "warning"
                    ? "bg-amber-500/12 text-amber-800 dark:text-amber-200"
                    : persistedPreviewSurface.persistedPreviewState.tone === "accent"
                      ? "bg-primary/10 text-primary"
                      : "bg-surface text-muted-foreground",
                )}
              >
                <FileCode2 className="mr-1 inline-block h-4 w-4" />
                {persistedPreviewSurface.persistedPreviewState.label}
              </div>
            </div>

            <div
              className={cx(
                "mt-4 rounded-[0.8rem] border px-4 py-3 text-sm",
                persistedPreviewSurface.persistedPreviewState.tone === "warning"
                  ? resolveSurfaceInsetToneClass("warning")
                  : persistedPreviewSurface.persistedPreviewState.tone === "accent"
                    ? "border-primary/20 bg-primary/8 text-foreground"
                    : "border-border bg-surface text-muted-foreground",
              )}
            >
              {persistedPreviewSurface.persistedPreviewState.detail}
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Validation Status
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {persistedPreviewSurface.validationSummary
                    ? persistedPreviewSurface.validationSummary.status === "invalid"
                      ? "Invalid"
                      : persistedPreviewSurface.validationSummary.status === "warning"
                      ? "Warnings Present"
                      : "Ready"
                    : "Pending Save"}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Notice Count
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {persistedPreviewSurface.validationSummary?.notice_count ?? 0}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Warning Count
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {persistedPreviewSurface.validationSummary?.warning_count ?? 0}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Preview Fields
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {persistedPreviewSurface.normalizedPreview.fieldCount}
                </p>
              </div>
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
              <section className="rounded-[0.8rem] border border-border bg-surface px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Persisted Notices</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Last successful save only.
                    </p>
                  </div>
                  <div className="rounded-full bg-background px-3 py-1 text-xs text-muted-foreground">
                    {persistedPreviewSurface.validationSummary?.status === "invalid"
                      ? "Blocking"
                      : persistedPreviewSurface.validationSummary?.status === "warning"
                        ? "Needs review"
                        : "Ready"}
                  </div>
                </div>

                {persistedPreviewSurface.validationNotices.length === 0 ? (
                  <div className="mt-4 rounded-[0.8rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                    {selectedDefinitionId === "new"
                      ? "Save the draft to generate persisted backend validation notices."
                      : form.formState.isDirty
                        ? "Save the current draft to refresh the persisted validation report."
                      : "No validation notices were returned for this definition."}
                  </div>
                ) : (
                  <div className="mt-4 space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-rose-700 dark:text-rose-300">
                        <AlertTriangle className="h-4 w-4" />
                        Blocking
                      </div>
                      {persistedPreviewSurface.validationGroups.blocking.length === 0 ? (
                        <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                          No blocking persisted notices were recorded.
                        </div>
                      ) : (
                        persistedPreviewSurface.validationGroups.blocking.map((notice) => (
                          <div
                            key={`blocking-${notice.code}-${notice.message}`}
                            className={cx(
                              "rounded-[0.8rem] border px-4 py-3 text-sm",
                              resolveSurfaceInsetToneClass("error"),
                            )}
                          >
                            <p className="font-medium">
                              {notice.code} · {notice.source}
                            </p>
                            <p className="mt-1">{notice.message}</p>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="h-4 w-4" />
                        Warnings
                      </div>
                      {persistedPreviewSurface.validationGroups.warnings.length === 0 ? (
                        <div
                          className={cx(
                            "rounded-[0.8rem] border px-4 py-3 text-sm",
                            resolveSurfaceInsetToneClass("success"),
                          )}
                        >
                          No persisted warnings were recorded.
                        </div>
                      ) : (
                        persistedPreviewSurface.validationGroups.warnings.map((notice) => (
                          <div
                            key={`warning-${notice.code}-${notice.message}`}
                            className={cx(
                              "rounded-[0.8rem] border px-4 py-3 text-sm",
                              resolveSurfaceInsetToneClass("warning"),
                            )}
                          >
                            <p className="font-medium">
                              {notice.code} · {notice.source}
                            </p>
                            <p className="mt-1">{notice.message}</p>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-300">
                        <BadgeCheck className="h-4 w-4" />
                        Checks
                      </div>
                      {persistedPreviewSurface.validationGroups.checks.length === 0 ? (
                        <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                          No passing notices were recorded yet.
                        </div>
                      ) : (
                        persistedPreviewSurface.validationGroups.checks.map((notice) => (
                          <div
                            key={`check-${notice.code}-${notice.message}`}
                            className={cx(
                              "rounded-[0.8rem] border px-4 py-3 text-sm",
                              resolveSurfaceInsetToneClass("success"),
                            )}
                          >
                            <p className="font-medium">
                              {notice.code} · {notice.source}
                            </p>
                            <p className="mt-1">{notice.message}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </section>

              <section className="rounded-[0.8rem] border border-border bg-surface px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Normalized Output</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Canonical backend-derived preview.
                    </p>
                  </div>
                  <div className="rounded-full bg-background px-3 py-1 text-xs text-muted-foreground">
                    {persistedPreviewSurface.normalizedPreview.isStructured ? "Structured" : "Raw"}
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {persistedPreviewSurface.normalizedPreview.fields.map((field) => (
                    <div
                      key={field.key}
                      className="rounded-[0.8rem] border border-border bg-background px-4 py-3"
                    >
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        {field.label}
                      </p>
                      <p className="mt-2 text-sm font-medium text-foreground">{field.value}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-4 rounded-[0.8rem] border border-border bg-background px-4 py-4">
                  <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-muted-foreground">
                    {persistedPreviewSurface.normalizedPreview.formattedOutput}
                  </pre>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                    Preview artifacts: {persistedPreviewSurface.previewArtifacts.length}
                  </div>
                  <div className="rounded-[0.8rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                    Output lines: {persistedPreviewSurface.normalizedPreview.lineCount}
                  </div>
                </div>
              </section>
            </div>
          </section>
        </div>
      </section>

      <ConfirmActionDialog
        open={pendingIntent !== null}
        title={
          pendingIntent?.kind === "delete"
            ? "Delete persisted definition?"
            : "Discard local draft changes?"
        }
        description={
          pendingIntent?.kind === "delete"
            ? pendingIntent.discardDraft
              ? `Delete "${pendingIntent.definition.name}" and discard the current unsaved draft. This action cannot be undone.`
              : `Delete "${pendingIntent.definition.name}" from persisted storage. This action cannot be undone.`
            : "Switching definitions will discard the current unsaved draft and rebind the editor to the selected persisted identity."
        }
        confirmLabel={
          pendingIntent?.kind === "delete" ? "Delete definition" : "Discard and switch"
        }
        tone={pendingIntent?.kind === "delete" ? "destructive" : "default"}
        isPending={mutationStatus.state === "deleting"}
        onCancel={() => {
          setPendingIntent(null);
        }}
        onConfirm={() => {
          void handleConfirmedIntent();
        }}
      />
    </div>
  );
}
