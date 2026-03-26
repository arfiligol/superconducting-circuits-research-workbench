---
title: "Task Management"
aliases:
  - "Frontend Task Management"
  - "Task Queue"
  - "Task Attachment"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
status: draft
owner: docs-team
audience: team
scope: Frontend runtime-mode-aware shared header task queue、task attachment、worker summary、control actions、refresh recovery 與 standalone tasks-page boundary contract
version: v0.16.0
last_updated: 2026-03-27
updated_by: codex
---

# Task Management

本頁定義 frontend shared task management surface：Header `Tasks Queue`、attached task、worker summary、control actions、result handoff、refresh recovery 與 standalone `Tasks` page boundary。

!!! info "Surface Boundary"
    這裡定義的是 shared task-centric contract，供 `Circuit Simulation` 與 `Characterization` 共用。
    analysis-specific `Run History` 與 artifact-specific result layout 不屬於本頁 owner 範圍。

!!! warning "Persisted Task Authority"
    task queue、attach、refresh recovery 必須以 persisted task state 為準。
    page-local memory 只能做暫時顯示，不可成為 execution authority。

!!! important "Queue Is Discovery, Not Page Authority"
    - page attached task truth 必須來自 task detail，而不是 queue row
    - task execution status authority = `task detail.status`
    - result readiness authority = `result_handoff.availability`

!!! info "Active Workspace Boundary"
    Header queue 只顯示目前 active workspace 中可見的 tasks。
    切換 workspace 後，queue content、allowed actions 與 attached task validity 都必須重新計算。

!!! info "Runtime Mode Boundary"
    local mode 與 online mode 共用同一份 queue surface，但 queue rows、visibility 與 control permission 必須依目前 active mode 重算。

!!! important "Independent Worker Topology Is Visible To The UI"
    local runtime topology =
    - `uv run sc-app`
    - `uv run sc-worker-simulation`
    - `uv run sc-worker-characterization`

    frontend 的 queue / worker summary / recovery contract，必須假設 heavy work 在獨立 worker process 執行，而不是在 app process 內同步或 background thread 執行。

## Shared Objects

| Object | Responsibility |
|---|---|
| Header Task Trigger | 在所有 app pages 上可直接打開右側 shell-side panel 的 queue section |
| Shell-Side Panel | shared shell 的右側 management surface，承接 `Global Context` 與 `Account` 兩大 panel families |
| Global Context Panel | 先以 summary cards 呈現 runtime mode、workspace、dataset、queue、worker 五個 sections，再顯示 selected section detail |
| Task Queue Section | `Global Context` 內的一個 selectable section；顯示最近可見的 tasks，支援 filter、attach、cancel、terminate、retry |
| Standalone Tasks Page | `/tasks`；extended browse / history / detail / audit surface，不取代 Header quick management |
| Worker Summary | Header 顯示 compact summary；drawer 顯示 lane-level detail |
| Attached Task | 表示目前 page body 正在關注的單一 persisted task |
| Lifecycle Summary | 顯示 queued / running / completed / failed / cancelled / terminated 與最近 event 概況 |
| Result Handoff | terminal task 完成後，將 page context 切到 persisted result surface |

## Local Runtime Topology Pairing

| Surface | Backend/runtime pairing |
|---|---|
| Header queue rows | 讀取 queue-backed persisted task visibility；不是 app-local background job list |
| Worker summary | 讀取 simulation / characterization 兩條獨立 worker lanes 的 runtime summary |
| Attached task recovery | 以 persisted task detail 重建；不依賴 app process 仍持有 live solver state |
| Local app close / reopen | queue UI 可以關閉再重開；只要 workers 還在，task 應能持續執行並在重開後被重新 attach |

!!! warning "Do not model local mode as app-owned execution"
    即使在 local mode，`sc-app` 也不是 heavy solver host。
    Task Queue 與 page recovery 都不得假設 solver work 跑在 UI / API 所在進程裡。

## Two-layer Queue Model

| Surface | Owns | Should not become |
|---|---|---|
| `Header -> Global Context -> Tasks Queue` | quick management、recent queue visibility、compact worker summary、cross-page recovery、常見 control actions | 大型 history / audit / full-detail wall |
| [`/tasks`](../workspace/tasks.md) | extended browse、longer history、deeper filters、master-detail inspection、event timeline、extended worker / lane inspection | workflow page 的替代品，或 page body 裡的 shell context dump |

