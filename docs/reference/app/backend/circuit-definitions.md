---
aliases:
  - Backend Circuit Definitions
  - Circuit Definition Service
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Circuit definition catalog、detail、mutation 與 persisted inspection read model 的 backend reference surface。
version: v0.6.0
last_updated: 2026-03-23
updated_by: codex
---

# Circuit Definitions

本頁定義 frontend `Schemas` / `Schema Editor` 依賴的 backend circuit definition surface。

!!! info "Surface Boundary"
    本頁只定義 definition catalog、detail、mutation 與 persisted inspection read model。
    simulation、schemdraw render 與 characterization run 不屬於本頁責任。

!!! tip "Primary Consumers"
    主要消費者是 [Schemas](../frontend/definition/schemas.md)、[Schema Editor](../frontend/definition/schema-editor.md)、[Schemdraw](../frontend/research-workflow/schemdraw.md) 與 [Circuit Simulation](../frontend/research-workflow/circuit-simulation.md)。

!!! important "UUIDv4-only Schema Identity"
    - `definition_id` 是 persisted schema identity，必須是 full UUIDv4
    - identity 是 opaque，不可從值本身推論建立順序、穩定 display order 或 human ranking
    - UI 若需 readability，可顯示 short `Schema ID`，但 canonical persisted identity 仍是 full UUIDv4
    - 同名 schema 的辨識必須依 short `Schema ID`、`created_at`，以及必要時的 owner / workspace context

!!! warning "No transition period"
    目前 SoT 不承認 legacy numeric definition identity，也不承認 dual-ID compatibility。
    任何 catalog cache、editor route、linked-schema selection、simulation binding 或 task draft，若仍依賴舊 numeric identity，都必須直接 rebuild 成 UUIDv4-only model。

---

## 涵蓋範圍 (Coverage)

| Surface | 說明 |
| :--- | :--- |
| **Definition Catalog List** | 定義目錄列表 |
| **Active Definition Detail** | 啟用中的定義詳情 |
| **CRUD Mutation** | 建立、更新、刪除操作 |
| **Validation** | 驗證通知與摘要 |
| **Output & Preview** | 正規化產出與預覽產物摘要 |

---

## Surface Contracts

=== "Catalog"

    catalog list 最低必須支援以下功能：

    | 功能 | 說明 |
    | :--- | :--- |
    | **搜尋** | 關鍵字查找 |
    | **排序** | 按日期、名稱或其他屬性排序 |
    | **Browse** | 以 cursor-based 方式分段載入大量資料 |
    | **Metadata** | 僅包含 summary-safe 的元資料 |

    catalog request / response baseline：

    | Field | Meaning |
    |---|---|
    | `workspace_id` | 由 active session context 決定；local mode 固定為 `Local Space`，不由 frontend 任意跨 workspace 指定 |
    | `search_query` | optional |
    | `sort_by` / `sort_order` | optional |
    | `limit` | optional |
    | `after` / `before` | optional，cursor-based browse 位置 |
    | `rows[]` | `definition_id`, `name`, `created_at`, optional `updated_at`, `visibility_scope`, `owner_display_name`, `allowed_actions` |
    | `meta.next_cursor` / `meta.prev_cursor` | cursor-based browse meta |
    | `total_count` | 總數摘要 |

=== "Detail"

    單一 definition detail 至少必須提供：

    | 類別 | 包含項目 |
    | :--- | :--- |
    | **Source** | canonical source text |
    | **Identity** | schema name |
    | **Validation** | validation notices, validation summary |
    | **Result** | normalized output, preview artifacts summary |

    detail response 另須至少包含：

    | Field | Meaning |
    |---|---|
    | `definition_id` | persisted schema identity；full UUIDv4 |
    | `workspace_id` / `visibility_scope` | shared visibility boundary；local mode 可固定為 `Local Space` / `local` |
    | `allowed_actions` | `update`, `delete`, `publish`, `clone` 等 |
    | `created_at` | identity disambiguation 與 stable ordering metadata |
    | `updated_at` | concurrency / freshness summary |

=== "Mutation"

    backend 必須支援標準的 CRUD 操作：

    1. **Create**: 建立新 definition
    2. **Update**: 更新既有 definition
    3. **Delete**: 刪除既有 definition

    mutation payload baseline：

    | Mutation | Required fields |
    |---|---|
    | `create` | `name`, `source_text`, optional `visibility_scope`；local mode 預設 `local` |
    | `update` | `definition_id`, `source_text`, optional `name`, optional concurrency token |
    | `delete` | `definition_id` |
    | `publish_to_workspace` | `definition_id` |
    | `clone_private_copy` | `definition_id`, optional `name` |

## Identity And Ordering Contract

