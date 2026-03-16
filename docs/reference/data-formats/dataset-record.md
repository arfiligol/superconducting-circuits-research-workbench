---
aliases:
  - "Dataset Record Schema"
  - "Dataset / Design / Trace Schema"
  - "資料集 / 設計 / Trace 規格"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/data-format
status: stable
owner: docs-team
audience: team
scope: DatasetRecord、dataset-local design scope、TraceRecord、TraceBatchRecord、AnalysisRunRecord、DerivedParameterRecord 與 TraceStore contract
version: v3.0.0
last_updated: 2026-03-14
updated_by: codex
title: Dataset / Design / Trace Schema
---

# Dataset / Design / Trace Schema

本頁定義 app 與 persisted storage 共用的 canonical research-data contract。

!!! info "Dataset-first baseline"
    `DatasetRecord` 是 collaboration、session context 與 persistence 的頂層 container。
    `Active Dataset` 綁定的是 dataset，不是 design。

!!! warning "Design does not replace dataset"
    `Design` 是 dataset 內部的分析邊界，不是另一個可取代 `Active Dataset` 的全域 context。
    `Raw Data Browser` 與 `Characterization` 選擇的是 **dataset-local design scope**。

## Canonical Relationship

```text
DatasetRecord
├── DesignScope
│   ├── TraceBatchRecord[]
│   ├── TraceRecord[]
│   ├── AnalysisRunRecord[]
│   └── DerivedParameterRecord[]
└── Dataset-level profile / tags / shared metadata
```

| Object | Canonical meaning |
| --- | --- |
| `DatasetRecord` | app-level persisted research container；也是 session `active_dataset` 的綁定對象 |
| `DesignScope` | dataset 內的分析 / browse 邊界；供 Raw Data Browser、Characterization、部分 result views 使用 |
| `TraceRecord` | one logical observable over ordered axes 的 canonical metadata record |
| `TraceBatchRecord` | import / simulation / preprocess / postprocess / analysis 的 persisted execution boundary |
| `AnalysisRunRecord` | trace-consuming analysis run 的 persisted identity |
| `DerivedParameterRecord` | 從 analysis run 萃取出的可命名物理參數 |

## Resource Envelope

所有 persisted research assets 至少必須帶有以下 envelope：

| Field | Required | Meaning |
| --- | --- | --- |
| `owner_user_id` | required | owner / creator identity |
| `workspace_id` | required | 唯一 workspace boundary |
| `visibility_scope` | required | `local`, `private` or `workspace` |
| `lifecycle_state` | required | `active`, `archived`, `deleted` |
| `created_at` | required | 建立時間 |
| `updated_at` | required | 最後更新時間 |

!!! tip "Inherited visibility"
    `TraceBatchRecord`、`AnalysisRunRecord`、`ResultArtifactRecord`、`DerivedParameterRecord`
    預設繼承來源 dataset / task 的 `workspace_id` 與 `visibility_scope`。

## DatasetRecord

`DatasetRecord` 是 app-level collaboration 與 workflow 的主容器。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string or int | required | dataset identity |
| `name` | string | required | dataset display name |
| `owner_user_id` | string | required | owner identity |
| `workspace_id` | string | required | owning workspace |
| `visibility_scope` | enum | required | `local` / `private` / `workspace` |
| `lifecycle_state` | enum | required | `active` / `archived` / `deleted` |
| `dataset_meta` | JSON | optional | dataset-level metadata / tags / summary |
| `profile_payload` | JSON | optional | device type、capabilities、profile source |
| `created_at` | datetime | required | creation time |
| `updated_at` | datetime | required | last update time |

### Dataset-level responsibilities

- session `active_dataset` 綁定的就是 `DatasetRecord.id`
- Dashboard 的 metadata editing 作用在 dataset-level profile
- dataset visibility / publish / archive / copy with lineage 也以 dataset 為邊界

## DesignScope

`DesignScope` 是 dataset 內的 analytical / browse boundary。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `design_id` | string or int | required | design scope identity；只在 dataset 內保證穩定 |
| `dataset_id` | string or int | required | parent dataset |
| `name` | string | required | design label |
| `design_meta` | JSON | optional | design-scoped metadata / source coverage / readiness summary |
| `source_coverage` | JSON | optional | 來源覆蓋摘要 |
| `created_at` | datetime | required | creation time |
| `updated_at` | datetime | required | last update time |

