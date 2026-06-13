---
aliases:
 - Circuit Authoring Model
 - circuit writing model
tags:
 - diataxis/explanation
 - audience/team
 - topic/circuit-authoring
status: stable
owner: docs-team
audience: team
scope: reusable circuit components, component libraries, plan builders, CircuitPlan, schematic intent, compiler, and simulation mental model.
version: v1.0.0
last_updated: 2026-06-12
updated_by: codex
title: Circuit Authoring Model
sidebar:
 label: Overview
 order: 10
---

# Circuit Authoring Model

This area answers "How does a reusable circuit system work?" It provides a conceptual model; the formal contract remains in the Julia Core Reference.

The core concept is: researchers first quickly explore in Pluto, but stable and reusable circuit construction should become component library and reusable plan builder. Notebook is an inspection surface, not a long-term reusable system owner.

## Page Map

| Page | Use it when |
| --- | --- |
| [Reusable Systems](reusable-systems.md) | To understand the division of labor between component, system, CircuitPlan and compiler |
| [Component Libraries](../../reference/julia-core/component-libraries.md) |To check the owner contract of component library|
| [Circuit Plan](../../reference/julia-core/circuit-plan.md) | To check the endpoints, relations, parameters, and simulation intent in the plan |
| [Schematic Layout Intent](../../reference/julia-core/schematic-layout-intent.md) | To check how to separate schematic/export intent from plan |

## Related

- [Reusable Circuit Design](../../start/reusable-circuit-design.md)
- [Circuit Authoring & Reuse](../../workflows/circuit-authoring/index.md)
- [Julia Core Reference](../../reference/julia-core/index.mdx)
