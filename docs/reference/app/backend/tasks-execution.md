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
version: v0.14.0
last_updated: 2026-03-21
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

!!! important "Single Authority Per Question"
    - Task execution status authority = `task detail.status`
    - Result readiness authority = `result_handoff.availability`
    - Queue is discovery, not page authority

!!! important "Local Submit Path Must Be Queue-backed"
    active local runtime path =
    - `uv run sc-app`
    - `uv run sc-worker-simulation`
    - `uv run sc-worker-characterization`

    local submit contract =
    - app process 建立 persisted task
    - app process enqueue 到 lane queue
    - heavy solver work 由 lane worker 執行

    app process 不得把 heavy solver work 當成 canonical in-process background thread job 直接執行。

## Coverage

| Surface | Meaning |
|---|---|
| Task submission | 建立新 persisted task，回傳可 attach 的 `task_id` |
| Queue read model | 供 Header queue 直接消費的 summary rows |
| Task detail | 附加後可供 page body 重建 execution context |
| Control actions | `cancel`, `terminate`, `retry` 等 lifecycle mutations |
| Event history | append-only task events |
| Result attachment | 透過 `result_ref` 連到 persisted result surface |

## Local Runtime Topology Contract

| Concern | Contract |
|---|---|
| App process | `uv run sc-app`；負責 submit、queue read model、task detail、result handoff surface |
| Simulation lane worker | `uv run sc-worker-simulation`；消費 `simulation` + `post_processing` |
| Characterization lane worker | `uv run sc-worker-characterization`；消費 `characterization` |
| Queue backend | `RQ` + Redis via `SC_RQ_REDIS_URL` / `SC_REDIS_URL` |
| Queue names | `SC_SIMULATION_QUEUE_NAME`、`SC_CHARACTERIZATION_QUEUE_NAME` |

!!! warning "Not allowed as canonical backend runtime"
    - app submit path 不得直接用 in-process `Thread(...)` 執行 solver work 取代 enqueue
    - app process 不得成為 local heavy execution host
    - in-process execution wiring 若暫時存在，只能被標記為 fallback / test-only，不得被文件當成 accepted architecture

## Task Authority Matrix

| Question | Authority surface | Authority field | Allowed derived read models | Must not become authority |
|---|---|---|---|---|
| 這筆 task 現在正在什麼 execution state？ | task detail | `task detail.status` | queue row `status`、badge、latest-run summary | queue row `status`、page-local lifecycle badge |
| 這筆 task 現在可不可以切到 result surface？ | task detail | `result_handoff.availability` | queue row `result_availability`、terminal/result-ready chip | `task.status == completed`、`result_ref` 存在與否的自行推論 |
| 使用者現在能在全域看到哪些 task？ | queue read model | `rows[]` + filter meta | Header badge、recent queue digest、quick list | workflow page 的 attached-task truth |
| attached page 應該重建哪一筆 task？ | task detail | `task_id` | compact attached-task summary | queue ordering、latest row heuristics |
| row-level quick actions 現在可不可點？ | queue read model | row `allowed_actions` | Header row buttons | page attached-state controls |
| attached task detail controls 現在可不可點？ | task detail | detail `allowed_actions` | standalone detail panel buttons | queue row echo、frontend 猜測 |

## Task Runtime Vocabulary

| Field | Means |
|---|---|
| `lane` | worker lane identity；只回答這筆 task 會由哪條 worker lane 處理 |
| `task_kind` | task execution kind / workflow semantics；回答 `simulation`、`post_processing`、`characterization` 等執行語意 |
| page stage / page step | workflow page 的 UI stage semantics；不得借用 `lane` 表達 |

## State Precedence

| Conflicting signals | Winner | Required behavior |
|---|---|---|
| queue row `status` vs task detail `status` | task detail `status` | page attach、page gating、recovery 全部以 detail 為準；queue 只做 discovery refresh |
| `task detail.status == completed` vs `result_handoff.availability != ready` | `result_handoff.availability` | 頁面停在 terminal/no-result 或 handoff-pending，不得直接切到 result surface |
| queue row `result_availability` vs task detail `result_handoff.availability` | task detail `result_handoff.availability` | queue row 只能當 discovery echo；page result readiness 必須以 detail 為準 |
| page-local derived summary vs latest persisted detail | latest persisted detail | frontend 可顯示 derived summary，但不得覆蓋 authority field |
| stale cached detail vs refetched detail for same `task_id` | refetched detail | reconnect / refresh 後以最新 persisted snapshot 重建 |

## Submission Contract

task submit response 至少必須提供：

| Field | Meaning |
|---|---|
| `task_id` | persisted primary key |
| `task_kind` | simulation / characterization / processing 等 |
| `lane` | worker lane identity；`post_processing` task 仍必須回 `simulation` |
| `status` | 初始 lifecycle status |
| `visibility_scope` | `local` / `workspace` / `private` |
| `owner_user_id` | task owner |
| `dataset_id` / `definition_id` / design context | 與 page context 相關的 binding |

