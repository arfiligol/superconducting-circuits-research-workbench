---
aliases:
  - "Contract Versioning"
  - "契約版本策略"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/code-quality
status: stable
owner: docs-team
audience: team
scope: "定義 heavy-development 期間 canonical contracts、資料格式與 adapter payload 的版本與相容性策略"
version: v1.3.0
last_updated: 2026-05-28
updated_by: codex
---

# Contract Versioning

本文件定義 migration 期間 contract 演進的最低要求，避免 `sc_core`、backend、CLI、frontend 之間各自演化。

!!! info "How to read this page"
    先判斷變更碰到哪一種 contract，再判斷變更類型是 additive、soft-breaking 還是 breaking。最後依照 required update set 補齊文件與測試。

!!! important "Heavy Development / No Compatible Fallback"
    目前階段是 **Heavy Development**，不是 release compatibility phase。
    預設政策是 **No Compatible Fallback**：backward compatibility、dual-path adapter、legacy fallback UI、read-compat shim 都不是預設交付要求。
    首要目標是把 current product 打穩，讓下一次真的部署上線時功能充分且穩定。
    既有底層 migration、runtime 或 rebuild 機制可以保留，但不得被 agent 自行升格成產品相容性承諾。

## Decision Map

| 先回答 | 再決定 |
| --- | --- |
| 這是哪一類 contract？ | 需不需要 version-aware 欄位或 lockstep 說明 |
| 這是 additive 還是 breaking？ | 是否必須同步更新 registry / parity / cutover notes |
| 這是 persisted data 嗎？ | 是否需要 migration、rebuild 或 explicit unsupported note |

## Contracts That Must Be Version-Aware

- circuit definition / netlist canonical contract
- dataset / trace / result / provenance contracts
- task submission / task detail / task result contracts
- session / workspace context payloads
- machine-consumable CLI output contracts

## Version Fields

| Contract 類型 | 最低要求 |
| --- | --- |
| persisted data contract | 明確 `schema_version` 或等價欄位 |
| API payload contract | route-level version note 或明確 lockstep branch policy |
| CLI machine output | command docs 中記錄版本或穩定輸出保證 |
| task/result handle | 必須可追到 result/provenance contract 版本 |

## Compatibility Classes

| 類型 | 定義 | 預設處理 |
| --- | --- | --- |
| Additive | 新增可選欄位、附加 metadata、保留舊欄位語意 | 可接受，但仍需更新 reference |
| Soft-breaking | 欄位仍存在，但預設值、排序、空值語意改變 | 視為高風險，需同步寫明行為改變 |
| Breaking | 刪除欄位、改型別、改必要欄位、改 enum / lifecycle 語意 | heavy-development 期間可接受；必須更新 registry / parity / cutover notes / tests |

## Persisted Data Rules

- No Compatible Fallback 不代表可以靜默破壞資料；它代表 read-compatible fallback 不是預設 requirement。
- SQLite metadata、TraceStore payload、export artifact 若因 current product 收斂而 breaking，至少要有下列其一：
  - migration script
  - explicit rebuild path
  - explicit unsupported cutover note
  - read-compat fallback（只有 owner SoT 明確要求時才需要）
  - one-time rebuild strategy，且在 parity matrix 記錄影響範圍
- `sc_core` 與 backend 不得各自維護不同版本解讀規則
- 既有底層 migration / rebuild / reset tooling 可以保留；除非 owner SoT 要求，不需要為了表面相容性把它們擴成 dual-runtime product path

## Compatibility Rules

!!! warning "Do not fake compatibility"
    不要只在 adapter 裡偷偷補 patch，卻讓 registry、parity matrix、reference docs 看起來像完全相容。文件與實作必須同時承認 breaking reality。

| 規則 | 說明 |
| --- | --- |
| Compatibility is opt-in | 沒有 owner SoT 明確要求時，不新增 backward-compatible fallback 或 legacy shim |
| Breaking changes require an explicit note | reference docs、parity matrix、contract registry 與 cutover/migration/rebuild/unsupported notes 必須同步更新 |
| Heavy-development branch is lockstep by default | 目前不承諾 frontend/backend/cli 與 `sc_core` 的跨 minor 版本相容 |
| Persisted data needs an explicit cutover story | DB、TraceStore、export artifact 若失去舊資料可讀性，必須寫明 migrate、rebuild 或 unsupported，不可靜默失效 |

## Required Update Set for Breaking Changes

任何 breaking contract 變更，都必須在同一交付線更新：

1. reference docs
2. [Parity Matrix](../../architecture/parity-matrix.md)
3. [Canonical Contract Registry](../../architecture/canonical-contract-registry.md)
4. cutover / migration / rebuild / unsupported notes
5. 對應測試

!!! tip "Fast check"
    如果你無法在同一交付線同時回答「舊資料要 migrate、rebuild 還是明確不支援、consumer 怎麼知道版本變了、哪些文件要更新」，就還不應該送出 breaking contract change。

## Agent Rule { #agent-rule }

```markdown
## Contract Versioning
- Treat circuit definitions, dataset/trace/result contracts, task contracts, session/workspace payloads, and machine-readable CLI outputs as version-aware surfaces.
- Current mode is **Heavy Development / No Compatible Fallback** until an owner SoT explicitly changes the release phase.
- Backward compatibility is opt-in, not default; do not add dual-path adapters, legacy fallback UI, read-compat shims, or compatibility patches unless an owner SoT requires them.
- Any breaking contract change MUST update:
    - reference docs
    - parity matrix
    - contract registry
    - cutover/migration/rebuild/unsupported notes
    - relevant tests
- During heavy development, assume frontend/backend/cli/`sc_core` evolve in lockstep on the same branch unless an explicit compatibility promise is documented.
- Persisted DB/TraceStore/exported data MUST have an explicit migration, rebuild, or unsupported-cutover story before breaking a contract; read-compat fallback is not required by default.
- Existing low-level migration/runtime/rebuild mechanisms may remain; do not delete them solely because compatibility guarantees are paused.
- Do not hide compatibility patches only inside adapters; document them.
```
