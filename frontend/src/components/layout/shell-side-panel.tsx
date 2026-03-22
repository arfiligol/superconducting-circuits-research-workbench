"use client";

import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { cx } from "@/features/shared/components/surface-kit";

type ShellSidePanelProps = Readonly<{
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  eyebrow?: string | null;
  children: ReactNode;
  className?: string;
  offsetTopClassName?: string;
  variant?: "context" | "account";
  interactionBoundaryRef?: RefObject<HTMLElement | null>;
}>;

export function ShellSidePanel({
  open,
  onClose,
  title,
  subtitle,
  eyebrow = "SUPERCONDUCTING CIRCUITS",
  children,
  className,
  offsetTopClassName = "top-[var(--shell-header-height)]",
  variant = "account",
  interactionBoundaryRef,
}: ShellSidePanelProps) {
  const isContextSurface = variant === "context";
  const panelRef = useRef<HTMLElement | null>(null);

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

  useEffect(() => {
    if (!open || variant !== "account") {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }

      if (panelRef.current?.contains(target)) {
        return;
      }

      if (interactionBoundaryRef?.current?.contains(target)) {
        return;
      }

      onClose();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [interactionBoundaryRef, onClose, open, variant]);

  useEffect(() => {
    if (!open || !isContextSurface) {
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousDocumentOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousDocumentOverflow;
    };
  }, [isContextSurface, open]);

  if (!open) {
    return null;
  }

  if (typeof document === "undefined") {
    return null;
  }

  const content = (
    <>
      {isContextSurface ? (
        <button
          type="button"
          aria-label="Close panel backdrop"
          className={cx(
            "fixed inset-x-0 bottom-0 z-40 bg-black/45 backdrop-blur-[8px] dark:bg-black/65",
            offsetTopClassName,
          )}
          onClick={onClose}
        />
      ) : null}
      <aside
        ref={panelRef}
        className={cx(
          "fixed flex flex-col overflow-hidden border border-border bg-card shadow-[0_28px_90px_rgba(15,23,42,0.22)]",
          isContextSurface
            ? "inset-x-4 top-[calc(var(--shell-header-height)+1rem)] bottom-4 z-45 mx-auto w-auto max-w-[min(1220px,calc(100vw-1.5rem))] overscroll-contain rounded-[1.4rem] border-border/90 bg-card/98 shadow-[0_36px_120px_rgba(15,23,42,0.34)] sm:inset-x-5 md:inset-x-7 md:top-[calc(var(--shell-header-height)+1.25rem)] md:bottom-5"
            : "right-0 top-[var(--shell-header-height)] z-[61] h-[calc(100dvh-var(--shell-header-height))] w-full max-w-[440px] rounded-l-[1.6rem] border-l border-border/85 bg-card/98 shadow-[-24px_0_70px_rgba(15,23,42,0.24)] backdrop-blur",
          className,
        )}
        aria-modal="true"
        role="dialog"
      >
        <div
          className={cx(
            "flex items-start justify-between gap-4 border-b border-border/80",
            isContextSurface ? "px-6 py-5" : "px-5 py-5",
          )}
        >
          <div className="min-w-0">
            {eyebrow ? (
              <p className="truncate text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                {eyebrow}
              </p>
            ) : null}
            <h2 className="mt-2 text-lg font-semibold text-foreground">{title}</h2>
            {subtitle ? (
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{subtitle}</p>
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

        <div
          className={cx(
            "min-h-0 flex-1 overflow-y-auto overscroll-contain",
            isContextSurface ? "px-6 py-5" : "px-5 py-5",
          )}
        >
          {children}
        </div>
      </aside>
    </>
  );

  return createPortal(content, document.body);
}
