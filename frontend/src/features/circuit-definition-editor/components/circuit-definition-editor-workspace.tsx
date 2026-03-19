"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Copy, Globe, LoaderCircle, Save, Shapes, Sparkles, Trash2 } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { z } from "zod";

import { useCircuitDefinitionEditorData } from "@/features/circuit-definition-editor/hooks/use-circuit-definition-editor-data";
import { summarizeEditorDefinitionActionState } from "@/features/circuit-definition-editor/lib/actions";
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
  parseCircuitNetlistSource,
} from "@/features/circuit-definition-editor/lib/netlist";
import {
  buildCircuitDefinitionDraftSurface,
  buildCircuitDefinitionPersistedPreviewSurface,
  isCircuitDefinitionMutationPending,
} from "@/features/circuit-definition-editor/lib/editor-state";
import type { CircuitDefinitionDetail } from "@/features/circuit-definition-editor/lib/contracts";
import { cx, resolveSurfaceInsetToneClass } from "@/features/shared/components/surface-kit";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";
import { useAppSession } from "@/lib/app-state";

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
  | null;

function SummaryCard({
  label,
  value,
  detail,
}: Readonly<{
  label: string;
  value: string;
  detail?: string;
}>) {
  return (
    <div className="rounded-[0.85rem] border border-border bg-surface px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
      {detail ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{detail}</p> : null}
    </div>
  );
}

