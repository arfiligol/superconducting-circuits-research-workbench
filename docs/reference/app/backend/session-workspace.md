---
aliases:
  - Backend Session Workspace Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Backend runtime mode、session、workspace membership、active workspace、active dataset、collaboration mutations 與 capability exposure surface
version: v0.12.0
last_updated: 2026-03-17
updated_by: codex
---

# Session & Workspace

本頁定義 frontend shell、workspace pages 與 shared app model 共用的 runtime-mode-aware session / workspace authority surface。

!!! info "Surface Boundary"
    本頁負責 runtime mode、session、workspace membership、active workspace、active dataset、workspace invitation / membership management、user summary、workspace role 與 capability exposure。
    task lifecycle、definition preview、result artifact 與 audit query 不屬於本頁責任。

!!! warning "Single Context Authority"
    app shell 顯示的 `Active Workspace`、`Active Dataset`、`Workspace Role`、`User Menu Summary`
    與 collaboration controls 必須來自同一份 backend session authority。

!!! warning "Local And Online Must Not Share One Session Cache"
    local mode 與 online mode 都走同一套 session surface，但不得共用同一份 active context。
    mode switch 必須重新建立 session envelope，而不是沿用舊 mode 的 workspace / dataset / user state。

!!! info "Authorization baseline"
    本頁所有 capability flags、membership mutation permission 與 collaboration control 都以 backend authorization engine 為準。
    正式 baseline 採 `Casbin`，由 backend service 先整理 resource envelope，再回傳 materialized `capabilities` 與 `allowed_actions`。

## Coverage

| Surface | Meaning |
| --- | --- |
| Runtime mode | app 目前以 `local` 或 `online` 運行 |
| Auth state | 使用者目前是 `local_bypass`、`authenticated`、`anonymous` 還是 `degraded` session |
| Connection target | 目前 active online target 的摘要，或 `null` |
| User summary | Header user icon / menu 所需 display data |
| Workspace identity | active workspace、membership role、default queue scope |
| Workspace membership list | user 可切換的 workspaces 與 roles |
| Active dataset | shell-level global dataset context |
| Capability flags | frontend 與 shared task-management 可直接使用的 permission summary |
| Collaboration mutations | invite、revoke、leave、remove member、transfer owner |

## Session Envelope

backend session surface 至少必須提供：

| Field | Meaning |
| --- | --- |
| `auth.state` | `local_bypass`, `authenticated`, `anonymous`, `degraded` 等 session state |
| `runtime_mode` | `local` 或 `online` |
| `auth.mode` | auth transport or mode summary |
| `session_id` | 目前 session identity；public online session 可為 `null` |
| `connection.target` | nested target summary object，含 `origin`、`label`、`is_active`、`validation_status`、`last_checked_at`；local mode 為 `null` |
| `user.id` | 目前使用者 identity |
| `user.display_name` | Header user icon / menu 顯示名稱 |
| `user.platform_role` | `admin` / `user` |
| `workspace.memberships[]` | 使用者可進入的 workspace 列表與 role 摘要；local mode 可退化成單一 `Local Space` membership |
| `workspace.id` | active workspace identity |
| `workspace.slug` | workspace route / slug summary |
| `workspace.name` | workspace display name |
| `workspace.role` | `owner` / `member` / `viewer` |
| `workspace.default_task_scope` | queue default visibility scope |
| `workspace.allowed_actions` | workspace-scoped mutation availability summary |
| `active_dataset.id` / `name` | global dataset context |
| `active_dataset.visibility_scope` | `local`, `private`, `workspace` 之一 |
| `capabilities` | capability flags summary |

## Runtime Mode Rules

| Rule | Meaning |
| --- | --- |
| Same envelope family | local 與 online 應回傳相容的 session envelope shape |
| Local mode returns implicit session | backend 直接提供 local user / `Local Space` / capability summary |
| Online mode may require auth | 若尚未登入，session surface 回 `auth_required` 或 anonymous/degraded state |
| Mode switch is session mutation | 不是單純 frontend config toggle |
| Mode switch clears stale shell context | 舊 mode 的 dataset、queue、attached task refs 不得殘留 |
| Mode switch drops remote auth continuity | 從 online 切到 local 再切回 online，不保留舊的 remote authenticated session |

