---
title: "Schemas"
aliases:
  - "Schemas UI"
  - "Circuit Schemas UI"
  - "電路綱要清單介面"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
page_id: app.page.schemas
route: /schemas
status: draft
owner: docs-team
audience: team
scope: "/schemas 頁面的 circuit schema catalog、搜尋/排序/cursor-based browse，以及建立/開啟/刪除契約"
version: v0.7.0
last_updated: 2026-03-23
updated_by: codex
---

# Schemas

本頁定義 Circuit Schema catalog 的瀏覽、搜尋、排序、cursor-based browse、建立、開啟與刪除契約。

!!! info "Page Frame"
    本頁負責 schema catalog、搜尋 / 排序 / cursor-based browse、建立、刪除與開啟 editor。
    source 編輯、preview render 與 simulation execution 不屬於本頁責任。

!!! tip "Shared Shell"
    本頁位於 shared [Header](../shared-shell/header.md) / [Sidebar](../shared-shell/sidebar.md) shell 中，但本頁本身不擁有 dataset 或 task context authority。

!!! info "Workspace-scoped catalog"
    Schema catalog 只列出目前 `Active Workspace` 中可見的 definitions。
    `private` schema 只對 owner、workspace owner 與 admin 可見；`workspace` schema 才是共同清單的一部分。

!!! important "Schema identity display"
    - persisted schema identity 是 UUIDv4-only `definition_id`
    - UI 不得再把 schema identity 描述成 `Definition #...` 這種 compact sequential 編號
    - 同名 schema 必須依 short `Schema ID` + `created_at` 區分；必要時補 owner / workspace context

---

## 使用者目標 (User Goals)

*   **高效檢索**: 在數以百計的 Schema 中快速定位目標。
*   **版本確認**: 根據建立時間或名稱確認最新的開發進度。
*   **便捷管理**: 快速啟動新專案 (New Circuit) 或清理廢棄的電路定義。
*   **流暢對接**: 從清單無縫導向至 `Schema Editor` 或 `Circuit Simulation`。

---

## UI 配置與 組件說明

### 佈局結構 (Layout Structure)

```mermaid
graph LR
    H[Page Header] --> Actions[Primary Actions]
    Actions --> Filters[Search & Sort Bars]
    Filters --> List[Schema List Container]
    List --> Paging[Browse Status]
```

### 關鍵組件清單 (Components)

| ID | 組件 | 功能描述 | 關鍵行為 |
| :--- | :--- | :--- | :--- |
| **C1** | New Circuit Button | 位於頂部，為主要行動按鈕。 | 導向至 Schema 建立流程。 |
| **C2** | Filter Bar | 提供名稱搜尋、欄位排序與方向選擇。 | 觸發列表重新查詢。 |
| **C3** | Schema Item Row | 列表核心，顯示 `name`、short `Schema ID`、`created_at`。 | 支援開啟、編輯與刪除。 |
| **C4** | Browse Controls | 位於底部，控制 cursor-based 的前後段瀏覽。 | 驅動分段載入，同步更新總數與 cursor 狀態。 |

---

## 資料與狀態契約 (Contract)

=== "數據依賴 (Data Dependencies)"
    | 資料 | 來源 | 必要性 | 用途 |
    | :--- | :--- | :---: | :--- |
    | schema summary list | definition summary service | ✅ | 渲染各列摘要。 |
    | total items count | definition summary service | ✅ | 顯示總筆數與 browse summary。 |
    | cursor meta | definition summary service | ✅ | 驅動前後段瀏覽。 |
    | search & sort params | UI State | ✅ | 控制過濾與排序行為。 |
    | active workspace | session surface | ✅ | 限定 catalog 可見範圍。 |
    | capability flags | session surface | ✅ | 決定是否顯示 create / delete affordance。 |

=== "頁面狀態 (States)"
    | 狀態 | 說明 |
    | :--- | :--- |
    | `Default` | 正常顯示清單與控制項。 |
    | `Loading` | 資料更新中，列表顯示載入遮罩。 |
    | `Empty` | 查無資料 (或搜尋後無結果)，顯示對應提示。 |
    | `Error` | 服務請求失敗，於列表區塊顯示錯誤資訊。 |

!!! warning "邊界約束"
    Schema Catalog **禁止**在列表階段預載完整的 Definition Payload。其詳細內容應僅在 Editor 或 Detail 流中按需讀取。

## Schema Identity And Ordering Rules

| Concern | Rule |
|---|---|
| Persisted identity | catalog row 綁定的是 full UUIDv4 `definition_id` |
| Visible label | row 可顯示 short `Schema ID`，但這只是 full UUIDv4 的縮寫 display |
| Same-name rows | 不得用隱含 display order 當唯一區分；至少要顯示 short `Schema ID` + `created_at` |
| Sorting | 使用 `created_at`、`updated_at`、`name` 等欄位；不得使用 `definition_id` 值排序 |
| Open / delete / clone | 仍以 full `definition_id` 作為 action binding；不是以 row order 或 visible short ID 綁定 |

## Workspace And Permission Rules

| Concern | Rule |
|---|---|
| Catalog scope | 僅查詢目前 active workspace 可見的 definitions |
| Create permission | 只有具 `can_manage_definitions` 的 session 才能建立 |
| Delete permission | 由 backend capability 與 ownership 決定；frontend 不自行猜測 |
| Default creation scope | 新建 schema 預設屬於 current active workspace，且預設 `private` |
| Workspace switch | 切換 workspace 後，catalog 必須重查；若目前 editor 目標不再可見，不得假裝仍存在於清單 |

---

## 互動流程 (Interaction Flow)

=== "建立與開啟 (Create/Open)"
    1.  點擊 `New Circuit` → 導向 Editor 建立新檔。
    2.  點擊 `Edit` 或 Row → 導向 Editor 並帶入選定的 full UUIDv4 `definition_id`。

=== "Workspace Rebinding"
    1. Header 切換 active workspace。
    2. 本頁清除舊列表結果並重查新 workspace 的 definition summaries。
    3. 若目前 search/sort/cursor 不再適用，至少清除 cursor 並保留可重用的 filter。

=== "搜尋與排序 (Search/Sort)"
    1.  更新搜尋框或排序選項。
    2.  清除目前 cursor。
    3.  根據新條件刷新列表視圖。

=== "刪除流程 (Delete)"
    1.  點擊 `Delete` → 觸發二次確認視窗。
    2.  成功刪除後，刷新列表並重新校正 cursor 視圖 (如有必要)。

---

## 視覺規範 (Visual Rules)

*   **層次分明**: Page Title 的視覺比重必須顯著高於 Subtitle。
*   **CTA 定位**: `New Circuit` 按鈕應始終位於主要內容區的最上方。
*   **密度一致**: 無論使用 Table 或 Card，short `Schema ID`、`Created At` 與 Action 按鈕在每列中需維持穩定對齊。
*   **反饋定位**: Error 或 Mutation Feedback 應在列表區域附近清晰可見。

---

## 相關參考

*   [Schema Editor](schema-editor.md)
*   [Header](../shared-shell/header.md)
*   [Sidebar](../shared-shell/sidebar.md)
*   [Circuit Simulation](../research-workflow/circuit-simulation.md)
*   [Backend: Circuit Definitions](../../backend/circuit-definitions.md)
*   [Record Format: Circuit Netlist](../../data-formats/circuit-netlist.md)