| Concern | Contract |
|---|---|
| `definition_id` | full UUIDv4 persisted identity；opaque、不可排序推論 |
| `Schema ID` display | UI convenience only；可取 UUID prefix，但不得取代 full `definition_id` |
| Human ordering | 必須使用 `created_at`、`updated_at`、`name` 等欄位；不得用 `definition_id` 值排序 |
| Same-name disambiguation | 至少顯示 short `Schema ID` + `created_at`；必要時再加 owner / workspace context |
| Selection / mutation binding | catalog、editor、schemdraw、simulation、task submit 全部以 full `definition_id` 綁定 |

## Workspace And Visibility Rules

| Rule | Meaning |
|---|---|
| One workspace per definition | persisted definition 只屬於一個 workspace |
| Default create scope | local mode 預設在 `Local Space` 且 `local`；online mode 預設在 current active workspace 且 `private` |
| Visibility filtering | catalog / detail 僅回傳對目前 session 可見的 definitions |
| Publish is explicit | 只在 online mode 有 `private -> workspace`；local mode 不做 publish / share |

!!! warning "Catalog is Summary-only"
    definition catalog **不得**把完整 definition payload 當成列表回應的一部分。
    list path 只提供 `id`、`name`、`created_at` 與等價 summary 欄位。

!!! warning "Do not use schema identity as display order"
    `definition_id` 的 UUIDv4 值不具人類排序意義。
    若 UI 需要顯示「最新」或「較舊」schema，必須依 `created_at` / `updated_at` 等時間欄位計算。

!!! warning "Persisted Preview Authority"
    `validation notices`、`normalized output` 與 `preview artifacts` 只代表**最後一次成功儲存後**的 persisted state。
    backend 不得把未儲存的 editor draft 當成正式的 preview authority。

!!! tip "Persistence Sync"
    mutation 成功後，frontend 重新讀取 detail 時，必須能看到最新的 persisted inspection result。

!!! warning "Destructive Mutation"
    刪除 definition 是 **destructive mutation**。
    backend 應維持明確的成功 / 失敗回應，不得以靜默忽略取代。

---

## Delivery Rules

| 項目 | 規則 |
| :--- | :--- |
| **Source of Truth** | canonical source text 是唯一的寫入 authority。 |
| **Derived Preview** | normalized output 與 preview artifacts 是 read model，不可反向寫回 source。 |
| **Mutation Refresh** | create / update / delete 後，catalog 與 detail 都必須可重新讀回一致結果。 |
| **Reuse** | 同一 definition detail 必須可供 schema editor、schemdraw、circuit simulation 共用。 |

## Request / Response Examples

!!! example "Catalog list"
    Response:
    ```json
    {
      "ok": true,
      "data": {
        "rows": [
          {
            "definition_id": "7b1e4c65-8c3b-4dd0-9a02-7f1cf0cf0f3e",
            "name": "Series LC Resonator",
            "created_at": "2026-03-14T09:20:00Z",
            "updated_at": "2026-03-14T10:15:00Z",
            "visibility_scope": "private",
            "owner_display_name": "Ari",
            "allowed_actions": {
              "update": true,
              "delete": true,
              "publish": true,
              "clone": true
            }
          }
        ],
        "total_count": 1
      }
    }
    ```

!!! example "Update definition"
    Request:
    ```json
    {
      "definition_id": "7b1e4c65-8c3b-4dd0-9a02-7f1cf0cf0f3e",
      "source_text": "{...canonical source...}",
      "name": "Series LC Resonator",
      "concurrency_token": "etag_4"
    }
    ```

    Response:
    ```json
    {
      "ok": true,
      "data": {
        "definition_id": "7b1e4c65-8c3b-4dd0-9a02-7f1cf0cf0f3e",
        "workspace_id": "ws_lab_a",
        "visibility_scope": "private",
        "updated_at": "2026-03-14T10:15:00Z",
        "validation_summary": {
          "status": "valid",
          "notice_count": 0
        }
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
|---|---|---|
| `definition_not_found` | `not_found` | 目標 definition 不存在 |
| `definition_not_visible` | `permission_denied` | definition 對目前 session 不可見 |
| `definition_source_invalid` | `validation_error` | source text 無法通過 validation |
| `definition_conflict` | `conflict` | concurrency token 或 persisted version 衝突 |
| `definition_delete_blocked` | `conflict` | definition 目前不能被刪除 |

---

## Related

- [Schemas](../frontend/definition/schemas.md)
- [Schema Editor](../frontend/definition/schema-editor.md)
- [Schemdraw](../frontend/research-workflow/schemdraw.md)
- [Circuit Simulation](../frontend/research-workflow/circuit-simulation.md)
- [Circuit Netlist](../../data-formats/circuit-netlist.md)
