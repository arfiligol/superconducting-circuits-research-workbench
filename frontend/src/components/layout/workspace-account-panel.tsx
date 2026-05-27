"use client";

import Link from "next/link";
import type { RefObject } from "react";
import { Globe, LogIn, LogOut, Wrench } from "lucide-react";

import { ShellNotice } from "@/components/layout/shell-notice";
import { ShellSidePanel } from "@/components/layout/shell-side-panel";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import {
  describeShellError,
  resolveRuntimeModeLabel,
  resolveShellAuthSummary,
  resolveShellConnectionTargetLabel,
  resolveSessionWorkspaceLabel,
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
  const {
    session,
    status,
    sessionError,
    runtimeMode,
    serverTargetDraft,
    setServerTargetDraft,
    switchRuntimeMode,
  } = useAppSession();
  const { enabled: developerModeEnabled, toggle: toggleDeveloperMode } = useDeveloperMode();
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const summaryMessage =
    authSummary.state === "degraded" && !developerModeEnabled
      ? "Connection recovery is needed before trusting online account-backed actions."
      : authSummary.menuDescription;

  const summaryBadgeClass =
    authSummary.tone === "success"
      ? "border-emerald-500/30 bg-emerald-500/16 text-emerald-950 dark:text-emerald-200"
      : authSummary.tone === "warning"
        ? "border-amber-500/30 bg-amber-500/16 text-amber-950 dark:text-amber-200"
        : authSummary.tone === "error"
          ? "border-rose-600/30 bg-rose-500/16 text-rose-950 dark:text-rose-200"
          : "border-primary/25 bg-primary/12 text-foreground";

  const runtimeTargetLabel =
    runtimeMode === "local"
      ? "No online target"
      : resolveShellConnectionTargetLabel(session);
  const runtimeSummaryTitle =
    runtimeMode === "local"
      ? "Local operator"
      : authSummary.state === "authenticated"
        ? session?.user?.displayName ?? "Authenticated user"
        : "Online mode";
  const runtimeSummaryDetail =
    runtimeMode === "local"
      ? `${resolveSessionWorkspaceLabel(session)} · No remote sign-in required`
      : authSummary.state === "authenticated"
        ? `${runtimeTargetLabel} · Sign out remains online-only`
        : `${runtimeTargetLabel} · Sign in is required`;

  async function handleSwitchToLocalMode() {
    try {
      await switchRuntimeMode({ mode: "local" });
    } catch {
      // surface stays readable through auth/session notice
    }
  }

  async function handleSwitchToOnlineMode() {
    try {
      await switchRuntimeMode({
        mode: "online",
        serverOrigin: serverTargetDraft.trim() || null,
      });
    } catch {
      // surface stays readable through auth/session notice
    }
  }

  return (
    <ShellSidePanel
      open={open}
      onClose={() => {
        onOpenChange(false);
      }}
      title="Account"
      subtitle="Preferences and account actions."
      eyebrow={null}
      variant="account"
      className="max-w-[448px]"
      interactionBoundaryRef={interactionBoundaryRef}
    >
      <div className="space-y-5">
        <ShellNotice tone={authSummary.tone} title={authSummary.menuTitle}>
          {summaryMessage}
        </ShellNotice>

        <section className="rounded-[1.35rem] border border-border/90 bg-surface px-4 py-4 shadow-[0_12px_28px_rgba(15,23,42,0.08)]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {resolveRuntimeModeLabel(runtimeMode)}
              </p>
              <p className="mt-2 truncate text-sm font-semibold text-foreground">
                {runtimeSummaryTitle}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{runtimeSummaryDetail}</p>
            </div>
            <span
              className={cx(
                "rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]",
                summaryBadgeClass,
              )}
            >
              {authSummary.badgeLabel}
            </span>
          </div>

          <div className="mt-4 rounded-[1rem] border border-border/80 bg-background px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Server target
            </p>
            <input
              value={serverTargetDraft}
              onChange={(event) => {
                setServerTargetDraft(event.target.value);
              }}
              className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              placeholder="http://127.0.0.1:8000"
            />
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {runtimeMode === "local" ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    void handleSwitchToOnlineMode();
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <Globe className="h-4 w-4" />
                  Connect to Online Mode
                </button>
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <LogIn className="h-4 w-4" />
                  Open Auth Entry
                </Link>
              </>
            ) : authSummary.state === "authenticated" ? (
              <>
                <Link
                  href="/logout"
                  className="inline-flex items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    void handleSwitchToLocalMode();
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <Globe className="h-4 w-4" />
                  Switch to Local Mode
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <LogIn className="h-4 w-4" />
                  Sign in
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    void handleSwitchToLocalMode();
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-[0.95rem] border border-border bg-background px-4 py-3 text-sm font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
                >
                  <Globe className="h-4 w-4" />
                  Switch to Local Mode
                </button>
              </>
            )}
          </div>
        </section>

        <section className="rounded-[1.35rem] border border-border/90 bg-surface px-4 py-4 shadow-[0_12px_28px_rgba(15,23,42,0.08)]">
          <div className="mb-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Preferences
            </p>
            <p className="mt-2 text-sm text-foreground/72 dark:text-foreground/74">
              App-level controls.
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
          <details className="rounded-[1.25rem] border border-border/90 bg-surface px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
            <summary className="cursor-pointer list-none text-sm font-semibold text-foreground marker:hidden">
              Debug details
            </summary>
            <p className="mt-2 text-sm text-foreground/72 dark:text-foreground/74">
              App-level technical detail is visible only while Developer Mode is enabled.
            </p>

            <dl className="mt-4 grid gap-3 sm:grid-cols-2">
              {[
                { label: "Runtime Mode", value: resolveRuntimeModeLabel(runtimeMode) },
                { label: "Workspace", value: resolveSessionWorkspaceLabel(session) },
                { label: "Target", value: runtimeTargetLabel },
                { label: "Auth State", value: authSummary.badgeLabel },
              ].map((item) => (
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
      </div>
    </ShellSidePanel>
  );
}
