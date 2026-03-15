---
aliases:
  - "Contributor Agent 回報格式"
  - "Contributor Reporting"
  - "Agent Handoff Formats"
tags:
  - audience/team
  - sot/true
status: stable
owner: docs-team
audience: team
scope: "Planning & Reviewing / Implementation / Test Agents 的標準交接格式"
version: v2.5.0
last_updated: 2026-03-16
updated_by: codex
---

# Agent Handoff Formats

規範 Documentation Agent 產出的正式 SoT 與 `Planning & Reviewing / Implementation / Test Agents` 之間的交接結構，讓人類與其他 agents 可以直接消費。

!!! important "Goal"
    handoff 必須同時滿足兩件事：
    1) 人類可快速看懂成果與風險
    2) 下一個 agent 可直接提取 commits、檔案、測試、風險與待決策事項

## Handoff Map

| handoff type | owner | 主要用途 |
| --- | --- | --- |
| Plan Artifact v1 | Planning & Reviewing Agent | 定義 slice、test backlog、verification |
| Delivery Report v1 | Frontend / Backend / Core / CLI Agent / Test Agent | 回報 commits、changed files、測試、風險 |
| Review Merge Report v1 | Planning & Reviewing Agent | 整合 accepted inputs、驗證結果、主線狀態 |

## Plan Artifact v1

```markdown
## Plan Artifact v1

### 0) 任務資訊
- Agent: <name>
- Task ID / Topic: <id-or-title>
- 狀態: <draft|ready|blocked>

### 1) Goal
- 目標: <what was requested>
- 使用者成功條件: <what must become true>

### 2) Source of Truth
- Primary docs:
  - <path>
  - <path>
- Current authority owner: <doc or surface>

### 3) Current Implementation State
- Existing code paths:
  - <path>: <state>
- Current gaps:
  - <gap-1>
  - <gap-2>

### 4) Implementation Slices
- Frontend:
  - Allowed Area: <summary>
  - Do Not Touch: <summary>
  - Goal: <slice goal>
- Backend:
  - Allowed Area: <summary>
  - Do Not Touch: <summary>
  - Goal: <slice goal>
- Core:
  - Allowed Area: <summary>
  - Do Not Touch: <summary>
  - Goal: <slice goal>
- CLI:
  - Allowed Area: <summary>
  - Do Not Touch: <summary>
  - Goal: <slice goal>

### 5) Test Backlog
- Integration:
  - <scenario-1>
  - <scenario-2>
- E2E:
  - <scenario-1>
  - <scenario-2>

### 6) Verification Matrix
- Unit:
  - <command>
- Integration:
  - <command or planned owner>
- E2E:
  - <command or planned owner>

### 7) Risks / Open Decisions
- <risk-1>
- <risk-2>
```

## Delivery Report v1

```markdown
## Delivery Report v1

### 0) 任務資訊
- Agent: <name>
- Role: <frontend|backend|core|cli|test>
- Task ID / Topic: <id-or-title>
- Branch / Worktree: <branch-or-path>
- Scope (Allowed Area): <summary>
- Do Not Touch: <summary>
- Assigned Slice: <slice-id-or-title>
- 狀態: <done|blocked|needs-review>

### 1) Summary
- 目標: <what was requested>
- 結果: <what is now true>

### 2) Preflight 與邊界遵守
- 指派的 `Branch / Worktree` 是否存在且專屬: <yes|no + note>
- 開工前 `git status --porcelain`: <clean|dirty + note>
- 是否超出 `Allowed Area`: <no|yes + reason>
- 跨界處理方式: <n/a|handoff-to-planning-and-reviewing>

### 3) 變更內容
- Commit(s):
  - `<hash>` `<message>`
- Changed Files:
  - `<path>`: <why changed>

### 4) 文件更新（若有）
- `<path>`: <contract/spec change>

### 5) 測試結果
- Commands:
  - `<command>`
- Results:
  - `<pass/fail + key output>`

### 6) API / Contract Touched Matrix
- Public APIs touched:
  - `<module.path.symbol>`: `<added|changed|removed|none>`
- Downstream callers checked:
  - `<caller-path-or-n/a>`

### 7) Integration / E2E Impact
- Needed but not owned here:
  - <integration gap>
  - <e2e gap>

### 8) Known Risks
- <risk-1>
- <risk-2>

### 9) Needs Planning & Reviewing Agent Decision
- <decision-needed-1>
```

## Review Merge Report v1

```markdown
## Review Merge Report v1

### 0) Delivery Line
- Topic: <topic>
- Target Branch: <main-or-other>
- Planning & Reviewing Agent: <name>

### 1) Accepted Inputs
- Planning artifact:
  - <path or link>
- Delivery reports:
  - <source-1>
  - <source-2>

### 2) Integrated Commits
- `<hash>` `<message>`
- `<hash>` `<message>`

### 3) Conflict Resolution
- <none or summary>

### 4) Final Verification
- `<command>`: <result>
- `<command>`: <result>

### 5) Remaining Risks
- <risk-1>

### 6) Mainline Status
- <merged|queued|blocked>

### 7) Review Basis
- SoT pages reread:
  - <path>
  - <path>
- Code context reread:
  - <path>
  - <path>
- UI evidence (required for user-visible frontend changes):
  - Playwright flow: <path-or-summary>
  - Screenshot(s): <path-or-summary>
- Judgement:
  - <why the implementation does / does not satisfy product need and current SoT>
```

## Required Sections

- Planning handoff 必須包含：`Source of Truth`、`Current Implementation State`、`Implementation Slices`、`Test Backlog`
- Delivery handoff 必須包含：`Commit(s)`、`Changed Files`、`測試結果`、`Known Risks`、`API / Contract Touched Matrix`
- Merge handoff 必須包含：`Integrated Commits`、`Final Verification`、`Mainline Status`、`Review Basis`

## Readability Rules

- 先給結論，再給證據
- 不要貼整段長 log，改為「指令 + 結果摘要 + 證據路徑」
- 回報用語必須區分：
  - **已完成**
  - **已驗證**
  - **待 Planning & Reviewing 決策**

## Agent Rule { #agent-rule }

```markdown
## Agent Handoff Formats
- Planning & Reviewing Agents MUST produce a written `Plan Artifact v1`.
- Implementation Agents and Test Agents MUST hand off using `Delivery Report v1`.
- Planning & Reviewing Agents MUST summarize integration and verification using `Review Merge Report v1`.
- Delivery reports MUST include:
    - assigned branch/worktree
    - allowed area
    - do-not-touch boundary
    - assigned slice
    - commit hashes
    - changed files with reason
    - test commands and results
    - API / contract touched matrix
    - known risks
- Review merge reports MUST include:
    - SoT pages reread
    - code context reread
    - UI evidence for user-visible frontend changes
    - explicit judgement against current docs and product need
- Reporting quality rules:
    - lead with conclusion, then evidence
    - summarize logs instead of dumping long raw output
    - explicitly separate completed work, verified work, and items needing planning/reviewing decisions
```
