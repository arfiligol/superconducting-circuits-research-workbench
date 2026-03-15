import { apiRequest } from "@/lib/api/client";

export type SessionAuthState = "authenticated" | "anonymous" | "degraded";
type SessionAuthModeResponseShape = "local_stub" | "development_stub" | "jwt_cookie";
export type SessionAuthMode = "local_stub" | "jwt_cookie";

type AllowedActionsResponseShape = Readonly<{
  switch_to: boolean;
  activate_dataset: boolean;
  invite_members: boolean;
  remove_members: boolean;
  transfer_owner: boolean;
  leave_workspace: boolean;
  view_audit_logs: boolean;
  manage_definitions: boolean;
  manage_datasets: boolean;
  manage_tasks: boolean;
}>;

type MembershipResponseShape = Readonly<{
  id: string;
  slug: string;
  name: string;
  role: "owner" | "member" | "viewer";
  default_task_scope: "workspace" | "owned";
  is_active: boolean;
  allowed_actions: AllowedActionsResponseShape;
}>;

type SessionResponseShape = Readonly<{
  session_id: string;
  auth: Readonly<{
    state: SessionAuthState;
    mode: SessionAuthModeResponseShape;
    reason?: string | null;
  }>;
  user:
    | Readonly<{
        id: string;
        display_name: string;
        email: string | null;
        platform_role: "admin" | "user";
      }>
    | null;
  workspace: Readonly<{
    id: string;
    slug: string;
    name: string;
    role: "owner" | "member" | "viewer";
    default_task_scope: "workspace" | "owned";
    allowed_actions: AllowedActionsResponseShape;
    memberships?: ReadonlyArray<MembershipResponseShape>;
  }>;
  memberships?: ReadonlyArray<MembershipResponseShape>;
  active_dataset:
    | Readonly<{
        id: string;
        name: string;
        family: string;
        status: "Ready" | "Queued" | "Review";
        owner_user_id: string;
        owner_display_name: string;
        workspace_id: string;
        visibility_scope: "private" | "workspace";
        lifecycle_state: "active" | "archived" | "deleted";
      }>
    | null;
  capabilities: Readonly<{
    can_switch_workspace: boolean;
    can_switch_dataset: boolean;
    can_invite_members: boolean;
    can_remove_members: boolean;
    can_transfer_workspace_owner: boolean;
    can_leave_workspace: boolean;
    can_submit_tasks: boolean;
    can_manage_workspace_tasks: boolean;
    can_cancel_own_tasks: boolean;
    can_cancel_workspace_tasks: boolean;
    can_terminate_workspace_tasks: boolean;
    can_retry_own_tasks: boolean;
    can_retry_workspace_tasks: boolean;
    can_manage_definitions: boolean;
    can_manage_datasets: boolean;
    can_view_audit_logs: boolean;
  }>;
}>;

type WorkspaceSwitchResponseShape = SessionResponseShape &
  Readonly<{
    active_dataset_resolution: "preserved" | "rebound" | "cleared";
    detached_task_ids: readonly string[];
  }>;

type WorkspaceInvitationResponseShape = Readonly<{
  invite_id: string;
  invite_token: string;
  workspace_id: string;
  workspace_name: string;
  email: string;
  role: "member" | "viewer";
  state:
    | "pending"
    | "delivered"
    | "accepted"
    | "revoked"
    | "expired"
    | "delivery_failed";
  expires_at: string;
  created_at: string;
  delivery_state: "smtp" | "manual_link" | "pending" | "failed";
  created_by_user_id: string;
  delivery_error: string | null;
}>;

type WorkspaceInvitationListResponseShape = Readonly<{
  rows: readonly WorkspaceInvitationResponseShape[];
}>;

type WorkspaceInvitationMutationResponseShape = Readonly<{
  operation: "created" | "revoked";
  invitation: WorkspaceInvitationResponseShape;
}>;

type WorkspaceInvitationAcceptanceResponseShape = Readonly<{
  invitation: WorkspaceInvitationResponseShape;
  memberships: readonly MembershipResponseShape[];
  switch_available: boolean;
  post_accept_context: "switch_available" | "already_active";
}>;

