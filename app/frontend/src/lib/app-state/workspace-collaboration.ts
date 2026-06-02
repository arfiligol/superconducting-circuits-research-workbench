"use client";

import { useState } from "react";
import useSWR from "swr";

import {
  createWorkspaceInvitation,
  leaveWorkspace,
  listWorkspaceInvitations,
  listWorkspaceMemberships,
  removeWorkspaceMember,
  revokeWorkspaceInvitation,
  transferWorkspaceOwnership,
  workspaceInvitationsKey,
  workspaceMembershipsKey,
  type WorkspaceInvitationCreateInput,
} from "@/lib/api/session";
import { useAppSession } from "@/lib/app-state/app-session";

type CollaborationMutationState = Readonly<{
  state: "idle" | "submitting" | "success" | "error";
  message: string | null;
}>;

export function useWorkspaceCollaboration() {
  const { session, refreshSession } = useAppSession();
  const [mutationState, setMutationState] = useState<CollaborationMutationState>({
    state: "idle",
    message: null,
  });
  const workspaceId = session?.workspace.workspaceId ?? null;
  const canManageInvites =
    (session?.capabilities.canInviteMembers ?? false) ||
    (session?.workspace.allowedActions.inviteMembers ?? false);
  const canManageMembers =
    (session?.capabilities.canRemoveMembers ?? false) ||
    (session?.workspace.allowedActions.removeMembers ?? false);
  const canTransferOwnership =
    (session?.capabilities.canTransferWorkspaceOwner ?? false) ||
    (session?.workspace.allowedActions.transferOwner ?? false);
  const canLeaveWorkspace =
    (session?.capabilities.canLeaveWorkspace ?? false) ||
    (session?.workspace.allowedActions.leaveWorkspace ?? false);

  const invitationsQuery = useSWR(
    workspaceId && canManageInvites ? [workspaceInvitationsKey, workspaceId] : null,
    () => listWorkspaceInvitations(workspaceId),
  );
  const membershipsQuery = useSWR(
    workspaceId ? [workspaceMembershipsKey, workspaceId] : null,
    () => listWorkspaceMemberships(workspaceId),
  );

  async function revalidateCollaboration() {
    await Promise.all([
      invitationsQuery.mutate(),
      membershipsQuery.mutate(),
      refreshSession(),
    ]);
  }

  async function createInvitation(input: WorkspaceInvitationCreateInput) {
    setMutationState({ state: "submitting", message: null });
    try {
      const result = await createWorkspaceInvitation(input);
      await revalidateCollaboration();
      setMutationState({
        state: "success",
        message: `Invitation queued for ${result.invitation.email}.`,
      });
      return result;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to create the workspace invitation.";
      setMutationState({ state: "error", message });
      throw error;
    }
  }

  async function revokeInvitation(inviteId: string) {
    setMutationState({ state: "submitting", message: null });
    try {
      const result = await revokeWorkspaceInvitation(inviteId);
      await revalidateCollaboration();
      setMutationState({
        state: "success",
        message: `Invitation ${result.invitation.email} revoked.`,
      });
      return result;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to revoke the workspace invitation.";
      setMutationState({ state: "error", message });
      throw error;
    }
  }

  async function leaveActiveWorkspace() {
    setMutationState({ state: "submitting", message: null });
    try {
      const result = await leaveWorkspace(workspaceId);
      await revalidateCollaboration();
      setMutationState({
        state: "success",
        message: `Left ${result.workspaceName}.`,
      });
      return result;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to leave the active workspace.";
      setMutationState({ state: "error", message });
      throw error;
    }
  }

  async function removeMember(userId: string) {
    setMutationState({ state: "submitting", message: null });
    try {
      const result = await removeWorkspaceMember({
        userId,
        workspaceId,
      });
      await revalidateCollaboration();
      setMutationState({
        state: "success",
        message: `Workspace membership ${userId} removed.`,
      });
      return result;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to remove the workspace membership.";
      setMutationState({ state: "error", message });
      throw error;
    }
  }

  async function transferOwnership(newOwnerUserId: string) {
    setMutationState({ state: "submitting", message: null });
    try {
      const result = await transferWorkspaceOwnership({
        newOwnerUserId,
        workspaceId,
      });
      await revalidateCollaboration();
      setMutationState({
        state: "success",
        message: `Ownership transferred to ${newOwnerUserId}.`,
      });
      return result;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to transfer workspace ownership.";
      setMutationState({ state: "error", message });
      throw error;
    }
  }

  function clearMutationState() {
    setMutationState({ state: "idle", message: null });
  }

  return {
    workspaceId,
    canManageInvites,
    canManageMembers,
    canTransferOwnership,
    canLeaveWorkspace,
    invitations: invitationsQuery.data?.rows ?? [],
    invitationsError: invitationsQuery.error as Error | undefined,
    isInvitationsLoading: invitationsQuery.isLoading,
    memberships: membershipsQuery.data?.memberships ?? [],
    membershipsError: membershipsQuery.error as Error | undefined,
    isMembershipsLoading: membershipsQuery.isLoading,
    mutationState,
    createInvitation,
    revokeInvitation,
    leaveActiveWorkspace,
    removeMember,
    transferOwnership,
    refreshCollaboration: revalidateCollaboration,
    clearMutationState,
  };
}
