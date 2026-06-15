---
aliases:
 - Pipeline Concepts
 - pipeline concept
tags:
 - diataxis/explanation
 - audience/team
 - topic/architecture
 - topic/pipeline
status: stable
owner: docs-team
audience: team
scope: Information and execution process instructions for Research Direct, Product Async and Data/Platform Notebook tracks
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
sidebar:
 label: Overview
 order: 10
---

# Pipeline

Pipeline explains how research execution, product simulation, and notebook data inspection move through the platform. The current architecture uses three tracks instead of one shared command workflow.

## Track Map

| Track | Used by | Authority |
| --- | --- | --- |
| Research Direct Track | Pluto Notebook | Julia Core direct execution and local research outputs |
| Product Async Track | Application Simulation Workbench, Python Notebook task submission | Python Backend task lifecycle, Julia Runner compute, Backend publication |
| Data / Platform Notebook Track | Python Notebook | direct data-file reads for analysis; Backend APIs for platform state |

The tracks share scientific concepts and data formats, but they do not share ownership. Pluto owns direct research execution. The Application owns product workflow. Python Notebook may inspect files directly, but platform mutations go through Backend contracts.

## Why This Matters

- Application-triggered simulation stays asynchronous and publishable.
- Python Notebook remains useful for analysis without becoming a second platform writer.
- Pluto can prototype physics directly without becoming a Backend task client.
- Runner output becomes official only after Backend validation and TraceStore publication.

## Topics

- [Data Flow](data-flow.md) - end-to-end tracks and authority handoffs
- [Preprocessing Rationale](preprocessing-rationale.md) - why ingestion, normalization, and publication are separate responsibilities

## Related

- [Simulation Interface Boundaries](../contracts/simulation-interface-boundaries.md)
- [Product Async Contracts](../contracts/product-async-contracts.md)
- [TraceStore Zarr](../contracts/trace-store-zarr.md)
