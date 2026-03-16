"use client";

import { apiRequest } from "@/lib/api/client";

export type RuntimeMode = "local" | "online";
export type SessionAuthState = "local_bypass" | "authenticated" | "anonymous" | "degraded";
type SessionAuthModeResponseShape =
  | "local_stub"
  | "development_stub"
  | "local_bypass"
  | "jwt_cookie"
  | "jwt_refresh_cookie";
export type SessionAuthMode = "local_stub" | "local_bypass" | "jwt_cookie" | "jwt_refresh_cookie";
export type SessionDefaultTaskScope = "local" | "workspace" | "owned";
export type SessionVisibilityScope = "local" | "private" | "workspace";
export type SessionRole = "owner" | "member" | "viewer";

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
  slug: string | null;
  name: string | null;
  role: SessionRole | null;
  default_task_scope: SessionDefaultTaskScope | null;
  is_active: boolean;
  allowed_actions: AllowedActionsResponseShape;
}>;

type SessionCapabilitiesResponseShape = Readonly<{
  can_switch_runtime_mode?: boolean;
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

type SessionConnectionResponseShape = Readonly<{
  target?: string | null;
  label?: string | null;
}> | null;

type SessionResponseShape = Readonly<{
  session_id: string | null;
  runtime_mode?: RuntimeMode | null;
  connection?: SessionConnectionResponseShape;
  auth: Readonly<{
    state: SessionAuthState;
    mode?: SessionAuthModeResponseShape | null;
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
    id: string | null;
    slug: string | null;
    name: string | null;
    role: SessionRole | null;
    default_task_scope: SessionDefaultTaskScope | null;
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
        owner_user_id: string | null;
        owner_display_name: string | null;
        workspace_id: string | null;
        visibility_scope: SessionVisibilityScope;
        lifecycle_state: "active" | "archived" | "deleted";
      }>
    | null;
  capabilities: SessionCapabilitiesResponseShape;
}>;

type WorkspaceSwitchResponseShape = SessionResponseShape &
  Readonly<{
    active_dataset_resolution: "preserved" | "rebound" | "cleared";
    detached_task_ids: readonly string[];
  }>;

type RuntimeModeSwitchResponseShape = Readonly<{
  runtime_mode: RuntimeMode;
  connection?: SessionConnectionResponseShape;
  auth_transition:
    | "local_ready"
    | "online_auth_required"
    | "online_target_rejected"
    | "context_cleared";
  session_reset: boolean;
  workspace:
    | Readonly<{
        id: string | null;
        name: string | null;
        role: SessionRole | null;
      }>
    | null;
  active_dataset:
    | Readonly<{
        id: string | null;
        name: string | null;
      }>
    | null;
  capabilities?: Partial<SessionCapabilitiesResponseShape>;
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
  canSwitchRuntimeMode: boolean;
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
  slug: string | null;
  displayName: string | null;
  role: SessionRole | null;
  defaultTaskScope: SessionDefaultTaskScope | null;
  isActive: boolean;
  allowedActions: SessionAllowedActions;
}>;

export type SessionConnectionSummary = Readonly<{
  target: string | null;
  label: string | null;
}>;

export type SessionSnapshot = Readonly<{
  sessionId: string | null;
  runtimeMode: RuntimeMode;
  connection: SessionConnectionSummary;
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
    workspaceId: string | null;
    slug: string | null;
    displayName: string | null;
    role: SessionRole | null;
    defaultTaskScope: SessionDefaultTaskScope | null;
    allowedActions: SessionAllowedActions;
  }>;
  memberships: ReadonlyArray<SessionMembership>;
  activeDataset:
    | Readonly<{
        datasetId: string;
        name: string;
        family: string;
        status: "Ready" | "Queued" | "Review";
        ownerUserId: string | null;
        owner: string | null;
        workspaceId: string | null;
        visibilityScope: SessionVisibilityScope;
        lifecycleState: "active" | "archived" | "deleted";
      }>
    | null;
}>;

export type WorkspaceSwitchResult = Readonly<{
  session: SessionSnapshot;
  activeDatasetResolution: "preserved" | "rebound" | "cleared";
  detachedTaskIds: readonly string[];
}>;

export type RuntimeModeSwitchInput = Readonly<{
  mode: RuntimeMode;
  serverOrigin?: string | null;
}>;