type WorkspaceMembershipListResponseShape = Readonly<{
  workspace_id: string;
  workspace_name: string;
  memberships: readonly MembershipResponseShape[];
}>;

type WorkspaceMembershipMutationResponseShape = Readonly<
  {
    operation: "left" | "removed" | "ownership_transferred";
  } & WorkspaceMembershipListResponseShape
>;

export type SessionAllowedActions = Readonly<{
  switchTo: boolean;
  activateDataset: boolean;
  inviteMembers: boolean;
  removeMembers: boolean;
  transferOwner: boolean;
  leaveWorkspace: boolean;
  viewAuditLogs: boolean;
  manageDefinitions: boolean;
  manageDatasets: boolean;
  manageTasks: boolean;
}>;

export type SessionCapabilities = Readonly<{
  canSwitchWorkspace: boolean;
  canSwitchDataset: boolean;
  canInviteMembers: boolean;
  canRemoveMembers: boolean;
  canTransferWorkspaceOwner: boolean;
  canLeaveWorkspace: boolean;
  canSubmitTasks: boolean;
  canManageWorkspaceTasks: boolean;
  canCancelOwnTasks: boolean;
  canCancelWorkspaceTasks: boolean;
  canTerminateWorkspaceTasks: boolean;
  canRetryOwnTasks: boolean;
  canRetryWorkspaceTasks: boolean;
  canManageDefinitions: boolean;
  canManageDatasets: boolean;
  canViewAuditLogs: boolean;
}>;

export type SessionMembership = Readonly<{
  workspaceId: string;
  slug: string;
  displayName: string;
  role: "owner" | "member" | "viewer";
  defaultTaskScope: "workspace" | "owned";
  isActive: boolean;
  allowedActions: SessionAllowedActions;
}>;

export type SessionSnapshot = Readonly<{
  sessionId: string;
  authState: SessionAuthState;
  authMode: SessionAuthMode;
  authReason: string | null;
  capabilities: SessionCapabilities;
  canSubmitTasks: boolean;
  canManageDatasets: boolean;
  canManageDefinitions: boolean;
  canInviteMembers: boolean;
  canRemoveMembers: boolean;
  canTransferWorkspaceOwner: boolean;
  canLeaveWorkspace: boolean;
  user:
    | Readonly<{
        userId: string;
        displayName: string;
        email: string | null;
        platformRole: "admin" | "user";
      }>
    | null;
  workspace: Readonly<{
    workspaceId: string;
    slug: string;
    displayName: string;
    role: "owner" | "member" | "viewer";
    defaultTaskScope: "workspace" | "owned";
    allowedActions: SessionAllowedActions;
  }>;
  memberships: ReadonlyArray<SessionMembership>;
  activeDataset:
    | Readonly<{
        datasetId: string;
        name: string;
        family: string;
        status: "Ready" | "Queued" | "Review";
        ownerUserId: string;
        owner: string;
        workspaceId: string;
        visibilityScope: "private" | "workspace";
        lifecycleState: "active" | "archived" | "deleted";
      }>
    | null;
}>;

export type WorkspaceSwitchResult = Readonly<{
  session: SessionSnapshot;
  activeDatasetResolution: "preserved" | "rebound" | "cleared";
  detachedTaskIds: readonly string[];
}>;

export type WorkspaceInvitationSnapshot = Readonly<{
  inviteId: string;
  inviteToken: string;
  workspaceId: string;
  workspaceName: string;
  email: string;
  role: "member" | "viewer";
  state:
    | "pending"
    | "delivered"
    | "accepted"
    | "revoked"
    | "expired"
    | "delivery_failed";
  expiresAt: string;
  createdAt: string;
  deliveryState: "smtp" | "manual_link" | "pending" | "failed";
  createdByUserId: string;
  deliveryError: string | null;
}>;

export type WorkspaceInvitationList = Readonly<{
  rows: readonly WorkspaceInvitationSnapshot[];
}>;

export type WorkspaceInvitationCreateInput = Readonly<{
  workspaceId?: string | null;
  email: string;
  role: "member" | "viewer";
}>;

export type WorkspaceInvitationMutationResult = Readonly<{
  operation: "created" | "revoked";
  invitation: WorkspaceInvitationSnapshot;
}>;

