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
scope: build、lint、test、CI、direct-develop flow 與 Codex subagent coordination 規範索引。
version: v2.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Execution & Verification

本區定義 workspace delivery 的執行與驗證基準。
若新規則與現有腳本不一致，應修正腳本或規則來源，而不是放棄驗證基準。

!!! info "What belongs here"
    這一層不是在定義產品功能，而是在定義如何交付、如何驗證、如何協作。
    如果問題在問 build、test、CI、handoff 或 Codex subagent execution flow，答案應該先從這裡找。

## Page Map

| Page | Read this when | Primary concern |
| --- | --- | --- |
| [Build Commands](./build-commands.md) | 你要跑開發環境、build、docs build | run and build entrypoints |
| [Linting & Formatting](./linting.md) | 你要跑 format、lint、typecheck | static quality gates |
| [Testing](./testing.md) | 你要補單元測試、integration、Playwright | test expectations |
| [Commit Standards](./commit-standards.md) | 你要整理 commit 邊界與訊息 | commit hygiene |
| [Branch & Worktree Flow](./branch-and-worktree-flow.md) | 你在定義 `develop` direct update、optional branch/worktree 或 release promotion | canonical Git/worktree policy |
| [CI Gates](./ci-gates.md) | 你在改 GitHub Actions 或 merge criteria | pipeline acceptance |
| [Task Scope Sizing](./prompt-grading.md) | 你在決定 task 粒度、驗證深度或是否需要短 plan | task sizing |
| [Codex Subagent Coordination](./multi-agent-collaboration.md) | 你在決定是否使用 Codex subagents 或如何回報整合結果 | collaboration framework |
| [Work Summary Formats](./contributor-reporting.md) | 你要撰寫 final summary、PR body 或風險回報 | summary structure |

!!! warning "Do not skip verification ownership"
    `Implementation` 完成不等於整條交付線完成。
    integration / E2E / final summary 仍必須對齊 `Testing` 與 `Codex Subagent Coordination` 的規則。

## Agent Rule { #agent-rule }

```markdown
## Execution & Verification
- 定義 build、lint、type-check、test、CI 的 workspace 基線。
- branch roles、direct-develop policy 與 optional worktree use 由 `Branch & Worktree Flow` 定義。
- 變更程式碼時，優先執行與 touched area 直接相關的檢查。
- workspace delivery baseline 包含 app/frontend、app/backend、Julia Runner、desktop、docs 五條驗證線。
- task scope、驗證深度與 subagent coordination 需對齊本區規則。
```
