import { RefreshCcw, Search } from "lucide-react";

import type { ResearchWorkflowSurfaceSummary } from "@/lib/research-workflow-surface";

import { AppSelectField } from "./app-select";
import { SurfaceHeader, SurfacePanel, SurfaceStat, SurfaceTag, cx } from "./surface-kit";

type SurfaceTone = "default" | "primary" | "success" | "warning";

export type ResearchWorkflowHeroTag = Readonly<{
  label: string;
  tone?: SurfaceTone;
}>;

export type ResearchWorkflowHeroStat = Readonly<{
  label: string;
  value: string;
  tone?: "default" | "primary";
}>;

type ResearchWorkflowHeroProps = Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  contextTags: readonly ResearchWorkflowHeroTag[];
  submitAuthorityLabel: string;
  stats: readonly ResearchWorkflowHeroStat[];
}>;

type ResearchTaskQueuePanelProps = Readonly<{
  title: string;
  description: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder: string;
  scopeValue: string;
  onScopeChange: (value: string) => void;
  scopeOptions: readonly Readonly<{
    label: string;
    value: string;
  }>[];
  statusValue: string;
  onStatusChange: (value: string) => void;
  statusOptions: readonly Readonly<{
    label: string;
    value: string;
  }>[];
  summaryLabel: string;
  summaryTags?: readonly ResearchWorkflowHeroTag[];
  isRefreshing: boolean;
  onRefresh: () => void;
  isEmpty: boolean;
  emptyMessage: string;
  children: React.ReactNode;
}>;

type ResearchWorkflowOverviewPanelProps = Readonly<{
  title?: string;
  description?: string;
  summary: ResearchWorkflowSurfaceSummary;
  narrative: string;
}>;

export function ResearchWorkflowHero({
  eyebrow,
  title,
  description,
  contextTags,
  submitAuthorityLabel,
  stats,
}: ResearchWorkflowHeroProps) {
  return (
    <section className="space-y-6">
      <SurfaceHeader eyebrow={eyebrow} title={title} description={description} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(180px,0.3fr)_minmax(180px,0.3fr)_minmax(180px,0.3fr)]">
        <div className="rounded-[1rem] border border-border bg-card px-4 py-4 shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            {contextTags.map((tag, index) => (
              <SurfaceTag key={`${tag.label}-${index}`} tone={tag.tone ?? "default"}>
                {tag.label}
              </SurfaceTag>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{submitAuthorityLabel}</p>
        </div>
        {stats.map((stat) => (
          <SurfaceStat
            key={stat.label}
            label={stat.label}
            value={stat.value}
            tone={stat.tone ?? "default"}
          />
        ))}
      </div>
    </section>
  );
}

export function ResearchTaskQueuePanel({
  title,
  description,
  searchValue,
  onSearchChange,
  searchPlaceholder,
  scopeValue,
  onScopeChange,
  scopeOptions,
  statusValue,
  onStatusChange,
  statusOptions,
  summaryLabel,
  summaryTags = [],
  isRefreshing,
  onRefresh,
  isEmpty,
  emptyMessage,
  children,
}: ResearchTaskQueuePanelProps) {
  return (
    <SurfacePanel
      title={title}
      description={description}
      actions={
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCcw className={cx("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
          Refresh queue
        </button>
      }
    >
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px]">
        <label className="rounded-[0.9rem] border border-border bg-surface px-4 py-3">
          <span className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
            <Search className="h-3.5 w-3.5" />
            Search
          </span>
          <input
            value={searchValue}
            onChange={(event) => {
              onSearchChange(event.target.value);
            }}
            placeholder={searchPlaceholder}
            className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </label>

        <AppSelectField
          label="Scope"
          value={scopeValue}
          onChange={onScopeChange}
          options={scopeOptions}
        />

        <AppSelectField
          label="Status"
          value={statusValue}
          onChange={onStatusChange}
          options={statusOptions}
        />
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 rounded-[0.9rem] border border-border bg-surface px-4 py-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2">
          <span>{summaryLabel}</span>
          {summaryTags.map((tag, index) => (
            <SurfaceTag key={`${tag.label}-${index}`} tone={tag.tone ?? "default"}>
              {tag.label}
            </SurfaceTag>
          ))}
        </div>
        <SurfaceTag tone={isRefreshing ? "primary" : "default"}>
          {isRefreshing ? "Refreshing" : "Stable"}
        </SurfaceTag>
      </div>

      <div className="mt-4 space-y-3">{children}</div>

      {isEmpty ? (
        <div className="mt-4 rounded-[0.9rem] border border-dashed border-border bg-surface px-4 py-5 text-sm text-muted-foreground">
          {emptyMessage}
        </div>
      ) : null}
    </SurfacePanel>
  );
}

export function ResearchWorkflowOverviewPanel({
  title = "Research Workflow State",
  description = "Read attachment, dispatch, event, and result authority in one sequence before drilling into the persisted task detail panels.",
  summary,
  narrative,
}: ResearchWorkflowOverviewPanelProps) {
  return (
    <SurfacePanel title={title} description={description}>
      <div className="grid gap-3 md:grid-cols-4">
        {summary.cards.map((card) => (
          <div
            key={card.id}
            className={cx(
              "rounded-[0.9rem] border px-4 py-4",
              card.tone === "success" && "border-emerald-500/20 bg-emerald-500/10",
              card.tone === "primary" && "border-primary/20 bg-primary/10",
              card.tone === "warning" && "border-amber-500/25 bg-amber-500/10",
              card.tone === "default" && "border-border bg-surface",
            )}
          >
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              {card.label}
            </p>
            <p className="mt-2 text-lg font-semibold text-foreground">{card.value}</p>
            <p className="mt-2 text-sm text-muted-foreground">{card.detail}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-[0.9rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">{narrative}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
          <SurfaceTag tone={summary.statusTone}>{summary.statusLabel}</SurfaceTag>
          <SurfaceTag tone="default">{summary.persistenceLabel}</SurfaceTag>
          <SurfaceTag tone={summary.errorEventCount > 0 ? "warning" : "default"}>
            Error events {summary.errorEventCount}
          </SurfaceTag>
          <SurfaceTag tone={summary.warningEventCount > 0 ? "warning" : "default"}>
            Warning events {summary.warningEventCount}
          </SurfaceTag>
          <SurfaceTag
            tone={summary.materializedHandleCount > 0 ? "success" : "default"}
          >
            Materialized {summary.materializedHandleCount}
          </SurfaceTag>
          <SurfaceTag tone={summary.pendingHandleCount > 0 ? "primary" : "default"}>
            Pending {summary.pendingHandleCount}
          </SurfaceTag>
          <SurfaceTag tone={summary.hasTracePayload ? "success" : "default"}>
            Trace payload {summary.hasTracePayload ? "attached" : "pending"}
          </SurfaceTag>
        </div>
      </div>
    </SurfacePanel>
  );
}
