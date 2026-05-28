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
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Compiled Circuit

The compiler output should be richer than raw netlist rows. Pluto needs inspection and debugging metadata; Worker execution needs deterministic simulation input and provenance.

The target concept is `JosephsonCompiledCircuit`.

## Conceptual Shape

```julia
struct JosephsonCompiledCircuit
    netlist
    component_values
    node_map
    component_map
    line_tap_map
    warnings
    provenance
    metadata
end
```

This is a documentation target, not a required implementation in this docs-only task.

## Fields

| Field | Purpose |
| --- | --- |
| `netlist` | JosephsonCircuits.jl target rows |
| `component_values` | target component values and parameter bindings |
| `node_map` | mapping from plan endpoints and internal nodes to target node names |
| `component_map` | mapping from plan components and subcomponents to emitted target rows |
| `line_tap_map` | records line tap endpoints, inserted breakpoints, and target nodes |
| `warnings` | compile warnings, physics sanity warnings, and recoverable lowering notes |
| `provenance` | builder, transform, source, and reproducibility metadata |
| `metadata` | target version, compiler settings, discretization settings, and auxiliary data |

## Pluto Inspection

Pluto can inspect compiled output without guessing how the compiler lowered the plan:

```julia
compiled = compile_to_josephson(plan)

compiled.netlist
compiled.warnings
compiled.line_tap_map
```

This lets notebook cells show the target netlist, trace line taps back to user expressions, and display warnings near the design that caused them.

## Worker Execution

Worker execution can run deterministic simulations from compiled output:

```julia
compiled = compile_to_josephson(plan)

run_frequency_sweep(compiled, frequency_range_hz; kwargs...)
```

The Worker should stage numeric arrays through filesystem packages such as Zarr when results are large. HTTP JSON should carry control payloads, status, manifest locators, summaries, and small metadata, not large numeric arrays.

## Why Raw Rows Are Not Enough

Raw netlist rows cannot explain:

- which Plan-level component emitted a row;
- which endpoint produced a node name;
- where a line tap inserted a breakpoint;
- which warnings were recoverable;
- which compiler settings produced the discretization;
- how Pluto or Worker should trace simulation output back to authoring intent.

`JosephsonCompiledCircuit` keeps those inspection and reproducibility surfaces together.
