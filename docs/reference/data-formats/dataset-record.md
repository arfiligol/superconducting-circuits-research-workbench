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
version: v3.4.0
last_updated: 2026-04-06
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
| `axes` | JSON | required | axis definitions、order 與 canonical sweep structure |
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

| Concern | Rule |
| --- | --- |
| Semantic axis authority | `TraceRecord.axes` 擁有 canonical axis identity；至少包含 axis names、order、units 與 semantic axis meaning |
| Coordinate values | axis definition 必須讓 coordinate values 可 machine-readably 恢復；可 inline 保存，也可透過 backend-controlled store reference 取回，僅有 `length` 並不足夠 |
| Axis naming | parameter sweep axis 名稱應重用 Circuit Definition / simulation setup 的 canonical parameter name |
| Axis order | axis order 是 canonical numeric layout 的一部分；consumer 不得自行重排後再回寫為 authority |
| Responsibility split | dense coordinate arrays 可由 `TraceStore` 持有；metadata/read model 只暴露 query-safe summary，不直接取代 axis authority |

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

!!! tip "Axis coordinates may live beside values"
    sweep-aware traces 的 axis coordinate arrays 可以與 `values` 一起存在 `TraceStore`。
    實際欄位命名可由 backend storage contract 控制，但 coordinate values 必須保持 machine-readable，可供 Characterization input collection 與 result explorer 恢復。

### Axis Signature Contract

`axis_signature` 是對 canonical axis identity / coordinate structure 的 deterministic summary。

| Concern | Rule |
| --- | --- |
| Primary use | 用於 cache safety、collection derivation、grouping compatibility checks 與 deep-link safety |
| Non-goal | 它不是 user-facing scientific label，也不是 full coordinate arrays 的替代品 |
| Equality meaning | 在同一 contract version 下，equal signatures 應表示相同 canonical axis structure |
| Formula freedom | exact hashing / signature formula 可由 implementation 決定，但必須 deterministic 且可重建 |

!!! important "Canonical ND trace"
    canonical `TraceRecord` 可以是 1D、2D 或 ND。
    sweep point 不是唯一 canonical record 單位；若 UI 需要 point-level rows，應視為 projection。

### Sweep-aware Trace Rules

| Concern | Rule |
| --- | --- |
| Canonical swept publication | parameter-swept simulation / post-processing outputs 應以 canonical ND `TraceRecord` 持久化，不以多筆 sweep-point 1D traces 當作唯一 authority |
| Axis authority | `frequency` 與所有 parameter sweep axes 都必須直接存在 `TraceRecord.axes`，不可只藏在檔名、`parameter` 字串或 provenance prose |
| Sweep meaning recovery | sweep axis 的語意必須可由 `TraceRecord.axes` 與來源 `TraceBatchRecord.setup_payload` 恢復；不得依賴 free-form label parsing |
| Point / slice browse | point-level rows、單一 sweep point preview 或 compare slices 只可視為 browse projection，不可反向成為 canonical storage model |
| Multi-sweep | 多軸 sweep 可直接以 ND trace 表示，例如 `axes = [frequency, L_jun, C_q]` |

!!! tip "Circuit Definition + Simulation Setup authority"
    哪些參數可被 sweep，來自 Circuit Definition / schema parameter model；
    實際 sweep 了哪些軸、值與順序，來自 `TraceBatchRecord.setup_payload`。
    `TraceRecord.axes` 是 published numeric result 的 canonical axis contract。

### Invalid Cell And Mask Semantics

| Concern | Rule |
| --- | --- |
| Canonical invalid cell | persisted numeric payload 可使用 `NaN` 表示 canonical ND grid 中沒有有效數值的 cell |
| `NaN` meaning | `NaN` 代表 invalid / unavailable numeric value，不得被重解釋為 `0` |
| Mask-first processing | analysis / explorer 應先建立 validity mask，再只對 valid cells 計算，同時保留原始 ND axes / shape |
| Shape preservation | consumer 不得因為某些 cells 無效，就默默 drop values 後重塑成不同維度的 authority payload |
| Fully masked slice | 即使整個 slice / sweep point 都無有效 cells，該 axis member 仍必須在 canonical grid 中保持存在，不得因全遮罩而被刪除 |
| Transport projection | transport / UI 可用 display-safe empty cell、`null` 或 explicit mask summary 呈現 invalid cells，但不得改變 persisted authority 的 `NaN` + mask 語意 |

### Metadata Materialization Direction

query / filter / readiness surface 所需的 trace summary 應 materialize 在 metadata/query 層，而不是每次去打開完整 ND payload。

recommended materialization targets：

| Summary concern | Direction |
| --- | --- |
| grid rank / shape | `ndim`、`shape` |
| axis structure | `axis_names`、`axis_units`、`axis_lengths` |
| sweep readiness | `available_sweep_axes` |
| phase-1 filtering scope | summary-safe axis existence / shape / typing；不含 coordinate-value / range filtering |
| coordinate identity | `axis_signature` 或等價的 coordinate/hash summary |
| scientific identity | `family`、`parameter`、`representation`、`source_kind`、`stage_kind` |
| collection derivation | lineage / batch summary、shared-axis summary |

!!! tip "Field names may evolve"
    最終 metadata DB / read model 的欄位名可以調整；
    但上述 summary meaning 必須存在於 query-compatible surface，而不能只留在 TraceStore 深處。

!!! warning "Query surfaces do not own dense coordinates"
    query / filter / readiness surface 只擁有 summary-safe axis information。
    full coordinate arrays 仍屬於 dense numeric authority，不得要求 list/filter path 打開它們才能判斷相容性。

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

