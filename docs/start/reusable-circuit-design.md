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
scope: Concise first-pass introduction to reusable circuit design in the research-first docs path.
version: v1.0.0
last_updated: 2026-06-13
updated_by: codex
title: Reusable Circuit Design
sidebar:
 label: Reusable Circuit Design
 order: 40
---

# Reusable Circuit Design

The core value of this repo is to make circuit design a reusable research asset. Pluto notebook can be quickly explored, but the recurring circuit structure, parameter semantics, schematic intent and simulation intent should be converged into a reusable model on Julia Core.

## Main Model

```text
Component Library
  -> reusable plan builder
  -> CircuitPlan
  -> EngineeringGraph / SchematicLayoutIntent / SchematicExportSpec
  -> compiler
  -> simulation
```

## What Each Layer Owns

| Layer | Owns |
| --- | --- |
| Component Library | Named components, parameter conventions, reusable builders, and lab/project-specific design vocabulary |
| Plan builder | Turn a reusable circuit idea into a checkable, testable, and simulated `CircuitPlan` |
| `CircuitPlan` | ports, endpoints, relations, component instances, simulation intent and engineering semantics |
| Engineering graph | inspection-friendly connectivity model |
| Schematic intent | renderer-neutral diagram/export intent, allowing the same plan to generate schematic evidence |
| Compiler | Lowers the high-level plan into solver-facing structures |
| Pluto notebook | Select parameters, check intermediate objects, execute simulation, and generate research evidence |

## First Principle

You can write the prototype first in the Notebook cell, but don't let the notebook become a component library. When a piece of circuit construction is reused, promote it to a named component / plan builder so that Pluto, package tests, API docs, and future downstream surfaces all use the same semantics.

## What To Learn Next

- [Promote Pluto Prototype To Reusable Core](../workflows/research-tools/promote-pluto-prototype-to-reusable-core.md) - Convergence notebook idea into reusable Julia Core / component library work.
- [Circuit Authoring Model](../concepts/circuit-authoring-model/index.md) - Understand the conceptual division of labor between reusable components, systems, plan builders and compilers.
- [Component Libraries](../reference/julia-core/component-libraries.md) - See reusable component library of reference contract.
