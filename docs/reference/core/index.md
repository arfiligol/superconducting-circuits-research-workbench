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
scope: Core reference index, listing Julia Core, Julia Visualizer, Julia Runner, Julia Analysis Bridge, Python analysis, and the Python Schemdraw visual library.
version: v0.10.0
last_updated: 2026-05-30
updated_by: codex
---

# Core Reference

Core docs describe reusable contracts and compute libraries.
Session state, HTTP transport, UI state, and packaged application lifecycle live outside this section.

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
| Julia Runner owns async task execution | claim tasks, dispatch compute, write staging artifacts, write manifest, report complete/fail |
| Julia Analysis Bridge owns Pluto-friendly Python analysis calls | wrap Python analysis through PythonCall without moving algorithms into Julia |
| Python analysis owns fitting and matrix algorithms | keep transport routes and UI DTOs out of analysis code |
| Product publication stays outside Core | validate manifests, publish canonical data, create metadata and provenance records |
| Packaged application surfaces stay outside Core | HTTP schemas, session authority, UI state, and packaged lifecycle are separate concerns |

## Page Map

| Page | Focus | Primary code surface |
|---|---|---|
| [Python Core](python-core.mdx) | Python analysis package and Schemdraw visual library boundaries | `core/python/analysis/`, `core/python/circuit_libraries/` |
| [Julia Compute Boundary](julia-wrapper.md) | Julia Core, Runner, and Analysis Bridge responsibility split | `core/julia/SuperconductingCircuitsCore/`, `core/julia/SuperconductingCircuitsRunner/`, `core/julia/SuperconductingCircuitsAnalysisBridge/` |
| [Julia Core Authoring](../julia-core/index.mdx) | Circuit Plan source of truth, reusable components, endpoints, compiler output, Pluto and Runner shared API | `core/julia/SuperconductingCircuitsCore/`, `notebooks/pluto/` |
| [Julia Visualizer](../julia-visualizer/index.mdx) | PlotlyJS figure construction for real `HBSolveResult` traces | `core/julia/SuperconductingCircuitsVisualizer/`, `notebooks/pluto/` |
| [Julia Package Surface](julia-core.mdx) | Julia-native package boundary | `core/julia/` |

## Related

- [Julia Visualizer](../julia-visualizer/index.mdx)
- [Notebook Interface](../notebooks/index.md)
