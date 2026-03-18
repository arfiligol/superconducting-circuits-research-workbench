---
aliases:
  - Backend Tasks Execution Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Backend task queue read model、control actions、worker summary、event history 與 result attachment surface
version: v0.11.0
last_updated: 2026-03-18
updated_by: codex
---

# Tasks & Execution

本頁定義 shared task management、simulation 與 characterization 依賴的 backend task surface。

!!! info "Surface Boundary"
    本頁負責 task submission、queue read model、task detail、control actions、event history、result attachment 與 worker summary pairing。
    analysis-specific artifact layout 不屬於本頁責任。

!!! warning "Queue Is A Backend-owned Read Model"
    Header `Tasks Queue` 不是 frontend 自行組裝的列表。
    queue rows、control-action availability、worker summary 與 persisted lifecycle 都必須由 backend authority 提供。

## Coverage

| Surface | Meaning |
|---|---|
| Task submission | 建立新 persisted task，回傳可 attach 的 `task_id` |
| Queue read model | 供 Header queue 直接消費的 summary rows |
| Task detail | 附加後可供 page body 重建 execution context |
| Control actions | `cancel`, `terminate`, `retry` 等 lifecycle mutations |
| Event history | append-only task events |
| Result attachment | 透過 `result_ref` 連到 persisted result surface |

## Submission Contract

task submit response 至少必須提供：

| Field | Meaning |
|---|---|
| `task_id` | persisted primary key |
| `task_kind` | simulation / characterization / processing 等 |
| `lane` | workflow lane |
| `status` | 初始 lifecycle status |
| `visibility_scope` | `local` / `workspace` / `private` |
| `owner_user_id` | task owner |
| `dataset_id` / `definition_id` / design context | 與 page context 相關的 binding |

## Submission Payload Families

=== "Simulation Submit"

    | Field | Meaning |
    |---|---|
    | `dataset_id` | active dataset |
    | `definition_id` | selected canonical definition |
    | `task_kind` | simulation lane task |
    | `setup` | frequency sweep、parameter sweeps、solver、sources 與 persisted `ptc` 設定 |
    | `post_processing_plan` | optional，若同時聲明後處理需求 |

### `simulation_setup.ptc` contract

| Field | Meaning |
|---|---|
| `enabled` | 此 simulation run 是否啟用 PTC |
| `mode` | stable、backend-recognized 的 PTC mode |
| `selected_ports[]` | schema-defined port selection；未選時預設為空 |
| `config` | solver-required PTC config payload |

!!! warning "PTC is task authority"
    `PTC` 不屬於長期 browser-local draft。
    一旦使用者以 `PTC` 參與 simulation stage，backend 必須把它持久化在 `setup.ptc`，並在 task detail / refresh recovery 中回傳同一份 canonical snapshot。

=== "Characterization Submit"

    | Field | Meaning |
    |---|---|
    | `dataset_id` | active dataset |
    | `design_id` | current design scope |
    | `analysis_id` | selected analysis kind |
    | `selected_trace_ids[]` | 明確輸入 trace selection |
    | `analysis_config` | optional analysis-specific config |

## Shared Task Lifecycle

!!! warning "Primary Recovery Key"
    `task_id` 是 attach、inspect、wait、refresh recovery 的 primary key。
    `dataset_id`、`definition_id`、design labels 只能當輔助索引。

```text
queued
-> dispatching
-> running
-> completed | failed

running
-> cancellation_requested
-> cancelling
-> cancelled

running | cancelling
-> termination_requested
-> terminated
```

## Queue Read Model

Header queue rows 至少必須能讀到：

| Field | Meaning |
|---|---|
| `task_id` | attach / inspect / recover key |
| `summary` | 人類可讀的 task label |
| `status` | queue row 狀態 |
| `lane` / `task_kind` | workflow lane summary |
| `owner_display_name` | 多使用者 queue 辨識；local mode 可固定為 `Local` 或等價 local operator label |
| `visibility_scope` | queue filter 與共享語意 |
| `updated_at` | 排序與最近活動 |
| `result_availability` | terminal 後是否有 persisted result |
| `allowed_actions` | 當前使用者可見的 row actions |

## Queue Query Contract

### Mode-specific queue semantics

| Mode | Required read model |
|---|---|
| `local` | queue rows 只來自 `Local Space`；不做 workspace role 過濾；`visibility_scope` 固定為 `local`；`owner_display_name` 可固定為 `Local` |
| `online` | queue rows 來自 active workspace；依 role / visibility / allowed actions materialize row actions |

