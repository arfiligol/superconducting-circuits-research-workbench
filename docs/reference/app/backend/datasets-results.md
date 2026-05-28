---
aliases:
  - Backend Datasets Results Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: Backend dataset catalog、DesignScope lifecycle / target selection、sweep-aware trace browse / preview / mutation、analysis-facing trace projection、dataset profile、tagged core metrics 與 provenance-bearing result handles
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Datasets & Results

本頁定義 Dashboard、Header dataset switcher、Raw Data Browser、Analysis Workbench 與 ResultView 依賴的 dataset / design / trace / result surface。

!!! important "Authoring authority"
    This page is the current Backend data-surface authority for Dataset Catalog, Dataset Profile, DesignScope, Trace Surface, Result Handles, sweep-aware trace browse, analysis-facing trace projection, and summary-first query rules.
    Future implementation agents should treat these contracts as active unless a newer source-of-truth explicitly replaces them.

!!! info "Surface Boundary"
    本頁負責 dataset catalog、dataset profile、dataset-local DesignScope browse / lifecycle / target selection、sweep-aware trace browse / preview / edit payload、trace mutation gating、analysis-facing trace filtering projection、tagged core metrics summary 與 provenance-bearing result handles。
    task lifecycle、analysis-specific artifact manifest 與 audit query 不屬於本頁責任。

!!! tip "Primary Consumers"
    主要消費者是 [Dashboard](../frontend/workspace/dashboard.md)、[Raw Data Browser](../frontend/workspace/raw-data-browser.md)、Analysis Workbench、ResultView API 與 [Header](../frontend/shared-shell/header.md)。

## Coverage

| Surface | Meaning |
| --- | --- |
| Dataset Catalog | Header / Dashboard 可見 dataset 列表 |
| Dataset Profile | Dashboard 唯一正式 metadata write surface |
| Design Browse | active dataset 內的 dataset-local `DesignScope` list |
| Design Scope Lifecycle | create / rename / merge / archive / delete gating 與 stale `design_id` resolution |
| Target Design Scope | Data Ingestion 與 Simulation publication 使用的 explicit existing-scope / create-new contract |
| Trace Surface | trace metadata list、sweep-aware filter projection、single-trace preview、trace edit payload、single / batch delete gating |
| Tagged Core Metrics Summary | Dashboard 唯讀摘要 |
| Result Handles | 指向 persisted artifacts / trace payload 的 result refs |

## Dataset Catalog Contract

dataset catalog 至少必須支援：

| Field | Meaning |
| --- | --- |
| `dataset_id` | dataset identity |
| `name` | display name |
| `visibility_scope` | `local`, `private` or `workspace` |
| `lifecycle_state` | `active`, `archived`, `deleted` |
| `device_type` | dataset profile summary |
| `updated_at` | freshness summary |
| `allowed_actions` | select / update profile / publish / archive 等可用動作 |

### Catalog rules

1. local mode 的 catalog 只列出 `Local Space` datasets；online mode 的 catalog 只能列出對 active workspace 可見的 datasets。
2. `active_dataset` 切換必須使用此 catalog 的 stable identity。
3. catalog row 只提供 summary-safe 欄位，不得內含 trace payload。
4. Dataset Catalog is the browse and selection surface for dataset identity, lifecycle state, visibility, and allowed actions.

## Dataset Profile Contract

backend 必須支援 Dashboard 對應的 profile 讀寫：

| Field | Meaning |
| --- | --- |
| `dataset_id` | active dataset identity |
| `device_type` | dataset profile device type |
| `capabilities[]` | dataset capability labels |
| `source` | `manual`, `inferred`, `imported` 等 profile source |
| `updated_at` | profile freshness |

!!! warning "Single write entry"
    dataset profile 的正式可寫入口只服務 Dashboard 類型 surface。
    Raw Data Browser、Simulation Workbench 與 Analysis Workbench 不應提供等價 metadata write。

## Design Browse Contract

`Raw Data Browser` 與 Analysis Workbench 選擇的是 active dataset 內的 `design_id`。
Data Ingestion 與 Simulation publication 使用 `Target Design Scope` selector，但 backend/domain canonical resource name 仍是 `DesignScope`。

