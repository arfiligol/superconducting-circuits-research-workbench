---
aliases:
  - Julia Core Compiler
  - Circuit Plan Compiler
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Compiler pipeline from Circuit Plan to JosephsonCompiledCircuit and JosephsonCircuits.jl target rows.
version: v1.4.0
last_updated: 2026-05-30
updated_by: codex
---

# Compiler

The compiler owns lowering from a complete Circuit Plan into a target-specific compiled circuit. For the JosephsonCircuits.jl target, the conceptual API is:

```julia
compiled = compile_to_josephson(plan)
```

The compiler is target-specific. Other targets may use the same Circuit Plan concepts but different lowering rules and compiled outputs.

The compiler consumes a `CircuitPlan` that may also contain EngineeringGraph records. It should preserve trace links from compiled rows back to plan and EngineeringGraph IDs, but it must not treat the JosephsonCircuits netlist as the source of human-facing engineering semantics.

## Pipeline

```text
Plan
 |
 v
preserve EngineeringGraph trace links
 |
 v
expand composite components
 |
 v
resolve endpoints
 |
 v
reject ambiguous line taps / spans
 |
 v
insert taps / split lines
 |
 v
lower lumped and distributed components
 |
 v
lower couplings
 |
 v
emit JosephsonCircuits netlist + report
```

## Stages

| Stage | Responsibility |
| --- | --- |
| 1. expand composite components | flatten Plan-level hierarchy only inside the global compile pass |
| 2. namespace private nodes | keep internal component nodes from colliding |
| 3. resolve pins, endpoint aliases, and line references | convert public endpoint references into compiler-owned node identities and line identities |
| 4. reject ambiguous line taps and spans | fail before target lowering when `line_tap` or `line_span` cannot resolve to one default line |
| 5. insert line-tap breakpoints | make node taps on distributed components explicit |
| 6. split distributed lines into chunks | discretize line components as required by target lowering |
| 7. lower lumped elements | emit capacitors, linear inductors, and other lumped elements |
| 8. lower nonlinear inductive elements | emit junctions, SQUIDs, nonlinear parameters, and related values |
| 9. lower capacitive / inductive couplings | place coupling elements after endpoint resolution |
| 10. lower distributed coupled windows | emit span-to-span distributed coupling representations |
| 11. emit JosephsonCircuits.jl netlist | produce target-specific simulator input |
| 12. generate compile report / maps / provenance | return enough metadata for inspection, debugging, and reproducibility |

## Global Compilation

Composite components must be flattened by the global compiler. That is the only point where private nodes, subcomponent hierarchy, endpoint aliases, line taps, spans, coupled windows, and target-specific row generation are all visible at once.

!!! warning "No partial netlist reuse"
    A component compiler that emits a reusable netlist fragment too early loses plan-level structure. That makes endpoint constraints, distributed transforms, compile reports, and provenance harder to verify.

## Target Maps

The compiler should return maps alongside the netlist so callers can inspect what happened:

| Map | Use |
| --- | --- |
| `node_map` | connect plan endpoints and internal nodes to target node names |
| `component_map` | trace emitted target rows back to Plan-level components |
| `line_tap_map` | explain inserted breakpoints and tap locations |
| warnings | show validation or lowering issues that did not abort compilation |
| provenance | preserve builder and transform history |

## Compiler Responsibilities for HB Simulation

For harmonic-balance simulation, compilation is not only `CircuitPlan -> JosephsonCircuits netlist`.

The compiler should validate:

- netlist lowerability;
- external port declarations and port-index uniqueness;
- endpoint resolution for every external port;
- `HBIntent` compatibility with the compiled port map;
- source slots, pump axes, mode tuples, and observable requests;
- the maps needed to build an HB problem without Runner inventing source semantics.

The compiled output should contain enough metadata to build an `HBProblemSpec` from runtime values. Unsupported HB intent paths must fail clearly during compile or HB problem construction, not during result extraction after a partial run.

See [HB Simulation Intent](hb-simulation-intent.md) for the source-of-truth simulation-intent contract.

## JosephsonCircuits Lowering Contract

The JosephsonCircuits compiler lowers authored circuit intent into solver rows after endpoint resolution, validation, and topology-key construction.

The lowering contract includes:

- registered component IDs and component pins;
- `GroundEndpoint` and `ExternalNodeEndpoint`;
- `NodeConnection` endpoint aliasing;
- `CapacitiveCoupling` and `ShuntCapacitor` lowering to target capacitor rows;
- `SeriesInductor`, `ShuntInductor`, `SeriesResistor`, and `JosephsonJunction` lowering to target rows;
- branch mutual inductive coupling between generated inductor rows;
- uniform LC/RLGC ladder rows generated by `build_lc_ladder_line!`;
- generated-boundary MTL coupled-window relations generated by `couple_transmission_window!`, lowered as C12 capacitor rows and K mutual-inductance rows;
- explicit external port rows when the plan declares `metadata[:external_ports]`;
- `node_map`, `component_map`, `line_tap_map`, relation provenance, and topology metadata.

Invalid or unresolved relation paths fail clearly before solver execution instead of emitting placeholder rows.