## Authorization Resolution Rules

| Rule | Meaning |
| --- | --- |
| Session never trusts JWT claims for permissions | JWT 只提供 authentication continuity |
| Workspace role is backend-resolved | active workspace role 由 membership lookup + authorization engine 決定 |
| Capability flags are materialized decisions | frontend 不需自行重建 role matrix |
| Mutation availability is echoed | invite / revoke / leave / remove / transfer 等 controls 必須回傳 `allowed_actions` 或等價 flags |
| Casbin policy is implementation baseline | policy engine 可替換，但對 frontend 暴露的 contract 不變 |

## Active Workspace Switching

| Rule | Meaning |
| --- | --- |
| Session exposes memberships | Header 要能列出使用者可切換的 workspaces |
| Switch mutates session | active workspace switch 是 session mutation，不是純 frontend state |
| Dataset rebinding is required | workspace 切換後，active dataset 必須重新驗證或重選 |
| Queue rebinding is required | workspace 切換後，queue visibility 與 allowed actions 必須同步更新 |

## Mutation Surfaces

| Mutation | Responsibility |
| --- | --- |
| `switch_runtime_mode(runtime_mode, server_origin | null, label | null)` | 切換 `local` / `online`，建立對應 session envelope 或 auth-required outcome |
| `list_server_targets()` | 列出 active target 與 remembered recent online targets |
| `validate_server_target(server_origin)` | 驗證 target reachability / health / version compatibility |
| `remember_server_target(server_origin, label | null)` | 儲存或更新 app-level online target config |
| `switch_active_workspace(workspace_id)` | 變更 active workspace，回傳新 session envelope 與 rebind outcome |
| `activate_dataset(dataset_id | null)` | 設定 active dataset，並驗證該 dataset 對目前 active workspace 可見 |
| `create_workspace_invitation(workspace_id, email, role)` | 建立 pending invite 並觸發 outbound delivery |
| `revoke_workspace_invitation(invite_id)` | 在 accept 前撤銷 pending / delivered invite |
| `accept_workspace_invitation(invite_token)` | 驗證 invite、建立 membership，並回傳 post-accept suggestion |
| `leave_workspace(workspace_id)` | 使用者主動退出 membership，並重新繫結 session context |
| `remove_workspace_member(workspace_id, member_user_id)` | 移除其他 membership |
| `transfer_workspace_owner(workspace_id, new_owner_user_id)` | 轉移 owner 權限並回傳更新後 membership summary |

## Live HTTP Routes

| Route | Status | Responsibility |
| --- | --- | --- |
| `GET /session` | live | 回傳 runtime-mode-aware session envelope |
| `PATCH /session/runtime-mode` | live | 切換 `local` / `online`，並回傳新 session envelope + switch result fields |
| `GET /session/server-targets` | live | 列出 remembered online targets 與 active target origin |
| `POST /session/server-targets` | live | 新增或更新 app-level online target config |
| `POST /session/server-targets/validate` | live | 驗證 target reachability / health / compatibility |
| `PATCH /session/active-workspace` | live | 切換 active workspace |
| `PATCH /session/active-dataset` | live | 切換 active dataset |
| `POST /session/login` | live | 建立 online authenticated session |
| `POST /session/logout` | live | 清除 online authenticated session |
| `POST /session/refresh` | live | 透過 refresh transport 重建 online authenticated session |

## Workspace Switch Response

| Field | Meaning |
| --- | --- |
| `workspace.id` / `name` / `role` | 新的 active workspace |
| `active_dataset_resolution` | `preserved`, `rebound`, `cleared` |
| `active_dataset` | 重新繫結後的 dataset summary，或 `null` |
| `detached_task_ids[]` | 因 visibility 失效而解除附著的 task ids |
| `capabilities` | 新 workspace 下的 capability summary |
| `memberships[]` | 供 Header 重新渲染 switcher |

## Runtime Mode Switch Response

!!! info "Extends the session envelope"
    `PATCH /session/runtime-mode` 的成功回應不是一個獨立小 payload。
    它會回傳完整 session envelope，再額外附加 runtime-mode switch result fields。

