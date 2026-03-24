---
aliases:
  - "Parity Matrix"
  - "架構對齊矩陣"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/architecture
status: stable
owner: docs-team
audience: team
scope: 目前 App / CLI / Core / Data Formats 的 cross-layer 對齊矩陣
version: v0.9.0
last_updated: 2026-03-24
updated_by: codex
---

# Parity Matrix

本頁記錄目前主要 workflows 在 `App / CLI / Core / Data Formats` 之間的對齊狀態。

## Status Legend

| Status | Meaning |
|---|---|
| `aligned` | owner 與主要 consumers 已對齊，文件與 primary surfaces 一致 |
| `partial` | 主要 authority 已明確，但仍有 shared surface 或 control depth 尚未完全拉齊 |
| `defined` | SoT 已定義，但 implementation / consumer adoption 尚未全面對齊 |
| `gap` | 目前仍缺少足夠的 cross-layer architecture 定義 |

## Matrix

| Concern | Frontend or CLI surface | App / Core / Data Formats authority | Current state | Note |
|---|---|---|---|---|
| App runtime modes | [Header](../app/frontend/shared-shell/header.md), [Auth Entry](../app/frontend/shared-shell/auth-entry.md) | [Runtime Modes](../app/shared/runtime-modes.md), [Session & Workspace](../app/backend/session-workspace.md), [Authentication & Authorization](../app/shared/authentication-and-authorization.md) | `defined` | same-app local / online model 已定義； implementation adoption 仍待跟上 |
| App shell context | [Header](../app/frontend/shared-shell/header.md), [Sidebar](../app/frontend/shared-shell/sidebar.md) | [Runtime Modes](../app/shared/runtime-modes.md), [Session & Workspace](../app/backend/session-workspace.md), [Authentication & Authorization](../app/shared/authentication-and-authorization.md) | `partial` | active workspace、dataset、mode switch 與 user menu 已定義；實作 adoption 仍待收斂 |
| Workspace-scoped resource model | Header, workspace pages, task management | [Resource Ownership & Visibility](../app/shared/resource-ownership-and-visibility.md), [Identity & Workspace Model](../app/shared/identity-workspace-model.md), [Session & Workspace](../app/backend/session-workspace.md) | `partial` | multi-workspace membership + single active workspace 已定義；dataset/design adoption 剛收斂到 dataset-first |
| Multi-user auth | Header, Auth Entry, Task Management | [Runtime Modes](../app/shared/runtime-modes.md), [Authentication & Authorization](../app/shared/authentication-and-authorization.md), [Identity & Workspace Model](../app/shared/identity-workspace-model.md), [Session & Workspace](../app/backend/session-workspace.md) | `partial` | online-only auth / capability / invitation lifecycle 已定義； transport adoption 仍待實作 |
| Shared task management | [Task Management](../app/frontend/shared-workflow/task-management.md) | [Tasks & Execution](../app/backend/tasks-execution.md), [Task Runtime & Processors](../app/shared/task-runtime-and-processors.md) | `partial` | queue / control / runtime state machine 已定義； implementation 仍待 adoption |
| Simulation workflow | [Circuit Simulation](../app/frontend/research-workflow/circuit-simulation.md) | [Tasks & Execution](../app/backend/tasks-execution.md), [Circuit Definitions](../app/backend/circuit-definitions.md) | `partial` | queue 與 attach 已收斂； simulation-specific runtime/result depth 仍待細化 |
| Characterization workflow | [Characterization](../app/frontend/research-workflow/characterization.md) | [Tasks & Execution](../app/backend/tasks-execution.md), [Characterization Results](../app/backend/characterization-results.md) | `partial` | run history 與 shared queue distinction 已定義 |
| Circuit definition workflow | [Schemas](../app/frontend/definition/schemas.md), [Schema Editor](../app/frontend/definition/schema-editor.md) | [Circuit Definitions](../app/backend/circuit-definitions.md), [Circuit Netlist](../data-formats/circuit-netlist.md) | `partial` | UUIDv4-only opaque schema identity、same-name disambiguation 與 cross-page binding 已定義； backend metadata DB 已改由 Alembic migration 管理 schema identity cutover，但 remaining consumer / local-state adoption 仍需持續收斂 |
| Schema identity across linked flows | [Schemas](../app/frontend/definition/schemas.md), [Schema Editor](../app/frontend/definition/schema-editor.md), [Schemdraw](../app/frontend/research-workflow/schemdraw.md), [Circuit Simulation](../app/frontend/research-workflow/circuit-simulation.md) | [Circuit Definitions](../app/backend/circuit-definitions.md), [Tasks & Execution](../app/backend/tasks-execution.md), [Identity & Workspace Model](../app/shared/identity-workspace-model.md) | `defined` | `definition_id` 現為 UUIDv4-only opaque identity；UI 只能顯示 short `Schema ID`，不可再用 numeric `Definition #` model |
| Schemdraw live render | [Schemdraw](../app/frontend/research-workflow/schemdraw.md) | [Schemdraw Render](../app/backend/schemdraw-render.md) | `defined` | three-step flow 與 backend authority 已定義 |
| Worker / processor runtime | Header queue worker summary | [Task Runtime & Processors](../app/shared/task-runtime-and-processors.md) | `defined` | processor summary、cancel/terminate semantics 已寫清楚 |
| Audit logging | queue controls, privileged actions, admin governance | [Audit Logging](../app/shared/audit-logging.md), [Audit Logs](../app/backend/audit-logs.md) | `partial` | separate audit store 與 read surface 已定義； governance UI adoption 仍待完成 |
| Dataset / Design / Trace model | Dashboard, Raw Data Browser, Characterization, CLI datasets | [Dataset / Design / Trace Schema](../data-formats/dataset-record.md), [Datasets & Results](../app/backend/datasets-results.md) | `partial` | dataset-first + dataset-local design scope 已定義； persistence code adoption 尚未完成 |
| Standalone CLI runtime | [CLI / Standalone Runtime](../cli/standalone-runtime.md), [sc session](../cli/sc-session.md), [sc tasks](../cli/sc-tasks.md) | [CLI Options](../cli/index.md), [Core / Python Core](../core/python-core.md), [Data Formats](../data-formats/index.md) | `partial` | local context、local run registry 已定義； interchange 與 implementation adoption 仍待完成 |
| CLI / App interchange | [CLI / Local / App Interchange](../cli/local-app-interchange.md) | [Local / App Interchange](../cli/local-app-interchange.md), [Resource Ownership & Visibility](../app/shared/resource-ownership-and-visibility.md) | `defined` | import/export/copy-with-lineage 邊界已定義；不做 live sync |

!!! warning "How To Use This Matrix"
    `defined` 表示文件 SoT 已成立，不代表實作已完成。
    若你要把工作交給實作者，應優先挑 `partial` 或 `defined` 並補最後一層 endpoint / payload 或 adoption 細節。

## Related

* [Architecture Reference](index.md)
* [Canonical Contract Registry](canonical-contract-registry.md)
* [App / Shared](../app/shared/index.md)
