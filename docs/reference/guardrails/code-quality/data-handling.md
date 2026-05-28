---
aliases:
  - "Data Handling Rules"
  - "數據處理規範"
tags:
  - audience/team
  - sot/true
status: stable
owner: docs-team
audience: team
scope: "數據處理規範：原始數據唯讀、metadata DB / TraceStore 分工、Runner staging、ND trace、NaN/mask、summary-first query、Unit of Work、Zarr backend 邊界"
version: v3.0.0
last_updated: 2026-03-30
updated_by: codex
---

# Data Handling

數據處理與儲存規範。

!!! info "What this page answers"
    這頁回答資料應該放哪裡、誰可以寫哪一層、以及 raw data、metadata、numeric payload 之間的責任邊界。

## Storage Map

| 區塊 | 用途 | 不該放什麼 |
| --- | --- | --- |
| `data/raw/` | 原始輸入資料，唯讀保存 | import、simulation、post-processing 的輸出 |
| metadata DB | 索引、lineage、查詢、setup metadata | 大型 numeric payload |
| Runner staging | temporary local filesystem Zarr result packages | official metadata / provenance authority |
| TraceStore | trace values、axes arrays、sweep arrays | UI/scripts 自己解析出的 backend 細節 |

## Directory Structure

```text
data/
├── raw/                        # 原始數據 (唯讀)
│   ├── measurement/
│   ├── circuit_simulation/
│   └── layout_simulation/
├── metadata.db                # metadata DB（可為 SQLite；若改用 PostgreSQL，仍須維持相同 contract）
├── trace_store/               # official Zarr TraceStore（local backend）
│   └── datasets/
├── artifacts/
│   └── tasks/
└── staging/
    └── tasks/
```

## Rules

### 1. Raw Data is Read-Only

`data/raw/` 下的所有檔案視為不可變：

- 不修改原始檔案
- 不刪除原始檔案
- ingest / import / simulation / post-processing 的輸出不得回寫到 raw tree

### 2. Metadata vs Numeric Payload

資料責任分工必須明確：

=== "Metadata DB"

    - `DesignRecord`
    - `TraceRecord`
    - `TraceBatchRecord`
    - `AnalysisRunRecord`
    - `DerivedParameterRecord`

=== "TraceStore"

    - trace numeric payload
    - axes arrays
    - sweep ND arrays

!!! important "No large numeric payload in metadata DB"
    大型 trace values 不應作為主要 payload 存入 SQLite/PostgreSQL JSON/BLOB。
    metadata DB 負責索引、lineage、setup、查詢；numeric payload 應進入 `Zarr` TraceStore。

!!! important "No large ND arrays over HTTP/JSON"
    HTTP/JSON 只可承載 task control、status、progress、manifest locator、error summary、metadata summary 與明確 slice/detail payload。
    S/Y/Z matrices、frequency sweeps、ND traces 與 Runner result arrays 必須寫入 local filesystem Zarr。

### 2.1 Materialized Summary Is Expected

query / filter / readiness surfaces 應依賴 metadata DB / read model 的 materialized summary，而不是每次打開完整 ND payload。

典型 summary target：

- `ndim`
- `shape`
- `axis_names`
- `axis_units`
- `axis_lengths`
- `available_sweep_axes`
- `axis_signature` 或等價 hash / coordinate summary
- `family` / `parameter` / `representation` / `source_kind` / `stage_kind`
- lineage / batch summary

!!! warning "Summary-first query"
    trace list、design browse、analysis readiness、filter suggestion path 不得預設載入完整 ND values 或 full coordinate arrays。

### 2.2 Responsibility Split Is Mandatory

- `TraceRecord.axes` 擁有 canonical axis identity 與 semantic axis meaning
- `TraceStore` 可持有 dense coordinate arrays 與 dense numeric values
- metadata/read models 擁有 query/filter/readiness 所需的 summary-safe axis information
- list/filter/readiness path 不得依賴打開 full coordinate arrays

### 2.3 Axis Signature Discipline

- `axis_signature` 是 deterministic summary of canonical axis identity / coordinate structure
- 可用於 cache safety、collection derivation、grouping compatibility 與 deep-link safety
- 不可當作 user-facing scientific label
- 不可取代 full coordinates

