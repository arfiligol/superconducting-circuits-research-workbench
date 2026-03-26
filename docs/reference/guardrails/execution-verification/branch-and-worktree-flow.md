---
aliases:
  - Branch and Worktree Flow
  - Git Flow and Worktree Policy
  - Branch / Worktree Policy
  - 分支與 Worktree 流程
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: team
scope: main/develop branch roles、AI-agent isolated worktree policy、merge authority 與 autonomous bounded write roots。
version: v1.0.0
last_updated: 2026-03-27
updated_by: codex
---

# Branch & Worktree Flow

本頁定義本 repo 的正式 Git Flow 與 worktree collaboration policy。
它回答的是：

- `main` 與 `develop` 各自扮演什麼角色
- AI agents 應該從哪個 branch 開工
- 哪一類 agent 可以把工作合回 `develop`
- autonomous sandbox / example agents 何時可以自行 merge
- 每位 agent 是否都必須使用獨立 worktree

!!! important "`main` is release, `develop` is development main"
    `main` 是 release branch，不是日常 feature work 的預設整合分支。
    `develop` 才是 active development 的 primary integration target，也是 AI agents 開 task branch / isolated worktree 的預設 base。

!!! warning "Isolated worktree is mandatory"
    每個 agent / task 都必須使用專屬 branch + isolated worktree。
    active user-facing root worktree 不是預設 implementation surface，也不是多位 agents 共編的共享工作樹。

## Purpose

| Concern | This page defines |
| --- | --- |
| Branch roles | `main` / `develop` 的正式職責 |
| Default delivery flow | 正常 implementation slice 從哪裡開 branch、往哪裡整合 |
| Merge authority | 哪一類 agent 可以合回 `develop` |
| Worktree policy | isolated worktree 的必要性與禁止事項 |
| Bounded autonomy | sandbox / example 類 agent 的可寫範圍與自主管理條件 |

## Branch Roles

| Branch | Canonical role | Must not be treated as |
| --- | --- | --- |
| `main` | release branch；應代表 release-ready integrated state | 預設日常開發整合分支 |
| `develop` | primary development branch；active feature work 的預設 integration target | release promotion branch 的替代品 |

!!! tip "Default base for new work"
    若沒有更窄的 release / hotfix 指示，新的 implementation、test、docs、planning slices 都應以 `develop` 為預設 base。

## Default Delivery Flow

正常 implementation work 的正式流程如下：

1. 從 `develop` 建立專屬 task branch + isolated worktree。
2. `Frontend / Backend / Core / CLI Agent` 在該 worktree 內完成被指派的 slice。
3. agent 只 commit 自己在該 isolated worktree 內完成的工作。
4. implementation agents 不直接把自己的 slice merge 回 `develop`。
5. `Planning & Reviewing Agent` 是這類 implementation slices 的預設 integration authority。
6. `Planning & Reviewing Agent` review、verify、回收 accepted work，再整合回 `develop`。

## Agent Merge Authority

| Agent family / lane | Default merge authority | Notes |
| --- | --- | --- |
| Documentation Agent | 依同一 delivery line 的 integration authority 決定；通常不直接整合別人的 implementation slices | 文件本身可在專屬 worktree 內提交，但不取代整體 integration authority |
| Planning & Reviewing Agent | normal implementation slices 的預設 integration authority | 回收 accepted work，整合回 `develop` |
| Frontend / Backend / Core / CLI Agent | no direct merge to `develop` by default | 完成 slice + unit tests + delivery report 後交回 review |
| Test Agent | no direct merge to `develop` by default | 完成 integration / E2E / verification evidence 後交回 review |
| autonomous sandbox/example agent | 可在符合 bounded write root 規則時自行 merge 回 `develop` | 僅限明確授權的 research / sandbox / examples surfaces |

!!! warning "Do not collapse implementation with integration authority"
    完成 code slice 不等於擁有 integration authority。
    對正常產品 implementation work，`Planning & Reviewing Agent` 才是預設把 accepted work 帶回 `develop` 的 owner。

