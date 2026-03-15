"use client";

import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

import { cx } from "@/features/shared/components/surface-kit";

type ShellSidePanelProps = Readonly<{
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  offsetTopClassName?: string;
}>;

export function ShellSidePanel({
  open,
  onClose,
  title,
  subtitle,
  children,
  className,
  offsetTopClassName = "top-[74px]",
}: ShellSidePanelProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close panel backdrop"
        className={cx(
          "fixed inset-x-0 bottom-0 z-40 bg-slate-950/42 backdrop-blur-[1px]",
          offsetTopClassName,
        )}
        onClick={onClose}
      />
      <aside
        className={cx(
          "fixed bottom-0 right-0 z-40 flex w-full max-w-[560px] flex-col border-l border-border bg-card shadow-[-24px_0_70px_rgba(15,23,42,0.24)]",
          offsetTopClassName,
          className,
        )}
        aria-modal="true"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4 border-b border-border/80 px-5 py-5">
          <div className="min-w-0">
            <p className="truncate text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              SUPERCONDUCTING CIRCUITS
            </p>
            <h2 className="mt-2 text-lg font-semibold text-foreground">{title}</h2>
            {subtitle ? (
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-border bg-surface text-foreground transition hover:border-primary/35 hover:bg-primary/8"
            aria-label={`Close ${title}`}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">{children}</div>
      </aside>
    </>
  );
}