### 3. Use Path / Store Helpers

不得硬編碼 DB 或 TraceStore 路徑。

- metadata DB path 必須由 persistence helper 提供
- TraceStore backend（local / S3-compatible）必須透過抽象層決定

### 4. Database Access (Unit of Work)

所有 metadata DB 存取必須透過 Unit of Work：

!!! example "Metadata write flow"
    ```python
    from core.shared.persistence import get_unit_of_work

    with get_unit_of_work() as uow:
        design = uow.designs.get_by_name("PF6FQ_Q0")
        uow.traces.add(new_trace)
        uow.commit()
    ```

### 5. TraceStore Access

Trace numeric payload 的讀寫必須經由 TraceStore abstraction，而不是 UI/scripts 直接碰 backend 細節。

允許的 backend 方向：

- local filesystem `Zarr`
- S3-compatible `Zarr`（例如 MinIO / S3 endpoint）

`TraceStoreRef` 必須維持 backend-owned locator contract：

- `backend`：`local_zarr` / `s3_zarr`
- `store_key`：backend-neutral store object key
- `store_uri`：可保留為相容/debug locator，但視為 opaque，不可由 UI/app layer 解析 local layout
- `group_path` / `array_path`：TraceStore 內部群組與 array 定位

### 5.1 Runner Staging and Publication

Julia Runner writes local staging packages only:

```text
data/staging/tasks/<task_id>/
├── manifest.json
├── result.zarr/
└── logs/
```

Python Backend owns official publication:

```text
data/trace_store/datasets/<dataset_id>/designs/<design_id>/batches/<batch_id>.zarr/
```

Rules:

- staging is temporary and not authoritative
- TraceStore is the official numeric authority
- Backend must validate manifest paths, Zarr layout, dtype, shape, chunk shape, and axis lengths before publication
- Backend must reject absolute paths and path traversal such as `../`
- Runner must not write DatasetRecord, TraceRecord, TraceBatchRecord, workspace, auth, or provenance tables
- Runner result packages use Zarr v2 local filesystem staging
- S3-compatible direct write from Julia Runner is not allowed

### 5.2 Complex Arrays

Complex arrays must be stored as real/imag arrays:

```text
/traces/S11/real
/traces/S11/imag
```

Do not rely on cross-language `ComplexF64` dtype compatibility.

### 6. Canonical Trace Contract

- `TraceRecord` 的 canonical 單位是 **one logical observable over axes**
- 可為 1D / 2D / ND
- sweep point 不應自動視為一筆 canonical trace record
- point/slice level materialization 僅可作 projection / cache / export 契約

### 6.1 Invalid Cell Semantics

- canonical ND payload 可使用 `NaN` 表示 invalid / unavailable numeric cell
- `NaN` 不得被視為 `0`
- analysis / explorer 應採 mask-first 處理：先建立 validity mask，再只在 valid cells 上計算
- invalid cells 不得授權 consumer collapse axes、drop sweep structure 或默默 reshape authority payload
- fully masked slice 仍須保留原 axis position，不得因整段無效而刪除該 slice

### 6.2 Collection Projection Contract

- scientific `collection_projection` 可以由 canonical trace structure 派生
- collection projection 是 read model，不是獨立 authority resource
- 可使用 deterministic `collection_key` 支援 deep-linking、cache 與 UI restoration
- `collection_key` 必須可由 dataset/design scope、shared axis structure / `axis_signature`、lineage 與 trace set 內在的 stable scientific typing 重建
- analysis-specific readiness、consumer-specific presentation choice、UI sort/filter state 不可參與 `collection_key` identity
- 若需 persisted / editable collections，必須另定正式 resource contract

### 6.3 Access Pattern-aware Retrieval

- detail / explorer / result path 才載入 full coordinate arrays 或 dense numeric slices
- large matrix / tensor payload 應優先支援 slice / preset query，而不是總是整包 inline
- chunking / retrieval 應對齊主要 scientific access pattern
- whole dense tensor transport 不是 large result 的預設 contract
- sweep filtering uses summary-safe axis-name / collection-level filters; coordinate-value / range filtering requires a coordinate-domain summary contract
- 目前優先 access pattern：
  - fixed sweep point -> read full frequency slice
  - fixed result axes -> read one plot / table projection

