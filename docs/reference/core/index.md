---
aliases:
  - Core Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Core reference 索引，條列 Julia Core、Julia Visualizer、Julia Runner、Julia Analysis Bridge、Python analysis 與 Python Schemdraw visual library。
version: v0.10.0
last_updated: 2026-05-30
updated_by: codex
---

# Core Reference

Core docs describe reusable contracts and compute libraries.
Application session state, HTTP transport, UI state, and desktop lifecycle live outside this section.

## Read Order

1. [Julia Core Authoring](../julia-core/index.mdx) for Circuit Plan, endpoints, reusable components, compiler, and Runner-safe authoring architecture.
2. [Julia Compute Boundary](julia-wrapper.md) for the Core/Runner split.
3. [Julia Visualizer](../julia-visualizer/index.mdx) for Pluto-facing PlotlyJS figure contracts built from Julia Core results.
4. [Python Core](python-core.mdx) for Python-owned analysis and Schemdraw visual library boundaries.
5. [Julia Package Surface](julia-core.mdx) for the concrete Julia package surfaces.

## Ownership Rules

| Rule | Meaning |
|---|---|
| Julia Core owns reusable compute logic | keep HTTP, task polling, and database publication out of Core |
| Julia Runner owns async task execution | claim tasks, dispatch compute, write staging Zarr, write manifest, report complete/fail |
| Julia Analysis Bridge owns Pluto-friendly Python analysis calls | wrap Python analysis through PythonCall without moving algorithms into Julia |
| Python analysis owns fitting and matrix algorithms | keep FastAPI routes and frontend DTOs out of analysis code |
| Python Backend owns publication | validate manifests, publish TraceStore data, create metadata and provenance records |
| App surfaces stay outside Core | HTTP schemas, session authority, frontend state, and desktop supervision are app concerns |

## Page Map

| Page | Focus | Primary code surface |
|---|---|---|
| [Python Core](python-core.mdx) | Python analysis package and Schemdraw visual library boundaries | `core/python/analysis/`, `core/python/circuit_libraries/` |
| [Julia Compute Boundary](julia-wrapper.md) | Julia Core, Runner, and Analysis Bridge responsibility split | `core/julia/SuperconductingCircuitsCore/`, `core/julia/SuperconductingCircuitsRunner/`, `core/julia/SuperconductingCircuitsAnalysisBridge/` |
| [Julia Core Authoring](../julia-core/index.mdx) | Circuit Plan source of truth, reusable components, endpoints, compiler output, Pluto and Runner shared API | `core/julia/SuperconductingCircuitsCore/`, `notebooks/pluto/` |
| [Julia Visualizer](../julia-visualizer/index.mdx) | PlotlyJS figure construction for real `HBSolveResult` traces | `core/julia/SuperconductingCircuitsVisualizer/`, `notebooks/pluto/` |
| [Julia Package Surface](julia-core.mdx) | Julia-native package boundary | `core/julia/` |

## Related

- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
- [Julia Visualizer](../julia-visualizer/index.mdx)
- [Runner Result Manifest](../architecture/runner-result-manifest.md)
- [TraceStore Zarr](../architecture/trace-store-zarr.md)
