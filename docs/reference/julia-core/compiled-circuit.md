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
version: v1.4.0
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

The compiled circuit record is the structured handoff between authoring and execution. HB metadata belongs in typed fields rather than ad hoc dictionaries.

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

HB metadata is part of the compiled-circuit contract. The compiler should preserve enough intent metadata for `build_hb_problem` to create an executable `HBProblemSpec` without asking Runner payloads to redefine HB semantics.

The compiled HB handoff includes:

- declared pump axes and their stable IDs;
- source slots, roles, mode tuples, compiled port indices, and current-parameter names;
- DC source-slot validation, including `role = :dc_bias`, `mode = (0,)`, and `dc = true`;
- observable requests and their output/input mode-port extraction paths;
- default solver controls and output-family requests;
- netlist rows and component values needed by `run_hb_problem`.

Pump-off does not remove compiled HB metadata. The compiled circuit still carries the pump axis and pump source slot; runtime binds the pump source current to `0.0`.

The compiled circuit records output request intent, not solver-output availability. `validate_output_request_configuration(compiled, hb_problem)` validates the request configuration before solve. Actual S/Z/QE/QEideal/CM availability is checked after `hbsolve` returns.

When a family is requested, Julia Core extracts the full requested family. Upper layers handle filtering, persistence, and display. Missing requested families fail clearly; missing unrequested families are allowed. Solver-returned `NaN` values are preserved, and Core does not create NaN-placeholder values for missing families.

## HBProblemSpec Handoff

`HBProblemSpec` is the executable object produced from a compiled circuit plus runtime bindings. It should carry, or reference immutably, the compiled circuit identity, netlist rows, component values, normalized `ws`, `wp`, `sources`, harmonic tuples, solver controls, observables, and whitelisted kwargs.

Runner execution should pass this problem spec to `run_hb_problem`. It should not rebuild source slots, infer observables, or re-map ports from raw task payload fields.

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

The compiler emits real JosephsonCircuits-compatible rows for lowerable plans. Component rows use target value references and `component_values`; port rows use integer port indices. Invalid compiler paths fail clearly before Runner writes output.

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