| Input | Baseline |
|---|---|
| `scope_filter` | local mode 固定 `local`；online mode 為 `workspace`, `mine` |
| `status_filter` | `active`, `recent`, `all` |
| `lane_filter` | optional |
| `search_query` | optional，對 `summary`、owner display name、`task_id` 生效 |
| `limit` | optional，回應筆數上限 |
| `after` / `before` | optional，cursor-based 瀏覽位置 |
| `sort` | fixed baseline: active first, then `updated_at desc` |

| Output | Meaning |
|---|---|
| `rows[]` | 目前 filter 下的 queue rows |
| `worker_summary[]` | lane-scoped processor summary |
| `meta.generated_at` | queue read model 產生時間 |
| `meta.next_cursor` / `meta.prev_cursor` | cursor-based browse meta |
| `meta.filter_echo` | backend 實際採用的 filter / scope |

## Control Actions

| Action | Input | Immediate response rule | Terminal rule |
|---|---|---|---|
| `cancel` | `task_id` | 立即把 task 標成 `cancellation_requested` 或等價 control state | 最終由 runtime 決定 `cancelled` |
| `terminate` | `task_id` | 立即把 task 標成 `termination_requested` | 最終由 runtime 決定 `terminated` |
| `retry` | `task_id` | 建立新 task 並回傳新 `task_id`，保留 lineage | 舊 task 不被覆寫 |

## Action Permission Echo

| Field | Meaning |
|---|---|
| `allowed_actions.attach` | 是否允許 attach |
| `allowed_actions.cancel` | 是否允許 graceful cancel |
| `allowed_actions.terminate` | 是否允許 force terminate |
| `allowed_actions.retry` | 是否允許 retry |
| `rejection_reason` | action 被拒時的穩定 machine-readable reason |

!!! tip "Immediate Control Echo"
    使用者在 Header queue 點擊 `Cancel` 或 `Terminate` 後，backend 必須立即回寫 control-request state。
    UI 不應等待 worker 真正結束後才顯示該動作已被接受。

## Task Detail & Events

| Surface | Required meaning |
|---|---|
| task detail | 附加後重建 page body 所需的完整 persisted state；simulation task 必須能回傳完整 `setup` snapshot，包含 `setup.ptc` |
| task events | append-only lifecycle and execution events；可附帶 accepted `PTC` config、materialization milestones 等 stable execution metadata |
| execution metadata | worker / processor / result refs / runtime-safe metadata；simulation task 應能表達 downstream source availability，例如 `Raw` / `PTC` |
| result attachment | terminal task 如何連到 persisted result；simulation task 必須明確指出 downstream 是否有 `Raw`、`PTC`，或兩者皆有 |

## Downstream Source Availability

| Source | Rule |
|---|---|
| `Raw` | upstream simulation run 成功 materialize solver-native result 後可用 |
| `PTC` | 只有在 `setup.ptc.enabled = true`，且 completed simulation run 真正 persisted / materialized PTC-capable output 時才可用 |

!!! tip "Do not infer from UI state"
    downstream `PTC` source availability 不得只靠 frontend 當前 toggle 或 browser draft 推定。
    page / result surface 必須以 task detail、execution metadata 或 persisted result attachment 的 authority echo 為準。

## Worker Summary Pairing

!!! info "Header Worker Status"
    Header queue trigger 旁的 worker status，不應由本頁單獨硬編。
    但 backend task surface 必須能把 queue 與 [Task Runtime & Processors](../shared/task-runtime-and-processors.md) 的 processor summary 對齊。

| Concern | Rule |
|---|---|
| Queue consistency | active task status 與 worker summary 不得互相矛盾 |
| Lane visibility | queue 至少能辨識 task 所屬 lane |
| Control permissions | `allowed_actions` 必須依 [Authentication & Authorization](../shared/authentication-and-authorization.md) 計算 |
| Workspace boundary | online mode 的 queue query 不得跨出 active workspace，除非明確是 admin-scoped governance surface |
| Local boundary | local mode 的 queue query 只看 `Local Space`，不支援 `mine` / workspace membership 語意 |

## Delivery Rules

| Rule | Meaning |
|---|---|
| Persisted state wins | refresh / reconnect 後以 persisted task state 重建 |
| Queue is globally consumable | Header 在任何頁都能消費同一份 queue read model |
| Detail is attach-ready | simulation / characterization 必須能以 `task_id` 重新附加 |
| Result handoff is explicit | task terminal 後要能分辨 `result ready` 與 `no result` |
| `PTC` capability is persisted | simulation task 的 `PTC` config 與 downstream `PTC` availability 必須能由 persisted task / result authority 重建 |
| Control actions are auditable | `cancel` / `terminate` / `retry` 必須可進入 audit trail |