### Local Submit Delivery Rules

| Rule | Meaning |
|---|---|
| Persist before enqueue | 先建立 persisted task，再 enqueue 到對應 lane queue |
| App returns attach-ready detail | submit response 不等待 solver 完成，只回 attach / recovery 所需 identity |
| Lane selection is deterministic | `simulation` + `post_processing` 一律進 simulation lane；`characterization` 一律進 characterization lane |
| App is not executor | local submit path 不把 solver 直接跑在 app process 內 |

## Queue Dispatch Contract

| Rule | Meaning |
|---|---|
| `task_id` is the only app/public primary key | frontend、pages、queue、refresh recovery、result handoff 一律以 `task_id` 辨識 task |
| runtime queue identifiers are metadata only | RQ `job_id`、dispatch token、queue-native handle 若存在，只能放在 runtime metadata；不得取代 `task_id` |
| dispatch metadata is persisted | enqueue / claim / start / finish / requeue 的最小 metadata 必須能在 persisted task detail 中重建 |
| enqueue outcome is explicit | persisted task 寫成功但 enqueue 失敗時，不可讓 app / worker / queue row 各自猜測 |
| worker retry does not create new public identity | 同一筆 task 的 requeue / redispatch 只能增加 dispatch attempt metadata；只有使用者明確 `retry` 才建立新 `task_id` |

### Persisted Dispatch Metadata

task detail 的 `dispatch` 至少必須能表達：

| Field | Meaning |
|---|---|
| `dispatch.status` | dispatch lifecycle summary，例如 `accepted`、`running`、`completed`、`failed` |
| `dispatch.queue_name` | 最後一次 dispatch 對應的 queue name |
| `dispatch.accepted_at` | task 被 app/local runtime 接受的時間 |
| `dispatch.enqueued_at` | 最後一次 enqueue 成功時間；若尚未成功可為 `null` |
| `dispatch.runtime_job_id` | queue/runtime metadata only；不得作為 public identity |
| `dispatch.dispatch_attempt_count` | enqueue 或 requeue 的累積嘗試次數 |
| `dispatch.last_dispatch_outcome` | 穩定 dispatch outcome，例如 `enqueue_succeeded`、`enqueue_failed`、`claimed`、`requeued` |
| `dispatch.last_dispatch_error_code` | 最近一次 dispatch 失敗時的穩定 error code |
| `dispatch.last_updated_at` | dispatch metadata 最近更新時間 |

### Submit Outcome Boundary

| Situation | Required backend response |
|---|---|
| persisted task + enqueue 都成功 | submit `ok = true`；回傳 attach-ready task identity 與 dispatch metadata |
| persisted task 成功，但 enqueue 失敗 | submit `ok = false`，error code 應落在 queue/runtime failure family；同時仍需回傳 persisted `task_id` 與最小 dispatch metadata，讓 UI 可以 recovery / inspect |
| persisted task 尚未寫入就失敗 | submit 直接失敗；不得產生可 attach 的 `task_id` |

!!! warning "Accepted-but-dispatch-failed is not silent success"
    若 task 已持久化但 enqueue 失敗，backend 不得把它包裝成一般 submit success。
    它必須帶有 stable failure code，並讓 queue/detail 能表達這筆 task 需要 dispatch recovery 或 reconcile。

### Dispatch / Runtime Event Family

| Event family | Meaning |
|---|---|
| `task_submitted` | persisted task 已建立，public `task_id` 已存在 |
| `task_dispatch_claimed` | worker/runtime 已 claim 這筆 dispatch；仍屬 runtime metadata family |
| `task_running` | worker 已開始執行或回報 progress heartbeat |
| `task_completed` | worker 成功完成 execution |
| `task_failed` | worker 或 reconcile path 將 task 收斂為 failed |
| `task_cancel_acknowledged` | worker 已 ack graceful cancel |
| `task_terminate_acknowledged` | worker 已 ack force terminate |
| `task_requeued` | 同一筆 `task_id` 已進入新的 dispatch attempt |

## Submission Payload Families

=== "Simulation Submit"

| Field | Meaning |
|---|---|
| `dataset_id` | active dataset |
| `definition_id` | selected canonical definition |
| `task_kind` | simulation lane task；`post_processing` 也走同一條 simulation worker lane |
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
| `status` | discovery 用的 derived row status；必須回聲 `task detail.status`，但不是 page authority |
| `lane` | worker lane identity；`post_processing` row 必須顯示 `simulation` |
| `task_kind` | task execution kind / workflow semantics；不得拿來冒充第三條 worker lane |
| `owner_display_name` | 多使用者 queue 辨識；local mode 可固定為 `Local` 或等價 local operator label |
| `visibility_scope` | queue filter 與共享語意 |
| `updated_at` | 排序與最近活動 |
| `result_availability` | discovery 用的 derived echo；必須對齊 `result_handoff.availability`，但不能單獨解鎖 result surface |
| `reconcile` echo | compact runtime/dispatch reconcile-needed summary；authority 仍來自 task detail |
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

