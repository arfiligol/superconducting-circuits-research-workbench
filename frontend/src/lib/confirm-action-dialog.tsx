"use client";

import type { ReactNode } from "react";
import { AlertTriangle, LoaderCircle } from "lucide-react";

import { cx } from "@/features/shared/components/surface-kit";

export type ConfirmActionDialogProps = Readonly<{
  open: boolean;
  title: string;
  description: string;
  details?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "default" | "destructive";
  isPending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}>;

export function ConfirmActionDialog({
  open,
  title,
  description,
  details,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "default",
  isPending = false,
  onCancel,
  onConfirm,
}: ConfirmActionDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/75 px-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-[1rem] border border-border bg-card px-5 py-5 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="flex items-start gap-3">
          <div
            className={cx(
              "mt-0.5 inline-flex h-10 w-10 items-center justify-center rounded-full border",
              tone === "destructive"
                ? "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-200"
                : "border-primary/30 bg-primary/10 text-primary",
            )}
          >
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
            {details ? <div className="mt-4">{details}</div> : null}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className={cx(
              "inline-flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
              tone === "destructive"
                ? "bg-rose-500/90 text-white hover:bg-rose-500"
                : "bg-primary text-primary-foreground hover:opacity-90",
            )}
          >
            {isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
