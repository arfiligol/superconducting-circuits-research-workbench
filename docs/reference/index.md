---
aliases:
- Reference
- 技術參考
tags:
- diataxis/reference
- audience/team
- sot/true
- topic/documentation
status: draft
owner: docs-team
audience: team
scope: 技術規格索引，涵蓋 architecture、app、notebooks、core、data formats 與開發規範
version: v0.6.0
last_updated: 2026-03-14
updated_by: team
---

# Reference

本區是平台的規格表。

凡是寫在 `Reference` 的定義，都是 notebooks、application、backend、Julia Runner 與核心能力需要對齊的 SoT。

!!! info "How to read Reference"
    先看 `Architecture`、`App`、`Notebooks`、`Core`、`Data Formats` 這些 owner layer，再用 `Guardrails` 確認開發流程與寫作規範。

## Reading Map

| 如果你想確認 | 先看哪裡 |
| --- | --- |
| App 的 shell、page、backend authority | `Application Interface`、`App / Shared / Frontend / Backend` |
| Notebook workflow 與直接研究執行 | `Notebook Interface` |
| Julia Runner compute plane | `Julia Runner Compute Plane` |
| 核心科學模組與 Julia/Python 邊界 | `Core` |
| persisted payload 與 canonical record schema | `Data Formats` |
| 哪個 contract 由誰擁有 | `Architecture Reference` |
| 開發與文件規範 | `Guardrails` |

## Categories

| 類別 | 核心聚焦 |
|---|---|
| [Architecture Reference](architecture/index.md) | cross-layer registry、owner boundary 與 parity 對齊 |
| [Julia Runner Compute Plane](architecture/julia-runner-compute-plane.md) | async compute plane、Runner API 與 task execution boundary |
| [Runner Result Manifest](architecture/runner-result-manifest.md) | staged result manifest schema 與 Backend validation |
| [TraceStore Zarr](architecture/trace-store-zarr.md) | canonical local Zarr publication contract |
| [Application Interface](app/application-interface.md) | Electron data workbench surface |
| [Notebook Interface](notebooks/index.md) | Pluto / Python notebook roles |
| [App / Shared](app/shared/index.md) | workspace collaboration、auth、task runtime、audit logging 等 app-shared semantics |
| [App / Frontend](app/frontend/index.md) | shared shell、definition pages、research workflows |
| [App / Backend](app/backend/index.md) | frontend 與 shared app model 依賴的 backend authority surfaces |
| [Core](core/index.md) | Python core、Julia wrapper、Julia core 與 Julia plotting |
| [Data Formats](data-formats/index.md) | 數據格式、record schema 與 canonical payload rules |
| [Guardrails](guardrails/index.md) | workspace 開發規範、文件規範與執行驗證規則 |
| [Contributors](contributors.md) | 貢獻者名錄與文件引用依據 |

!!! tip "Owner-first rule"
    若兩頁看起來都在談同一件事，優先回到真正擁有該 contract 的 layer，而不是先相信較靠近 consumer 的說明頁。

## Related

- [Explanation](../explanation/index.md) - 核心概念
- [How-to Guides](../how-to/index.md) - 操作指南
