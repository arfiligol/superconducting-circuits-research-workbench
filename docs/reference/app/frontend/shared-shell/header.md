---
title: "Header"
aliases:
  - "Frontend Header"
  - "Workspace Header"
  - "App Header"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
status: draft
owner: docs-team
audience: team
scope: Frontend shared header 的 shell identity、active workspace、global context controls、shell-side panel、task queue 與 user menu contract
version: v0.5.0
last_updated: 2026-03-16
updated_by: codex
---

# Header

本頁定義 frontend shared header 的正式契約。它是 app shell 的 single-line identity 與 global context entry surface。

!!! info "Surface Boundary"
    Header 負責唯一可見的 shell identity、`Active Workspace`、`Active Dataset`、`Tasks Queue`、worker status summary 與 user menu。
    page-local title、form、table filter、result table 與 editor internals 不屬於 Header。

!!! warning "Single Visible Shell Identity"
    Header 只允許一個可見 shell identity：`SUPERCONDUCTING CIRCUITS`。
    它必須維持單行，且不得再出現 `Research Workbench`、secondary shell subtitle 或額外 brand helper text。

!!! warning "Global Context Lives In Header"
    `Active Workspace`、`Active Dataset` 與 `Tasks Queue` 是 shared shell 的 global context。
    使用者必須能在 Header 直接點擊、展開與操作它們，而不是各頁各自重造入口。

!!! tip "Compact Trigger, Heavy Management Elsewhere"
    Header 仍然是 global context owner，但應優先承載 compact triggers / chips。
    實際的 workspace switch、dataset switch、queue rows、worker detail 與 user controls，應集中在右側 `Shell-Side Panel`，而不是把大型管理面板攤平在 top bar 下方。

!!! tip "Read With Task Management"
    Header 負責「從哪裡切換 active workspace、切換 dataset、打開 queue、看 worker 狀態、開啟 user menu」。
    queue row 內 `Attach`、`Cancel`、`Terminate`、`Retry` 的行為語意，則由 [Task Management](../shared-workflow/task-management.md) 定義。

## Slot Map

| Slot | Responsibility |
|---|---|
| Left Cluster | Sidebar toggle、single-line shell identity |
| Global Context Cluster | `Active Workspace`、`Active Dataset`、`Tasks Queue` 與 worker summary 的 compact triggers / chips |
| Right Cluster | user menu / account trigger |

## Shell Identity Contract

| Concern | Required behavior |
|---|---|
| Visible label | 只顯示 `SUPERCONDUCTING CIRCUITS` |
| Line rule | 必須維持單行，不得換行 |
| Subtitle rule | 不得顯示 `Research Workbench` 或任何 secondary shell copy |
| Ownership rule | Sidebar 不得重複承擔 shell identity |
| Page-title rule | page identity 必須回到 page body，不由 Header 承擔 |

## Shell-Side Panels

| Panel concern | Required behavior |
|---|---|
| Owner | 由 Header triggers 開啟，是 shared shell 的正式 management surface |
| Placement | 右側 drawer / panel；不得要求使用者離開當前頁面才能切換 shell context |
| Sections | 至少承接 workspace switch、dataset switch、queue rows、worker summary 與 account controls |
| Density rule | Header 顯示 compact summary，panel 顯示 management UI；不得把兩者同時鋪平造成雙重密度 |
| Top strip rule | Header 下方不再擁有大型常駐 status strip；若保留 summary strip，也只能是 summary-only，不得承擔 management actions |

## Shell-Side Panel Interaction Model

| Concern | Required behavior |
|---|---|
| Single active panel | 同一時間只能有一個 active shell-side panel |
| Trigger switching | 點擊另一個 header trigger，應切換 active panel，而不是留下第二個 trigger 無法點擊 |
| Same-trigger toggle | 再次點擊同一 trigger 應直接關閉 panel |
| Outside click | 點擊 panel 外側應關閉 |
| Escape | `Escape` 應關閉 active panel |
| Close CTA | 不需要顯式 `Close menu` / `Close panel` CTA 才能關閉 |
| Z-order / hit-testing | open panel 不得把其他 header triggers 變成不可互動；若 panel 開著，其他 trigger 仍必須可切換 active panel |
| Shared model | account panel 與 global-context panel 屬於同一套 shell-side panel interaction model，不是彼此無關的 overlays |

## Global Context Order

| Order | Control | Why it comes first |
|---|---|---|
| 1 | `Active Workspace` | 決定 dataset list、queue visibility 與 capability context |
| 2 | `Active Dataset` | 決定 workflow pages 的預設 dataset scope |
| 3 | `Tasks Queue` | 顯示目前 workspace 中的 shared task activity |
| 4 | worker status summary | 是 queue 與 runtime 的摘要，不高於 queue 本身 |
| 5 | user menu | identity、settings、appearance 與 sign out |

## Global Controls

