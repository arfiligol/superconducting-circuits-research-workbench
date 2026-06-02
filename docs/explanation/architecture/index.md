---
aliases:
- Architecture Explanation
- 架構概念
tags:
- diataxis/explanation
- audience/team
- topic/architecture
status: draft
owner: docs-team
audience: team
scope: Architecture 說明索引，涵蓋 Clean Architecture、Data Storage、Desktop、Observability、Pipeline、Circuit Simulation
version: v0.4.0
last_updated: 2026-03-25
updated_by: codex
---

# Architecture

這個區塊整理系統的架構觀點，聚焦「為什麼這樣設計」與「如何運作」。

## Sections

- [Clean Architecture](design-decisions/clean-architecture.md)
  分層邊界、依賴方向、組合位置。
- [Data Storage](data-storage.md)
  `DesignRecord / TraceRecord / TraceBatchRecord / TraceStore` 的責任分層。
- [Desktop Runtime Supervisor](desktop-runtime-supervisor.md)
  為什麼 desktop shell 應採 Electron + runtime profile supervisor，而不是讓 main process 承擔 solver work。
- [Observability Taxonomy](observability-taxonomy.md)
  為什麼 audit logging、workflow observability 與 product telemetry 必須分層。
- [Pipeline](pipeline/index.md)
  Research Direct、Product Async 與 Data / Platform Notebook tracks 的資料與執行流程。
- [Circuit Simulation](circuit-simulation/index.md)
  Schema 編輯、Live Preview、領域語意與互動策略。
- [Visualization Backend](design-decisions/visualization-backend.md)
  Plotly / Matplotlib 的定位與取捨。

## Related

- [Explanation](../index.md)
- [Data Formats](../../reference/data-formats/index.md)
