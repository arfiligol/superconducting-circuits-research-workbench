---
aliases:
 - Notebook Roles
 - Pluto and Python notebook roles
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: stable
owner: docs-team
audience: team
scope: Contract-level notebook responsibilities for the four circuit research routes.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: Notebook Roles
description: Defines Pluto and Python notebook responsibilities for reusable circuit authoring, external-result analysis, quantum modeling, and pulse simulation.
sidebar:
 label: Notebook Roles
 order: 50
---

# Notebook Roles

Notebooks are research surfaces, not package ownership surfaces. Each notebook type has a route-specific job.

## Pluto Notebook

Pluto owns the direct Julia research cockpit:

- reusable circuit authoring experiments
- Julia Core component and plan-builder studies
- JosephsonCircuits.jl response studies
- sweep design and inspection
- result figure exploration through Julia Visualizer
- explicit bridge calls into Python Analysis Core when the analysis belongs beside a Julia study

Pluto may consume normalized external result packages, but it should not become the primary external RF file importer.

## Python Notebook

Python notebooks own Python-native research exploration:

- trace table, Touchstone, and Zarr ingestion sketches
- scikit-rf-compatible inspection and conversion
- fitting experiments before promotion to Python Analysis Core
- scqubits, QuTiP, and qutip-qip studies
- report evidence assembly

Python notebooks may read local/exported/canonical data files directly for ad hoc analysis. Persistent product-state mutations stay out of research notebooks and belong to the product documentation lane.

## Forbidden Shortcut

Python notebooks must not use JuliaCall or Julia Core as the normal simulation compute path. Scientific circuit-response compute belongs to Pluto direct execution or Julia Runner async execution. Python notebooks can consume exported or normalized results and can own Python-native quantum modeling or pulse/dynamics experiments.

## Related

- [Notebook Interface](../notebooks/index.md)
- [FEM Result To Equivalent Circuit](../../workflows/fem-result-to-equivalent-circuit/index.md)
- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
