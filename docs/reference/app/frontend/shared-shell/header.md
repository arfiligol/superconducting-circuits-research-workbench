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
scope: Frontend shared header 的 shell identity、runtime mode entry、global context entry、account surface、developer mode 與 shell-side panel contract
version: v0.12.0
last_updated: 2026-05-27
updated_by: codex
---

# Header

本頁定義 frontend shared header 的正式契約。它是 app shell 的 single-line identity、compact global context entry 與 account-preference entry surface。

!!! info "Surface Boundary"
    Header 負責唯一可見的 shell identity、`Runtime Mode`、`Active Workspace`、`Active Dataset`、`Tasks Queue`、worker status summary、account surface 與 app-level preferences。
    page-local title、workspace management page、membership management、form、table filter、result table 與 editor internals 不屬於 Header。

!!! warning "Single Visible Shell Identity"
    Header 只允許一個可見 shell identity：`SUPERCONDUCTING CIRCUITS`。
    它必須維持單行，且不得再出現 `Research Workbench`、secondary shell subtitle 或額外 brand helper text。

!!! warning "Global Context Lives Behind Compact Triggers"
    `Runtime Mode`、`Active Workspace`、`Active Dataset` 與 `Tasks Queue` 是 shared shell 的 global context。
    使用者必須能從 Header 進入這些 context，但 Header closed state 只顯示 compact triggers，不鋪開 summary cards。

!!! warning "Page Bodies Must Not Duplicate Shell Context"
    以下內容屬於 shared shell，不應在各 page body 再鋪成 summary cards 或 authority walls：
    `Runtime Mode`、`Active Workspace`、`Active Dataset`、`Tasks Queue`、worker summary、queue recovery / attach / cancel / retry / terminate、shell-level session / authority summary。
    若頁面只是在重複 shell 已知資訊，就應移除，而不是保留成「helpful context」。

!!! tip "Compact Trigger, Selected Detail Elsewhere"
    Header 仍然是 global context owner，但只承載 compact triggers / chips。
    實際的 workspace switch、dataset switch、queue rows、account preference 與 debug disclosure，應集中在右側 `Shell-Side Panel`；worker lane detail 與 long task history 應進入 `/tasks` 或 developer disclosure。

!!! tip "Read With Task Management"
    Header 負責「從哪裡切換 active workspace、切換 dataset、打開 queue、看 worker 狀態、開啟 user menu」。
    queue row 內 `Attach`、`Cancel`、`Terminate`、`Retry` 的行為語意，則由 [Task Management](../shared-workflow/task-management.md) 定義。

## Slot Map

| Slot | Responsibility |
|---|---|
| Left Cluster | Sidebar toggle、single-line shell identity |
| Global Context Cluster | `Runtime Mode`、`Active Workspace`、`Active Dataset`、`Tasks Queue` 的 compact triggers / chips |
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
| Sections | 至少承接 `Global Context` 與 `Account` 兩大 panel families |
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

## Global Context Panel

| Concern | Required behavior |
|---|---|
| Role | shared shell 的 compact management entry，承接 workspace、dataset 與 recent queue detail |
| Top row | 顯示 3 至 4 個 compact section triggers：`Runtime Mode`、`Active Workspace`、`Active Dataset`、`Tasks Queue` |
| Trigger role | triggers 是 section switchers；不得為了「完整」改成大型 summary cards |
| Detail model | triggers 下方只顯示目前 selected section 的 detailed content，不得把所有 section 一次整疊鋪開 |
| Non-selected sections | 非 selected section 只保留 compact trigger label / badge，不顯示完整 detail body |
| Worker rule | worker 只在 queue trigger 顯示 compact health badge；lane detail 屬於 `/tasks` 或 developer disclosure |
| Density rule | `Global Context` 必須 summary-first 且 selected-section-only；不得變成 shell-state 管理牆 |

!!! tip "Selected-section detail only"
    `Global Context` 的核心是「compact triggers 切 section，detail 區只顯示一個 active section」。
    不要把 runtime mode、workspace、dataset、queue、worker 五段內容整包常駐展開。

## Global Context Order

| Order | Control | Why it comes first |
|---|---|---|
| 1 | `Runtime Mode` | 決定是否連到 local backend 或 remote server，也決定 auth 是否必要 |
| 2 | `Active Workspace` | 決定 dataset list、queue visibility 與 capability context |
| 3 | `Active Dataset` | 決定 workflow pages 的預設 dataset scope |
| 4 | `Tasks Queue` | 顯示目前 workspace / mode 中的 task activity |
| 5 | user menu | identity、settings、appearance 與 sign out |

## Global Controls