| Field | Meaning |
| --- | --- |
| `design_id` | dataset-local design identity |
| `dataset_id` | parent dataset |
| `name` | design label |
| `lifecycle_state` | `active`, `archived`, `deleted` |
| `redirect_design_id` | stale-link / merge redirect target；無 redirect 時為 `null` |
| `source_coverage` | source summary / provenance coverage |
| `compare_readiness` | `ready`, `inspect_only`, `blocked` |
| `trace_count` | trace metadata row count |
| `allowed_actions` | row-level lifecycle gating，例如 rename / merge / archive / delete |
| `mutation_policy_summary` | UI-safe lifecycle restriction summary |
| `updated_at` | freshness summary |

### Design browse rules

1. `design_id` 只在對應 `dataset_id` 內保證穩定。
2. normal browse / target selectors 預設只列 `active` scopes；archived scopes 只能在 explicit history / stale-link context 顯示。
3. design browse 預設為 cursor-based。
4. 切換 dataset 後，design browse 必須整批 rebinding。
5. successful trace delete responses 必須同時回傳更新後的 design browse row，讓 Raw Data Browser 可立即同步 `trace_count` 與 compare/browse readiness。

## Design Scope Lifecycle Contract

| Operation | Backend-owned behavior | Minimum response |
| --- | --- | --- |
| create | create active `DesignScope` inside one dataset and enforce active-name uniqueness | new design browse row |
| rename | update display `name` without changing `design_id` | updated design browse row |
| merge | re-parent source design-scoped metadata to target, archive source and set redirect | source archived row, target updated row, recompute / invalidation summary |
| archive | remove scope from default target selectors while preserving history and optional redirect | archived row |
| delete | mark terminal soft state when backend policy allows; no frontend physical purge | deleted / tombstone summary |

### Lifecycle ownership rules

1. backend is the only authority that creates `design_id`, changes `lifecycle_state`, writes `redirect_design_id`, or re-parents design-scoped records.
2. frontend may request lifecycle actions and render returned rows, but must not rewrite `design_id` locally.
3. archive / delete availability must come from `allowed_actions` and `mutation_policy_summary`, not frontend inference from trace counts.
4. `DesignScope.name` is a display label; matching an existing scope by free-text name is not an authority rule.

## Target Design Scope Contract

Data Ingestion and Simulation publication must bind output to an explicit target decision.

| Mode | Request contract | Backend rule |
| --- | --- | --- |
| existing target | `dataset_id + design_id` | validate active scope and attach imported / published records to that scope |
| create-new target | `dataset_id + requested_name` plus create intent | create active scope first, then attach records to the new `design_id` |
| invalid / archived target | request carries `design_id` that is not active | reject with target-scope error and optional redirect summary |

!!! warning "No hidden auto-match"
    A free-text design name is only a create-new default.
    Backend must not silently treat a name as an existing target unless the request carries the explicit existing `design_id`.

## Design Scope Merge Contract

| Concern | Rule |
| --- | --- |
| Scope boundary | source and target must be different active scopes under the same `dataset_id` |
| Re-parented records | traces、trace batches、trace-batch links、analysis runs、result artifacts、derived parameters、design assets、design-scoped summaries / read models |
| Source lifecycle | source scope becomes `archived` and carries `redirect_design_id=target_design_id` |
| Target refresh | target row must reflect refreshed or invalidated `source_coverage`、`trace_count`、`compare_readiness`、`collection_projection`、analysis readiness and tagged metrics summaries |
| TraceStore | physical payload paths may remain unchanged; `store_ref` is opaque backend-owned locator |
| Conflict handling | backend must reject trace identity collisions and return explicit conflict details for non-coalescible design assets |

TraceStore physical paths are opaque Backend-owned locators. Application code and Python Notebook helpers may display handles or use read-only file paths for analysis when explicitly provided, but they must not infer publication authority from physical path structure.

### Merge response minimum

| Field | Meaning |
| --- | --- |
| `operation` | `merged` |
| `dataset_id` | dataset boundary |
| `source_design` | archived source row with redirect |
| `target_design` | updated active target row |
| `reparented_counts` | counts by record family |
| `recompute_status` | refreshed / invalidated materialized summaries |
| `warnings[]` | optional conflict / stale-link notes |

## Deep Link And Stale Design Scope Resolution

