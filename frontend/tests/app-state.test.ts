import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  canRetryRouteDatasetSync,
  parseDatasetIdFromSearch,
  resolveActiveDatasetId,
  resolveActiveDatasetSource,
  resolveSearchWithDatasetId,
  shouldAutoSyncRouteDataset,
} from "../src/lib/app-state/active-dataset-state";
import { resolveSearchFromParams, resolveUrlSnapshot } from "../src/lib/app-state/url-state";
import {
  mapLoginResponse,
  mapLogoutResponse,
  mapRuntimeModeSwitchResponse,
  mapSessionResponse,
  resolveSessionConnectionTargetLabel,
  resolveSessionConnectionTargetOrigin,
  switchRuntimeMode,
  mapWorkspaceSwitchResponse,
  normalizeSessionAuthMode,
} from "../src/lib/api/session";
import { mapTaskQueueResponse, mapTaskSummaryResponse, mapWorkerLaneSummaryResponse } from "../src/lib/api/tasks";
import {
  resolveLatestTask,
  resolveTaskQueueRefreshInterval,
  summarizeTaskQueue,
} from "../src/lib/app-state/task-queue-store";

const appSessionSource = readFileSync(
  fileURLToPath(new URL("../src/lib/app-state/app-session.tsx", import.meta.url)),
  "utf8",
);
const taskQueueSource = readFileSync(
  fileURLToPath(new URL("../src/lib/app-state/task-queue.tsx", import.meta.url)),
  "utf8",
);
const activeTaskSource = readFileSync(
  fileURLToPath(new URL("../src/lib/app-state/active-task.tsx", import.meta.url)),
  "utf8",
);
const SIMULATION_SCHEMA_ID = "7f3a2c91-1d7f-4a55-9cfd-0f0b7d5c1001";
const SECONDARY_SIMULATION_SCHEMA_ID = "51cfd0e2-1a2f-4c1e-86d9-33f6b2d91003";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("active dataset state helpers", () => {
  it("parses dataset ids from URL search params", () => {
    expect(parseDatasetIdFromSearch("?datasetId=fluxonium-2025-031")).toBe("fluxonium-2025-031");
    expect(parseDatasetIdFromSearch("?datasetId=   ")).toBeNull();
    expect(parseDatasetIdFromSearch("")).toBeNull();
    expect(resolveSearchWithDatasetId("?taskId=31", "fluxonium-2025-031")).toBe(
      "?taskId=31&datasetId=fluxonium-2025-031",
    );
    expect(resolveSearchWithDatasetId("?taskId=31&datasetId=old", null)).toBe("?taskId=31");
  });

  it("prefers route state over preferred in-memory state", () => {
    expect(resolveActiveDatasetId("route-dataset", "session-dataset")).toBe("route-dataset");
    expect(resolveActiveDatasetId(null, "session-dataset")).toBe("session-dataset");
    expect(resolveActiveDatasetSource("route-dataset", "session-dataset")).toBe("url");
    expect(resolveActiveDatasetSource(null, "session-dataset")).toBe("session");
    expect(resolveActiveDatasetSource(null, null)).toBe("none");
  });

  it("suppresses repeated automatic route sync after a failed attach until inputs change", () => {
    expect(
      shouldAutoSyncRouteDataset("route-dataset", "session-dataset", {
        targetDatasetId: null,
        status: "idle",
      }),
    ).toBe(true);
    expect(
      shouldAutoSyncRouteDataset("route-dataset", "session-dataset", {
        targetDatasetId: "route-dataset",
        status: "error",
      }),
    ).toBe(false);
    expect(
      canRetryRouteDatasetSync("route-dataset", "session-dataset", {
        targetDatasetId: "route-dataset",
        status: "error",
      }),
    ).toBe(true);
    expect(
      canRetryRouteDatasetSync("route-dataset", "route-dataset", {
        targetDatasetId: "route-dataset",
        status: "error",
      }),
    ).toBe(false);
  });
});