| Field | Meaning |
| --- | --- |
| `runtime_mode` | 新的 active mode |
| `connection.target` | nested target summary object 或 `null`；不再使用 plain string target |
| `outcome` | backend switch outcome：目前 live values 為 `entered_local`、`entered_online_auth_required` |
| `auth_transition` | auth continuity outcome：目前 live values 為 `entered_local_bypass`、`online_auth_required`、`online_session_dropped` |
| `session_reset` | 是否已清除舊 mode shell context |
| `workspace` | 使用標準 session workspace object；online public session 也保留 object shape，但 identity fields 為 `null` |
| `active_dataset` | 使用標準 session active-dataset object，若尚未解析 dataset 則為 `null` |
| `capabilities` | 由新 mode materialize 的 capability summary |
| `detached_task_ids[]` | mode switch 時被解除附著的 task ids |

## Server Target Summary Shape

| Field | Meaning |
| --- | --- |
| `origin` | canonical remote origin，例如 `https://lab.example.com` |
| `label` | target display label |
| `is_active` | 是否為目前 active online target |
| `validation_status` | `validated`、`target_validation_failed`、`target_unreachable`、`target_incompatible`、`online_target_rejected` |
| `last_checked_at` | 最近一次 validation timestamp；若尚未驗證可為 `null` |

## Online Server Target Rules

| Rule | Meaning |
| --- | --- |
| App-level owner | server target config 不屬於 workspace、dataset 或 account preference |
| One active target | 同一時間只有一個 active online target |
| Recent history allowed | 可保留 remembered recent targets，供 mode switcher 重用 |
| Validation before switch | 切到 online mode 前，必須先完成 target validation |
| Failure keeps current mode | 若 target 驗證失敗，保持原 active mode，不建立半完成 session |
| Connection shape | session / runtime-mode response 中的 `connection.target` 一律使用 nested summary object 或 `null` |

## Active Dataset Activation Rules

| Rule | Meaning |
| --- | --- |
| Must belong to active workspace | dataset 若不屬於或不可見於 active workspace，mutation 必須被拒絕 |
| Explicit clear allowed | 允許把 active dataset 設為 `null` |
| Session-wide propagation | mutation 成功後，所有 page consumers 看到同一 active dataset |
| Rejection must explain why | 至少區分 `not_found`、`not_visible_in_workspace`、`archived` 等原因 |

## Local Session Baseline

| Field | Required behavior |
| --- | --- |
| `runtime_mode` | 必須是 `local` |
| `auth.state` | 使用 `local_bypass` 或等價 local state |
| `user` | 回傳 implicit local operator summary |
| `workspace` | 回傳 `Local Space` |
| `memberships[]` | 可省略，或回傳單一 `Local Space` membership |
| `connection.target` | 回傳 `null`，而不是 `"local"` string |
| `active_dataset.visibility_scope` | 若 local dataset 已綁定，必須是 `local` |
| `capabilities` | 回傳 local mode capability summary，不由 frontend 猜測 |

!!! info "Local mode still uses the same backend surface"
    local mode 不代表跳過 backend session surface。
    frontend 仍應透過同一份 authority 取得 user summary、workspace、dataset 與 capability flags。

## Invitation Surfaces

| Field | Meaning |
| --- | --- |
| `invite_id` | invite identity |
| `workspace_id` | target workspace |
| `email` | invited email |
| `role` | proposed workspace role |
| `status` | `pending`, `delivered`, `accepted`, `revoked`, `expired`, `delivery_failed` |
| `expires_at` | invite expiry |
| `delivery.channel` | `smtp` or `manual_link` |

### Invitation acceptance response

| Field | Meaning |
| --- | --- |
| `invite.status` | `accepted`, `revoked`, `expired`, `rejected_account_mismatch` |
| `workspace` | 受邀 workspace summary |
| `membership.role` | 新 membership role |
| `switch_available` | 若目前已有其他 active workspace，提示 frontend 顯示切換 CTA |
| `recommended_next_action` | `switch_workspace`, `stay_current`, `reopen_invite` 等 |

## Membership Management Rules

| Rule | Meaning |
| --- | --- |
| Invite creation is explicit | 不存在靜默 auto-join |
| Owner leave requires another owner | 否則必須先 transfer ownership |
| Removing active member rebinds session | 若目標 user 正在使用此 workspace，session 必須清除 active workspace / dataset |
| Transfer owner updates capabilities immediately | owner transfer 成功後，雙方 capability summary 都必須立即改變 |

