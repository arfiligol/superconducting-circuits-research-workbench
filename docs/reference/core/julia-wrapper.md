---
aliases:
  - Julia Wrapper Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Julia wrapper / bridge reference surface。
version: v0.4.0
last_updated: 2026-03-21
updated_by: codex
---

# Julia Wrapper

本頁記錄 Python 與 Julia 之間的 bridge layer：Python application service 如何驗證、編譯並送出 simulation input，Julia bridge 又如何將結果映射回 Python domain model。

!!! info "Current Location"
    canonical surface 已收斂到 top-level `core/`。
    目前 wrapper surface 仍不在 `sc_core` installable package 裡，
    且 implementation 主要落在 `core/simulation/application/run_simulation.py`、`core/simulation/infrastructure/julia_adapter.py` 與 `core/simulation/infrastructure/hbsolve.jl`。

!!! warning "Boundary"
    Julia wrapper 只負責 marshalling、validation、runtime bootstrap 與 result mapping。
    task semantics、session scope、persistence provenance 仍由 Python core 與 app adapters 擁有。

## Wrapper Path

| File | Responsibility |
|---|---|
| `core/simulation/application/run_simulation.py` | 組裝 simulation application flow，建立 Julia adapter |
| `core/simulation/infrastructure/julia_adapter.py` | 驗證 Python-side inputs、初始化 JuliaCall、呼叫 bridge、將 payload 映射回 `SimulationResult` |
| `core/simulation/infrastructure/hbsolve.jl` | Julia bridge entry point，負責把 Python 送來的 topology / value / source config 交給 JosephsonCircuits.jl |

## Input Contract

| Input | Source | Wrapper Responsibility |
|---|---|---|
| `CircuitDefinition` | Python domain model | 驗證 element references、port shunt resistor、available ports |
| `FrequencyRange` | Python domain model | 轉成 Julia 可接受的 numeric sweep inputs |
| `SimulationConfig` | Python domain model | 驗證 harmonics、solver tolerances、source list、explicit mode tuples |
| compiled topology | `compile_simulation_topology(...)` | 在 compiler boundary 轉成 Julia-compatible tuples |
| component values | canonical component specs | 依 unit multiplier 轉成 Julia runtime values |

## Validation And Error Mapping

| Situation | Wrapper behavior |
|---|---|
| undefined component reference | raise `SimulationInputError`-style `ValueError` |
| port node missing shunt resistor | raise `SimulationInputError`-style `ValueError` |
| unsupported unit | raise `SimulationInputError`-style `ValueError` |
| invalid harmonics / tolerance / iteration config | raise `SimulationInputError`-style `ValueError` |
| mixed implicit / explicit source modes, conflicting pump frequencies | raise `SimulationInputError`-style `ValueError` |
| Julia `SingularException` | map to `SimulationNumericalError`-style `RuntimeError` |
| missing JuliaCall / JosephsonCircuits runtime | fail during wrapper initialization with dependency-focused import/runtime error |

## Output Contract

| Output field family | Mapped into Python result |
|---|---|
| `frequencies_ghz` | frequency axis |
| `s11_real`, `s11_imag` | default S11 traces |
| `s_parameter_*`, `z_parameter_*`, `y_parameter_*` | matrix-family trace maps |
| `mode_indices`, `port_indices` | mode / port metadata |
| `qe_parameter_mode`, `qe_ideal_parameter_mode`, `cm_parameter_mode` | scalar derived trace families |

!!! example "Execution Path"
    Python domain models
    → wrapper validation / compilation
    → Julia bridge call
    → raw Julia payload
    → Python `SimulationResult`

## Related

- [Python Core](python-core.md)
- [Julia Core](julia-core.md)