| Input state | Backend response rule |
| --- | --- |
| active `design_id` | return normal design row / trace browse |
| archived `design_id` with redirect | return `design_scope_redirected` metadata and target design summary |
| archived `design_id` without redirect | return archived-state summary and no normal target selection |
| deleted `design_id` | return tombstone / not-found style response; do not create replacement scope |

## Trace Surface Contract

trace surface 必須嚴格拆成以下 path families：

1. **Trace Metadata List Path**
2. **Trace Preview Path**
3. **Trace Edit Path**
4. **Trace Mutation Path**

!!! warning "Preview is not edit authority"
    `Trace Preview Path` 只服務 single-trace preview。
    sampled preview payload 不得直接被當作 numeric edit authority。

### Trace metadata list minimum fields

| Field | Meaning |
| --- | --- |
| `trace_id` | trace identity |
| `dataset_id` | parent dataset |
| `design_id` | parent design scope |
| `family` | `s_matrix`, `y_matrix`, `z_matrix` |
| `parameter` | observable parameter |
| `representation` | `real`, `imaginary`, `magnitude`, `phase` |
| `trace_mode_group` | `base`, `sideband`, `all` |
| `source_kind` | `circuit_simulation`, `layout_simulation`, `measurement` |
| `stage_kind` | `raw`, `preprocess`, `postprocess` |
| `ndim` | canonical axis rank summary |
| `shape` | persisted ND grid shape summary |
| `axes_summary` | UI-safe axis summary；至少指出 trace 是否為 1D / ND 與可見 axis names |
| `axis_signature` | deterministic coordinate/hash summary；供 caching / collection derivation / deep-link safety 使用 |
| `available_sweep_axes[]` | analysis / compare 可用的 structured sweep axis names |
| `collection_projection` | optional scientific grouping / collection summary；供 Analysis Workbench 等 consumer 作為 filter / grouping 提示 |
| `provenance_summary` | UI-safe provenance label |
| `allowed_actions` | row-level mutation gating，至少包含 `edit`、`delete` |
| `mutation_policy_summary` | UI-safe restriction summary；說明為何 row 為 mutable / delete-only / read-only |

### Trace preview minimum fields

| Field | Meaning |
| --- | --- |
| `trace_id` | trace identity |
| `axes` | axis metadata |
| `preview_payload` | lightweight preview rows or sampled series |
| `payload_ref` | persisted numeric authority handle |
| `result_handles[]` | optional result / artifact linkage |

!!! warning "Summary-first browse"
    trace metadata list path 只能提供 summary-safe 欄位。
    不得在 list query 時一併回傳大型 numeric payload。

    Full numeric arrays and full coordinate arrays only belong to detail, explorer, ResultView, or export paths with explicit payload bounds.

## Sweep-aware Trace Browse Rules

| Concern | Rule |
| --- | --- |
| Canonical storage | parameter-swept trace 的 authority 仍是 ND `TraceRecord`；trace list 只做 summary / browse projection |
| Point-level browse | implementation 可提供 point / slice read model，但必須能回指 canonical `trace_id`，不得把 projection 當唯一 persisted authority |
| Axis discoverability | trace browse 與 trace detail 至少必須讓 consumer 知道 axis names、是否存在 sweep axes，以及哪些 axes 可供 Analysis Workbench / explorer 使用 |
| Structured filtering | backend 應支援以 family、representation、source、stage、axis name、available sweep axes 等 structured characteristics 篩選 traces |
| Summary-safe sweep filtering | 支援 axis-name / collection-level / summary-safe filters；coordinate-value / range filtering 需要明確的 coordinate-domain summary contract，不得預設打開 dense coordinates |
| Collection projection | backend 可回傳 UI-safe `collection_projection`，表示由 shared axes / lineage 派生的 scientific grouping；但它是 read model，不取代 trace identity |
| Analysis selection | Analysis Workbench 可以從 selected traces 派生 collection；raw checkbox list 不是最終 scientific model |

## Materialized Metadata Summary Rules

query / filter / readiness surface 應依賴 metadata DB / read model 的 materialized summary，而不是每次從 `TraceStore` 打開完整 ND payload。

minimum direction：