## Request / Response Examples

!!! example "Switch active workspace"
    Request:
    ```json
    {
      "workspace_id": "ws_lab_a"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "workspace": {
          "id": "ws_lab_a",
          "name": "Lab A",
          "role": "member"
        },
        "active_dataset_resolution": "rebound",
        "active_dataset": {
          "id": "ds_xy_001",
          "name": "FloatingQubitWithXYLine Post 0308_1819"
        },
        "detached_task_ids": ["task_402"],
        "capabilities": {
          "can_switch_workspace": true,
          "can_switch_dataset": true,
          "can_submit_tasks": true
        }
      },
      "meta": {
        "memberships_count": 3
      }
    }
    ```

!!! example "Switch runtime mode to local"
    Request:
    ```json
    {
      "runtime_mode": "local",
      "server_origin": null
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "session_id": "local-session",
        "runtime_mode": "local",
        "outcome": "entered_local",
        "connection": {
          "target": null
        },
        "auth": {
          "state": "local_bypass",
          "mode": "local_bypass",
          "reason": null
        },
        "auth_transition": "entered_local_bypass",
        "session_reset": true,
        "workspace": {
          "id": "local-space",
          "slug": "local-space",
          "name": "Local Space",
          "role": "owner"
        },
        "active_dataset": {
          "id": "local-dataset-001",
          "name": "Local Dataset 001",
          "visibility_scope": "local"
        },
        "capabilities": {
          "can_switch_runtime_mode": true,
          "can_switch_workspace": false,
          "can_switch_dataset": true,
          "can_submit_tasks": true
        },
        "detached_task_ids": [44]
      }
    }
    ```

!!! example "Switch runtime mode to online, auth required"
    Request:
    ```json
    {
      "runtime_mode": "online",
      "server_origin": "https://lab.example.com",
      "label": "Lab Server"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "session_id": null,
        "runtime_mode": "online",
        "outcome": "entered_online_auth_required",
        "connection": {
          "target": {
            "origin": "https://lab.example.com",
            "label": "Lab Server",
            "is_active": true,
            "validation_status": "validated",
            "last_checked_at": "2026-03-17T09:10:00Z"
          }
        },
        "auth": {
          "state": "anonymous",
          "mode": "jwt_refresh_cookie",
          "reason": null
        },
        "auth_transition": "online_auth_required",
        "session_reset": true,
        "workspace": {
          "id": null,
          "slug": null,
          "name": null,
          "role": null
        },
        "active_dataset": null,
        "capabilities": {},
        "detached_task_ids": [12]
      }
    }
    ```

!!! example "Create workspace invitation"
    Request:
    ```json
    {
      "workspace_id": "ws_lab_a",
      "email": "researcher@example.com",
      "role": "member"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "invite_id": "inv_4d7c8f",
        "workspace_id": "ws_lab_a",
        "email": "researcher@example.com",
        "role": "member",
        "status": "delivered",
        "expires_at": "2026-03-21T10:30:00Z",
        "delivery": {
          "channel": "smtp"
        }
      }
    }
    ```

!!! example "Accept workspace invitation"
    Request:
    ```json
    {
      "invite_token": "inv_4d7c8f"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "invite": {
          "status": "accepted"
        },
        "workspace": {
          "id": "ws_lab_b",
          "name": "Lab B"
        },
        "membership": {
          "role": "viewer"
        },
        "switch_available": true,
        "recommended_next_action": "switch_workspace"
      }
    }
    ```

