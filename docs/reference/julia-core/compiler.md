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
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Compiler

The compiler owns lowering from a complete Circuit Plan into a target-specific compiled circuit. For the JosephsonCircuits.jl target, the conceptual API is:

```julia
compiled = compile_to_josephson(plan)
```

The compiler is target-specific. Other targets may use the same Circuit Plan concepts but different lowering rules and compiled outputs.

## Pipeline

```text
Plan
 |
 v
expand composite components
 |
 v
resolve endpoints
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
| 3. resolve pins and endpoint aliases | convert public endpoint references into compiler-owned node identities |
| 4. insert line-tap breakpoints | make point taps on distributed components explicit |
| 5. split distributed lines into chunks | discretize line components as required by target lowering |
| 6. lower lumped elements | emit capacitors, linear inductors, and other lumped elements |
| 7. lower nonlinear inductive elements | emit junctions, SQUIDs, nonlinear parameters, and related values |
| 8. lower capacitive / inductive couplings | place coupling elements after endpoint resolution |
| 9. lower distributed coupled windows | emit span-to-span distributed coupling representations |
| 10. emit JosephsonCircuits.jl netlist | produce target-specific simulator input |
| 11. generate compile report / maps / provenance | return enough metadata for inspection, debugging, and reproducibility |

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
