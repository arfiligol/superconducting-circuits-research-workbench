---
aliases:
  - Circuit Plan
  - CircuitPlan
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Circuit Plan semantics and stored authoring data before JosephsonCircuits.jl compilation.
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Circuit Plan

A `CircuitPlan` is the semantic source of truth before simulation. It stores what the user means to build, not the final JosephsonCircuits.jl representation.

`CircuitDraft` is the current implementation of this Circuit Plan concept.

## Stored Data

| Plan data | Purpose |
| --- | --- |
| components | reusable primitive or composite components added to the design |
| composite component hierarchy | subcomponent trees that remain inspectable until compilation |
| public pins | user-facing named points exposed by components |
| private internal nodes | component-owned implementation nodes that need compiler namespacing |
| endpoints | pins, line taps, spans, ground, external nodes, and loop targets |
| line taps | point attachments on distributed components |
| line spans | distributed interval attachments and transforms |
| node connections | endpoint aliasing and node merge intent |
| capacitive couplings | plan-level capacitor placements between point endpoints |
| inductive couplings | mutual or flux-related coupling intent |
| distributed coupled windows | span-to-span distributed coupling intent |
| shunt placements | convenience placements from a point endpoint to ground |
| parameters / sweep knobs | user-facing values that may vary across simulation sweeps |
| provenance | source, builder, and transform metadata needed for inspection and reproducibility |

## Not A Netlist

A Circuit Plan is not yet a JosephsonCircuits.jl netlist. It may contain hierarchy, aliases, symbolic endpoints, line transformations, validation state, and unresolved target-specific decisions.

The compiler is responsible for turning the complete plan into target-specific rows and maps.

!!! tip "Practical rule"
    Keep user intent in the plan as long as possible. Lower to JosephsonCircuits.jl only after validation has seen the whole circuit.

## Why It Helps Pluto

Pluto can inspect the plan before compilation:

- show component hierarchy;
- expose public pins and endpoints;
- drive sliders through parameters and sweep knobs;
- inspect line taps and spans before line splitting;
- display validation warnings close to the authoring cell.

This keeps Pluto interactive without giving Pluto a separate construction path.

## Why It Helps Worker Execution

The Julia Worker can receive deterministic task input, rebuild the same plan, validate it, compile it, simulate it, and stage output with provenance.

Worker execution should call the same plan builders and compiler used by Pluto. The caller changes; the Core pipeline does not.

## Plan-Level Transforms

Plan-level transforms are recorded as semantic intent:

```julia
connect!(plan, pin(a, :right), pin(b, :left))

tap = line_tap(readout; at_m = 2.0mm)

shunt_capacitor!(
    plan;
    id = "readout_shunt_c",
    at = tap,
    capacitance = 20.0fF,
)
```

During compilation, the compiler resolves endpoint aliases, inserts line-tap breakpoints, splits distributed lines, lowers lumped and distributed elements, and emits the target netlist plus maps.