=== "Runtime Mode Trigger"

    | Element | Required behavior |
    |---|---|
    | mode chip / button | 顯示目前為 `Local Mode` 或 `Online Mode`，並可附帶 compact target summary |
    | open behavior | 點擊後打開右側 shell-side panel 的 `Global Context` runtime-mode section |
    | mode switch | 應支援切到 local 或 configured online target；切換後不得混用舊 mode 的 workspace / dataset / task state |
    | local outcome | 切到 local mode 時，直接進入 local session，不經 auth entry |
    | online outcome | 切到 online mode 時，先驗證 active server target；成功後應收到 `entered_online_auth_required` outcome，且 auth transition 為 `online_auth_required` 或 `online_session_dropped`，再重新進入 auth entry |
    | target summary source | compact target summary 應來自 `connection.target` 的 summary object（`label` / `origin` / `validation_status`），不是由 frontend 自行拼字串 |
    | unsafe-context handling | 若切 mode 會清掉 dirty draft、attached task 或 queue context，必須先要求確認 |

=== "Active Workspace Trigger"

    | Element | Required behavior |
    |---|---|
    | workspace chip / button | 直接顯示目前 active workspace 名稱與 role 摘要 |
    | open behavior | 點擊後打開右側 shell-side panel 的 `Global Context`，聚焦 workspace section，只列出目前 user memberships |
    | mode applicability | local mode 下可退化成單一 `Local Space` summary，不必強制顯示多 membership switcher |
    | propagation | 切換後必須同步更新 active dataset、queue visibility、role / capabilities |
    | unsafe-context handling | 若切換造成 attached task 或 active dataset 不再可見，Header 必須觸發清理或重選流程 |
    | dirty-state handling | 若目前頁存在 dirty draft，Header 先顯示 confirm，再送出 switch mutation |

=== "Active Dataset Trigger"

    | Element | Required behavior |
    |---|---|
    | dataset chip / button | 直接顯示目前 active dataset 名稱與狀態 |
    | open behavior | 點擊後打開右側 shell-side panel 的 `Global Context` dataset section，僅列出 active workspace 中可見的 datasets，並支援 search 與 select |
    | propagation | 切換後必須同步更新 Dashboard、Raw Data、Simulation、Characterization |
    | no-dataset state | 若目前 workspace 尚無可用 dataset，trigger 必須顯示 clear empty state 與 next step |

=== "Tasks Queue Trigger"

    | Element | Required behavior |
    |---|---|
    | queue button / badge | 顯示目前可見 active tasks 數量 |
    | open behavior | 點擊後打開右側 shell-side panel 的 `Global Context` queue section |
    | queue section | 展示少量 recent queue rows 與 filter (`Workspace` / `Mine`)；非 selected sections 只留 compact trigger 摘要 |
    | mode behavior | local mode 顯示 local runtime tasks；online mode 顯示 workspace-visible shared tasks |
    | worker summary | Header / Global Context 只保留 compact health badge；各 lane 的 `idle / running / degraded / draining / offline` detail 進入 `/tasks` 或 developer disclosure |
    | liveness wording | `idle` 代表 worker alive and available；`offline` 只代表 unavailable，不得把 merely idle worker 或被動 heartbeat 稀疏的 worker 誤標成 `offline` |
    | row action entry | 每列至少支援 `Attach`，並依權限顯示 `Cancel` / `Terminate` / `Retry` |
    | default ordering | active tasks 優先，之後按 `updated_at desc` 顯示最近 terminal tasks |
    | extended browse | standalone [`Tasks`](../workspace/tasks.md) page 負責較長 history / deeper inspect；panel 不得變成第二個 full task center |

=== "User Menu"

    | Element | Required behavior |
    |---|---|
    | user icon trigger | 關閉狀態只顯示 compact identity / avatar / initials 與必要的 compact warning indicator |
    | closed-state density | 關閉狀態不得攤開完整錯誤文案、session diagnostics 或 recovery instructions |
    | open behavior | 可直接打開右側 shell-side panel 的 `Account` section，不得打開第二套獨立 overlay 模型 |
    | menu sections | 至少包含 mode-aware `Account Summary`、`Appearance`、`Developer Mode` 與對應的 auth / mode actions |
    | opened-state detail | 完整 degraded / warning / recovery detail 只在打開後顯示 |
    | appearance control | `Light / Dark / System` 由 User Menu 擁有，不由 Sidebar 擁有 |

## Account Surface Contract

| Concern | Required behavior |
|---|---|
| Role | lightweight personal / app-preference surface，不是 shell-wide state-management surface |
| Allowed content | account summary、appearance、developer mode、mode-aware auth actions 與 runtime-mode entry |
| Mode relation | account 可顯示目前 mode 的 account-side summary，並提供 mode switch entry；真正的切換 authority 仍是 shared runtime-mode mutation |
| Excluded content | workspace state、session diagnostics、membership management、queue detail、heavy collaboration controls |
| Header density | account panel header 應保持簡潔，可使用 `Account`、`Appearance` 或等價輕量標題 |
| Branding rule | account panel 不得再次重複 `SUPERCONDUCTING CIRCUITS` 或其他 shell identity |
| Diagnostics rule | 若需要顯示 degraded / error / debug detail，必須在 opened panel 內以 disclosure 或 secondary block 呈現 |

## Account Surface By Mode

