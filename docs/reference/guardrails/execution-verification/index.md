---
aliases:
  - Execution & Verification
  - 執行與驗證
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: build、lint、test、CI、branch/worktree flow、multi-agent workflow 與 migration phase 驗收規範索引。
version: v1.3.0
last_updated: 2026-03-27
updated_by: codex
---

# Execution & Verification

本區定義 workspace delivery 的執行與驗證基準。
若新規則與現有腳本暫時不一致，應視為 migration task，而不是放棄規則的理由。

!!! info "What belongs here"
    這一層不是在定義產品功能，而是在定義如何交付、如何驗證、如何協作。
    如果問題在問 build、test、CI、handoff、phase acceptance 或 multi-agent execution flow，答案應該先從這裡找。

## Page Map

| Page | Read this when | Primary concern |
| --- | --- | --- |
| [Build Commands](./build-commands.md) | 你要跑開發環境、build、docs build | run and build entrypoints |
| [Linting & Formatting](./linting.md) | 你要跑 format、lint、typecheck | static quality gates |
| [Testing](./testing.md) | 你要補單元測試、integration、Playwright | test expectations |
| [Commit Standards](./commit-standards.md) | 你要整理 commit 邊界與訊息 | commit hygiene |
| [Branch & Worktree Flow](./branch-and-worktree-flow.md) | 你在定義 delivery branches、worktree isolation 或 agent merge authority | canonical Git/worktree policy |
| [CI Gates](./ci-gates.md) | 你在改 GitHub Actions 或 merge criteria | pipeline acceptance |
| [Phase Gates](./phase-gates.md) | 你在推 migration milestone | milestone-level readiness |
| [Prompt Grading](./prompt-grading.md) | 你在拆 implementation / test slices | task sizing |
| [Multiple Agent Collaboration](./multi-agent-collaboration.md) | 你在定義 agent roles 與交接順序 | collaboration framework |
| [Agent Handoff Formats](./contributor-reporting.md) | 你要撰寫 plan / delivery / merge reports | handoff structure |

!!! warning "Do not skip verification ownership"
    `Implementation` 完成不等於整條交付線完成。
    integration / E2E / final merge authority 仍必須經過 `Testing`、`Phase Gates` 與 `Multiple Agent Collaboration` 的規則。

## Agent Rule { #agent-rule }

```markdown
## Execution & Verification
- 定義 build、lint、type-check、test、CI 的 workspace 基線。
- branch roles、isolated worktree policy 與 merge authority 由 `Branch & Worktree Flow` 定義。
- 變更程式碼時，優先執行與 touched area 直接相關的檢查。
- workspace delivery baseline 包含 frontend、backend、CLI、desktop、docs 五條驗證線。
- migration phases 需搭配 Phase Gates、Prompt Grading 與 multi-agent collaboration rules 驗收。
```
