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
scope: Frontend app reference 索引，涵蓋 shared shell、shared workflow、workspace 與 research workflow surfaces
version: v0.23.1
last_updated: 2026-03-25
updated_by: codex
---

# Frontend Reference

本區收錄 frontend app layer 的可查詢規格，涵蓋 shared shell、shared workflow、workspace 與 research workflow surfaces。

!!! info "How To Read Frontend App Docs"
    先讀 shared surfaces 了解 global context 與 shared workflow，再讀各 page specs。
    若你要問的是 layout、control action、權限或 result handoff，先確認它是不是 shared surface，而不是直接埋在單頁裡。

!!! warning "IA Groups Are Not Pages"
    `Shared Shell`、`Shared Workflow`、`Workspace`、`Definition`、`Research Workflow` 是資訊架構分組，不是可點的實作頁。
    本頁只列真正存在的 frontend reference pages。

!!! warning "Do Not Rewrite Sidebar Taxonomy In Implementation"
    目前 frontend 的可見 sidebar groups 為 `Dashboard`、`Pipeline`、`Circuit Simulation`。
    其中 `Dashboard` 承擔 workspace-level overview / operations 語意，並包含 standalone `Tasks` entry。
    若產品要新增 `Session`，或替 `Pipeline` 新增 overview route，必須先更新 SoT，再改 frontend implementation。

!!! warning "Anti-overbuild baseline"
    frontend page specs 除了定義功能，也要定義禁止條件。
    duplicated shell context、cross-page CTA walls、authority summary cards 與 handoff explanation，不應因為「看起來完整」就被塞回 page body。

## Sidebar Section Meanings

| Section | Meaning | Current baseline |
|---|---|---|
| `Dashboard` | workspace-level overview / operations / cross-workflow context | 目前由 `/dashboard` 作為 canonical landing page，並包含 `Dataset`、`Tasks` entry |
| `Pipeline` | data-analysis flow；item order 具有 UX 引導含義 | 放 `Data Ingestion`、`Raw Data`、`Characterization` 等流程節點，不放 system / task infra management page |
| `CIRCUIT SIMULATION` | definition-driven modeling / simulation flow | 放 schema、schemdraw、simulation 等建模工作頁 |

## Page Map

=== "Shared Shell"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Header](shared-shell/header.md) | single-line shell identity、runtime mode switch、summary-first global context panel、lightweight account surface、developer mode、right-side shell panel | [App / Shared / Runtime Modes](../shared/runtime-modes.md), [App / Shared / Identity & Workspace Model](../shared/identity-workspace-model.md), [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
    | [Sidebar](shared-shell/sidebar.md) | navigation-only sidebar、strict group labels、responsive shell behavior | [Backend / Session & Workspace](../backend/session-workspace.md) |
    | [Auth Entry](shared-shell/auth-entry.md) | online-mode login / logout / recovery entry、concise auth status、secondary diagnostics disclosure、developer-mode-aware debug detail | [App / Shared / Runtime Modes](../shared/runtime-modes.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [Backend / Session & Workspace](../backend/session-workspace.md) |

=== "Shared Workflow"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Task Management](shared-workflow/task-management.md) | runtime-mode-aware `Global Context` queue section、attach、cancel、terminate、retry、refresh recovery | [App / Shared / Runtime Modes](../shared/runtime-modes.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md), [App / Shared / Audit Logging](../shared/audit-logging.md) |

=== "Workspace / Pipeline Pages"

    | Page | Sidebar group | Core focus | Authority pair |
    |---|---|---|---|
    | [Dashboard](workspace/dashboard.md) | `Dashboard` | summary-first landing page；目前 dataset context、tagged core metrics 與 dedicated page entry points | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md), [Backend / Characterization Results](../backend/characterization-results.md) |
    | [Dataset](workspace/dataset.md) | `Dashboard` | visible dataset catalog、active dataset switch、profile edit、lifecycle actions | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Tasks](workspace/tasks.md) | `Dashboard` | standalone queue browse、worker inspection、history、task detail、control actions | [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md) |
    | [Data Ingestion](workspace/data-ingestion.md) | `Pipeline` | upload-first raw-data intake、validation、preprocess、import handoff | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Raw Data Browser](workspace/raw-data-browser.md) | `Pipeline` | design list、trace summary CRUD、single-trace preview、batch delete | [Backend / Datasets & Results](../backend/datasets-results.md) |