| Mode | Required account behavior |
|---|---|
| `local` | 顯示 local operator / `Local Space` summary、appearance、developer mode 與 `Connect to Online Mode` / 指定 target 入口；不顯示 remote sign out |
| `online-authenticated` | 顯示 authenticated user summary、appearance、developer mode、target summary、`Sign out` 與 `Switch to Local Mode` |
| `online-auth-required` | 顯示 target summary、appearance、developer mode、`Sign in`、重新指定 `IP:Port` / target 與 `Switch to Local Mode`；不冒充已有 authenticated account |
| `online-session-dropped` | 顯示 target summary 與 compact warning，說明目前已連到 target 但舊 online session 不再可沿用；優先引導重新登入 |

!!! tip "Local account is preference-first"
    `Local Mode` 下的 account surface 不是登入入口的縮小版。
    它應該先回答「目前在 Local Space、這是本地操作員、這裡可以切外觀或開 Developer Mode」，需要連線時再提供切到 online 的入口。

## Developer Mode Preference

| Concern | Required behavior |
|---|---|
| Ownership | app-level preference，與 `Appearance` 同層，由 account surface 擁有 |
| Scope | 不屬於 workspace-scoped，也不屬於 session-scoped |
| Default | local development build 可預設 `On`；產品向 user-facing sessions 預設 `Off` |
| `Off` behavior | primary product UI 只顯示 concise status 與 recovery messaging；若仍需保留 technical detail，應放在 secondary disclosure、debug panel 或 compact debug block |
| `On` behavior | 允許 raw backend / JS exception detail 直接出現在發生問題的主內容區，幫助辨識是哪個 UI surface 壞掉；debug panel 仍可保留作更完整的 structured detail |
| Covered surfaces | shell-side panels、auth entry、page-level error blocks、diagnostics-heavy workflow surfaces |

!!! info "Developer Mode controls message density, not panel existence"
    `Developer Mode` 決定的是主內容區錯誤訊息要顯示 user-safe summary，還是 raw technical detail。
    它不負責決定 debug panel 是否存在；secondary debug surface 在 `On` 與 `Off` 兩種模式下都可以存在。

!!! warning "Inline raw detail should stay local to the failing surface"
    即使 `Developer Mode` 為 `On`，raw technical detail 也應出現在對應的壞掉區塊，而不是把整個頁面變成 diagnostics wall。

## Toggle And Trigger Affordance

| Control | Required behavior |
|---|---|
| Sidebar toggle | 必須有 pointer cursor、清楚 hover state 與 focus-visible state |
| Global context cards / chips | 必須明確可點、selected state 明顯、不可只靠文字說明理解互動 |
| Account trigger | 必須有 pointer cursor、hover 與 focus-visible state；closed state 保持 compact |

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
| Runtime mode is the outer shell boundary | `Runtime Mode` 先決定 local / online authority，再往下決定 workspace、dataset 與 queue context |
| Workspace is top-level shell context | `Active Workspace` 優先於 `Active Dataset`，因為 dataset list、queue 與 capabilities 都依賴它 |
| Queue is globally reachable | 不論目前在哪一頁，都能從 Header 打開 `Tasks Queue` |
| Worker summary is runtime-driven | Header 顯示的 compact worker badge 必須來自 runtime summary，不可由 UI 推測 |
| Header is summary-first | Header 可以提示 dirty / attached / stale，但不應攤平大型管理 UI |
| Shell-side panel owns selected detail | workspace switch、dataset switch、recent queue rows 與 account detail 應集中在右側 panel；worker lane detail 與 long history 屬於 `/tasks` |
| Account is preference-first | account panel 優先承擔 personal/app preference，不承擔 workspace 與 collaboration 管理面 |
| Responsive collapse | 窄螢幕可縮成 icon + chips，但仍必須保留 dataset、queue 與 user menu trigger |
| Helpful context is not enough | page 若能透過 Header / Global Context 取得資訊，就不應再重做 runtime / dataset / authority summary cards |

!!! tip "Header vs Sidebar"
    Header 負責 global context 與 user controls 的 entry。
    [Sidebar](sidebar.md) 只負責穩定導航，不再承擔 dataset switch 或 appearance toggle。

## App Pair

| Concern | Authority |
|---|---|
| active workspace / dataset / user summary | [Backend / Session & Workspace](../../backend/session-workspace.md) |
| runtime mode / mode switch outcome | [App / Shared / Runtime Modes](../../shared/runtime-modes.md), [Backend / Session & Workspace](../../backend/session-workspace.md) |
| attached task summary / queue rows | [Backend / Tasks & Execution](../../backend/tasks-execution.md) |
| permission & user menu capability | [App / Shared / Authentication & Authorization](../../shared/authentication-and-authorization.md) |
| workspace ownership / visibility | [App / Shared / Resource Ownership & Visibility](../../shared/resource-ownership-and-visibility.md) |
| worker / processor status summary | [App / Shared / Task Runtime & Processors](../../shared/task-runtime-and-processors.md) |

## Related

- [Sidebar](sidebar.md)
- [Task Management](../shared-workflow/task-management.md)
- [Runtime Modes](../../shared/runtime-modes.md)