describe("url state snapshot helpers", () => {
  it("derives the search string from Next-style URLSearchParams without patching history", () => {
    expect(
      resolveSearchFromParams(
        new URLSearchParams(`definitionId=${SECONDARY_SIMULATION_SCHEMA_ID}&taskId=31`),
      ),
    ).toBe(
      `?definitionId=${SECONDARY_SIMULATION_SCHEMA_ID}&taskId=31`,
    );
    expect(resolveSearchFromParams(new URLSearchParams())).toBe("");
    expect(resolveSearchFromParams(null)).toBe("");
  });

  it("reuses the previous snapshot object when pathname and search are unchanged", () => {
    const snapshot = {
      pathname: "/circuit-simulation",
      search: `?definitionId=${SIMULATION_SCHEMA_ID}&taskId=31`,
    } as const;

    expect(resolveUrlSnapshot(snapshot, snapshot.pathname, snapshot.search)).toBe(snapshot);
  });

  it("returns a new snapshot when pathname or search changes", () => {
    const snapshot = {
      pathname: "/circuit-simulation",
      search: `?definitionId=${SIMULATION_SCHEMA_ID}`,
    } as const;

    expect(
      resolveUrlSnapshot(
        snapshot,
        "/circuit-simulation",
        `?definitionId=${SECONDARY_SIMULATION_SCHEMA_ID}`,
      ),
    ).toEqual({
      pathname: "/circuit-simulation",
      search: `?definitionId=${SECONDARY_SIMULATION_SCHEMA_ID}`,
    });
    expect(resolveUrlSnapshot(snapshot, "/raw-data", "?datasetId=fluxonium-2025-031")).toEqual({
      pathname: "/raw-data",
      search: "?datasetId=fluxonium-2025-031",
    });
  });
});