=== "Active Workspace Trigger"

    | Element | Required behavior |
    |---|---|
    | workspace chip / button | 直接顯示目前 active workspace 名稱與 role 摘要 |
    | open behavior | 點擊後打開右側 shell-side panel，聚焦 workspace section，只列出目前 user memberships |
    | propagation | 切換後必須同步更新 active dataset、queue visibility、role / capabilities |
    | unsafe-context handling | 若切換造成 attached task 或 active dataset 不再可見，Header 必須觸發清理或重選流程 |
    | dirty-state handling | 若目前頁存在 dirty draft，Header 先顯示 confirm，再送出 switch mutation |

=== "Active Dataset Trigger"

    | Element | Required behavior |
    |---|---|
    | dataset chip / button | 直接顯示目前 active dataset 名稱與狀態 |
    | open behavior | 點擊後打開右側 shell-side panel 的 dataset section，僅列出 active workspace 中可見的 datasets，並支援 search 與 select |
    | propagation | 切換後必須同步更新 Dashboard、Raw Data、Simulation、Characterization |
    | no-dataset state | 若目前 workspace 尚無可用 dataset，trigger 必須顯示 clear empty state 與 next step |

=== "Tasks Queue Trigger"

    | Element | Required behavior |
    |---|---|
    | queue button / badge | 顯示目前可見 active tasks 數量 |
    | open behavior | 點擊後打開右側 shell-side panel 的 queue section |
    | queue section | 展示 queue rows、worker summary、filter (`Workspace` / `Mine`) |
    | worker summary | 在 drawer 內可看到各 lane 的 `healthy / busy / degraded / draining / offline` 摘要；header 只保留 compact summary |
    | row action entry | 每列至少支援 `Attach`，並依權限顯示 `Cancel` / `Terminate` / `Retry` |
    | default ordering | active tasks 優先，之後按 `updated_at desc` 顯示最近 terminal tasks |

=== "User Menu"

    | Element | Required behavior |
    |---|---|
    | user icon trigger | 關閉狀態只顯示 compact identity / avatar / initials 與必要的 compact warning indicator |
    | closed-state density | 關閉狀態不得攤開完整錯誤文案、session diagnostics 或 recovery instructions |
    | open behavior | 可直接打開 account panel，或導向右側 shell-side panel 的 account section |
    | menu sections | 至少包含 `Profile Summary`、`Settings`、`Appearance`、`Sign out` |
    | opened-state detail | 完整 degraded / warning / recovery detail 只在打開後顯示 |
    | appearance control | `Light / Dark / System` 由 User Menu 擁有，不由 Sidebar 擁有 |

## Context Switching Outcomes

| Switch | Header must do |
|---|---|
| workspace changed | 重新繫結 active dataset、刷新 queue、更新 role 與 user menu capabilities |
| dataset changed | 更新 dataset chip，通知 workflow pages 重讀 dataset-bound state |
| workspace caused task detachment | 顯示 detached notice，並將 queue panel 保持可重新 attach |
| invite accepted in another workspace | 顯示 `Switch to workspace` CTA，而非無提示地切換 |

## Delivery Rules

| Rule | Meaning |
|---|---|
| Context follows authority | workspace / dataset 來自 session surface；definition 來自 definition surface；task 來自 persisted task surface |
| Workspace is top-level shell context | `Active Workspace` 優先於 `Active Dataset`，因為 dataset list、queue 與 capabilities 都依賴它 |
| Queue is globally reachable | 不論目前在哪一頁，都能從 Header 打開 `Tasks Queue` |
| Worker summary is runtime-driven | Header 顯示的 worker status 必須來自 runtime summary，不可由 UI 推測 |
| Header is summary-first | Header 可以提示 dirty / attached / stale，但不應攤平大型管理 UI |
| Shell-side panel owns heavy management | workspace switch、dataset switch、queue rows、worker detail 與 account detail 應集中在右側 panel |
| Responsive collapse | 窄螢幕可縮成 icon + chips，但仍必須保留 dataset、queue 與 user menu trigger |

!!! tip "Header vs Sidebar"
    Header 負責 global context 與 user controls 的 entry。
    [Sidebar](sidebar.md) 只負責穩定導航，不再承擔 dataset switch 或 appearance toggle。

## App Pair

| Concern | Authority |
|---|---|
| active workspace / dataset / user summary | [Backend / Session & Workspace](../../backend/session-workspace.md) |
| attached task summary / queue rows | [Backend / Tasks & Execution](../../backend/tasks-execution.md) |
| permission & user menu capability | [App / Shared / Authentication & Authorization](../../shared/authentication-and-authorization.md) |
| workspace ownership / visibility | [App / Shared / Resource Ownership & Visibility](../../shared/resource-ownership-and-visibility.md) |
| worker / processor status summary | [App / Shared / Task Runtime & Processors](../../shared/task-runtime-and-processors.md) |

## Related

- [Sidebar](sidebar.md)
- [Task Management](../shared-workflow/task-management.md)
