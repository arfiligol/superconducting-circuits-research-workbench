---
aliases:
- How-to Guides
- 操作指南
tags:
- audience/team
status: stable
owner: docs-team
audience: team
scope: 目標導向的操作指南索引
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# How-to Guides

目標導向的操作指南，協助您解決特定問題或完成任務。

## Categories

### [Data Ingestion](ingest-data/hfss-admittance.md)
如何將外部數據（如 HFSS 模擬結果）匯入系統。

- [Ingest HFSS Admittance Data](ingest-data/hfss-admittance.md)
- [Ingest HFSS Scattering Data](ingest-data/hfss-scattering.md)

### [Model Fitting](fit-model/squid.md)
執行電路參數擬合與分析。

- [Fit SQUID Models](fit-model/squid.md)

### [Database Management](manage-db/index.md)
管理已匯入的數據與標籤。

- [Manage Datasets](manage-db/datasets.md)
- [Manage Tags](manage-db/tags.md)
- [Reorder IDs](manage-db/reorder-record-ids.md)

### [Simulation](simulation/index.md)
透過 Pluto direct execution 或 Application/Backend → Julia Runner async task 執行電路模擬。

### [Pluto](pluto/authoring-workflow.md)
使用 Julia Core 和選定的 Component Library 進行互動式 authoring、preflight 與 explicit batch sweep。

- [Authoring Workflow](pluto/authoring-workflow.md)
- [Parameter Sweep Workflow](pluto/parameter-sweep-workflow.md)

### [Contributing](contributing.md)
專案貢獻流程與規範。

### [Extend](extend/index.md)
擴充系統功能（新增 Parser 或 Model）。

## Related

- [Tutorials](../tutorials/index.md) - 按部就班的教學
- [Reference](../reference/index.md) - 詳細技術規格