### Design scope rules

1. `DesignScope` 必須永遠屬於單一 `dataset_id`。
2. `Characterization`、`Raw Data Browser` 與 design-scoped results 都以 `design_id + dataset_id` 決定邊界。
3. `DesignScope` 不是 session global context；切換 dataset 會先改變可見 design scope 集合。

!!! info "Browse projection is allowed"
    implementation 可以用 dedicated table 或 derived read model 產生 design browse rows。
    但對 frontend / backend contract 而言，`design_id`、`dataset_id`、`name`、`source_coverage` 的語意必須穩定。

## DesignAssetRecord

設計層 source artifact。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string or int | required | asset identity |
| `dataset_id` | string or int | required | 所屬 dataset |
| `design_id` | string or int | optional | 所屬 design scope；若是 dataset-level source 可為 `null` |
| `asset_type` | string | required | `circuit_definition`, `layout_source`, `measurement_source`, `import_manifest` |
| `version` | string | optional | revision / import version |
| `content_payload` | JSON | required | source-form document or import manifest |
| `created_at` | datetime | required | creation time |

!!! important "Circuit Definition stays document-first"
    Circuit Definition 的原子單位仍是一份 revisioned source document，
    不先拆成 relational components/topology rows。

## TraceRecord

`TraceRecord` 是 one logical observable over axes 的 canonical metadata record。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string or int | required | trace identity |
| `dataset_id` | string or int | required | parent dataset |
| `design_id` | string or int | required | parent design scope |
| `family` | string | required | `s_matrix`, `y_matrix`, `z_matrix` or equivalent canonical family |
| `parameter` | string | required | `Y11`, `Y_dm_dm`, `S21` 等 |
| `representation` | string | required | `real`, `imaginary`, `magnitude`, `phase` |
| `axes` | JSON | required | axis definitions and order |
| `trace_meta` | JSON | optional | units、basis labels、source annotations、compare tags |
| `store_ref` | JSON | required | canonical TraceStore locator |
| `created_at` | datetime | required | creation time |

### Axes Contract

```json
[
  {"name": "frequency", "unit": "GHz", "length": 4001},
  {"name": "L_q", "unit": "nH", "length": 11}
]
```

### TraceStoreRef Contract

```json
{
  "backend": "local_zarr",
  "store_key": "datasets/ds_xy_001/designs/design_a/batches/batch_105.zarr",
  "store_uri": "data/trace_store/datasets/ds_xy_001/designs/design_a/batches/batch_105.zarr",
  "group_path": "/traces/trace_9001",
  "array_path": "values",
  "dtype": "float64",
  "shape": [4001, 11],
  "chunk_shape": [4001, 1],
  "schema_version": "1.0"
}
```

`store_key` 是 canonical locator；`store_uri` 僅作 backend-controlled opaque locator，不應由 UI 或 app layer 自行解析 local path layout。

!!! important "Canonical ND trace"
    canonical `TraceRecord` 可以是 1D、2D 或 ND。
    sweep point 不是唯一 canonical record 單位；若 UI 需要 point-level rows，應視為 projection。

## TraceBatchRecord

`TraceBatchRecord` 是一次 import / simulation / preprocess / postprocess / analysis 的 persisted execution boundary。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string or int | required | batch identity |
| `dataset_id` | string or int | required | parent dataset |
| `design_id` | string or int | required | parent design scope |
| `owner_user_id` | string | required | execution owner |
| `workspace_id` | string | required | owning workspace |
| `visibility_scope` | enum | required | inherited `local` / `private` / `workspace` |
| `lifecycle_state` | enum | required | `active`, `archived`, `deleted` |
| `source_kind` | string | required | `circuit_simulation`, `layout_simulation`, `measurement` |
| `stage_kind` | string | required | `import`, `raw`, `preprocess`, `postprocess`, `analysis` |
| `parent_batch_id` | string or int | optional | upstream lineage |
| `asset_record_id` | string or int | optional | linked source asset |
| `status` | string | required | `queued`, `running`, `completed`, `failed`, `cancelled`, `terminated` |
| `setup_kind` | string | required | execution/setup family |
| `setup_version` | string | required | payload version |
| `setup_payload` | JSON | required | source/setup/post-processing contract |
| `provenance_payload` | JSON | required | lineage / source refs / summaries |
| `summary_payload` | JSON | optional | UI-safe summary / preview |
| `created_at` | datetime | required | creation time |
| `completed_at` | datetime | optional | terminal time |

