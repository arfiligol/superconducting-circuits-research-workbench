---
aliases:
 - Circuit Authoring & Reuse
 - Circuit writing and reuse
tags:
 - diataxis/how-to
 - audience/user
 - topic/circuit-authoring
status: stable
owner: docs-team
audience: user
scope: Build simulatable systems using Julia Core reusable components, plan builders, and CircuitPlan.
version: v1.1.0
last_updated: 2026-06-14
updated_by: codex
title: Reusable Circuit Authoring
sidebar:
 label: Overview
 order: 10
---

# Reusable Circuit Authoring

This route answers "How do I turn a circuit idea into reusable research code?" It is the Start Here route in full detail: Pluto is the research surface, Julia Core owns reusable component and plan semantics, and JosephsonCircuits.jl provides the circuit-response solve path.

```text
Pluto Notebook
  -> reusable component or plan builder
  -> CircuitPlan
  -> JosephsonCircuits.jl response
  -> traces, sweeps, figures, and reusable package logic
```

## Page Map

| Page | Use it when |
| --- | --- |
| [Pluto Research](pluto-research.md) | You need the notebook-first research lane and its boundaries. |
| [Pluto Examples](pluto-examples.mdx) | You want to continue through the numbered Pluto examples. |
| [LC Resonator](lc-resonator.md) | You need the smallest reusable circuit example. |
| [Parameter Sweep](parameter-sweep.md) | You need to scan circuit parameters and compare responses. |
| [JosephsonCircuits Simulation](josephsoncircuits-simulation.md) | You need the solver-facing response path. |
| [Promote Pluto Prototype To Reusable Core](promote-pluto-prototype-to-reusable-core.md) | A notebook idea appears repeatedly and should become reusable Julia Core or component-library code. |
| [Research Tooling](research-tooling.md) | You need the package-promotion and notebook-support boundary. |

## Related

- [Circuit Authoring Model](../../concepts/circuit-authoring-model/index.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
- [Component Libraries](../../reference/julia-core/component-libraries.md)
- [Julia Core Reference](../../reference/julia-core/index.mdx)