!!! tip "Canonical entry first"
    queue 的 canonical shared-shell 入口仍然是 `Header -> Global Context -> Tasks Queue`。
    `/tasks` 是第二層 extended surface，用來承接較重的 browse / history / audit 需求，而不是讓 workflow pages 自己長出 queue dashboard。

## Task Queue Section Contract

| Field / affordance | Required meaning |
|---|---|
| `task_id` | primary recovery / attach key |
| `lane` | worker lane identity；永遠只回答由哪條 worker lane 處理 |
| `task_kind` | task execution kind / workflow semantics；回答 `simulation`、`post_processing`、`characterization` |
| `status` | discovery 用的 derived lifecycle echo；page attached state 仍以 task detail `status` 為準 |
| `summary` | 人類可讀的 task 摘要 |
| `owner_display_name` | 多使用者 queue 中辨識 task owner；local mode 可固定為 `Local` |
| `visibility_scope` | `local`、`workspace` / `private` 等共享可見性語意 |
| `dataset_id` / `definition_id` / design context | 提供與目前頁面 context 的關聯 |
| `updated_at` | 幫助排序最近活動 |
| `Attach` action | 明確將 page body 切到指定 persisted task |
| `Cancel` / `Terminate` / `Retry` actions | 依 task 狀態與使用者權限顯示 |
| result availability | discovery 用的 derived echo；只能提示這列可能可 handoff，不可直接主導 page result gating |
| `reconcile` echo | queue 可顯示 compact reconcile-needed chip，但 authority 仍來自 task detail |
| `next_cursor` / `prev_cursor` | 若 queue section 支援延伸瀏覽 recent rows，應使用 cursor-based meta |

!!! tip "`lane` is not page stage vocabulary"
    workflow page 的 stage、step、tab、panel 都不得借用 `lane` 表達。
    在 frontend task surface 中，`lane` 只屬於 worker runtime；`task_kind` 才屬於 execution semantics。

## Queue Filters And Ordering

| Concern | Baseline |
|---|---|
| Primary filters | `Workspace`, `Mine` |
| Default filter | online mode 預設 `Workspace`；若目前 session 無 workspace-level task visibility，退回 `Mine`；local mode 可退化成 `Local` 或等價單一視角 |
| Ordering | active tasks first，之後 `updated_at desc` |
| Terminal retention in panel | 保留最近 terminal tasks，避免 queue 只剩 active rows |
| Search | 以 `summary`、`task_id`、owner 顯示名做輕量搜尋 |
| Authority | filter availability 與 row actions 以 backend `allowed_actions` 與 session capabilities 為準 |

!!! tip "`Mine` is a filter, not a visibility scope"
    queue 的 `Mine` 來自 owner-based filter。
    `Local Mode` 的 persisted `visibility_scope` 為 `local`；`Online Mode` 才使用 `private` 與 `workspace`。

!!! tip "Drawer, not inline strip"
    `Tasks Queue` 是 shared shell management surface，應集中在右側 `Shell-Side Panel`。
    Header 只保留 trigger / badge / compact worker summary，不應再鋪一條第二層大型 queue strip。

!!! info "Panel first, page second"
    一般 attach、resume、cancel、terminate、retry 與 recent queue visibility，應可在 panel 內完成。
    只有當使用者需要更長 history、更細 filter、較深 event timeline 或 extended worker inspection 時，才進入 [`/tasks`](../workspace/tasks.md)。

!!! warning "Workflow pages must not duplicate the global queue"
    workflow page 可以顯示 stage-local execution summary、latest run summary、`View Task` 或 `Open in Global Context`。
    但不得在 page body 重新做一份全域 queue、worker dashboard、或大型 attachment / recovery diagnostics wall。

!!! warning "Cross-page buttons are not a substitute for IA"
    `Open Task Center`、`Go to Dataset`、`Open Raw Data` 之類的按鈕，只能在它是單一主要下一步時出現。
    workflow page 不應用一排 handoff buttons 取代清楚的 page ownership 與 section hierarchy。

!!! info "Section switcher, not stacked dump"
    `Tasks Queue` 是 `Global Context` panel 內的一個 section。
    queue detail 只有在 queue card 為 selected section 時才展開；workspace、dataset、worker 在非 selected 狀態只保留 cards 摘要。

!!! warning "Single Active Shell Panel"
    queue section 與 account section 屬於同一套右側 shell-side panel interaction model。
    同一時間只能有一個 active panel section；切換 trigger 時應切換 active section，而不是留下被 overlay 擋住的不可點 header trigger。

