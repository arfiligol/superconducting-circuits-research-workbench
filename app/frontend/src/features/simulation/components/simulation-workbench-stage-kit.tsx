"use client";

import { useMemo } from "react";
import { EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { EditorView } from "@codemirror/view";
import { FileCode2, X } from "lucide-react";
import CodeMirror from "@uiw/react-codemirror";

import { vsCodeDarkEditorTheme } from "@/lib/codemirror-theme";
import {
  SurfaceTag,
  cx,
  resolveSurfaceInsetToneClass,
} from "@/features/shared/components/surface-kit";
import {
  type StageTone,
  type WorkflowStageState,
} from "@/features/simulation/lib/stage-state";
import type { TaskSummary } from "@/lib/api/tasks";

export function SummaryCard({
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

export function StageNotice({
  tone,
  title,
  message,
  actions,
}: Readonly<{
  tone: StageTone;
  title: string;
  message: string;
  actions?: React.ReactNode;
}>) {
  const toneClass =
    tone === "error"
      ? resolveSurfaceInsetToneClass("error")
      : tone === "warning"
        ? resolveSurfaceInsetToneClass("warning")
        : tone === "success"
          ? resolveSurfaceInsetToneClass("success")
          : tone === "primary"
            ? resolveSurfaceInsetToneClass("primary")
            : "border-border bg-surface text-foreground";

  return (
    <div className={cx("rounded-[0.95rem] border px-4 py-4 text-sm", toneClass)}>
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-2 leading-6">{message}</p>
      {actions ? <div className="mt-4 flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function ReadOnlyCodeSurface({
  label,
  detail,
  value,
  height,
}: Readonly<{
  label: string;
  detail?: string;
  value: string;
  height: string;
}>) {
  const extensions = useMemo(
    () => [json(), EditorState.readOnly.of(true), EditorView.editable.of(false), vsCodeDarkEditorTheme],
    [],
  );

  return (
    <div className="overflow-hidden rounded-[0.95rem] border border-border bg-background shadow-[0_8px_24px_rgba(15,23,42,0.08)]">
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {label}
          </p>
          {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
        </div>
        <FileCode2 className="h-4 w-4 text-muted-foreground" />
      </div>
      <CodeMirror
        value={value}
        height={height}
        theme="dark"
        editable={false}
        extensions={extensions}
        className="text-sm leading-6"
      />
    </div>
  );
}

export function WorkflowStageSection({
  step,
  title,
  description,
  status,
  actions,
  children,
}: Readonly<{
  step: number;
  title: string;
  description: string;
  status: WorkflowStageState;
  actions?: React.ReactNode;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-[1.15rem] border border-border bg-card px-5 py-5 shadow-[0_12px_30px_rgba(0,0,0,0.08)]">
      <div className="grid gap-5 lg:grid-cols-[56px_minmax(0,1fr)]">
        <div className="flex lg:justify-center">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-sm font-semibold text-primary">
            {step}
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex flex-col gap-3 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-foreground">{title}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <SurfaceTag tone={status.tone}>{status.label}</SurfaceTag>
              {actions}
            </div>
          </div>
          <div className="mt-4 space-y-4">{children}</div>
        </div>
      </div>
    </section>
  );
}

export function SetupSection({
  title,
  description,
  status,
  actions,
  children,
}: Readonly<{
  title: string;
  description: string;
  status?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-[1rem] border border-border bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.06)]">
      <div className="flex flex-col gap-3 border-b border-border/80 pb-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            {status}
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

export function SetupInputField({
  label,
  detail,
  children,
  error,
}: Readonly<{
  label: string;
  detail?: string;
  children: React.ReactNode;
  error?: string;
}>) {
  return (
    <label className="block rounded-[0.95rem] border border-border bg-background px-4 py-3 shadow-[0_1px_0_rgba(255,255,255,0.04)]">
      <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </span>
      {detail ? <span className="mt-1 block text-xs leading-5 text-muted-foreground">{detail}</span> : null}
      <div className="mt-3">{children}</div>
      {error ? <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{error}</p> : null}
    </label>
  );
}

export function CompactField({
  label,
  detail,
  headerAside,
  children,
  error,
  className,
}: Readonly<{
  label: string;
  detail?: string;
  headerAside?: React.ReactNode;
  children: React.ReactNode;
  error?: string;
  className?: string;
}>) {
  return (
    <label className={cx("block min-w-0", className)}>
      <span className="flex items-start justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </span>
        {headerAside ? (
          <span className="text-[11px] text-muted-foreground">{headerAside}</span>
        ) : null}
      </span>
      {detail ? <span className="mt-1 block text-xs leading-5 text-muted-foreground">{detail}</span> : null}
      <div className="mt-2">{children}</div>
      {error ? <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{error}</p> : null}
    </label>
  );
}

export function SetupTextInput(
  props: Readonly<React.InputHTMLAttributes<HTMLInputElement>>,
) {
  return (
    <input
      {...props}
      className={cx(
        "w-full rounded-[0.8rem] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15",
        props.className,
      )}
    />
  );
}

export function DraftOnlyBadge() {
  return <SurfaceTag>Local draft only</SurfaceTag>;
}

export function SetupSlideToggle({
  checked,
  onCheckedChange,
  label,
  description,
  className,
  disabled = false,
}: Readonly<{
  checked: boolean;
  onCheckedChange: (nextChecked: boolean) => void;
  label: string;
  description?: string;
  className?: string;
  disabled?: boolean;
}>) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => {
        if (!disabled) {
          onCheckedChange(!checked);
        }
      }}
      className={cx(
        "flex w-full cursor-pointer items-center justify-between gap-4 rounded-[0.95rem] border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-60",
        checked
          ? "border-primary/35 bg-primary/10"
          : "border-border bg-background hover:border-primary/25 hover:bg-primary/5",
        className,
      )}
    >
      <span className={cx("min-w-0", !disabled && "cursor-pointer")}>
        <span className={cx("block text-sm font-medium text-foreground", !disabled && "cursor-pointer")}>{label}</span>
        {description ? (
          <span
            className={cx(
              "mt-1 block text-xs leading-5 text-muted-foreground",
              !disabled && "cursor-pointer",
            )}
          >
            {description}
          </span>
        ) : null}
      </span>
      <span
        className={cx(
          "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition",
          checked
            ? "border-primary/30 bg-primary"
            : "border-border bg-muted/70",
          !disabled && "cursor-pointer",
        )}
      >
        <span
          className={cx(
            "inline-flex h-5 w-5 rounded-full bg-white shadow-[0_4px_12px_rgba(15,23,42,0.22)] transition-transform",
            checked ? "translate-x-6" : "translate-x-1",
            !disabled && "cursor-pointer",
          )}
        />
      </span>
    </button>
  );
}

export function OverlayDialog({
  open,
  title,
  description,
  children,
  onClose,
}: Readonly<{
  open: boolean;
  title: string;
  description: string;
  children: React.ReactNode;
  onClose: () => void;
}>) {
  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-3xl rounded-[1.1rem] border border-border bg-card shadow-[0_28px_90px_rgba(0,0,0,0.38)]">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/35 hover:bg-primary/10 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  );
}

export function StageTaskActions({
  task,
  resolvedTaskId,
  onViewTask,
}: Readonly<{
  task: TaskSummary | undefined;
  resolvedTaskId: number | null;
  onViewTask: (taskId: number) => void;
}>) {
  if (!task) {
    return null;
  }

  const isAttached = resolvedTaskId === task.taskId;

  return (
    <div className="flex flex-wrap gap-2">
      {isAttached ? (
        <SurfaceTag tone="primary">Attached to Page</SurfaceTag>
      ) : (
        <button
          type="button"
          onClick={() => {
            onViewTask(task.taskId);
          }}
          className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
        >
          Attach Run
        </button>
      )}
    </div>
  );
}
