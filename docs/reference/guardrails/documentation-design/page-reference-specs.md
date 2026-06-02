---
aliases:
  - "Page Reference Specs"
  - "App Page Reference"
  - "頁面規格文件"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/documentation
status: stable
owner: docs-team
audience: team
scope: "App frontend pages 技術文件的固定骨架、命名規則、引用方式與驗收標準"
version: v0.3.0
last_updated: 2026-03-13
updated_by: team
---

# Page Reference Specs

本文件定義 App frontend pages 技術文件的正式寫法。

這類文件不是需求文件，不是設計理念散文，也不是實作筆記。
它們是 **Page Reference Spec**：
直接描述某一頁現在應該長什麼樣、做什麼事、怎麼互動、依賴哪些正式 contract，以及什麼叫做實作完成。

---

## 適用範圍

本規範適用於：

- `docs/reference/app/frontend/` 下的 App frontend page reference
- 任何以 route / page 為單位的正式 UI reference 頁

本規範不適用於：

- Tutorials
- How-to
- Explanation
- migration 背景說明
- implementation notes / PR notes

---

## 核心原則

| 原則 | 說明 |
|------|------|
| 文件是 SoT | 頁面規格以文件為準，實作必須對齊文件 |
| 描述現在式 | 不寫歷史背景、舊版行為、遷移故事；只寫本頁當前正式規格 |
| 先寫穩定結構 | 先固定頁面目的、區塊順序、互動流程，再寫細節 |
| 人機共讀 | 人類能快速掃描，AI Agent 能穩定抽取欄位 |
| 少講實作，多講契約 | 不先寫 framework / hook / service 類名；先寫 UI contract |
| 一頁一格式 | 所有 page reference 採同一套骨架，降低理解成本 |

!!! important "Reference 邊界"
    Page Reference Spec 屬於 `Reference`。
    它描述的是正式頁面契約，不是設計理由，也不是操作教學。

---

## 推薦位置與命名

App frontend pages 技術文件建議放在：

- `docs/reference/app/frontend/pages/<route-name>.md`

若既有專案仍維持較扁平的 frontend reference 結構，應逐步整理到 `app/frontend/` 下，再依需要細分子目錄。

頁面標題應優先對齊 sidebar / nav label。
route 應保留在 frontmatter 的 `route` 欄位與正文 identity 區塊，不應拿 route 直接取代頁名。

frontmatter 建議至少包含：

| Property | Required | Example |
|----------|----------|---------|
| `title` | ✅ | `Circuit Simulation` |
| `page_id` | ✅ | `app.page.circuit_simulation` |
| `route` | ✅ | `/circuit-simulation` |
| `tags` | ✅ | `diataxis/reference`, `audience/team`, `sot/true`, `topic/ui` |
| `owner` | ✅ | `team` / `team/person` |
| `status` | ✅ | `draft` / `stable` |

---

## 固定骨架

每一頁 App page reference 必須固定成以下 8 個區塊：

1. `Purpose`
2. `User Goal`
3. `Layout Structure`
4. `Component Inventory`
5. `Data & State Contract`
6. `Interaction Flows`
7. `Visual Rules`
8. `Acceptance Checklist`

這 8 個區塊是最小完整骨架，不得任意省略。

---

## 區塊定義

### 1. Purpose

回答這頁是什麼、負責什麼。

應寫：

- 本頁負責的正式範圍
- 本頁承接的平台能力

不應寫：

- 設計動機故事
- 技術框架選型理由

### 2. User Goal

回答使用者進這頁要完成什麼。

應包含：

- 主要目標
- 非目標

### 3. Layout Structure

回答畫面骨架與區塊順序。

至少應包含：

- shell 區塊
- main content order
- 簡化 UI tree

優先使用：

- 表格
- 有序列表
- 簡單 tree block

### 4. Component Inventory

回答有哪些關鍵元件，以及每個元件的責任。

至少應包含：

- 元件 ID
- 元件名稱
- 類型
- 位置
- 作用
- 關鍵行為

跨頁共用元件若已有獨立 spec，應引用，不要重複定義。

### 5. Data & State Contract

回答本頁依賴哪些正式資料與狀態。

至少應包含：

- data dependencies
- page state
- UI states（`loading` / `empty` / `error` / `partial` / `default`）

本節應使用正式 contract 名稱，不得直接引用 implementation-local 類名作為規格本體。

