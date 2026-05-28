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
version: v1.0.0
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
+-- AbstractPointEndpoint
|   +-- PinEndpoint
|   +-- LineTapEndpoint
|   +-- GroundEndpoint
|   +-- ExternalNodeEndpoint
|
+-- AbstractSpanEndpoint
|   +-- LineSpanEndpoint
|
+-- AbstractLoopEndpoint
    +-- LoopEndpoint
```

Point endpoints attach at one node or one resolved point. Span endpoints attach across a distributed interval. Loop endpoints target an inductive or flux-related loop.

## User-Facing Examples

```julia
pin(lc, :signal)
pin(flc, :plus)
line_tap(qwr; at_m = 1.2mm)
line_span(qwr; from_m = 2.0mm, to_m = 2.5mm)
ground()
external_node("drive")
squid_loop(lc)
```

These values are all endpoints, but only `pin(lc, :signal)` and `pin(flc, :plus)` are pins.

## Endpoint Kinds

| Endpoint | Category | Meaning |
| --- | --- | --- |
| `PinEndpoint` | point | public named point exposed by a component |
| `LineTapEndpoint` | point | a point location on a distributed component |
| `GroundEndpoint` | point | the canonical ground target |
| `ExternalNodeEndpoint` | point | a named external or drive node |
| `LineSpanEndpoint` | span | a distributed interval on a line-like component |
| `LoopEndpoint` | loop | a SQUID loop or other inductive coupling target |

## Constraints

Use endpoint category constraints to keep the API explicit:

| Relation | Accepted endpoint categories |
| --- | --- |
| `connect!` | Point to Point |
| `couple_capacitive!` | Point to Point |
| `shunt_capacitor!` | Point to Ground |
| `couple_window!` | Span to Span |
| `couple_inductive!` | Point or Span to Loop or another inductive target |

The compiler should reject incompatible endpoint categories before emitting target netlist rows.
