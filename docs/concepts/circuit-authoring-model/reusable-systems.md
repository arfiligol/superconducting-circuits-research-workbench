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
version: v1.0.0
last_updated: 2026-06-12
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
Component Library
  -> reusable plan builder
  -> CircuitPlan
  -> EngineeringGraph / schematic intent
  -> compiler
  -> simulation
```

## Mental Model

| Layer | Responsibility |
| --- | --- |
| Component library | named reusable component vocabulary selected by a project, lab, or study |
| Component | reusable local circuit unit with typed ports and parameters |
| Plan builder | function or small API that assembles a reusable circuit idea into a `CircuitPlan` |
| System | composition of components, couplings, endpoints, and simulation intent |
| CircuitPlan | authoring contract that preserves engineering semantics |
| Schematic intent | renderer-neutral diagram/export intent derived from the authored system |
| Compiler | lowers the plan into solver-facing structures |
| Research notebook | chooses parameters, plots evidence, and inspects intermediate results |

## Why This Matters

Pluto users need reusable authoring without copying circuit construction logic into every notebook. The shared Julia Core model keeps component composition, compiler lowering, schematic evidence, and solver intent aligned.

This is also how notebook prototypes become durable. A prototype cell can sketch a circuit once; a reusable builder should own the second version.

## Related

- [Circuit Authoring & Reuse](../../workflows/circuit-authoring/index.md)
- [Reusable Circuit Design](../../start/reusable-circuit-design.md)
- [Authoring Model](../../reference/julia-core/authoring-model.mdx)
- [Components and Composition](../../reference/julia-core/components-and-composition.mdx)
