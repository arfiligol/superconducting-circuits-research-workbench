---
aliases:
  - "Simulation Guide"
  - "模擬指南"
tags:
  - diataxis/how-to
  - status/stable
  - topic/simulation
status: stable
owner: docs-team
audience: user
scope: "電路模擬教學索引"
version: v0.1.0
last_updated: 2026-01-28
updated_by: docs-team
---

# 電路模擬 (Simulation)

本專案使用 Julia Core 與 Julia Runner 執行超導電路模擬。
Application-triggered simulation 一律走 Python Backend task lifecycle，再由 Julia Runner 非同步產生 local filesystem Zarr result package。

## 教學方法選擇

使用下列兩種入口：

| 方法 | 適合對象 | Contract |
|------|----------|----------|
| **Pluto Notebook** | 研究、快速實驗、直接呼叫 Julia Core | notebook kernel 是 explicit research execution environment |
| **Application Task** | 產品化提交、監控、結果瀏覽 | Python Backend 建立 task，Julia Runner 寫 staging Zarr，Backend publish TraceStore |

## 教學列表

### Julia Runner task

| 教學 | 說明 |
|------|------|
| [Julia Runner Compute Plane](../../reference/architecture/julia-runner-compute-plane.md) | Runner task claim、heartbeat、complete/fail contract |
| [Runner Result Manifest](../../reference/architecture/runner-result-manifest.md) | staging manifest 與 Zarr layout |

### Notebook direct execution

| 教學 | 說明 |
|------|------|
| [Notebook Interface](../../reference/notebooks/index.md) | Pluto 與 Python notebook 的使用邊界 |
| [原生 Julia 模擬](native-julia.md) | 直接使用 Julia Core / JosephsonCircuits.jl 進行研究模擬 |

## 相關資源

- [Tutorial: LC 共振器](../../tutorials/lc-resonator.md) - 完整入門案例
- [Physics（重建中）](../../explanation/physics/index.md) - Physics 章節重建狀態
- [擴充 Julia 函數](../extend/extend-julia-functions.md) - 貢獻者指南
