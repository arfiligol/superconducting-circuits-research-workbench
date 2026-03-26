---
aliases:
  - "多 Agent 協作"
  - "Multiple Agent Collaboration"
  - "Agent Collaboration Framework"
tags:
  - audience/team
  - sot/true
status: stable
owner: docs-team
audience: team
scope: "Documentation / Planning & Reviewing / Implementation / Test Agents 的責任分工、交接順序與並行協作規範"
version: v2.6.0
last_updated: 2026-03-27
updated_by: codex
---

# 多 Agent 協作

規範本專案的多 Agent 協作框架，確保文件、計劃、實作、驗收與測試有明確 owner。

!!! important "Single Planning & Reviewing Authority"
    同一條交付線（同一主題 / PR / milestone）在同一時間只允許 **1 位 active Planning & Reviewing Agent** 負責 plan baseline、整合與主線回收。
    可以同時有多位 Documentation / Implementation / Test Agents，但不可同時有多位 Planning & Reviewing Agents 對同一交付線做最終裁決。

!!! info "Document-first execution"
    正式流程是：先收斂文件，再由 `Planning & Reviewing Agent` 產出計劃，再做實作，再補 integration / E2E，
    最後仍由同一類 agent 做整合與 accepted delivery 回收。

!!! info "Branch roles and merge authority live elsewhere"
    本頁只定義 agent families、交接順序與 delivery boundaries。
    `main` / `develop` 的 branch roles、isolated worktree policy、merge authority 與 bounded autonomous write roots，
    一律以 [Branch & Worktree Flow](./branch-and-worktree-flow.md) 為準。

!!! tip "Give Implementation Agents room"
    `Implementation Agent` 應在明確 SoT、`Allowed Area`、`Do Not Touch` 與驗收條件下自由選擇具體修改點。
    `Planning & Reviewing Agent` 的工作是之後依結果收斂範圍與補 fixup prompt，不是預先把每輪 prompt 縮成極小檔案清單。

## Collaboration Map

| stage | primary owner | output |
| --- | --- | --- |
| Documentation | Documentation Agent | updated SoT / decision notes |
| Planning & Reviewing (plan pass) | Planning & Reviewing Agent | plan artifact + test backlog |
| Implementation | Frontend / Backend / Core / CLI Agent | code + unit tests + delivery report |
| Test | Test Agent | integration / E2E tests + evidence |
| Planning & Reviewing (merge pass) | Planning & Reviewing Agent | integrated delivery + final verification |

## Agent Families

| Agent family | Primary responsibility | Not responsible for |
|---|---|---|
| Documentation Agents | 與人類開發者討論需求、整理決策、把 SoT 寫進 docs、先定義 architecture / contracts / page specs | 大量 feature code、integration / E2E |
| Planning & Reviewing Agents | 讀 SoT 與現有程式碼、撰寫 plan artifact、拆 implementation slices、列出缺的 integration / E2E coverage、回收 deliverables、做 final verification | 正式文件編輯、大量產品實作 |
| Implementation Agents | 依計劃撰寫 `Frontend / Backend / Core / CLI` 實作與 unit tests | integration tests、E2E tests、最終主線整合、正式文件編輯 |
| Test Agents | 依計劃撰寫 integration / E2E tests、補 test fixtures 與 cross-surface verification | feature unit work、最終 merge authority |

## Role Boundaries

### Documentation Agents

- 負責與人類開發者對齊需求、語意、owner boundary 與 acceptance。
- 若新功能或重構涉及 contract / workflow / shell context / permission model，必須先補或更新 SoT。
- 可直接修改文件，但不得把未確認的設計假設寫成既成事實。

### Planning & Reviewing Agents

- 必須讀 SoT 與現有 code，再產出可交付的 plan artifact。
- 只能修改 `Plans/` 底下的計劃文件，不得直接編輯 `docs/reference/**`。
- 若發現 SoT 缺頁、需要改規格或 owner boundary 有衝突，必須回交 `Documentation Agent`。
- plan artifact 至少要回答：
  - 哪些文件已定義、哪些尚未落地
  - 哪些 implementation slices 需要交給前端 / 後端 / core / CLI Agents
  - 哪些功能尚未具備 integration tests / E2E tests
  - 每個 slice 的 verification 與 non-goals