| Summary concern | Materialization target |
| --- | --- |
| rank / shape | `ndim`、`shape` |
| axis structure | `axis_names`、`axis_units`、`axis_lengths` |
| sweep filtering | `available_sweep_axes[]` |
| coordinate identity | `axis_signature` 或等價 hash / signature summary |
| scientific typing | `family`、`parameter`、`representation`、`source_kind`、`stage_kind` |
| grouping inputs | batch / lineage / shared-axis summary |
| summary-safe filtering contract | axis-name / collection-level / summary-safe filters；不含 coordinate-value / range filtering |

!!! warning "List paths are summary-first"
    trace list、design browse、analysis readiness 與 filter suggestion path 不得預設載入完整 ND values。
    full numeric arrays 與 full coordinate arrays 只應進入 detail / explorer / result path。

## Axis Responsibility Split

| Surface | Responsibility |
| --- | --- |
| `TraceRecord.axes` | canonical axis identity、axis names、order、units 與 semantic axis meaning |
| `TraceStore` | dense numeric values 與 dense coordinate arrays |
| metadata DB / read model | query-safe axis summary、`ndim`、`shape`、`available_sweep_axes`、`axis_signature` 等 materialized summaries |
| list / filter / readiness path | 只能依賴 summary surface，不得要求打開 dense coordinate arrays |

## Axis Signature Contract

| Concern | Rule |
| --- | --- |
| Semantic role | `axis_signature` 是 canonical axis identity / coordinate structure 的 deterministic summary |
| Allowed uses | cache safety、collection derivation、grouping compatibility checks、deep-link safety |
| Non-goal | 不可把 `axis_signature` 當成 user-facing scientific label，也不可拿它取代 full coordinates |
| Equality meaning | equal signatures 應表示相同 canonical axis structure under this contract |
| Formula | exact signature formula 可保持 backend-owned，但必須 deterministic、可重建，且只依賴 stable axis inputs |

### Trace edit minimum fields

| Field | Meaning |
| --- | --- |
| `trace_id` | stable trace identity |
| `editable_metadata` | backend 允許修改的 summary metadata；例如 `parameter`、`representation`、`provenance_summary` |
| `immutable_summary` | 不可改寫的 trace identity / lineage context |
| `editable_numeric_payload` | dialog 專用 numeric edit payload；必須是完整可提交版本，而不是 sampled preview |
| `recompute_scope` | backend edit path 影響的 dependent summary / derived surface 家族 |
| `allowed_actions` | edit / delete gating |
| `mutation_policy_summary` | origin / provenance 限制的 UI-safe 說明 |

## Trace Mutation Rules

| Concern | Rule |
| --- | --- |
| Stable identity | `trace_id` 是唯一 trace identity；successful edit 必須維持同一個 `trace_id` |
| Editable scope | single-trace edit 只允許修改 numeric payload 與 backend 明確允許的 UI-safe summary metadata |
| Immutable scope | `trace_id`、`dataset_id`、`design_id`、`family`、`trace_mode_group`、`source_kind`、`stage_kind`、`payload_ref` authority handle 與 `result_handles[]` 不可由 mutation 改寫 |
| Edit invalidation obligation | 若 numeric edit 或 editable metadata 會影響 axis structure、coordinate identity、materialized summaries、collection derivation、analysis readiness 或 persisted analysis/result truth，backend 必須同步 re-materialize 或 invalidate 這些依賴面 |
| Minimum downstream scope | edit path 至少必須處理 `axis_signature`、materialized metadata summary、`collection_projection`、analysis readiness summary 與所有依賴該 trace truth 的 persisted analysis/result surfaces；若 axis / coordinates 改變，axis-derived summaries 也必須重算 |
| Edit availability rule | 若 backend 無法維持上述 invalidation / recomputation contract，該 trace class 的 `allowed_actions.edit` 必須為 `false` |
| Origin restriction | provenance-bearing 或 system-generated traces 可以是 `edit=false`、`delete=true`；frontend 不得自行從 `source_kind` / `stage_kind` 推導，必須依 `allowed_actions` 與 `mutation_policy_summary` 呈現 |
| Audit semantics | edit / delete 是 in-place mutation + audited operation；trace version lineage 若需要獨立保存，必須由專門 contract 定義 |
| Batch scope | 目前只支援 batch delete；batch edit 不屬於本頁 SoT |

## Analysis-facing Trace Projection

