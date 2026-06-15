---
aliases:
 - GDSFactory-Compatible Result Workflow
 - GDSFactory ecosystem result route
tags:
 - diataxis/how-to
 - audience/user
 - topic/analysis
status: stable
owner: docs-team
audience: user
scope: Workflow for consuming GDSFactory ecosystem-style simulation results without running GDSFactory, gsim, gplugins, or qpdk inside this repo.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: GDSFactory-Compatible Result Workflow
description: Mirror the gsim-style S to Z/Y to RLC/RLGC flow without importing upstream layout/FEM runtimes.
sidebar:
 label: GDSFactory-Compatible Result Workflow
 order: 80
---

# GDSFactory-Compatible Result Workflow

This workflow keeps the workbench compatible with GDSFactory ecosystem outputs while preserving repo ownership. Upstream layout and FEM execution stay outside this repo. The workbench consumes exported result artifacts.

## Compatibility Target

Compatibility means the result artifact can be understood by this repo:

| Required information | Why it matters |
| --- | --- |
| frequency axis and units | establishes the independent variable |
| port names and order | maps trace matrix entries to circuit meaning |
| complex S/Y/Z traces | supports RF conversion and fitting |
| reference impedance or normalization metadata | makes S-parameter conversion reviewable |
| source provenance | records upstream tool, geometry, solver, mesh, and simulation settings when available |

## Expected Analysis Shape

The gsim-style analysis pattern is:

```text
S-parameter result
  -> RF network representation
  -> Z or Y conversion
  -> differential impedance or admittance extraction
  -> equivalent RLC/RLGC fit
  -> reusable circuit or quantum-model handoff
```

The workbench may mirror this analysis shape with Python Analysis Core and Python notebooks. It should not import `gdsfactory`, `gsim`, `gplugins`, or `qpdk` just to run the upstream job.

## What Belongs Elsewhere

| Work | Owner |
| --- | --- |
| layout cell authoring | GDSFactory ecosystem or private layout repo |
| meshing and solver handoff | upstream FEM workflow |
| Palace execution | upstream solver workflow |
| equivalent-circuit fitting and downstream circuit research | this workbench |

## Related

- [External FEM Result To Equivalent Circuit](external-fem-result-to-equivalent-circuit.md)
- [External FEM Result Contract](../../reference/research-contracts/external-fem-result-contract.md)
- [GDSFactory-Compatible Artifacts](../../concepts/gdsfactory-compatible-artifacts/index.md)
- [Circuit Research Routes](../../concepts/gdsfactory-compatible-artifacts/circuit-research-routes.md)
