---
aliases:
  - Project Overview
  - 專案概述
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/project-basics
status: stable
owner: docs-team
audience: contributor
scope: 定義 current platform 的 Notebook、Application、Julia Runner 與 TraceStore 產品邊界。
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Project Overview

本專案不再把 NiceGUI、CLI、Redis/RQ worker 或 Python-in-process Julia execution 視為主要產品落點。
當前 branch 的目標是把既有需求重構為 **Notebook Interface + Electron Application Interface + Julia Runner Compute Plane**。

!!! info "How to read this page"
    先用這頁確認產品使命與核心 surface，再去看 `Tech Stack`、`Folder Structure`、`Backend Architecture` 等執行層 guardrails。這頁定的是產品邊界，不是實作細節。

!!! important "Current development mode"
    現階段是 **Heavy Development / No Compatible Fallback**。
    專案已撤出「需要維持相容 fallback」的發佈準備階段；現在首要目標是把 current product 打穩，確保下一次真正部署上線時功能足夠充分且穩定。
    後續 agent 應優先收斂 canonical product path，不要主動補 legacy compatibility path。
    既有底層 migration、runtime 或 rebuild 機制可以先保留；只有在它們阻礙產品穩定或 owner SoT 要求時，才需要刪除或重寫。

## Overview Map

| 區塊 | 回答的問題 |
| --- | --- |
| Mission | 這個產品在解什麼問題 |
| Product Goals | 這次 rewrite 真正要交付什麼 |
| Research Workflow Goals | 研究流程如何在 Notebook 與 Application 之間分工 |
| System Success Criteria | 什麼狀態才算 rewrite 成功 |

## Mission

建立一個讓研究者能用清楚分層完成下列工作的超導電路平台：

- Data Browser
- Dataset / Trace / Result Browser
- Async Task Monitor
- Notebook research cockpit
- Julia simulation and analysis runner
- TraceStore-backed numeric result management

## Product Goals

本產品的核心目標不是單純重寫 UI，而是建立一個可維護、可擴張、可追蹤的超導電路研究工作平台。

- Python Backend 是 control plane + data plane，負責 task lifecycle、metadata、publication、provenance、TraceStore registration 與資料 API
- Julia Runner 是 compute plane，負責 simulation、parameter sweep、post-processing、analysis、fitting、derived parameter extraction 與 result package generation
- Electron Application 是 productized data workbench，聚焦 dataset、ingestion、trace browsing、task/result browsing
- Pluto Notebook 是 research cockpit，可直接執行 Julia Core，也可選擇提交 async task
- CLI 不再是產品 surface；repo 僅保留 `scripts/` 作為 dev/build/test/maintenance helpers

## Research Workflow Goals

本專案必須支援下列研究工作流，而不是只提供零散工具：

- 在 Pluto 中直接使用 Julia Core 進行研究式模擬與分析
- 從 Application 或 Notebook 提交 async Julia Runner task
- 管理 dataset / design / trace / task / result / provenance
- 讓 Runner staging result 經 Python Backend 驗證後 publish 成正式 TraceStore batch
- 讓結果可被保存、追溯、重新 attach、重新分析與比較

## Data And Provenance Goals

本專案的資料面目標是把 metadata、trace payload 與結果關聯清楚切開，同時保持可重建性。

- metadata 由資料庫管理
- numeric payload 與 trace 由 Python Backend 管理的 TraceStore Zarr 管理
- Runner 只寫 local filesystem staging Zarr package，不寫正式 metadata DB
- 任一 simulation / post-process / analysis 結果都必須可追到 dataset、design、trace、task、batch 與 provenance
- frontend 不得成為 canonical computation state 的唯一持有者
- HTTP/JSON 不得傳輸大型 ND array；只傳 task control、status、manifest locator、summary 與 slice/detail API payload

## System Success Criteria

整體重構完成時，至少要同時成立：

- legacy NiceGUI、CLI、Redis/RQ worker 與 Python JuliaCall runtime 不再是 active product/runtime surfaces
- backend 可獨立提供 auth/session/workspace、dataset/design/trace metadata、task、TraceStore publication 與 frontend/notebook data API contracts
- Julia Core 成為 reusable circuit construction / simulation / analysis library
- Julia Runner 可執行 fake smoke task、寫 Zarr v2 staging result、寫 manifest 並回報 backend
- frontend 只保留 draft state / interaction state / view state，不保存 canonical computation state
- Electron 只作為 desktop shell，local mode 啟動 frontend、Python Backend 與 Julia Runner，不啟動 Redis
- task / dataset / result 可在 refresh、reconnect、重開後重新 attach 與重建

