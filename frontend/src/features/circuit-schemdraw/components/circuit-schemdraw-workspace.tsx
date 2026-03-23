"use client";

import { useMemo, useTransition } from "react";
import { json } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
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

import { SchemdrawSvgViewer } from "@/features/circuit-schemdraw/components/schemdraw-svg-viewer";
import { useCircuitSchemdrawData } from "@/features/circuit-schemdraw/hooks/use-circuit-schemdraw-data";
import { parseSchemdrawDefinitionIdParam } from "@/features/circuit-schemdraw/lib/definition-id";
import {
  buildSchemdrawEditorDiagnostics,
  createSchemdrawDiagnosticsExtension,
  summarizeSchemdrawEditorNotice,
} from "@/features/circuit-schemdraw/lib/editor-diagnostics";
import type { SchemdrawFailureDetail } from "@/features/circuit-schemdraw/lib/render";
import { resolveSchemdrawSelectionRecovery } from "@/features/circuit-schemdraw/lib/workflow";
import { AppInlineSelect } from "@/features/shared/components/app-select";
import {
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import {
  buildSchemaIdentityDescription,
  formatSchemaIdLabel,
  type CircuitDefinitionId,
} from "@/features/circuit-definition-editor/lib/schema-identity";
import { useDeveloperMode } from "@/lib/app-state";
import { vsCodeDarkEditorTheme } from "@/lib/codemirror-theme";

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

  if (phase === "validating") {
    return "primary" as const;
  }

  if (phase === "stale") {
    return "warning" as const;
  }

  if (phase === "syntax_error" || phase === "runtime_error" || phase === "request_error") {
    return "error" as const;
  }

  return "default" as const;
}

function failureTone(detail: SchemdrawFailureDetail) {
  return detail.kind === "relation_config" ? ("warning" as const) : ("error" as const);
}

