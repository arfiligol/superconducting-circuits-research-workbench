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
scope: CircuitPlan semantics, owned authoring data, validation boundary, and solver handoff.
version: v2.0.0
last_updated: 2026-05-31
updated_by: codex
---

# Circuit Plan

A `CircuitPlan` is one complete runnable circuit design point. It stores the concrete system the user intends to validate, compile, simulate, inspect, and export.

Reusable component hierarchy is defined by `@circuit_component`. A plan instantiates components and relations into one system-level design. If a simulated system becomes useful as a reusable building block, refactor that design into a component template with explicit pins, taps, probes, and anchors.

## Ownership

A plan owns the concrete authoring state needed before solver lowering:

| Plan data | Purpose |
| --- | --- |
| instantiated components | concrete component instances used by this design point |
| endpoints | external nodes, ground, pins, line taps, line spans, loop targets, probes, and anchors referenced by this plan |
| primitive relations | capacitors, inductors, resistors, Josephson elements, connections, shunts, and couplings |
| physical generator outputs | emitted ladder sections, resonator sections, coupled-window sections, and generated primitive relations |
| ports | external simulation ports with index, endpoint, resistance, and semantic role |
| parameter metadata | parameter names, units, roles, owners, sweep-facing names, and topology-key relevance |
| EngineeringGraph records | human-facing components, groups, relations, roles, ports, HB overlays, and provenance |
| SchematicLayoutIntent | renderer-neutral drawing intent such as tracks, spans, terminals, and labels |
| SchematicExportSpec projection | renderer-neutral schematic export assembled from semantics and layout intent |
| compiler-ready representation | validated authoring state that can lower to JosephsonCircuits.jl rows |

The plan remains the source of authoring semantics until compilation. The compiled netlist is a projection for the solver.

## Runnable System Boundary

Each plan represents one runnable system:

```text
CircuitPlan
  -> validate_authoring
  -> validate_compile_ready
  -> compile_to_josephson
  -> build_hb_problem
  -> run_hb_problem
```

A notebook may build several plans for comparisons or sweeps. Each plan still owns one complete design point with concrete endpoints, concrete relations, concrete ports, and concrete HB intent.

Use `@circuit_component` for repeatable templates. Use `@circuit` or functional builder calls to instantiate a complete system.

## Interface Discipline

Component internals are private by default. The enclosing circuit may attach only to exposed interface points:

| Interface | Electrical? | Use |
| --- | --- | --- |
| `pin(instance, :name)` | yes | normal public connection point |
| `tap(instance, distance_from_head)` | yes | point on a distributed model |
| `probe(instance, :name)` | yes | intentional measurement, debug, or coupling point |
| `anchor(instance, :name)` | no | schematic, report, or layout reference point |

An anchor is not an electrical endpoint. If a renderer reference point must also be connectable, expose the physical point as a pin, tap, or probe and use an anchor only for drawing metadata.

## Terminations

Line-like generators use explicit termination contracts:

| Termination | Meaning |
| --- | --- |
| `:open` | terminal node exists, no ground connection is added, and no outside connection is required |
| `:short` / `:grounded` | terminal node is connected to ground |
| `:external` | terminal node is exposed as an enclosing-circuit interface |

Validation must report an `:external` terminal that has no enclosing connection. Use `:open` when the intended boundary condition is an open end.

## EngineeringGraph Records

A plan preserves enough authoring information to build an [`EngineeringGraph`](engineering-graph.md) without reading solver rows.

EngineeringGraph records include:

```text
- component identity and display names;
- reusable component type and engineering role;
- groups such as readout chain, pump network, coupling network, and measurement path;
- relation verbs such as connect, couple, drive, observe, feed, and terminate;
- through components such as couplers, feed structures, and distributed windows;
- ports, source slots, observable requests, and HB overlays;
- source-code or notebook provenance;
- schematic export hints.
```

Human-facing inspection uses the plan and graph. Solver-facing inspection uses compiled rows and compiled maps.

