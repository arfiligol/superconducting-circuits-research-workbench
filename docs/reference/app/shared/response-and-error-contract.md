---
aliases:
  - Response and Error Contract
  - Common API Contract
  - 回應與錯誤契約
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: app backend surfaces 共用的 success envelope、error envelope、error code family 與 frontend display contract
version: v0.1.0
last_updated: 2026-03-14
updated_by: team
---

# Response & Error Contract

本頁定義 App backend surfaces 共用的回應 envelope 與 error code contract。frontend 應以本頁作為顯示與分流錯誤的共同基線。

!!! info "Shared backend contract"
    `Session & Workspace`、`Tasks & Execution`、`Circuit Definitions`、`Schemdraw Render`、`Analysis Results` 都應回到這份 shared envelope。

!!! warning "Frontend keys off codes, not messages"
    前端 UI 不應靠訊息文字比對來決定顯示行為。
    正式分流鍵是 `error.code`、`error.category` 與 `error.retryable`。

## Success Envelope

| Field | Required | Meaning |
|---|---|---|
| `ok` | required | success 時固定為 `true` |
| `data` | required | surface-specific payload |
| `meta` | optional | collection pagination、generated_at、request echo、context summary |

!!! example "Success envelope"
    ```json
    {
      "ok": true,
      "data": {
        "workspace": {
          "id": "ws_lab_a",
          "name": "Lab A"
        }
      },
      "meta": {
        "generated_at": "2026-03-14T10:00:00Z"
      }
    }
    ```

## Collection Meta Baseline

對 list / catalog / history / queue 類回應，`meta` 應優先採用 cursor-based collection meta。

| Field | Meaning |
|---|---|
| `generated_at` | response 產生時間 |
| `limit` | 本次回應的目標筆數 |
| `next_cursor` | 下一頁 cursor；若無更多資料可為 `null` |
| `prev_cursor` | 回看前一段資料的 cursor；若不支援或已在起點可為 `null` |
| `has_more` | 是否仍有更多資料 |
| `filter_echo` | backend 實際採用的 filter / scope / sort |

!!! tip "Cursor-based by default"
    App backend 的動態列表應優先採 cursor-based pagination，而不是 `page/page_size`。
    這特別適用於 queue、run history、audit logs，以及會持續變動的 catalog / browse surfaces。

## Error Envelope

| Field | Required | Meaning |
|---|---|---|
| `ok` | required | error 時固定為 `false` |
| `error.code` | required | 穩定 machine-readable error code |
| `error.category` | required | 共用高階分類 |
| `error.message` | required | user-safe message |
| `error.retryable` | required | 是否可安全重試 |
| `error.details` | optional | redaction-safe structured detail |
| `error.debug_ref` | optional | correlation id、task id 或 request id |

!!! example "Error envelope"
    ```json
    {
      "ok": false,
      "error": {
        "code": "dataset_not_visible_in_workspace",
        "category": "permission_denied",
        "message": "The selected dataset is not visible in the active workspace.",
        "retryable": false,
        "details": {
          "dataset_id": "ds_123",
          "workspace_id": "ws_lab_a"
        },
        "debug_ref": "req_7b4c4e"
      }
    }
    ```

## Common Error Categories

本頁沿用 [Code Quality / Error Handling](../../guardrails/code-quality/error-handling.md) 的高階分類。

| Category | Meaning |
|---|---|
| `auth_required` | 尚未登入或 session 不可用 |
| `permission_denied` | 已登入，但目前身份 / workspace 無權執行 |
| `validation_error` | request payload 或 surface-specific input 不合法 |
| `not_found` | 目標資源不存在或不可解析 |
| `conflict` | 版本衝突、狀態衝突、ownership 衝突 |
| `task_not_ready` | 結果或控制動作尚未準備好 |
| `task_execution_failed` | runtime / execution 本身失敗 |
| `persistence_error` | storage / persistence 寫入或讀取失敗 |
| `internal_error` | 未分類的服務端錯誤 |

## Shared Error Code Families

| Family | Representative codes |
|---|---|
| Session / Workspace | `workspace_membership_required`, `workspace_invite_expired`, `workspace_invite_revoked`, `workspace_invite_account_mismatch`, `active_workspace_required`, `dataset_not_visible_in_workspace`, `context_rebind_required` |
| Tasks | `task_not_found`, `task_not_visible`, `task_submit_denied`, `task_not_cancellable`, `task_not_terminable`, `task_already_terminal`, `task_retry_denied` |
| Definitions | `definition_not_found`, `definition_not_visible`, `definition_source_invalid`, `definition_conflict`, `definition_delete_blocked` |
| Schemdraw | `schemdraw_relation_invalid`, `schemdraw_linked_schema_not_visible`, `schemdraw_syntax_error`, `schemdraw_runtime_error` |
| Analysis Workbench | `analysis_not_available`, `trace_selection_invalid`, `artifact_not_found`, `tagging_conflict` |

## HTTP Status Mapping Baseline

| Situation | HTTP status |
|---|---|
| auth required | `401` |
| permission denied | `403` |
| validation error | `400` |
| not found | `404` |
| conflict | `409` |
| task not ready | `409` |
| persistence error | `503` or `500` |
| internal error | `500` |

## Frontend Display Rules

| Signal | Frontend expectation |
|---|---|
| `error.code` | 驅動 page-specific UI state 與 action disable / retry affordance |
| `error.retryable = true` | 可顯示 retry CTA 或 polling guidance |
| `error.debug_ref` | 不直接當 user message，但可供 support / audit / logs 關聯 |
| `error.details` | 只用於 safe structured rendering，不顯示 raw internals |

!!! tip "Surface-specific pages still define their own codes"
    這份文件只定 envelope 與共用 families。
    每一個 backend surface 仍需列出自己的 concrete error codes 與 example payload。

## Related

* [Authentication & Authorization](authentication-and-authorization.md)
* [Audit Logging](audit-logging.md)
* [Session & Workspace](../backend/session-workspace.md)
* [Tasks & Execution](../backend/tasks-execution.md)
* [Code Quality / Error Handling](../../guardrails/code-quality/error-handling.md)