### 6. Interaction Flows

回答操作路徑與事件結果。

每個 flow 應寫成明確步驟，例如：

1. 使用者做什麼
2. state / request 發生什麼
3. UI 更新什麼
4. 成功 / 失敗後如何處理

### 7. Visual Rules

回答視覺層級與版面關係。

應寫：

- hierarchy
- CTA placement
- density
- empty-state alignment
- responsive rules

不應寫：

- 像素級 spacing
- 純實作層 hover workaround
- 框架特定 style hook

### 8. Acceptance Checklist

回答什麼叫做實作完成。

應使用可驗收條列，例如：

- [ ] 區塊順序正確
- [ ] 主要元件齊全
- [ ] UI states 完整
- [ ] interaction flows 可走通
- [ ] 只透過正式 contract 存取資料

---

## 可選附加區塊

### Related Contracts

若頁面依賴共享 contract，應引用而不是重複定義。

例如：

- Session / Workspace Contract
- Task Runtime / Task Execution Contract
- Dataset / Design / Trace Schema
- Analysis Result Contract

### Runtime Notes

只有 simulation / task / characterization 這類研究 workflow 頁面可以額外加 `Runtime Notes`。

用途是補充：

- task attachment
- refresh / reconnect recovery
- persisted contract rebuild
- failure display

這一節只在 runtime-sensitive pages 使用，不是所有頁面都必須有。

---

## 觀測輸入與正式規格

Page Reference Spec 可以吸收其他來源整理出的頁面觀測資料，例如：

- 其他 Agent 抽出的 page context
- 現有頁面的 UI inventory
- 截圖整理出的 layout / component / flow
- 現行產品需求補充

但這些資料只能作為 **輸入材料**，不能直接原樣視為正式規格。

### 正規化原則

當你把 page context 轉成正式 Page Reference Spec 時，必須遵守：

| 原則 | 說明 |
|------|------|
| 保留穩定頁面身份 | 保留 page purpose、route、主要 user goals、穩定 layout 結構 |
| 重新整理為正式骨架 | 必須改寫成 8 個固定區塊，不保留自由格式觀測筆記 |
| 吸收新需求 | 若目前產品已要求 task management、result recovery、research workflow 等能力，正式 spec 應納入，不得被舊觀測內容限制 |
| Unknown 不能直接進正式 SoT | `Unknown from current page context` 這類內容只能作為待確認訊號；正式 reference 必須驗證後再寫，或暫不列入 |
| 觀測不等於契約 | 現場看到的錯誤訊息、暫時 UI 呈現、框架特定行為，不自動等於正式 contract |

### 區塊對應方式

若輸入材料含有下列常見欄位，轉寫時應對應如下：

| 輸入欄位 | 正式 Page Reference 位置 |
|----------|--------------------------|
| `Page Context` / `Route / Identity` | frontmatter + `Purpose` + `User Goal` |
| `Layout Structure` / `UI Tree` | `Layout Structure` |
| `Component Inventory` | `Component Inventory` |
| `Data Surface` | `Data & State Contract` 的 `Data Dependencies` / `UI States` |
| `Interaction Flows` | `Interaction Flows` |
| `UI States` | `Data & State Contract` 或 `Runtime Notes` |
| `Acceptance Criteria` | `Acceptance Checklist` |

### 擴寫規則

若一頁原本只有列表與基本 CRUD，但目前產品已明確需要更高階 workflow，正式 spec 應主動補上：

- task attachment / task management
- result / trace / event / provenance surfaces
- refresh / reconnect recovery
- 與 backend / CLI / shared contracts 的一致性

正式 reference 的目標不是複製既有畫面，而是定義 **當前應實作的頁面契約**。

---

## 不應寫進 Page Reference 的內容

以下內容不應作為 page reference 正文主體：

- 歷史背景
- 舊版行為
- migration 故事
- React hook 名稱
- framework component 實作細節
- repository / service 類名
- CSS pixel 級細節
- 暫時性 workaround

!!! warning "禁止歷史化語氣"
    不要寫「原本」「舊版」「legacy page」「移植前」。
    Page Reference Spec 只描述當前正式頁面契約。

---

## 建議模板

````md
---
title: Page Name
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/ui
page_id: app.page.route_name
route: /route
owner: app-team
status: stable
---

# Page Name

## 1. Purpose

本頁負責：
- ...
- ...

## 2. User Goal

