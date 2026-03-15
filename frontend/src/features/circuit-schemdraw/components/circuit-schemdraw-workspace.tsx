"use client";

import { useTransition } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileCode2,
  LoaderCircle,
  RefreshCcw,
  Shapes,
  WandSparkles,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import CodeMirror from "@uiw/react-codemirror";

import { useCircuitSchemdrawData } from "@/features/circuit-schemdraw/hooks/use-circuit-schemdraw-data";
import { parseSchemdrawDefinitionIdParam } from "@/features/circuit-schemdraw/lib/definition-id";
import { resolveSchemdrawSelectionRecovery } from "@/features/circuit-schemdraw/lib/workflow";
import { AppSelectField } from "@/features/shared/components/app-select";
import { cx, resolveSurfaceInsetToneClass } from "@/features/shared/components/surface-kit";

function definitionSearchHref(
  pathname: string,
  searchParamsValue: string,
  definitionId: string | null,
) {
  const params = new URLSearchParams(searchParamsValue);
  if (definitionId) {
    params.set("definitionId", definitionId);
  } else {
    params.delete("definitionId");
  }

  const nextSearch = params.toString();
  return nextSearch ? `${pathname}?${nextSearch}` : pathname;
}

function renderTone(phase: string) {
  if (phase === "rendered") {
    return "success" as const;
  }

  if (phase === "syntax_error" || phase === "runtime_error" || phase === "request_error") {
    return "warning" as const;
  }

  if (phase === "validating") {
    return "primary" as const;
  }

  return "default" as const;
}

