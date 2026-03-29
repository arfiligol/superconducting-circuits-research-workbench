---
aliases:
  - Backend Characterization Results
  - Characterization Result Service
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Characterization analysis registry、input collection、run history、axis-aware artifact manifest、artifact payload 與 identify/tagging 的 backend reference surface。
version: v0.10.0
last_updated: 2026-03-30
updated_by: codex
---

# Characterization Results

本頁定義 frontend `Characterization` 頁依賴的 analysis result surface。

!!! info "Surface Boundary"
    本頁負責 analysis-specific read / mutation contract。
    task lifecycle 本身由 [Tasks & Execution](tasks-execution.md) 定義。

!!! tip "Primary Consumers"
    主要消費者是 [Characterization](../frontend/research-workflow/characterization.md) 與 [Dashboard](../frontend/workspace/dashboard.md)。

---

## 涵蓋範圍 (Coverage)

| Surface | 說明 |
| :--- | :--- |
| **Analysis Registry Summary** | 分析項註冊摘要 |
| **Characterization Input Collection** | 由 selected traces 與 persisted trace structure 派生的 scientific input collection |
| **Run History List** | 執行歷史列表 |
| **Result Artifact Manifest** | analysis-aware、axis-aware 結果產出清單 |
| **Artifact Payload Query** | table / plot / preset 產出內容查詢 |
| **Identify Mode / Parameter Tagging** | 識別模式與參數標記異動 |

---

## Surface Contracts

=== "Analysis Registry"

    registry summary 至少必須提供：

    | 欄位 | 說明 |
    | :--- | :--- |
    | `analysis_id` | 分析項唯一識別 |
    | `label` | 顯示標籤 |
    | `availability_state` | 可用狀態 |
    | `required_config_fields` | 必要配置欄位 |
    | `trace_compatibility` | Trace 相容性摘要 |
    | `input_axis_requirements` | 對 source trace axes / sweep axes 的需求摘要 |
    | `result_view_capabilities` | 此 analysis 預期提供的 table / plot presets 摘要 |

    query input baseline：

    | Field | Meaning |
    |---|---|
    | `dataset_id` | active dataset scope |
    | `design_id` | 目前 design scope |
    | `selected_trace_ids[]` | compatibility 計算可參考的明確 selection；仍屬於 UI interaction input |

=== "Characterization Input Collection"

    backend 可依 selected traces 派生 characterization input collection。

    minimum collection contract：

    | Field | Meaning |
    |---|---|
    | `source_trace_ids[]` | user-selected source traces |
    | `source_batch_ids[]` | optional upstream batch lineage |
    | `shared_axes[]` | selected traces 共同可解讀的 canonical axes；包含 axis names、units 與可恢復的 coordinate values / refs |
    | `available_sweep_axes[]` | 可供 analysis / explorer 使用的 input sweep axes |
    | `grouping_summary` | 由 batch lineage / axis compatibility 派生的 scientific grouping 摘要 |
    | `readiness_state` | `ready`, `inspect_only`, `blocked` 等 collection readiness |

    collection rules：

    | Concern | Rule |
    |---|---|
    | Interaction vs scientific model | `selected_trace_ids[]` 是使用者互動輸入，不是最終 scientific meaning；最終 meaning 來自 collection 與 persisted trace axes |
    | ND sweep preservation | 若 source trace 本身為 parameter-swept ND trace，collection 必須直接保留 sweep axes，不得先降成 ad hoc point-trace bag |
    | Structured filtering | collection readiness 與 analysis availability 可依 family、representation、source、stage 與 available sweep axes 判定 |
    | No provenance parsing | backend 不得以解析 free-form provenance summary 來猜 sweep axis meaning |

=== "Run History"

    run history 每列至少必須提供：

    | 類別 | 包含項目 |
    | :--- | :--- |
    | **Identity** | run identifier, analysis type |
    | **State** | status, scope |
    | **Metrics** | traces count、axis summary |
    | **Metadata** | sources summary, provenance summary, input collection summary |

    run history query baseline：

    | Field | Meaning |
    |---|---|
    | `dataset_id` | active dataset scope |
    | `design_id` | design-scoped history |
    | `analysis_id` | optional filter |
    | `limit` | optional |
    | `after` / `before` | optional，cursor-based browse 位置 |

