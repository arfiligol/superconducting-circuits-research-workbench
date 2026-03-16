---
aliases:
  - Backend App Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Backend app reference 索引，收錄 frontend 與 app-shared model 依賴的 runtime-mode-aware backend authority surfaces
version: v0.9.0
last_updated: 2026-03-16
updated_by: codex
---

# Backend Reference

本區收錄 backend app layer 的可查詢規格，描述 frontend 與 app-shared model 對齊時所依賴的 authority surfaces。

!!! info "How To Read Backend App Docs"
    先看 `Foundation` 找資料與身份 authority，再看 `Workflow` 找 execution、render、analysis result surfaces。
    workspace collaboration、auth、worker runtime 與 audit logging 等跨頁規則，則由 [Shared App Model](../shared/index.md) 定義。

!!! tip "Read With Frontend And Shared App Model"
    Backend reference 定義 app surface，不負責頁面 layout，也不重複定義 shared collaboration model。
    最穩定的閱讀方式是把本頁和 [Frontend Reference](../frontend/index.md) 與 [Shared App Model](../shared/index.md) 對照著看。

!!! info "Same backend surfaces across local and online modes"
    Local mode 與 online mode 優先共用同一套 backend authority surfaces。
    差異主要落在 `Session & Workspace`、`Authentication & Authorization` 與 collaboration semantics，而不是另做第二套 backend API family。

## Surface Map

=== "Foundation"

    | Surface | Primary consumers | Core focus |
    |---|---|---|
    | [Session & Workspace](session-workspace.md) | Header, Auth Entry, Dashboard, Raw Data Browser, Task Management | runtime mode、session、workspace、user summary、active dataset、capabilities |
    | [Circuit Definitions](circuit-definitions.md) | Schemas, Schema Editor, Schemdraw, Circuit Simulation | catalog、detail、mutation、persisted preview |
    | [Datasets & Results](datasets-results.md) | Header, Dashboard, Raw Data Browser, Characterization, Circuit Simulation | dataset catalog、dataset profile、design browse、trace preview、tagged metrics summary、result handles |
    | [Audit Logs](audit-logs.md) | governance surfaces, admin tools | audit query、detail、export summary |

=== "Workflow"

    | Surface | Primary consumers | Core focus |
    |---|---|---|
    | [Tasks & Execution](tasks-execution.md) | Header, Task Management, Circuit Simulation, Characterization | queue read model、control actions、task detail、events、result attachment |
    | [Schemdraw Render](schemdraw-render.md) | Schemdraw | snapshot render、diagnostics、SVG response |
    | [Characterization Results](characterization-results.md) | Characterization, Dashboard | run history、artifact manifest、identify/tagging |

## Shared Pairing

| Concern | Backend surface | Shared authority |
|---|---|---|
| runtime mode / auth boundary / user menu visibility | [Session & Workspace](session-workspace.md) | [Runtime Modes](../shared/runtime-modes.md), [Authentication & Authorization](../shared/authentication-and-authorization.md) |
| queue actions / worker summary / lifecycle control | [Tasks & Execution](tasks-execution.md) | [Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
| privileged task controls / audit trail | [Tasks & Execution](tasks-execution.md) | [Audit Logging](../shared/audit-logging.md) |
| audit read model / governance query | [Audit Logs](audit-logs.md) | [Audit Logging](../shared/audit-logging.md) |
| resource visibility / workspace binding | [Session & Workspace](session-workspace.md), [Tasks & Execution](tasks-execution.md) | [Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md) |

## Related

* [Frontend Reference](../frontend/index.md)
* [Shared App Model](../shared/index.md)
* [Architecture Reference](../../architecture/index.md)
