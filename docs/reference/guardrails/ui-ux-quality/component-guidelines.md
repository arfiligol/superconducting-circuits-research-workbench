---
aliases:
  - Component Guidelines
  - 元件規範
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/ui-ux
status: stable
owner: docs-team
audience: contributor
scope: frontend component 選型、表單、dialog 與資料表格規範。
version: v2.3.0
last_updated: 2026-03-16
updated_by: codex
---

# Component Guidelines

元件規範的目標是讓 frontend 在資料密集與互動密集情境下仍保持一致。

!!! info "How to read this page"
    先決定元件屬於 primitive、feature-local 還是 app-wide layout，再看 interaction 與 data browser 規則。這頁重點是 component boundary，不是完整 design system token 表。

## Component Sources

| 類型 | 來源 |
| --- | --- |
| 基礎 UI primitives | `@/components/ui/*`（shadcn/ui） |
| feature-specific UI | `frontend/src/features/<feature>/components/*` |
| app-wide layout | `frontend/src/components/layout/*` |

## Visible Surface Rule

- 所有使用者可見的互動 UI，必須以 `@/components/ui/*` 或 feature-local wrapper 呈現
- 不可把 browser 預設樣式的 `button`、`input`、`select`、`textarea`、`dialog` 直接當成最終產品 UI
- 若平台原生控制不可避免，必須用自家 trigger / label / helper text / error state / surrounding layout 包起來
- 例外必須屬於 platform bridge 類型，例如：
  - `input[type=file]` 觸發檔案選擇
  - browser / OS 提供的 picker surface
  - 無法完全自繪的安全權限 prompt

!!! warning "Native controls are implementation detail, not product surface"
    原生控制可以是橋接機制，但不應直接成為使用者看到的最終互動樣式。
    若不得不用原生控制，產品仍必須提供一致的外框、標籤、狀態提示、錯誤訊息與操作入口。

## Interaction Rules

- 優先使用 `@/components/ui` 的 Button、Input、Select、Dialog、Tabs、Table 等封裝
- 禁止使用 `alert()`、`confirm()`、`prompt()`
- 表單要搭配 Label、validation、error state
- destructive action 必須有確認流程
- 所有可點擊 icon 必須提供明確 hover state；至少要有 cursor feedback 與可見的 hover 樣式變化
- data-dense table 必須支援 sorting、filtering、pagination 或明確的 virtualization 策略

!!! warning "Confirmation rule"
    destructive action 不能退化成 browser-native `confirm()`。產品互動必須保留一致的語意、樣式與 error handling surface。

## Data Browser Contract

- 列表先載入 summary rows
- 詳細 payload 僅在 row selection 或 detail panel 時抓取
- 不要因為單純切頁就重抓大型 payload

## Copy Density Contract

- 元件與卡片應優先靠標題、status、metadata 與 action hierarchy 自我說明
- helper text 僅在風險高、歧義高或表單輸入需要額外說明時出現
- empty / loading / error state 應簡短直接，不應變成一大段說明牆
- shell、sidebar、header 與 login entry 尤其應避免多餘文字

!!! tip "Use copy as support, not scaffolding"
    若一個 surface 需要大量文字才能被理解，優先先調整 component hierarchy、grouping 與 layout。
    只有在這些都不足時，再加入精簡的輔助文案。

## Agent Rule { #agent-rule }

```markdown
## Component Guidelines
- Prefer components from `@/components/ui/` for interactive primitives.
- Put feature-specific UI in `frontend/src/features/<feature>/components/`.
- Do not expose browser-default styled controls as the final product UI.
- If a platform-native control is unavoidable, wrap it with app-owned trigger, labels, helper text, and error handling.
- Do not use `alert()`, `confirm()`, or `prompt()` for product interactions.
- Destructive actions require an explicit confirmation flow.
- Forms need labels, validation, and visible error states.
- Clickable icons must provide a clear hover state, including pointer feedback and visible hover styling.
- Data-dense tables must support sorting, filtering, and pagination or a clear virtualization strategy.
- Load summary rows first; fetch heavy detail payload only on explicit detail interaction.
- Prefer hierarchy, metadata, and status over long helper copy in dense product UI.
- Keep error, empty, and recovery copy concise; do not turn product surfaces into diagnostics walls.
```