## Schematic Data

The plan may carry both engineering semantics and drawing intent:

```text
CircuitPlan
  -> EngineeringGraph
  -> SchematicLayoutIntent
  -> SchematicExportSpec
```

Engineering semantics answer what the circuit is. Schematic layout intent answers how the circuit should be drawn. The compiler must depend on electrical topology and circuit parameters, not on drawing placement.

`SchematicExportSpec` is renderer-neutral. A downstream renderer may draw it with Schemdraw, a browser canvas, SVG, or another backend without changing the plan.

## HBIntent Boundary

`HBIntent` is separate from topology and bound to a plan:

```text
@circuit
  -> topology, components, endpoints, relations, ports

@hbintent plan
  -> pump axes, source slots, observable requests, solver defaults
```

HB declarations reference plan objects by ID, such as port IDs and pump-axis IDs. Validation resolves those references against the owning plan before compilation and before `HBProblemSpec` construction.

Example:

```julia
begin
    plan = @circuit "one-port-lc" begin
        drive = external_node("drive")

        resonator = lc_resonator!(
            id = :res,
            signal = drive,
            capacitance = C,
            inductance = L,
        )

        port(:drive_port) do
            index = 1
            endpoint = pin(resonator, :signal)
            resistance = 50.0
            role = :reflection
        end
    end

    @hbintent plan begin
        pump_axis(:pump; frequency_parameter = :pump_frequency)

        source_slot(:pump_in) do
            role = :pump
            port = :drive_port
            mode = (1,)
            current_parameter = :pump_current
        end

        sparameter(:s11) do
            outputmode = (0,)
            outputport = :drive_port
            inputmode = (0,)
            inputport = :drive_port
        end
    end

    plan
end
```

Changing source current values is a runtime binding. Changing port declarations, pump axes, source-slot shape, or observable requests changes plan-bound simulation intent.

## Compilation Handoff

Compilation consumes a validated plan:

```text
CircuitPlan
  -> endpoint resolution
  -> relation lowering
  -> physical generator lowering
  -> HBIntent validation
  -> JosephsonCompiledCircuit
```

The compiled circuit may preserve links back to plan records and EngineeringGraph IDs. Those links support diagnostics, traceability, and notebook inspection, but the compiled rows do not replace the plan as the authoring contract.

For harmonic-balance execution, the product-aligned handoff is:

```text
CircuitPlan
  -> HBIntent
  -> compile_to_josephson
  -> build_hb_problem
  -> HBProblemSpec
  -> run_hb_problem
```

Runner code should bind runtime values to validated slots and execute `HBProblemSpec`. It must not invent circuit topology, port meanings, source slots, pump axes, or observable semantics after compilation.

## Plan-Level Transforms

Plan-level transforms are recorded as semantic intent before target lowering:

```julia
connect!(plan, pin(a, :right), pin(b, :left))

tap = line_tap(readout; line = :main, at_m = 2.0e-3)

shunt_capacitor!(
    plan;
    id = :readout_shunt_c,
    at = tap,
    capacitance = 20.0e-15,
)
```

During compilation, the compiler resolves endpoint aliases, inserts line-tap breakpoints, splits distributed lines, lowers lumped and distributed elements, and emits solver rows plus traceability maps.

## Line References

`line_tap(component; at_m = ...)` and `line_span(component; from_m, to_m)` are shorthand forms. They are valid only when the component exposes exactly one unambiguous default line.

For components with multiple internal lines, select the line explicitly:

```julia
line_tap(component; line = :main, at_m = 1.2e-3)
line_span(component; line = :main, from_m = 2.0e-3, to_m = 2.5e-3)
```

You can also resolve the line first:

```julia
main_line = line_ref(component, :main)

line_tap(main_line; at_m = 1.2e-3)
line_span(main_line; from_m = 2.0e-3, to_m = 2.5e-3)
```

The compiler must reject ambiguous line taps and spans before solver lowering.