- prompt 預設應使用 `Allowed Area` 與 `Do Not Touch`，只在必要時補充 `Allowed Files`
- 不應在沒有 plan artifact 的情況下直接大規模派工。
- 回收 implementation / test deliverables 時，負責：
  - conflict resolution
  - final verification
  - accepted slices 的 integration 回收與 regression summary
  - 重讀 SoT 與實際程式碼脈絡後做實質判斷，而不是只檢查 prompt 是否被逐字遵守
  - 若實作過寬或仍有缺口，透過新的 fixup prompt 收縮，而不是要求第一輪 prompt 過度窄化
  - 對 user-visible frontend 交付執行 Playwright-based smoke 驗證，並用 screenshot / 等價視覺證據確認 layout 與互動沒有跑掉

### Implementation Agents

- 固定分成四條 implementation lanes：
  - `Frontend Agent`
  - `Backend Agent`
  - `Core Agent`
  - `CLI Agent`
- 每位 agent 只負責自己被指派 lane 內的 slice 與 unit tests。
- 若任務超出 prompt 的 `Allowed Area`、`Do Not Touch`、lane 邊界或 slice 範圍，必須回交 Planning & Reviewing Agent 重新切分。
- 不負責 integration / E2E test。

### Test Agents

- 只負責 integration tests、E2E tests、cross-surface verification。
- 必須直接依 Planning & Reviewing Agent 的 test backlog 與 SoT 撰寫測試。
- 不應把 integration / E2E 缺口留給 Implementation Agents 臨時補。

## Delivery Flow

1. **Documentation**
   - Documentation Agent 與人類對齊需求。
   - 必要時先更新 SoT。

2. **Planning & Reviewing**
   - Planning & Reviewing Agent 讀文件與程式碼。
   - 產出 plan artifact 與 test backlog。

3. **Implementation**
   - Frontend / Backend / Core / CLI Agents 依 slice 開發。
   - 每位 agent 只做自己被指派 lane 內的 code + unit tests。

4. **Test**
   - Test Agent 根據同一份 plan 補 integration / E2E tests。

5. **Planning & Reviewing**
   - Planning & Reviewing Agent 回收所有 deliverables。
   - 做整合、驗證、accepted slices 回收與最終摘要。

!!! warning "No direct jump from idea to code"
    若需求仍在變、authority boundary 未定、或 SoT 尚未更新，Implementation Agents 不得直接把設計猜進程式碼。

## Required Artifacts

| Stage | Required artifact |
|---|---|
| Documentation | updated SoT pages / decision notes |
| Planning & Reviewing (plan pass) | `Plan Artifact`，含 implementation slices 與 test backlog |
| Implementation | `Delivery Report`，含 commits、changed files、unit test results、known risks |
| Test | `Test Report`，含 scenarios、evidence、integration / E2E results |
| Planning & Reviewing (merge pass) | `Review Merge Report`，含 accepted commits、conflicts、final verification、`develop` integration status，必要時再附 release-promotion note |

## Plan Artifact Minimum Content

Planning & Reviewing Agent 產出的 plan artifact 至少必須包含：

- `Task ID / Topic`
- `Goal`
- `Source of Truth`
- `Current Implementation State`
- `Gap List`
- `Implementation Slices`
- `Test Backlog`
- `Verification Matrix`
- `Open Decisions / Risks`

!!! tip "Plan artifacts are first-class docs"
    若該計劃需要被持續追蹤或多人共同引用，應把它寫成可保存的文件紀錄，而不是只留在短訊息或臨時聊天上下文中。

## Parallelism Rules

1. 同一時間可並行：
   - 多位 Documentation Agents
   - 多位 Implementation Agents
   - 多位 Test Agents
   - 多位 Planning & Reviewing Agents，但必須屬於不同 delivery lines
