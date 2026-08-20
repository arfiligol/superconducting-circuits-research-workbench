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
scope: Contract-level Pluto and Python notebook responsibilities across circuit runtime, analysis, and quantum routes.
version: v1.1.0
last_updated: 2026-08-20
updated_by: codex
title: Notebook Roles
description: Defines Pluto and Python notebook responsibilities for circuit execution, external-result analysis, quantum modeling, and pulse simulation.
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

Python notebooks are the routine client for the accepted public circuit runtime
and also own Python-native research exploration:

- visible generic `CircuitPlan` assembly and consumer-owned circuit libraries
- declarative artifact bindings, reduction, cared outputs, objective, exact
  Human-authorized Gates, variables, and optimizer controls
- explicit `CircuitSim.evaluate()`, `optimize()`, and pure-Python `analyze()`

- trace table, Touchstone, and Zarr ingestion sketches
- scikit-rf-compatible inspection and conversion
- fitting experiments before promotion to Python Analysis Core
- scqubits, QuTiP, and qutip-qip studies
- report evidence assembly

Python notebooks may read local/exported/canonical data files directly for ad
hoc analysis. Persistent application state mutations stay out of research
notebooks and use the application service contracts.

## Process Boundary

The public runtime starts one Julia process for each complete `evaluate` action
and one for the complete `optimize` search. Candidate and frequency-point work
does not call back into Python. `analyze` verifies sealed evidence in pure Python
and never starts Julia.

Python notebooks must not import `juliacall`, invoke Julia Core directly, build
C/K/G, or call Schur helpers. Application execution remains a separate
persisted service/Julia Runner path. See
[Circuit Runtime / Python Consumer](circuit-runtime-python-consumer.md) for the
accepted package, schema, ownership, and failure contract.

## Related

- [Notebook Interface](../notebooks/index.md)
- [FEM Result To Equivalent Circuit](../../workflows/fem-result-to-equivalent-circuit/index.md)
- [Equivalent Circuit To Quantum Model](../../workflows/equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../../workflows/quantum-dynamics-pulse-simulation/index.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
- [Circuit Runtime / Python Consumer](circuit-runtime-python-consumer.md)
