---
aliases:
  - "Source of Truth Order"
  - "單一真理優先順序"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/project-basics
status: stable
owner: docs-team
audience: team
scope: "定義 reference docs、Julia Core authoring、Julia Runner、Backend、adapter 與 retired surfaces 的裁決順序"
version: v3.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Source of Truth Order

本文件定義 reference 體系的裁決順序，避免人類、Codex 或 Codex subagents 在 shared contract、backend authority、Runner boundary、page spec 與 implementation 之間自行猜測。

!!! warning "Concern-first resolution"
    不可只看「哪個檔案層級比較前面」就裁決衝突。
    先判定這個問題屬於哪個 concern，再回到該 concern 的 owner 文件。

## Canonical Ordering

若同一能力的描述彼此衝突，應依下列順序裁決：

1. concern owner 對應的 reference 文件：
   - App collaboration / session / auth / workspace / task runtime / audit / common error contract：
     `docs/reference/app/shared/*` + `docs/reference/app/backend/*`
   - Persisted payload / storage schema / field semantics：
     `docs/reference/data-formats/*`
   - Public Julia Core authoring invariants：
     `docs/reference/julia-core/*`
   - Julia Core / Runner runtime boundary and package invariants：
     `docs/reference/core/*`
   - User-visible page behavior / page layout / interaction flow：
     `docs/reference/app/frontend/**/*`
   - Notebook workflow behavior：
     `docs/reference/notebooks/*`
   - App frontend/backend/desktop behavior：
     `docs/reference/app/**/*`
2. `docs/reference/architecture/*` 的 owner-boundary 與 canonical contract registry 文件
3. canonical implementation surface for the concern（例如 Runner concern 的 canonical implementation surface 是 `core/julia/SuperconductingCircuitsRunner/`）
4. adapters 與 application implementations：`app/backend/`、`app/frontend/`、`app/desktop/`、`core/`、`notebooks/`
5. retired surfaces and old behavior evidence have no authority over current product contracts

## Scope Boundaries

| Layer | What it owns |
| --- | --- |
| `docs/reference/app/shared/*` | app-level shared semantics、workspace/resource/auth/task runtime/audit/error families |
| `docs/reference/app/backend/*` | app-facing authority surfaces、request/response contract、mutation/read model |
| `docs/reference/data-formats/*` | persisted record shape、field semantics、storage payload contract |
| `docs/reference/julia-core/*` | Julia Core authoring model、Circuit Plan、components、endpoints、compiler、compiled output、worker-safe API |
| `docs/reference/core/*` | Julia Core / Runner runtime boundary、installable contract、package-level invariants |
| `docs/reference/app/frontend/**/*` | page purpose、layout、interaction、acceptance |
| `docs/reference/notebooks/*` | Notebook research cockpit and inspection workflows |
| `docs/reference/architecture/*` | owner discovery、contract registry、cross-layer boundary map；不能覆寫 owner contract |
| implementations | transport、mapping、storage/runtime integration，不可反向改寫 canonical truth |

## Conflict Handling

### Typical Cases

| 衝突情境 | 裁決方式 |
| --- | --- |
| frontend page spec 與 app/shared/backend 衝突 | 以 `app/shared` + `app/backend` 為準；page spec 需回退成 consumer contract |
| script / old CLI surface 與 app/shared 衝突 | 以 app/shared 或 backend/runner owner docs 為準；CLI 不再是 product surface |
| data formats 與 frontend/backend payload 範例不同 | 以 data formats 的欄位語意為準，再修 frontend/backend surface |
| Julia Core / Runner 與 backend/frontend adapter 不同 | 先修 adapter；若 core/runner contract 缺規格，再同步補 docs 與 implementation |
| architecture registry 與 owner docs 不同 | 以 owner docs 為準，先修 registry |
| product behavior needs an exception | 必須在 owner docs 與 canonical contract registry 顯式標記，不可只留在程式碼內 |
| retired behavior 與 owner SoT 衝突 | 以 owner SoT 為準；retired behavior 不構成產品 contract |

## Interpretation Rules

- **Owner-first, not consumer-first**：
  page spec、notebook docs、scripts 與 architecture registry 都是重要 consumer，但不能覆寫 owner contract。
- **Reference-first**：
  若 reference 文件與 implementation 行為衝突，預設以 reference 文件為準。
- **Implementation is not silent law**：
  code path、adapter 行為與過去輸出都不是自動 canonical truth。
- **Julia Core / Runner beats adapters**：
  若 Julia Core / Runner contract 與 adapter 行為衝突，先修 adapter；只有在 contract 本身不完整時才修 core/runner 與其文件。
- **Current app/core/notebooks boundaries beat old root layout**：
  `app/backend/`、`app/frontend/`、`app/desktop/`、`core/julia/`、`core/python/`、`notebooks/` 才是 architecture-level surfaces。
  root `backend/`、`frontend/`、`desktop/`、`cli/` 或 `src/` 若仍有內容，只能視為 retired residue，不可反向推導 canonical topology。
- **Do not silently revise docs to match code**：
  發現 implementation 與 reference 不一致時，不可直接改文件湊合程式碼，除非使用者明確確認規格要變。
- **Exceptions must be explicit**：
  若確定產品 contract 需要特例，必須在 owner docs 與 canonical contract registry 顯式記錄，不能只留在程式碼內。
- **Legacy fallback is not a product contract**：
  除非 owner SoT 明確要求，不得用舊行為、舊資料或 retired adapter 反向要求 current product path 保留相容層。

## Required Follow-up Documents

本文件不單獨生效。若發生跨層衝突，應一併檢查：

- [App / Backend / Tasks & Execution](../../app/backend/tasks-execution.md)
- [App / Backend / Datasets & Results](../../app/backend/datasets-results.md)
- [Identity & Workspace Model](../../app/shared/identity-workspace-model.md)
- [Response & Error Contract](../../app/shared/response-and-error-contract.md)
- [Canonical Contract Registry](../../architecture/canonical-contract-registry.md)

## Agent Rule { #agent-rule }

```markdown
## Source of Truth Order
- Resolve conflicts by concern owner first:
    - app collaboration/session/auth/workspace/task runtime/audit/error -> `docs/reference/app/shared/*` + `docs/reference/app/backend/*`
    - persisted payload/schema fields -> `docs/reference/data-formats/*`
    - Julia Core authoring invariants -> `docs/reference/julia-core/*`
    - Julia Core / Runner runtime boundary and package invariants -> `docs/reference/core/*`
    - page behavior/layout -> `docs/reference/app/frontend/**/*`
    - notebook workflow behavior -> `docs/reference/notebooks/*`
- Use `docs/reference/architecture/*` only as owner-boundary and canonical contract registry guidance, not as the primary owner when owner docs already exist.
- Treat implementation and old behavior as evidence, not automatic canonical truth.
- If owner docs and consumer docs conflict, prefer the owner docs unless the user explicitly changes the spec.
- If Julia Core / Runner and adapters conflict, fix the adapter first unless the canonical contract is incomplete.
- Treat root-level `backend/`, `frontend/`, `desktop/`, `cli/`, and `src/` residues as retired surfaces with no authority over product boundaries.
- Record intentional product-contract exceptions in the owner docs and canonical contract registry.
- Legacy fallback is not a product contract unless an owner SoT explicitly requires it.
```
