---
aliases:
  - JosephsonCompiledCircuit
  - Compiled Circuit
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Compiler output contract for JosephsonCompiledCircuit, maps, warnings, provenance, and caller inspection.
version: v1.3.0
last_updated: 2026-05-29
updated_by: codex
---

# Compiled Circuit

The compiler output should be richer than raw netlist rows. Pluto needs inspection and debugging metadata; Runner execution needs deterministic simulation input and provenance.

The target concept is `JosephsonCompiledCircuit`.

Compiled output is the solver-facing representation. Human-facing engineering structure belongs to [`EngineeringGraph`](engineering-graph.md). The compiler should preserve trace links from solver rows back to plan and EngineeringGraph records, but it should not make the netlist the source of engineering semantics.

## Target Contract

```julia
struct JosephsonCompiledCircuit
    netlist
    component_values
    node_map
    component_map
    line_tap_map
    port_map
    hb_intent_summary
    source_slot_map
    observable_request_map
    hb_validation_summary
    warnings
    provenance
    metadata
end
```

The current MVP struct does not yet contain every target field. Implementation should move toward this target rather than adding long-term HB metadata through ad hoc dictionaries.

## Fields

| Field | Purpose |
| --- | --- |
| `netlist` | JosephsonCircuits.jl target rows |
| `component_values` | target component values and parameter bindings |
| `node_map` | mapping from plan endpoints and internal nodes to target node names |
| `component_map` | mapping from plan components and subcomponents to emitted target rows |
| `line_tap_map` | records line tap endpoints, inserted breakpoints, and target nodes |
| `port_map` | maps `ExternalPort` IDs to target port indices and node names |
| `hb_intent_summary` | records pump axes, source slots, observables, and solver-control shape |
| `source_slot_map` | maps source slot IDs to compiled ports and mode tuples |
| `observable_request_map` | maps observable IDs to output/input mode and port extraction paths |
| `hb_validation_summary` | records compile-time HB compatibility checks |
| `warnings` | compile warnings, physics sanity warnings, and recoverable lowering notes |
| `provenance` | builder, transform, source, and reproducibility metadata |
| `metadata` | target version, compiler settings, discretization settings, and auxiliary data |

## EngineeringGraph Links

`JosephsonCompiledCircuit` should preserve links to the EngineeringGraph where useful:

```text
- component_map entries should reference EngineeringComponent IDs;
- port_map entries should reference EngineeringPort IDs;
- source_slot_map entries should reference EngineeringHBIntentOverlay source slots;
- observable_request_map entries should reference EngineeringHBIntentOverlay observable requests;
- provenance should identify the CircuitPlan and EngineeringGraph source version.
```

These links let Pluto and Runner logs explain compiled rows in engineering language. They do not make the compiled netlist the canonical human-facing schematic.

## HB Simulation Metadata

HB metadata is part of the target compiled-circuit contract. Current MVP support is smaller: the compiler can emit JosephsonCircuits-compatible port rows for supported lumped plans, but the full `HBIntent` metadata contract is still a target contract for the next implementation step.

## Pluto Inspection

Pluto can inspect compiled output without guessing how the compiler lowered the plan:

```julia
compiled = compile_to_josephson(plan)

compiled.netlist
compiled.warnings
compiled.line_tap_map
```

This lets notebook cells show the target netlist, trace line taps back to user expressions, and display warnings near the design that caused them.

## Runner Execution

Runner execution can run deterministic simulations from compiled output:

```julia
compiled = compile_to_josephson(plan)

run_frequency_sweep(compiled, frequency_range_hz; kwargs...)
```

The Runner should stage numeric arrays through filesystem packages such as Zarr when results are large. HTTP JSON should carry control payloads, status, manifest locators, summaries, and small metadata, not large numeric arrays.

The current MVP compiler emits real JosephsonCircuits-compatible rows for supported lumped plans. Component rows use target value references and `component_values`; port rows use integer port indices. Unsupported compiler paths fail clearly before Runner writes output.

Runner execution must bind runtime values to compiled HB intent. It must not invent source slots, port roles, pump axes, or observable semantics from task payloads alone.

## Why Raw Rows Are Not Enough

Raw netlist rows cannot explain:

- which Plan-level component emitted a row;
- which endpoint produced a node name;
- where a line tap inserted a breakpoint;
- which warnings were recoverable;
- which compiler settings produced the discretization;
- how Pluto or Runner should trace simulation output back to authoring intent.

`JosephsonCompiledCircuit` keeps those inspection and reproducibility surfaces together.
