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
version: v1.4.1
last_updated: 2026-05-29
updated_by: codex
---

# Circuit Plan

A `CircuitPlan` is the semantic source of truth before simulation. It stores what the user means to build, not the final JosephsonCircuits.jl representation.

`CircuitDraft` is a transitional implementation detail. The architecture contract is `CircuitPlan`, and implementation work should rename, remove, or replace old names when they conflict with this reference.

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
| capacitive couplings | plan-level capacitor placements between node-resolving endpoints |
| inductive couplings | mutual or flux-related coupling intent |
| distributed coupled windows | span-to-span distributed coupling intent |
| shunt placements | convenience placements from a node-resolving endpoint to ground |
| parameter metadata / sweep knobs | declared parameter roles, effective-role validation inputs, parameter owners, parameter bindings, high-level Plan Builder mappings, valid domains, units, and sweep-facing names |
| engineering graph records | component display names, engineering roles, relation semantics, ports, groups, HB overlays, source provenance, and schematic export hints |
| provenance | source, builder, and transform metadata needed for inspection and reproducibility |

A Circuit Plan should preserve parameter metadata from components, relations, and plan builders so the sweep engine can classify axes, build topology keys, and validate compile reuse.

## Parameter Metadata

A CircuitPlan should preserve parameter metadata from:

```text
- Component Libraries;
- Relations / Couplings;
- Plan Builders;
- SweepSpec role assumptions.
```

This metadata allows the sweep engine to:

```text
- classify axes;
- compute topology keys;
- group points by compile equivalence;
- decide whether compiled circuits can be reused;
- produce SweepExecutionPlan preflight reports;
- preserve provenance in SweepResult.
```

## EngineeringGraph Records

A `CircuitPlan` should preserve enough authoring information to build an [`EngineeringGraph`](engineering-graph.md) without reading the compiled solver netlist.

EngineeringGraph records include:

```text
- component identity and display names;
- reusable component type and engineering role;
- named pins, ports, source slots, and observable requests;
- relation verbs such as connect, couple, drive, observe, feeds, and terminates;
- through components such as couplers or feed structures;
- groups such as readout chain, pump network, and coupling network;
- source-code or notebook provenance;
- schematic export hints.
```

The compiler may preserve links from compiled rows back to these records, but the engineering graph remains a plan-level semantic representation.

## Not A Netlist

A Circuit Plan is not yet a JosephsonCircuits.jl netlist. It may contain hierarchy, aliases, symbolic endpoints, line transformations, validation state, and unresolved target-specific decisions.

The compiler is responsible for turning the complete plan into target-specific rows and maps.

!!! tip "Practical rule"
    Keep user intent in the plan as long as possible. Lower to JosephsonCircuits.jl only after validation has seen the whole circuit.

The EngineeringGraph follows the same rule. Human visualization should use EngineeringGraph, not a reverse-engineered view of target rows.

## Why It Helps Pluto

Pluto can inspect the plan before compilation:

- show component hierarchy;
- expose public pins and endpoints;
- drive sliders through parameters and sweep knobs;
- inspect line taps and spans before line splitting;
- display validation warnings close to the authoring cell.

This keeps Pluto interactive without giving Pluto a separate construction path.

Pluto tutorial notebooks may define a minimal local component to make an acceptance harness readable. That local component is allowed only as a tutorial or test fixture; it must not become evidence that Julia Core ships lab-specific component catalogs.

## Why It Helps Runner Execution

The Julia Runner can receive deterministic task input, rebuild the same plan, validate it, compile it, simulate it, and stage output with provenance.

Runner execution should call the same plan builders and compiler used by Pluto. The caller changes; the Core pipeline does not.

For HB execution, the product-aligned handoff is:

```text
CircuitPlan
  -> HBIntent
  -> compile_to_josephson
  -> build_hb_problem
  -> HBProblemSpec
  -> run_hb_problem
```

Low-level `run_hbsolve` may remain as a JosephsonCircuits-facing adapter, but it must not replace `HBProblemSpec` and `run_hb_problem` as the documented Core/Runner path.

## Plan-Level Transforms

Plan-level transforms are recorded as semantic intent:

```julia
connect!(plan, pin(a, :right), pin(b, :left))

tap = line_tap(readout; line = :main, at_m = 2.0mm)

shunt_capacitor!(
    plan;
    id = "readout_shunt_c",
    at = tap,
    capacitance = 20.0fF,
)
```

During compilation, the compiler resolves endpoint aliases, inserts line-tap breakpoints, splits distributed lines, lowers lumped and distributed elements, and emits the target netlist plus maps.

## Line References

`line_tap(component; at_m = ...)` and `line_span(component; from_m, to_m)` are shorthand forms. They are valid only when the component exposes exactly one unambiguous default line.

For components with multiple internal lines, select the line explicitly:

```julia
line_tap(component; line = :main, at_m = 1.2mm)
line_span(component; line = :main, from_m = 2.0mm, to_m = 2.5mm)
```

You can also resolve the line first:

```julia
main_line = line_ref(component, :main)

line_tap(main_line; at_m = 1.2mm)
line_span(main_line; from_m = 2.0mm, to_m = 2.5mm)
```

The compiler must reject an ambiguous line tap or span before target lowering.