## Worktree Isolation Rules

| Rule | Required meaning |
| --- | --- |
| One task, one worktree | 每個 agent / task 都必須有自己的 branch + isolated worktree |
| No shared dirty worktree | agents 不得共編同一個 dirty worktree |
| Root worktree is not default | active user-facing root worktree 不是預設 implementation surface |
| Commit ownership stays local | agent 只提交自己在該 isolated worktree 內完成的工作 |
| Dirty-worktree collision is forbidden | 若 worktree 已有非本任務 dirty changes，不得直接覆蓋或共編 |
| Isolation is mandatory | 這不是 best effort；未分 worktree 的 agent task 視為流程不完整 |

!!! tip "Read widely, write narrowly"
    agents 可以讀整個 repo 建立 context。
    但實際修改仍必須受 branch / worktree assignment 與 write-root policy 約束。

## Autonomous Sandbox / Example Agent Rules

某些 agents 不屬於主要產品 implementation lanes，而是 research-support、sandbox、example、experimentation 類型。
這類 agents 仍必須使用 isolated worktree，但 merge authority 與 write scope 不同。

### Bounded write root contract

| Concern | Contract |
| --- | --- |
| Read access | 可以讀 repo 其他區域取得 context |
| Write access | 只能寫入明確授權的 bounded write root |
| Merge authority | 若完全遵守 bounded write root，且該 agent family 被明確授權，可自行 merge 回 `develop` |
| Out-of-scope edits | 不得順手修改 bounded write root 之外的檔案 |

### Example bounded write roots

| Agent | Read scope | Write scope | Autonomous merge rule |
| --- | --- | --- | --- |
| `Sandbox Agent` | repo-wide read for context | `sandbox/**` only | 可在僅修改 `sandbox/**` 時自行 merge 回 `develop` |
| `Example Agent` | repo-wide read for context | `examples/**` only | 可在僅修改 `examples/**` 時自行 merge 回 `develop` |

!!! warning "Readable everywhere, writable only in assigned roots"
    autonomous sandbox/example agent 可以讀其他區域理解 API、contracts、fixtures 或 examples context。
    但只要修改超出 bounded write root，就不再屬於 autonomous merge model，必須回到一般 review / integration flow。

## Promotion Path

正式 promotion path 為：

1. feature / task branches -> `develop`
2. verified release promotion -> `main`

| Path | Meaning |
| --- | --- |
| feature/task branch -> `develop` | 日常 implementation / docs / test slices 的預設 integration path |
| `develop` -> `main` | 經驗證的 release promotion；不是一般 feature slice 的預設 landing path |

!!! warning "Do not merge normal task work straight to `main`"
    若文件或流程仍寫成「預設 merge 回 `main`」，應視為過時 wording。
    正常 task work 的預設目標是 `develop`；`main` 只接 verified promotion。

## Related

- [Execution & Verification](./index.md)
- [Multiple Agent Collaboration](./multi-agent-collaboration.md)
- [Prompt Grading](./prompt-grading.md)
- [CI Gates](./ci-gates.md)
- [How-to / Contributing](../../../how-to/contributing.md)

## Agent Rule { #agent-rule }

```markdown
## Branch & Worktree Flow
- `main` is the release branch; do not treat it as the default daily integration branch.
- `develop` is the primary development branch and default base for new AI-agent task branches/worktrees.
- Every agent/task must use a dedicated branch + isolated worktree.
- Do not let multiple agents co-edit the same dirty worktree.
- Normal implementation slices (`Frontend` / `Backend` / `Core` / `CLI`) do not merge directly to `develop`; `Planning & Reviewing Agent` is the default integration authority.
- Autonomous sandbox/example agents may merge to `develop` only when they stay fully inside explicitly assigned bounded write roots.
- Read access may be repo-wide for context, but write access is limited to the assigned bounded write root.
- Promotion path is:
    - feature/task branches -> `develop`
    - verified release promotion -> `main`
```
