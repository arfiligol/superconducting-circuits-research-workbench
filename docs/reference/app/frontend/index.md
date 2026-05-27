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
version: v0.24.0
last_updated: 2026-05-27
updated_by: codex
---

# Frontend Reference

本區收錄 frontend app layer 的可查詢規格，涵蓋 shared shell、shared workflow、workspace 與 research workflow surfaces。

!!! info "How To Read Frontend App Docs"
    先讀 shared surfaces 了解 global context 與 shared workflow，再讀各 page specs。
    若你要問的是 layout、control action、權限或 result handoff，先確認它是不是 shared surface，而不是直接埋在單頁裡。

!!! warning "IA Groups Are Not Pages"
    `Shared Shell`、`Shared Workflow`、`Workspace`、`Research Workflow`、`Data Pipeline`、`Circuit Simulation` 是資訊架構分組，不是可點的實作頁。
    本頁只列真正存在的 frontend reference pages。

!!! warning "Do Not Rewrite Sidebar Taxonomy In Implementation"
    目前 frontend 的可見 sidebar groups 為 `Dashboard`、`Pipeline`、`Circuit Simulation`。
    其中 `Dashboard` 承擔 workspace-level overview / operations 語意，並包含 standalone `Tasks` entry。
    若產品要新增 `Session`，或替 `Pipeline` 新增 overview route，必須先更新 SoT，再改 frontend implementation。

!!! warning "Anti-overbuild baseline"
    frontend page specs 除了定義功能，也要定義禁止條件。
    duplicated shell context、cross-page CTA walls、authority summary cards 與 handoff explanation，不應因為「看起來完整」就被塞回 page body。

## Minimum Page Contract

所有 sidebar page 預設只顯示完成主任務所需的資訊。若資訊只是解釋系統權威、跨頁去向、debug 細節或 shell state，預設要移除或放進 disclosure。

| Page | Primary job | Default visible | Disclosure-only | Remove from default body |
|---|---|---|---|---|
| `/dashboard` | 看 workspace 當前狀態 | concise overview、必要 metrics | recent detail | active dataset/workspace cards、entry-card wall |
| `/dataset` | 選擇與管理 dataset | dataset list + selected detail | lifecycle history、raw metadata | shell context cards、tagged metrics duplicate |
| `/tasks` | extended task browse | queue table + selected task detail | event timeline、setup/result payload、worker lanes | cross-page handoff wall |
| `/data-ingestion` | 匯入 raw data | upload/drop area、validation summary、primary import action | per-file/per-trace detail、provenance detail | validation card wall |
| `/raw-data` | browse and preview traces | design/trace list、single preview、row actions | batch metadata、advanced edit payload | dataset/ingestion CTA wall |
| `/schemas` | browse circuit schemas | schema list、search/sort、primary create action | full metadata、delete/clone confirmations | tutorial/helper copy |
| `/circuit-definition-editor` | edit one schema | editor、validation state、save actions | quick reference、raw validation detail | persistent guidance panels |
| `/circuit-schemdraw` | edit source and preview SVG | linked schema selector、editor、preview、render/download | diagnostics、schema snapshot、advanced mapping | guidance card、AI/developer copy |
| `/circuit-simulation` | run simulation pipeline | current stage、submit/status、result surface | task detail、post-processing setup payload | submit-authority cards、queue dashboard |
| `/characterization` | run analysis and inspect result | design scope、selected analysis、latest result | run history、fit diagnostics、artifact payload | global queue/worker/detail walls |

!!! warning "Default-hidden by category"
    Product UI must not show `AI assistant` wording, backend authority explanations, handoff explanations, duplicated `Runtime Mode` / `Active Workspace` / `Active Dataset`, or diagnostics panels unless the user opened a relevant disclosure or an actual error needs concise recovery text.

## Sidebar Section Meanings

| Section | Meaning | Current baseline |
|---|---|---|
| `Dashboard` | workspace-level overview / operations / cross-workflow context | 目前由 `/dashboard` 作為 canonical landing page，並包含 `Dataset`、`Tasks` entry |
| `Pipeline` | data-analysis flow；item order 具有 UX 引導含義 | 放 `Data Ingestion`、`Raw Data`、`Characterization` 等流程節點，不放 system / task infra management page |
| `CIRCUIT SIMULATION` | definition-driven modeling / simulation flow | 放 schema、schemdraw、simulation 等建模工作頁 |

## Documentation IA Rule

frontend docs 的功能分組應盡量對齊產品可見的 sidebar taxonomy。

