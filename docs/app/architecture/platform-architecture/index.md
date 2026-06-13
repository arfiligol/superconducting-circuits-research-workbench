---
aliases:
- Platform Architecture Concepts
- Architecture concepts
tags:
- diataxis/explanation
- audience/team
- topic/architecture
status: draft
owner: docs-team
audience: team
scope: Architecture description index, covering Clean Architecture, Data Storage, Desktop, Observability, Pipeline, Circuit Simulation
version: v0.4.0
last_updated: 2026-03-25
updated_by: codex
sidebar:
 label: Overview
 order: 10
---

# Architecture

The architectural perspective of this block organization system focuses on "why it is designed this way" and "how it works".

## Sections

- [Clean Architecture](clean-architecture.md)
Hierarchical boundaries, dependency directions, combined locations.
- [Data Storage](data-storage.md)
Layering of responsibilities for `DesignRecord / TraceRecord / TraceBatchRecord / TraceStore`.
- [Desktop Runtime Supervisor](desktop-runtime-supervisor.md)
Why desktop shell should use Electron + runtime profile supervisor, instead of letting the main process take on the solver work.
- [Observability Taxonomy](observability-taxonomy.mdx)
Why audit logging, workflow observability and product telemetry must be layered.
- [Pipeline](../pipeline/index.md)
Data and execution processes for Research Direct, Product Async and Data / Platform Notebook tracks.
- [Circuit Simulation](circuit-simulation/index.mdx)
Schema editing, Live Preview, domain semantics and interaction strategies.
- [Visualization Backend](../design-decisions/visualization-backend.md)
Positioning and trade-offs of Plotly / Matplotlib.

## Related

- [Concepts](../index.mdx)
- [Data Formats](../../data-contracts/index.mdx)
