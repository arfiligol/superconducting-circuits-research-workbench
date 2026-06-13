---
aliases:
 - Julia Core Relations
 - Relations and Couplings
tags:
 - diataxis/reference
 - audience/contributor
 - sot/true
 - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Plan-level relations, endpoint constraints, capacitive couplings, inductive couplings, shunts, and distributed windows.
version: v1.6.0
last_updated: 2026-05-30
updated_by: codex
---

# Relations and Couplings

Relations are Plan-level intents. They are recorded in the Circuit Plan and lowered by the compiler after endpoint resolution, namespacing, line splitting, and validation.

They are not immediate JosephsonCircuits.jl rows.

## Relation Types

| Relation | Meaning |
| --- | --- |
| `connect!` | endpoint aliasing or node connection intent |
| `couple_capacitive!` | capacitor placement between node-resolving endpoints |
| `shunt_capacitor!` | convenience capacitor placement from a node-resolving endpoint to implicit ground |
| `shunt_inductor!` | convenience inductor placement from a node-resolving endpoint to implicit ground |
| `series_inductor!` | inductor placement between two node-resolving endpoints |
| `series_resistor!` | resistor placement between two node-resolving endpoints |
| `josephson_junction!` | Josephson inductive branch placement between two node-resolving endpoints |
| `couple_window!` | distributed span-to-span coupling intent |
| `couple_transmission_window!` | `TransmissionLineLadder` coupled-window helper |
| `couple_inductive!` | inductive, mutual, or flux-related coupling intent |

## EngineeringGraph Capture

Physical relation operations record matching [`EngineeringGraph`](engineering-graph.md) relations while they update the Circuit Plan. Standard `connect!`, `couple_capacitive!`, `shunt_capacitor!`, `shunt_inductor!`, `series_inductor!`, `series_resistor!`, `josephson_junction!`, `couple_inductive!`, `couple_window!`, and `couple_transmission_window!` calls keep the solver-facing relation and human-facing semantic graph synchronized.

Users should not normally call `record_engineering_relation!` after those standard operations. Use manual relation recording only for extra semantic annotations, non-physical overlays, or metadata that is not already represented by the physical operation.

## Endpoint Constraints

