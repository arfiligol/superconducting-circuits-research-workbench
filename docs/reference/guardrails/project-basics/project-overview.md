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
scope: 定義 rewrite branch 的產品使命、功能範疇、desktop 支援與 migration 方向。
version: v2.4.0
last_updated: 2026-03-25
updated_by: codex
---

# Project Overview

本專案不再把 NiceGUI 視為主要產品落點。
當前 branch 的目標是把既有需求重構為 **前後端分離的超導電路工作台**，同時保留 CLI 與科學計算核心，並支援本地 desktop runtime。

!!! info "How to read this page"
    先用這頁確認產品使命與核心 surface，再去看 `Tech Stack`、`Folder Structure`、`Backend Architecture` 等執行層 guardrails。這頁定的是產品邊界，不是實作細節。

## Overview Map

| 區塊 | 回答的問題 |
| --- | --- |
| Mission | 這個產品在解什麼問題 |
| Product Goals | 這次 rewrite 真正要交付什麼 |
| Research Workflow Goals | 研究流程要怎麼被整合成同一個產品 |
| System Success Criteria | 什麼狀態才算 rewrite 成功 |

## Mission

建立一個讓研究者能在同一套系統中完成下列工作的平台：

- Data Browser
- Circuit Definition Editor
- Circuit Schemdraw
- Circuit Simulation
- Characterization & Analysis
- CLI Available

## Product Goals

本產品的核心目標不是單純重寫 UI，而是建立一個可維護、可擴張、可追蹤的超導電路研究工作平台。

- 以單一 canonical circuit definition 串起 UI、CLI、模擬、schemdraw 與分析流程
- 讓研究者能在同一套系統中完成電路定義、模擬、characterization、資料管理、任務追蹤與結果回看
- 讓既有 NiceGUI、CLI、core script 與資料檔案中的能力收斂到一致的 contract 與 execution model

## Research Workflow Goals

本專案必須支援下列研究工作流，而不是只提供零散工具：

- 撰寫與驗證 circuit definition / netlist
- 從 circuit definition 驅動 schemdraw、simulation 與 characterization
- 管理 dataset / trace / analysis result / derived parameters / provenance
- 讓結果可被保存、追溯、重新 attach、重新分析與比較

## Data And Provenance Goals

本專案的資料面目標是把 metadata、trace payload 與結果關聯清楚切開，同時保持可重建性。

- metadata 由資料庫管理
- numeric payload 與 trace 由 TraceStore 管理
- 任一 simulation / post-process / characterization 結果都必須可追到 dataset、trace、task 與 provenance
- frontend 不得成為 canonical computation state 的唯一持有者

## System Success Criteria

整體重構完成時，至少要同時成立：

- legacy NiceGUI 與既有 CLI 能做到的事，在新系統中都能做到
- backend 可獨立提供 auth / CRUD / task / TraceStore / execution contracts
- `sc_core` 成為 canonical contracts 與共享計算邏輯的中心
- frontend 只保留 draft state / interaction state / view state，不保存 canonical computation state
- Electron 只作為 desktop shell，不改變系統邊界
- desktop shell 應可同時承載 managed local runtime 與 remote server client 兩種 profile，而不是分裂成兩個產品
- task / dataset / result 可在 refresh、reconnect、重開後重新 attach 與重建

!!! success "Success bar"
    rewrite 的完成條件不是「畫面換成 Next.js」，而是 canonical definition、task/result recovery、資料 provenance、CLI 與 desktop shell 都能在同一套邊界下成立。

## Scope

### Core Product Surfaces

| 能力 | 說明 |
| --- | --- |
| Data Browser | 瀏覽 metadata、trace summary、analysis result 與 lineage |
| Circuit Definition Editor | 編輯 circuit/netlist/schema 定義，並提供驗證與格式化 |
| Circuit Schemdraw | 由 canonical circuit definition 產生可視化電路圖 |
| Circuit Simulation | 以 `JosephsonCircuits.jl` 為核心進行模擬與掃描 |
| Characterization & Analysis | 對 simulation / layout / measurement traces 套用一致分析流程，並提供後處理、擬合、比較、參數萃取與視覺化 |
| CLI Available | 所有關鍵工作流必須可從 CLI 執行，不以 UI 獨占 |

### Accepted Data Sources

- circuit simulation traces
- layout simulation traces（例如 HFSS / Q3D）
- measurement traces（例如 VNA）
- 相容的 S/Y/Z matrix traces 與其衍生分析結果

### Rewrite Direction

- UI：以 **Next.js App Router** 為主
- API：以 **FastAPI** 為主
- CLI：維持一級公民，與 API/核心服務共用規則而非複製邏輯
- Desktop：允許使用 **Electron** 包裝 frontend，形成可本地執行的 desktop app
- Desktop runtime direction：同一個 shell 可進入 managed local runtime 或 remote server client profile
- Legacy：既有 NiceGUI 僅作為 migration 參考，不再作為新功能預設實作層

??? note "CLI position"
    CLI 仍是正式產品 surface，但已收斂為 standalone-first。這不改變 workbench 的核心產品定位，只是避免把 app collaboration model 硬套到 CLI。

## Target Audience

- 超導電路與量子硬體研究人員
- 需要整合 simulation / layout / measurement 的使用者
- 需要可重現 CLI workflow 與可擴充 Web UI 的開發者

## Agent Rule { #agent-rule }

```markdown
## Project Goal
- **Mission**: Build a superconducting-circuit workbench with a separated frontend/backend architecture and first-class CLI support.
- **Core product surfaces**:
    - Data Browser
    - Circuit Definition Editor
    - Circuit Schemdraw
    - Circuit Simulation
    - Characterization & Analysis
    - CLI Available
- **Data sources**:
    - circuit simulation
    - layout simulation
    - measurement
    - compatible S/Y/Z traces
- **Architecture direction**:
    - UI uses Next.js App Router
    - API uses FastAPI
    - CLI stays supported and must share business rules with the core/backend
    - Electron is an allowed desktop wrapper for local-first desktop runtime
    - existing NiceGUI code is legacy, not the default place for new work
- **Core values**:
    - scientific accuracy
    - reproducible workflows
    - one canonical definition feeding UI, API, CLI, simulation, and schemdraw
- **Product goals**:
    - support circuit definition, simulation, characterization, data management, task tracking, and result recovery in one platform
    - keep metadata, trace payloads, and provenance contracts explicit and reconstructible
    - ensure frontend holds draft/view state only, while canonical computation state stays in backend/core/storage contracts
- **Audience**: researchers, students, and developers working on superconducting-circuit simulation and analysis workflows.
```