Analysis Workbench 需要的不只是 generic trace metadata list，還需要可由 persisted trace structure 派生的 selection / filtering projection。

minimum projection direction：

| Field | Meaning |
| --- | --- |
| `available_families[]` | 可供 analysis compatibility 使用的 family filter |
| `available_representations[]` | 可供 analysis compatibility 使用的 representation filter |
| `available_sweep_axes[]` | 當前 design scope 可見的 structured sweep axis names |
| `collection_projection[]` | optional；由 shared axes / source batch lineage 派生的 scientific grouping summary |
| `analysis_readiness` | optional；某 analysis 是否在當前 trace structure 下可形成有效 collection 的摘要 |
| `summary_filter_scope` | summary-safe filter capability 描述；指出 coordinate-value / range filtering 需要 coordinate-domain summary contract |

!!! tip "Selection remains user-driven"
    使用者仍可明確勾選 traces。
    但 backend 在 Analysis Workbench submit / result query 時，應以 persisted trace structure 解讀那些 selection，而不是只看 checkbox list 本身。

## Collection Projection Contract

| Concern | Rule |
| --- | --- |
| Authority | `collection_projection` 是由 canonical trace structure 派生的 read model，不是獨立 owner |
| Identity | projection 可暴露 deterministic `collection_key`，供 deep-linking、caching 與 UI restoration 使用 |
| Allowed derivation inputs | `collection_key` 與 projection summary 只能來自 dataset/design scope、shared axes / `axis_signature`、lineage / batch grouping，以及 trace set 內在的 scientific typing 等 stable structural inputs |
| Disallowed derivation inputs | analysis-specific readiness outcome、per-analysis compatibility verdict、consumer-specific presentation choice、UI sort/filter state 不可參與 `collection_key` identity |
| Read-model scope | collection projection 不要求 persisted `TraceCollectionRecord` 或可編輯 collection resource |
| Stronger contract path | 若需可儲存 / bookmark / edit 的 collection，必須另定更強 contract，而不是直接把 projection 當成 authority |
| Identity discipline | `collection_key` 可作 projection identity，但不得被當成獨立 persisted resource existence proof |

## Query Efficiency Rules

| Concern | Rule |
| --- | --- |
| List / filter paths | 必須依賴 materialized metadata summary；不得預設讀 full ND values |
| Preview path | 應優先回傳 slice / sampled projection，而不是整個 dense tensor |
| Detail / explorer paths | 只有真正需要時才載入 full coordinate arrays 或 dense numeric slice |
| Dominant access pattern | 目前應優先對齊 `固定 sweep point -> 讀完整 frequency slice` 與 `固定 result axes -> 讀單一 projection` |
| Storage access | chunking / retrieval 應服務主要 scientific access pattern，而不是 generic default |
| Full dense transport | 完整 dense trace payload 不是 list/filter 的預設 contract；只有 detail / export / explicitly defined view 才可回傳 |

## Trace Mutation Path Contract

| Operation | Contract |
| --- | --- |
| Single edit | 以 `dataset_id + design_id + trace_id` 鎖定單筆 trace，提交新的 editable metadata 與完整 numeric payload |
| Single delete | 以同一組 stable identity 刪除單筆 trace；需明確 destructive confirmation |
| Batch delete | 同一個 `dataset_id + design_id` 下提交 `trace_ids[]`；不得跨 design 混刪 |

### Mutation result rules

1. single edit 成功後，backend 至少必須回傳更新後的 trace summary，讓 Raw Data Browser 可立即刷新 row 與 focused preview。
2. single edit 若影響 axis structure、coordinate identity、collection derivation、analysis readiness 或 persisted result truth，backend 必須先完成對應的 re-materialize / invalidate，再回傳成功結果。
3. single delete 成功後，backend 至少必須回傳 `deleted_trace_id`、`deleted_count=1` 與更新後的 design browse row。
4. batch delete 成功後，backend 至少必須回傳 `deleted_trace_ids[]`、`deleted_count` 與更新後的 design browse row。
5. batch delete 必須是單一 request contract；partial silent delete 不可成為預設行為。

### Mutation failure family

