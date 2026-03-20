---
aliases:
  - Julia Core Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Julia-native simulation / analysis core reference surface。
version: v0.4.0
last_updated: 2026-03-21
updated_by: codex
---

# Julia Core

本頁記錄 Julia-native simulation / analysis runtime 的目前邊界，以及 repo 內實際存在的 Julia surface。

!!! info "Current Julia Surface"
    canonical core surface 已收斂到 top-level `core/`。
    目前 repository 內的 Julia surface 主要分成兩類：
    1. `core/simulation/infrastructure/hbsolve.jl` 的 simulation bridge
    2. `src/julia/` 下的 project-level helper 與 plotting utilities

!!! warning "Ownership Boundary"
    Julia runtime 負責數值求解與 Julia-side helper。
    canonical circuit-definition、task lifecycle、trace / provenance contract 仍由 Python-owned core surface 決定。

## Surface Map

=== "Simulation Bridge"

    | Surface | Role |
    |---|---|
    | `core/simulation/infrastructure/hbsolve.jl` | 將 normalized topology、component values、pump / source config 送入 JosephsonCircuits `hbsolve` |
    | JosephsonCircuits.jl runtime | 執行 harmonic balance 求解與矩陣家族導出 |
    | Python-facing bridge payload | 回傳 frequency axis、S / Z / Y family traces、mode metadata、derived scalar traces |

=== "Direct Julia Workflows"

    | Surface | Role |
    |---|---|
    | `docs/how-to/simulation/native-julia.md` | 直接以 repo Julia environment 執行 advanced simulation workflow 的操作路徑 |
    | `src/julia/plotting.jl` | Julia-owned plotting helpers |
    | `src/julia/utils.jl` | Julia helper re-export boundary |

## Current Repository Files

| File | What it means in the current design |
|---|---|
| `core/simulation/infrastructure/hbsolve.jl` | Julia-native simulation bridge owned by core simulation runtime |
| `src/julia/plotting.jl` | Julia-owned plotting / result visualization helpers |
| `src/julia/utils.jl` | helper alias boundary for Julia-side call sites |

## Consumer Pairing

| Consumer | Reads Julia Core through |
|---|---|
| Python simulation application service | [Julia Wrapper](julia-wrapper.md) |
| Advanced Julia users / contributors | [How-to / Native Julia Simulation](../../how-to/simulation/native-julia.md) |
| Julia plotting consumers | [Julia Plotting](julia-plotting.md) |

## Related

- [Julia Wrapper](julia-wrapper.md)
- [Julia Plotting](julia-plotting.md)
- [How-to / Native Julia Simulation](../../how-to/simulation/native-julia.md)