export type RuntimeModeSwitchResult = Readonly<{
  runtimeMode: RuntimeMode;
  connection: SessionConnectionSummary;
  authTransition:
    | "local_ready"
    | "online_auth_required"
    | "online_target_rejected"
    | "context_cleared";
  sessionReset: boolean;
  workspaceName: string | null;
  workspaceRole: SessionRole | null;
  activeDatasetName: string | null;
  capabilities: Partial<SessionCapabilities>;
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
const runtimeModePath = `${appSessionKey}/runtime-mode`;

const defaultAllowedActions: SessionAllowedActions = {
  switchTo: false,
  activateDataset: false,
  inviteMembers: false,
  removeMembers: false,
  transferOwner: false,
  leaveWorkspace: false,
  viewAuditLogs: false,
  manageDefinitions: false,
  manageDatasets: false,
  manageTasks: false,
};

const defaultCapabilities: SessionCapabilities = {
  canSwitchRuntimeMode: false,
  canSwitchWorkspace: false,
  canSwitchDataset: false,
  canInviteMembers: false,
  canRemoveMembers: false,
  canTransferWorkspaceOwner: false,
  canLeaveWorkspace: false,
  canSubmitTasks: false,
  canManageWorkspaceTasks: false,
  canCancelOwnTasks: false,
  canCancelWorkspaceTasks: false,
  canTerminateWorkspaceTasks: false,
  canRetryOwnTasks: false,
  canRetryWorkspaceTasks: false,
  canManageDefinitions: false,
  canManageDatasets: false,
  canViewAuditLogs: false,
};

function mapAllowedActions(payload?: AllowedActionsResponseShape | null): SessionAllowedActions {
  if (!payload) {
    return defaultAllowedActions;
  }

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

function mapCapabilities(
  payload?: Partial<SessionCapabilitiesResponseShape> | null,
): SessionCapabilities {
  return {
    canSwitchRuntimeMode: payload?.can_switch_runtime_mode ?? false,
    canSwitchWorkspace: payload?.can_switch_workspace ?? false,
    canSwitchDataset: payload?.can_switch_dataset ?? false,
    canInviteMembers: payload?.can_invite_members ?? false,
    canRemoveMembers: payload?.can_remove_members ?? false,
    canTransferWorkspaceOwner: payload?.can_transfer_workspace_owner ?? false,
    canLeaveWorkspace: payload?.can_leave_workspace ?? false,
    canSubmitTasks: payload?.can_submit_tasks ?? false,
    canManageWorkspaceTasks: payload?.can_manage_workspace_tasks ?? false,
    canCancelOwnTasks: payload?.can_cancel_own_tasks ?? false,
    canCancelWorkspaceTasks: payload?.can_cancel_workspace_tasks ?? false,
    canTerminateWorkspaceTasks: payload?.can_terminate_workspace_tasks ?? false,
    canRetryOwnTasks: payload?.can_retry_own_tasks ?? false,
    canRetryWorkspaceTasks: payload?.can_retry_workspace_tasks ?? false,
    canManageDefinitions: payload?.can_manage_definitions ?? false,
    canManageDatasets: payload?.can_manage_datasets ?? false,
    canViewAuditLogs: payload?.can_view_audit_logs ?? false,
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

function mapConnection(payload?: SessionConnectionResponseShape): SessionConnectionSummary {
  return {
    target: payload?.target ?? null,
    label: payload?.label ?? null,
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

function resolveRuntimeMode(payload: SessionResponseShape): RuntimeMode {
  if (payload.runtime_mode) {
    return payload.runtime_mode;
  }

  if (payload.auth.state === "local_bypass") {
    return "local";
  }

  if (payload.connection?.target === "local") {
    return "local";
  }

  if (payload.workspace.name === "Local Space") {
    return "local";
  }

  return "online";
}

export function normalizeSessionAuthMode(
  mode: SessionAuthModeResponseShape | null | undefined,
): SessionAuthMode {
  if (mode === "development_stub" || mode === "local_stub") {
    return "local_stub";
  }

  if (mode === "jwt_cookie" || mode === "jwt_refresh_cookie") {
    return mode;
  }

  return "local_bypass";
}

export function mapSessionResponse(payload: SessionResponseShape): SessionSnapshot {
  const capabilities = mapCapabilities(payload.capabilities);
  const memberships = payload.workspace.memberships ?? payload.memberships ?? [];

  return {
    sessionId: payload.session_id ?? null,
    runtimeMode: resolveRuntimeMode(payload),
    connection: mapConnection(payload.connection),
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

export function mapRuntimeModeSwitchResponse(
  payload: RuntimeModeSwitchResponseShape,
): RuntimeModeSwitchResult {
  return {
    runtimeMode: payload.runtime_mode,
    connection: mapConnection(payload.connection),
    authTransition: payload.auth_transition,
    sessionReset: payload.session_reset,
    workspaceName: payload.workspace?.name ?? null,
    workspaceRole: payload.workspace?.role ?? null,
    activeDatasetName: payload.active_dataset?.name ?? null,
    capabilities: mapCapabilities(payload.capabilities ?? null),
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

export async function switchRuntimeMode(input: RuntimeModeSwitchInput) {
  const response = await apiRequest<RuntimeModeSwitchResponseShape>(runtimeModePath, {
    method: "POST",
    body: {
      mode: input.mode,
      server_origin: input.serverOrigin ?? null,
    },
  });

  return mapRuntimeModeSwitchResponse(response);
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
