---
aliases:
- App Reference
- UI Reference
- 介面參考
- Frontend Reference
tags:
- diataxis/reference
- audience/team
- sot/true
- topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Frontend app reference 索引，涵蓋 shared shell、shared workflow、workspace、definition 與 research workflow surfaces
version: v0.16.0
last_updated: 2026-03-16
updated_by: codex
---

# Frontend Reference

本區收錄 frontend app layer 的可查詢規格，涵蓋 shared shell、shared workflow、workspace、definition 與 research workflow surfaces。

!!! info "How To Read Frontend App Docs"
    先讀 shared surfaces 了解 global context 與 shared workflow，再讀各 page specs。
    若你要問的是 layout、control action、權限或 result handoff，先確認它是不是 shared surface，而不是直接埋在單頁裡。

!!! warning "IA Groups Are Not Pages"
    `Shared Shell`、`Shared Workflow`、`Workspace`、`Definition`、`Research Workflow` 是資訊架構分組，不是可點的實作頁。
    本頁只列真正存在的 frontend reference pages。

## Page Map

=== "Shared Shell"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Header](shared-shell/header.md) | single-line shell identity、compact global context triggers、right-side shell panel、worker summary、user menu | [App / Shared / Identity & Workspace Model](../shared/identity-workspace-model.md), [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
    | [Sidebar](shared-shell/sidebar.md) | navigation-only sidebar、strict group labels、responsive shell behavior | [Backend / Session & Workspace](../backend/session-workspace.md) |
    | [Auth Entry](shared-shell/auth-entry.md) | login / logout / recovery entry、concise auth status、secondary diagnostics disclosure | [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [Backend / Session & Workspace](../backend/session-workspace.md) |

=== "Shared Workflow"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Task Management](shared-workflow/task-management.md) | right-side shell-panel queue、attach、cancel、terminate、retry、refresh recovery | [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md), [App / Shared / Audit Logging](../shared/audit-logging.md) |

=== "Workspace"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Dashboard](workspace/dashboard.md) | active dataset、dataset metadata、tagged core metrics summary | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md), [Backend / Characterization Results](../backend/characterization-results.md) |
    | [Raw Data Browser](workspace/raw-data-browser.md) | design list、trace preview、compare readiness、summary-only browse | [Backend / Datasets & Results](../backend/datasets-results.md) |

=== "Definition"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Schemas](definition/schemas.md) | circuit schema catalog、search、sort、cursor-based browse | [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Schema Editor](definition/schema-editor.md) | canonical source editing、auto-format、persisted validation、quick reference hints | [Backend / Circuit Definitions](../backend/circuit-definitions.md) |

=== "Research Workflow"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Schemdraw](research-workflow/schemdraw.md) | linked schema context、source editor、SVG live preview、backend-owned diagnostics/render | [Backend / Schemdraw Render](../backend/schemdraw-render.md), [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Circuit Simulation](research-workflow/circuit-simulation.md) | definition-bound run setup、task attach、result handoff、shared queue | [Backend / Circuit Definitions](../backend/circuit-definitions.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Characterization](research-workflow/characterization.md) | design scope、run analysis、task attach、run history、result view | [Backend / Datasets & Results](../backend/datasets-results.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [Backend / Characterization Results](../backend/characterization-results.md) |

## Surface Pairing

| Question | Frontend surface | Authority |
|---|---|---|
| 哪裡切換 active workspace、active dataset、打開 task queue、看 worker 狀態、開 user menu？ | [Header](shared-shell/header.md) | [Identity & Workspace Model](../shared/identity-workspace-model.md), [Session & Workspace](../backend/session-workspace.md), [Tasks & Execution](../backend/tasks-execution.md), [Authentication & Authorization](../shared/authentication-and-authorization.md), [Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
| 哪裡定義登入 / 登出 / 恢復入口的產品密度，而不是診斷頁？ | [Auth Entry](shared-shell/auth-entry.md) | [Authentication & Authorization](../shared/authentication-and-authorization.md), [Session & Workspace](../backend/session-workspace.md) |
| 哪裡看 shared task queue 與管理 actions？ | [Task Management](shared-workflow/task-management.md) | [Tasks & Execution](../backend/tasks-execution.md), [Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md), [Authentication & Authorization](../shared/authentication-and-authorization.md), [Task Runtime & Processors](../shared/task-runtime-and-processors.md), [Audit Logging](../shared/audit-logging.md) |
| 哪裡編輯 schema 並取得可讀 hints？ | [Schema Editor](definition/schema-editor.md) | [Circuit Definitions](../backend/circuit-definitions.md), [Circuit Netlist](../../data-formats/circuit-netlist.md) |
| 哪裡做 schemdraw live preview？ | [Schemdraw](research-workflow/schemdraw.md) | [Schemdraw Render](../backend/schemdraw-render.md) |

!!! success "Coverage Rule"
    每個 frontend workflow 都必須能在 backend 或 app-shared reference 找到 authority。
    如果 page spec 需要靠猜測補齊 queue、auth、runtime 或 audit，代表 SoT 還不完整。

## Related

* [Backend Reference](../backend/index.md)
* [Shared App Model](../shared/index.md)
* [Architecture Reference](../../architecture/index.md)
