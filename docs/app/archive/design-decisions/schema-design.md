---
aliases:
- Dataset Schema Design
- 資料集 Schema 設計
- Schema Design
- Schema 設計
tags:
  - diataxis/explanation
  - status/stable
  - topic/architecture
  - topic/data-format
  - audience/team
status: stable
owner: docs-team
audience: team
scope: DatasetRecord/DataRecord 的資料集 Schema 設計細節
version: v0.2.0
last_updated: 2026-02-27
updated_by: docs-team
sidebar:
  label: Dataset Schema Design
  order: 40
---

# Dataset Schema Design

目前的標準資料格式以 **SQLite Dataset** 為核心，使用 `DatasetRecord`/`DataRecord` 存放資料與關聯資訊。

## 核心概念

- **DatasetRecord**：描述一組資料的 metadata（名稱、來源、標籤、建立時間）。
- **DataRecord**：存放實際量測/模擬數據與軸資訊（頻率、偏壓等）。
- **DerivedParameter**：分析後的參數結果（例如擬合得到的 $L_s, C$）。

## 擴展性考量

- **多軸支援**：同一 Dataset 可包含多維掃描資料。
- **多參數**：一個 Dataset 可以同時包含多個參數族（S/Y/Z）或不同表示法。
- **可追溯**：資料來源與標籤集中管理，方便回溯與查詢。

## Related

- [Dataset Record Reference](../../../reference/data-formats/dataset-record.mdx) - 完整欄位說明
