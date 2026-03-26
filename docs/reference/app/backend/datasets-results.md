---
aliases:
  - Backend Datasets Results Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Backend dataset catalog、design browse、trace browse / preview / mutation、dataset profile、tagged core metrics 與 provenance-bearing result handles
version: v0.10.0
last_updated: 2026-03-26
updated_by: codex
---

# Datasets & Results

本頁定義 Dashboard、Header dataset switcher、Raw Data Browser、Characterization 與部分 Result View 依賴的 dataset / design / trace / result surface。

!!! info "Surface Boundary"
    本頁負責 dataset catalog、dataset profile、dataset-local design browse、trace metadata list、trace preview / edit payload、trace mutation gating、tagged core metrics summary 與 provenance-bearing result handles。
    task lifecycle、analysis-specific artifact manifest 與 audit query 不屬於本頁責任。

!!! tip "Primary Consumers"
    主要消費者是 [Dashboard](../frontend/workspace/dashboard.md)、[Raw Data Browser](../frontend/workspace/raw-data-browser.md)、[Characterization](../frontend/research-workflow/characterization.md) 與 [Header](../frontend/shared-shell/header.md)。

## Coverage

| Surface | Meaning |
| --- | --- |
| Dataset Catalog | Header / Dashboard 可見 dataset 列表 |
| Dataset Profile | Dashboard 唯一正式 metadata write surface |
| Design Browse | active dataset 內的 dataset-local design scope list |
| Trace Surface | trace metadata list、single-trace preview、trace edit payload、single / batch delete gating |
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
    Raw Data Browser、Simulation 與 Characterization 不應提供等價 metadata write。

## Design Browse Contract

`Raw Data Browser` 與 `Characterization` 選擇的是 active dataset 內的 `design_id`。

| Field | Meaning |
| --- | --- |
| `design_id` | dataset-local design identity |
| `dataset_id` | parent dataset |
| `name` | design label |
| `source_coverage` | source summary / provenance coverage |
| `compare_readiness` | `ready`, `inspect_only`, `blocked` |
| `trace_count` | trace metadata row count |
| `updated_at` | freshness summary |

### Design browse rules

1. `design_id` 只在對應 `dataset_id` 內保證穩定。
2. design browse 預設為 cursor-based。
3. 切換 dataset 後，design browse 必須整批 rebinding。
4. successful trace delete responses 必須同時回傳更新後的 design browse row，讓 Raw Data Browser 可立即同步 `trace_count` 與 compare/browse readiness。

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

### Trace edit minimum fields

| Field | Meaning |
| --- | --- |
| `trace_id` | stable trace identity |
| `editable_metadata` | backend 允許修改的 summary metadata；例如 `parameter`、`representation`、`provenance_summary` |
| `immutable_summary` | 不可改寫的 trace identity / lineage context |
| `editable_numeric_payload` | dialog 專用 numeric edit payload；必須是完整可提交版本，而不是 sampled preview |
| `allowed_actions` | edit / delete gating |
| `mutation_policy_summary` | origin / provenance 限制的 UI-safe 說明 |

## Trace Mutation Rules

| Concern | Rule |
| --- | --- |
| Stable identity | `trace_id` 是唯一 trace identity；successful edit 必須維持同一個 `trace_id` |
| Editable scope | single-trace edit 只允許修改 numeric payload 與 backend 明確允許的 UI-safe summary metadata |
| Immutable scope | `trace_id`、`dataset_id`、`design_id`、`family`、`trace_mode_group`、`source_kind`、`stage_kind`、`payload_ref` authority handle 與 `result_handles[]` 不可由 mutation 改寫 |
| Origin restriction | provenance-bearing 或 system-generated traces 可以是 `edit=false`、`delete=true`；frontend 不得自行從 `source_kind` / `stage_kind` 推導，必須依 `allowed_actions` 與 `mutation_policy_summary` 呈現 |
| Audit semantics | edit / delete 是 in-place mutation + audited operation；trace version lineage 若需要獨立保存，必須由專門 contract 定義 |
| Batch scope | 目前只支援 batch delete；batch edit 不屬於本頁 SoT |

## Trace Mutation Path Contract

| Operation | Contract |
| --- | --- |
| Single edit | 以 `dataset_id + design_id + trace_id` 鎖定單筆 trace，提交新的 editable metadata 與完整 numeric payload |
| Single delete | 以同一組 stable identity 刪除單筆 trace；需明確 destructive confirmation |
| Batch delete | 同一個 `dataset_id + design_id` 下提交 `trace_ids[]`；不得跨 design 混刪 |

### Mutation result rules

1. single edit 成功後，backend 至少必須回傳更新後的 trace summary，讓 Raw Data Browser 可立即刷新 row 與 focused preview。
2. single delete 成功後，backend 至少必須回傳 `deleted_trace_id`、`deleted_count=1` 與更新後的 design browse row。
3. batch delete 成功後，backend 至少必須回傳 `deleted_trace_ids[]`、`deleted_count` 與更新後的 design browse row。
4. batch delete 必須是單一 request contract；partial silent delete 不可成為預設行為。

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
    identify / tagging mutation 仍由 [Characterization Results](characterization-results.md) 定義。

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
        "capabilities": ["characterization", "simulation_review"],
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
      "capabilities": ["characterization", "simulation_review"]
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "dataset_id": "ds_xy_001",
        "device_type": "transmon",
        "capabilities": ["characterization", "simulation_review"],
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
            "source_coverage": {
              "measurement": 2,
              "layout_simulation": 1
            },
            "compare_readiness": "ready",
            "trace_count": 18,
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
          {"name": "frequency", "unit": "GHz", "length": 401}
        ],
        "preview_payload": {
          "kind": "sampled_series",
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
| `trace_not_found` | `not_found` | trace detail 指向不存在 trace |
| `trace_payload_not_ready` | `task_not_ready` | trace payload 尚未 materialize |

## Related

- [Dashboard](../frontend/workspace/dashboard.md)
- [Raw Data Browser](../frontend/workspace/raw-data-browser.md)
- [Characterization](../frontend/research-workflow/characterization.md)
- [Characterization Results](characterization-results.md)
- [Dataset / Design / Trace Schema](../../data-formats/dataset-record.md)
- [Analysis Result](../../data-formats/analysis-result.md)