## Worker Summary Contract

| Field | Required meaning |
|---|---|
| `lane` | 對應獨立 worker lane；`simulation` lane 承接 `simulation` + `post_processing`，`characterization` lane 承接 `characterization` |
| `idle_processors` | worker alive 且可接新 task，但目前沒有在執行 task 的數量 |
| `running_processors` | worker alive 且目前正在執行 task 的數量 |
| `degraded_processors` | worker alive，但 health / liveness evidence 已出現有意義異常的數量 |
| `draining_processors` | 不再接新任務、等待收尾數量 |
| `offline_processors` | absent、unreachable、shut down，或經 backend 判定為 effectively unavailable 的數量 |

!!! warning "Worker summary is not task truth"
    frontend 必須把 worker liveness 與 task lifecycle 分開。
    `idle` 代表 worker alive and available，不代表 `offline`；
    queue row / attached task 的 lifecycle authority 仍只來自 task detail 與 queue read model。

## Management Actions

| Action | Required states | Permission gate | Effect |
|---|---|---|---|
| `Attach` | any visible task | visible to current user | page body 切到指定 task |
| `Cancel` | `queued`, `dispatching`, `running`, `cancellation_requested` | own task or workspace-manage permission | 發出 graceful cancel |
| `Terminate` | `running`, `cancelling`, `termination_requested` | workspace-manage permission | 發出 force terminate |
| `Retry` | `completed`, `failed`, `cancelled`, `terminated` | submit permission + ownership rule | 建立新 task 並保留 lineage |

## Shared States

| State | Meaning |
|---|---|
| `Queue Closed` | Header queue trigger 未開啟 shell-side panel |
| `Queue Open` | 右側 shell-side panel 的 `Global Context` queue section 為 active |
| `Loading` | task list / task detail / worker summary 請求中 |
| `Workspace Switching` | shell 正在切換 active workspace，queue 需暫停舊內容 |
| `Attached` | derived；表示頁面已用 `task_id` 成功抓到 detail，並綁定到一筆 persisted task |
| `Stale` | derived；page body 顯示的是舊結果，等待新的 task detail 或 result render 更新 |
| `Cancellation Requested` | derived；以 attached task detail `status` 顯示已發出 graceful stop |
| `Termination Requested` | derived；以 attached task detail `status` 顯示已發出 force terminate |
| `Reconcile Required` | derived；以 attached task detail `reconcile.required` 顯示 runtime/dispatch conflict 仍待收斂 |
| `Terminal / No Result` | derived；task detail 已 terminal，但 `result_handoff.availability` 仍不是 `ready` |
| `Terminal / Result Ready` | derived；task detail 已 terminal，且 `result_handoff.availability = ready` |

## State Precedence

| Conflicting signals | Winner | Frontend rule |
|---|---|---|
| queue row `status` vs attached task detail `status` | attached task detail `status` | page body、stage gate、inline latest-run summary 都以 detail 為準 |
| `task detail.status == completed` vs `result_handoff.availability != ready` | `result_handoff.availability` | 頁面不得因 `completed` 直接切到 result surface |
| queue row `result_availability` vs attached task detail `result_handoff.availability` | attached task detail `result_handoff.availability` | queue 只負責 discovery；page result readiness 只看 detail |
| page-local convenience chips vs latest backend detail | latest backend detail | derived state 必須被覆蓋，不能反向主導 page |
| run history row vs active attached task | active attached task 由 detail 決定；run history 由 persisted results 決定 | 不得把 run history 當 queue 或 attached-task authority |

## Derived State Contract

| UI state / summary | Type | Depends on | Must not become |
|---|---|---|---|
| queue badge / recent rows | derived | backend queue read model | workflow page authority |
| compact latest-run summary | derived | attached task detail `status` + `result_handoff.availability` | 第二份 lifecycle truth |
| `Terminal / Result Ready` chip | derived | attached task detail `status` + `result_handoff.availability` | result readiness authority |
| `Terminal / No Result` chip | derived | attached task detail `status` + `result_handoff.availability` | no-result authority outside detail |
| worker summary | derived | processor summary authority | task status authority |
| `Reconcile Required` chip | derived | attached task detail `reconcile.required` + `reconcile.reason` | page-local recovery logic |
| context mismatch warning | derived | active dataset / page context + attached task detail bindings | persisted task mutation authority |

!!! warning "Derived state must declare dependencies"
    任何 queue badge、summary、digest、latest-run chip 都只能當 UI convenience。
    若它沒有明確寫出依賴哪個 authority field，就不應被納入正式 contract。