function describeSchemdrawDiagnosticSource(
  source: SchemdrawFailureDetail["source"],
) {
  switch (source) {
    case "python_syntax":
      return "Python syntax";
    case "render_runtime":
      return "Render runtime";
    case "relation_config":
      return "Advanced mapping";
    case "request":
      return "Request";
    default:
      return "Diagnostic";
  }
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

function EditorHintNotice({
  tone,
  title,
  message,
}: Readonly<{
  tone: "default" | "warning" | "error";
  title: string;
  message: string;
}>) {
  return (
    <div
      className={cx(
        "rounded-[0.9rem] border px-4 py-3 text-sm shadow-[0_8px_20px_rgba(15,23,42,0.08)]",
        tone === "error"
          ? resolveSurfaceInsetToneClass("error")
          : tone === "warning"
            ? resolveSurfaceInsetToneClass("warning")
            : resolveSurfaceInsetToneClass("default"),
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cx(
            "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
            tone === "error"
              ? "border-rose-600/25 bg-rose-500/10 text-rose-900 dark:text-rose-200"
              : tone === "warning"
                ? "border-amber-500/25 bg-amber-500/10 text-amber-900 dark:text-amber-200"
                : "border-border bg-background text-foreground",
          )}
        >
          <FileCode2 className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-foreground/84 dark:text-foreground/82">
            {title}
          </p>
          <p className="mt-2 leading-6 text-foreground/82 dark:text-foreground/80">{message}</p>
        </div>
      </div>
    </div>
  );
}

function FailureDetailCard({
  detail,
  showDebugDisclosure,
  staleSvgVisible,
}: Readonly<{
  detail: SchemdrawFailureDetail;
  showDebugDisclosure: boolean;
  staleSvgVisible: boolean;
}>) {
  const metadataRows = [
    detail.errorCode ? { label: "Error Code", value: detail.errorCode } : null,
    detail.category ? { label: "Category", value: detail.category } : null,
    detail.statusCode ? { label: "Status", value: String(detail.statusCode) } : null,
    detail.source ? { label: "Source", value: detail.source } : null,
    detail.debugRef ? { label: "Debug Ref", value: detail.debugRef } : null,
    detail.line || detail.column
      ? {
          label: "Location",
          value: [detail.line ? `line ${detail.line}` : null, detail.column ? `column ${detail.column}` : null]
            .filter(Boolean)
            .join(" · "),
        }
      : null,
    detail.retryable !== null
      ? { label: "Retryable", value: detail.retryable ? "Yes" : "No" }
      : null,
  ].filter(Boolean) as Array<{ label: string; value: string }>;

  return (
    <div
      className={cx(
        "rounded-[0.95rem] border px-4 py-4 text-sm shadow-[0_10px_24px_rgba(15,23,42,0.08)]",
        resolveSurfaceInsetToneClass(failureTone(detail)),
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em]">{detail.title}</p>
          {detail.technicalMessage && detail.technicalMessage !== detail.userMessage ? (
            <div className="mt-2 rounded-[0.8rem] border border-current/15 bg-background/80 px-3 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground/76 dark:text-foreground/74">
                Error message
              </p>
              <p className="mt-2 font-mono text-xs leading-5 text-foreground/88 dark:text-foreground/84">
                {detail.technicalMessage}
              </p>
            </div>
          ) : null}
          <p className="mt-3 leading-6">{detail.userMessage}</p>
          {detail.source || detail.line || detail.column ? (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
              {detail.source ? (
                <SurfaceTag tone={failureTone(detail)}>
                  {describeSchemdrawDiagnosticSource(detail.source)}
                </SurfaceTag>
              ) : null}
              {detail.line ? <SurfaceTag tone="default">line {detail.line}</SurfaceTag> : null}
              {detail.column ? <SurfaceTag tone="default">column {detail.column}</SurfaceTag> : null}
            </div>
          ) : null}
        </div>
        <SurfaceTag tone={failureTone(detail)}>
          {detail.kind === "transport"
            ? "Transport failure"
            : detail.kind === "backend_error"
              ? "Backend envelope error"
              : detail.kind === "relation_config"
                ? "Relation config blocked"
                : detail.kind === "runtime_error"
                  ? "Runtime diagnostic"
                  : "Syntax diagnostic"}
        </SurfaceTag>
      </div>

      <p className="mt-3 text-xs leading-5 text-foreground/78 dark:text-foreground/76">
        {staleSvgVisible
          ? "The last successful SVG stays visible until a newer valid backend response replaces it."
          : "No SVG preview is available until the render path succeeds."}
      </p>

      {showDebugDisclosure ? (
        <details className="mt-4 rounded-[0.85rem] border border-current/15 bg-background/70 px-4 py-3">
          <summary className="cursor-pointer list-none text-xs font-semibold uppercase tracking-[0.16em] text-foreground marker:hidden">
            Debug detail
          </summary>
          {detail.technicalMessage && detail.technicalMessage === detail.userMessage ? (
            <p className="mt-3 rounded-[0.8rem] border border-border/80 bg-background px-3 py-3 font-mono text-xs leading-5 text-foreground/86 dark:text-foreground/82">
              {detail.technicalMessage}
            </p>
          ) : null}
          {metadataRows.length > 0 ? (
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
              {metadataRows.map((row) => (
                <div
                  key={row.label}
                  className="rounded-[0.8rem] border border-border/80 bg-background px-3 py-3"
                >
                  <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    {row.label}
                  </dt>
                  <dd className="mt-1 break-words text-sm font-medium text-foreground">
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </details>
      ) : null}
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
  const { enabled: developerModeEnabled } = useDeveloperMode();
  const selectionRecovery = resolveSchemdrawSelectionRecovery(
    requestedDefinitionId,
    resolvedDefinitionId,
    definitions,
  );
  const previewTone = renderTone(renderSurface.phase);
  const { sourceDiagnostics, relationDiagnostics } = useMemo(
    () => buildSchemdrawEditorDiagnostics(renderSurface.diagnostics),
    [renderSurface.diagnostics],
  );
  const sourceEditorExtensions = useMemo(
    () => [
      python(),
      vsCodeDarkEditorTheme,
      createSchemdrawDiagnosticsExtension({
        diagnostics: sourceDiagnostics,
        developerModeEnabled,
      }),
    ],
    [developerModeEnabled, sourceDiagnostics],
  );
  const relationEditorExtensions = useMemo(
    () => [
      json(),
      vsCodeDarkEditorTheme,
      createSchemdrawDiagnosticsExtension({
        diagnostics: relationDiagnostics,
        developerModeEnabled,
      }),
    ],
    [developerModeEnabled, relationDiagnostics],
  );
  const sourceEditorNotice = useMemo(
    () =>
      summarizeSchemdrawEditorNotice({
        diagnostics: sourceDiagnostics,
        failureDetail: renderSurface.failureDetail,
        target: "source",
        developerModeEnabled,
      }),
    [developerModeEnabled, renderSurface.failureDetail, sourceDiagnostics],
  );
  const relationEditorNotice = useMemo(
    () =>
      summarizeSchemdrawEditorNotice({
        diagnostics: relationDiagnostics,
        failureDetail: renderSurface.failureDetail,
        target: "relation",
        developerModeEnabled,
      }),
    [developerModeEnabled, relationDiagnostics, renderSurface.failureDetail],
  );

  function replaceDefinitionId(definitionId: CircuitDefinitionId | null) {
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
            Edit source, render again, and inspect the latest SVG preview plus diagnostics.
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
          {resolvedDefinitionId !== null ? (
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
              Choose the saved schema you want to keep beside this preview.
            </p>
          </div>
          <SurfaceTag tone={previewTone}>{renderSurface.statusLabel}</SurfaceTag>
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
              <p className="mt-1 text-foreground/78 dark:text-foreground/76">{selectionRecovery.message}</p>
            </div>
          ) : null}
        </div>

        <div className="mt-4 rounded-[0.95rem] border border-border bg-surface px-4 py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Linked Schema
              </p>
              <div className="mt-2 max-w-2xl">
                <AppInlineSelect
                  ariaLabel="Linked schema"
                  value={resolvedDefinitionId === null ? "" : String(resolvedDefinitionId)}
                  disabled={isDefinitionsLoading || isNavigating}
                  placeholder={isDefinitionsLoading ? "Loading schemas..." : "No linked schema"}
                  onChange={(nextValue) => {
                    replaceDefinitionId(nextValue || null);
                  }}
                  options={[
                    { value: "", label: "No linked schema" },
                    ...(definitions ?? []).map((definition) => ({
                      value: String(definition.definition_id),
                      label: definition.name,
                      description: buildSchemaIdentityDescription({
                        definitionId: definition.definition_id,
                        createdAt: definition.created_at,
                      }),
                    })),
                  ]}
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-2 text-[11px]">
              <SurfaceTag tone="default">
                {resolvedDefinitionId === null
                  ? "Schema ID --"
                  : formatSchemaIdLabel(resolvedDefinitionId)}
              </SurfaceTag>
              <SurfaceTag tone={selectionRecovery ? "warning" : resolvedDefinitionId === null ? "default" : "primary"}>
                {isDefinitionTransitioning
                  ? "Refreshing"
                  : resolvedDefinitionId === null
                    ? "Unlinked"
                    : selectionRecovery
                      ? "Recovered"
                      : "Attached"}
              </SurfaceTag>
              <SurfaceTag tone={previewTone}>
                {renderSurface.isStale ? "Stale preview" : renderSurface.statusLabel}
              </SurfaceTag>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full border border-border px-3 py-1">
            {selectedDefinitionSummary?.name ?? "No linked schema"}
          </span>
          {selectedDefinitionSummary ? (
            <span className="rounded-full border border-border px-3 py-1">
              {formatSchemaIdLabel(selectedDefinitionSummary.definition_id)}
            </span>
          ) : null}
          {selectedDefinitionSummary ? (
            <span className="rounded-full border border-border px-3 py-1">
              {selectedDefinitionSummary.created_at}
            </span>
          ) : null}
          <span className="rounded-full border border-border px-3 py-1">
            {activeDefinition?.element_count ?? 0} elements
          </span>
          <span className="rounded-full border border-border px-3 py-1">
            {activeDefinition?.preview_artifact_count ?? 0} preview artifacts
          </span>
          <span className="rounded-full border border-border px-3 py-1">
            latest render
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
          {relationEditorNotice ? (
            <div className="mt-3">
              <EditorHintNotice
                tone={relationEditorNotice.tone}
                title={relationEditorNotice.title}
                message={relationEditorNotice.message}
              />
            </div>
          ) : null}
          <div className="mt-3 overflow-hidden rounded-[0.8rem] border border-border bg-background">
            <CodeMirror
              value={draft.relationText}
              height="180px"
              theme="dark"
              onChange={updateRelationText}
              extensions={relationEditorExtensions}
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
                Editing makes the preview stale until you render again.
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

          {sourceEditorNotice ? (
            <div className="mt-4">
              <EditorHintNotice
                tone={sourceEditorNotice.tone}
                title={sourceEditorNotice.title}
                message={sourceEditorNotice.message}
              />
            </div>
          ) : null}

          <div className="mt-4 overflow-hidden rounded-[0.8rem] border border-border bg-background">
            <CodeMirror
              value={draft.sourceText}
              height="520px"
              theme="dark"
              onChange={updateSourceText}
              extensions={sourceEditorExtensions}
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
                The latest successful render stays visible until a newer valid one replaces it.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <SurfaceTag tone={previewTone}>{renderSurface.statusLabel}</SurfaceTag>
              {renderSurface.isStale ? (
                <SurfaceTag tone="warning">Stale preview</SurfaceTag>
              ) : null}
              {renderSurface.requestId ? (
                <SurfaceTag tone="default">{renderSurface.requestId}</SurfaceTag>
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

          {renderSurface.failureDetail ? (
            <div className="mt-4">
              <FailureDetailCard
                detail={renderSurface.failureDetail}
                showDebugDisclosure={false}
                staleSvgVisible={renderSurface.svg !== null}
              />
            </div>
          ) : null}

          {renderSurface.svg ? (
            <SchemdrawSvgViewer
              svg={renderSurface.svg}
              previewMetadata={renderSurface.previewMetadata ?? null}
            />
          ) : (
            <div className="mt-4 flex min-h-[520px] items-center justify-center rounded-[0.8rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
              {renderSurface.failureDetail
                ? "No rendered SVG is available. Resolve the render failure and request a new preview."
                : "No rendered SVG yet. Update the source and request a backend render."}
            </div>
          )}

          <div className="mt-4 rounded-[0.8rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-2 text-foreground">
              {renderSurface.phase === "rendered" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 dark:text-emerald-300" />
              ) : (
                <AlertTriangle
                  className={cx(
                    "h-4 w-4",
                    renderSurface.failureDetail ? "text-rose-700 dark:text-rose-300" : "text-amber-700 dark:text-amber-300",
                  )}
                />
              )}
              <span>
                {renderSurface.phase === "rendered"
                  ? "Latest backend response is applied."
                  : renderSurface.failureDetail
                    ? "Preview is waiting for a valid backend response after the latest failure."
                    : "Preview is waiting for a successful latest response."}
              </span>
            </div>
            <p className="mt-3">Current document version: {draft.documentVersion}.</p>
            {renderSurface.appliedDocumentVersion ? (
              <p className="mt-2">Last applied version: {renderSurface.appliedDocumentVersion}.</p>
            ) : null}
            {renderSurface.previewMetadata?.view_box ? (
              <p className="mt-2 font-mono text-xs">{renderSurface.previewMetadata.view_box}</p>
            ) : null}
          </div>
        </section>
      </section>

      <section className="rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="border-b border-border/80 pb-4">
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Render Diagnostics
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Diagnostics come from the latest render or request error.
          </p>
        </div>

        {renderSurface.failureDetail ? (
          <div className="mt-4">
            <FailureDetailCard
              detail={renderSurface.failureDetail}
              showDebugDisclosure={developerModeEnabled}
              staleSvgVisible={renderSurface.svg !== null}
            />
          </div>
        ) : null}

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
                  <SurfaceTag
                    tone={
                      diagnostic.severity === "error"
                        ? "error"
                        : diagnostic.severity === "warning"
                          ? "warning"
                          : "primary"
                    }
                  >
                    {describeSchemdrawDiagnosticSource(diagnostic.source)}
                  </SurfaceTag>
                  {diagnostic.blocking ? <SurfaceTag tone="default">blocking</SurfaceTag> : null}
                  {diagnostic.line ? <SurfaceTag tone="default">line {diagnostic.line}</SurfaceTag> : null}
                  {diagnostic.column ? <SurfaceTag tone="default">column {diagnostic.column}</SurfaceTag> : null}
                  {developerModeEnabled ? (
                    <>
                      <SurfaceTag tone="default">{diagnostic.code}</SurfaceTag>
                      <SurfaceTag tone="default">{diagnostic.source}</SurfaceTag>
                    </>
                  ) : null}
                </div>
                <p className="mt-2 text-foreground/86 dark:text-foreground/84">{diagnostic.message}</p>
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
          <CodeMirror
            value={activeDefinition?.normalized_output ?? '{\n  "linked_schema": "pending"\n}'}
            editable={false}
            basicSetup={{
              lineNumbers: true,
              foldGutter: false,
              highlightActiveLine: false,
              highlightActiveLineGutter: false,
            }}
            extensions={[json()]}
            theme={vsCodeDarkEditorTheme}
            className="overflow-hidden rounded-[0.9rem] border border-border/80 bg-background text-sm"
          />
        </div>
      </section>
    </div>
  );
}
