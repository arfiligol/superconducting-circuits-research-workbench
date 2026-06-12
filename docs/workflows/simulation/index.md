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
scope: "Notebook-first simulation workflow index"
version: v0.2.0
last_updated: 2026-06-12
updated_by: codex
sidebar:
  label: Overview
  order: 10
---

# Julia Core Simulation

本專案的研究模擬路徑以 Pluto Notebook 作為起點，再把穩定語意推進 Julia Core。研究者應先用 Pluto 直接呼叫 Julia Core / JosephsonCircuits.jl，確認物理設定、sweep 範圍與可視化結果。

## 教學方法選擇

使用下列入口：

| 方法 | 適合對象 | Contract |
|------|----------|----------|
| **Pluto Notebook** | 研究、快速實驗、直接呼叫 Julia Core | notebook kernel 是 explicit research execution environment |
| **Julia Core package code** | 可重用 components、helpers、simulation intent | package code owns reusable semantics |
| **Native Julia script / REPL** | 小型檢查或除錯 | explicit local execution |

## 教學列表

| 教學 | 說明 |
|------|------|
| [Pluto Research](../pluto/index.md) | Pluto Notebook 的研究執行與參數掃描入口 |
| [Notebook Interface](../../reference/notebooks/index.md) | Pluto 與 Python notebook 的使用邊界 |
| [原生 Julia 模擬](native-julia.md) | 直接使用 Julia Core / JosephsonCircuits.jl 進行研究模擬 |

## 相關資源

- [Tutorial: LC 共振器](../circuit-authoring/lc-resonator.md) - 完整入門案例
- [Core Reference](../../reference/core/index.md) - Julia Core、Python Core、Runner 與 Analysis Bridge 的責任邊界
- [Extending Research Tools](../research-tools/index.md) - 貢獻者指南
