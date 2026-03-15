"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn, LogOut, MailPlus, ShieldAlert, UserMinus, Users } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ShellNotice } from "@/components/layout/shell-notice";
import { ShellSidePanel } from "@/components/layout/shell-side-panel";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import {
  describeShellError,
  resolveShellAuthModeLabel,
  resolveShellAuthSummary,
} from "@/components/layout/workspace-shell-contract";
import { AppSelectField } from "@/features/shared/components/app-select";
import { cx } from "@/features/shared/components/surface-kit";
import { useAppSession } from "@/lib/app-state";
import { useWorkspaceCollaboration } from "@/lib/app-state/workspace-collaboration";
import { ConfirmActionDialog } from "@/lib/confirm-action-dialog";

const invitationSchema = z.object({
  email: z.string().trim().email("Use a valid invite email."),
  role: z.enum(["member", "viewer"]),
});

type InvitationValues = z.infer<typeof invitationSchema>;

type PendingAccountAction =
  | Readonly<{ kind: "leave-workspace" }>
  | Readonly<{ kind: "revoke-invite"; inviteId: string; inviteEmail: string }>
  | null;

type WorkspaceAccountPanelProps = Readonly<{
  open: boolean;
  onOpenChange: (nextOpen: boolean) => void;
}>;

export function WorkspaceAccountPanel({
  open,
  onOpenChange,
}: WorkspaceAccountPanelProps) {
  const { session, status, sessionError } = useAppSession();
  const collaboration = useWorkspaceCollaboration();
  const [pendingAction, setPendingAction] = useState<PendingAccountAction>(null);
  const [removeUserId, setRemoveUserId] = useState("");
  const [transferOwnerUserId, setTransferOwnerUserId] = useState("");
  const authSummary = resolveShellAuthSummary({
    session,
    status,
    error: sessionError,
  });
  const invitationForm = useForm<InvitationValues>({
    resolver: zodResolver(invitationSchema),
    defaultValues: {
      email: "",
      role: "member",
    },
  });
  const sessionSummary = useMemo(
    () => ({
      workspaceName: session?.workspace.displayName ?? "Workspace unavailable",
      authMode: session?.authMode ? resolveShellAuthModeLabel(session.authMode) : "Pending",
      authReason: session?.authReason ?? describeShellError(sessionError),
      platformRole: session?.user?.platformRole ?? "anonymous",
    }),
    [session, sessionError],
  );

  async function handleInvite(values: InvitationValues) {
    await collaboration.createInvitation({
      email: values.email,
      role: values.role,
      workspaceId: session?.workspace.workspaceId ?? null,
    });
    invitationForm.reset({
      email: "",
      role: values.role,
    });
  }

  async function handleRemoveMember() {
    if (!removeUserId.trim()) {
      return;
    }
    await collaboration.removeMember(removeUserId.trim());
    setRemoveUserId("");
  }

  async function handleTransferOwnership() {
    if (!transferOwnerUserId.trim()) {
      return;
    }
    await collaboration.transferOwnership(transferOwnerUserId.trim());
    setTransferOwnerUserId("");
  }

  async function handleConfirmAction() {
    if (!pendingAction) {
      return;
    }

    if (pendingAction.kind === "leave-workspace") {
      await collaboration.leaveActiveWorkspace();
      setPendingAction(null);
      return;
    }

    await collaboration.revokeInvitation(pendingAction.inviteId);
    setPendingAction(null);
  }

  return (
    <>
      <ShellSidePanel
        open={open}
        onClose={() => {
          onOpenChange(false);
        }}
        title={authSummary.triggerName}
        subtitle="Account, authentication, collaboration, and appearance."
      >
        <div className="space-y-5">
          <ShellNotice tone={authSummary.tone} title={authSummary.menuTitle}>
            {authSummary.menuDescription}
          </ShellNotice>

          {collaboration.mutationState.message ? (
            <ShellNotice
              tone={
                collaboration.mutationState.state === "success" ? "success" : "error"
              }
              title={
                collaboration.mutationState.state === "success"
                  ? "Workspace collaboration updated"
                  : "Workspace collaboration error"
              }
            >
              {collaboration.mutationState.message}
            </ShellNotice>
          ) : null}

          <section className="rounded-[1rem] border border-border bg-surface px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Session
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {session?.user?.displayName ?? authSummary.triggerName}
                </p>
              </div>
              <span
                className={cx(
                  "rounded-full px-3 py-1 text-[10px] font-medium uppercase tracking-[0.16em]",
                  authSummary.tone === "success"
                    ? "bg-emerald-500/12 text-emerald-800 dark:text-emerald-200"
                    : authSummary.tone === "warning"
                      ? "bg-amber-500/12 text-amber-800 dark:text-amber-200"
                      : authSummary.tone === "error"
                        ? "bg-rose-500/12 text-rose-800 dark:text-rose-200"
                        : "bg-primary/10 text-primary",
                )}
              >
                {authSummary.badgeLabel}
              </span>
            </div>

            <dl className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Active Workspace
                </dt>
                <dd className="mt-1 text-sm font-medium text-foreground">
                  {sessionSummary.workspaceName}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Auth Mode
                </dt>
                <dd className="mt-1 text-sm font-medium text-foreground">
                  {sessionSummary.authMode}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Platform Role
                </dt>
                <dd className="mt-1 text-sm font-medium text-foreground">
                  {sessionSummary.platformRole}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  Memberships
                </dt>
                <dd className="mt-1 text-sm font-medium text-foreground">
                  {session?.memberships.length ?? 0}
                </dd>
              </div>
            </dl>

            {sessionSummary.authReason ? (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                {sessionSummary.authReason}
              </p>
            ) : null}
          </section>

          <section className="rounded-[1rem] border border-border bg-surface px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Appearance
                </p>
                <p className="mt-2 text-sm text-foreground">
                  Theme ownership stays in the account panel.
                </p>
              </div>
              <ThemeToggle className="border border-border bg-background" />
            </div>
          </section>

          <section className="rounded-[1rem] border border-border bg-surface px-4 py-4">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" />
              <p className="text-sm font-semibold text-foreground">Workspace Collaboration</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Invite, revoke, leave, remove, and transfer stay gated by backend authority.
            </p>

            <div className="mt-4 space-y-4">
              {collaboration.canManageInvites ? (
                <form className="grid gap-3 md:grid-cols-[minmax(0,1fr)_200px_auto]" onSubmit={invitationForm.handleSubmit(handleInvite)}>
                  <label className="rounded-[0.9rem] border border-border bg-background px-4 py-3">
                    <span className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Invite Email
                    </span>
                    <input
                      {...invitationForm.register("email")}
                      className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="researcher@example.com"
                    />
                    {invitationForm.formState.errors.email ? (
                      <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">
                        {invitationForm.formState.errors.email.message}
                      </p>
                    ) : null}
                  </label>
                  <AppSelectField
                    label="Role"
                    value={invitationForm.watch("role")}
                    onChange={(value) => {
                      invitationForm.setValue("role", value as InvitationValues["role"], {
                        shouldDirty: true,
                        shouldTouch: true,
                      });
                    }}
                    options={[
                      { value: "member", label: "Member" },
                      { value: "viewer", label: "Viewer" },
                    ]}
                  />
                  <button
                    type="submit"
                    disabled={invitationForm.formState.isSubmitting}
                    className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 self-end rounded-[0.9rem] border border-primary/35 bg-primary/10 px-4 text-sm font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/16 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <MailPlus className="h-4 w-4" />
                    Invite
                  </button>
                </form>
              ) : (
                <ShellNotice tone="warning" title="Invites not available">
                  The current session cannot create workspace invitations in this workspace.
                </ShellNotice>
              )}

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Pending Invitations
                  </p>
                  <span className="rounded-full border border-border px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    {collaboration.invitations.length}
                  </span>
                </div>

                {collaboration.isInvitationsLoading ? (
                  <div className="rounded-[0.9rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                    Loading invitation authority...
                  </div>
                ) : collaboration.invitations.length > 0 ? (
                  collaboration.invitations.map((invitation) => (
                    <div
                      key={invitation.inviteId}
                      className="rounded-[0.9rem] border border-border bg-background px-4 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">
                            {invitation.email}
                          </p>
                          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                            {invitation.role} · {invitation.state}
                          </p>
                          <p className="mt-2 text-xs text-muted-foreground">
                            Expires {invitation.expiresAt}
                          </p>
                        </div>
                        {collaboration.canManageInvites ? (
                          <button
                            type="button"
                            onClick={() => {
                              setPendingAction({
                                kind: "revoke-invite",
                                inviteId: invitation.inviteId,
                                inviteEmail: invitation.email,
                              });
                            }}
                            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-rose-500/30 px-3 py-2 text-xs font-medium uppercase tracking-[0.16em] text-rose-700 transition hover:bg-rose-500/10 dark:text-rose-300"
                          >
                            Revoke
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-[0.9rem] border border-dashed border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                    No pending workspace invitations are visible for the active workspace.
                  </div>
                )}
              </div>

              {collaboration.invitationsError ? (
                <ShellNotice tone="error" title="Invitation surface error">
                  {collaboration.invitationsError.message}
                </ShellNotice>
              ) : null}

              {collaboration.isMembershipsLoading ? (
                <div className="rounded-[0.9rem] border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
                  Loading membership authority...
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="rounded-[0.9rem] border border-border bg-background px-4 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      Workspace Membership Surface
                    </p>
                    <p className="mt-2 text-sm text-foreground">
                      Backend currently returns collaboration authority without rich user identity labels,
                      so ownership transfer and member removal stay as explicit user-id operations.
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Visible memberships in authority response: {collaboration.memberships.length}
                    </p>
                  </div>

                  {collaboration.memberships.length > 0 ? (
                    collaboration.memberships.map((membership) => (
                      <div
                        key={membership.workspaceId}
                        className="rounded-[0.9rem] border border-border bg-background px-4 py-3"
                      >
                        <p className="text-sm font-semibold text-foreground">
                          {membership.displayName}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          {membership.role} · {membership.defaultTaskScope} tasks
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                          <span className="rounded-full border border-border px-2.5 py-1">
                            {membership.isActive ? "active" : "inactive"}
                          </span>
                          <span className="rounded-full border border-border px-2.5 py-1">
                            {membership.allowedActions.switchTo ? "switchable" : "pinned"}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : null}
                </div>
              )}

              {collaboration.canManageMembers ? (
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
                  <label className="rounded-[0.9rem] border border-border bg-background px-4 py-3">
                    <span className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Remove Member by User ID
                    </span>
                    <input
                      value={removeUserId}
                      onChange={(event) => {
                        setRemoveUserId(event.target.value);
                      }}
                      className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="user_44"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      void handleRemoveMember();
                    }}
                    disabled={removeUserId.trim().length === 0}
                    className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 self-end rounded-[0.9rem] border border-rose-500/30 px-4 text-sm font-medium text-rose-700 transition hover:bg-rose-500/10 dark:text-rose-300 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <UserMinus className="h-4 w-4" />
                    Remove
                  </button>
                </div>
              ) : null}

              {collaboration.canTransferOwnership ? (
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
                  <label className="rounded-[0.9rem] border border-border bg-background px-4 py-3">
                    <span className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                      Transfer Ownership to User ID
                    </span>
                    <input
                      value={transferOwnerUserId}
                      onChange={(event) => {
                        setTransferOwnerUserId(event.target.value);
                      }}
                      className="mt-2 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                      placeholder="user_44"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      void handleTransferOwnership();
                    }}
                    disabled={transferOwnerUserId.trim().length === 0}
                    className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 self-end rounded-[0.9rem] border border-primary/35 bg-primary/10 px-4 text-sm font-medium text-foreground transition hover:border-primary/50 hover:bg-primary/16 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <ShieldAlert className="h-4 w-4" />
                    Transfer
                  </button>
                </div>
              ) : null}

              {collaboration.canLeaveWorkspace ? (
                <button
                  type="button"
                  onClick={() => {
                    setPendingAction({ kind: "leave-workspace" });
                  }}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-[0.9rem] border border-amber-500/30 px-4 py-3 text-sm font-medium text-amber-800 transition hover:bg-amber-500/10 dark:text-amber-200"
                >
                  Leave active workspace
                </button>
              ) : null}
            </div>
          </section>

          {collaboration.membershipsError ? (
            <ShellNotice tone="error" title="Membership surface error">
              {collaboration.membershipsError.message}
            </ShellNotice>
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

      <ConfirmActionDialog
        open={pendingAction !== null}
        title={
          pendingAction?.kind === "leave-workspace"
            ? "Leave active workspace?"
            : "Revoke invitation?"
        }
        description={
          pendingAction?.kind === "leave-workspace"
            ? "Leaving the active workspace will rebind the shared session context. Use this only if you intend to drop the current workspace membership."
            : `Revoke the invitation for ${pendingAction?.inviteEmail ?? "this invite"}? The recipient will no longer be able to accept it.`
        }
        confirmLabel={
          pendingAction?.kind === "leave-workspace" ? "Leave workspace" : "Revoke invitation"
        }
        tone="destructive"
        isPending={collaboration.mutationState.state === "submitting"}
        onCancel={() => {
          setPendingAction(null);
        }}
        onConfirm={() => {
          void handleConfirmAction();
        }}
      />
    </>
  );
}
