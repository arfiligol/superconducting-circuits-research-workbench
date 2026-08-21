---
aliases:
 - Notebook Roles
 - Pluto and Python notebook roles
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: converging
owner: docs-team
audience: team
scope: Contract-level Pluto and Python notebook responsibilities, including the converging staged Circuit Runtime boundary.
version: v1.2.0
last_updated: 2026-08-21
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

Python notebooks are the routine client for the public circuit runtime
and also own Python-native research exploration:

- visible generic `CircuitPlan` assembly and consumer-owned circuit libraries
- declarative artifact bindings, reduction, cared outputs, objective, exact
  Human-authorized Gates, variables, and optimizer controls
- explicit `CircuitSim` stages: `optimize`, `refine_winner`,
  `evaluate_responses`, `fit_c11`, `evaluate_t1`, and `build_report`
- a visible `execute` or `resolve` value beside each stage call
- pure-Python, read-only result, campaign, and report resolution

- trace table, Touchstone, and Zarr ingestion sketches
- scikit-rf-compatible inspection and conversion
- fitting experiments before promotion to Python Analysis Core
- scqubits, QuTiP, and qutip-qip studies
- consumer-specific report interpretation

Python notebooks may read local/exported/canonical data files directly for ad
hoc analysis. Persistent application state mutations stay out of research
notebooks and use the application service contracts.

## Process Boundary

`execute` performs one complete named stage. A Julia-backed stage starts exactly
one Julia process for that action; candidate and frequency-point work never
calls back into Python. Python-owned fit/report stages start none. `resolve` and
the result/campaign/report readers are pure Python and read-only: they start no
Julia process, recompute nothing, mutate nothing, and fail closed over absent,
stale, incomplete, or identity-mismatched evidence.

The notebook owns visible plan assembly and consumer declarations, not stage
orchestration internals, identities, receipt writing, scientific calculations,
or generic report construction. Each independent case should use an explicit
run directory; campaign readers consume only the directories the notebook
lists and never select a latest run.

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
