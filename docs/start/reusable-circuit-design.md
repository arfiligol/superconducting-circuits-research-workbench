---
aliases:
 - Reusable Circuit Design
 - Reusable Circuit Model
 - Reusable circuit design
tags:
 - diataxis/tutorial
 - audience/user
 - topic/circuit-authoring
status: stable
owner: docs-team
audience: user
scope: Concise first-pass introduction to the Circuit Workbench reusable-component and project-plan ownership model.
version: v1.1.0
last_updated: 2026-07-28
updated_by: codex
title: Reusable Circuit Design
sidebar:
 label: Reusable Circuit Design
 order: 40
---

# Reusable Circuit Design

Circuit Workbench turns circuit topology into a reusable research asset. The
same Julia builder should drive inspection, compilation, schematic export,
Pluto simulation, and research evidence.

```text
Reusable Component
  -> project Plan Builder
  -> CircuitPlan
  -> validation + compiled netlist
  -> schematic export + SVG
  -> Pluto research evidence
```

## Choose What You Are Building

| If the circuit code represents | Build |
| --- | --- |
| Stable local topology used inside a larger circuit | A Reusable Component that inserts its owned relations into a supplied `CircuitPlan` |
| A complete research topology with feedlines, ports, drives, and observables | A project or Component Library Plan Builder that returns a `CircuitPlan` |
| One concrete parameterized design point | A `CircuitPlan` produced by that builder |
| Early topology exploration with no stable reuse boundary | A Pluto-local probe |

A stable local topology that is used as a component inside a larger circuit is
eligible to enter the Julia Core reusable catalog. Eligibility does not force a
move: lab-, process-, and project-specific variants may stay in their
Component Library. Complete project circuits expressed through Plan Builders
do not enter the Julia Core reusable catalog.

## Know The Boundaries

| Layer | Responsibility |
| --- | --- |
| Reusable Component | Local electrical topology, public endpoints, parameters, validation, and inspectable component identity |
| Plan Builder | Complete system composition and project-owned feedlines, ports, drives, observables, and parameter choices |
| `CircuitPlan` | One concrete, inspectable authoring source for validation, compilation, simulation, and export |
| `EngineeringGraph` | Human- and Agent-facing record of what the circuit is |
| `SchematicLayoutIntent` | Renderer-neutral record of how the circuit should be arranged |
| Schemdraw | Visual projection of exported plan semantics into light/dark SVG |
| Pluto | Parameter binding, inspection, real solver execution, figures, diagnostics, and research evidence |

Drawing placement never creates electrical connectivity. The Julia plan and
its compiled netlist remain the topology source of truth.

## Use The Manual

Open the
[Circuit Workbench Manual](../workflows/reusable-circuit-authoring/index.md)
before creating files. It gives the current lifecycle, ownership decision,
file map, Julia validation path, schematic-export commands, SVG pipeline,
Pluto usage, and Human/Agent stop conditions.

The
[Intrinsic Interferometric Purcell Components](../reference/julia-core/intrinsic-interferometric-purcell-components.md)
are the current complete worked example: reusable component topology lives in
Julia Core, the diagram consumes a Julia export, and an enclosing project plan
remains responsible for feedline and simulation-system composition.

## Next References

- [Circuit Plan](../reference/julia-core/circuit-plan.md) — one complete
  runnable design point and its ownership.
- [Components And Composition](../reference/julia-core/components-and-composition.mdx)
  — component interfaces and enclosing-circuit composition.
- [Schematic Layout Intent](../reference/julia-core/schematic-layout-intent.md)
  — renderer-neutral drawing and export semantics.
- [Contributing Circuit Diagrams](../contribute/contributing/circuit-diagrams.mdx)
  — export-backed Schemdraw SVG assets.

## Semantic Status

- Scope: Start Here explanation of the Circuit Workbench ownership model.
- Current state: `STABILIZED` V1, aligned with the accepted Manual.
- Human acceptance: explicitly accepted the named V1 scope on 2026-07-28.
- Test policy: `stabilization_tests_authorized`; existing docs validation
  covers this documentation-only scope.