!!! example "Transfer workspace owner"
    Request:
    ```json
    {
      "workspace_id": "ws_lab_a",
      "new_owner_user_id": "user_44"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "workspace": {
          "id": "ws_lab_a",
          "name": "Lab A"
        },
        "previous_owner_user_id": "user_12",
        "new_owner_user_id": "user_44",
        "memberships_updated": true
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
| --- | --- | --- |
| `auth_required` | `auth_required` | session 無效或未登入 |
| `request_validation_failed` | `validation_error` | `runtime_mode`、`server_origin`、`label` 等 request payload 不合法 |
| `target_validation_failed` | `conflict` | target 回應存在 validation failure，無法進入 online mode |
| `target_unreachable` | `conflict` | online server target 無法連線 |
| `target_incompatible` | `conflict` | target reachability 正常，但版本或 contract 不相容 |
| `online_target_rejected` | `conflict` | target validation 被拒絕或無法歸類到更細的 failure code |
| `auth_session_expired` | `auth_required` | 先前 online authenticated session 已失效，需重新登入 |
| `workspace_membership_required` | `permission_denied` | 目標 workspace 不屬於目前 memberships |
| `dataset_not_visible_in_workspace` | `permission_denied` | activate dataset 指向不可見 dataset |
| `dataset_archived` | `conflict` | active dataset 已 archive |
| `workspace_invite_expired` | `conflict` | invite token 已過期 |
| `workspace_invite_revoked` | `conflict` | invite 已撤銷 |
| `workspace_invite_account_mismatch` | `permission_denied` | invite email 與目前帳號不符 |
| `workspace_invite_create_denied` | `permission_denied` | session 無 invite 權限 |
| `workspace_invite_not_found` | `not_found` | invite identity 不存在 |
| `workspace_member_remove_denied` | `permission_denied` | session 無移除 member 權限 |
| `workspace_owner_transfer_denied` | `permission_denied` | session 無 transfer owner 權限 |
| `workspace_owner_transfer_invalid` | `validation_error` | 目標 user 不符合 owner transfer 條件 |
| `context_rebind_required` | `conflict` | session 切換後需重新選 dataset / task |

## Capability Flags

| Capability | Why frontend needs it |
| --- | --- |
| `can_switch_workspace` | 顯示 workspace switcher |
| `can_switch_runtime_mode` | 顯示 local / online mode switcher |
| `can_switch_dataset` | 顯示 active dataset switcher |
| `can_import_datasets` | 顯示 import / upload entry |
| `can_export_datasets` | 顯示 export / download entry |
| `can_invite_members` | 顯示 invite entry point |
| `can_remove_members` | 顯示 member removal action |
| `can_transfer_workspace_owner` | 顯示 owner transfer action |
| `can_submit_tasks` | 決定 Simulation / Characterization 是否可送出 task |
| `can_cancel_local_tasks` / `can_terminate_local_tasks` / `can_retry_local_tasks` | local mode queue row actions |
| `can_manage_workspace_tasks` | 決定 Header queue 是否顯示 `Cancel` / `Terminate` / `Retry` |
| `can_manage_definitions` | 決定 `Schemas` / `Schema Editor` 是否可建立、儲存、刪除 |
| `can_publish_definitions` | 決定 online publish controls 是否可顯示 |
| `can_manage_datasets` | 決定 `Dashboard` metadata editing 是否可寫入 |
| `can_view_audit_logs` | 決定 governance surfaces 是否可顯示 audit entry points |

## Delivery Rules

| Rule | Meaning |
| --- | --- |
| Dataset switch is global | active dataset 一旦切換，所有 page consumers 應看到同一版本 |
| Mode switch is stronger than workspace switch | 切 mode 之後，workspace / dataset / queue / user summary 都必須以新 mode 重建 |
| Role is workspace-scoped | shell 與 pages 看到的 action availability 必須依 workspace role 決定 |
| Capability beats guessing | frontend page 不得自己推斷是否可 submit / manage / delete |
| Session survives refresh | refresh 後必須能重建 user summary、workspace role 與 active dataset |

## Pairing

| Consumer | Why it depends on this surface |
| --- | --- |
| [Header](../frontend/shared-shell/header.md) | 顯示 active workspace、active dataset 與 user menu |
| [Sidebar](../frontend/shared-shell/sidebar.md) | 需要知道 shell-level context propagation |
| [Dashboard](../frontend/workspace/dashboard.md) | dataset metadata editing 依賴 capability flags |
| [Task Management](../frontend/shared-workflow/task-management.md) | queue visibility 與 row actions 依賴 workspace role / capability |

## Related

- [Shared / Runtime Modes](../shared/runtime-modes.md)
- [Shared / Identity & Workspace Model](../shared/identity-workspace-model.md)
- [Shared / Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md)
- [Shared / Authentication & Authorization](../shared/authentication-and-authorization.md)
- [Shared / Outbound Email Delivery](../shared/outbound-email-delivery.md)
- [Header](../frontend/shared-shell/header.md)
- [Tasks & Execution](tasks-execution.md)
