---
title: "Mode Feature Matrix"
aliases:
  - "Local Online Feature Matrix"
  - "Runtime Mode Feature Matrix"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: App `Local Mode` / `Online Mode` 下各 shared surfaces 與 workflow features 的 support matrix
version: v0.1.0
last_updated: 2026-03-16
updated_by: codex
---

# Mode Feature Matrix

本頁定義同一個 App 在 `Local Mode` 與 `Online Mode` 下，各主要 surface 的支援等級。

!!! info "Why this page exists"
    `Runtime Modes` 定義模式本身與切換規則。
    本頁則回答每一個 user-facing capability 在兩種 mode 下到底是 `full`、`reduced`、還是 `online-only`。

## Status Legend

| Status | Meaning |
|---|---|
| `full` | contract 與主要 UX 在該 mode 下完整成立 |
| `reduced` | surface 仍存在，但行為或資料模型被刻意縮減 |
| `online-only` | 只在 `Online Mode` 正式支援 |

## Shared Shell Matrix

| Concern | Local Mode | Online Mode | Notes |
|---|---|---|---|
| Header shell identity | `full` | `full` | 同一套 shell identity |
| Runtime mode switch | `full` | `full` | 可從 Header、Account、Auth Entry 進入 |
| Account drawer | `full` | `full` | local 顯示 local operator；online 顯示 authenticated account / sign-in state |
| Auth entry | `reduced` | `full` | local 只作 bypass / escape；online 才是 primary auth surface |
| Active workspace | `reduced` | `full` | local 固定為 `Local Space` |
| Active dataset | `full` | `full` | 兩邊都可切換，但資料來源不同 |
| Tasks queue | `full` | `full` | local queue 為 `Local Space`；online queue 為 workspace-visible shared tasks |
| Worker summary | `full` | `full` | local 看本地 processors；online 看 server-side processors |

## Workflow Matrix

| Workflow / feature | Local Mode | Online Mode | Notes |
|---|---|---|---|
| Dashboard | `full` | `full` | local 用本地 dataset / result authority |
| Raw Data Browser | `full` | `full` | local 不做 workspace visibility 分流 |
| Schemas / Schema Editor | `full` | `full` | local scope 為 `local`；online 可 `private / workspace` |
| Schemdraw | `full` | `full` | 仍走同一套 request / response assist surface |
| Circuit Simulation | `full` | `full` | local 跑本地 runtime；online 跑 shared server runtime |
| Characterization / Analysis | `full` | `full` | local / online 都保留分析能力 |

## Data And Collaboration Matrix

| Concern | Local Mode | Online Mode | Notes |
|---|---|---|---|
| Import / Upload | `full` | `full` | 兩邊都允許顯式 import / upload |
| Export / Download | `full` | `full` | 兩邊都允許顯式 export / download |
| Publish to workspace | `online-only` | `full` | local mode 無 share / publish 概念 |
| Workspace invitation / membership | `online-only` | `full` | local mode 不做 collaboration |
| Audit logging governance surface | `online-only` | `full` | local mode 不暴露 governance read model |
| Remote server target config | `online-only` | `full` | local mode 不需要 remote target |

## Task And Runtime Matrix

| Concern | Local Mode | Online Mode | Notes |
|---|---|---|---|
| Persisted task lifecycle | `full` | `full` | 同一套 task lifecycle vocabulary |
| Queue recovery after reconnect | `reduced` | `full` | local 只需本地 runtime recovery；online 需重抓 remote queue |
| Continue running after mode switch | `reduced` | `full` | local tasks 不跨到 online；online tasks 可在 server 繼續跑 |
| Continue running after app close | `reduced` | `full` | local app close 會終止 local tasks；online tasks 由 server 繼續管理 |

## Delivery Rules

| Rule | Meaning |
|---|---|
| No implicit bridge on mode switch | 切 mode 不等於把 local data 自動帶進 online，或反向帶回 |
| Same page does not mean same authority | UI surface 可以相同，但資料來源、capability 與 visibility semantics 依 mode 改變 |
| Reduced does not mean hidden by default | `reduced` surface 仍可存在，只是去掉不適用的 collaboration / governance depth |
| Online-only actions must disappear cleanly | local mode 不應顯示 publish、invite、membership、audit governance 等 action |

## Related

- [Runtime Modes](runtime-modes.md)
- [Identity & Workspace Model](identity-workspace-model.md)
- [Authentication & Authorization](authentication-and-authorization.md)
- [Resource Ownership & Visibility](resource-ownership-and-visibility.md)