## Live Update Baseline

| Situation | Baseline behavior |
|---|---|
| shell-side panel open on queue | 定期重抓 queue rows 與 worker summary |
| panel closed / queue section hidden | 只維持 badge / worker summary 的低頻更新 |
| after control action | 立即重新抓取對應 task row 與 summary |
| after workspace switch | 停止舊 queue 更新，改抓新 workspace queue |
| after refresh / reconnect | 若存在 attached `task_id`，先抓 task detail，再同步 queue summary |

!!! tip "Latest Backend State Wins"
    queue row、worker summary、allowed actions 與 attached task 都以最新 backend 回應為準。
    frontend 可以做 optimistic affordance，但不得在 backend 已拒絕後繼續保留舊 action state。

## Recovery Semantics

| Situation | Required frontend behavior | Must not do |
|---|---|---|
| submit then auto-attach | 收到 `task_id` 後抓 detail，detail 成功才把 page 視為 attached | 只靠 queue row 出現就切換 page authority |
| attach from queue row | queue row 只提供 discovery 入口；page 仍需再抓 detail | 直接把 row payload 當 page state |
| refresh / reconnect | 先重抓 attached `task_id` 的 detail，再重抓 queue / worker summary | 先用 queue row 回填 page body |
| local app restart while workers stay alive | 重開後重新抓 queue / detail 並恢復 attach；不得假設 local task 因 app 關閉而終止 | 把 app process 關閉等同於 local execution 結束 |
| backend 回傳 `reconcile.required = true` | 顯示 compact reconcile-needed 狀態，並禁止 page 自行推論成 completed / running | 在 frontend 自己發明 retry/requeue/recover 流程 |
| workspace / mode switch | 重新驗證 attached `task_id` 是否仍可見；不可見就 detached 並提示原因 | 把舊 mode / workspace 的 attached task 繼續視為有效 |
| terminal with pending handoff | 顯示 terminal-or-handoff-pending，不切 result | 以 `completed` 或 queue badge 推定 result ready |
| terminal with ready handoff | 允許 workflow page 切到 persisted result surface | 等 queue row 先變綠才允許 handoff |

## Permission Resolution

| Concern | Rule |
|---|---|
| `Attach` | 只要 task 對目前 session 可見，就應允許 |
| `Cancel` | 依 `can_cancel_own_tasks` 或 `can_cancel_workspace_tasks` 決定 |
| `Terminate` | 依 `can_terminate_workspace_tasks` 決定，不由 frontend 猜測 |
| `Retry` | 依 ownership 與 backend 回傳 `allowed_actions` 決定 |
| Filter visibility | `Workspace` / `Mine` 的可用性由 session capability summary 決定 |
| Local mode baseline | local mode 不要求 multi-user permission matrix，但仍應由 backend capability summary materialize 可用 actions |

## Interaction Rules

=== "Submit And Attach"

    1. page 提交新 task
    2. 立即取得 persisted `task_id`
    3. Header queue 立即出現該 task
    4. page body 自動附加到該 task
    5. lifecycle summary 與 result area 轉為 task-driven state

=== "Attach Existing"

    1. 從 Header 打開右側 shell-side panel 的 queue section，或使用 `Attach Latest`
    2. page body 切換到該 task
    3. 以 persisted task detail / events / result refs 重建畫面

=== "Cancel / Terminate"

    1. 從 Header queue row 點擊 `Cancel` 或 `Terminate`
    2. backend 立即回寫 control request
    3. 頁面顯示 `Cancellation Requested` 或 `Termination Requested`
    4. terminal status 與 result availability 由 persisted task state 決定

=== "Refresh Recovery"

    1. refresh / reconnect 後，若 URL 或 page state 仍指向既有 `task_id`
    2. frontend 必須能重讀 persisted task state
    3. 不得因刷新而退回尚未附加的初始畫面

=== "Workspace Switch"

    1. Header 切換 active workspace
    2. queue rows 改為新 workspace 中可見的 persisted tasks
    3. 若目前 attached task 不再可見，前端必須解除附著並提示原因
    4. 之後再依新 workspace 重新選擇 dataset / task

=== "Runtime Mode Switch"

    1. Header 切換 `Local Mode` 或 `Online Mode`
    2. queue rows 與 worker summary 改抓新 mode 的 authority
    3. 舊 mode 的 attached task 一律重新驗證；若不可見，必須解除附著
    4. 不得把 local queue rows 與 online workspace queue 混合顯示

