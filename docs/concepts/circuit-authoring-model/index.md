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
version: v1.1.0
last_updated: 2026-07-28
updated_by: codex
title: Circuit Authoring Model
sidebar:
 label: Overview
 order: 10
---

# Circuit Authoring Model

This area answers "How does a reusable circuit system work?" It provides a conceptual model; the formal contract remains in the Julia Core Reference.

The core concept is: researchers may explore in Pluto, but a stable local
topology used inside a larger topology becomes a Reusable Component, while the
complete research circuit remains a project Plan Builder that produces a
`CircuitPlan`. The component is eligible for Julia Core; eligibility does not
force an external Component Library to move it. A notebook is an inspection
surface, not a long-term reusable-system owner.

## Page Map

| Page | Use it when |
| --- | --- |
| [Reusable Systems](reusable-systems.md) | To understand the division of labor between component, system, CircuitPlan and compiler |
| [Component Libraries](../../reference/julia-core/component-libraries.md) |To check the owner contract of component library|
| [Circuit Plan](../../reference/julia-core/circuit-plan.md) | To check the endpoints, relations, parameters, and simulation intent in the plan |
| [Schematic Layout Intent](../../reference/julia-core/schematic-layout-intent.md) | To check how to separate schematic/export intent from plan |

## Related

- [Reusable Circuit Design](../../start/reusable-circuit-design.md)
- [Reusable Circuit Authoring](../../workflows/reusable-circuit-authoring/index.md)
- [Julia Core Reference](../../reference/julia-core/index.mdx)