| Code | Meaning |
| --- | --- |
| `trace_update_denied` | 目前 session 或 provenance policy 不允許 edit 此 trace |
| `trace_delete_denied` | 目前 session 或 provenance policy 不允許 delete 此 trace |
| `trace_batch_delete_denied` | batch delete 包含不可刪除、不可見或跨 design 的 trace |
| `trace_mutation_conflict` | mutation 目標已變更或目前 payload 與 submit 前提不相容 |
| `trace_not_found` | 指定 trace 不存在於目前 `dataset_id + design_id` scope |

## Tagged Core Metrics Summary

Dashboard 顯示的 `Tagged Core Metrics` 屬於唯讀摘要 surface。

| Field | Meaning |
| --- | --- |
| `metric_id` | metric identity |
| `label` | display name |
| `source_parameter` | source parameter label |
| `designated_metric` | target metric name |
| `tagged_at` | tagging time |

!!! tip "Read / Write split"
    `Tagged Core Metrics` 的讀取摘要屬於本頁。
    identify / tagging mutation 仍由 [Analysis Results](characterization-results.md) 定義。

## Result Handles

Result handles connect tasks, artifacts, traces, published result views, and provenance-bearing result browsing.

They are consumed by ResultView API and Application workbenches after Backend publication. They are not Runner manifests and not raw Zarr payloads.

| Concern | Rule |
| --- | --- |
| Authority | Backend publication creates and registers result handles |
| Consumers | Simulation Workbench, Analysis Workbench, Raw Data Browser, Python Notebook, and ResultView API |
| Payload boundary | handles point to published records, previews, projections, or locators; they do not carry full ND arrays |
| Provenance | handles preserve task/artifact/trace lineage needed for result browsing and analysis recovery |

## Dataset Activation Pairing

| Concern | Rule |
| --- | --- |
| Dataset browse | 只列出對 active workspace 可見的 datasets |
| Design browse | 僅在 active dataset 內列出 design scopes |
| Trace browse | 必須同時綁定 `dataset_id + design_id` |
| Profile write | 必須對應 active dataset，不接受 page-local 假 dataset |
| Tagged metrics summary | 隨 active dataset 切換而一起切換 |

## Request / Response Examples

!!! example "Visible dataset catalog"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "dataset_id": "ds_xy_001",
            "name": "FloatingQubitWithXYLine Post 0308_1819",
            "visibility_scope": "workspace",
            "lifecycle_state": "active",
            "device_type": "transmon",
            "updated_at": "2026-03-14T10:20:00Z",
            "allowed_actions": {
              "select": true,
              "update_profile": true,
              "publish": false,
              "archive": true
            }
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

!!! example "Dataset profile read"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "dataset_id": "ds_xy_001",
        "device_type": "transmon",
        "capabilities": ["analysis", "simulation_review"],
        "source": "manual",
        "updated_at": "2026-03-14T10:20:00Z"
      }
    }
    ```

!!! example "Dataset profile update"
    Request:
    ```json
    {
      "dataset_id": "ds_xy_001",
      "device_type": "transmon",
      "capabilities": ["analysis", "simulation_review"]
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "dataset_id": "ds_xy_001",
        "device_type": "transmon",
        "capabilities": ["analysis", "simulation_review"],
        "source": "manual",
        "updated_at": "2026-03-14T10:22:00Z"
      }
    }
    ```

!!! example "Design browse within active dataset"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "design_id": "design_flux_scan_a",
            "dataset_id": "ds_xy_001",
            "name": "Flux Scan A",
            "lifecycle_state": "active",
            "redirect_design_id": null,
            "source_coverage": {
              "measurement": 2,
              "layout_simulation": 1
            },
            "compare_readiness": "ready",
            "trace_count": 18,
            "allowed_actions": {
              "rename": true,
              "merge": true,
              "archive": true,
              "delete": false
            },
            "mutation_policy_summary": "Active design scope with persisted traces.",
            "updated_at": "2026-03-14T10:24:00Z"
          }
        ]
      },
      "meta": {
        "limit": 20,
        "next_cursor": null,
        "prev_cursor": null,
        "has_more": false,
        "filter_echo": {
          "dataset_id": "ds_xy_001"
        }
      }
    }
    ```