export type WorkspaceInvitationAcceptanceResult = Readonly<{
  invitation: WorkspaceInvitationSnapshot;
  memberships: readonly SessionMembership[];
  switchAvailable: boolean;
  postAcceptContext: "switch_available" | "already_active";
}>;

export type WorkspaceMembershipList = Readonly<{
  workspaceId: string;
  workspaceName: string;
  memberships: readonly SessionMembership[];
}>;

export type WorkspaceMembershipMutationResult = Readonly<{
  operation: "left" | "removed" | "ownership_transferred";
  workspaceId: string;
  workspaceName: string;
  memberships: readonly SessionMembership[];
}>;

export type SessionLoginCredentials = Readonly<{
  email: string;
  password: string;
}>;

export type SessionLoginResult = SessionSnapshot;
export type SessionLogoutResult = SessionSnapshot;

export const appSessionKey = "/api/backend/session";
export const workspaceInvitationsKey = `${appSessionKey}/workspace-invitations`;
export const workspaceMembershipsKey = `${appSessionKey}/workspace-memberships`;

const authLoginPath = `${appSessionKey}/login`;
const authLogoutPath = `${appSessionKey}/logout`;
const authRefreshPath = `${appSessionKey}/refresh`;

function mapAllowedActions(payload: AllowedActionsResponseShape): SessionAllowedActions {
  return {
    switchTo: payload.switch_to,
    activateDataset: payload.activate_dataset,
    inviteMembers: payload.invite_members,
    removeMembers: payload.remove_members,
    transferOwner: payload.transfer_owner,
    leaveWorkspace: payload.leave_workspace,
    viewAuditLogs: payload.view_audit_logs,
    manageDefinitions: payload.manage_definitions,
    manageDatasets: payload.manage_datasets,
    manageTasks: payload.manage_tasks,
  };
}

function mapMembership(payload: MembershipResponseShape): SessionMembership {
  return {
    workspaceId: payload.id,
    slug: payload.slug,
    displayName: payload.name,
    role: payload.role,
    defaultTaskScope: payload.default_task_scope,
    isActive: payload.is_active,
    allowedActions: mapAllowedActions(payload.allowed_actions),
  };
}

function mapWorkspaceInvitation(
  payload: WorkspaceInvitationResponseShape,
): WorkspaceInvitationSnapshot {
  return {
    inviteId: payload.invite_id,
    inviteToken: payload.invite_token,
    workspaceId: payload.workspace_id,
    workspaceName: payload.workspace_name,
    email: payload.email,
    role: payload.role,
    state: payload.state,
    expiresAt: payload.expires_at,
    createdAt: payload.created_at,
    deliveryState: payload.delivery_state,
    createdByUserId: payload.created_by_user_id,
    deliveryError: payload.delivery_error,
  };
}

function mapWorkspaceMembershipList(
  payload: WorkspaceMembershipListResponseShape,
): WorkspaceMembershipList {
  return {
    workspaceId: payload.workspace_id,
    workspaceName: payload.workspace_name,
    memberships: payload.memberships.map(mapMembership),
  };
}

export function normalizeSessionAuthMode(mode: SessionAuthModeResponseShape): SessionAuthMode {
  return mode === "development_stub" ? "local_stub" : mode;
}