## Request / Response Examples

!!! example "Submit simulation task"
    Request:
    ```json
    {
      "dataset_id": "ds_xy_001",
      "definition_id": "def_lc_12",
      "task_kind": "simulation",
      "setup": {
        "frequency_sweep": {
          "start_ghz": 1.0,
          "stop_ghz": 8.0,
          "points": 401
        },
        "solver": {
          "nmod": 6,
          "npump": 3
        },
        "ptc": {
          "enabled": true,
          "mode": "backend_defined_mode",
          "selected_ports": ["port_ro"],
          "config": {}
        }
      }
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "task_id": "task_501",
        "task_kind": "simulation",
        "lane": "simulation",
        "status": "queued",
        "visibility_scope": "private",
        "owner_user_id": "user_12",
        "dataset_id": "ds_xy_001",
        "definition_id": "def_lc_12"
      }
    }
    ```

!!! example "Simulation task detail excerpt"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "task_id": "task_501",
        "task_kind": "simulation",
        "status": "completed",
        "setup": {
          "frequency_sweep": {
            "start_ghz": 1.0,
            "stop_ghz": 8.0,
            "points": 401
          },
          "solver": {
            "nmod": 6,
            "npump": 3
          },
          "ptc": {
            "enabled": true,
            "mode": "backend_defined_mode",
            "selected_ports": ["port_ro"],
            "config": {}
          }
        },
        "execution_metadata": {
          "downstream_sources": {
            "raw": true,
            "ptc": true
          }
        }
      }
    }
    ```

!!! example "Queue query"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "task_id": "task_501",
            "summary": "Simulation · LC Resonator",
            "status": "running",
            "lane": "simulation",
            "task_kind": "simulation",
            "owner_display_name": "Ari",
            "visibility_scope": "workspace",
            "updated_at": "2026-03-14T10:12:00Z",
            "result_availability": "pending",
            "allowed_actions": {
              "attach": true,
              "cancel": true,
              "terminate": false,
              "retry": false
            }
          }
        ],
        "worker_summary": [
          {
            "lane": "simulation",
            "healthy_processors": 1,
            "busy_processors": 1,
            "degraded_processors": 0,
            "draining_processors": 0,
            "offline_processors": 0
          }
        ]
      },
      "meta": {
        "generated_at": "2026-03-14T10:12:00Z",
        "next_cursor": "task_498",
        "prev_cursor": null,
        "has_more": true,
        "filter_echo": {
          "scope_filter": "workspace",
          "status_filter": "active"
        }
      }
    }
    ```

!!! example "Queue query in local mode"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "task_id": "task_local_021",
            "summary": "Characterization · Local Space",
            "status": "running",
            "lane": "characterization",
            "task_kind": "characterization",
            "owner_display_name": "Local",
            "visibility_scope": "local",
            "updated_at": "2026-03-16T09:20:00Z",
            "result_availability": "pending",
            "allowed_actions": {
              "attach": true,
              "cancel": true,
              "terminate": true,
              "retry": false
            }
          }
        ],
        "worker_summary": [
          {
            "lane": "characterization",
            "healthy_processors": 1,
            "busy_processors": 1,
            "degraded_processors": 0,
            "draining_processors": 0,
            "offline_processors": 0
          }
        ],
        "meta": {
          "generated_at": "2026-03-16T09:20:01Z",
          "filter_echo": {
            "scope_filter": "local",
            "status_filter": "active"
          }
        }
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
|---|---|---|
| `active_dataset_required` | `validation_error` | submit payload 缺 dataset context |
| `task_submit_denied` | `permission_denied` | session 無 submit 權限 |
| `task_not_found` | `not_found` | 指定 task 不存在 |
| `task_not_visible` | `permission_denied` | task 不在目前 active workspace visibility 內 |
| `task_not_cancellable` | `conflict` | task 狀態不允許 cancel |
| `task_not_terminable` | `conflict` | task 狀態不允許 terminate |
| `task_already_terminal` | `conflict` | retry / control 對 terminal task 不適用 |
| `task_retry_denied` | `permission_denied` | retry 不符合 ownership 或 capability 規則 |

## Related

* [Task Management](../frontend/shared-workflow/task-management.md)
* [Header](../frontend/shared-shell/header.md)
* [Shared / Authentication & Authorization](../shared/authentication-and-authorization.md)
* [Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md)
* [Shared / Audit Logging](../shared/audit-logging.md)