!!! example "Design scope merge"
    Request:
    ```json
    {
      "source_design_id": "design_hfss_import_01",
      "target_design_id": "design_flux_scan_a"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "operation": "merged",
        "dataset_id": "ds_xy_001",
        "source_design": {
          "design_id": "design_hfss_import_01",
          "dataset_id": "ds_xy_001",
          "name": "HFSS import 01",
          "lifecycle_state": "archived",
          "redirect_design_id": "design_flux_scan_a"
        },
        "target_design": {
          "design_id": "design_flux_scan_a",
          "dataset_id": "ds_xy_001",
          "name": "Flux Scan A",
          "lifecycle_state": "active",
          "redirect_design_id": null,
          "trace_count": 27
        },
        "reparented_counts": {
          "traces": 9,
          "trace_batches": 1,
          "analysis_runs": 2,
          "result_artifacts": 4,
          "derived_parameters": 3,
          "design_assets": 1
        },
        "recompute_status": {
          "source_coverage": "refreshed",
          "collection_projection": "invalidated",
          "analysis_readiness": "invalidated",
          "tagged_metrics": "refreshed"
        },
        "warnings": []
      }
    }
    ```

!!! example "Trace metadata list"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "trace_id": "trace_101",
            "dataset_id": "ds_xy_001",
            "design_id": "design_flux_scan_a",
            "family": "y_matrix",
            "parameter": "Y_dm_1_2_dm_1_2",
            "representation": "imaginary",
            "trace_mode_group": "base",
            "source_kind": "measurement",
            "stage_kind": "postprocess",
            "ndim": 2,
            "shape": [401, 11],
            "axes_summary": {
              "rank": 2,
              "axis_names": ["frequency", "L_jun"]
            },
            "axis_signature": "axsig_freq_ljun_v1",
            "available_sweep_axes": ["L_jun"],
            "collection_projection": {
              "collection_key": "collection_postprocess_batch4_ljun",
              "kind": "batch_axis_group",
              "group_label": "Postprocess batch #4 · L_jun sweep"
            },
            "provenance_summary": "Y · Post-Processed · batch #4",
            "allowed_actions": {
              "edit": false,
              "delete": true
            },
            "mutation_policy_summary": "Provenance-bearing or system-generated trace; delete is allowed, but edit from the source workflow."
          }
        ]
      },
      "meta": {
        "limit": 50,
        "next_cursor": null,
        "prev_cursor": null,
        "has_more": false
      }
    }
    ```

!!! example "Trace preview"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "trace_id": "trace_101",
        "axes": [
          {"name": "frequency", "unit": "GHz", "length": 401},
          {"name": "L_jun", "unit": "nH", "length": 11}
        ],
        "preview_payload": {
          "kind": "sampled_series",
          "slice_axis": "L_jun",
          "slice_value": 15.0,
          "points": [
            [1.0, 0.014],
            [1.1, 0.018]
          ]
        },
        "payload_ref": {
          "backend": "local_zarr",
          "store_key": "datasets/ds_xy_001/designs/design_flux_scan_a/batches/batch_4.zarr",
          "group_path": "/traces/trace_101",
          "array_path": "values"
        },
        "result_handles": []
      }
    }
    ```