export function mapSessionResponse(payload: SessionResponseShape): SessionSnapshot {
  const capabilities: SessionCapabilities = {
    canSwitchWorkspace: payload.capabilities.can_switch_workspace,
    canSwitchDataset: payload.capabilities.can_switch_dataset,
    canInviteMembers: payload.capabilities.can_invite_members,
    canRemoveMembers: payload.capabilities.can_remove_members,
    canTransferWorkspaceOwner: payload.capabilities.can_transfer_workspace_owner,
    canLeaveWorkspace: payload.capabilities.can_leave_workspace,
    canSubmitTasks: payload.capabilities.can_submit_tasks,
    canManageWorkspaceTasks: payload.capabilities.can_manage_workspace_tasks,
    canCancelOwnTasks: payload.capabilities.can_cancel_own_tasks,
    canCancelWorkspaceTasks: payload.capabilities.can_cancel_workspace_tasks,
    canTerminateWorkspaceTasks: payload.capabilities.can_terminate_workspace_tasks,
    canRetryOwnTasks: payload.capabilities.can_retry_own_tasks,
    canRetryWorkspaceTasks: payload.capabilities.can_retry_workspace_tasks,
    canManageDefinitions: payload.capabilities.can_manage_definitions,
    canManageDatasets: payload.capabilities.can_manage_datasets,
    canViewAuditLogs: payload.capabilities.can_view_audit_logs,
  };
  const memberships = payload.workspace.memberships ?? payload.memberships ?? [];

  return {
    sessionId: payload.session_id,
    authState: payload.auth.state,
    authMode: normalizeSessionAuthMode(payload.auth.mode),
    authReason: payload.auth.reason ?? null,
    capabilities,
    canSubmitTasks: capabilities.canSubmitTasks,
    canManageDatasets: capabilities.canManageDatasets,
    canManageDefinitions: capabilities.canManageDefinitions,
    canInviteMembers: capabilities.canInviteMembers,
    canRemoveMembers: capabilities.canRemoveMembers,
    canTransferWorkspaceOwner: capabilities.canTransferWorkspaceOwner,
    canLeaveWorkspace: capabilities.canLeaveWorkspace,
    user: payload.user
      ? {
          userId: payload.user.id,
          displayName: payload.user.display_name,
          email: payload.user.email,
          platformRole: payload.user.platform_role,
        }
      : null,
    workspace: {
      workspaceId: payload.workspace.id,
      slug: payload.workspace.slug,
      displayName: payload.workspace.name,
      role: payload.workspace.role,
      defaultTaskScope: payload.workspace.default_task_scope,
      allowedActions: mapAllowedActions(payload.workspace.allowed_actions),
    },
    memberships: memberships.map(mapMembership),
    activeDataset: payload.active_dataset
      ? {
          datasetId: payload.active_dataset.id,
          name: payload.active_dataset.name,
          family: payload.active_dataset.family,
          status: payload.active_dataset.status,
          ownerUserId: payload.active_dataset.owner_user_id,
          owner: payload.active_dataset.owner_display_name,
          workspaceId: payload.active_dataset.workspace_id,
          visibilityScope: payload.active_dataset.visibility_scope,
          lifecycleState: payload.active_dataset.lifecycle_state,
        }
      : null,
  };
}

export function mapWorkspaceSwitchResponse(
  payload: WorkspaceSwitchResponseShape,
): WorkspaceSwitchResult {
  return {
    session: mapSessionResponse(payload),
    activeDatasetResolution: payload.active_dataset_resolution,
    detachedTaskIds: [...payload.detached_task_ids],
  };
}

export function mapLoginResponse(payload: SessionResponseShape): SessionLoginResult {
  return mapSessionResponse(payload);
}

export function mapLogoutResponse(payload: SessionResponseShape): SessionLogoutResult {
  return mapSessionResponse(payload);
}

export function mapWorkspaceInvitationListResponse(
  payload: WorkspaceInvitationListResponseShape,
): WorkspaceInvitationList {
  return {
    rows: payload.rows.map(mapWorkspaceInvitation),
  };
}

export function mapWorkspaceInvitationMutationResponse(
  payload: WorkspaceInvitationMutationResponseShape,
): WorkspaceInvitationMutationResult {
  return {
    operation: payload.operation,
    invitation: mapWorkspaceInvitation(payload.invitation),
  };
}

export function mapWorkspaceInvitationAcceptanceResponse(
  payload: WorkspaceInvitationAcceptanceResponseShape,
): WorkspaceInvitationAcceptanceResult {
  return {
    invitation: mapWorkspaceInvitation(payload.invitation),
    memberships: payload.memberships.map(mapMembership),
    switchAvailable: payload.switch_available,
    postAcceptContext: payload.post_accept_context,
  };
}

export function mapWorkspaceMembershipMutationResponse(
  payload: WorkspaceMembershipMutationResponseShape,
): WorkspaceMembershipMutationResult {
  return {
    operation: payload.operation,
    workspaceId: payload.workspace_id,
    workspaceName: payload.workspace_name,
    memberships: payload.memberships.map(mapMembership),
  };
}

export async function getSession() {
  const response = await apiRequest<SessionResponseShape>(appSessionKey);
  return mapSessionResponse(response);
}

