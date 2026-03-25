---
aliases:
  - Backend Audit Logs
  - Audit Log Query Surface
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Backend audit log query、detail、export summary 與 governance read surface
version: v0.1.1
last_updated: 2026-03-25
updated_by: codex
---

# Audit Logs

本頁定義 app governance surfaces 依賴的 backend audit log read model。

!!! info "Surface Boundary"
    本頁只定義 audit log 的 query / detail / export summary read surface。
    audit write semantics、separate audit store 與 retention baseline 由 [Shared / Audit Logging](../shared/audit-logging.md) 定義。

!!! warning "Governance-only surface"
    audit log 不是 page analytics，也不是 task event history。
    consumer 必須具備 `can_view_audit_logs` 或等價治理權限。

## Coverage

| Surface | Meaning |
| --- | --- |
| Audit list query | workspace-aware cursor-based browse |
| Audit detail | 單筆 audit record detail |
| Export summary | audit export job or snapshot request summary |

## Audit List Query Contract

| Input | Meaning |
| --- | --- |
| `workspace_id` | optional；admin 可跨 workspace 查詢，其他角色只能查自身可見 workspace |
| `actor_user_id` | optional actor filter |
| `action_kind` | optional stable machine-readable action filter |
| `resource_kind` | optional resource family filter |
| `outcome` | optional `accepted`, `rejected`, `completed`, `failed` |
| `after` / `before` | cursor-based browse position |
| `limit` | maximum rows |

| Output row | Meaning |
| --- | --- |
| `audit_id` | audit identity |
| `occurred_at` | event timestamp |
| `workspace_id` | workspace boundary |
| `actor_summary` | actor id + display summary |
| `action_kind` | stable machine-readable action |
| `resource_kind` | resource family |
| `resource_id` | target resource identity |
| `outcome` | accepted / rejected / completed / failed |
| `correlation_id` | workflow-level link |

## Audit Detail Contract

| Field | Meaning |
| --- | --- |
| `audit_id` | audit identity |
| `occurred_at` | event timestamp |
| `actor_user_id` | actor identity |
| `session_id` | session linkage |
| `correlation_id` | workflow / request linkage |
| `workspace_id` | workspace boundary |
| `action_kind` | stable action code |
| `resource_kind` / `resource_id` | target resource |
| `outcome` | accepted / rejected / completed / failed |
| `payload` | redaction-safe structured payload |
| `debug_ref` | support-safe debug linkage |

## Export Summary Contract

| Field | Meaning |
| --- | --- |
| `export_id` | export request identity |
| `status` | `queued`, `running`, `completed`, `failed` |
| `workspace_id` | scoped workspace or `null` for admin global export |
| `filter_echo` | applied export filters |
| `artifact_ref` | completed export artifact handle |

!!! tip "Cursor-based by default"
    audit list query 必須沿用 shared [Response & Error Contract](../shared/response-and-error-contract.md) 的 cursor-based collection meta。

## Request / Response Examples

!!! example "Audit list query"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "audit_id": "audit_9001",
            "occurred_at": "2026-03-14T11:10:00Z",
            "workspace_id": "ws_lab_a",
            "actor_summary": {
              "user_id": "user_12",
              "display_name": "Ari"
            },
            "action_kind": "workspace_invite_created",
            "resource_kind": "workspace_invitation",
            "resource_id": "inv_4d7c8f",
            "outcome": "accepted",
            "correlation_id": "corr_1001"
          }
        ]
      },
      "meta": {
        "limit": 50,
        "next_cursor": null,
        "prev_cursor": null,
        "has_more": false
      }
    }
    ```

!!! example "Audit detail"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "audit_id": "audit_9001",
        "occurred_at": "2026-03-14T11:10:00Z",
        "actor_user_id": "user_12",
        "session_id": "sess_44",
        "correlation_id": "corr_1001",
        "workspace_id": "ws_lab_a",
        "action_kind": "workspace_invite_created",
        "resource_kind": "workspace_invitation",
        "resource_id": "inv_4d7c8f",
        "outcome": "accepted",
        "payload": {
          "invitee_email": "researcher@example.com",
          "role": "member"
        },
        "debug_ref": "req_7b4c4e"
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
| --- | --- | --- |
| `audit_access_denied` | `permission_denied` | session 無 audit query 權限 |
| `audit_record_not_found` | `not_found` | 指定 audit record 不存在 |
| `audit_query_invalid` | `validation_error` | filter 組合不合法 |
| `audit_export_denied` | `permission_denied` | session 無 export 權限 |

## Related

- [Shared / Observability Model](../shared/observability-model.md)
- [Shared / Audit Logging](../shared/audit-logging.md)
- [Shared / Response & Error Contract](../shared/response-and-error-contract.md)
- [Session & Workspace](session-workspace.md)
- [Tasks & Execution](tasks-execution.md)