function InlineNotice({
  tone,
  title,
  message,
  items,
}: Readonly<{
  tone: "default" | "success" | "warning" | "error";
  title: string;
  message: string;
  items?: readonly string[];
}>) {
  const toneClass =
    tone === "error"
      ? resolveSurfaceInsetToneClass("error")
      : tone === "warning"
        ? resolveSurfaceInsetToneClass("warning")
        : tone === "success"
          ? resolveSurfaceInsetToneClass("success")
          : "border-border bg-surface text-foreground";

  return (
    <div className={cx("rounded-[0.85rem] border px-4 py-3 text-sm", toneClass)}>
      <p className="font-medium">{title}</p>
      <p className="mt-1 leading-6">{message}</p>
      {items && items.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function CircuitDefinitionEditorWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isNavigating, startTransition] = useTransition();
  const { session } = useAppSession();

  const selectedDefinitionId = parseDefinitionIdParam(searchParams.get("definitionId"));
  const [pendingIntent, setPendingIntent] = useState<PendingEditorIntent>(null);
  const {
    definitions,
    definitionsError,
    activeDefinition,
    activeDefinitionError,
    mutationStatus,
    saveDefinition,
    publishDefinition,
    cloneDefinition,
    removeDefinition,
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
      const parsedSource = formatCircuitNetlistSource(activeDefinition.source_text);
      form.reset({
        name: parsedSource.document?.name?.trim() || "",
        source_text: parsedSource.formattedSource || activeDefinition.source_text,
      });
    }
  }, [activeDefinition, form, selectedDefinitionId]);

  const sourceText = form.watch("source_text");
  const parsedSourceDraft = useMemo(() => parseCircuitNetlistSource(sourceText), [sourceText]);
  const definitionName = parsedSourceDraft.document?.name?.trim() || "";

  useEffect(() => {
    if (form.getValues("name") === definitionName) {
      return;
    }
    form.setValue("name", definitionName, {
      shouldDirty: false,
      shouldTouch: false,
      shouldValidate: false,
    });
  }, [definitionName, form]);

  async function handleFormat() {
    const formatted = formatCircuitNetlistSource(form.getValues("source_text"));
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

  const draftSurface = useMemo(
    () =>
      buildCircuitDefinitionDraftSurface({
        name: definitionName,
        sourceText,
      }),
    [definitionName, sourceText],
  );
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
  const isMutationPending = isCircuitDefinitionMutationPending(mutationStatus.state);
  const editorActionState = summarizeEditorDefinitionActionState({
    selectedDefinitionId,
    activeDefinition,
    isDirty: form.formState.isDirty,
    isMutationPending,
    isNavigating,
    hasBlockingLocalDiagnostics: draftSurface.blockingLocalDiagnostics.length > 0,
    canManageDefinitions: session?.capabilities.canManageDefinitions ?? false,
    runtimeMode: session?.runtimeMode ?? "online",
  });

  const activeDefinitionLabel =
    selectedDefinitionId === "new" ? "New Circuit Definition" : activeDefinition?.name ?? "Loading schema";
  const persistedStateToneClass =
    persistedPreviewSurface.persistedPreviewState.tone === "warning"
      ? resolveSurfaceInsetToneClass("warning")
      : persistedPreviewSurface.persistedPreviewState.tone === "accent"
        ? "border-primary/20 bg-primary/8 text-foreground"
        : "border-border bg-surface text-muted-foreground";
  const prioritizedNoticeToneClass =
    persistedPreviewSurface.prioritizedNoticeLane.tone === "error"
      ? resolveSurfaceInsetToneClass("error")
      : persistedPreviewSurface.prioritizedNoticeLane.tone === "warning"
        ? resolveSurfaceInsetToneClass("warning")
        : persistedPreviewSurface.prioritizedNoticeLane.tone === "success"
          ? resolveSurfaceInsetToneClass("success")
          : "border-border bg-background text-muted-foreground";

  const sourceNotice = useMemo(() => {
    if (draftSurface.blockingLocalDiagnostics.length > 0) {
      return {
        tone: "error" as const,
        title: "Local authoring errors",
        message: "Fix the blocking source issues before the next save can succeed.",
        items: draftSurface.blockingLocalDiagnostics.map(
          (diagnostic) => `${diagnostic.path}: ${diagnostic.message}`,
        ),
      };
    }

    if (draftSurface.serializerBoundary.willRewriteSourceName) {
      return {
        tone: "warning" as const,
        title: "Serializer boundary notice",
        message: draftSurface.serializerBoundary.detail,
        items:
          draftSurface.localDiagnostics.length > 0
            ? draftSurface.localDiagnostics.map(
                (diagnostic) => `${diagnostic.path}: ${diagnostic.message}`,
              )
            : undefined,
      };
    }

    if (draftSurface.localDiagnostics.length > 0) {
      return {
        tone: "warning" as const,
        title: "Local authoring notice",
        message: "The source is parseable, but local warnings still deserve review before save.",
        items: draftSurface.localDiagnostics.map(
          (diagnostic) => `${diagnostic.path}: ${diagnostic.message}`,
        ),
      };
    }

    return {
      tone: "success" as const,
      title: "Authoring ready",
      message: "Local source currently matches the canonical circuit-netlist contract.",
      items: undefined,
    };
  }, [draftSurface]);

  async function onSubmit(values: DefinitionFormValues) {
    const nextDraft = buildCircuitDefinitionDraft({
      name: values.name,
      sourceText: values.source_text,
    });

    if (!nextDraft.draft) {
      form.setError("source_text", {
        type: "validate",
        message:
          nextDraft.diagnostics[0]?.message ??
          "Source does not match the circuit-netlist contract.",
      });
      return;
    }

    const detail = await saveDefinition(nextDraft.draft, {
      definitionId: selectedDefinitionId,
      activeDefinition,
    });
    replaceDefinitionId(String(detail.definition_id));
    const persistedSource = formatCircuitNetlistSource(nextDraft.formattedSource);
    form.reset({
      name: persistedSource.document?.name?.trim() || "",
      source_text: persistedSource.formattedSource,
    });
  }

  async function handleConfirmedIntent() {
    if (!pendingIntent) {
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

  function discardChanges() {
    if (selectedDefinitionId === "new") {
      form.reset(emptyDefinitionForm);
      return;
    }

    if (activeDefinition) {
      const parsedSource = formatCircuitNetlistSource(activeDefinition.source_text);
      form.reset({
        name: parsedSource.document?.name?.trim() || "",
        source_text: parsedSource.formattedSource || activeDefinition.source_text,
      });
    }
  }

  async function handlePublish() {
    if (!activeDefinition) {
      return;
    }

    const detail = await publishDefinition(activeDefinition.definition_id);
    const parsedSource = formatCircuitNetlistSource(detail.source_text);
    form.reset({
      name: parsedSource.document?.name?.trim() || "",
      source_text: parsedSource.formattedSource,
    });
  }

  async function handleClone() {
    if (!activeDefinition) {
      return;
    }

    const detail = await cloneDefinition(activeDefinition.definition_id);
    replaceDefinitionId(String(detail.definition_id));
    const parsedSource = formatCircuitNetlistSource(detail.source_text);
    form.reset({
      name: parsedSource.document?.name?.trim() || "",
      source_text: parsedSource.formattedSource,
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
    <div className="space-y-6">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[2.05rem] font-semibold tracking-tight text-foreground">
            Schema Editor
          </h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            Author one active circuit definition at a time, then compare the draft against the
            last persisted backend validation output.
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

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="flex flex-col gap-4 border-b border-border/80 pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Active Schema
            </h2>
            <p className="mt-2 text-lg font-semibold text-foreground">{activeDefinitionLabel}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-full border border-border bg-surface px-3 py-1">
                {selectedDefinitionId === "new"
                  ? "Draft only"
                  : `Definition #${activeDefinition?.definition_id ?? "--"}`}
              </span>
              {activeDefinition ? (
                <>
                  <span className="rounded-full border border-border bg-surface px-3 py-1">
                    {activeDefinition.visibility_scope}
                  </span>
                  <span className="rounded-full border border-border bg-surface px-3 py-1">
                    {activeDefinition.lifecycle_state}
                  </span>
                </>
              ) : null}
              <span className="rounded-full border border-border bg-surface px-3 py-1">
                {persistedPreviewSurface.persistedPreviewState.label}
              </span>
              {typeof activeDefinition?.lineage_parent_id === "number" ? (
                <span className="rounded-full border border-border bg-surface px-3 py-1">
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
            {typeof selectedDefinitionId === "number" && session?.runtimeMode !== "local" ? (
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

        <div className="mt-4 rounded-[0.85rem] border px-4 py-3 text-sm">
          <div className={cx("rounded-[0.8rem] border px-4 py-3", persistedStateToneClass)}>
            {persistedPreviewSurface.persistedPreviewState.detail}
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <SummaryCard
            label="Components"
            value={String(draftSurface.localSummary.componentCount)}
          />
          <SummaryCard
            label="Topology Rows"
            value={String(draftSurface.localSummary.topologyCount)}
          />
          <SummaryCard
            label="Parameters"
            value={String(draftSurface.localSummary.parameterCount)}
          />
          <SummaryCard
            label="Persisted Notices"
            value={String(persistedPreviewSurface.validationSummary?.notice_count ?? 0)}
            detail={
              persistedPreviewSurface.validationSummary
                ? `Status: ${persistedPreviewSurface.validationSummary.status}`
                : "Pending save"
            }
          />
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.16fr)_minmax(340px,0.84fr)]">
        <form
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
                  <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold normal-case tracking-normal text-amber-700 dark:text-amber-200">
                    Unsaved changes
                  </span>
                ) : null}
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Edit the JSON source here. Saving refreshes the preview and notices below.
              </p>
            </div>

            <div className="mt-4">
              <InlineNotice
                tone={sourceNotice.tone}
                title={sourceNotice.title}
                message={sourceNotice.message}
                items={sourceNotice.items}
              />
            </div>

            <div className="mt-4 grid gap-4">
              <label className="grid gap-2 text-sm">
                <input type="hidden" {...form.register("name")} />
                <span className="flex items-center justify-between gap-3">
                  <span className="font-medium text-foreground">Canonical Source Name</span>
                  <button
                    type="button"
                    onClick={() => {
                      void handleFormat();
                    }}
                    disabled={!editorActionState.format.enabled}
                    title={editorActionState.format.reason}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Format JSON
                  </button>
                </span>
                <input
                  type="text"
                  value={definitionName}
                  disabled
                  readOnly
                  className="rounded-[0.8rem] border border-border bg-surface px-4 py-3 text-sm text-muted-foreground outline-none disabled:cursor-not-allowed disabled:opacity-100"
                />
                {form.formState.errors.name ? (
                  <span className="text-xs text-rose-700 dark:text-rose-300">
                    {form.formState.errors.name.message}
                  </span>
                ) : null}
              </label>

              <div className="grid gap-2 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-foreground">Source Text</span>
                  <span className="rounded-full border border-border bg-surface px-3 py-1 text-[11px] text-muted-foreground">
                    JSON syntax highlight
                  </span>
                </div>
                <div className="overflow-hidden rounded-[0.85rem] border border-border bg-background">
                  <Controller
                    name="source_text"
                    control={form.control}
                    render={({ field }) => (
                      <CodeMirror
                        value={field.value}
                        height="560px"
                        theme="dark"
                        extensions={[json()]}
                        onChange={(value) => field.onChange(value)}
                        className="text-sm leading-6"
                      />
                    )}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  `Cmd/Ctrl + Shift + F` rewrites the local draft into normalized JSON. It does not save.
                </p>
                {form.formState.errors.source_text ? (
                  <span className="text-xs text-rose-700 dark:text-rose-300">
                    {form.formState.errors.source_text.message}
                  </span>
                ) : null}
              </div>
            </div>
          </section>
        </form>

        <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
          <div className="border-b border-border/80 pb-4">
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Validation & Preview
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Checks and normalized output appear here after save.
            </p>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <SummaryCard
              label="Validation Status"
              value={
                persistedPreviewSurface.validationSummary
                  ? persistedPreviewSurface.validationSummary.status === "invalid"
                    ? "Invalid"
                    : persistedPreviewSurface.validationSummary.status === "warning"
                      ? "Warnings"
                      : "Checks"
                  : "Pending Save"
              }
            />
            <SummaryCard
              label="Notice Count"
              value={String(persistedPreviewSurface.validationSummary?.notice_count ?? 0)}
            />
            <SummaryCard
              label="Preview Artifacts"
              value={String(persistedPreviewSurface.previewArtifacts.length)}
            />
          </div>

          <div className="mt-4 rounded-[0.85rem] border px-4 py-4 text-sm">
            <div className={cx("rounded-[0.8rem] border px-4 py-3", prioritizedNoticeToneClass)}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{persistedPreviewSurface.prioritizedNoticeLane.title}</p>
                  <p className="mt-1 leading-6">
                    {persistedPreviewSurface.prioritizedNoticeLane.detail}
                  </p>
                </div>
                <span className="rounded-full border border-current/20 bg-background/60 px-3 py-1 text-[11px] uppercase tracking-[0.14em]">
                  {persistedPreviewSurface.prioritizedNoticeLane.kind}
                </span>
              </div>

              {persistedPreviewSurface.prioritizedNoticeLane.notices.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {persistedPreviewSurface.prioritizedNoticeLane.notices.map((notice) => (
                    <div
                      key={`${notice.code}-${notice.message}`}
                      className="rounded-[0.8rem] border border-current/15 bg-background/70 px-4 py-3"
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.16em]">
                        {notice.code} · {notice.source}
                      </p>
                      <p className="mt-2 text-sm leading-6">{notice.message}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="mt-4 rounded-[0.85rem] border border-border bg-surface px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Normalized Output</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Latest saved preview, kept expanded for inspection.
                </p>
              </div>
              <span className="rounded-full border border-border bg-background px-3 py-1 text-[11px] text-muted-foreground">
                Expanded
              </span>
            </div>

            {persistedPreviewSurface.normalizedPreview.fields.length > 0 ? (
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {persistedPreviewSurface.normalizedPreview.fields.map((field) => (
                  <div
                    key={field.key}
                    className="rounded-[0.8rem] border border-border bg-background px-4 py-3"
                  >
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      {field.label}
                    </p>
                    <p className="mt-2 break-words text-sm font-medium text-foreground">
                      {field.value}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="mt-4 rounded-[0.8rem] border border-border bg-background px-4 py-4">
              <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-muted-foreground">
                {persistedPreviewSurface.normalizedPreview.formattedOutput}
              </pre>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <SummaryCard
                label="Output Lines"
                value={String(persistedPreviewSurface.normalizedPreview.lineCount)}
              />
              <SummaryCard
                label="Structured Fields"
                value={String(persistedPreviewSurface.normalizedPreview.fieldCount)}
              />
            </div>
          </div>
        </section>
      </div>

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="border-b border-border/80 pb-4">
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Circuit Netlist Quick Reference
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Keep the component, unit, and topology rules nearby while you edit.
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
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {authoringRules.map((rule) => (
            <div
              key={rule}
              className="rounded-[0.85rem] border border-border bg-surface px-4 py-3 text-sm text-muted-foreground"
            >
              {rule}
            </div>
          ))}
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