| Relation | Constraint |
| --- | --- |
| `connect!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `couple_capacitive!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `shunt_capacitor!` | `NodeEndpoint` -> implicit `GroundEndpoint` |
| `shunt_inductor!` | `NodeEndpoint` -> implicit `GroundEndpoint` |
| `series_inductor!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `series_resistor!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `josephson_junction!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `couple_window!` | `LineSpanEndpoint` <-> `LineSpanEndpoint` |
| `couple_transmission_window!` | `TransmissionLineLadder` <-> `TransmissionLineLadder`; generated-boundary section windows |
| `couple_inductive!` | branch inductor references for lowerable mutual inductance, or line/loop endpoints for semantic flux intent |

The compiler should fail early when a relation receives the wrong endpoint category.

`shunt_capacitor!(plan; id, at, capacitance)` is equivalent to a capacitive coupling from `at` to `ground()`:

```julia
couple_capacitive!(
  plan;
  id = id,
  from = at,
  to = ground(),
  capacitance = capacitance,
)
```

`shunt_inductor!(plan; id, at, inductance)` is the corresponding inductive termination from `at` to `ground()`.

`series_inductor!(plan; id, from, to, inductance)` and `series_resistor!(plan; id, from, to, resistance)` are the minimal two-node lumped primitives for ladder examples. They lower to `L_...` and `R_...` JosephsonCircuits rows between the resolved nodes. They do not create ports or source semantics.

`josephson_junction!(plan; id, from, to, josephson_inductance)` is the nonlinear inductive primitive for JosephsonCircuits lowering. It resolves the two endpoint nodes like a branch relation and lowers to an `Lj...` row whose value is the Josephson inductance binding.

`InductiveTargetEndpoint` is the relation-side category for non-loop inductive targets. It is not a node-resolving endpoint.

## Line Selection

`line_tap(component; at_m = ...)` and `line_span(component; from_m, to_m)` are shorthand forms. They are valid only when the component exposes exactly one unambiguous default line.

Multi-line components must select a line explicitly:

```julia
line_tap(component; line =:main, at_m = 1.2mm)
line_span(component; line =:main, from_m = 2.0mm, to_m = 2.5mm)
```

Or use a resolved line reference:

```julia
line_tap(line_ref(component,:main); at_m = 1.2mm)
line_span(line_ref(component,:main); from_m = 2.0mm, to_m = 2.5mm)
```

The compiler must reject an ambiguous line tap or ambiguous line span before target lowering.

## Relation Parameter Roles

Relations and couplings may introduce their own parameters. These parameters should also declare default roles.

Examples:

| Relation parameter | Default role |
| --- | --- |
| capacitive coupling value | `NumericParameter` if endpoints are unchanged |
| mutual inductance value | `NumericParameter` if coupling topology is unchanged |
| line tap position | `StructuralParameter` |
| line span start / stop | `StructuralParameter` |
| coupled-window length | `StructuralParameter` |

The declared role is a sweep input. The compiler and sweep engine still verify whether each relation parameter changes the topology key before compiled output is reused.

## Relation-Owned Parameter Metadata

Relations should expose parameter metadata for the parameters they introduce.

Examples:

| Relation | Parameter | Default role |
| --- | --- | --- |
| `couple_capacitive!` | capacitance | `NumericParameter` if endpoints are unchanged |
| `couple_inductive!` | mutual inductance | `NumericParameter` if coupling topology is unchanged |
| `josephson_junction!` | Josephson inductance | `NumericParameter` if endpoints are unchanged |
| `line_tap(...)` | tap position | `StructuralParameter` |
| `line_span(...)` | start / stop | `StructuralParameter` |
| `couple_window!` | window length | `StructuralParameter` |
| `couple_transmission_window!` | start distances and window length | `StructuralParameter` |

Relation-owned metadata should be stored in the CircuitPlan so `preflight_sweep` can classify sweep axes before execution.

## LC To Quarter-Wave Resonator

```julia
couple_capacitive!(
  plan;
  id = "lc_to_qwr",
  from = pin(lc,:signal),
  to = line_tap(qwr; line =:main, at_m = 1.2mm),
  capacitance = 3.0fF,
)
```

The tap is a node endpoint on a distributed component. The compiler decides how to insert the breakpoint and split the line.

## SQUID Coupled To CPW Flux Line

```julia
couple_inductive!(
  plan;
  id = "flux_to_squid",
  from = line_tap(flux_line; line =:main, at_m = 2.0mm),
  to = squid_loop(lc),
  mutual_inductance = 3.0pH,
)
```

The SQUID loop is a loop endpoint. The relation is flux or mutual-coupling intent, not a user-authored internal node splice.

## Floating LC In Series

```julia
connect!(plan, pin(left_line,:right), pin(flc,:plus))
connect!(plan, pin(flc,:minus), pin(right_line,:left))
```

The plan records endpoint aliasing. During compilation, the compiler resolves node names and private component namespaces.

## Two QWRs With Fixed-Length Distributed Coupling

```julia
window = couple_transmission_window!(
  plan;
  id = "qwr_a_qwr_b_window",
  line1 = qwr_a_ladder,
  line2 = qwr_b_ladder,
  start1 = 2.0e-3,
  start2 = 2.0e-3,
  length = 0.5e-3,
  model = MTLCoupledRLGCSpec(...),
)
```

This expresses a fixed-length coupled region between two generated ladder models. The coupled window uses coupled-section self terms in the generated ladder sections, then adds generated C12 and K primitive relations and records an EngineeringGraph `:coupled_window` relation.

`couple_window!(line_span(...), line_span(...))` carries span-to-span intent for component-level distributed lines. Executable examples should use the Core API path that provides real compiler lowering for the declared model.

## QWR To Readout Line With Shunt

```julia
tap = line_tap(readout; line =:main, at_m = 2.0mm)

couple_capacitive!(
  plan;
  id = "qwr_to_readout",
  from = pin(qwr,:feed),
  to = tap,
  capacitance = 6.0fF,
)

shunt_capacitor!(
  plan;
  id = "readout_shunt_c",
  at = tap,
  capacitance = 20.0fF,
)
```

Both relations target the same node endpoint. The compiler must preserve that shared tap location when it inserts breakpoints and emits netlist rows.
