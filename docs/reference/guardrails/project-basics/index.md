---
aliases:
  - Project Basics
  - 專案基礎規範
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/project-basics
status: stable
owner: docs-team
audience: contributor
scope: 定義 current platform 的專案目標、heavy-development 階段、技術方向、結構與單一真理順序索引。
version: v1.4.0
last_updated: 2026-05-28
updated_by: codex
---

# Project Basics

本區定義目前 branch 的基礎共識：產品範疇、技術選型與 repo 結構。
任何會影響整體開發方向的修改，都應先更新這些文件。

!!! info "What this section owns"
    `Project Basics` 定義整個 workspace 的共同前提。
    如果問題在問「我們到底在做什麼、用什麼做、檔案應該放哪、衝突時誰說了算」，答案都應該先從這裡找。

!!! important "Development phase"
    現階段是 Heavy Development / No Compatible Fallback。
    後續工作以打穩 current product、準備下一次真正部署上線為優先；不要把 backward-compatible fallback 當成預設要求。

## Page Map

| Page | Read this when | Core question |
| --- | --- | --- |
| [Project Overview](./project-overview.md) | 你要確認產品邊界、主要 workflows、重寫方向 | 這個平台到底要做什麼？ |
| [Tech Stack](./tech-stack.md) | 你要確認 framework、dependency 或 runtime baseline | 我們正式採用哪些技術？ |
| [Folder Structure](./folder-structure.md) | 你要新增檔案、搬動模組、重整目錄 | 這種變更應該落在哪裡？ |
| [Backend Architecture](./backend-architecture.md) | 你要改 API / services / persistence / facade 邊界 | backend 應如何分層？ |
| [Source of Truth Order](./source-of-truth-order.md) | 你遇到 docs、backend、frontend、Runner、Notebook 說法衝突 | 衝突時誰說了算？ |

!!! tip "Read order"
    先看 `Project Overview`，再看 `Tech Stack` 與 `Folder Structure`。
    若任務直接碰到 contract 衝突、owner boundary 或 migration 對齊，再補看 `Source of Truth Order` 與 `Backend Architecture`。

## Agent Rule { #agent-rule }

```markdown
## Project Basics
- Project Basics 定義 current platform 的使命、範疇、heavy-development 階段、技術棧與結構。
- Current development mode is Heavy Development / No Compatible Fallback; prioritize stabilizing the current product over preserving backward-compatible fallback paths.
- 任何影響整體協作與架構一致性的變更，必須先更新本區。
- 目前 UI 方向為 Next.js，API 方向為 FastAPI，compute plane 方向為 Julia Runner，Notebook 是研究 cockpit。
- backend 的責任邊界與內部藍圖由 `backend-architecture.md` 定義。
- 舊的 CLI、NiceGUI、Redis/RQ worker 與 Python JuliaCall runtime 視為 migration legacy，不應再成為新功能的預設落點。
```