describe("session contract mapping", () => {
  it("maps backend session payloads into the frontend session snapshot", () => {
    expect(
      mapSessionResponse({
        session_id: "session-dev-001",
        runtime_mode: "online",
        connection: {
          target: {
            origin: "https://lab.example.com",
            label: "Lab Cluster",
            is_active: true,
            validation_status: "ok",
            last_checked_at: "2026-03-17T00:00:00Z",
          },
        },
        auth: {
          state: "authenticated",
          mode: "local_stub",
        },
        user: {
          id: "user-dev-01",
          display_name: "Device Lab",
          email: "device-lab@example.com",
          platform_role: "user",
        },
        workspace: {
          id: "workspace-lab",
          slug: "device-lab",
          name: "Device Lab",
          role: "owner",
          default_task_scope: "workspace",
          allowed_actions: {
            switch_to: true,
            activate_dataset: true,
            invite_members: true,
            remove_members: true,
            transfer_owner: true,
            leave_workspace: false,
            view_audit_logs: false,
            manage_definitions: true,
            manage_datasets: true,
            manage_tasks: true,
          },
          memberships: [
            {
              id: "workspace-lab",
              slug: "device-lab",
              name: "Device Lab",
              role: "owner",
              default_task_scope: "workspace",
              is_active: true,
              allowed_actions: {
                switch_to: true,
                activate_dataset: true,
                invite_members: true,
                remove_members: true,
                transfer_owner: true,
                leave_workspace: false,
                view_audit_logs: false,
                manage_definitions: true,
                manage_datasets: true,
                manage_tasks: true,
              },
            },
          ],
        },
        active_dataset: {
          id: "fluxonium-2025-031",
          name: "Fluxonium sweep 031",
          family: "Fluxonium",
          status: "Ready",
          owner_user_id: "user-dev-01",
          owner_display_name: "Device Lab",
          workspace_id: "workspace-lab",
          visibility_scope: "workspace",
          lifecycle_state: "active",
        },
        capabilities: {
          can_switch_workspace: false,
          can_switch_dataset: true,
          can_invite_members: true,
          can_remove_members: true,
          can_transfer_workspace_owner: true,
          can_leave_workspace: false,
          can_submit_tasks: true,
          can_manage_workspace_tasks: true,
          can_cancel_own_tasks: true,
          can_cancel_workspace_tasks: true,
          can_terminate_workspace_tasks: true,
          can_retry_own_tasks: true,
          can_retry_workspace_tasks: true,
          can_manage_definitions: true,
          can_manage_datasets: true,
          can_view_audit_logs: false,
        },
      }),
    ).toEqual({
      sessionId: "session-dev-001",
      runtimeMode: "online",
      connection: {
        target: {
          kind: "remote",
          origin: "https://lab.example.com",
          label: "Lab Cluster",
          isActive: true,
          validationStatus: "ok",
          lastCheckedAt: "2026-03-17T00:00:00Z",
        },
        origin: "https://lab.example.com",
        label: "Lab Cluster",
        isActive: true,
        validationStatus: "ok",
        lastCheckedAt: "2026-03-17T00:00:00Z",
      },
      authState: "authenticated",
      authMode: "local_stub",
      authReason: null,
      capabilities: {
        canSwitchRuntimeMode: false,
        canSwitchWorkspace: false,
        canSwitchDataset: true,
        canInviteMembers: true,
        canRemoveMembers: true,
        canTransferWorkspaceOwner: true,
        canLeaveWorkspace: false,
        canSubmitTasks: true,
        canManageWorkspaceTasks: true,
        canCancelOwnTasks: true,
        canCancelWorkspaceTasks: true,
        canTerminateWorkspaceTasks: true,
        canRetryOwnTasks: true,
        canRetryWorkspaceTasks: true,
        canManageDefinitions: true,
        canManageDatasets: true,
        canViewAuditLogs: false,
      },
      canSubmitTasks: true,
      canManageDatasets: true,
      canManageDefinitions: true,
      canInviteMembers: true,
      canRemoveMembers: true,
      canTransferWorkspaceOwner: true,
      canLeaveWorkspace: false,
      user: {
        userId: "user-dev-01",
        displayName: "Device Lab",
        email: "device-lab@example.com",
        platformRole: "user",
      },
      workspace: {
        workspaceId: "workspace-lab",
        slug: "device-lab",
        displayName: "Device Lab",
        role: "owner",
        defaultTaskScope: "workspace",
        allowedActions: {
          switchTo: true,
          activateDataset: true,
          inviteMembers: true,
          removeMembers: true,
          transferOwner: true,
          leaveWorkspace: false,
          viewAuditLogs: false,
          manageDefinitions: true,
          manageDatasets: true,
          manageTasks: true,
        },
      },
      memberships: [
        {
          workspaceId: "workspace-lab",
          slug: "device-lab",
          displayName: "Device Lab",
          role: "owner",
          defaultTaskScope: "workspace",
          isActive: true,
          allowedActions: {
            switchTo: true,
            activateDataset: true,
            inviteMembers: true,
            removeMembers: true,
            transferOwner: true,
            leaveWorkspace: false,
            viewAuditLogs: false,
            manageDefinitions: true,
            manageDatasets: true,
            manageTasks: true,
          },
        },
      ],
      activeDataset: {
        datasetId: "fluxonium-2025-031",
        name: "Fluxonium sweep 031",
        family: "Fluxonium",
        status: "Ready",
        ownerUserId: "user-dev-01",
        owner: "Device Lab",
        workspaceId: "workspace-lab",
        visibilityScope: "workspace",
        lifecycleState: "active",
      },
    });
  });

  it("keeps local-mode refresh on the session envelope path instead of the auth-refresh path", () => {
    expect(appSessionSource).toContain('runtimeMode === "local"');
    expect(appSessionSource).toContain("await getSession()");
    expect(appSessionSource).toContain("await refreshCurrentSession()");
  });

  it("preserves broader auth states and modes from the session surface", () => {
    expect(
      mapSessionResponse({
        session_id: "session-dev-002",
        auth: {
          state: "degraded",
          mode: "jwt_cookie",
        },
        user: null,
        workspace: {
          id: "workspace-lab",
          slug: "device-lab",
          name: "Device Lab",
          role: "viewer",
          default_task_scope: "workspace",
          allowed_actions: {
            switch_to: true,
            activate_dataset: false,
            invite_members: false,
            remove_members: false,
            transfer_owner: false,
            leave_workspace: false,
            view_audit_logs: false,
            manage_definitions: false,
            manage_datasets: false,
            manage_tasks: false,
          },
          memberships: [],
        },
        active_dataset: null,
        capabilities: {
          can_switch_workspace: true,
          can_switch_dataset: false,
          can_invite_members: false,
          can_remove_members: false,
          can_transfer_workspace_owner: false,
          can_leave_workspace: false,
          can_submit_tasks: false,
          can_manage_workspace_tasks: false,
          can_cancel_own_tasks: false,
          can_cancel_workspace_tasks: false,
          can_terminate_workspace_tasks: false,
          can_retry_own_tasks: false,
          can_retry_workspace_tasks: false,
          can_manage_definitions: false,
          can_manage_datasets: false,
          can_view_audit_logs: false,
        },
      }),
    ).toMatchObject({
      authState: "degraded",
      authMode: "jwt_cookie",
      authReason: null,
    });
  });

  it("maps nested server target summaries into frontend-friendly connection details", () => {
    const session = mapSessionResponse({
      session_id: "session-dev-009",
      runtime_mode: "online",
      connection: {
        target: {
          origin: "https://lab.example.com",
          label: "Lab Cluster",
          is_active: true,
          validation_status: "ok",
          last_checked_at: "2026-03-17T08:00:00Z",
        },
      },
      auth: {
        state: "anonymous",
        mode: "jwt_cookie",
      },
      user: null,
      workspace: {
        id: null,
        slug: null,
        name: null,
        role: null,
        default_task_scope: "workspace",
        allowed_actions: {
          switch_to: false,
          activate_dataset: false,
          invite_members: false,
          remove_members: false,
          transfer_owner: false,
          leave_workspace: false,
          view_audit_logs: false,
          manage_definitions: false,
          manage_datasets: false,
          manage_tasks: false,
        },
        memberships: [],
      },
      active_dataset: null,
      capabilities: {
        can_switch_runtime_mode: true,
        can_switch_workspace: false,
        can_switch_dataset: false,
        can_invite_members: false,
        can_remove_members: false,
        can_transfer_workspace_owner: false,
        can_leave_workspace: false,
        can_submit_tasks: false,
        can_manage_workspace_tasks: false,
        can_cancel_own_tasks: false,
        can_cancel_workspace_tasks: false,
        can_terminate_workspace_tasks: false,
        can_retry_own_tasks: false,
        can_retry_workspace_tasks: false,
        can_manage_definitions: false,
        can_manage_datasets: false,
        can_view_audit_logs: false,
      },
    });

    expect(session.connection).toEqual({
      target: {
        kind: "remote",
        origin: "https://lab.example.com",
        label: "Lab Cluster",
        isActive: true,
        validationStatus: "ok",
        lastCheckedAt: "2026-03-17T08:00:00Z",
      },
      origin: "https://lab.example.com",
      label: "Lab Cluster",
      isActive: true,
      validationStatus: "ok",
      lastCheckedAt: "2026-03-17T08:00:00Z",
    });
    expect(resolveSessionConnectionTargetOrigin(session.connection)).toBe("https://lab.example.com");
    expect(resolveSessionConnectionTargetLabel(session.connection)).toBe("Lab Cluster");
  });

  it("normalizes legacy development stub auth modes and canonical auth mutation payloads", () => {
    expect(normalizeSessionAuthMode("development_stub")).toBe("local_stub");
    expect(
      mapLoginResponse({
        session_id: "session-dev-003",
        auth: {
          state: "authenticated",
          mode: "development_stub",
        },
        user: {
          id: "user-dev-02",
          display_name: "Lab Operator",
          email: "lab.operator@example.com",
          platform_role: "admin",
        },
        workspace: {
          id: "workspace-lab",
          slug: "device-lab",
          name: "Device Lab",
          role: "owner",
          default_task_scope: "workspace",
          allowed_actions: {
            switch_to: true,
            activate_dataset: true,
            invite_members: true,
            remove_members: true,
            transfer_owner: true,
            leave_workspace: false,
            view_audit_logs: true,
            manage_definitions: true,
            manage_datasets: true,
            manage_tasks: true,
          },
        },
        active_dataset: null,
        capabilities: {
          can_switch_workspace: true,
          can_switch_dataset: true,
          can_invite_members: true,
          can_remove_members: true,
          can_transfer_workspace_owner: true,
          can_leave_workspace: false,
          can_submit_tasks: true,
          can_manage_workspace_tasks: true,
          can_cancel_own_tasks: true,
          can_cancel_workspace_tasks: true,
          can_terminate_workspace_tasks: true,
          can_retry_own_tasks: true,
          can_retry_workspace_tasks: true,
          can_manage_definitions: true,
          can_manage_datasets: true,
          can_view_audit_logs: true,
        },
      }),
    ).toMatchObject({
      authState: "authenticated",
      authMode: "local_stub",
      user: {
        email: "lab.operator@example.com",
      },
    });
    expect(
      mapLogoutResponse({
        session_id: "session-dev-003",
        auth: {
          state: "anonymous",
          mode: "jwt_cookie",
          reason: "logged_out",
        },
        user: null,
        workspace: {
          id: "workspace-lab",
          slug: "device-lab",
          name: "Device Lab",
          role: "viewer",
          default_task_scope: "workspace",
          allowed_actions: {
            switch_to: false,
            activate_dataset: false,
            invite_members: false,
            remove_members: false,
            transfer_owner: false,
            leave_workspace: false,
            view_audit_logs: false,
            manage_definitions: false,
            manage_datasets: false,
            manage_tasks: false,
          },
        },
        active_dataset: null,
        capabilities: {
          can_switch_workspace: false,
          can_switch_dataset: false,
          can_invite_members: false,
          can_remove_members: false,
          can_transfer_workspace_owner: false,
          can_leave_workspace: false,
          can_submit_tasks: false,
          can_manage_workspace_tasks: false,
          can_cancel_own_tasks: false,
          can_cancel_workspace_tasks: false,
          can_terminate_workspace_tasks: false,
          can_retry_own_tasks: false,
          can_retry_workspace_tasks: false,
          can_manage_definitions: false,
          can_manage_datasets: false,
          can_view_audit_logs: false,
        },
      }),
    ).toMatchObject({
      authState: "anonymous",
      authMode: "jwt_cookie",
      authReason: "logged_out",
    });
  });

  it("maps workspace switch responses into session plus rebind outcome", () => {
    expect(
      mapWorkspaceSwitchResponse({
        session_id: "session-dev-001",
        runtime_mode: "online",
        connection: {
          target: {
            origin: "https://lab.example.com",
            label: "Lab Cluster",
            is_active: true,
            validation_status: "ok",
            last_checked_at: "2026-03-17T08:15:00Z",
          },
        },
        auth: {
          state: "authenticated",
          mode: "local_stub",
        },
        user: {
          id: "user-dev-01",
          display_name: "Device Lab",
          email: "device-lab@example.com",
          platform_role: "user",
        },
        workspace: {
          id: "workspace-modeling",
          slug: "modeling",
          name: "Modeling",
          role: "member",
          default_task_scope: "owned",
          allowed_actions: {
            switch_to: true,
            activate_dataset: true,
            invite_members: false,
            remove_members: false,
            transfer_owner: false,
            leave_workspace: false,
            view_audit_logs: false,
            manage_definitions: true,
            manage_datasets: true,
            manage_tasks: false,
          },
          memberships: [
            {
              id: "workspace-lab",
              slug: "device-lab",
              name: "Device Lab",
              role: "owner",
              default_task_scope: "workspace",
              is_active: false,
              allowed_actions: {
                switch_to: true,
                activate_dataset: true,
                invite_members: true,
                remove_members: true,
                transfer_owner: true,
                leave_workspace: false,
                view_audit_logs: false,
                manage_definitions: true,
                manage_datasets: true,
                manage_tasks: true,
              },
            },
            {
              id: "workspace-modeling",
              slug: "modeling",
              name: "Modeling",
              role: "member",
              default_task_scope: "owned",
              is_active: true,
              allowed_actions: {
                switch_to: true,
                activate_dataset: true,
                invite_members: false,
                remove_members: false,
                transfer_owner: false,
                leave_workspace: false,
                view_audit_logs: false,
                manage_definitions: true,
                manage_datasets: true,
                manage_tasks: false,
              },
            },
          ],
        },
        active_dataset: {
          id: "transmon-coupler-014",
          name: "Transmon Coupler 014",
          family: "Transmon",
          status: "Review",
          owner_user_id: "user-dev-01",
          owner_display_name: "Device Lab",
          workspace_id: "workspace-modeling",
          visibility_scope: "workspace",
          lifecycle_state: "active",
        },
        capabilities: {
          can_switch_workspace: true,
          can_switch_dataset: true,
          can_invite_members: false,
          can_remove_members: false,
          can_transfer_workspace_owner: false,
          can_leave_workspace: false,
          can_submit_tasks: true,
          can_manage_workspace_tasks: false,
          can_cancel_own_tasks: true,
          can_cancel_workspace_tasks: false,
          can_terminate_workspace_tasks: false,
          can_retry_own_tasks: true,
          can_retry_workspace_tasks: false,
          can_manage_definitions: true,
          can_manage_datasets: true,
          can_view_audit_logs: false,
        },
        active_dataset_resolution: "rebound",
        detached_task_ids: ["task_402"],
      }),
    ).toEqual({
      session: {
        sessionId: "session-dev-001",
        runtimeMode: "online",
        connection: {
          target: {
            kind: "remote",
            origin: "https://lab.example.com",
            label: "Lab Cluster",
            isActive: true,
            validationStatus: "ok",
            lastCheckedAt: "2026-03-17T08:15:00Z",
          },
          origin: "https://lab.example.com",
          label: "Lab Cluster",
          isActive: true,
          validationStatus: "ok",
          lastCheckedAt: "2026-03-17T08:15:00Z",
        },
        authState: "authenticated",
        authMode: "local_stub",
        authReason: null,
        capabilities: {
          canSwitchRuntimeMode: false,
          canSwitchWorkspace: true,
          canSwitchDataset: true,
          canInviteMembers: false,
          canRemoveMembers: false,
          canTransferWorkspaceOwner: false,
          canLeaveWorkspace: false,
          canSubmitTasks: true,
          canManageWorkspaceTasks: false,
          canCancelOwnTasks: true,
          canCancelWorkspaceTasks: false,
          canTerminateWorkspaceTasks: false,
          canRetryOwnTasks: true,
          canRetryWorkspaceTasks: false,
          canManageDefinitions: true,
          canManageDatasets: true,
          canViewAuditLogs: false,
        },
        canSubmitTasks: true,
        canManageDatasets: true,
        canManageDefinitions: true,
        canInviteMembers: false,
        canRemoveMembers: false,
        canTransferWorkspaceOwner: false,
        canLeaveWorkspace: false,
        user: {
          userId: "user-dev-01",
          displayName: "Device Lab",
          email: "device-lab@example.com",
          platformRole: "user",
        },
        workspace: {
          workspaceId: "workspace-modeling",
          slug: "modeling",
          displayName: "Modeling",
          role: "member",
          defaultTaskScope: "owned",
          allowedActions: {
            switchTo: true,
            activateDataset: true,
            inviteMembers: false,
            removeMembers: false,
            transferOwner: false,
            leaveWorkspace: false,
            viewAuditLogs: false,
            manageDefinitions: true,
            manageDatasets: true,
            manageTasks: false,
          },
        },
        memberships: [
          {
            workspaceId: "workspace-lab",
            slug: "device-lab",
            displayName: "Device Lab",
            role: "owner",
            defaultTaskScope: "workspace",
            isActive: false,
            allowedActions: {
              switchTo: true,
              activateDataset: true,
              inviteMembers: true,
              removeMembers: true,
              transferOwner: true,
              leaveWorkspace: false,
              viewAuditLogs: false,
              manageDefinitions: true,
              manageDatasets: true,
              manageTasks: true,
            },
          },
          {
            workspaceId: "workspace-modeling",
            slug: "modeling",
            displayName: "Modeling",
            role: "member",
            defaultTaskScope: "owned",
            isActive: true,
            allowedActions: {
              switchTo: true,
              activateDataset: true,
              inviteMembers: false,
              removeMembers: false,
              transferOwner: false,
              leaveWorkspace: false,
              viewAuditLogs: false,
              manageDefinitions: true,
              manageDatasets: true,
              manageTasks: false,
            },
          },
        ],
        activeDataset: {
          datasetId: "transmon-coupler-014",
          name: "Transmon Coupler 014",
          family: "Transmon",
          status: "Review",
          ownerUserId: "user-dev-01",
          owner: "Device Lab",
          workspaceId: "workspace-modeling",
          visibilityScope: "workspace",
          lifecycleState: "active",
        },
      },
      activeDatasetResolution: "rebound",
      detachedTaskIds: ["task_402"],
    });
  });

  it("maps runtime-mode switch responses through the shared backend mutation contract", () => {
    expect(
      mapRuntimeModeSwitchResponse({
        runtime_mode: "online",
        connection: {
          target: {
            origin: "http://127.0.0.1:8000",
            label: "Local server",
            is_active: true,
            validation_status: "ok",
            last_checked_at: "2026-03-17T09:00:00Z",
          },
        },
        auth_transition: "online_auth_required",
        session_reset: true,
        workspace: {
          id: null,
          name: null,
          role: null,
        },
        active_dataset: {
          id: null,
          name: null,
        },
        capabilities: {
          can_switch_runtime_mode: true,
          can_switch_workspace: false,
          can_switch_dataset: false,
          can_manage_definitions: false,
          can_manage_datasets: false,
          can_submit_tasks: false,
        },
        detached_task_ids: ["task_404"],
      }),
    ).toEqual({
      runtimeMode: "online",
      connection: {
        target: {
          kind: "remote",
          origin: "http://127.0.0.1:8000",
          label: "Local server",
          isActive: true,
          validationStatus: "ok",
          lastCheckedAt: "2026-03-17T09:00:00Z",
        },
        origin: "http://127.0.0.1:8000",
        label: "Local server",
        isActive: true,
        validationStatus: "ok",
        lastCheckedAt: "2026-03-17T09:00:00Z",
      },
      authTransition: "online_auth_required",
      sessionReset: true,
      workspaceName: null,
      workspaceRole: null,
      activeDatasetName: null,
      capabilities: {
        canSwitchRuntimeMode: true,
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
      },
      detachedTaskIds: ["task_404"],
    });
  });

  it("accepts the live backend runtime transition enums without frontend-only fallbacks", () => {
    expect(
      mapRuntimeModeSwitchResponse({
        runtime_mode: "local",
        connection: {
          target: "local",
        },
        auth_transition: "entered_local_bypass",
        session_reset: true,
        workspace: {
          id: null,
          name: null,
          role: null,
        },
        active_dataset: {
          id: null,
          name: null,
        },
        capabilities: {
          can_switch_runtime_mode: true,
        },
        detached_task_ids: [],
      }).authTransition,
    ).toBe("entered_local_bypass");

    expect(
      mapRuntimeModeSwitchResponse({
        runtime_mode: "online",
        connection: {
          target: {
            origin: "http://127.0.0.1:8000",
            label: "Lab Cluster",
            is_active: true,
            validation_status: "validated",
            last_checked_at: "2026-03-17T09:12:00Z",
          },
        },
        auth_transition: "online_session_dropped",
        session_reset: true,
        workspace: {
          id: null,
          name: null,
          role: null,
        },
        active_dataset: {
          id: null,
          name: null,
        },
        capabilities: {
          can_switch_runtime_mode: true,
        },
        detached_task_ids: ["task_17"],
      }).authTransition,
    ).toBe("online_session_dropped");
  });

  it("uses PATCH and runtime_mode for runtime-mode mutation requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        data: {
          runtime_mode: "online",
          connection: {
            target: {
              origin: "http://127.0.0.1:8000",
              label: "Local server",
              is_active: true,
              validation_status: "ok",
              last_checked_at: "2026-03-17T09:10:00Z",
            },
          },
          auth_transition: "online_auth_required",
          session_reset: true,
          workspace: null,
          active_dataset: null,
          capabilities: {
            can_switch_runtime_mode: true,
          },
          detached_task_ids: [],
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    await switchRuntimeMode({
      mode: "online",
      serverOrigin: "http://127.0.0.1:8000",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/session/runtime-mode",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          runtime_mode: "online",
          server_origin: "http://127.0.0.1:8000",
        }),
      }),
    );
  });
});

