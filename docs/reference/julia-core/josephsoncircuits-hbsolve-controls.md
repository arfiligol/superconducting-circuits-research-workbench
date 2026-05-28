---
aliases:
  - JosephsonCircuits hbsolve Controls
  - HB Solver Controls
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Defines first-class, whitelisted, and unsupported JosephsonCircuits.jl hbsolve controls for Julia Core and Runner use.
version: v1.3.1
last_updated: 2026-05-29
updated_by: codex
---

# JosephsonCircuits hbsolve Controls

This page defines the Julia Core contract for JosephsonCircuits.jl `hbsolve` controls. Product Runner execution should use typed first-class controls and a small whitelist of optional kwargs instead of passing arbitrary solver internals through task payloads.

The initial inventory is derived from the official [JosephsonCircuits.jl reference](https://josephsoncircuits.org/stable/reference/) and official [JosephsonCircuits.jl examples](https://github.com/kpobrien/JosephsonCircuits.jl).

The product-aligned Core path is `HBProblemSpec` plus `run_hb_problem`. This page documents the lower-level JosephsonCircuits-facing controls and call shapes that `HBProblemSpec` normalizes into.

## Official Example Inventory

This inventory is not allowed to be hand-wavy. If a control is promoted to first-class or optional-whitelisted, the official example or reference source that motivated it must be listed here.

| Example | Source / URL | Observed call shape | `hbsolve` inputs used | Source mode shape | Solver flags | Outputs inspected |
| --- | --- | --- | --- | --- | --- | --- |
| Single-pump JPA | [official examples](https://josephsoncircuits.org/stable/#Josephson-parametric-amplifier-(JPA)) | `Npumpharmonics = (16,)`; `Nmodulationharmonics = (8,)`; `hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)` | `ws`, `wp`, `sources`, `Nmodulationharmonics`, `Npumpharmonics`, `circuit`, `circuitdefs` | `(1,)` | four-wave mixing default | `S` |
| Double-pump JPA | [official examples](https://josephsoncircuits.org/stable/#Double-pumped-Josephson-parametric-amplifier-(JPA)) | `Npumpharmonics = (8, 8)`; `Nmodulationharmonics = (8, 8)`; `hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)` | same family with two pump frequencies | `(1, 0)`, `(0, 1)` | pump harmonic tuples for two independent pumps | `S` |
| Flux-pumped JPA | [official examples](https://josephsoncircuits.org/stable/#Flux-pumped-Josephson-parametric-amplifier-(JPA)) | `sources = [(mode=(0,), port=2, current=Idc), (mode=(1,), port=2, current=Ip)]`; `Npumpharmonics = (16,)`; `Nmodulationharmonics = (8,)`; `hbsolve(...; dc=true, threewavemixing=true, fourwavemixing=true)` | same family with DC and pump sources | `(0,)`, `(1,)` | `dc`, `threewavemixing`, `fourwavemixing` | `S` |
| SNAIL PA | [official repository README](https://github.com/kpobrien/JosephsonCircuits.jl#snail-parametric-amplifier) | `hbsolve(...; dc=true, threewavemixing=true, fourwavemixing=true)` | same family with DC and pump sources | `(0,)`, `(1,)` | `dc`, `threewavemixing`, `fourwavemixing` | `S` |
| JTWPA | [official examples](https://josephsoncircuits.org/stable/#Josephson-traveling-wave-parametric-amplifier-(JTWPA)) | `Npumpharmonics = (20,)`; `Nmodulationharmonics = (10,)`; `hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)` | same family with signal, pump, and idler modes | `(1,)` plus idler output modes | `Npumpharmonics = (20,)`, `Nmodulationharmonics = (10,)` | `S`, `QE`, `QEideal`, `CM` |
| Advanced solver tuning | [official examples](https://josephsoncircuits.org/stable/#Example-with-switchofflinesearchtol) and [reference](https://josephsoncircuits.org/stable/reference/) | `hbsolve(...; switchofflinesearchtol=..., alphamin=..., iterations=...)` | same family with solver tuning | varies | `switchofflinesearchtol`, `alphamin`, `iterations` | varies |

!!! note "Pump-off is still a real source slot"
    Official examples include pump-off cases where the pump source remains present and the current value is `0.0`. Julia Core treats that as intentional source-off behavior, not fake compute or a missing pump.

## First-Class Controls

These controls should become typed product / Runner controls because they commonly appear in the official examples, affect HB problem shape or outputs, and are important for reproducibility.

```julia
HBSolverControls(
    pump_frequencies_hz,
    n_pump_harmonics,
    n_modulation_harmonics,
    dc,
    threewavemixing,
    fourwavemixing,
    returnS,
    returnZ,
    returnQE,
    returnCM,
    sorting,
    keyedarrays,
)
```

Julia Core should normalize product-facing frequency values from Hz to the angular-frequency values expected by JosephsonCircuits.jl.

| Control | Contract |
| --- | --- |
| `pump_frequencies_hz` | runtime pump-frequency values bound to declared `PumpAxis` entries |
| `n_pump_harmonics` | harmonic truncation for pump axes; shape follows `pump_frequencies_hz` / `wp` |
| `n_modulation_harmonics` | harmonic truncation for small-signal / modulation / linearized signal basis; not required to match pump-axis count |
| `dc` | enables explicit DC mode handling |
| `threewavemixing` | enables three-wave mixing terms |
| `fourwavemixing` | enables four-wave mixing terms |
| `returnS` | requests scattering-parameter output |
| `returnZ` | requests impedance output |
| `returnQE` | requests quantum-efficiency output |
| `returnCM` | requests commutation-relation output |
| `sorting` | controls target node ordering behavior |
| `keyedarrays` | controls keyed-array output shape |

## Control Status Registry

Every listed control has an explicit status.

| Control | Status | Source |
| --- | --- | --- |
| `pump_frequencies_hz` | first-class | official examples use `wp` |
| `n_modulation_harmonics` | first-class | official examples use `Nmodulationharmonics` |
| `n_pump_harmonics` | first-class | official examples use `Npumpharmonics` |
| `dc` | first-class | flux-pumped and SNAIL examples |
| `threewavemixing` | first-class | flux-pumped and SNAIL examples |
| `fourwavemixing` | first-class | flux-pumped and SNAIL examples |
| `returnS` | first-class | reference and examples inspect `S` |
| `returnZ` | first-class | reference output control |
| `returnQE` | first-class | JTWPA / reference output control |
| `returnCM` | first-class | JTWPA / reference output control |
| `sorting` | first-class | reference output / indexing control |
| `keyedarrays` | first-class | reference output / indexing control |
| `switchofflinesearchtol` | optional-whitelisted | advanced solver tuning example |
| `alphamin` | optional-whitelisted | advanced solver tuning example |
| `iterations` | optional-whitelisted | advanced solver tuning example |
| `ftol` | optional-whitelisted | reference nonlinear solve control |
| `nbatches` | optional-whitelisted | reference batching control |
| `maxintermodorder` | optional-whitelisted | reference mode-truncation control; contributes to `hb_problem_shape_key` |
| `returnSnoise` | unsupported | reference-only output family |
| `returnnodeflux` / `returnvoltage` | unsupported | reference-only node output families |
| adjoint output flags | unsupported | reference-only output families |
| sensitivity flags | unsupported | reference marks sensitivity APIs as in progress |
| custom `factorization` | research-only | reference accepts a runtime object |

## Product Defaults

The product default should request all core output families.

```julia
HBSolverControls(
    pump_frequencies_hz = Dict(:pump => 8.0e9),
    n_pump_harmonics = Dict(:pump => 16),
    n_modulation_harmonics = (8,),
    dc = false,
    threewavemixing = false,
    fourwavemixing = true,
    returnS = true,
    returnZ = true,
    returnQE = true,
    returnCM = true,
    sorting = :name,
    keyedarrays = false,
)
```

`n_pump_harmonics` can be represented as a named map keyed by pump-axis ID. `n_modulation_harmonics` may be a tuple because it belongs to the modulation basis, not the pump-axis map.

Exact default numeric values may be adjusted per circuit family, but the default return flags are all `true`.

## Example Call Shapes

The target Julia Core API normalizes user-facing values into JosephsonCircuits-facing shapes like these official examples.

These snippets are reference call shapes, not the preferred product or Runner entry point. Product-aligned code should build an `HBProblemSpec` and call `run_hb_problem`; low-level `run_hbsolve` must stay consistent with that normalized problem shape.

Single-pump JPA:

```julia
ws = 2*pi*(4.5:0.001:5.0)*1e9
wp = (2*pi*4.75001*1e9,)
sources = [(mode=(1,), port=1, current=Ip)]
Npumpharmonics = (16,)
Nmodulationharmonics = (8,)
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)
```

Double-pump JPA:

```julia
wp = (2*pi*4.65001*1e9, 2*pi*4.85001*1e9)
sources = [
    (mode=(1, 0), port=1, current=Ip),
    (mode=(0, 1), port=1, current=Ip),
]
Npumpharmonics = (8, 8)
Nmodulationharmonics = (8, 8)
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)
```

Flux-pumped / DC style:

```julia
sources = [
    (mode=(0,), port=2, current=Idc),
    (mode=(1,), port=2, current=Ip),
]
Npumpharmonics = (16,)
Nmodulationharmonics = (8,)
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics,
    circuit, circuitdefs; dc=true, threewavemixing=true, fourwavemixing=true)
```

JTWPA:

```julia
Npumpharmonics = (20,)
Nmodulationharmonics = (10,)
hbsolve(ws, wp, sources, Nmodulationharmonics, Npumpharmonics, circuit, circuitdefs)
```

## Scalar Convenience

For single-pump or single-modulation cases, user-facing APIs may accept a single integer for harmonic counts. Julia Core normalizes that scalar into the tuple shape required by JosephsonCircuits.jl.

Pump harmonics:

```julia
n_pump_harmonics = 16
```

normalizes to:

```julia
Npumpharmonics = (16,)
```

For multiple pump axes, use named entries:

```julia
n_pump_harmonics = Dict(
    :pump_1 => 8,
    :pump_2 => 8,
)
```

Modulation harmonics:

```julia
n_modulation_harmonics = 8
```

normalizes to:

```julia
Nmodulationharmonics = (8,)
```

Users may also provide explicit tuple form:

```julia
n_modulation_harmonics = (8, 8)
```

## Optional Whitelisted Kwargs

Some solver controls are useful for research and troubleshooting, but should remain explicitly whitelisted in product Runner payloads.

```julia
optional_hb_kwargs::Dict{Symbol,Any}
```

Initial whitelist:

```julia
:switchofflinesearchtol
:alphamin
:iterations
:ftol
:nbatches
:maxintermodorder
```

Rules:

- product Runner path must reject unknown kwargs;
- Pluto research APIs require a separate source-of-truth decision before accepting any wider pass-through;
- optional kwargs must be recorded in provenance.
- `maxintermodorder` contributes to `hb_problem_shape_key`.

## Unsupported Product Runner Controls

Unsupported controls must fail clearly in product Runner execution until Julia Core documents and implements them.

| Control | Example source | Reason not yet supported | Expected failure behavior | Future note |
| --- | --- | --- | --- | --- |
| `returnSnoise` | JosephsonCircuits reference | noise result schema is not mapped to TraceStore yet | reject in Runner payload | add a noise observable request and result schema |
| `returnnodeflux` / `returnvoltage` | JosephsonCircuits reference | node-resolved outputs need compiled node provenance and storage schema | reject in Runner payload | expose through diagnostic / research result schema |
| adjoint output flags | JosephsonCircuits reference | adjoint result families need separate observable contracts | reject in Runner payload | add explicit adjoint observable request types |
| sensitivity flags | JosephsonCircuits reference | sensitivity APIs are marked as in progress upstream and need stable provenance | reject in Runner payload | revisit after Core owns sensitivity contracts |
| custom `factorization` | JosephsonCircuits reference | runtime object injection is not a product task payload contract | reject in Runner payload | expose only through trusted local Julia configuration if needed |

## Shape Validation Rules

For ordered pump-axis controls:

```text
length(pump_frequencies_hz) == length(n_pump_harmonics)
```

`n_modulation_harmonics` is validated against the small-signal / linearized modulation model, not directly against pump-axis count.

For named-axis schemas:

```text
keys(pump_frequencies_hz) == keys(n_pump_harmonics)
```

`n_modulation_harmonics` belongs to the signal/modulation frequency basis declared by `HBIntent` or `HBProblemSpec`.

Source mode rules:

- source mode tuple length must match the pump-axis count;
- DC-only mode must be represented explicitly and allowed by `HBIntent`;
- DC bias is represented as `HBSourceSlot(mode = (0,))`;
- DC bias current is bound through `source_currents`, not a separate DC binding map;
- `controls.dc = true` is required when a DC bias source slot is declared;
- `current_a = 0.0` is valid;
- missing source slot binding is invalid unless the source slot declares an explicit default;
- unknown source slot ID is invalid.

Optional kwargs rules:

- product Runner rejects unknown `optional_hb_kwargs`;
- optional kwargs must be recorded in provenance;
- optional kwargs that change solver problem shape contribute to `hb_problem_shape_key`;
- optional kwargs that only change numeric convergence contribute to `run_value_key`.

## Source Semantics

The canonical JosephsonCircuits source entry produced by Julia Core is:

```julia
(mode = (...), port = N, current = I)
```

Product requests bind source currents by source slot ID:

```json
{
  "runtime_bindings": {
    "source_currents": {
      "dc_bias": 0.000001,
      "pump_in": 0.0
    }
  }
}
```

Rules:

- `current_a = 0.0` is legal;
- source role, source mode, and source port are declared in CircuitPlan source slots;
- runtime only binds current values by source slot ID;
- DC bias uses the same binding map with an `HBSourceSlot(mode = (0,))`;
- DC handling is enabled by `controls.dc = true`;
- Julia Core maps validated source slots to JosephsonCircuits `(mode, port, current)` entries.

## Unsupported Ambiguous Source Fields

Fields named `target`, UI-level drive magnitude, or unlabeled drive values are not HB source semantics.

Rules:

- product Runner rejects ambiguous drive fields;
- Runner must not convert ambiguous drive magnitude into physical current;
- Runner must not create source slots from payload fields;
- future conversion from dBm, voltage, or current requires a separate calibrated source model.

## Implementation Status

This page is stable as the target source of truth. It is not claiming that every concept is already implemented.

| Concept | Target contract | Current implementation | Status |
| --- | --- | --- | --- |
| `ExternalPort` | first-class CircuitPlan declaration | currently approximated by `metadata[:external_ports]` in MVP | target |
| `HBIntent` | first-class plan-level intent | not implemented as a struct yet | target |
| `HBSourceSlot` | first-class source slot declaration | not implemented yet | target |
| `HBObservableRequest` | first-class observable declaration | current Runner extraction still MVP / trace-specific | target |
| `HBSolverControls` | typed first-class controls | current Runner only partially maps controls | target |
| `optional_hb_kwargs` | whitelist only | not fully implemented | target |
| `current = 0.0` | valid source-off runtime binding | should be accepted | design-stable |

## Related

- [HB Simulation Intent](hb-simulation-intent.md)
- [Runner-Safe API](runner-safe-api.md)
- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