export async function loginWithPassword(credentials: SessionLoginCredentials) {
  const response = await apiRequest<SessionResponseShape>(authLoginPath, {
    method: "POST",
    body: credentials,
  });
  return mapLoginResponse(response);
}

export async function logoutCurrentSession() {
  const response = await apiRequest<SessionResponseShape>(authLogoutPath, {
    method: "POST",
  });
  return mapLogoutResponse(response);
}

export async function refreshCurrentSession() {
  const response = await apiRequest<SessionResponseShape>(authRefreshPath, {
    method: "POST",
  });
  return mapSessionResponse(response);
}

export async function patchActiveWorkspace(workspaceId: string) {
  const response = await apiRequest<WorkspaceSwitchResponseShape>(
    `${appSessionKey}/active-workspace`,
    {
      method: "PATCH",
      body: { workspace_id: workspaceId },
    },
  );

  return mapWorkspaceSwitchResponse(response);
}

export async function patchActiveDataset(datasetId: string | null) {
  const response = await apiRequest<SessionResponseShape>(`${appSessionKey}/active-dataset`, {
    method: "PATCH",
    body: { dataset_id: datasetId },
  });

  return mapSessionResponse(response);
}

export async function listWorkspaceInvitations(workspaceId?: string | null) {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  const response = await apiRequest<WorkspaceInvitationListResponseShape>(
    `${workspaceInvitationsKey}${query}`,
  );
  return mapWorkspaceInvitationListResponse(response);
}

export async function createWorkspaceInvitation(input: WorkspaceInvitationCreateInput) {
  const response = await apiRequest<WorkspaceInvitationMutationResponseShape>(
    workspaceInvitationsKey,
    {
      method: "POST",
      body: {
        workspace_id: input.workspaceId ?? null,
        email: input.email,
        role: input.role,
      },
    },
  );
  return mapWorkspaceInvitationMutationResponse(response);
}

export async function revokeWorkspaceInvitation(inviteId: string) {
  const response = await apiRequest<WorkspaceInvitationMutationResponseShape>(
    `${workspaceInvitationsKey}/${encodeURIComponent(inviteId)}/revoke`,
    {
      method: "POST",
    },
  );
  return mapWorkspaceInvitationMutationResponse(response);
}

export async function acceptWorkspaceInvitation(inviteToken: string) {
  const response = await apiRequest<WorkspaceInvitationAcceptanceResponseShape>(
    `${workspaceInvitationsKey}/accept`,
    {
      method: "POST",
      body: { invite_token: inviteToken },
    },
  );
  return mapWorkspaceInvitationAcceptanceResponse(response);
}

export async function listWorkspaceMemberships(workspaceId?: string | null) {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  const response = await apiRequest<WorkspaceMembershipListResponseShape>(
    `${workspaceMembershipsKey}${query}`,
  );
  return mapWorkspaceMembershipList(response);
}

export async function leaveWorkspace(workspaceId?: string | null) {
  const response = await apiRequest<WorkspaceMembershipMutationResponseShape>(
    `${workspaceMembershipsKey}/leave`,
    {
      method: "POST",
      body: workspaceId ? { workspace_id: workspaceId } : {},
    },
  );
  return mapWorkspaceMembershipMutationResponse(response);
}

export async function removeWorkspaceMember(input: Readonly<{ userId: string; workspaceId?: string | null }>) {
  const response = await apiRequest<WorkspaceMembershipMutationResponseShape>(
    `${workspaceMembershipsKey}/${encodeURIComponent(input.userId)}/remove`,
    {
      method: "POST",
      body: input.workspaceId ? { workspace_id: input.workspaceId } : {},
    },
  );
  return mapWorkspaceMembershipMutationResponse(response);
}

export async function transferWorkspaceOwnership(input: Readonly<{ newOwnerUserId: string; workspaceId?: string | null }>) {
  const response = await apiRequest<WorkspaceMembershipMutationResponseShape>(
    `${workspaceMembershipsKey}/transfer-ownership`,
    {
      method: "POST",
      body: {
        workspace_id: input.workspaceId ?? null,
        new_owner_user_id: input.newOwnerUserId,
      },
    },
  );
  return mapWorkspaceMembershipMutationResponse(response);
}
