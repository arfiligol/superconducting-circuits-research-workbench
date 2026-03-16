"use client";

import Link from "next/link";
import type { RefObject } from "react";
import { LogIn, LogOut, Wrench } from "lucide-react";

import { ShellNotice } from "@/components/layout/shell-notice";
import { ShellSidePanel } from "@/components/layout/shell-side-panel";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import {
  describeShellError,
  resolveShellAuthModeLabel,
  resolveShellAuthSummary,
} from "@/components/layout/workspace-shell-contract";
import { cx } from "@/features/shared/components/surface-kit";
import { useAppSession, useDeveloperMode } from "@/lib/app-state";

type WorkspaceAccountPanelProps = Readonly<{
  open: boolean;
  onOpenChange: (nextOpen: boolean) => void;
  interactionBoundaryRef?: RefObject<HTMLElement | null>;
}>;

function PreferenceRow({
  label,
  detail,
  children,
}: Readonly<{
  label: string;
  detail: string;
  children: React.ReactNode;
}>) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[1.1rem] border border-border/90 bg-background px-4 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="mt-1 text-xs leading-5 text-foreground/72 dark:text-foreground/74">{detail}</p>
      </div>
      {children}
    </div>
  );
}

export function WorkspaceAccountPanel({
  open,
  onOpenChange,
  interactionBoundaryRef,
}: WorkspaceAccountPanelProps) {
  const { session, status, sessionError } = useAppSession();
  const { enabled: developerModeEnabled, toggle: toggleDeveloperMode } = useDeveloperMode();
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const summaryMessage =
    authSummary.state === "degraded" && !developerModeEnabled
      ? "Session recovery is needed before trusting account-backed actions."
      : authSummary.menuDescription;
  const sessionDebugItems = [
    {
      label: "Auth Mode",
      value: session?.authMode ? resolveShellAuthModeLabel(session.authMode) : "Pending",
    },
    {
      label: "Active Workspace",
      value: session?.workspace.displayName ?? "Workspace unavailable",
    },
    {
      label: "Memberships",
      value: `${session?.memberships.length ?? 0}`,
    },
    {
      label: "Capability Profile",
      value: session?.capabilities.canSwitchWorkspace ? "Collaborative" : "Single workspace",
    },
  ];

  return (
    <ShellSidePanel
      open={open}
      onClose={() => {
        onOpenChange(false);
      }}
      title="Account"
      subtitle="Account, preferences, and app-level debug visibility."
      eyebrow={null}
      variant="account"
      className="max-w-[448px]"
      interactionBoundaryRef={interactionBoundaryRef}
    >
      <div className="space-y-5">
        <ShellNotice tone={authSummary.tone} title={authSummary.menuTitle}>
          {summaryMessage}
        </ShellNotice>

        <section className="rounded-[1.2rem] border border-border/90 bg-surface px-4 py-4 shadow-[0_12px_28px_rgba(15,23,42,0.08)]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Account
              </p>
              <p className="mt-2 truncate text-sm font-semibold text-foreground">
                {session?.user?.displayName ?? authSummary.triggerName}
              </p>
              <p className="mt-1 truncate text-sm text-muted-foreground">
                {session?.user?.email ?? "Use login to attach an authenticated identity."}
              </p>
            </div>
            <span
              className={cx(
                "rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]",
                authSummary.tone === "success"
                  ? "border-emerald-500/30 bg-emerald-500/16 text-emerald-950 dark:text-emerald-200"
                  : authSummary.tone === "warning"
                    ? "border-amber-500/30 bg-amber-500/16 text-amber-950 dark:text-amber-200"
                    : authSummary.tone === "error"
                      ? "border-rose-600/30 bg-rose-500/16 text-rose-950 dark:text-rose-200"
                      : "border-primary/25 bg-primary/12 text-foreground",
              )}
            >
              {authSummary.badgeLabel}
            </span>
          </div>

          <p className="mt-4 text-sm leading-6 text-foreground/74 dark:text-foreground/76">
            Workspace switching, datasets, queue visibility, and worker context stay in the global context surface.
          </p>
        </section>

        <section className="rounded-[1.2rem] border border-border/90 bg-surface px-4 py-4 shadow-[0_12px_28px_rgba(15,23,42,0.08)]">
          <div className="mb-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Preferences
            </p>
            <p className="mt-2 text-sm text-foreground/72 dark:text-foreground/74">
              App-level controls stay lightweight here.
            </p>
          </div>

          <div className="space-y-3">
            <PreferenceRow
              label="Appearance"
              detail="Theme ownership stays in the account drawer."
            >
              <ThemeToggle className="border border-border bg-background" />
            </PreferenceRow>

            <PreferenceRow
              label="Developer Mode"
              detail={
                developerModeEnabled
                  ? "Technical detail is available behind debug disclosures."
                  : "Primary UI stays concise and hides raw technical detail."
              }
            >
              <button
                type="button"
                onClick={toggleDeveloperMode}
                aria-pressed={developerModeEnabled}
                className={cx(
                  "inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-medium uppercase tracking-[0.16em] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                  developerModeEnabled
                    ? "border-primary/40 bg-primary/12 text-foreground shadow-[0_8px_22px_rgba(37,99,235,0.14)]"
                    : "border-border bg-background text-foreground/76 hover:border-primary/25 hover:bg-surface-elevated hover:text-foreground",
                )}
              >
                <Wrench className="h-3.5 w-3.5" />
                {developerModeEnabled ? "On" : "Off"}
              </button>
            </PreferenceRow>
          </div>
        </section>

        {developerModeEnabled ? (
          <details className="rounded-[1.2rem] border border-border/90 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
            <summary className="cursor-pointer list-none text-sm font-semibold text-foreground marker:hidden">
              Debug details
            </summary>
            <p className="mt-2 text-sm text-foreground/72 dark:text-foreground/74">
              App-level technical detail is visible only while Developer Mode is enabled.
            </p>

            <dl className="mt-4 grid gap-3 sm:grid-cols-2">
              {sessionDebugItems.map((item) => (
                <div
                  key={item.label}
                  className="rounded-[0.9rem] border border-border bg-background px-4 py-3"
                >
                  <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                    {item.label}
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-foreground">{item.value}</dd>
                </div>
              ))}
            </dl>

            {sessionError ? (
              <ShellNotice className="mt-4" tone="warning" title="Session detail">
                {describeShellError(sessionError) ?? sessionError.message}
              </ShellNotice>
            ) : null}
          </details>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Link
            href={authSummary.primaryActionHref}
            className="inline-flex cursor-pointer items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
          >
            {authSummary.primaryActionHref === "/logout" ? (
              <LogOut className="h-4 w-4" />
            ) : (
              <LogIn className="h-4 w-4" />
            )}
            {authSummary.primaryActionLabel}
          </Link>
        </div>
      </div>
    </ShellSidePanel>
  );
}
