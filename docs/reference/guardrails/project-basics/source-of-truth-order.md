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
scope: "定義 heavy-development 過程中 reference docs、Julia Core/Runner、Backend、adapter、legacy behavior 的裁決順序"
version: v2.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Source of Truth Order

本文件定義目前 reference 體系的裁決順序，避免人類、Codex 或 Codex subagents 在 shared contract、backend authority、Runner boundary、page spec 與 implementation 之間自行猜測。

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
   - Public Julia Core / Runner runtime and computation invariants：
     `docs/reference/core/*`
   - User-visible page behavior / page layout / interaction flow：
     `docs/reference/app/frontend/**/*`
   - Notebook workflow behavior：
     `docs/reference/notebooks/*`
   - App frontend/backend/desktop behavior：
     `docs/reference/app/**/*`
2. `docs/reference/architecture/*` 的 registry / parity 文件
3. canonical implementation surface for the concern（例如 Runner concern 的 canonical implementation surface 是 `core/julia/SuperconductingCircuitsRunner/`）
4. adapters 與 application implementations：`app/backend/`、`app/frontend/`、`app/desktop/`、`core/`、`notebooks/`
5. root-level `backend/`、`frontend/`、`desktop/`、`cli/`、`src/` residues 與其他舊行為證據，只算 migration evidence，不構成正式 SoT

## Scope Boundaries

| Layer | What it owns |
| --- | --- |
| `docs/reference/app/shared/*` | app-level shared semantics、workspace/resource/auth/task runtime/audit/error families |
| `docs/reference/app/backend/*` | app-facing authority surfaces、request/response contract、mutation/read model |
| `docs/reference/data-formats/*` | persisted record shape、field semantics、storage payload contract |
| `docs/reference/core/*` | Julia Core / Runner runtime boundary、installable contract、core-owned invariants |
| `docs/reference/app/frontend/**/*` | page purpose、layout、interaction、acceptance |
| `docs/reference/notebooks/*` | Notebook research cockpit and inspection workflows |
| `docs/reference/architecture/*` | owner discovery、registry、cross-layer parity，不能覆寫 owner contract |
| implementations | transport、mapping、storage/runtime integration，不可反向改寫 canonical truth |

## Conflict Handling

### Typical Cases

| 衝突情境 | 裁決方式 |
| --- | --- |
| frontend page spec 與 app/shared/backend 衝突 | 以 `app/shared` + `app/backend` 為準；page spec 需回退成 consumer contract |
| script / old CLI surface 與 app/shared 衝突 | 以 app/shared 或 backend/runner owner docs 為準；CLI 不再是 product surface |
| data formats 與 frontend/backend payload 範例不同 | 以 data formats 的欄位語意為準，再修 frontend/backend surface |
| Julia Core / Runner 與 backend/frontend adapter 不同 | 先修 adapter；若 core/runner contract 缺規格，再同步補 docs 與 implementation |
| registry / parity 與 owner docs 不同 | 以 owner docs 為準，先修 registry / parity |
| intentional compatibility exception | 必須在 parity matrix 或 contract registry 顯式標記，不可只留在程式碼內 |
| compatibility fallback 與 current owner SoT 衝突 | 以 current owner SoT 為準；fallback 是 opt-in，不是預設裁決 |

## Interpretation Rules

- **Owner-first, not consumer-first**：
  page spec、notebook docs、scripts 與 architecture registry 都是重要 consumer，但不能覆寫 owner contract。
- **Reference-first**：
  若 reference 文件與 implementation 行為衝突，預設以 reference 文件為準。
- **Implementation is not silent law**：
  目前 code path、adapter 行為與過去輸出都不是自動 canonical truth。
- **Julia Core / Runner beats adapters**：
  若 Julia Core / Runner contract 與 adapter 行為衝突，先修 adapter；只有在 contract 本身不完整時才修 core/runner 與其文件。
- **New app/core/notebooks boundaries beat old root layout**：
  `app/backend/`、`app/frontend/`、`app/desktop/`、`core/julia/`、`core/python/`、`notebooks/` 才是 architecture-level surfaces。
  root `backend/`、`frontend/`、`desktop/`、`cli/` 或 `src/` 若仍有內容，只能視為 migration residue，不可反向推導 future canonical topology。
- **Do not silently revise docs to match code**：
  發現 implementation 與 reference 不一致時，不可直接改文件湊合程式碼，除非使用者明確確認規格要變。
- **Parity exceptions must be explicit**：
  若確定要保留相容特例，必須在 parity matrix 或 contract registry 顯式記錄，不能只留在程式碼內。
- **Compatibility fallback is opt-in**：
  現階段是 Heavy Development / No Compatible Fallback；除非 owner SoT 明確要求，不得用舊行為、舊資料或 legacy adapter 反向要求 current product path 保留相容層。

## Required Follow-up Documents

本文件不單獨生效。若發生跨層衝突，應一併檢查：

- [App / Backend / Tasks & Execution](../../app/backend/tasks-execution.md)
- [App / Backend / Datasets & Results](../../app/backend/datasets-results.md)
- [Identity & Workspace Model](../../app/shared/identity-workspace-model.md)
- [Response & Error Contract](../../app/shared/response-and-error-contract.md)
- [Parity Matrix](../../architecture/parity-matrix.md)
- [Canonical Contract Registry](../../architecture/canonical-contract-registry.md)

## Agent Rule { #agent-rule }

```markdown
## Source of Truth Order
- Resolve conflicts by concern owner first:
    - app collaboration/session/auth/workspace/task runtime/audit/error -> `docs/reference/app/shared/*` + `docs/reference/app/backend/*`
    - persisted payload/schema fields -> `docs/reference/data-formats/*`
    - Julia Core / Runner runtime invariants -> `docs/reference/core/*`
    - page behavior/layout -> `docs/reference/app/frontend/**/*`
    - notebook workflow behavior -> `docs/reference/notebooks/*`
- Use `docs/reference/architecture/*` only as registry/parity guidance, not as the primary owner when owner docs already exist.
- Treat implementation and old behavior as evidence, not automatic canonical truth.
- If owner docs and consumer docs conflict, prefer the owner docs unless the user explicitly changes the spec.
- If Julia Core / Runner and adapters conflict, fix the adapter first unless the canonical contract is incomplete.
- Treat root-level `backend/`, `frontend/`, `desktop/`, `cli/`, and `src/` residues as migration evidence only; do not infer future architecture boundaries from them.
- Record any intentional compatibility exception in the parity matrix or contract registry.
- Compatibility fallback is opt-in during Heavy Development / No Compatible Fallback; do not add or preserve legacy fallback paths unless an owner SoT explicitly requires them.
```
