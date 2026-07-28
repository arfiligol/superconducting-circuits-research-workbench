---
aliases:
 - Reusable Systems
 - reusable system
tags:
 - diataxis/explanation
 - audience/team
 - topic/circuit-authoring
status: stable
owner: docs-team
audience: team
scope: reusable component, component library, reusable builder, CircuitPlan, schematic intent, and simulation mental model across Julia Core and Pluto.
version: v1.1.0
last_updated: 2026-07-28
updated_by: codex
title: Reusable Systems
sidebar:
 label: Reusable Systems
 order: 20
---

# Reusable Systems

Reusable systems let the project describe circuit structure once, inspect it in Pluto, and reuse the same Julia Core semantics across notebooks and package tests.

The reusable path is:

```text
Reusable Component
  -> project Plan Builder
  -> CircuitPlan
  -> EngineeringGraph / schematic intent
  -> compiler
  -> simulation
```

## Mental Model

| Layer | Responsibility |
| --- | --- |
| Julia Core reusable catalog | eligible stable local topologies already used as components inside larger circuit topologies |
| External Component Library | reusable component variants intentionally kept in user, lab, process, device-family, or project space |
| Reusable Component | local circuit topology with public endpoints, parameters, validation, and private internals |
| Project Plan Builder | function or small API that assembles the complete research circuit into a `CircuitPlan` |
| System | composition of components, couplings, endpoints, and simulation intent |
| CircuitPlan | authoring contract that preserves engineering semantics |
| Schematic intent | renderer-neutral diagram/export intent derived from the authored system |
| Compiler | lowers the plan into solver-facing structures |
| Research notebook | chooses parameters, plots evidence, and inspects intermediate results |

## Why This Matters

Pluto users need reusable authoring without copying circuit construction logic into every notebook. The shared Julia Core model keeps component composition, compiler lowering, schematic evidence, and solver intent aligned.

This is also how notebook prototypes become durable. A prototype cell can
sketch a circuit once; when a larger topology uses that stable local topology,
a Reusable Component should own it. The complete circuit remains in its
project Plan Builder.

## Related

- [Reusable Circuit Authoring](../../workflows/reusable-circuit-authoring/index.md)
- [Reusable Circuit Design](../../start/reusable-circuit-design.md)
- [Authoring Model](../../reference/julia-core/authoring-model.mdx)
- [Components and Composition](../../reference/julia-core/components-and-composition.mdx)