=== "Active Dataset Switch"

    1. Header 切換 active dataset
    2. queue 保持同一 workspace 邊界，但 page body 重新計算 dataset-bound panels
    3. 若 attached task 與新 dataset 顯著不一致，頁面必須提示 `context mismatch`，但不應直接篡改 persisted task

## Page Variants

=== "Circuit Simulation"

    | Aspect | Requirement |
    |---|---|
    | Queue entry | queue 由 Header trigger + shell-side panel 提供，頁面不重複造一份全域 queue |
    | Page-local task UI | 只允許 stage-local status、latest run summary、`View Task`、`Resume Latest`、`Open in Global Context` |
    | Result handoff | 任務完成後切到 simulation result 或 post-processing result stage，不做 generic task diagnostics page |
    | Context binding | task 與 active definition、dataset 必須可同時被看見 |

## Workflow Page Guardrail

| Rule | Meaning |
|---|---|
| Workflow pages stay workflow-first | page-local task UI 只能回答目前 stage 是否可繼續，不得取代 global queue / worker surfaces |
| Stage-local summary only | inline task UI 最多顯示 latest run summary、status、compact failure summary 與 jump actions |
| Deep task control stays global | 完整 queue browse、worker lane state、跨頁 recovery 與 event drill-down 應回到 Header `Global Context` |
| No duplicated shell context | page body 不得再補 runtime mode、active dataset、submit authority 等與 shared shell 重複的 context cards |
| No handoff wall | 不得把 attach、recovery、cross-page navigation 做成頁面主視覺；若需要 deeper control，導回 `Global Context` |

=== "Characterization"

    | Aspect | Requirement |
    |---|---|
    | Queue entry | 透過 Header trigger + shell-side panel 觀察 shared task activity 與 worker status |
    | Page-local task UI | 只允許 latest run summary、compact stage state、`Resume Latest Run`、`View Task`、`Open in Global Context` |
    | Run history relation | `Run History` 是 analysis artifact surface，不取代 shared task semantics |
    | Result handoff | completed task 之後切到 persisted characterization results |

=== "Standalone Tasks Page"

    | Aspect | Requirement |
    |---|---|
    | Role | extended queue browse / history / detail / worker inspection，不取代 Header quick management |
    | Relation to panel | `Global Context` 先承擔 quick actions；需要更長 history / deeper filters / richer detail 時才進入 page |
    | Workflow impact | workflow page 不得因為有 `/tasks` 就失去最基本的 stage-local task continuity |

!!! tip "Run History 不是 Task Queue"
    `Run History` 回答的是「這個 analysis 曾經跑過什麼」；
    `Task Queue` 回答的是「目前有哪些 persisted task 可以 attach、追蹤、取消、終止或恢復」。

## Authority Pair

| Concern | Authority |
|---|---|
| local / online queue boundary | [App / Shared / Runtime Modes](../../shared/runtime-modes.md), [Backend / Session & Workspace](../../backend/session-workspace.md) |
| task submission / detail / latest / control actions | [Backend / Tasks & Execution](../../backend/tasks-execution.md) |
| result attachment / persisted result availability | [Backend / Tasks & Execution](../../backend/tasks-execution.md), [Backend / Datasets & Results](../../backend/datasets-results.md) |
| workspace-scoped resource visibility | [App / Shared / Resource Ownership & Visibility](../../shared/resource-ownership-and-visibility.md) |
| control-action permission | [App / Shared / Authentication & Authorization](../../shared/authentication-and-authorization.md) |
| worker summary / terminate semantics | [App / Shared / Task Runtime & Processors](../../shared/task-runtime-and-processors.md) |

## Primary Consumers

| Consumer | Why it depends on Task Management |
|---|---|
| [Circuit Simulation](../research-workflow/circuit-simulation.md) | 需要 task submission、attach、recovery、result handoff |
| [Characterization](../research-workflow/characterization.md) | 需要 live run attach、refresh recovery、result handoff |
| [Tasks](../workspace/tasks.md) | 需要 extended queue browse、history、detail、worker inspection 與 control actions |

## Related

- [Header](../shared-shell/header.md)
- [Sidebar](../shared-shell/sidebar.md)
- [Backend / Tasks & Execution](../../backend/tasks-execution.md)
- [App / Shared / Authentication & Authorization](../../shared/authentication-and-authorization.md)
- [App / Shared / Task Runtime & Processors](../../shared/task-runtime-and-processors.md)
