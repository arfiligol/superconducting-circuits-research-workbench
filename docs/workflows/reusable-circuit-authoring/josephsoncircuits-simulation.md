---
aliases:
 - "Simulation Guide"
 - "Simulation Guide"
tags:
 - diataxis/how-to
 - status/stable
 - topic/simulation
status: stable
owner: docs-team
audience: user
scope: "Notebook-first simulation workflow index"
version: v0.2.0
last_updated: 2026-06-12
updated_by: codex
sidebar:
 label: Overview
 order: 10
---

# Julia Core Simulation

The research simulation path of this project uses Pluto Notebook as the starting point, and then advances the stable semantics to Julia Core. Researchers should first use Pluto to directly call Julia Core / JosephsonCircuits.jl to confirm the physics settings, sweep range, and visualization results.

## Teaching method selection

Use the following entrance:

| Method | Suitable for Object | Contract |
|------|----------|----------|
| **Pluto Notebook** | Research, quick experiments, direct calls to Julia Core | The notebook kernel is an explicit research execution environment |
| **Julia Core package code** |Reusable components, helpers, simulation intent| package code owns reusable semantics |
| **Native Julia script / REPL** | Small checking or debugging | explicit local execution |

## Teaching list

| Teaching | Instructions |
|------|------|
| [Pluto Research](../pluto/index.md) | Research execution and parameter scanning entrance of Pluto Notebook |
| [Notebook Interface](../../reference/notebooks/index.md) | Boundaries of use between Pluto and Python notebook |
| [Native Julia simulation](native-julia.md) | Use Julia Core / JosephsonCircuits.jl directly for research simulation |

## Related resources

- [Tutorial: LC Resonator](../circuit-authoring/lc-resonator.md) - Complete Getting Started Case
- [Core Reference](../../reference/core/index.md) - Responsibility boundaries for Julia Core, Python Core, Runner and Analysis Bridge
- [Extending Research Tools](../research-tools/index.md) - Contributor Guide
