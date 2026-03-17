---
aliases:
  - Layout Patterns
  - 佈局規範
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/ui-ux
status: stable
owner: docs-team
audience: contributor
scope: App Router layout、workspace shell 與 data-dense 頁面結構規範。
version: v2.3.0
last_updated: 2026-03-18
updated_by: codex
---

# Layout Patterns

!!! info "Use this page for shell and page-structure decisions"
    這頁回答 layout boundary 應該放在哪一層，以及 data-dense 頁面應該怎麼排。它不替代 page-level spec。

## Layout Map

| 層級 | 主要責任 |
| --- | --- |
| Root layout | providers、theme、fonts、global styles |
| Workspace layout | sidebar、top bar、shared workspace context |
| Feature layout | tabs、breadcrumb、sub-navigation |

## App Router Responsibilities

- Root layout：providers、theme、fonts、global styles
- Workspace layout：sidebar、top bar、shared workspace context
- Feature layout：tabs、breadcrumb、sub-navigation

## Route Groups

- `(workspace)`：主產品區
- `(docs)` 或其他非主產品區可獨立分群
- 不要把所有頁面都堆在 root layout 下

## Data-Dense View Pattern

資料密集頁面優先採用 master-detail：

- 左側：table / list / search / filters
- 右側：detail panel / chart / analysis output
- mobile 下需可堆疊

!!! tip "Good default"
    若頁面同時有列表、搜尋、過濾與 detail/preview，優先從 master-detail 開始，而不是先把所有東西往單欄直堆。

## Spacing

- 使用一致的 spacing scale
- 頁面級區塊用中等間距
- 卡片內距保持緊湊但可讀
- 避免為了「看起來大氣」而犧牲資料密度

## Guidance Density

| Prefer | Avoid |
|---|---|
| 透過 hierarchy、grouping、alignment 與 spacing 引導 | 先堆大量 explanatory paragraphs 再希望使用者自己整理 |
| concise labels、status badges、section titles | 長段 helper copy 佔滿 shell 或 card |
| clear primary action + quiet secondary actions | 同層級塞滿很多文案與 CTA |

!!! tip "Let layout teach first"
    能用佈局、分區、按鈕層級與狀態位置說清楚的事情，就不要再加一段輔助文字。
    說明文字應是補充，不應成為整個 UX 的主要導引機制。

## Single-primary-task Rule

| Rule | Meaning |
|---|---|
| One page, one primary job | 每個 page body 應明確服務一個主任務，例如 dataset management、raw-data browse、simulation workflow、schemdraw authoring |
| Secondary surfaces stay secondary | 支援資訊可以存在，但不得稀釋主任務或搶走首屏注意力 |
| Shell context stays in shell | `Runtime Mode`、`Active Workspace`、`Active Dataset`、`Tasks Queue`、worker summary 屬於 shared shell，不應在各頁重做 context summary wall |
| Cross-page CTA is not IA | `Open X`、`Go to Y`、`Handoff to Z` 不是資訊架構；只有在它是單一主要下一步時才應出現 |

!!! warning "Do not overbuild page bodies"
    不要因為某塊資訊「看起來完整」就把它塞進 page body。
    duplicated shell context、authority summary、handoff cards、navigation button walls 與大段 explanation copy，若不是完成本頁主任務不可缺，就不應存在。

## Noise Budget

| Keep | Remove or demote |
|---|---|
| 清楚的 section hierarchy、必要的 state、單一 primary CTA | runtime mode cards、target dataset cards、submit authority cards 等重複 shell context |
| 主流程需要的 concise blocking reason | 只是為了「幫忙解釋」而放的大段補充文字 |
| 與本頁主任務直接相關的結果 / 狀態 | 跨頁導航牆、handoff wall、與本頁無直接關聯的 summary cards |
| 可快速掃讀的 metadata 與 status | 會讓頁面變成管理牆或 diagnostics wall 的額外資訊 |

## Agent Rule { #agent-rule }

```markdown
## Layout Patterns
- Use App Router layouts intentionally:
    - root layout for providers/theme/fonts
    - workspace layout for shared shell
    - feature layout for sub-navigation
- Use route groups to separate workspace surfaces from other sections.
- Data-dense pages should prefer a master-detail structure with mobile-safe stacking.
- Keep spacing consistent and compact enough for dense data workflows.
- Do not collapse the entire product into one flat page tree without layout boundaries.
- Prefer guidance through layout hierarchy before adding explanatory copy.
- Keep shell and dashboard surfaces low-noise; helper text should be concise and only where ambiguity or risk remains.
- Each page body should serve one primary task; do not dilute it with duplicated shell context or cross-page CTA walls.
- Keep runtime mode, active workspace, active dataset, task queue, and worker summary in shared shell surfaces unless the page cannot function without rendering a task-local subset.
- Use follow-up navigation only when it is the single primary next action, not as a substitute for clear IA.
- Remove or demote authority summaries, handoff cards, and helper panels that are not required to complete the page's primary job.
```
