---
aliases:
  - Guardrails
  - 開發守則
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/governance
status: stable
owner: docs-team
audience: contributor
scope: workspace guardrails 總索引，供人類與 AI Agent 載入任務相關規則。
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Guardrails

本區是 workspace 的開發規範單一真理來源。
核心方向是 **Notebook Interface + Electron Application Interface + Julia Runner Compute Plane**。
Python Backend 是 control/data plane；Julia Runner 是 compute plane；TraceStore 由 Backend publication 流程管理。

!!! info "How to read this section"
    先看 `Project Basics`，再依工作性質進入 `Code Quality`、`UI/UX Quality`、`Execution & Verification` 或 `Documentation Design`。
    不要把整個 guardrails tree 當成一次性必讀清單；先找 owner section，再讀子頁。

=== "Human Developers"

    - 先確認目前任務屬於哪一個 concern。
    - 只打開與當前修改直接相關的 section。
    - 若要改變架構方向、合作方式或 SoT，先回到 `Project Basics` 或 `Execution & Verification`。

=== "AI Agents"

    - 先用 `_agent_catalog.yml` 選擇規則，不要一次全載。
    - 先讀 concern owner，再讀 touched-area rules。
    - 若 owner docs 與 consumer docs 衝突，以 [Source of Truth Order](./project-basics/source-of-truth-order.md) 裁決。

!!! warning "Guardrails are owner documents"
    Guardrails 不是風格建議集，也不是可以自由略過的提示。
    若任務牽涉到這裡定義的 concern，相關規則必須先被載入，再進行設計或實作。

## Section Map

| Section | Use this when | Primary focus |
| --- | --- | --- |
| [Project Basics](./project-basics/index.md) | 任務會改變產品方向、技術選型、資料權威或 repo 結構 | mission、stack、folder layout、SoT ordering |
| [Code Quality](./code-quality/index.md) | 任務會改變實作邊界、service pattern、contract handling 或 error/logging behavior | implementation discipline |
| [UI/UX Quality](./ui-ux-quality/index.md) | 任務會改變 frontend shell、layout、state、routing、component interaction | app frontend quality baseline |
| [Execution & Verification](./execution-verification/index.md) | 任務需要 build、test、CI、handoff 或 subagent coordination | delivery and verification rules |
| [Documentation Design](./documentation-design/documentation.md) | 任務直接在寫 docs、改 docs IA、frontmatter 或 page specs | documentation writing and layout |

## Project Basics