=== "Result Artifacts"

    manifest 至少必須提供：

    | 屬性 | 說明 |
    | :--- | :--- |
    | `artifact_id` | 產出唯一識別 |
    | `category` | 類別 (例如：Plot, Table) |
    | `view_kind` | 視圖類型 |
    | `title` | 標題 |
    | `axis_contract` | input axes / derived axes / metric axes 摘要 |
    | `preset_views[]` | 可直接套用的 table / plot preset 摘要 |
    | `query_spec` | artifact-level 查詢規格 |

    query 至少必須支援：

    - **Mode Filter**: trace mode filter
    - **Selection**: category selection / artifact tab selection
    - **Axis Projection**: row / column / x / y / series 所需 axis semantics
    - **Data**: table / plot 繪製所需 payload

    artifact payload query baseline：

    | Field | Meaning |
    |---|---|
    | `run_id` | persisted analysis run identity |
    | `artifact_id` | selected artifact |
    | `view_mode` | `table` / `plot` |
    | `preset_id` | optional；使用 backend-defined preset view |
    | `row_axis` / `column_axis` | optional，table projection axis |
    | `x_axis` / `y_axis` / `series_axis` | optional，plot projection axis |
    | `slice_selector` | optional；限制 payload 只回傳某組 axis slice / window |
    | `trace_mode_filter` | optional |
    | `category` | optional |

### Analysis-specific Result Axis Contract

Characterization results 必須同時區分 source input axes 與 analysis-derived result axes。

| Axis family | Meaning |
|---|---|
| `input_axis` | 直接來自 source trace canonical structure 的 axis，例如 `L_jun` |
| `derived_axis` | 由 analysis 產生的 axis，例如 `mode_index` |
| `metric` | table cell / plot y-value 等被觀測量，例如 `frequency_ghz` |

!!! warning "Derived axes must be labeled as derived"
    `mode_index`、fit iteration、residual bucket 等 analysis-produced axes，必須標示為 derived。
    它們不得被寫成 source trace 原生 axis。

### First-phase Admittance Resonance Extraction

本分析的第一階段 canonical result semantics 應定義為：

| Concern | Contract |
|---|---|
| Input axis | sweep parameter，例如 `L_jun` |
| Derived axis | `mode_index` |
| Metric | `frequency_ghz` |
| Table preset | rows=`mode_index`，columns=`L_jun`，cell=`frequency_ghz` |
| Plot preset A | x=`mode_index`，y=`frequency_ghz`，series=`L_jun` |
| Plot preset B | x=`L_jun`，y=`frequency_ghz`，series=`mode_index` |
| First-phase mode meaning | `mode_index` 只表示單一 sweep point 內的 ordinal extracted mode |
| Explicit non-goal | 本 contract 不宣稱已具備跨 sweep 的 physical mode continuity；若需此能力，必須另定 `mode_track_id` 等更強 contract |

### Invalid Cell And Mask Semantics

| Concern | Contract |
|---|---|
| Persisted invalid cell | source ND payload 可用 `NaN` 表示 invalid / unavailable numeric cell |
| `NaN` meaning | `NaN` 不是 `0`；analysis 不得把它當成零值帶入計算 |
| Mask-first processing | analysis 應先建立 validity mask，再只對 valid cells 執行 extraction / fitting / reduction |
| Grid preservation | invalid cells 不得自動授權 consumer collapse axes、drop sweep coordinates 或重塑 scientific grid |
| All-masked slice | 若整個 slice / sweep point / projection region 全部 invalid，仍應保留該 axis position；artifact payload 可回傳 empty / `null` / masked cells，但不得直接省略該 slice |
| Warning summary | analysis 或 result payload 可附帶 explicit warning / summary note，指出某些 slices fully masked |
| Result transport | artifact payload 可用 empty cell、`null`、display-safe mask summary 或 explicit mask payload 呈現 invalid cells，但不得暗中把 invalid cell 改寫成可計算零值 |

!!! warning "Preserve ND semantics while masking"
    mask-first 的重點是保留 canonical ND grid 結構，再只在 valid region 上計算。
    這不是「把 invalid cells 刪掉，然後假裝原本就是稀疏 1D bag」。

## Artifact Payload Efficiency Rules

