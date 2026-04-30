---
aliases:
  - Data Formats Reference
  - 數據格式參考
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/data-format
status: stable
owner: docs-team
audience: team
scope: dataset-first persisted research model、dataset-local DesignScope lifecycle、trace storage 與 analysis artifact contract
version: v3.1.0
last_updated: 2026-04-30
updated_by: codex
---

# Data Formats

本章是 persisted research model 的 SoT，主軸為：

- `DatasetRecord` 是 collaboration 與 session context 的頂層 container
- `DesignScope` 是 dataset 內 lifecycle-managed analytical scope
- `TraceRecord` 是可分析的標準 trace 單位
- `TraceBatchRecord` 是 setup / provenance / lineage 邊界
- `TraceStore`（Zarr）保存大型 ND numeric payload
- `AnalysisRunRecord` + `ResultArtifactRecord` 定義 artifact-first result view

!!! important "Dataset-first baseline"
    - `active_dataset` 綁定 `DatasetRecord`，不是 design。
    - `Raw Data Browser` 與 `Characterization` 選的是 dataset-local `design_id`。
    - Data Ingestion 與 Simulation publication 必須明確選既有 `DesignScope` 或 create-new target。
    - Characterization 的輸入一律是相容的 S/Y/Z matrix traces。
    - `layout_simulation` / `circuit_simulation` / `measurement` 只是來源不同。
    - metadata DB 與 numeric TraceStore 必須分離。
    - canonical trace 可為 1D / 2D / ND；sweep point 不是唯一 canonical record 單位。

## Page Map

| Topic | 說明 |
|---|---|
| [Dataset / Design / Trace Schema](dataset-record.md) | `DatasetRecord`、`DesignScope` lifecycle / merge、`TraceRecord`、`TraceBatchRecord`、`TraceStoreRef` |
| [Circuit Netlist](circuit-netlist.md) | Circuit Definition source / expanded contract |
| [Raw Data Layout](raw-data-layout.md) | raw source 與 dataset/design ingest 邊界 |
| [Analysis Result](analysis-result.md) | `AnalysisRunRecord` / `ResultArtifactRecord` / `DerivedParameterRecord` |
| [Query Indexing Strategy](query-indexing-strategy.md) | metadata DB 查詢與 TraceStore slice-read 效能策略 |

## Quick Lookup

| 你想確認什麼？ | 先看哪頁 |
|---|---|
| `active_dataset` 到底指向什麼？ | [Dataset / Design / Trace Schema](dataset-record.md) |
| `design_id` 與 dataset 的關係是什麼？ | [Dataset / Design / Trace Schema](dataset-record.md) |
| DesignScope rename / merge / archive 後 deep link 怎麼辦？ | [Dataset / Design / Trace Schema](dataset-record.md) |
| sweep trace 是存成 ND 還是每點一筆？ | [Dataset / Design / Trace Schema](dataset-record.md) |
| 大型 trace values 存在哪裡？ | [Dataset / Design / Trace Schema](dataset-record.md) + [Data Storage](../../explanation/architecture/data-storage.md) |
| local 與 S3/MinIO backend 如何共存？ | [Dataset / Design / Trace Schema](dataset-record.md) + [Data Storage](../../explanation/architecture/data-storage.md) |
| Circuit Definition 在這套架構裡扮演什麼角色？ | [Circuit Netlist](circuit-netlist.md) |
| Characterization result view 到底依賴什麼？ | [Analysis Result](analysis-result.md) |
| Query / indexing 該先優化 DB 還是 TraceStore？ | [Query Indexing Strategy](query-indexing-strategy.md) |

## Related

- [Data Storage](../../explanation/architecture/data-storage.md)
- [Project Overview Guardrail](../guardrails/project-basics/project-overview.md)
- [Data Handling Guardrail](../guardrails/code-quality/data-handling.md)
