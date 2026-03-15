---
aliases:
  - Backend Schemdraw Render
  - Schemdraw Render Service
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/app-reference
status: draft
owner: docs-team
audience: team
scope: Schemdraw render service 的 three-step flow、request/response、diagnostics、authoritative syntax/live preview 與 advanced mapping envelope 契約
version: v0.6.0
last_updated: 2026-03-16
updated_by: codex
---

# Schemdraw Render

本頁定義 `Schemdraw` workspace 依賴的 backend render service 契約。

!!! info "Surface Boundary"
    本契約負責接收 frontend source snapshot、linked schema context 與 optional advanced mapping、進行 authoritative syntax check、執行 controlled render，並回傳 diagnostics 與 SVG preview。
    canonical definition persistence、task queue 建立與 streaming transport 不屬於本頁責任。

!!! warning "Backend Is The Syntax And Preview Authority"
    frontend 可以有本地 editor cues，但正式 syntax check、runtime validation 與 live preview 結果必須以 backend response 為準。

## Transport

| Item | Rule |
|---|---|
| Method | `POST` |
| Endpoint | `/api/backend/schemdraw/render` |
| Content Type | `application/json` |
| Response Type | `application/json` |
| Transport style | request / response |

## Three-step Processing Flow

1. **Frontend edits source**
   使用者在 editor 中修改 Python source、linked schema，必要時再提供 optional advanced mapping。
2. **Frontend sends snapshot**
   debounce 後送出 request；或由 `Render Now` 立即送出。
3. **Backend validates and renders**
   backend 做 request validation、syntax validation、entrypoint validation、controlled render execution，最後回傳 diagnostics 與 preview。

!!! tip "HTTP-first"
    這條 workflow 的正式 transport 是 HTTP request / response。
    若未來新增 WebSocket，也只能是增量能力，不能推翻本頁 contract。

## Request Contract

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source_text` | `string` | required | Schemdraw Python source |
| `relation_config` | `object | null` | optional | optional advanced mapping / relation metadata object |
| `linked_schema` | `object | null` | optional | linked schema metadata snapshot |
| `document_version` | `integer` | required | editor version |
| `request_id` | `string` | required | single render request identity |
| `render_mode` | `string` | optional | `debounced` or `manual` |

linked schema object baseline：

| Field | Meaning |
|---|---|
| `definition_id` | persisted definition identity |
| `workspace_id` | visibility boundary summary |
| `name` | display label |
| `source_hash` | optional freshness hint |

## Validation Layers

| Layer | Meaning |
|---|---|
| Request validation | body shape 與必要欄位是否合法 |
| Relation validation | optional advanced mapping 是否符合最低 shape |
| Syntax validation | Python source 是否可 parse |
| Entrypoint validation | `build_drawing(relation)` 是否存在且可呼叫 |
| Runtime render | controlled execution 是否成功產生 preview |

## Response Contract

| Field | Type | Required | Meaning |
|---|---|---|---|
| `request_id` | `string` | required | 對應 request |
| `document_version` | `integer` | required | 對應 editor version |
| `status` | `string` | required | `rendered`, `blocked`, `syntax_error`, `runtime_error` |
| `svg` | `string | null` | optional | render success 時的 SVG |
| `diagnostics` | `array` | required | 結構化 diagnostics |
| `cursor_position` | `object | null` | optional | pen cursor / pointer metadata |
| `probe_points` | `array` | optional | probe point metadata |
| `render_time_ms` | `number | null` | optional | render latency |
| `preview_metadata` | `object | null` | optional | SVG 尺寸、viewBox、backend preview summary |

## Diagnostics Item

| Field | Meaning |
|---|---|
| `severity` | `error`, `warning`, `info` |
| `code` | machine-readable code |
| `message` | user-readable message |
| `source` | `request`, `relation_config`, `python_syntax`, `render_runtime` |
| `blocking` | 是否阻止 render |
| `line` / `column` | 若可定位，回傳 source location |

## Backend Guardrails

| Rule | Meaning |
|---|---|
| Linked schema visibility check | backend 必須拒絕目前 session 不可見的 linked schema |
| No implicit task creation | render request 不能靜默建立 persisted task |
| No implicit save | render request 不會保存 source / advanced mapping |
| Controlled runtime only | backend 僅允許受控 entrypoint 與受限 import boundary |
| Mapping stays secondary | backend 可驗證 `relation_config`，但它只屬於 optional advanced mapping，不應成為 page primary workflow 的理由 |

## Delivery Rules

| Rule | Meaning |
|---|---|
| Formal errors stay in envelope | syntax / runtime errors 應回正式 response envelope，而不是 transport failure |
| No implicit persistence | source、advanced mapping 與 SVG 都不能被默默保存 |
| Latest-only safe | response 必須帶 `request_id` 與 `document_version`，讓 frontend 丟棄 stale result |
| Cancellation is best-effort | 新 request 來時可嘗試取消舊 render |

## Request / Response Examples

!!! example "Render request"
    Request:
    ```json
    {
      "source_text": "import schemdraw\n\ndef build_drawing(relation):\n    ...",
      "relation_config": {
        "tag": "draft",
        "labels": {
          "P1": "input"
        }
      },
      "linked_schema": {
        "definition_id": "def_lc_12",
        "workspace_id": "ws_lab_a",
        "name": "Series LC Resonator"
      },
      "document_version": 14,
      "request_id": "req_sdraw_14",
      "render_mode": "debounced"
    }
    ```

!!! example "Syntax error response"
    ```json
    {
      "ok": false,
      "error": {
        "code": "schemdraw_syntax_error",
        "category": "validation_error",
        "message": "The Schemdraw source cannot be parsed.",
        "retryable": false,
        "details": {
          "line": 12,
          "column": 8
        },
        "debug_ref": "req_sdraw_14"
      }
    }
    ```

!!! example "Rendered response"
    ```json
    {
      "ok": true,
      "data": {
        "request_id": "req_sdraw_14",
        "document_version": 14,
        "status": "rendered",
        "svg": "<svg>...</svg>",
        "diagnostics": [],
        "preview_metadata": {
          "width": 1200,
          "height": 640,
          "view_box": "0 0 1200 640"
        }
      }
    }
    ```

## Error Code Contract

| Code | Category | When it applies |
|---|---|---|
| `schemdraw_relation_invalid` | `validation_error` | optional advanced mapping 不符合 contract |
| `schemdraw_linked_schema_not_visible` | `permission_denied` | linked schema 對目前 session 不可見 |
| `schemdraw_syntax_error` | `validation_error` | Python source parse 失敗 |
| `schemdraw_runtime_error` | `task_execution_failed` | controlled render 執行失敗 |

## Related

* [Frontend / Schemdraw](../frontend/research-workflow/schemdraw.md)
* [Backend / Circuit Definitions](circuit-definitions.md)
* [Circuit Netlist](../../data-formats/circuit-netlist.md)