目前的整理原則是：

- `Workspace`：承接 workspace-level overview / operations surfaces
- `Research Workflow`：承接功能工作流
- `Research Workflow` 之下再以目前 sidebar 語言收斂成：
  - `Data Pipeline`
  - `Circuit Simulation`

!!! info "Docs IA can be slightly more compact than the visible sidebar"
    文件可以把可見 sidebar groups 收斂成更穩定的閱讀分組。
    但分組語意仍必須與 `Dashboard`、`Pipeline`、`Circuit Simulation` 這三個產品語言一致。

## Page Map

=== "Shared Shell"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Header](shared-shell/header.md) | single-line shell identity、compact global-context triggers、lightweight account surface、developer mode disclosure | [App / Shared / Runtime Modes](../shared/runtime-modes.md), [App / Shared / Identity & Workspace Model](../shared/identity-workspace-model.md), [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md) |
    | [Sidebar](shared-shell/sidebar.md) | navigation-only sidebar、strict group labels、responsive shell behavior | [Backend / Session & Workspace](../backend/session-workspace.md) |
    | [Auth Entry](shared-shell/auth-entry.md) | online-mode login / logout / recovery entry、concise auth status、secondary diagnostics disclosure、developer-mode-aware debug detail | [App / Shared / Runtime Modes](../shared/runtime-modes.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [Backend / Session & Workspace](../backend/session-workspace.md) |

=== "Shared Workflow"

    | Page | Core focus | Authority pair |
    |---|---|---|
    | [Task Management](shared-workflow/task-management.md) | compact queue trigger、task attach/control semantics、standalone `/tasks` boundary | [App / Shared / Runtime Modes](../shared/runtime-modes.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Resource Ownership & Visibility](../shared/resource-ownership-and-visibility.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md), [App / Shared / Audit Logging](../shared/audit-logging.md) |

=== "Workspace"

    | Page | Sidebar group | Core focus | Authority pair |
    |---|---|---|---|
    | [Dashboard](workspace/dashboard.md) | `Dashboard` | summary-first landing page with concise metrics only | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md), [Backend / Characterization Results](../backend/characterization-results.md) |
    | [Dataset](workspace/dataset.md) | `Dashboard` | visible dataset catalog、active dataset switch、profile edit、lifecycle actions | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Tasks](workspace/tasks.md) | `Dashboard` | standalone queue browse、worker inspection、history、task detail、control actions | [Backend / Tasks & Execution](../backend/tasks-execution.md), [App / Shared / Task Runtime & Processors](../shared/task-runtime-and-processors.md), [App / Shared / Authentication & Authorization](../shared/authentication-and-authorization.md) |

=== "Research Workflow / Data Pipeline"

    | Page | Sidebar group | Core focus | Authority pair |
    |---|---|---|---|
    | [Data Ingestion](workspace/data-ingestion.md) | `Pipeline` | upload-first raw-data intake、validation summary、import action | [Backend / Session & Workspace](../backend/session-workspace.md), [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Raw Data Browser](workspace/raw-data-browser.md) | `Pipeline` | design list、trace summary CRUD、single-trace preview、batch delete | [Backend / Datasets & Results](../backend/datasets-results.md) |
    | [Characterization](research-workflow/characterization.md) | `Pipeline` | design scope、selected analysis、latest result view | [Backend / Datasets & Results](../backend/datasets-results.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [Backend / Characterization Results](../backend/characterization-results.md) |

=== "Research Workflow / Circuit Simulation"

    | Page | Sidebar group | Core focus | Authority pair |
    |---|---|---|---|
    | [Schemas](definition/schemas.md) | `Circuit Simulation` | circuit schema catalog、search、sort、cursor-based browse | [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Schema Editor](definition/schema-editor.md) | `Circuit Simulation` | canonical source editing、auto-format、persisted validation | [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Schemdraw](research-workflow/schemdraw.md) | `Circuit Simulation` | linked schema context、source editor、SVG live preview、backend-owned diagnostics/render | [Backend / Schemdraw Render](../backend/schemdraw-render.md), [Backend / Circuit Definitions](../backend/circuit-definitions.md) |
    | [Circuit Simulation](research-workflow/circuit-simulation.md) | `Circuit Simulation` | pipeline-first simulation workflow、stage-local run state、simulation result、post-processing result | [Backend / Circuit Definitions](../backend/circuit-definitions.md), [Backend / Tasks & Execution](../backend/tasks-execution.md), [Backend / Datasets & Results](../backend/datasets-results.md) |

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
