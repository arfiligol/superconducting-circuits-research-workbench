"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, Info, X } from "lucide-react";

import {
  cx,
  resolveSurfaceInsetToneClass,
  type SurfaceInsetTone,
} from "@/features/shared/components/surface-kit";

type AppToastDraft = Readonly<{
  tone?: SurfaceInsetTone;
  title: string;
  message: string;
  durationMs?: number;
}>;

type AppToast = Readonly<{
  id: string;
  tone: SurfaceInsetTone;
  title: string;
  message: string;
  durationMs: number;
}>;

type AppToastContextValue = Readonly<{
  pushToast: (toast: AppToastDraft) => string;
  dismissToast: (id: string) => void;
}>;

const DEFAULT_DURATION_MS = 5200;

const AppToastContext = createContext<AppToastContextValue | null>(null);

function ToastIcon({ tone }: Readonly<{ tone: SurfaceInsetTone }>) {
  if (tone === "error") {
    return <CircleAlert className="h-4 w-4" />;
  }
  if (tone === "success") {
    return <CheckCircle2 className="h-4 w-4" />;
  }
  return <Info className="h-4 w-4" />;
}

function AppToastItem({
  toast,
  onDismiss,
}: Readonly<{
  toast: AppToast;
  onDismiss: (id: string) => void;
}>) {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      onDismiss(toast.id);
    }, toast.durationMs);

    return () => {
      window.clearTimeout(timer);
    };
  }, [onDismiss, toast.durationMs, toast.id]);

  return (
    <div
      className={cx(
        "pointer-events-auto w-full rounded-[1rem] border px-4 py-3 shadow-[0_20px_60px_rgba(15,23,42,0.22)] backdrop-blur-sm",
        resolveSurfaceInsetToneClass(toast.tone),
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <ToastIcon tone={toast.tone} />
            <p className="text-sm font-semibold text-foreground">{toast.title}</p>
          </div>
          <p className="mt-2 text-sm leading-6">{toast.message}</p>
        </div>
        <button
          type="button"
          aria-label="Dismiss notification"
          onClick={() => {
            onDismiss(toast.id);
          }}
          className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-current/15 bg-background/55 text-current transition hover:bg-background/80"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function AppToastProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [toasts, setToasts] = useState<readonly AppToast[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const pushToast = useCallback((toast: AppToastDraft) => {
    const id = `app-toast:${crypto.randomUUID()}`;
    setToasts((current) => [
      ...current,
      {
        id,
        tone: toast.tone ?? "default",
        title: toast.title,
        message: toast.message,
        durationMs: toast.durationMs ?? DEFAULT_DURATION_MS,
      },
    ]);
    return id;
  }, []);

  const value = useMemo<AppToastContextValue>(
    () => ({
      pushToast,
      dismissToast,
    }),
    [dismissToast, pushToast],
  );

  return (
    <AppToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-[120] flex justify-end sm:inset-x-auto sm:right-6 sm:w-full sm:max-w-sm">
        <div className="flex w-full flex-col gap-3">
          {toasts.map((toast) => (
            <AppToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
          ))}
        </div>
      </div>
    </AppToastContext.Provider>
  );
}

export function useAppToasts() {
  const context = useContext(AppToastContext);
  if (context === null) {
    throw new Error("useAppToasts must be used within AppToastProvider.");
  }
  return context;
}
