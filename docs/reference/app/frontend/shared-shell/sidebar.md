---
title: "Sidebar"
aliases:
  - "Frontend Sidebar"
  - "Unified Sidebar"
  - "App Sidebar"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
status: draft
owner: docs-team
audience: team
scope: Frontend shared sidebar 的導航、route grouping 與 responsive shell contract
version: v0.5.0
last_updated: 2026-03-16
updated_by: codex
---

# Sidebar

本頁定義 frontend shared sidebar 的正式契約。它是 app shell 的 navigation-only surface。

!!! info "Surface Boundary"
    Sidebar 負責全域導航、route grouping 與 responsive shell entry。
    active dataset、tasks queue 與 user settings 不屬於 Sidebar。

!!! warning "Navigation Is Not Page Logic"
    Sidebar 只決定「如何在 app surfaces 之間移動」。
    它不得承擔 page body 內的 workflow 邏輯，也不得重複 page-local controls。

!!! warning "Navigation-Only Sidebar"
    本產品的 Sidebar 應收斂成 navigation-only surface。
    它只允許 group labels、nav item title、icon 與 active state；
    shell identity、brand helper text、explanatory copy、item summary、group description、onboarding CTA 與 intro card 都不屬於 Sidebar。

## Sidebar Composition

| Area | Responsibility |
|---|---|
| Navigation Groups | 以穩定資訊架構列出 app pages |
| Collapse Control | 在窄螢幕下提供展開 / 收合行為 |

## Density Contract

| Sidebar element | Allowed | Notes |
|---|---|---|
| Shell identity / app title | no | 只允許 Header 顯示 shell identity |
| Brand helper text / monogram | no | 不得顯示 `SC`、`Navigation`、`Workspace routes` 等 shell copy |
| Group label | yes | 只作 IA grouping |
| Nav item icon | yes | 幫助快速掃讀 |
| Nav item title | yes | 作為主要 navigation label |
| Active highlight | yes | 必須清楚顯示目前 route |
| Group description | no | 移到 page body、overview 頁或 onboarding surface |
| Item summary / subtitle | no | 不應佔用持久導航密度 |
| Intro paragraph / explanatory copy | no | 不應放在 shared sidebar |
| CTA card / onboarding card | no | 應移到 dashboard、empty state 或 dedicated onboarding surface |
| Global status / queue summary | no | 屬於 [Header](header.md) / shell context controls |

## Taxonomy Stability Rule

| Concern | Current SoT |
|---|---|
| `Dashboard` page | 目前仍是單一 canonical page，不得在 frontend implementation 中自行拆成 `Workspace` / `Session` 雙頁 |
| `DASHBOARD` group | 目前仍是 top-level nav group，不得未經 SoT 更新就改成其他 label 或改成 purely abstract container |
| `PIPELINE` overview | 若未新增正式 page spec，不得自行在 sidebar 補一個 pipeline overview route |
| Route / label changes | route naming、sidebar labels 與 group hierarchy 需要先更新 SoT，再進行 frontend implementation |

!!! warning "No silent IA rewrite in frontend"
    如果產品想把 `Dashboard` 改成群組容器，或新增 `Workspace` / `Session` dedicated pages，必須先更新 frontend reference 與相關 page specs。
    不得由 sidebar implementation 先行改名、補頁或變更 route taxonomy。

## Group Label Contract

| Allowed label | Meaning |
|---|---|
| `DASHBOARD` | app 主入口群組 |
| `PIPELINE` | dataset-driven workflow 群組 |
| `CIRCUIT SIMULATION` | definition-driven workflow 群組 |

!!! tip "No helper copy in the sidebar"
    若使用者需要理解群組用途，應透過 page body、overview page、empty state 或 onboarding surface 引導。
    不要把持久導航變成一個需要閱讀段落說明的資訊牆。

## Navigation Contract

=== "Top-level Groups"

    | Group | Purpose |
    |---|---|
    | `DASHBOARD` | app 主入口與總覽 |
    | `PIPELINE` | dataset-driven workflow：Dashboard、Raw Data、Characterization |
    | `CIRCUIT SIMULATION` | definition-driven workflow：Schemas、Simulation、Schemdraw |

=== "Required Behaviors"

| Behavior | Meaning |
|---|---|
| Active route highlight | 目前 route 必須在 Sidebar 中有清楚的 active 狀態 |
| Stable entry points | 主要頁面不得只靠 page-internal links 才能抵達 |
| Responsive collapse | 窄螢幕可收合，但不可丟失 active route 與導覽分組 |
| Dense-but-quiet presentation | 側欄是持久導航，不應承擔教育文案或管理面板 |

## Collapse Toggle Contract

| Concern | Required behavior |
|---|---|
| Pointer affordance | toggle button 必須顯示 pointer cursor |
| Hover state | 必須有清楚但克制的 hover feedback |
| Focus-visible state | keyboard navigation 時必須有可見 focus ring / outline |
| Meaning | toggle 只負責展開 / 收合 sidebar，不承擔 global context 或 account management |

!!! tip "Sidebar vs Header"
    Sidebar 負責持久導航。
    [Header](header.md) 負責 `Active Workspace`、`Active Dataset`、`Tasks Queue`、worker status 與 user menu 的 compact entry points。

## Primary Consumers

| Consumer | Why it depends on Sidebar |
|---|---|
| [Dashboard](../workspace/dashboard.md) | 共享 pipeline 導覽入口 |
| [Raw Data Browser](../workspace/raw-data-browser.md) | 共享 design browse 導覽入口 |
| [Schemas](../definition/schemas.md) | 共享 definition workflow entry |
| [Schema Editor](../definition/schema-editor.md) | 共享 catalog-to-editor navigation |
| [Schemdraw](../research-workflow/schemdraw.md) | 共享 research workflow shell |
| [Circuit Simulation](../research-workflow/circuit-simulation.md) | 共享 task-driven workflow shell |
| [Characterization](../research-workflow/characterization.md) | 共享 task-driven workflow shell |

## Related

- [Header](header.md)
- [Frontend Reference](../index.md)
