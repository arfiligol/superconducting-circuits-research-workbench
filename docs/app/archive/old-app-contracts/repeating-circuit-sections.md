---
aliases:
 - Repeating Circuit Sections
 - Repeated Circuit Segment
tags:
 - diataxis/tutorial
 - audience/user
 - topic/netlist
status: stable
owner: docs-team
audience: user
scope: Use repeat to create maintainable repeating structures in Source Forms
version: v0.1.0
last_updated: 2026-03-05
updated_by: codex
sidebar:
 label: Repeating Circuit Sections
 order: 60
---

# Repeating Circuit Sections

Legacy notice: this page is archived App-specific Schema Editor / CircuitDefinition reference. For current research authoring, use Julia Core component libraries, reusable plan builders, and `CircuitPlan`.

This page explains how to use `repeat` within a Source Form to create reusable topology and component sections.

## Suggestion process

1. First write an explicit section that can be run.
2. Extract repeating patterns to `repeat`:`count`, `start`, `emit`.
3. Use the notebook display or test helper to verify the expansion results and indexes.
4. Keep the source-level pattern; the expansion results are only used as input for inspection and simulation.

## Related

- [Circuit Netlist Format](circuit-netlist.mdx)
- [Circuit Authoring Model](../../../concepts/circuit-authoring-model/index.md)