=== "Definition"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Schemas](definition/schemas.md) | circuit schema catalog、search、sort、cursor-based browse | [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Schema Editor](definition/schema-editor.md) | canonical source editing、auto-format、persisted validation、quick reference hints | [Backend / Circuit Definitions](../backend/circuit-definitions.md) |

=== "Research Workflow"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Schemdraw](research-workflow/schemdraw.md) | linked schema context、source editor、SVG live preview、backend-owned diagnostics/render | [Backend / Schemdraw Render](../backend/schemdraw-render.md), [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Circuit Simulation](research-workflow/circuit-simulation.md) | pipeline-first simulation workflow、stage-local run state、simulation result、post-processing result | [Backend / Circuit Definitions](../backend/circuit-definitions.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Characterization](research-workflow/characterization.md) | design scope、run analysis、latest run summary、run history、result view | [Backend / Datasets & Results](../backend/datasets-results.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [Backend / Characterization Results](../backend/characterization-results.md) |

## Surface Pairing

| Question | Frontend surface | Authority |
|---|---|---|
| 哪裡定義同一個 App 的 local / online mode 與 mode switch？ | [Header](shared-shell/header.md), [Auth Entry](shared-shell/auth-entry.md) | [Runtime Modes](../shared/runtime-modes.md), [Session & Workspace](../backend/session-workspace.md) |
| 哪裡切換 active workspace、active dataset、打開 task queue、看 worker 狀態、開 user menu？ | [Header](shared-shell/header.md) | [Identity & Workspace Model](../shared/identity-workspace-model.md), [Session & Workspace](../backend/session-workspace.md), [Tasks & Execution](../backend/tasks-execution.md), [Authentication & Authorization](../shared/authentication-and-authorization.md), [Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
| 哪裡定義登入 / 登出 / 恢復入口的產品密度，而不是診斷頁？ | [Auth Entry](shared-shell/auth-entry.md) | [Authentication & Authorization](../shared/authentication-and-authorization.md), [Session & Workspace](../backend/session-workspace.md) |
| 哪裡看 shared task queue 與管理 actions？ | [Task Management](shared-workflow/task-management.md) | [Tasks & Execution](../backend/tasks-execution.md), [Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md), [Authentication & Authorization](../shared/authentication-and-authorization.md), [Task Runtime & Processors](../shared/task-runtime-and-processors.md), [Audit Logging](../shared/audit-logging.md) |
| 哪裡看 extended queue history、deeper filters、task detail 與較完整 worker inspection？ | [Tasks](workspace/tasks.md) | [Tasks & Execution](../backend/tasks-execution.md), [Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
| 哪裡編輯 schema 並取得可讀 hints？ | [Schema Editor](definition/schema-editor.md) | [Circuit Definitions](../backend/circuit-definitions.md), [Circuit Netlist](../../data-formats/circuit-netlist.md) |
| 哪裡做 schemdraw live preview？ | [Schemdraw](research-workflow/schemdraw.md) | [Schemdraw Render](../backend/schemdraw-render.md) |

!!! success "Coverage Rule"
    每個 frontend workflow 都必須能在 backend 或 app-shared reference 找到 authority。
    如果 page spec 需要靠猜測補齊 queue、auth、runtime 或 audit，代表 SoT 還不完整。

## Related

* [Backend Reference](../backend/index.md)
* [Shared App Model](../shared/index.md)
* [Architecture Reference](../../architecture/index.md)
