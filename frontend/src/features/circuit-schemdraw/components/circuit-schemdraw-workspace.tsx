"use client";

import { useTransition } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
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

function statusPillClass(tone: "default" | "primary" | "success" | "warning") {
  if (tone === "success") {
    return "bg-emerald-500/12 text-emerald-800 dark:text-emerald-200";
  }

  if (tone === "warning") {
    return "bg-amber-500/12 text-amber-800 dark:text-amber-200";
  }

  if (tone === "primary") {
    return "bg-primary/10 text-primary";
  }

  return "bg-surface text-muted-foreground";
}

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
    <div className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
      {detail ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{detail}</p> : null}
    </div>
  );
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
  const previewTone = renderTone(renderSurface.phase);

  function replaceDefinitionId(definitionId: number | null) {
    startTransition(() => {
      router.replace(
        definitionSearchHref(
          pathname,
          searchParams.toString(),
          definitionId === null ? null : String(definitionId),
        ),
        { scroll: false },
      );
    });
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[2rem] font-semibold tracking-tight text-foreground">
            Circuit Schemdraw
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Edit source in a request/response authoring assist surface, then inspect the latest SVG preview plus diagnostics.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              router.push("/schemas");
            }}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-4 py-2.5 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
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
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-4 py-2.5 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              <Shapes className="h-4 w-4" />
              Open Schema Editor
            </button>
          ) : null}
        </div>
      </section>

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="flex flex-col gap-4 border-b border-border/80 pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Linked Schema Context
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Attach one persisted schema as reference context for the current render request.
            </p>
          </div>
          <span className={cx("rounded-full px-3 py-1 text-xs font-medium", statusPillClass(previewTone))}>
            {renderSurface.statusLabel}
          </span>
        </div>

        <div className="mt-4 space-y-3">
          {definitionsError ? (
            <div className={cx("rounded-[0.95rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
              Unable to load linked schemas. {definitionsError.message}
            </div>
          ) : null}

          {activeDefinitionError ? (
            <div className={cx("rounded-[0.95rem] border px-4 py-3 text-sm", resolveSurfaceInsetToneClass("error"))}>
              Unable to load linked schema detail. {activeDefinitionError.message}
            </div>
          ) : null}

          {selectionRecovery ? (
            <div
              className={cx(
                "rounded-[0.95rem] border px-4 py-3 text-sm",
                selectionRecovery.tone === "warning"
                  ? resolveSurfaceInsetToneClass("warning")
                  : resolveSurfaceInsetToneClass("default"),
              )}
            >
              <p className="font-medium text-foreground">{selectionRecovery.title}</p>
              <p className="mt-1 text-muted-foreground">{selectionRecovery.message}</p>
            </div>
          ) : null}
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.35fr)_repeat(3,minmax(0,0.55fr))]">
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

          <SummaryCard
            label="Definition Id"
            value={resolvedDefinitionId === null ? "--" : String(resolvedDefinitionId)}
          />
          <SummaryCard
            label="Schema State"
            value={
              isDefinitionTransitioning
                ? "Refreshing"
                : resolvedDefinitionId === null
                  ? "Unlinked"
                  : selectionRecovery
                    ? "Recovered"
                    : "Attached"
            }
          />
          <SummaryCard
            label="Preview State"
            value={renderSurface.isStale ? "Stale" : renderSurface.statusLabel}
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full border border-border px-3 py-1">
            {selectedDefinitionSummary?.name ?? "No linked schema"}
          </span>
          <span className="rounded-full border border-border px-3 py-1">
            {activeDefinition?.element_count ?? 0} elements
          </span>
          <span className="rounded-full border border-border px-3 py-1">
            {activeDefinition?.preview_artifact_count ?? 0} preview artifacts
          </span>
          <span className="rounded-full border border-border px-3 py-1">
            backend render authority
          </span>
        </div>

        <details className="mt-4 rounded-[0.95rem] border border-border bg-surface px-4 py-4">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-foreground">
            <span>Advanced relation mapping</span>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </summary>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Optional JSON mapping sent with the source snapshot. Use it only when the preview needs extra label or relation metadata.
          </p>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={resetDraft}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10"
            >
              <RefreshCcw className="h-4 w-4" />
              Reset Template
            </button>
          </div>
          <div className="mt-3 overflow-hidden rounded-[0.8rem] border border-border bg-background">
            <CodeMirror
              value={draft.relationText}
              height="180px"
              theme="dark"
              onChange={updateRelationText}
              className="text-sm leading-6"
            />
          </div>
        </details>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
          <div className="flex flex-col gap-4 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Schemdraw Source Editor
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Editing marks the preview stale until a newer backend response is accepted.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void renderNow();
              }}
              disabled={isRendering}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
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
              height="520px"
              theme="dark"
              onChange={updateSourceText}
              className="text-sm leading-6"
            />
          </div>
        </section>

        <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
          <div className="flex flex-col gap-4 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                SVG Live Preview
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                The latest successful backend render stays visible until a newer valid response replaces it.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span className={cx("rounded-full px-3 py-1 font-medium", statusPillClass(previewTone))}>
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
            <SummaryCard
              label="Applied Version"
              value={renderSurface.appliedDocumentVersion ? String(renderSurface.appliedDocumentVersion) : "--"}
            />
            <SummaryCard
              label="Preview Width"
              value={renderSurface.previewMetadata?.width ? String(renderSurface.previewMetadata.width) : "--"}
            />
            <SummaryCard
              label="Preview Height"
              value={renderSurface.previewMetadata?.height ? String(renderSurface.previewMetadata.height) : "--"}
            />
          </div>

          {renderSurface.svg ? (
            <div className="mt-4 flex min-h-[520px] items-start justify-center overflow-auto rounded-[0.8rem] border border-border bg-white p-5 text-slate-900">
              <div
                className="max-w-full"
                dangerouslySetInnerHTML={{ __html: renderSurface.svg }}
              />
            </div>
          ) : (
            <div className="mt-4 flex min-h-[520px] items-center justify-center rounded-[0.8rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              No rendered SVG yet. Update the source and request a backend render.
            </div>
          )}

          <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-2 text-foreground">
              {renderSurface.phase === "rendered" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 dark:text-emerald-300" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-amber-700 dark:text-amber-300" />
              )}
              <span>
                {renderSurface.phase === "rendered"
                  ? "Latest backend response is applied."
                  : "Preview is waiting for a successful latest response."}
              </span>
            </div>
            <p className="mt-3">Current document version: {draft.documentVersion}.</p>
            {renderSurface.previewMetadata?.view_box ? (
              <p className="mt-2 font-mono text-xs">{renderSurface.previewMetadata.view_box}</p>
            ) : null}
          </div>
        </section>
      </section>

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="border-b border-border/80 pb-4">
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Backend Diagnostics
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Diagnostics come from the latest backend render response or request error.
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
            No diagnostics yet. Edit source or trigger a render to ask the backend for validation.
          </div>
        )}
      </section>

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="border-b border-border/80 pb-4">
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Linked Schema Snapshot
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Read-only reference from the selected persisted schema.
          </p>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <SummaryCard
            label="Schema"
            value={selectedDefinitionSummary?.name ?? "--"}
          />
          <SummaryCard
            label="Validation"
            value={activeDefinition?.validation_status ?? "--"}
          />
          <SummaryCard
            label="Preview Artifacts"
            value={String(activeDefinition?.preview_artifact_count ?? 0)}
          />
          <SummaryCard
            label="Source Lines"
            value={String(activeDefinition?.source_text.split("\n").length ?? 0)}
          />
        </div>

        <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-4">
          <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-muted-foreground">
            {activeDefinition?.normalized_output ?? '{\n  "linked_schema": "pending"\n}'}
          </pre>
        </div>
      </section>
    </div>
  );
}
