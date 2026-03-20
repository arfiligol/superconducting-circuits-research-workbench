---
aliases:
  - Core Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Core reference 索引，條列平台核心能力與 Python/Julia 邊界。
version: v0.5.0
last_updated: 2026-03-21
updated_by: codex
---

# Core Reference

本區收錄平台核心能力的 reference surface，涵蓋 Python-owned canonical contracts、Python↔Julia bridge，以及 Julia-native simulation / plotting boundary。

!!! info "How To Read Core Docs"
    先讀 [Python Core](python-core.md) 了解 `sc_core` 與 Python adopter 的 canonical contracts，再讀 [Julia Wrapper](julia-wrapper.md) 看 Python↔Julia bridge，最後讀 [Julia Core](julia-core.md) 與 [Julia Plotting](julia-plotting.md) 查看 Julia-native execution 與 visualization surface。

!!! warning "Boundary"
    `Core` 不等於整個 app。
    session、HTTP transport、CLI presenter、UI state 都不屬於本區；本區只記錄核心計算、canonical contract 與 bridge boundary。

!!! important "Canonical top-level core surface"
    `core/` 是 canonical shared-core folder。
    `src/worker/` 也只能視為 transition residue consumer，不是 core owner。

## Ownership Rules

| Rule | Meaning |
|---|---|
| `sc_core` owns canonical Python contracts | backend、worker、CLI 都是 adopter，不是 owner |
| App surfaces stay outside Core | HTTP schemas、session authority、frontend state 不屬於 Core |
| Julia bridge is still Core-adjacent | Python↔Julia adapter 屬於 core runtime 邊界，但不等於整個 app owner |

## Page Map

=== "Python-Owned Contracts"

    | 頁面 | 核心聚焦 | Primary Code Surface |
    |---|---|---|
    | [Python Core](python-core.md) | `sc_core` 的 circuit-definition、tasking、execution、storage contracts，以及 Python adopters | canonical implementation evidence: `core/sc_core/`, `core/shared/`; `src/worker/` is transition residue consumer only |

=== "Python ↔ Julia Bridge"

    | 頁面 | 核心聚焦 | Primary Code Surface |
    |---|---|---|
    | [Julia Wrapper](julia-wrapper.md) | Python domain model 如何被編譯、驗證、送入 Julia runtime，再映射回 Python result | canonical `core/` bridge surface；implementation evidence: `core/simulation/application/run_simulation.py`, `core/simulation/infrastructure/julia_adapter.py`, `core/simulation/infrastructure/hbsolve.jl` |

=== "Julia-Native Surface"

    | 頁面 | 核心聚焦 | Primary Code Surface |
    |---|---|---|
    | [Julia Core](julia-core.md) | JosephsonCircuits-driven simulation runtime 與 direct Julia workflow boundary | canonical `core/` + Julia runtime surfaces；implementation evidence: `core/simulation/infrastructure/hbsolve.jl`, `src/julia/` |
    | [Julia Plotting](julia-plotting.md) | Julia-owned plotting / visualization helpers | `src/julia/plotting.jl`, `src/julia/utils.jl` |

## Ownership Map

| 想回答的問題 | 應優先查看 |
|---|---|
| canonical circuit-definition / task / storage contract 由誰定義？ | [Python Core](python-core.md) |
| Python application service 如何把 simulation config 送進 Julia？ | [Julia Wrapper](julia-wrapper.md) |
| Julia runtime 目前真正負責哪些模擬能力？ | [Julia Core](julia-core.md) |
| Julia plotting helper 與 figure contract 在哪裡？ | [Julia Plotting](julia-plotting.md) |

!!! success "Coverage Rule"
    若 CLI、backend 或 worker 引入新的核心計算或 contract helper，應能在本區找到對應 page；
    找不到時，代表 Core reference 尚未完整。

## Related

- [Architecture / Canonical Contract Registry](../architecture/canonical-contract-registry.md)
- [CLI Options](../cli/index.md)
