---
aliases:
  - Julia Core Endpoints
  - Circuit Endpoints
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/julia-core
status: stable
owner: docs-team
audience: contributor
scope: Endpoint abstraction for pins, line taps, spans, ground, external nodes, and loop targets in Circuit Plans.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Endpoints

Endpoint is the general attachment abstraction used by connections, couplings, shunts, and compiler transforms. Pin is one kind of endpoint; many other endpoint kinds are not pins.

Use `Endpoint`, not `Pin`, as the top-level concept.

## Hierarchy

```text
AbstractCircuitEndpoint
|
+-- AbstractNodeEndpoint
|   +-- PinEndpoint
|   +-- LineTapEndpoint
|   +-- GroundEndpoint
|   +-- ExternalNodeEndpoint
|
+-- AbstractLineSpanEndpoint
|   +-- LineSpanEndpoint
|
+-- AbstractLoopEndpoint
    +-- LoopEndpoint
```

`AbstractNodeEndpoint` is the node-resolving endpoint category. Node endpoints resolve to one circuit node and can participate in node aliasing or lumped capacitor placement. `AbstractLineSpanEndpoint` attaches across a distributed interval. `AbstractLoopEndpoint` targets an inductive or flux-related loop.

## User-Facing Examples

```julia
pin(lc, :signal)
pin(flc, :plus)
line_tap(qwr; at_m = 1.2mm)
line_tap(readout; line = :main, at_m = 2.0mm)
line_span(qwr; from_m = 2.0mm, to_m = 2.5mm)
line_span(readout; line = :main, from_m = 2.0mm, to_m = 2.5mm)
line_tap(line_ref(readout, :main); at_m = 2.0mm)
ground()
external_node("drive")
squid_loop(lc)
```

These values are all endpoints, but only `pin(lc, :signal)` and `pin(flc, :plus)` are pins.

The shorthand forms `line_tap(component; at_m = ...)` and `line_span(component; from_m, to_m)` are valid only when the component has one unambiguous default line. Multi-line components must use `line = :main` or pass an explicit `line_ref(component, :main)`.

## Endpoint Kinds

| Endpoint | Category | Meaning |
| --- | --- | --- |
| `PinEndpoint` | node | public named node-resolving endpoint exposed by a component |
| `LineTapEndpoint` | node | a resolved node location on a distributed component |
| `GroundEndpoint` | node | the canonical ground target |
| `ExternalNodeEndpoint` | node | a named external or drive node |
| `LineSpanEndpoint` | line span | a distributed interval on a line-like component |
| `LoopEndpoint` | loop | a SQUID loop or other inductive coupling target |

## Constraints

Use endpoint category constraints to keep the API explicit:

| Relation | Accepted endpoint categories |
| --- | --- |
| `connect!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `couple_capacitive!` | `NodeEndpoint` <-> `NodeEndpoint` |
| `shunt_capacitor!` | `NodeEndpoint` -> implicit `GroundEndpoint` |
| `couple_window!` | `LineSpanEndpoint` <-> `LineSpanEndpoint` |
| `couple_inductive!` | `LineTapEndpoint` or `LineSpanEndpoint` <-> `LoopEndpoint` or `InductiveTargetEndpoint` |

The compiler should reject incompatible endpoint categories before emitting target netlist rows.