!!! warning "Persisted execution boundary"
    trace-producing flow 的正式 authority 是 `TraceBatchRecord` + `TraceRecord` + `TraceStore`。
    page-local last result、live memory cache 或 ad-hoc file parser 不得成為唯一 authority。

## TraceBatchTraceLink

batch 與 trace 的 membership 關聯。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `trace_batch_id` | string or int | required | batch identity |
| `trace_record_id` | string or int | required | trace identity |

## AnalysisRunRecord

`AnalysisRunRecord` 是 trace-consuming analysis 的 persisted identity。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string or int | required | run identity |
| `dataset_id` | string or int | required | parent dataset |
| `design_id` | string or int | required | parent design scope |
| `owner_user_id` | string | required | run owner |
| `workspace_id` | string | required | owning workspace |
| `visibility_scope` | enum | required | inherited `local` / `private` / `workspace` |
| `lifecycle_state` | enum | required | `active`, `archived`, `deleted` |
| `analysis_id` | string | required | `admittance_extraction` 等 |
| `input_trace_ids` | JSON | required | selected trace ids |
| `input_batch_ids` | JSON | optional | source batch refs |
| `config_payload` | JSON | required | analysis config |
| `status` | string | required | `queued`, `running`, `completed`, `failed`, `cancelled`, `terminated` |
| `artifact_manifest` | JSON | optional | result artifact summary |
| `created_at` | datetime | required | creation time |
| `completed_at` | datetime | optional | terminal time |

!!! important "Trace-first authority"
    Characterization 的統一輸入是 `TraceRecord`，不以來源類型區分 circuit/layout/measurement 專用分析流程。

## ResultArtifactRecord

結果檢視以 artifact-first 契約為主。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `artifact_id` | string | required | artifact identity |
| `analysis_run_id` | string or int | required | parent analysis run |
| `dataset_id` | string or int | required | parent dataset |
| `design_id` | string or int | required | parent design scope |
| `category` | string | required | `resonance`, `fit_table`, `plot`, `summary` 等 |
| `view_kind` | string | required | `table`, `plot`, `text`, `json` |
| `title` | string | required | display title |
| `trace_mode_group` | string | optional | `base`, `sideband`, `all` |
| `query_spec` | JSON | optional | artifact payload query baseline |
| `payload_ref` | JSON | required | storage / payload handle |

## DerivedParameterRecord

物理萃取結果與 tagged metrics 的 canonical scalar contract。

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string or int | required | parameter identity |
| `dataset_id` | string or int | required | parent dataset |
| `design_id` | string or int | required | parent design scope |
| `analysis_run_id` | string or int | required | source analysis run |
| `name` | string | required | parameter name |
| `value` | float | required | scalar value |
| `unit` | string | optional | unit |
| `extra` | JSON | optional | sweep provenance / fit metadata / trace mode |

## TraceStore Direction

`TraceStore` 採 `Zarr`，並保留 backend abstraction：

- 現階段：local filesystem
- storage extension（deferred）：S3-compatible endpoint（例如 MinIO / S3）

### Recommended Local Layout

```text
data/trace_store/
└── datasets/
    └── <dataset_id>/
        └── designs/
            └── <design_id>/
                └── batches/
                    └── <batch_id>.zarr
```

## Canonical Relationship Summary

| Question | Canonical answer |
| --- | --- |
| What does `active_dataset` point to? | `DatasetRecord.id` |
| What does the user pick inside Raw Data Browser / Characterization? | a dataset-local `design_id` |
| Can a design exist outside a dataset? | No |
| Can a resource belong to multiple workspaces? | No |
| Where do large numeric arrays live? | `TraceStore`, referenced by `store_ref` |

## Related

- [Data Formats Overview](index.md)
- [Raw Data Layout](raw-data-layout.md)
- [Query Indexing Strategy](query-indexing-strategy.md)
- [Analysis Result](analysis-result.md)
- [Datasets & Results](../app/backend/datasets-results.md)
