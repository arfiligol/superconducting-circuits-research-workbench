---
title: "Auth Entry"
aliases:
  - "Frontend Auth Entry"
  - "Login Surface"
  - "Authentication Entry"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
status: draft
owner: docs-team
audience: team
scope: Frontend online-mode login、logout、anonymous / degraded session entry 與 auth-diagnostics density contract
version: v0.3.0
last_updated: 2026-03-16
updated_by: codex
---

# Auth Entry

本頁定義 frontend 在 `Online Mode` 下未登入、已登出或 session degraded 時的正式 auth entry surface。

!!! info "Surface Boundary"
    本頁負責 login / logout / recovery entry 的產品呈現密度。
    workspace membership、invite lifecycle、capability flags 與 JWT transport authority 仍由 shared auth / backend session surfaces 擁有。

!!! warning "Auth Entry Is Online-Mode Only"
    `Local Mode` 不應被 auth entry 攔住。
    使用者切到 local mode 時，應直接進入 app shell；只有 `Online Mode` 且需要 auth 時，auth entry 才成為 primary surface。

!!! warning "Auth Entry Is Not A Diagnostics Dashboard"
    在 anonymous 或 degraded 狀態下，auth entry 的 primary UI 必須聚焦在使用者下一步要做的動作。
    `Auth State`、`Workspace`、`Session Mode` 這類 diagnostics 不得作為 primary cards 預設鋪開。

## Primary Purpose

| Situation | Primary user goal |
|---|---|
| anonymous | sign in / sign up |
| expired session | re-authenticate |
| degraded session | understand the issue briefly, then recover or sign in again |
| signed out | return to sign-in entry quickly |

## Content Density Contract

| Surface area | Required behavior |
|---|---|
| Primary panel | 只承接 action、concise status、minimal recovery guidance |
| Secondary disclosure | diagnostics、session internals、workspace/debug state 只能作 secondary disclosure |
| Tone | 簡潔、產品導向，不可呈現成 developer diagnostics page |
| Copy weight | 能靠 layout、field labels、status badge 與 button hierarchy 解決的，不要再堆段落說明 |

!!! tip "Layout should carry the guidance"
    auth entry 應優先用 card hierarchy、field order、button prominence、status placement 來引導使用者。
    不要依賴大量文字說明才讓使用者知道下一步該做什麼。

## Primary States

| State | Required presentation |
|---|---|
| `anonymous` | 顯示 sign-in / sign-up entry 與最少必要說明 |
| `degraded` | 顯示簡短狀態、compact warning 與 recovery action |
| `signed_out` | 顯示已登出確認與重新登入入口 |
| `invite_pending_auth` | 優先引導登入，再保留 invite continuation |
| `mode_switch_to_local` | 允許使用者改切 local mode，直接 bypass auth entry |

## Diagnostics Placement

| Item | Placement rule |
|---|---|
| `Auth State` | secondary disclosure only |
| `Workspace` | secondary disclosure only |
| `Session Mode` | secondary disclosure only |
| transport / debug refs | secondary disclosure only |
| recovery detail | 可在 secondary disclosure 或 opened panel 顯示，不得搶過 primary action |

## Developer Mode Interaction

| Concern | Required behavior |
|---|---|
| Preference owner | 由 [Header](header.md) 的 account surface 擁有，屬於 app-level preference |
| `Developer Mode = Off` | auth entry 只顯示 concise status、action 與 minimal recovery guidance；raw transport / exception detail 保留在 secondary disclosure 或 debug block |
| `Developer Mode = On` | 允許 transport / technical detail 直接出現在發生錯誤的 auth surface，幫助辨識壞掉區塊；secondary debug block 仍可存在 |
| Guardrail | `Developer Mode` 影響的是錯誤訊息密度，不是 debug surface 是否存在；auth entry 仍不得整頁退化成 diagnostics dashboard |

## Mode Switching

| Concern | Required behavior |
|---|---|
| Entry condition | 只有 `Online Mode` 且 auth 尚未建立時，才進入 auth entry |
| Local escape hatch | auth entry 應允許使用者改切 `Local Mode`，而不是把使用者永久困在登入頁 |
| Online re-entry | auth entry 應允許使用者重新指定 `IP:Port` / target，或重試目前 target |
| Post-login handoff | online mode 登入成功後，回到 shell 並重建 online session context |
| Post-switch handoff | 切回 local mode 後，直接建立 local session 並離開 auth entry |

## Connection Failure Presentation

| Situation | Required behavior |
|---|---|
| target connecting | 顯示明確的 connecting / validating spinner 與 concise status |
| target rejected | 顯示 concise failure summary，並提供 `Retry`、`Edit Server Target`、`Switch to Local Mode` |
| target detail | `IP:Port` / target label 可顯示為 secondary context，不應壓過 primary recovery action |
| degraded transport | 可保留 compact debug ref 或 disclosure；`Developer Mode = On` 時可在出錯區塊直接顯示 raw technical detail |

## Layout Baseline

| Concern | Rule |
|---|---|
| Primary layout | 單一主 card 或明確主次分層，不可出現左右兩欄同級大診斷卡 |
| Status placement | 靠近 primary action，保持 concise |
| Error detail | summary 先出現，長 detail 收在 disclosure |
| Logged-in handoff | 若 session 已恢復或已登入，應 hand off 回 shell / target route，而非停留在 auth entry 上堆更多資訊 |

## User-Facing Copy Baseline

| Prefer | Avoid |
|---|---|
| `Sign in`, `Continue`, `Session expired`, `Try again` | `Auth State`, `Workspace`, `Session Mode` 當作大標題 |
| concise recovery hint | 長段 diagnostics narrative |
| action-first labels | debug-first section labels |

## App Pair

| Concern | Authority |
|---|---|
| auth state summary | [Backend / Session & Workspace](../../backend/session-workspace.md) |
| invite continuation / degraded semantics | [App / Shared / Authentication & Authorization](../../shared/authentication-and-authorization.md) |
| runtime mode boundary | [App / Shared / Runtime Modes](../../shared/runtime-modes.md) |
| shell handoff after auth | [Header](header.md) |

## Related

- [Header](header.md)
- [Authentication & Authorization](../../shared/authentication-and-authorization.md)
- [Backend / Session & Workspace](../../backend/session-workspace.md)
