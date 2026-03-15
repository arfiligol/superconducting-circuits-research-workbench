"use client";

import { AlertTriangle, ChevronRight, UserRound } from "lucide-react";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";

import { WorkspaceAccountPanel } from "@/components/layout/workspace-account-panel";
import { WorkspaceStatusStrip } from "@/components/layout/workspace-status-strip";
import {
  resolveShellAuthSummary,
  resolveShellUserInitials,
} from "@/components/layout/workspace-shell-contract";
import { cx } from "@/features/shared/components/surface-kit";
import { useAppSession } from "@/lib/app-state";
import { resolveWorkspacePageIdentity } from "@/lib/navigation";

export function WorkspaceHeader() {
  const pathname = usePathname();
  const [activePanel, setActivePanel] = useState<"account" | "context" | null>(null);
  const { session, sessionError, status } = useAppSession();
  const identity = resolveWorkspacePageIdentity(pathname);
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const initials = resolveShellUserInitials(authSummary.triggerName);
  const accountTriggerStatus = useMemo(() => {
    if (authSummary.state === "authenticated") {
      return {
        label: session?.user?.displayName ?? authSummary.triggerName,
        detail: session?.workspace.displayName ?? "Workspace pending",
        tone: "success" as const,
      };
    }

    if (authSummary.state === "loading") {
      return {
        label: "Resolving session",
        detail: "Checking shell authority",
        tone: "info" as const,
      };
    }

    if (authSummary.state === "anonymous") {
      return {
        label: "Anonymous session",
        detail: "Sign in",
        tone: "warning" as const,
      };
    }

    return {
      label: "Session warning",
      detail: "Recover",
      tone: "error" as const,
    };
  }, [authSummary, session]);

  return (
    <>
      <div className="flex min-w-0 flex-1 items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            SUPERCONDUCTING CIRCUITS
          </p>
          <div className="mt-2 flex min-w-0 flex-wrap items-center gap-2 sm:flex-nowrap">
            <span className="inline-flex shrink-0 rounded-full border border-border bg-surface px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              {identity.sectionLabel}
            </span>
            <ChevronRight className="hidden h-3.5 w-3.5 shrink-0 text-muted-foreground sm:block" />
            <p className="truncate text-base font-semibold text-foreground md:text-lg">
              {identity.pageTitle}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setActivePanel((current) => (current === "account" ? null : "account"));
            }}
            className={cx(
              "inline-flex min-h-11 cursor-pointer items-center gap-3 rounded-full border px-2.5 py-1.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-header",
              activePanel === "account"
                ? "border-primary/35 bg-primary/10"
                : "border-border bg-background hover:border-primary/25 hover:bg-surface",
            )}
            aria-expanded={activePanel === "account"}
            aria-label="Open account panel"
          >
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/12 text-[12px] font-semibold text-primary">
              {authSummary.state === "authenticated" ? (
                initials
              ) : authSummary.state === "degraded" ? (
                <AlertTriangle className="h-4 w-4" />
              ) : (
                <UserRound className="h-4 w-4" />
              )}
            </span>
            <span className="hidden min-w-0 lg:block">
              <span className="block truncate text-sm font-medium text-foreground">
                {accountTriggerStatus.label}
              </span>
              <span
                className={cx(
                  "block truncate text-[11px]",
                  accountTriggerStatus.tone === "error"
                    ? "text-amber-800 dark:text-amber-200"
                    : "text-muted-foreground",
                )}
              >
                {accountTriggerStatus.detail}
              </span>
            </span>
          </button>

          <WorkspaceStatusStrip
            open={activePanel === "context"}
            onOpenChange={(nextOpen) => {
              setActivePanel(nextOpen ? "context" : null);
            }}
          />
        </div>
      </div>

      <WorkspaceAccountPanel
        open={activePanel === "account"}
        onOpenChange={(nextOpen) => {
          setActivePanel(nextOpen ? "account" : null);
        }}
      />
    </>
  );
}