### Sweep Publication Rules

| Concern | Rule |
| --- | --- |
| Sweepable parameter source | `setup_payload` 只可引用 Circuit Definition / simulation setup 已定義為可 sweep 的 parameter axes |
| Published trace grouping | 同一次 parameter-swept execution 產生的 ND traces，應以 shared `TraceBatchRecord` lineage 與 compatible axes 結構形成 scientific grouping |
| Browse projection | implementation 可另外產生 sweep-point browse rows、slice thumbnails 或 compare projections，但它們是 read model，不取代 `TraceRecord` / `TraceStore` authority |
| Provenance wording | provenance / summary payload 可提供人類可讀摘要，但不得成為 sweep axis meaning 的唯一 machine-readable source |

### Query Efficiency Direction

| Concern | Rule |
| --- | --- |
| List / filter / readiness | 應優先依賴 materialized metadata summary，不得預設打開完整 ND values 或 full coordinate arrays |
| Detail / explorer | 只有在 trace detail、explorer 或 result view 真的需要時，才載入 full coordinate arrays 或 dense numeric slices |
| Storage chunking | `TraceStore` chunking 應對齊主要 scientific access pattern，而不是只用 generic square chunk defaults |
| Current target pattern | 目前優先支援 `固定 sweep point -> 讀完整 frequency slice`，以及 `固定 result axes -> 讀單一 plot / table projection` |

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
| `input_trace_ids` | JSON | required | user-selected trace ids |
| `input_batch_ids` | JSON | optional | source batch refs |
| `input_collection_payload` | JSON | optional | 由 persisted trace structure 派生的 scientific input collection；保留 shared axes、sweep values 與 grouping summary |
| `input_result_refs` | JSON | optional | downstream analysis 消費的 upstream run / artifact refs；當 input 來自 persisted analysis result surface 時使用 |
| `config_payload` | JSON | required | analysis config |
| `status` | string | required | `queued`, `running`, `completed`, `failed`, `cancelled`, `terminated` |
| `artifact_manifest` | JSON | optional | result artifact summary |
| `result_axes_manifest` | JSON | optional | analysis-defined input axes、derived axes、metric axes 與 preset view semantics |
| `created_at` | datetime | required | creation time |
| `completed_at` | datetime | optional | terminal time |

!!! important "Trace-first authority"
    Characterization 的統一輸入是 `TraceRecord`，不以來源類型區分 circuit/layout/measurement 專用分析流程。

### Characterization Input Collection Rules

| Concern | Rule |
| --- | --- |
| Interaction vs scientific authority | `input_trace_ids` 保留使用者互動層的明確 selection；scientific meaning 則由 backend 依 persisted trace structure 派生 `input_collection_payload` |
| Preserved structure | `input_collection_payload` 至少應保留 selected traces、shared axes、axis labels / units / values、compatible grouping 與 source batch lineage |
| ND sweep input | 若 source traces 本身是 parameter-swept ND traces，collection contract 應直接保留 sweep axes，而不是先降成散落的 1D point rows |
| No free-form recovery | collection 的 sweep meaning 不得依賴解析 `parameter` label、檔名或 provenance prose |
| Upstream result lineage | 若 analysis 消費的是前一個 analysis 的 persisted result surface，必須透過 `input_result_refs` 或等價 lineage refs 顯式記錄，而不是只保留 raw trace selection |

### Analysis Pipeline Lineage Rules

| Concern | Rule |
| --- | --- |
| Separate analysis runs | extraction、fitting、comparison 等每個 analysis 都維持獨立 `AnalysisRunRecord` |
| Upstream dependency | 下游 analysis 若依賴上游 persisted result，必須在 run lineage 中明確指向 upstream run / artifact refs |
| No synthetic mega-run | pipeline relation 以 lineage 串接，不得把多步分析壓成單一 do-everything run record |
| Compare-preserving path | 若 result 需要同時保留多個 collection members / source identities，該 identity 必須進入 result artifact / manifest contract，而不是在 runtime 中被平均後丟失 |

### Result Axes Manifest Rules

| Concern | Rule |
| --- | --- |
| Input axes | `result_axes_manifest` 必須可指出 analysis 消費了哪些 input axes，例如 `L_jun` |
| Derived axes | analysis 若產生 derived axes，例如 `mode_index`，必須顯式標示為 derived，不得假裝是 source trace 自帶 axis |
| Compare dimension | 若 analysis 需要保留多個 collection members / source identities，`result_axes_manifest` 或 artifact query spec 必須明示 member/source compare dimension，而不是把 identity 藏在 prose |
| Metric axes | table / plot cell metric 例如 `frequency_ghz`，必須可由 manifest 清楚識別 |
| Explorer presets | 若結果預設支援 table / plot 視圖，row / column / x / y / series 的 axis semantics 應由 manifest 或 artifact query spec 明示 |
| First-phase mode semantics | `mode_index` 只代表單一 sweep point 內的 ordinal extracted modes；它不是跨 sweep 的 physical mode identity |

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
| What is the canonical model for parameter sweeps? | ND `TraceRecord` axes；point rows are projections |
| Where does sweep meaning come from? | Circuit Definition / setup payload + `TraceRecord.axes` |
| Where should query/filter summaries live? | materialized metadata/query surfaces, not only TraceStore |

## Related

- [Data Formats Overview](index.md)
- [Raw Data Layout](raw-data-layout.md)
- [Query Indexing Strategy](query-indexing-strategy.md)
- [Analysis Result](analysis-result.md)
- [Datasets & Results](../app/backend/datasets-results.md)
- [Data Handling](../guardrails/code-quality/data-handling.md)