describe("task queue store", () => {
  it("maps backend task queue rows into the frontend queue shape", () => {
    expect(
      mapTaskSummaryResponse({
        task_id: 14,
        task_kind: "simulation",
        lane: "simulation",
        status: "running",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:30:00",
        result_availability: "ready",
        control_state: "none",
        reconcile: {
          required: true,
          reason: "queue_job_missing",
          recorded_at: "2026-03-12 01:31:00",
        },
        summary: "Fluxonium sweep queued from workspace",
        allowed_actions: {
          attach: true,
          cancel: false,
          retry: true,
          terminate: false,
          rejection_reason: "Only owners can cancel this task.",
        },
      }),
    ).toEqual({
      taskId: 14,
      kind: "simulation",
      lane: "simulation",
      executionMode: null,
      status: "running",
      submittedAt: null,
      updatedAt: "2026-03-12 01:30:00",
      ownerUserId: null,
      ownerDisplayName: "Device Lab",
      workspaceId: null,
      workspaceSlug: null,
      visibilityScope: "workspace",
      datasetId: null,
      definitionId: null,
      summary: "Fluxonium sweep queued from workspace",
      resultAvailability: "ready",
      controlState: "none",
      reconcile: {
        required: true,
        reason: "queue_job_missing",
        recordedAt: "2026-03-12 01:31:00",
      },
      allowedActions: {
        attach: true,
        cancel: false,
        retry: true,
        terminate: false,
        rejectionReason: "Only owners can cancel this task.",
      },
      hasActionAuthority: true,
    });
  });

  it("maps backend worker summary rows and queue envelopes", () => {
    expect(
      mapWorkerLaneSummaryResponse({
        lane: "simulation",
        healthy_processors: 1,
        busy_processors: 2,
        degraded_processors: 3,
        draining_processors: 4,
        offline_processors: 5,
      }),
    ).toEqual({
      lane: "simulation",
      healthyProcessors: 1,
      busyProcessors: 2,
      degradedProcessors: 3,
      drainingProcessors: 4,
      offlineProcessors: 5,
    });

    expect(
      mapTaskQueueResponse(
        {
          rows: [
            {
              task_id: 31,
              task_kind: "characterization",
              lane: "characterization",
              status: "queued",
              owner_display_name: "Local",
              visibility_scope: "local",
              updated_at: "2026-03-17T12:00:00Z",
              result_availability: "pending",
              control_state: "none",
              reconcile: {
                required: false,
                reason: null,
                recorded_at: null,
              },
              summary: "Queued characterization",
              allowed_actions: {
                attach: true,
                cancel: true,
                terminate: false,
                retry: false,
                rejection_reason: null,
              },
            },
          ],
          worker_summary: [
            {
              lane: "characterization",
              healthy_processors: 1,
              busy_processors: 0,
              degraded_processors: 0,
              draining_processors: 0,
              offline_processors: 0,
            },
          ],
        },
        {
          generated_at: "2026-03-17T12:00:00Z",
          total_count: 1,
        },
      ),
    ).toEqual({
      rows: [
        {
          taskId: 31,
          kind: "characterization",
          lane: "characterization",
          executionMode: null,
          status: "queued",
          submittedAt: null,
          updatedAt: "2026-03-17T12:00:00Z",
          ownerUserId: null,
          ownerDisplayName: "Local",
          workspaceId: null,
          workspaceSlug: null,
          visibilityScope: "local",
          datasetId: null,
          definitionId: null,
          summary: "Queued characterization",
          resultAvailability: "pending",
          controlState: "none",
          reconcile: {
            required: false,
            reason: null,
            recordedAt: null,
          },
          hasActionAuthority: true,
          allowedActions: {
            attach: true,
            cancel: true,
            terminate: false,
            retry: false,
            rejectionReason: null,
          },
        },
      ],
      workerSummary: [
        {
          lane: "characterization",
          healthyProcessors: 1,
          busyProcessors: 0,
          degradedProcessors: 0,
          drainingProcessors: 0,
          offlineProcessors: 0,
        },
      ],
      generatedAt: "2026-03-17T12:00:00Z",
      totalCount: 1,
      nextCursor: null,
      prevCursor: null,
      hasMore: false,
    });
  });

  it("summarizes task counts by backend status", () => {
    const tasks = [
      mapTaskSummaryResponse({
        task_id: 11,
        task_kind: "simulation",
        lane: "simulation",
        status: "queued",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:20:00",
        result_availability: "pending",
        control_state: "none",
        summary: "Queued simulation",
        allowed_actions: {
          attach: true,
          cancel: true,
          retry: false,
          terminate: false,
          rejection_reason: null,
        },
      }),
      mapTaskSummaryResponse({
        task_id: 12,
        task_kind: "characterization",
        lane: "characterization",
        status: "running",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:21:00",
        result_availability: "pending",
        control_state: "none",
        summary: "Running characterization",
        allowed_actions: {
          attach: true,
          cancel: false,
          retry: false,
          terminate: false,
          rejection_reason: null,
        },
      }),
      mapTaskSummaryResponse({
        task_id: 13,
        task_kind: "post_processing",
        lane: "characterization",
        status: "failed",
        owner_display_name: "Device Lab",
        visibility_scope: "owned",
        updated_at: "2026-03-12 01:22:00",
        result_availability: "none",
        control_state: "none",
        summary: "Failed post-processing",
        allowed_actions: {
          attach: true,
          cancel: false,
          retry: true,
          terminate: false,
          rejection_reason: null,
        },
      }),
      mapTaskSummaryResponse({
        task_id: 14,
        task_kind: "simulation",
        lane: "simulation",
        status: "completed",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:23:00",
        result_availability: "ready",
        control_state: "none",
        summary: "Completed simulation",
        allowed_actions: {
          attach: true,
          cancel: false,
          retry: true,
          terminate: false,
          rejection_reason: null,
        },
      }),
      mapTaskSummaryResponse({
        task_id: 15,
        task_kind: "simulation",
        lane: "simulation",
        status: "cancelled",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:24:00",
        result_availability: "none",
        control_state: "cancellation_requested",
        summary: "Cancelled simulation",
        allowed_actions: {
          attach: true,
          cancel: false,
          retry: true,
          terminate: false,
          rejection_reason: null,
        },
      }),
    ];

    expect(summarizeTaskQueue(tasks)).toEqual({
      total: 5,
      pendingCount: 1,
      runningCount: 1,
      failedCount: 1,
      completedCount: 1,
      cancelledCount: 1,
      terminatedCount: 0,
    });
  });

  it("keeps polling while the backend still reports active tasks", () => {
    const activeTasks = [
      mapTaskSummaryResponse({
        task_id: 21,
        task_kind: "simulation",
        lane: "simulation",
        status: "running",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:40:00",
        result_availability: "pending",
        control_state: "none",
        summary: "Running simulation",
        allowed_actions: {
          attach: true,
          cancel: true,
          retry: false,
          terminate: false,
          rejection_reason: null,
        },
      }),
    ];
    const settledTasks = [
      mapTaskSummaryResponse({
        task_id: 22,
        task_kind: "simulation",
        lane: "simulation",
        status: "completed",
        owner_display_name: "Device Lab",
        visibility_scope: "workspace",
        updated_at: "2026-03-12 01:41:00",
        result_availability: "ready",
        control_state: "none",
        summary: "Completed simulation",
        allowed_actions: {
          attach: true,
          cancel: false,
          retry: true,
          terminate: false,
          rejection_reason: null,
        },
      }),
    ];

    expect(resolveTaskQueueRefreshInterval(activeTasks)).toBe(5_000);
    expect(resolveTaskQueueRefreshInterval(settledTasks)).toBe(0);
    expect(resolveLatestTask(activeTasks)?.taskId).toBe(21);
    expect(resolveLatestTask(settledTasks)?.taskId).toBe(22);
  });
});

describe("runtime-mode app-state source contracts", () => {
  it("routes runtime-mode switching through the shared backend session owner", () => {
    expect(appSessionSource).toContain("switchRuntimeMode as switchRuntimeModeApi");
    expect(appSessionSource).toContain("const result = await switchRuntimeModeApi({");
    expect(appSessionSource).toContain("const nextSession = await getSession()");
    expect(appSessionSource).toContain("resolveSessionConnectionTargetOrigin(sessionQuery.data?.connection)");
  });

  it("isolates queue and attached-task authority by runtime-mode context keys", () => {
    expect(taskQueueSource).toContain("const contextKey = `${session?.runtimeMode ?? \"online\"}");
    expect(taskQueueSource).toContain("[tasksListKey, contextKey]");
    expect(taskQueueSource).toContain("const workerSummary = taskQueue?.workerSummary ?? []");
    expect(activeTaskSource).toContain("[taskDetailKey(resolvedTaskId), contextKey]");
    expect(activeTaskSource).toContain("routeTaskStillVisible");
  });
});