### Attached Task Detail Contract

attached task detail 至少必須提供：

| Field | Meaning |
|---|---|
| `task_id` | attached / recovery primary key |
| `status` | execution status authority |
| `allowed_actions` | attached task control authority |
| `result_handoff.availability` | result readiness authority |
| `result_handoff.result_ref` | `availability = ready` 時的 persisted result identity |
| `result_handoff.reason` | `availability != ready` 時的 stable reason，例如 handoff still pending 或 terminal/no-result |
| `dispatch.queue_name` | persisted dispatch queue identity |
| `dispatch.runtime_job_id` | runtime metadata only；不得作為 UI primary key |
| `dispatch.dispatch_attempt_count` | dispatch / requeue 累積次數 |
| `dispatch.last_dispatch_outcome` | 最近一次 dispatch 結果 |
| `dispatch.last_dispatch_error_code` | 最近一次 dispatch failure code |
| `reconcile.required` | 是否需要 runtime/dispatch reconcile |
| `reconcile.reason` | stable reconcile reason code |
| `reconcile.recorded_at` | reconcile state 最近更新時間 |

!!! warning "Do not derive result readiness from terminal state"
    `completed` 只代表 execution terminal successfully。
    page 是否可以切到 result surface，仍只由 `result_handoff.availability` 決定。

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
| Lane visibility | queue 至少能辨識 task 所屬 worker lane；`post_processing` 與 `simulation` 共用 simulation lane |
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
| Queue-backed local runtime is canonical | local mode 的 accepted execution path 是 enqueue -> independent worker process consume，不是 app-local thread execution |

## Recovery Semantics

| Situation | Authority-first behavior | Forbidden inference |
|---|---|---|
| submit success | backend 回傳 `task_id`；page 之後必須抓 task detail 建立 attached state | 只靠新 queue row 決定 page 已附著成功 |
| attach existing task | 先用 `task_id` 讀 detail，再用 queue row 補 discovery context | 直接拿 queue row 當 page body truth |
| refresh / reconnect | 先重抓 task detail；若 detail 成功，再同步 queue row / worker summary | 因 queue row 還在就假設 attached state 可直接沿用 |
| queue row 與 detail 不一致 | 以 detail 為準；queue read model 後續自行收斂 | 用 queue row 反向覆寫 page status |
| terminal task without result | `status` 可為 terminal，但 page 只有在 `result_handoff.availability = ready` 才切 result | `status == completed` 就直接進 result browse |
| workspace / mode rebinding | 若 `task_id` 對新 authority 不可見，回傳 detached / not_visible 類型訊號 | 把舊 workspace 或舊 mode 的 attached task 繼續當成有效 |
| result handoff pending | page 保持 terminal-or-pending handoff state，等 detail 回傳新 `result_handoff` | 用 queue badge 或 event digest 猜測結果應已可讀 |

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
        "dispatch": {
          "status": "accepted",
          "queue_name": "simulation",
          "accepted_at": "2026-03-14T10:11:58Z",
          "enqueued_at": "2026-03-14T10:11:58Z",
          "runtime_job_id": "rq_job_94d3",
          "dispatch_attempt_count": 1,
          "last_dispatch_outcome": "enqueue_succeeded",
          "last_dispatch_error_code": null,
          "last_updated_at": "2026-03-14T10:11:58Z"
        },
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
        "dispatch": {
          "status": "completed",
          "queue_name": "simulation",
          "accepted_at": "2026-03-14T10:11:58Z",
          "enqueued_at": "2026-03-14T10:11:58Z",
          "runtime_job_id": "rq_job_94d3",
          "dispatch_attempt_count": 1,
          "last_dispatch_outcome": "claimed",
          "last_dispatch_error_code": null,
          "last_updated_at": "2026-03-14T10:12:04Z"
        },
        "reconcile": {
          "required": false,
          "reason": null,
          "recorded_at": null
        },
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
            "reconcile": {
              "required": false,
              "reason": null
            },
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
            "reconcile": {
              "required": false,
              "reason": null
            },
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
| `task_enqueue_failed` | `runtime_unavailable` | persisted task 已建立，但 enqueue 到 lane queue 失敗 |
| `worker_runtime_unavailable` | `runtime_unavailable` | submit / retry 時對應 lane 的 runtime backend 不可用 |
| `task_dispatch_stale` | `conflict` | persisted dispatch metadata 已 stale，需要 reconcile 後才能繼續 |
| `task_reconcile_required` | `conflict` | task detail 目前處於 reconcile-required 狀態，不能由 frontend 自行腦補成正常進行中 |
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
