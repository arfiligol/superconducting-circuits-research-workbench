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
scope: "定義 heavy-development 過程中 reference docs、shared core、adapter、legacy behavior 的裁決順序"
version: v1.5.0
last_updated: 2026-05-28
updated_by: codex
---

# Source of Truth Order

本文件定義目前 reference 體系的裁決順序，避免 Documentation / Planning & Reviewing / Implementation / Test Agents 在 shared contract、backend authority、page spec、CLI surface 與 implementation 之間自行猜測。

!!! warning "Concern-first resolution"
    不可只看「哪個檔案層級比較前面」就裁決衝突。
    先判定這個問題屬於哪個 concern，再回到該 concern 的 owner 文件。

## Canonical Ordering

若同一能力的描述彼此衝突，應依下列順序裁決：

1. concern owner 對應的 reference 文件：
   - App collaboration / session / auth / workspace / queue / runtime / audit / common error contract：
     `docs/reference/app/shared/*` + `docs/reference/app/backend/*`
   - Persisted payload / storage schema / field semantics：
     `docs/reference/data-formats/*`
   - Public core runtime / computation invariants：
     `docs/reference/core/*`
   - User-visible page behavior / page layout / interaction flow：
     `docs/reference/app/frontend/**/*`
   - Standalone CLI command surface / local runtime behavior：
     `docs/reference/cli/*`
2. `docs/reference/architecture/*` 的 registry / parity 文件
3. canonical implementation surface for the concern（例如 core concern 的 canonical implementation surface 是 `core/*`）
4. adapters 與 application implementations：`backend/`、`frontend/`、`core/`、`cli/`、`desktop/`、`legacy/`
5. root-level `src/` residues（例如 `src/app/`、`src/worker/`）與其他舊行為證據，只算 migration evidence，不構成正式 SoT

## Scope Boundaries

| Layer | What it owns |
| --- | --- |
| `docs/reference/app/shared/*` | app-level shared semantics、workspace/resource/auth/runtime/audit/error families |
| `docs/reference/app/backend/*` | app-facing authority surfaces、request/response contract、mutation/read model |
| `docs/reference/data-formats/*` | persisted record shape、field semantics、storage payload contract |
| `docs/reference/core/*` | reusable core runtime boundary、installable contract、core-owned invariants |
| `docs/reference/app/frontend/**/*` | page purpose、layout、interaction、acceptance |
| `docs/reference/cli/*` | standalone CLI command names、local runtime behavior、machine-readable output |
| `docs/reference/architecture/*` | owner discovery、registry、cross-layer parity，不能覆寫 owner contract |
| implementations | transport、mapping、storage/runtime integration，不可反向改寫 canonical truth |

## Conflict Handling

### Typical Cases

| 衝突情境 | 裁決方式 |
| --- | --- |
| frontend page spec 與 app/shared/backend 衝突 | 以 `app/shared` + `app/backend` 為準；page spec 需回退成 consumer contract |
| CLI surface 與 app/shared 衝突 | 若 concern 屬於 app collaboration model，CLI 必須收斂；若 concern 屬於 standalone local runtime，CLI 自有 contract 為準 |
| data formats 與 frontend/backend payload 範例不同 | 以 data formats 的欄位語意為準，再修 frontend/backend surface |
| `sc_core` 與 backend/frontend/cli adapter 不同 | 先修 adapter；若 `sc_core` 缺規格，再同步補 docs 與 `sc_core` |
| registry / parity 與 owner docs 不同 | 以 owner docs 為準，先修 registry / parity |
| intentional compatibility exception | 必須在 parity matrix 或 contract registry 顯式標記，不可只留在程式碼內 |
| compatibility fallback 與 current owner SoT 衝突 | 以 current owner SoT 為準；fallback 是 opt-in，不是預設裁決 |

## Interpretation Rules

- **Owner-first, not consumer-first**：
  page spec、CLI surface 與 architecture registry 都是重要 consumer，但不能覆寫 owner contract。
- **Reference-first**：
  若 reference 文件與 implementation 行為衝突，預設以 reference 文件為準。
- **Implementation is not silent law**：
  目前 code path、adapter 行為與過去輸出都不是自動 canonical truth。
- **Shared core beats adapters**：
  若 `sc_core` 與 adapter 行為衝突，先修 adapter；只有在 contract 本身不完整時才修 `sc_core` 與其文件。
- **Top-level boundaries beat old root `src/` layout**：
  `backend/`、`frontend/`、`core/`、`cli/`、`desktop/`、`legacy/` 才是 architecture-level surfaces。
  root `src/` 若仍有內容，只能視為 migration residue，不可反向推導 future canonical topology。
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
    - app collaboration/session/auth/workspace/runtime/audit/error -> `docs/reference/app/shared/*` + `docs/reference/app/backend/*`
    - persisted payload/schema fields -> `docs/reference/data-formats/*`
    - core runtime invariants -> `docs/reference/core/*`
    - page behavior/layout -> `docs/reference/app/frontend/**/*`
    - standalone CLI local runtime/command surface -> `docs/reference/cli/*`
- Use `docs/reference/architecture/*` only as registry/parity guidance, not as the primary owner when owner docs already exist.
- Treat implementation and old behavior as evidence, not automatic canonical truth.
- If owner docs and consumer docs conflict, prefer the owner docs unless the user explicitly changes the spec.
- If `sc_core` and adapters conflict, fix the adapter first unless the canonical contract is incomplete.
- Treat root-level `src/` residues as migration evidence only; do not infer future architecture boundaries from them.
- Record any intentional compatibility exception in the parity matrix or contract registry.
- Compatibility fallback is opt-in during Heavy Development / No Compatible Fallback; do not add or preserve legacy fallback paths unless an owner SoT explicitly requires them.
```
