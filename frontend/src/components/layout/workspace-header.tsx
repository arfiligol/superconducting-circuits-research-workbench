"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronDown, LogIn, LogOut } from "lucide-react";
import { usePathname } from "next/navigation";

import { ShellNotice } from "@/components/layout/shell-notice";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import {
  resolveShellAuthModeLabel,
  resolveShellAuthSummary,
  resolveShellUserInitials,
} from "@/components/layout/workspace-shell-contract";
import { cx } from "@/features/shared/components/surface-kit";
import { useAppSession } from "@/lib/app-state";
import { resolveWorkspacePageIdentity } from "@/lib/navigation";

export function WorkspaceHeader() {
  const pathname = usePathname();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const { session, workspace, status, sessionError } = useAppSession();
  const identity = resolveWorkspacePageIdentity(pathname);
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const userInitials = resolveShellUserInitials(authSummary.triggerName);

  useEffect(() => {
    setIsUserMenuOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-w-0 flex-1 items-start justify-between gap-4">
      <div className="min-w-0 space-y-2">
        <div className="min-w-0">
          <p className="truncate whitespace-nowrap text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            SUPERCONDUCTING CIRCUITS
          </p>
          <p className="truncate whitespace-nowrap text-sm font-semibold text-foreground md:text-base">
            Research Workbench
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {identity.sectionLabel !== identity.pageTitle ? (
            <span className="inline-flex rounded-full border border-border bg-surface px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
              {identity.sectionLabel}
            </span>
          ) : null}
          <p className="truncate text-base font-semibold text-foreground md:text-lg">
            {identity.pageTitle}
          </p>
        </div>
      </div>

      <div className="relative shrink-0">
        <button
          type="button"
          onClick={() => {
            setIsUserMenuOpen((open) => !open);
          }}
          className="inline-flex cursor-pointer items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-3 py-2 text-left text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-header"
          aria-haspopup="menu"
          aria-expanded={isUserMenuOpen}
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary/12 text-xs font-semibold text-primary">
            {userInitials}
          </span>
          <span className="hidden min-w-0 sm:block">
            <span className="block truncate text-sm font-medium">{authSummary.triggerName}</span>
            <span className="block truncate text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
              {authSummary.triggerDetail}
            </span>
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </button>

        {isUserMenuOpen ? (
          <div className="absolute right-0 top-[calc(100%+0.65rem)] z-40 w-[290px] rounded-[1rem] border border-border bg-card p-4 shadow-[0_18px_50px_rgba(15,23,42,0.28)]">
            <div className="border-b border-border/80 pb-4">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-primary/12 text-sm font-semibold text-primary">
                  {userInitials}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {authSummary.triggerName}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {session?.user?.email ?? authSummary.triggerDetail}
                  </p>
                </div>
              </div>
              <div className="mt-3 grid gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground sm:grid-cols-2">
                <span className="rounded-full border border-border px-3 py-1">
                  {authSummary.badgeLabel}
                </span>
                <span className="rounded-full border border-border px-3 py-1">
                  {status === "ready" || status === "refreshing" ? "session-backed" : status}
                </span>
              </div>
            </div>

            <div className="space-y-3 py-4">
              <ShellNotice tone={authSummary.tone} title={authSummary.menuTitle}>
                {authSummary.menuDescription}
              </ShellNotice>

              <div className="rounded-[0.9rem] border border-border bg-surface px-3 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Session Authority
                </p>
                <p className="mt-2 text-sm text-foreground">
                  {workspace?.displayName ?? "Workspace pending"} session with{" "}
                  {session?.memberships.length ?? 0} workspace memberships.
                </p>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Auth mode: {session?.authMode ? resolveShellAuthModeLabel(session.authMode) : "pending"} · Session status:{" "}
                  {status === "ready" || status === "refreshing" ? status : "recovering"}
                </p>
              </div>

              <div className="flex items-center justify-between rounded-[0.9rem] border border-border bg-surface px-3 py-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Appearance</p>
                  <p className="text-xs text-muted-foreground">
                    Theme control stays in the user menu per shell contract.
                  </p>
                </div>
                <ThemeToggle className="border border-border bg-background" />
              </div>
            </div>

            <Link
              href={authSummary.primaryActionHref}
              className={cx(
                "flex w-full cursor-pointer items-center justify-between rounded-[0.9rem] border border-border px-3 py-3 text-left text-sm text-foreground transition hover:border-primary/40 hover:bg-primary/10",
              )}
            >
              <span className="inline-flex items-center gap-2">
                {authSummary.primaryActionHref === "/logout" ? (
                  <LogOut className="h-4 w-4" />
                ) : (
                  <LogIn className="h-4 w-4" />
                )}
                {authSummary.primaryActionLabel}
              </span>
              <span className="text-[11px] uppercase tracking-[0.16em]">{authSummary.badgeLabel}</span>
            </Link>

            <button
              type="button"
              onClick={() => {
                setIsUserMenuOpen(false);
              }}
              className="mt-3 inline-flex cursor-pointer items-center justify-center rounded-md px-3 py-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground transition hover:bg-surface hover:text-foreground"
            >
              Close menu
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