2. 同一交付線只能有一位 active Planning & Reviewing Agent。
3. 同一 implementation slice 不得同時交給兩位 Implementation Agents。
4. 同一 integration / E2E scenario 不得同時交給兩位 Test Agents。

## Isolation Rules

1. 每位 Agent 必須使用獨立 `git worktree` + branch。
2. 開工前必須執行 `git status --porcelain`。
3. 若工作樹有非本人任務的 dirty changes，不得直接覆蓋。
4. `Allowed Area` 與 `Do Not Touch` 必須在 plan 或 merge prompt 中明確列出。
5. `Allowed Files` 只有在窄範圍 fixup 或高風險手術式改動時才應額外列出。

!!! tip "Read branch policy from the canonical page"
    branch roles、哪一類 agent 可以 merge 回 `develop`、以及 autonomous sandbox/example agents 的 bounded write roots，
    請直接看 [Branch & Worktree Flow](./branch-and-worktree-flow.md)。

## Escalation Rules

| Situation | Required escalation |
|---|---|
| SoT 缺頁或語意衝突 | 回 Documentation Agent |
| slice 邊界不穩或跨多領域 | 回 Planning & Reviewing Agent 重新拆分 |
| integration / E2E 缺口被 implementation 發現 | 回 Planning & Reviewing Agent，並轉交 Test Agent |
| deliverables 彼此衝突 | 交 Planning & Reviewing Agent 做整合與裁決 |

## Forbidden Moves

- Implementation Agent 不得直接宣告 integration / E2E 已完成，除非該工作明確由 Test Agent 交回。
- Implementation Agent 不得自行擴張 slice 邊界、lane 邊界或跨出 `Allowed Area` / `Do Not Touch` 邊界。
- Test Agent 不得順手重寫 feature implementation。
- Planning & Reviewing Agent 不得在未回收 handoff 的情況下假設某工作已完成。
- Documentation Agent 不得把未確認的未來功能寫成現況。
- Planning & Reviewing Agent 不得只給口頭方向而沒有可追蹤的 plan artifact。
- Planning & Reviewing Agent 不得只以 prompt 字面 compliance 作為驗收依據，而不重新檢查 SoT 與實作上下文。

## Related

- [Prompt Grading](./prompt-grading.md)
- [Branch & Worktree Flow](./branch-and-worktree-flow.md)
- [Agent Handoff Formats](./contributor-reporting.md)
- [Phase Gates](./phase-gates.md)

## Agent Rule { #agent-rule }

```markdown
## Multiple Agent Collaboration
- Use four agent families:
    - Documentation Agents
    - Planning & Reviewing Agents
    - Implementation Agents
    - Test Agents
- Documentation Agents:
    - discuss with humans
    - update SoT and architecture/contracts before coding when needed
- Planning & Reviewing Agents:
    - compare docs and code
    - produce a written plan artifact
    - split implementation slices
    - enumerate missing integration/E2E coverage for Test Agents
    - own final verification and accepted-slice integration for the delivery line
    - may edit `Plans/` artifacts only; if SoT must change, hand off to Documentation Agents
    - define `Allowed Area` + `Do Not Touch` for implementation prompts by default
    - review implementation against SoT and product need, not prompt literalism alone
    - use Playwright-based smoke verification plus screenshot or equivalent visual evidence when reviewing user-visible frontend changes
- Implementation Agents:
    - use four implementation lanes:
        - Frontend
        - Backend
        - Core
        - CLI
    - receive assigned slices via prompt (`Allowed Area` + `Do Not Touch` + worktree + verification)
    - own code + unit tests only
    - do not own integration/E2E or final branch integration
- Test Agents:
    - own integration tests and E2E tests
    - execute against the plan artifact and SoT
- Branch roles, worktree policy, merge authority, and bounded autonomous write roots are defined in `Branch & Worktree Flow`.
- Every agent must use an isolated worktree + branch and run `git status --porcelain` before editing.
- Do not skip the order:
    - docs -> planning/reviewing -> implementation -> test -> planning/reviewing
```