| Concern | Rule |
|---|---|
| Manifest / history surfaces | run history 與 artifact manifest 不得預設 inline 大型 matrix / tensor payload |
| Slice-aware queries | 大型結果 tensor / matrix 應支援 `preset_id`、axis projection 與 `slice_selector`，而不是總是回傳整個 dense payload |
| Coordinate loading | full coordinate arrays 只在 result view 真正需要時載入 |
| Dominant access pattern | 目前優先支援 `固定 sweep point -> 讀完整 frequency slice`，或 `固定 result axes -> 讀單一 plot / table projection` |
| Storage / chunking | artifact payload retrieval 與 underlying chunking 應對齊主要 scientific access pattern，而不是 generic default |
| Whole dense tensor transport | large-result whole dense tensor transport 不是預設 contract；只有某 artifact/view 明確宣告允許時才可整包回傳 |

=== "Identify / Tagging"

    backend 必須支援以下操作：

    1. **Selection Path**: source parameter selection 所需資料
    2. **Metric Path**: designated metric selection 所需資料
    3. **Mutation**: parameter tagging mutation

    tagging mutation payload baseline：

    | Field | Meaning |
    |---|---|
    | `dataset_id` | active dataset |
    | `run_id` | source analysis run |
    | `artifact_id` | source artifact |
    | `source_parameter` | 被標記的來源參數 |
    | `designated_metric` | 目標核心度量 |

!!! warning "Trace-first Gating"
    availability 必須由 **compatible traces**、`selected_trace_ids[]` 與其派生的 **input collection** 驅動。
    design profile 只提供提示，不是唯一的硬性門檻。

!!! tip "Persisted Authority"
    run history 是 **persisted record surface**。
    frontend 重新整理後必須能重新讀回一致內容，不得僅依賴 page-local memory。

!!! warning "Artifact-first Result View"
    frontend result view 應 **僅依賴** artifact manifest 與 artifact payload。
    backend 不得要求 frontend 直接解析 `DerivedParameter.name`、自由拼接 fit-table label，或從 prose 中自行恢復 sweep axes。

!!! tip "Artifact-first still means axis-aware"
    artifact-first 不代表結果只能是單一 fit table 或 scalar report。
    artifact payload 可以是 axis-aware table matrix、plot payload 與 preset view contract。

!!! tip "Cross-cutting storage guidance"
    metadata / TraceStore 分工、summary-first query 與 ND payload access 邊界，應同時遵守 [Data Handling](../../guardrails/code-quality/data-handling.md)。

!!! check "Consistency Guarantee"
    mutation 完成後，當 result context 或 run history 需要重讀時，應能從 **persisted state** 取得一致結果。

---

## Tagging Propagation

`Tag Parameter` mutation 成功後，backend 還必須更新供 Dashboard 使用的 dataset-level metrics summary。

| 讀回消費者 | 預期結果 |
| :--- | :--- |
| [Characterization](../frontend/research-workflow/characterization.md) | 重新讀取後看到最新 tagging 狀態 |
| [Dashboard](../frontend/workspace/dashboard.md) | `Tagged Core Metrics` 摘要可讀回最新標記 |

!!! warning "Cross-page Consistency"
    identify / tagging 不是只影響 Characterization 局部畫面。
    mutation 成功後，相關 dataset summary 必須能跨頁一致讀回。

## Tagged Core Metrics Resolution Contract

Dashboard 讀取 `Tagged Core Metrics` 時，必須用同一套 canonical resolution 規則將
`ParameterDesignation` 對到 `DerivedParameter`，避免 UI/CLI 各自重複拼 SQL 導致結果漂移。

| 項目 | 契約 |
| :--- | :--- |
| **Authority** | 由 persistence repository contract 負責 designation 與 derived parameter 查詢；UI/CLI 不得直接操作 ORM Session。 |
| **Exact Match** | 先嘗試 `dataset_id + source_analysis_type + source_parameter_name` 的精確匹配。 |
| **Compatibility Fallback** | 若 exact miss，允許 `source_parameter_name + "_b0"` fallback。 |
| **Prefix Fallback** | 若仍 miss，最後允許同 `dataset_id + method` 下的 name prefix 首筆匹配。 |
| **Tagging Uniqueness** | 同一 dataset 下，`designated_name + source_analysis_type + source_parameter_name` 不得重複。 |
| **Rename Migration Safety** | 對 legacy 參數名做正規化改名時，若新 key 已存在，必須去重且保持 idempotent。 |

