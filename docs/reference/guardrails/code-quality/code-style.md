---
aliases:
  - Code Style
  - 程式碼風格
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/code-quality
status: stable
owner: docs-team
audience: contributor
scope: Python 與 TypeScript 的共同程式風格與實作原則。
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Code Style

本專案的風格規則以「可讀、可改、可測」為優先。
若某個實作讓 UI、API、Notebook、Runner 或 scripts 其中一層看起來方便，卻讓共享規則變得分散或難以驗證，則視為不合格。

!!! info "How to use this page"
    先看跨語言原則，再看對應語言規則。若某個變更同時碰到 Python 與 TypeScript，優先遵守共通邊界，再處理語言特有風格。

## Style Map

| 區塊 | 回答的問題 |
| --- | --- |
| Cross-Language Principles | 所有語言都必須遵守的結構原則 |
| Language Rules | Python 與 TypeScript 各自怎麼保持可讀與可驗證 |
| Refactoring Rule | 什麼樣的重構粒度才算合格 |

## Cross-Language Principles

- 優先小 diff，避免無關重構
- 一個函式只做一件事
- 明確命名，不用模糊縮寫
- 避免把業務邏輯塞進 route handler、React component、notebook helper 或 script
- 重複邏輯先抽到共享層，再擴增呼叫點

!!! warning "Boundary rule"
    看起來方便的 inline workflow，若讓 route handler、component、notebook helper 或 script 擁有真正的業務決策，就屬於不合格實作。

## Language Rules

=== "Python"

    - 使用現代語法：`list[str]`、`str | None`
    - 依照 Ruff 規範維持 import 與格式一致
    - 在科學計算情境中，必要時可在名稱中保留單位，例如 `frequency_hz`
    - `core/` 與 service 層禁止 `print()`

=== "TypeScript"

    - 使用 TypeScript strict mode
    - 禁止無理由的 `any`
    - component props、service 回傳值、schema parse 結果都要有明確型別
    - React component 應保持 presentation-focused，資料抓取與 mutation 邏輯集中在 hooks / services

## Refactoring Rule

- 先做能被驗證的小步修改
- 先修正結構問題，再考慮抽象化
- 若抽象只服務單一使用點且沒有減少複雜度，先不要抽

??? note "Why this page stays short"
    這頁只定共通風格，不重複 lint、type-check、error handling 等更細的 guardrails。需要具體工具規則時，直接看同層專頁。

## Agent Rule { #agent-rule }

```markdown
## Code Style
- **Standard**:
    - Python uses Ruff + modern Python syntax
    - TypeScript uses strict typing and consistent formatting
- **Naming**:
    - variables use clear nouns
    - functions use clear verb phrases
    - scientific names may include units when that removes ambiguity
- **Boundaries**:
    - do not put business workflow logic inside route handlers, React components, notebooks, or scripts
    - shared logic belongs in app backend services, Julia Core, Julia Runner, or explicit contract packages
- **Refactoring**: prefer small, atomic changes
- **Complexity**: keep functions focused; split code when one function starts handling multiple responsibilities
```