使用者進入本頁時，主要想完成：
- ...
- ...

非目標：
- ...
- ...

## 3. Layout Structure

### Global Shell

| 區塊 | 說明 |
|---|---|
| Sidebar | ... |
| Main Content | ... |
| Secondary Panel | ... |

### Main Content Order

1. Page Header
2. Primary Action Row
3. Filters / Controls
4. Main Content Area
5. Footer / Pagination / Status Area

### UI Tree

```text
Page
├─ Header
├─ Action Row
├─ Filter Row
├─ Content Area
└─ Footer
```

## 4. Component Inventory

| ID | 元件名稱 | 類型 | 位置 | 作用 | 關鍵行為 |
|---|---|---|---|---|---|
| C1 | Page Title | heading | top | 顯示頁面名稱 | 無 |
| C2 | Search Input | input | filter row | 過濾列表 | 更新 filter state |
| C3 | Create Button | primary button | action row | 建立新項目 | 導向 create flow |

## 5. Data & State Contract

### Data Dependencies

| 資料名稱 | 來源 | 必要性 | 用途 |
|---|---|---|---|
| current_user | session contract | required | 顯示權限與 scope |
| dataset_list | backend API | required | 主列表 |

### Page State

| State | 類型 | 說明 |
|---|---|---|
| search_query | local UI state | 搜尋輸入值 |
| current_page | local UI state | 分頁頁碼 |

### UI States

| 狀態 | 說明 |
|---|---|
| default | 資料成功載入 |
| loading | 主資料載入中 |
| empty | 無資料或 filter 無結果 |
| error | 請求失敗 |
| partial | 部分資料可用、部分失敗 |

## 6. Interaction Flows

### Flow A: 搜尋

1. 使用者輸入關鍵字
2. 更新 search_query
3. 重新過濾或重新請求列表
4. 列表更新

## 7. Visual Rules

| 項目 | 規則 |
|---|---|
| Title hierarchy | 頁面標題必須高於 subtitle |
| CTA placement | 主要操作按鈕先於 filters |
| Empty state | 與 content area 對齊，不改變 shell 結構 |

## 8. Acceptance Checklist

- [ ] 頁面目的與使用者目標可由 UI 直接看出
- [ ] 主要區塊順序符合 Layout Structure
- [ ] loading / empty / error state 都有明確實作
- [ ] interaction flows 可完整走通
- [ ] 資料依賴只透過正式 contract 存取
````

---

## Review Checklist

當你撰寫或審查 App page reference 時，至少確認：

- 是否完整包含 8 個固定區塊
- 是否只寫當前正式規格
- 是否以 contract / state / flow 為主，而非實作細節
- 是否可讓 AI Agent 直接依文件實作
- 是否可讓 reviewer 直接依文件驗收

---

## Agent Rule { #agent-rule }

```markdown
## Page Reference Specs
- **Type**: App frontend page 技術文件必須寫成 Page Reference Spec，不是需求文件、散文或實作筆記
- **Diataxis**: 這類文件屬於 `Reference`
- **Now-only**: 只寫當前正式頁面契約；不要寫舊版/legacy/migration 歷史
- **Title alignment**: 文件 `title` 與 H1 必須優先對齊 sidebar / nav label；route 另寫在 frontmatter `route` 與正文 identity
- **Observed input**: 其他 Agent 抽出的 page context、截圖整理、現有 UI inventory 只能當輸入材料，不能直接當正式 spec
- **Normalization**: 輸入材料必須重新整理成 8 個固定區塊；`Unknown from current page context` 不得直接留在正式 SoT
- **Current product wins**: 若目前產品已要求 task management、result recovery、research workflow 等能力，正式 spec 必須納入，不受舊畫面限制
- **Fixed sections**: 必須包含 8 個區塊：
  1. Purpose
  2. User Goal
  3. Layout Structure
  4. Component Inventory
  5. Data & State Contract
  6. Interaction Flows
  7. Visual Rules
  8. Acceptance Checklist
- **Optional sections**: `Related Contracts`、`Runtime Notes` 只在需要時加入
- **Focus**: 先寫 page purpose、layout、components、state、flows、acceptance；不要先寫框架細節
- **Do not include**: framework 實作細節、repository/service 類名、pixel 級 CSS、歷史背景
- **Naming**: 新頁面優先使用 `docs/reference/app/frontend/pages/<route-name>.md`，並與 sidebar IA 對齊
```
