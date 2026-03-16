---
title: "Runtime Modes"
aliases:
  - "App Runtime Modes"
  - "Local Mode and Online Mode"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: 同一個 App 的 Local Mode / Online Mode、frontend/backend mode pairing 與 mode-switch isolation contract
version: v0.1.0
last_updated: 2026-03-16
updated_by: codex
---

# Runtime Modes

本頁定義同一個 App 的兩種正式 runtime modes：`Local Mode` 與 `Online Mode`。
它們不是兩套不同產品，而是同一個 frontend + backend system 的兩種運行方式。

!!! info "Single App, Two Runtime Modes"
    正式產品模型不是做兩個 App。
    使用者應在同一個 App 中切換模式：切到 `Local Mode` 時直接進入工作區；切到 `Online Mode` 時再依需要進入登入流程。

!!! warning "Mode Switch Must Rebind Shell Context"
    mode switch 不是單純換一個 label。
    它必須重新繫結 session、workspace、dataset、queue visibility 與 user summary，避免 local / online 內容混用。

## Mode Pairing

| Layer | Local-side name | Online-side name | Meaning |
|---|---|---|---|
| Frontend | `Local Mode` | `Client Mode` | 同一個 frontend app 的兩種連線模式 |
| Backend | `Local Mode` | `Server Mode` | 同一套 backend surfaces 的兩種運行方式 |
| Product pairing | frontend local <-> backend local | frontend client <-> backend server | 不做任意混搭矩陣 |

## Runtime Mode Contract

| Mode | Required meaning |
|---|---|
| `local` | frontend 連到本機 backend；資料與 task runtime 都在本地；不需要 Authentication / Authorization |
| `online` | frontend 連到遠端 server；需要 Authentication / Authorization；支援 workspace collaboration |

## Shared Product Rules

| Rule | Meaning |
|---|---|
| Same shell vocabulary | Header、Sidebar、workflow pages 盡量維持同一套 UI shell，而不是做兩套產品外觀 |
| Same backend surface family | local 與 online 優先共用同一組 backend authority surfaces；差異主要在 auth、collaboration 與 connection target |
| Mode-aware session | frontend 不自行拼湊 local / online state；session envelope 仍由 backend authority 擁有 |
| No mixed context | 任何 mode switch 都必須清掉不再有效的 session / task / queue / dataset caches |

## Local Mode Baseline

| Concern | Required behavior |
|---|---|
| Auth | 不需要 sign in；auth entry 不應攔住主流程 |
| Authorization | 不啟用 multi-user authorization gate；由 backend 回傳 local capability summary |
| User identity | 使用 implicit local user / local operator summary |
| Workspace model | 使用單一 implicit local workspace，維持與 app shell 相容的 context shape |
| Data | 以本地 datasets、results、tasks、artifacts 為主 |
| Queue | 顯示 local runtime tasks，不承擔 shared workspace visibility semantics |
| Collaboration | invitation、membership、shared task governance 不適用 |

## Online Mode Baseline

| Concern | Required behavior |
|---|---|
| Auth | 需要 sign in / session continuity |
| Authorization | 啟用 workspace role、capabilities、allowed actions |
| User identity | 使用 authenticated user summary |
| Workspace model | multi-workspace membership + single active workspace |
| Data | 以 remote server authority 為準 |
| Queue | 顯示 active workspace 中可見的 shared tasks |
| Collaboration | invite、join、leave、membership management 生效 |

## Session Shape Across Modes

| Concern | Local mode | Online mode |
|---|---|---|
| `runtime_mode` | `local` | `online` |
| `auth.state` | `local_bypass` 或等價 local state | `authenticated`, `anonymous`, `degraded` |
| `user` | implicit local operator | authenticated user |
| `workspace` | implicit local workspace | active workspace membership |
| `capabilities` | local-full or local-safe capability summary | backend materialized permission summary |
| `active_dataset` | local dataset context | remote dataset context |

!!! tip "Same shape, different authority semantics"
    local mode 與 online mode 應盡量共用同一種 session envelope shape。
    這樣 frontend 可以保持同一套 shell；真正不同的是每個欄位背後的 authority semantics。

## Mode Switch Contract

| Step | Required behavior |
|---|---|
| 1. User selects mode | 可從 app-level mode switcher 選 `Local Mode` 或 `Online Mode` |
| 2. App freezes unsafe context | 若目前存在 dirty draft、attached task 或 destructive context，先要求確認 |
| 3. Session is invalidated | 舊 mode 的 session envelope、capability cache、queue cache、attached task refs 全部失效 |
| 4. New connection target is bound | local mode 指向本機 backend；online mode 指向 configured server target |
| 5. New session is established | local mode 直接回 local session；online mode 若未登入則進 auth entry |
| 6. Shell context is rebuilt | active workspace、dataset、queue 與 user summary 用新 mode 重新計算 |

## Mode Switch Outcomes

| Outcome | Meaning |
|---|---|
| `entered_local` | local session 建立成功，直接進 app shell |
| `entered_online_authenticated` | online session 已存在且可直接進 shell |
| `entered_online_auth_required` | online mode 需要 auth entry，使用者尚未登入 |
| `context_cleared` | 舊 mode context 已清空，等待新 mode session ready |

## Isolation Rules

| Concern | Required behavior |
|---|---|
| Session cache | local / online 不得共用同一份 session cache |
| Active dataset | 切 mode 後不得沿用舊 mode 的 dataset identity |
| Attached task | 切 mode 後必須解除附著，除非新 mode 中仍能重新解析相同 persisted task |
| Queue rows | local queue 與 online queue 不得混合顯示 |
| Error messaging | debug / auth / capability errors 必須對應目前 active mode，不得顯示另一個 mode 的殘留訊息 |

## Consumer Expectations

| Consumer | What it should do |
|---|---|
| Header | 顯示目前 runtime mode，並提供 mode-aware account / global context entry |
| Auth Entry | 只在 `online` 需要 auth 時成為 primary entry；local mode 應可直接 bypass |
| Session & Workspace | 提供 mode-aware session envelope 與 mode-switch mutation |
| Authentication & Authorization | 只對 `online` 強制生效；local mode 走 bypass contract |
| Task Management | local mode 顯示 local tasks；online mode 顯示 workspace-visible tasks |

## Related

* [Identity & Workspace Model](identity-workspace-model.md)
* [Authentication & Authorization](authentication-and-authorization.md)
* [Frontend / Header](../frontend/shared-shell/header.md)
* [Frontend / Auth Entry](../frontend/shared-shell/auth-entry.md)
* [Backend / Session & Workspace](../backend/session-workspace.md)