!!! warning "Boundary Rule"
    上述匹配與去重邏輯屬於 backend/persistence contract，不能散落在 page handler 或 CLI command 的 Session query 中。

---

## Delivery Rules

| 項目 | 規則 |
| :--- | :--- |
| **Run/Result Split** | run lifecycle 與 result payload 是不同 surface，但必須可由同一 run lineage 串接。 |
| **Empty Diagnostics** | 若 run 完成但無 renderable artifact，backend 應回傳顯式的 empty-state 診斷資訊。 |
| **No Rerun** | artifact payload query **不得隱式重跑** analysis。 |
| **Trace Consistency** | `All / Base / Sideband` 的過濾語意必須與 frontend 保持絕對一致。 |

## Request / Response Examples

!!! example "Run history query"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "run_id": "run_20",
            "analysis_id": "admittance_extraction",
            "status": "completed",
            "scope": "design_traces",
            "trace_count": 1,
            "input_collection_summary": {
              "shared_axes": ["frequency", "L_jun"],
              "available_sweep_axes": ["L_jun"]
            },
            "result_axes_summary": {
              "input_axes": ["L_jun"],
              "derived_axes": ["mode_index"],
              "metrics": ["frequency_ghz"]
            },
            "sources_summary": "Y 1",
            "provenance_summary": "Postprocess · batches #4"
          }
        ]
      },
      "meta": {
        "limit": 20,
        "next_cursor": null,
        "prev_cursor": null,
        "has_more": false
      }
    }
    ```

!!! example "Artifact payload query"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "run_id": "run_20",
        "artifact_id": "artifact_resonance_frequency_matrix",
        "view_mode": "table",
        "axis_contract": {
          "row_axis": "mode_index",
          "column_axis": "L_jun",
          "metric": "frequency_ghz"
        },
        "preset_views": [
          {
            "preset_id": "table_mode_by_ljun",
            "view_mode": "table"
          },
          {
            "preset_id": "plot_mode_vs_frequency_by_ljun",
            "view_mode": "plot"
          }
        ],
        "columns": [
          {"key": "mode_index", "label": "Mode #", "role": "row_axis"},
          {"key": "14.0", "label": "L_jun = 14.0 nH", "role": "column_axis"},
          {"key": "15.0", "label": "L_jun = 15.0 nH", "role": "column_axis"}
        ],
        "rows": [
          {
            "mode_index": 0,
            "14.0": 4.031255,
            "15.0": 3.927465
          },
          {
            "mode_index": 1,
            "14.0": 5.884102,
            "15.0": 5.761774
          }
        ]
      }
    }
    ```

!!! example "Tag parameter mutation"
    Request:
    ```json
    {
      "dataset_id": "ds_xy_001",
      "run_id": "run_20",
      "artifact_id": "artifact_resonance_frequency_matrix",
      "source_parameter": "L_q",
      "designated_metric": "mode_1_frequency"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "tagging_status": "applied",
        "dataset_id": "ds_xy_001",
        "metric_id": "metric_mode_1_frequency"
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
|---|---|---|
| `analysis_not_available` | `validation_error` | analysis 與 design / trace selection 不相容 |
| `trace_selection_invalid` | `validation_error` | selected trace ids 缺失或不合法 |
| `characterization_input_collection_invalid` | `validation_error` | selected traces 無法形成有效的 scientific input collection |
| `result_axis_not_available` | `validation_error` | 指定 artifact / preset 不支援要求的 row / column / plot axis 組合 |
| `run_not_found` | `not_found` | run history 或 artifact 所指 run 不存在 |
| `artifact_not_found` | `not_found` | artifact manifest 中找不到指定 artifact |
| `tagging_conflict` | `conflict` | tagging mutation 與現有 metric mapping 衝突 |

---

## Related

- [Characterization](../frontend/research-workflow/characterization.md)
- [Tasks & Execution](tasks-execution.md)
- [Dataset / Design / Trace Schema](../../data-formats/dataset-record.md)
- [Analysis Result Schema](../../data-formats/analysis-result.md)
- [Data Handling](../../guardrails/code-quality/data-handling.md)
