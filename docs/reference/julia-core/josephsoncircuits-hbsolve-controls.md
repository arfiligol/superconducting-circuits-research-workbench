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
version: v1.0.0
last_updated: 2026-05-29
updated_by: codex
---

# JosephsonCircuits hbsolve Controls

This page defines the Julia Core contract for JosephsonCircuits.jl `hbsolve` controls. Product Runner execution should use typed first-class controls and a small whitelist of optional kwargs instead of passing arbitrary solver internals through task payloads.

The initial inventory is derived from the official [JosephsonCircuits.jl reference](https://josephsoncircuits.org/stable/reference/) and official [JosephsonCircuits.jl examples](https://github.com/kpobrien/JosephsonCircuits.jl).

## Official Example Inventory

| Example | `hbsolve` inputs used | Source mode shape | Solver flags | Outputs inspected |
| --- | --- | --- | --- | --- |
| Single-pump JPA | `ws`, `wp`, `sources`, `Nmodulationharmonics`, `Npumpharmonics`, `circuit`, `circuitdefs` | `(1,)` | default HB settings, four-wave mixing default | `S` |
| Double-pump JPA | same family with two pump frequencies | `(1, 0)`, `(0, 1)` | pump harmonic tuples for two independent pumps | `S` |
| Flux-pumped / DC JPA | same family with DC and pump sources | `(0,)`, `(1,)` | `dc=true`, `threewavemixing=true`, `fourwavemixing=true` | `S` |
| SNAIL PA | same family with DC and pump sources | `(0,)`, `(1,)` | `dc=true`, `threewavemixing=true`, `fourwavemixing=true` | `S` |
| JTWPA | same family with signal, pump, and idler modes | `(1,)` plus idler output modes | larger harmonic counts | `S`, `QE`, `QEideal`, `CM` |
| Advanced examples | same family with solver tuning | varies | `switchofflinesearchtol`, `alphamin`, `iterations` | `S`, `QE`, `QEideal`, `CM` |

!!! note "Pump-off is still a real source slot"
    Official examples include pump-off cases where the pump source remains present and the current value is `0.0`. Julia Core treats that as intentional source-off behavior, not fake compute or a missing pump.

## First-Class Controls

These controls should become typed product / Runner controls because they commonly appear in the official examples, affect HB problem shape or outputs, and are important for reproducibility.

```julia
HBSolverControls(
    pump_frequencies_hz,
    n_modulation_harmonics,
    n_pump_harmonics,
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
| `n_modulation_harmonics` | modulation harmonic tuple; shape must match output mode model |
| `n_pump_harmonics` | pump harmonic tuple; length must match pump-axis count |
| `dc` | enables explicit DC mode handling |
| `threewavemixing` | enables three-wave mixing terms |
| `fourwavemixing` | enables four-wave mixing terms |
| `returnS` | requests scattering-parameter output |
| `returnZ` | requests impedance output |
| `returnQE` | requests quantum-efficiency output |
| `returnCM` | requests commutation-relation output |
| `sorting` | controls target node ordering behavior |
| `keyedarrays` | controls keyed-array output shape |

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
```

Rules:

- product Runner path must reject unknown kwargs;
- Pluto research path may later support wider pass-through, but that requires a separate source-of-truth decision;
- optional kwargs must be recorded in provenance.

## Unsupported in Product Runner MVP

Unsupported controls must fail clearly in product Runner execution until Julia Core documents and implements them.

| Control | Example source | Reason not yet supported | Expected failure behavior | Future note |
| --- | --- | --- | --- | --- |
| `returnSnoise` | JosephsonCircuits reference | noise result schema is not mapped to TraceStore yet | reject in Runner payload | add a noise observable request and result schema |
| `returnnodeflux` / `returnvoltage` | JosephsonCircuits reference | node-resolved outputs need compiled node provenance and storage schema | reject in Runner payload | expose through diagnostic / research result schema |
| adjoint output flags | JosephsonCircuits reference | adjoint result families need separate observable contracts | reject in Runner payload | add explicit adjoint observable request types |
| sensitivity flags | JosephsonCircuits reference | sensitivity APIs are marked as in progress upstream and need stable provenance | reject in Runner payload | revisit after Core owns sensitivity contracts |
| custom `factorization` | JosephsonCircuits reference | runtime object injection is not a product task payload contract | reject in Runner payload | expose only through trusted local Julia configuration if needed |
| `maxintermodorder` | JosephsonCircuits reference | affects mode truncation and result interpretation; not part of MVP schema | reject in Runner payload | promote to first-class control when product workflows need it |

## Source Semantics

The canonical JosephsonCircuits source entry is:

```julia
(mode = (...), port = N, current = I)
```

Product schema equivalent:

```json
{
  "kind": "port_current",
  "mode": [1],
  "port": 1,
  "current_a": 0.0
}
```

Rules:

- `current_a = 0.0` is legal;
- `mode` is an integer array;
- `port` references a compiled external port;
- source role is declared in CircuitPlan source slots;
- runtime only binds current values.

## Legacy `amplitude` Handling

Legacy payloads such as:

```json
{
  "kind": "port_drive",
  "target": "port_1",
  "amplitude": -35.0
}
```

are ambiguous.

Rules:

- do not silently interpret `amplitude` as JosephsonCircuits current;
- either reject it in strict mode;
- or treat it as UI-level metadata while mapping `current_a = 0.0` with an explicit warning;
- future conversion from dBm, voltage, or current requires a separate calibrated source model.

## Related

- [HB Simulation Intent](hb-simulation-intent.md)
- [Runner-Safe API](runner-safe-api.md)
- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
