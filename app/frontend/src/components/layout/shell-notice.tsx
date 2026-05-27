"use client";

import { cx } from "@/features/shared/components/surface-kit";

export type ShellNoticeTone = "info" | "success" | "warning" | "error";

type ShellNoticeProps = Readonly<{
  tone?: ShellNoticeTone;
  title?: string;
  children: React.ReactNode;
  className?: string;
}>;

export function resolveShellNoticeToneClass(tone: ShellNoticeTone = "info") {
  switch (tone) {
    case "success":
      return "border-emerald-500/40 bg-emerald-50/95 text-emerald-950 dark:border-emerald-500/45 dark:bg-emerald-950/45 dark:text-emerald-100";
    case "warning":
      return "border-amber-500/45 bg-amber-50/95 text-amber-950 dark:border-amber-400/45 dark:bg-amber-950/45 dark:text-amber-100";
    case "error":
      return "border-rose-600/45 bg-rose-50/95 text-rose-950 dark:border-rose-500/45 dark:bg-rose-950/45 dark:text-rose-100";
    case "info":
    default:
      return "border-primary/30 bg-primary/10 text-foreground";
  }
}

export function ShellNotice({
  tone = "info",
  title,
  children,
  className,
}: ShellNoticeProps) {
  return (
    <div
      className={cx(
        "rounded-[0.9rem] border px-4 py-3 text-sm shadow-[0_6px_18px_rgba(15,23,42,0.08)]",
        resolveShellNoticeToneClass(tone),
        className,
      )}
    >
      {title ? <p className="text-xs font-semibold uppercase tracking-[0.16em]">{title}</p> : null}
      <div className={title ? "mt-2" : undefined}>{children}</div>
    </div>
  );
}