### 6.4 Edit Invalidation Discipline

- 若 trace edit 會影響 axis structure、coordinate identity、materialized metadata summary、`collection_projection`、analysis readiness 或 persisted analysis/result truth，backend 必須同步 re-materialize 或 invalidate 這些依賴面
- 若 backend 無法維持上述 invalidation / recomputation contract，該 trace class 不得宣告 `allowed_actions.edit=true`

### 7. Output Locations

| 類型 | 目標位置 |
|------|----------|
| metadata records | metadata DB |
| trace numeric payload | TraceStore (`Zarr`) |
| reports / exports | `data/processed/reports/` 或明確 export path |

## Related

- [Design / Trace Schema](../../data-formats/dataset-record.md)
- [Raw Data Layout](../../data-formats/raw-data-layout.md)
- [Data Storage](../../../explanation/architecture/data-storage.md)

??? note "Why this page does not describe every backend"
    這頁只定 storage split 與 access boundary。若新增 PostgreSQL、S3-compatible Zarr 或其他 backend，仍必須保持相同 canonical contract，而不是改寫這裡的責任邊界。

---

## Agent Rule { #agent-rule }

```markdown
## Data Handling
- **Immutable**: `data/raw/` is READ-ONLY.
- **Storage split**:
    - metadata goes to the metadata DB
    - numeric trace payload goes to the TraceStore (`Zarr`)
- **Summary-first query**:
    - materialize query/filter/readiness summaries in metadata/read models
    - do not open full ND payloads by default for list/filter paths
- **Responsibility split**:
    - `TraceRecord.axes` owns semantic axis identity
    - `TraceStore` may own dense coordinates and dense values
    - metadata/read models own summary-safe query/filter fields
- **Paths**: NEVER hardcode metadata DB or TraceStore paths/backends.
- **Database**:
    - MUST use Unit of Work for metadata DB operations.
    - NEVER access Session directly in UI/notebook/script code.
    - MUST call `uow.commit()` explicitly.
- **TraceStore**:
    - MUST go through a TraceStore abstraction.
    - MUST support local filesystem `Zarr v2` as the baseline storage contract.
    - MUST require a storage-backend SoT before adding remote object storage.
    - Runner staging is temporary and never authoritative.
    - Backend owns official TraceStore publication.
    - Complex arrays MUST be stored as explicit real/imag arrays.
- **Canonical trace contract**:
    - `TraceRecord` is one logical observable over axes.
    - ND traces are allowed and preferred over point-fragmented canonical storage.
    - point/slice materialization is projection/cache/export, not the only SoT.
- **Invalid cells**:
    - `NaN` means invalid/unavailable numeric data, not zero.
    - MUST use mask-first processing and preserve ND axis structure.
    - MUST preserve fully masked slice positions.
- **Collection projection**:
    - scientific grouping may be derived as a read model with deterministic keys.
    - collection keys must be reconstructable from stable structural grouping inputs.
    - do not derive collection identity from analysis-specific readiness or consumer presentation state.
    - do not treat projection as an independent authority resource unless separately specified.
- **Retrieval**:
    - load full coordinate arrays / dense payloads only on detail, explorer, or result paths that need them.
    - slice/preset queries should be preferred for large tensors/matrices.
    - no large ND arrays over HTTP/JSON.
    - whole dense tensor transport is not the default large-result contract.
    - sweep filtering is limited to summary-safe axis-name / collection-level filters unless a coordinate-domain summary contract exists.
- **Edit invalidation**:
    - if an editable trace changes data that affects summaries, collection derivation, readiness, or dependent results, the backend MUST re-materialize or invalidate those surfaces before reporting success.
    - if it cannot maintain that contract, it MUST expose `allowed_actions.edit=false`.
- **Flow**:
    - Raw -> Import/Simulation/Post-Processing -> metadata DB + TraceStore -> Characterization / Reports
- **Legacy**:
    - Do not create new JSON-only numeric pipelines.
    - Do not treat SQLite/PostgreSQL JSON/BLOB as the long-term primary numeric trace store.
```
