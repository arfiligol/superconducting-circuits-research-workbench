---
aliases:
  - Audit Logging
  - Audit Trail
  - 稽核日誌
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: persisted audit trail、separate audit store、query/redaction/retention contract
version: v0.5.1
last_updated: 2026-05-28
updated_by: codex
---

# Audit Logging

本頁定義 multi-user app 的 persisted audit logging 契約。

!!! info "App governance surface"
    audit logging 是 App collaboration / governance 的一部分，不是一般 runtime logging 的替代品。

!!! warning "Separate Audit Store"
    audit logs 不得與 app operational database 共用同一個資料庫。

## Boundary With Other Observability Layers

| Layer | What it answers | What it must not replace |
|---|---|---|
| Audit logging | 誰對哪種資源做了什麼治理意義的動作 | workflow task timeline、product telemetry |
| Workflow observability | request / task / execution runtime / result 經過哪些 runtime stage | actor-centric governance trail |
| Product telemetry | 哪種 flow 常用、哪裡慢、哪裡值得優化 | audit trail、single-task debug record |

!!! info "Shared identifiers are allowed"
    `correlation_id` 可以同時出現在 audit row 與 workflow timeline。
    這不表示 audit logging 可以取代 workflow observability。

## Required Record Fields

| Field | Meaning |
|---|---|
| `audit_id` | audit row 的唯一識別 |
| `occurred_at` | 事件時間 |
| `actor_user_id` | 執行動作者 |
| `session_id` | 對應 session |
| `correlation_id` | 將同一串 workflow / request 關聯起來 |
| `workspace_id` | 對應 workspace |
| `action_kind` | 穩定 machine-readable action |
| `resource_kind` | `task`, `dataset`, `definition`, `user`, `workspace` 等 |
| `resource_id` | 被操作資源識別 |
| `outcome` | `accepted`, `rejected`, `completed`, `failed` |
| `payload` | redaction-safe structured payload |

## Minimum Audited Actions

| Action family | Required examples |
|---|---|
| Authentication | login success, login failure, logout |
| Workspace membership | invite created, invite sent, invite delivery failed, invite accepted, invite revoked, member removed, owner transferred |
| Session context | active workspace switched, active workspace switch rejected, active dataset switched, active dataset switch rejected |
| Resource lifecycle | imported, published, archived, restored, deleted, exported |
| Task governance | submitted, cancelled, terminated, retried |
| Admin bootstrap | bootstrap attempted, bootstrap succeeded, bootstrap rejected |

## Query And Retention Rules

| Rule | Meaning |
|---|---|
| Separate store | audit store 與 app operational DB 分離 |
| Append-only | 一般 workflow 不可更新既有 audit row |
| Workspace-aware query | query 至少支援依 `workspace_id`、`actor_user_id`、`action_kind` 過濾 |
| Retention baseline | 預設保留至少 365 days |
| Redaction-safe payload | 不保存 secret-bearing raw payload |

## Storage Baseline

| Rule | Meaning |
|---|---|
| Separate physical store | audit store 與 app operational DB 必須分開部署 |
| SQL-first baseline | 第一版採 append-only SQL audit store；NoSQL 可之後再擴充 |
| Write path isolation | app workflow 寫 audit 時，不得要求 page consumer 直接碰 audit DB |
| Governance-oriented query | audit query API 與 app operational query 分開考慮，不混用一般 page list endpoint |

!!! warning "Audit logging is not UI event history"
    audit log 不是 task events 的別名，也不是 page analytics。
    它回答的是誰在什麼 workspace 對哪種資源做了什麼具治理意義的動作。

## Related

* [Observability Model](observability-model.md)
* [Authentication & Authorization](authentication-and-authorization.md)
* [Task Runtime & Processors](task-runtime-and-processors.md)
* [Backend / Tasks & Execution](../backend/tasks-execution.md)
* [Backend / Audit Logs](../backend/audit-logs.md)