export function CircuitSchemdrawWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isNavigating, startTransition] = useTransition();

  const requestedDefinitionId = searchParams.get("definitionId");
  const rawDefinitionId = parseSchemdrawDefinitionIdParam(requestedDefinitionId);
  const {
    definitions,
    definitionsError,
    isDefinitionsLoading,
    resolvedDefinitionId,
    selectedDefinitionSummary,
    activeDefinition,
    activeDefinitionError,
    isDefinitionTransitioning,
    draft,
    renderSurface,
    isRendering,
    updateSourceText,
    updateRelationText,
    resetDraft,
    renderNow,
  } = useCircuitSchemdrawData(rawDefinitionId);
  const selectionRecovery = resolveSchemdrawSelectionRecovery(
    requestedDefinitionId,
    resolvedDefinitionId,
    definitions,
  );

  function replaceDefinitionId(definitionId: number | null) {
    startTransition(() => {
      router.replace(
        definitionSearchHref(
          pathname,
          searchParams.toString(),
          definitionId === null ? null : String(definitionId),
        ),
        {
          scroll: false,
        },
      );
    });
  }

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[2.05rem] font-semibold tracking-tight text-foreground">
            Circuit Schemdraw
          </h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
            Use Schemdraw as a request/response authoring assist surface: edit Python source,
            edit relation JSON, send a backend render snapshot, and inspect diagnostics plus the
            latest SVG preview without touching the task queue.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              router.push("/schemas");
            }}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-4 py-2.5 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Catalog
          </button>
          {typeof resolvedDefinitionId === "number" ? (
            <button
              type="button"
              onClick={() => {
                router.push(`/circuit-definition-editor?definitionId=${resolvedDefinitionId}`);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-4 py-2.5 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              <Shapes className="h-4 w-4" />
              Open Schema Editor
            </button>
          ) : null}
        </div>
      </section>

      {definitionsError ? (
        <div className={cx("rounded-[1rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
          Unable to load linked schemas. {definitionsError.message}
        </div>
      ) : null}

      {activeDefinitionError ? (
        <div className={cx("rounded-[1rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
          Unable to load linked schema detail. {activeDefinitionError.message}
        </div>
      ) : null}

      {selectionRecovery ? (
        <div
          className={cx(
            "rounded-[1rem] border px-4 py-3 text-sm",
            selectionRecovery.tone === "warning"
              ? "border-amber-500/30 bg-amber-500/8 text-foreground"
              : "border-border bg-surface text-muted-foreground",
          )}
        >
          <p className="font-medium">{selectionRecovery.title}</p>
          <p className="mt-1">{selectionRecovery.message}</p>
        </div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(340px,0.88fr)_minmax(0,1.12fr)]">
        <div className="space-y-4">
          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Linked Schema Context
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Schemdraw preview can attach a canonical schema snapshot, but preview authority
                  still comes from backend render responses, not persisted tasks.
                </p>
              </div>
              <span
                className={cx(
                  "rounded-full px-3 py-1 text-xs font-medium",
                  renderTone(renderSurface.phase) === "success" &&
                    "bg-emerald-500/12 text-emerald-800 dark:text-emerald-200",
                  renderTone(renderSurface.phase) === "primary" && "bg-primary/10 text-primary",
                  renderTone(renderSurface.phase) === "warning" &&
                    "bg-amber-500/12 text-amber-800 dark:text-amber-200",
                  renderTone(renderSurface.phase) === "default" && "bg-surface text-muted-foreground",
                )}
              >
                {renderSurface.statusLabel}
              </span>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_140px_140px]">
              <AppSelectField
                label="Linked Schema"
                value={resolvedDefinitionId === null ? "" : String(resolvedDefinitionId)}
                disabled={isDefinitionsLoading || isNavigating}
                placeholder={isDefinitionsLoading ? "Loading schemas..." : "No linked schema"}
                onChange={(nextValue) => {
                  replaceDefinitionId(nextValue ? Number(nextValue) : null);
                }}
                options={[
                  { value: "", label: "No linked schema" },
                  ...(definitions ?? []).map((definition) => ({
                    value: String(definition.definition_id),
                    label: definition.name,
                    description: `Definition #${definition.definition_id}`,
                  })),
                ]}
              />

              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Definition Id
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {resolvedDefinitionId ?? "--"}
                </p>
              </div>

              <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Source State
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {isDefinitionTransitioning
                    ? "Refreshing"
                    : resolvedDefinitionId === null
                      ? "Unlinked"
                      : selectionRecovery
                        ? "Recovered"
                        : "Attached"}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">
                {selectedDefinitionSummary?.name ?? "No linked schema selected"}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-border px-3 py-1">
                  {activeDefinition?.element_count ?? 0} elements
                </span>
                <span className="rounded-full border border-border px-3 py-1">
                  {activeDefinition?.preview_artifact_count ?? 0} preview artifacts
                </span>
                <span className="rounded-full border border-border px-3 py-1">
                  request/response preview only
                </span>
              </div>
            </div>
          </section>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Relation Config Editor
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Edit the JSON relation config that will be sent with the current Schemdraw source
                  snapshot.
                </p>
              </div>
              <button
                type="button"
                onClick={resetDraft}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
              >
                <RefreshCcw className="h-4 w-4" />
                Reset Template
              </button>
            </div>

            <div className="mt-4 overflow-hidden rounded-[0.8rem] border border-border bg-background">
              <CodeMirror
                value={draft.relationText}
                height="240px"
                theme="dark"
                onChange={updateRelationText}
                className="text-sm leading-6"
              />
            </div>
          </section>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="border-b border-border/80 pb-4">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Backend Diagnostics
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Diagnostics always come from the latest backend render response or request error.
                Older responses are ignored.
              </p>
            </div>

            {renderSurface.diagnostics.length > 0 ? (
              <div className="mt-4 space-y-3">
                {renderSurface.diagnostics.map((diagnostic, index) => (
                  <div
                    key={`${diagnostic.code}-${index}`}
                    className={cx(
                      "rounded-[0.9rem] border px-4 py-3 text-sm",
                      diagnostic.severity === "error"
                        ? resolveSurfaceInsetToneClass("error")
                        : diagnostic.severity === "warning"
                          ? resolveSurfaceInsetToneClass("warning")
                          : "border-border bg-surface text-muted-foreground",
                    )}
                  >
                    <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.16em]">
                      <span>{diagnostic.code}</span>
                      <span>{diagnostic.source}</span>
                      {diagnostic.blocking ? <span>blocking</span> : <span>non-blocking</span>}
                      {diagnostic.line ? <span>line {diagnostic.line}</span> : null}
                      {diagnostic.column ? <span>column {diagnostic.column}</span> : null}
                    </div>
                    <p className="mt-2">{diagnostic.message}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
                No diagnostics yet. Edit the source or click `Render Now` to request backend
                validation.
              </div>
            )}
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex flex-col gap-4 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Schemdraw Source Editor
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Any edit marks the current preview as stale. The frontend keeps the last SVG until
                  a newer backend response is accepted.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  void renderNow();
                }}
                disabled={isRendering}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRendering ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <WandSparkles className="h-4 w-4" />
                )}
                Render Now
              </button>
            </div>

            <div className="mt-4 overflow-hidden rounded-[0.8rem] border border-border bg-background">
              <CodeMirror
                value={draft.sourceText}
                height="360px"
                theme="dark"
                onChange={updateSourceText}
                className="text-sm leading-6"
              />
            </div>
          </section>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  SVG Preview
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Latest-only apply is enforced by `request_id` and `document_version`. Stale
                  previews stay visible until a newer successful response replaces them.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span
                  className={cx(
                    "rounded-full px-3 py-1 font-medium",
                    renderTone(renderSurface.phase) === "success" &&
                      "bg-emerald-500/12 text-emerald-800 dark:text-emerald-200",
                    renderTone(renderSurface.phase) === "primary" && "bg-primary/10 text-primary",
                    renderTone(renderSurface.phase) === "warning" &&
                      "bg-amber-500/12 text-amber-800 dark:text-amber-200",
                    renderTone(renderSurface.phase) === "default" && "bg-surface text-muted-foreground",
                  )}
                >
                  {renderSurface.statusLabel}
                </span>
                {renderSurface.isStale ? (
                  <span className="rounded-full bg-amber-500/12 px-3 py-1 text-amber-800 dark:text-amber-200">
                    Stale preview
                  </span>
                ) : null}
                {renderSurface.requestId ? (
                  <span className="rounded-full bg-surface px-3 py-1 text-muted-foreground">
                    {renderSurface.requestId}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Applied Version
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {renderSurface.appliedDocumentVersion ?? "--"}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Preview Width
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {renderSurface.previewMetadata?.width ?? "--"}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Preview Height
                </p>
                <p className="mt-2 text-lg font-semibold text-foreground">
                  {renderSurface.previewMetadata?.height ?? "--"}
                </p>
              </div>
            </div>

            {renderSurface.svg ? (
              <div className="mt-4 rounded-[0.8rem] border border-border bg-white p-4 text-slate-900">
                <div
                  className="overflow-auto"
                  dangerouslySetInnerHTML={{ __html: renderSurface.svg }}
                />
              </div>
            ) : (
              <div className="mt-4 rounded-[0.8rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
                No rendered SVG yet. The current draft will keep sending backend snapshots until a
                successful render response arrives.
              </div>
            )}

            <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2 text-foreground">
                {renderSurface.phase === "rendered" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-amber-700 dark:text-amber-300" />
                )}
                <span>
                  {renderSurface.phase === "rendered"
                    ? "Latest backend response is applied to the preview."
                    : "Preview is still awaiting a successful latest response."}
                </span>
              </div>
              <p className="mt-3">
                Current document version: {draft.documentVersion}. Older backend responses are
                ignored even if they arrive later.
              </p>
              {renderSurface.previewMetadata?.view_box ? (
                <p className="mt-2 font-mono text-xs">{renderSurface.previewMetadata.view_box}</p>
              ) : null}
            </div>
          </section>

          <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
            <div className="border-b border-border/80 pb-4">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Linked Schema Snapshot
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                This is read-only context from the selected persisted definition. Schemdraw requests
                can reference it, but this page does not save schema changes.
              </p>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Schema
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {selectedDefinitionSummary?.name ?? "--"}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Validation
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDefinition?.validation_status ?? "--"}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Preview Artifacts
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDefinition?.preview_artifact_count ?? 0}
                </p>
              </div>
              <div className="rounded-[0.8rem] border border-border bg-surface px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Source Lines
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {activeDefinition?.source_text.split("\n").length ?? 0}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-4">
              <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-muted-foreground">
                {activeDefinition?.normalized_output ?? '{\n  "linked_schema": "pending"\n}'}
              </pre>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