!!! example "Trace edit payload"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "trace_id": "trace_manual_014",
        "dataset_id": "ds_xy_001",
        "design_id": "design_flux_scan_a",
        "editable_metadata": {
          "parameter": "S21",
          "representation": "magnitude",
          "provenance_summary": "Manual import · corrected on 2026-03-25"
        },
        "immutable_summary": {
          "family": "s_matrix",
          "trace_mode_group": "base",
          "source_kind": "measurement",
          "stage_kind": "raw"
        },
        "editable_numeric_payload": {
          "kind": "series_table",
          "columns": [
            {"key": "frequency", "label": "Frequency", "unit": "GHz", "role": "axis"},
            {"key": "value", "label": "Magnitude", "unit": null, "role": "value"}
          ],
          "rows": [
            {"frequency": 1.0, "value": 0.014},
            {"frequency": 1.1, "value": 0.018}
          ]
        },
        "recompute_scope": {
          "materialized_metadata_summary": true,
          "collection_projection": true,
          "analysis_readiness_summary": true,
          "persisted_analysis_results": "invalidate_or_recompute_if_dependent"
        },
        "allowed_actions": {
          "edit": true,
          "delete": true
        },
        "mutation_policy_summary": "Manually ingested raw trace."
      }
    }
    ```

!!! example "Single trace edit"
    Request:
    ```json
    {
      "parameter": "S21_corrected",
      "representation": "magnitude",
      "provenance_summary": "Manual correction · 2026-03-25",
      "numeric_payload": {
        "kind": "series_table",
        "rows": [
          {"frequency": 1.0, "value": 0.014},
          {"frequency": 1.1, "value": 0.019}
        ]
      }
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "operation": "updated",
        "recompute_status": {
          "materialized_metadata_summary": "refreshed",
          "collection_projection": "refreshed",
          "analysis_readiness_summary": "refreshed",
          "dependent_results": "invalidated"
        },
        "trace": {
          "trace_id": "trace_manual_014",
          "dataset_id": "ds_xy_001",
          "design_id": "design_flux_scan_a",
          "family": "s_matrix",
          "parameter": "S21_corrected",
          "representation": "magnitude",
          "trace_mode_group": "base",
          "source_kind": "measurement",
          "stage_kind": "raw",
          "provenance_summary": "Manual correction · 2026-03-25",
          "allowed_actions": {
            "edit": true,
            "delete": true
          },
          "mutation_policy_summary": "Manually ingested raw trace."
        }
      }
    }
    ```

!!! example "Batch delete"
    Request:
    ```json
    {
      "trace_ids": ["trace_manual_014", "trace_manual_015"]
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "operation": "deleted",
        "dataset_id": "ds_xy_001",
        "design_id": "design_flux_scan_a",
        "deleted_trace_ids": ["trace_manual_014", "trace_manual_015"],
        "deleted_count": 2,
        "design": {
          "design_id": "design_flux_scan_a",
          "dataset_id": "ds_xy_001",
          "name": "Flux Scan A",
          "lifecycle_state": "active",
          "redirect_design_id": null,
          "source_coverage": {
            "measurement": 1,
            "layout_simulation": 1
          },
          "compare_readiness": "ready",
          "trace_count": 16,
          "updated_at": "2026-03-26T03:28:00Z"
        }
      }
    }
    ```

!!! example "Tagged core metrics summary"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "dataset_id": "ds_xy_001",
        "metrics": [
          {
            "metric_id": "metric_mode_1_frequency",
            "label": "Mode 1 Frequency",
            "source_parameter": "L_q",
            "designated_metric": "mode_1_frequency",
            "tagged_at": "2026-03-14T10:24:00Z"
          }
        ]
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
| --- | --- | --- |
| `dataset_not_found` | `not_found` | dataset 不存在 |
| `dataset_not_visible_in_workspace` | `permission_denied` | dataset 不可見於 active workspace |
| `dataset_profile_update_denied` | `permission_denied` | session 無 dataset metadata write 權限 |
| `dataset_profile_invalid` | `validation_error` | device type 或 capability payload 不符合 contract |
| `design_not_found` | `not_found` | dataset 內找不到 design scope |
| `design_scope_name_conflict` | `validation_error` | active design scope name 與同 dataset 內現有 active scope 衝突 |
| `target_design_scope_required` | `validation_error` | ingest / publication request 未提供 existing target 或 create-new intent |
| `target_design_scope_invalid` | `validation_error` | target scope 不屬於 dataset、不是 active，或不可見 |
| `design_scope_redirected` | `stale_reference` | stale `design_id` 已 archived 並指向 target scope |
| `design_scope_merge_denied` | `permission_denied` | session 或 lifecycle policy 不允許 merge |
| `design_scope_merge_conflict` | `conflict` | merge 遇到不可自動處理的 trace / asset / summary 衝突 |
| `trace_not_found` | `not_found` | trace detail 指向不存在 trace |
| `trace_payload_not_ready` | `task_not_ready` | trace payload 尚未 materialize |

## Related

- [Dashboard](../frontend/workspace/dashboard.md)
- [Raw Data Browser](../frontend/workspace/raw-data-browser.md)
- [Frontend Reference](../frontend/index.md)
- [Analysis Results](characterization-results.md)
- [Product Async Contracts](../../architecture/product-async-contracts.md)
- [ResultView API](result-view-api.md)
- [Dataset / Design / Trace Schema](../../data-formats/dataset-record.md)
- [Analysis Result](../../data-formats/analysis-result.md)
- [Data Handling](../../guardrails/code-quality/data-handling.md)
