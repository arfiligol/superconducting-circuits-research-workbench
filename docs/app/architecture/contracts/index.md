---
aliases:
 - Architecture Reference
 - Architecture reference
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/architecture
status: stable
owner: docs-team
audience: team
scope: Notebook Interface, Application Interface, Python Backend, Julia Runner and TraceStore of owner boundary
version: v1.2.0
last_updated: 2026-05-28
updated_by: codex
---

# Architecture Reference

This area defines the formal architecture of the current platform SoT.

Current architecture:

```text
Notebook Interface + Electron Application Interface + Julia Runner Compute Plane
```

Python Backend is control/data plane.Julia Runner is compute plane.Electron App is productized data workbench.Pluto Notebook is research cockpit.

## Page Map

| Page | Core focus |
|---|---|
| [Simulation Interface Boundaries](simulation-interface-boundaries.md) | Pluto direct research, Python Notebook data inspection, and Application Simulation/Analysis Workbench boundary |
| [Product Async Contracts](product-async-contracts.md) |SimulationRequest, AnalysisRequest, RunnerTaskEnvelope, Runner manifest, ResultView API boundary|
| [Julia Runner Compute Plane](julia-runner-compute-plane.md) |Runner process boundary, claim/execute/complete protocol|
| [Runner Result Manifest](runner-result-manifest.md) |manifest schema, safe path rules, Zarr declaration|
| [TraceStore Zarr](trace-store-zarr.md) | canonical local Zarr authority owned by Python Backend |
| [Canonical Contract Registry](canonical-contract-registry.mdx) | cross-layer contracts and owners |

## Current Boundaries

| Boundary | Owner |
|---|---|
| task lifecycle, metadata, publication, provenance | Python Backend |
| simulation, sweeps, post-processing, fitting, derived extraction | Julia Runner |
| canonical numeric authority | Python Backend-managed TraceStore |
| local staging package | Julia Runner writes, Backend validates |
| app navigation and result browsing | Electron + Next.js App |
| productized simulation request workflow | Application Simulation Workbench |
| productized analysis/fitting workflow | Application Analysis Workbench |
| direct exploratory execution | Pluto Notebook |

## Removed Product Surfaces

User-facing command workflows, retired Python UI runtimes, separate local queue workers, Python-in-process Julia simulation, and Schemdraw standalone workflow are not active product/runtime surfaces.

Application Simulation Workbench and Analysis Workbench are active architecture. They submit persisted tasks through the Backend and never own heavy compute.

If a historical document mentions one of those surfaces, the current architecture pages override it.

## Related

* [Application Interface](../../app/application-interface.md)
* [Frontend Reference](../../app/frontend/index.md)
* [Simulation Interface Boundaries](simulation-interface-boundaries.md)
* [Product Async Contracts](product-async-contracts.md)
* [Backend Reference](../../app/backend/index.md)
* [Notebook Reference](../notebooks/index.md)
* [Core Reference](../core/index.md)