| Page | Focus | Agent Rule |
| --- | --- | --- |
| [Project Basics](./project-basics/index.md) | 專案目標、技術方向、目錄結構索引 | [#agent-rule](./project-basics/index.md#agent-rule) |
| [Project Overview](./project-basics/project-overview.md) | Notebook / Application / Julia Runner / TraceStore 範疇 | [#agent-rule](./project-basics/project-overview.md#agent-rule) |
| [Tech Stack](./project-basics/tech-stack.md) | Next.js + FastAPI + Electron + Julia Runner + Zarr stack | [#agent-rule](./project-basics/tech-stack.md#agent-rule) |
| [Folder Structure](./project-basics/folder-structure.md) | rewrite branch 的 app/core/notebooks/scripts/docs 分工 | [#agent-rule](./project-basics/folder-structure.md#agent-rule) |
| [Backend Architecture](./project-basics/backend-architecture.md) | Python Backend control/data plane 與 publication 邊界 | [#agent-rule](./project-basics/backend-architecture.md#agent-rule) |
| [Source of Truth Order](./project-basics/source-of-truth-order.md) | reference、shared core、adapter、legacy 衝突時的裁決順序 | [#agent-rule](./project-basics/source-of-truth-order.md#agent-rule) |

## Code Quality

| Page | Focus | Agent Rule |
| --- | --- | --- |
| [Code Quality](./code-quality/index.md) | 程式品質總覽 | [#agent-rule](./code-quality/index.md#agent-rule) |
| [Code Style](./code-quality/code-style.md) | Python / TypeScript 的共同撰寫原則 | [#agent-rule](./code-quality/code-style.md#agent-rule) |
| [Type Checking](./code-quality/type-checking.md) | BasedPyright + TypeScript strict | [#agent-rule](./code-quality/type-checking.md#agent-rule) |
| [Design Patterns](./code-quality/design-patterns.md) | API/UI/Notebook/Runner/scripts 與核心服務的依賴邊界 | [#agent-rule](./code-quality/design-patterns.md#agent-rule) |
| [Script Authoring](./code-quality/script-authoring.md) | dev/build/test/maintenance scripts 的結構與責任邊界 | [#agent-rule](./code-quality/script-authoring.md#agent-rule) |
| [Data Handling](./code-quality/data-handling.md) | metadata / trace store 責任分工 | [#agent-rule](./code-quality/data-handling.md#agent-rule) |
| [Logging](./code-quality/logging.md) | logging 使用方式 | [#agent-rule](./code-quality/logging.md#agent-rule) |
| [Contract Versioning](./code-quality/contract-versioning.md) | canonical contracts 的版本與相容性策略 | [#agent-rule](./code-quality/contract-versioning.md#agent-rule) |
| [Error Handling](./code-quality/error-handling.md) | API、Runner、Notebook 與 recovery flow 共用錯誤模型 | [#agent-rule](./code-quality/error-handling.md#agent-rule) |

## UI/UX Quality

| Page | Focus | Agent Rule |
| --- | --- | --- |
| [UI/UX Quality](./ui-ux-quality/index.md) | Next.js frontend 的 UI/UX 總覽 | [#agent-rule](./ui-ux-quality/index.md#agent-rule) |
| [Theming](./ui-ux-quality/theming.md) | semantic tokens、dark mode、theme provider | [#agent-rule](./ui-ux-quality/theming.md#agent-rule) |
| [Component Guidelines](./ui-ux-quality/component-guidelines.md) | shadcn/ui、dialog、form、table 規範 | [#agent-rule](./ui-ux-quality/component-guidelines.md#agent-rule) |
| [Layout Patterns](./ui-ux-quality/layout-patterns.md) | App Router layout 與 master-detail 規則 | [#agent-rule](./ui-ux-quality/layout-patterns.md#agent-rule) |
| [State Management](./ui-ux-quality/state-management.md) | SWR / Context / RHF + Zod | [#agent-rule](./ui-ux-quality/state-management.md#agent-rule) |
| [Accessibility](./ui-ux-quality/accessibility.md) | a11y 與 keyboard/ARIA 規則 | [#agent-rule](./ui-ux-quality/accessibility.md#agent-rule) |
| [Routing](./ui-ux-quality/routing.md) | Next.js App Router 路由策略 | [#agent-rule](./ui-ux-quality/routing.md#agent-rule) |

## Execution & Verification

| Page | Focus | Agent Rule |
| --- | --- | --- |
| [Execution & Verification](./execution-verification/index.md) | build / lint / test / CI 索引 | [#agent-rule](./execution-verification/index.md#agent-rule) |
| [Build Commands](./execution-verification/build-commands.md) | app/frontend / app/backend / Julia Runner / desktop / docs 常用指令 | [#agent-rule](./execution-verification/build-commands.md#agent-rule) |
| [Linting & Formatting](./execution-verification/linting.md) | Ruff / BasedPyright / frontend checks | [#agent-rule](./execution-verification/linting.md#agent-rule) |
| [Testing](./execution-verification/testing.md) | pytest / Vitest / Playwright / docs checks | [#agent-rule](./execution-verification/testing.md#agent-rule) |
| [CI Gates](./execution-verification/ci-gates.md) | rewrite branch 的合併品質門檻 | [#agent-rule](./execution-verification/ci-gates.md#agent-rule) |
| [Task Scope Sizing](./execution-verification/prompt-grading.md) | task 粒度、驗證深度與是否需要短 plan 的判準 | [#agent-rule](./execution-verification/prompt-grading.md#agent-rule) |
| [Codex Subagent Coordination](./execution-verification/multi-agent-collaboration.md) | Codex-managed subagent work lanes 與單一交付責任 | [#agent-rule](./execution-verification/multi-agent-collaboration.md#agent-rule) |
| [Work Summary Formats](./execution-verification/contributor-reporting.md) | final summary / PR body / risk report 格式 | [#agent-rule](./execution-verification/contributor-reporting.md#agent-rule) |
| [Commit Standards](./execution-verification/commit-standards.md) | commit 邊界與訊息規範 | [#agent-rule](./execution-verification/commit-standards.md#agent-rule) |

## Documentation Design

| Page | Focus | Agent Rule |
| --- | --- | --- |
| [Documentation Design](./documentation-design/documentation.md) | 文件規範索引 | [#agent-rule](./documentation-design/documentation.md#agent-rule) |
| [Documentation Standards](./documentation-design/standards.md) | Diataxis 與 frontmatter | [#agent-rule](./documentation-design/standards.md#agent-rule) |
| [Zensical Native Style](./documentation-design/zensical-native-style.md) | Zensical-native 寫作節奏與呈現方式 | [#agent-rule](./documentation-design/zensical-native-style.md#agent-rule) |
| [Documentation Maintenance](./documentation-design/maintenance.md) | 單語文件來源與 build 流程 | [#agent-rule](./documentation-design/maintenance.md#agent-rule) |

??? info "Installed vs loaded rules"
    `docs/reference/guardrails/` 是 SoT。
    `.agent/rules/` 是安裝後給 agent 使用的同步結果。

## Agent Rule { #agent-rule }

```markdown
## Guardrails
- `docs/reference/guardrails/` is the workspace rules Source of Truth.
- Use `_agent_catalog.yml` to load only task-relevant guardrails instead of loading the full tree.
- Current architecture is Notebook Interface + Electron Application Interface + Julia Runner Compute Plane.
- Python Backend is the control/data plane; Julia Runner is the compute plane; Backend-managed TraceStore is the official numeric authority.
- Retired command workflow, Python UI runtime, separate queue worker runtime, and Python in-process Julia execution have no authority over current product/runtime surfaces.
- `.agent/rules/` must be synchronized one-to-one from each guardrail file's `## Agent Rule` block whenever guardrail source changes.
```
    安裝與載入是兩件不同的事；任務中通常只需要載入少數必要規則。

## 驗證指令

```bash
uv run ruff format .
uv run ruff check .
uv run basedpyright src
uv run pytest
./scripts/prepare_docs_locales.sh
./scripts/build_docs_sites.sh
```
