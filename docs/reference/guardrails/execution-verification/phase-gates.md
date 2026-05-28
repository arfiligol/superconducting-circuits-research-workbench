---
aliases:
  - "Phase Gates"
  - "階段驗收關卡"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: team
scope: "定義 migration phases 最低驗收條件、對應測試類型與深度實作前置條件"
version: v2.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Phase Gates

本文件定義 migration 各 phase 最低驗收門檻。

!!! info "How to read this page"
    先看 planning prerequisites，再看 phase 對應的最低 gate。這頁是「可不可以宣告進下一階段」的判準，不是每次小改動都要完整走一遍的 checklist。

## Required Planning Artifacts

在深入 `Phase 4` 以前，必須已有：

- parity matrix
- canonical contract registry
- source-of-truth ordering
- identity/workspace minimal model
- task runtime / Runner protocol / publication contract
- error model
- work summary format

## Gate Map

| phase concern | 主要看哪一節 |
| --- | --- |
| 進入深度 implementation 前需要哪些前置物？ | Required Planning Artifacts |
| 每個 phase 至少要過哪些測試？ | Minimum Gates by Phase |
| 各層應搭配哪些測試類型？ | Phase-to-Test Mapping |
| 何時可以進入較深的跨面實作？ | Entry Criteria for Deep Implementation |

## Minimum Gates by Phase

| Phase | 最低必過項目 |
| --- | --- |
| Phase 3 | backend API contract tests、frontend build/type/test、schema/dataset parity entries 更新 |
| Phase 4 | auth/session contract tests、workspace-context tests、frontend app-state integration tests |
| Phase 4.5 | Notebook/Application task submission and Runner smoke tests |
| Phase 5A | repository/persistence tests、TraceStore contract tests、provenance linkage tests |
| Phase 5B | task lifecycle tests、Runner claim/complete/publish tests、retry/failure classification tests |
| Phase 6 | workflow integration tests、recovery/reattach tests、parity matrix workflow sign-off |
| Phase 7 | notebook/application parity checks、desktop smoke tests、migration sign-off against parity matrix |

## Phase-to-Test Mapping

| 範圍 | 最低測試類型 |
| --- | --- |
| Julia Core | invariant / contract tests、pure helper tests |
| Julia Runner | task parsing、manifest、Zarr staging、fake smoke dispatch tests |
| backend | API contract tests、service tests、repository/persistence tests |
| frontend | build/type/lint、shared hook/provider tests、必要時 integration tests |
| Notebook | workflow smoke / inspection tests when executable |
| Runner / publication | task lifecycle tests、retry/failure tests、recovery attach tests |
| docs | nav source check、site build、built route check |

## Entry Criteria for Deep Implementation

在進入跨多個 surfaces 的深度實作前，至少要有：

- [Source of Truth Order](../project-basics/source-of-truth-order.md)
- [Contract Versioning](../code-quality/contract-versioning.md)
- [Error Handling](../code-quality/error-handling.md)
- [Identity & Workspace Model](../../app/shared/identity-workspace-model.md)
- [App / Backend / Tasks & Execution](../../app/backend/tasks-execution.md)
- [Parity Matrix](../../architecture/parity-matrix.md)
- [Canonical Contract Registry](../../architecture/canonical-contract-registry.md)
- [Codex Subagent Coordination](./multi-agent-collaboration.md)
- [Work Summary Formats](./contributor-reporting.md)

!!! warning "Do not declare phase completion early"
    若 contract registry、parity matrix、tests 與 workflow recovery 還沒有對上，就不能只因為畫面能跑或 API 回資料就宣告 phase 完成。

## Agent Rule { #agent-rule }

```markdown
## Phase Gates
- Do not declare a migration phase complete until its minimum contract/test gates are green.
- Before deep Phase 4 work, require:
    - parity matrix
    - canonical contract registry
    - source-of-truth ordering
    - identity/workspace minimal model
    - task runtime / Runner protocol / publication contract
    - error model
    - work summary format
- If a public contract changes during any phase, update the parity matrix, contract registry, and relevant tests in the same delivery line.
- Treat recovery/reattach tests as mandatory for workflow-parity phases, not optional polish.
```
