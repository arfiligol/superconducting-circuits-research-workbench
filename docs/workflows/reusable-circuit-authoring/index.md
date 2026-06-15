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

This route answers "How do I turn a circuit idea into reusable research code?" It is the Start Here route in full detail: Pluto is the direct research cockpit, Julia Core owns reusable component and plan semantics, and JosephsonCircuits.jl provides the circuit-response solve path.

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
| [Authoring Workflow](pluto-authoring-workflow.mdx) | You need to build, inspect, validate, compile, and run one reusable `CircuitPlan` from Pluto. |
| [Parameter Sweep Workflow](pluto-parameter-sweep-workflow.mdx) | You need explicit batch sweeps after a single-point Pluto path is validated. |
| [Pluto Examples](pluto-examples.mdx) | You want to continue through the numbered Pluto examples. |
| [JosephsonCircuits Response Path](josephsoncircuits-simulation.md) | You need the solver-facing response path or direct Julia debugging material. |
| [Promote Pluto Prototype To Reusable Core](promote-pluto-prototype-to-reusable-core.md) | A notebook idea appears repeatedly and should become reusable Julia Core or component-library code. |
| [Extend Julia Functions](extend-julia-functions.mdx) | You need to add a Julia Core helper or reusable simulation utility. |

## Owner Map

| Surface | Owns |
| --- | --- |
| Pluto Notebook | direct research execution, inspection cells, figures, sweep selection, and notebook-local teaching fixtures |
| Julia Core | reusable components, plan builders, validation, compilation intent, solver-facing problem construction, and reusable research helpers |
| Component libraries | lab-specific or device-family builders that assemble reusable Julia Core plans |
| SuperconductingCircuitsVisualizer | PlotlyJS figures and notebook presentation helpers |
| Python Analysis Core / Analysis Bridge | reusable analysis routines and selected Python-backed analysis calls, only when the notebook explicitly needs them |

Keep direct notebook research fast and explicit. Promote only repeated, tested, reusable behavior into package code.

## Related

- [Circuit Authoring Model](../../concepts/circuit-authoring-model/index.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
- [Component Libraries](../../reference/julia-core/component-libraries.md)
- [Julia Core Reference](../../reference/julia-core/index.mdx)
