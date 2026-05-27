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
version: v2.7.0
last_updated: 2026-04-29
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
| Implementation | Frontend / Backend / Core / Runner / Docs Agent | code + unit tests + delivery report |
| Test | Test Agent | integration / E2E tests + evidence |
| Planning & Reviewing (merge pass) | Planning & Reviewing Agent | integrated delivery + final verification |

## Agent Families

| Agent family | Primary responsibility | Not responsible for |
|---|---|---|
| Documentation Agents | 與人類開發者討論需求、整理決策、把 SoT 寫進 docs、先定義 architecture / contracts / page specs | 大量 feature code、integration / E2E |
| Planning & Reviewing Agents | 讀 SoT 與現有程式碼、撰寫 plan artifact、拆 implementation slices、列出缺的 integration / E2E coverage、回收 deliverables、做 final verification | 正式文件編輯、大量產品實作 |
| Implementation Agents | 依計劃撰寫 `Frontend / Backend / Core / Runner / Docs` 實作與 unit tests | integration tests、E2E tests、最終主線整合 |
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
  - 哪些 implementation slices 需要交給 frontend / backend / core / runner / docs Agents
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

- 固定分成五條 implementation lanes：
  - `Frontend Agent`
  - `Backend Agent`
  - `Core Agent`
  - `Runner Agent`
  - `Docs Agent`
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
   - Frontend / Backend / Core / Runner / Docs Agents 依 slice 開發。
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

## `Plans/` Lifecycle

`Plans/` 是多 agent 協作期間的 active coordination workspace。
它的目的是讓不同 agents 在同一條 delivery line 中共享計劃、prompt、test backlog、review findings 與 verification expectations。

`Plans/` 不是產品規格的長期 Source of Truth：

- 產品、架構、資料契約與流程規格的長期 SoT 仍在 `docs/reference/**`。
- `Plans/` 只能引用 SoT、拆分工作、記錄當前協作狀態。
- 若 plan 中出現新的規格決策，Planning & Reviewing Agent 必須回交 Documentation Agent 或另開 docs update，把決策移到正式 SoT。

### Lifecycle States

| State | Meaning | Owner action |
| --- | --- | --- |
| `draft` | Planning & Reviewing Agent 正在整理上下文，尚未派工 | 不可直接交給 Implementation/Test Agent |
| `active` | 已可作為當前 delivery line 的派工基準 | 可發給對應 agents |
| `blocked` | 需要人類或 Documentation Agent 決策 | 暫停 implementation/test 派工 |
| `superseded` | 被較新的 plan/fixup plan 取代 | 不可再作為派工基準 |
| `accepted` | 對應 delivery reports 已被 review 接受 | 等待整合或測試 |
| `integrated` | accepted commits 已整合並完成 final verification | 準備 cleanup |
| `retired` | plan 已完成協作使命 | 從 active `Plans/` 移除，或只在明確需要時封存 |

### Creation Rules

Planning & Reviewing Agent 應在以下時機產生 `Plans/` artifacts：

- 需要把一個需求拆給多個 Implementation/Test Agents。
- 需要在 broad implementation 前固定 delivery line 的 scope、non-goals、verification matrix。
- review 後需要把 findings 轉成 multi-agent fixup slices。
- Test Agent 需要一份 integration/E2E backlog 與 tested-commit boundary。

Implementation Agents 與 Test Agents 不應自行建立新的 active plan 來改變 scope。
若他們發現現有 plan 不足，應在 Delivery/Test Report 中回交 Planning & Reviewing Agent。

### Active Plan Rules

- 同一條 delivery line 同一時間只能有一組 active plan baseline。
- 同一組 active plan 可以包含多個 lane-specific prompts，例如 backend/frontend/test prompts。
- 若產生新的 fixup plan，Planning & Reviewing Agent 必須明確標示它取代哪個 plan 或只補哪個 finding。
- Dirty/rejected prototype worktree 不得成為 active plan 的隱性 SoT；只能作為 read-only evidence/reference。

### Cleanup / Retirement Rules

Planning & Reviewing Agent 在 merge pass 必須處理 `Plans/` cleanup：

- 若 plan 只為一次性 agent 派工服務，accepted commits 整合並驗證後，應刪除該 delivery line 的 `Plans/` artifacts。
- 若 plan 仍代表未完成的 workstream backlog，應保留但更新狀態，明確標示 active/superseded/blocked。
- 若 plan 內容包含需要長期保存的設計決策，應把決策移到 `docs/reference/**`，再退休原 plan。
- 不得讓 stale active prompts 留在 `develop`，以免後續 agents 誤用過期指令。
- `Review Merge Report` 應記錄 plan 是已刪除、已退休、還是保留為後續 active backlog。

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
- `Lifecycle State`
- `Cleanup / Retirement Criteria`

!!! tip "Plan artifacts are first-class docs"
    若該計劃需要被多人共同引用，應把它寫成可保存的協作文件紀錄，而不是只留在短訊息或臨時聊天上下文中。
    但它仍是 active coordination artifact，不是長期產品 SoT；完成使命後必須被退休或刪除。

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
    - own the full `Plans/` lifecycle: create, mark active/blocked/superseded, retire, archive, or delete
    - remove or retire stale `Plans/` artifacts during merge/cleanup so old prompts are not reused as current instructions
    - define `Allowed Area` + `Do Not Touch` for implementation prompts by default
    - review implementation against SoT and product need, not prompt literalism alone
    - use Playwright-based smoke verification plus screenshot or equivalent visual evidence when reviewing user-visible frontend changes
- Implementation Agents:
    - use five implementation lanes:
        - Frontend
        - Backend
        - Core
        - Runner
        - Docs
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