!!! success "Success bar"
    rewrite 的完成條件不是「畫面換成 Next.js」，而是 Python Backend publication、Julia Runner staging、TraceStore provenance、Notebook research cockpit 與 Electron data workbench 都能在同一套邊界下成立。

## Scope

### Core Product Surfaces

| 能力 | 說明 |
| --- | --- |
| Data Browser | 瀏覽 metadata、trace summary、analysis result 與 lineage |
| Dataset | 管理 dataset、design、metadata 與 provenance |
| Data Ingestion | 匯入 measurement/layout/simulation artifacts |
| Raw Data / Trace Browser | 瀏覽 TraceStore metadata、summary、slice 與 result lineage |
| Tasks / Result Browser | 提交、監控、檢視 async Runner task 與 publication result |
| Notebook Interface | Pluto / Python notebooks for research cockpit、inspection、migration、emergency analysis |

### Accepted Data Sources

- circuit simulation traces
- layout simulation traces（例如 HFSS / Q3D）
- measurement traces（例如 VNA）
- 相容的 S/Y/Z matrix traces 與其衍生分析結果

### Rewrite Direction

- UI：以 `app/frontend/` 的 **Next.js App Router** 為主
- API：以 `app/backend/` 的 **FastAPI** 為主
- Compute：以 `core/julia/SuperconductingCircuitsRunner/` 作為 async compute plane
- Core：以 `core/julia/SuperconductingCircuitsCore/` 作為 reusable Julia library
- Desktop：以 `app/desktop/` 的 **Electron** 包裝 frontend、backend、runner local mode
- Notebook：以 `notebooks/pluto/` 和 `notebooks/python/` 作為研究與 inspection cockpit
- Legacy：既有 NiceGUI、CLI、Redis/RQ、Python JuliaCall execution 只作 migration evidence，不再保留 active entrypoint

??? note "CLI position"
    CLI 已從 product surface 移除。需要 automation 的動作應放在 `scripts/dev/`、`scripts/build/`、`scripts/test/` 或 `scripts/maintenance/`，且不得被包裝成使用者工作流 contract。

## Target Audience

- 超導電路與量子硬體研究人員
- 需要整合 simulation / layout / measurement 的使用者
- 需要可重現 notebook workflow、async runner pipeline 與可擴充 Web UI 的開發者

## Agent Rule { #agent-rule }

```markdown
## Project Goal
- **Mission**: Build a superconducting-circuit workbench centered on Notebook Interface, Electron Application Interface, and Julia Runner Compute Plane.
- **Current development mode**: Heavy Development / No Compatible Fallback; prioritize stabilizing the current product for the next real deployment over preserving legacy compatibility paths.
- **Core product surfaces**:
    - Data Browser
    - Dataset
    - Data Ingestion
    - Raw Data / Trace Browser
    - Tasks / Result Browser
    - Notebook Interface
- **Data sources**:
    - circuit simulation
    - layout simulation
    - measurement
    - compatible S/Y/Z traces
- **Architecture direction**:
    - UI uses Next.js App Router
    - API uses FastAPI
    - Python Backend is the control plane + data plane
    - Julia Runner is the async compute plane
    - Electron is the local desktop shell around frontend, backend, and runner
    - Pluto is the direct Julia research cockpit
    - CLI, NiceGUI, Redis/RQ, and Python JuliaCall execution are no longer active product/runtime surfaces
- **Core values**:
    - scientific accuracy
    - reproducible workflows
    - explicit staging/publication boundary between Runner outputs and official TraceStore records
- **Product goals**:
    - support notebook research, application data browsing, async simulation/analysis, task tracking, and result recovery in one platform
    - keep metadata, trace payloads, Runner manifests, and provenance contracts explicit and reconstructible
    - ensure frontend holds draft/view state only, while canonical computation state stays in backend/core/storage contracts
    - remove active CLI/NiceGUI/Redis/RQ/Python-JuliaCall entrypoints instead of preserving compatibility fallbacks
- **Audience**: researchers, students, and developers working on superconducting-circuit simulation and analysis workflows.
```
