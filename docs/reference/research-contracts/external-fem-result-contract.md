---
aliases:
 - External FEM Result Contract
 - FEM result contract
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/research-contracts
status: stable
owner: docs-team
audience: team
scope: Accepted external FEM/simulation result input forms, normalized trace expectations, and per-unit-length matrix handoff evidence.
version: v1.1.0
last_updated: 2026-07-10
updated_by: codex
title: External FEM Result Contract
description: Defines the accepted external result inputs for circuit-first analysis.
sidebar:
 label: External FEM Result Contract
 order: 20
---

# External FEM Result Contract

External FEM and simulation results enter the workbench as artifacts, not as live layout or solver jobs. This contract allows upstream GDSFactory/gsim/gplugins/qpdk-style work to feed circuit research without making this repo own layout, mesh, or Palace execution.

Reusable matrix physics is canonical in
[SCQ_Design: Multiconductor RLGC Matrices](https://github.com/arfiligol/SCQ_Design/blob/main/docs/knowledge/transmission-lines/multiconductor-rlgc-matrix-semantics.qmd).
This page owns only the Workbench input contract.

## Accepted Input Families

| Family | Required interpretation |
| --- | --- |
| trace table | table with frequency axis and complex trace columns or real/imaginary columns |
| Touchstone | RF network result that can be interpreted as an S-parameter package with port ordering and reference impedance |
| Zarr package | already-normalized result package with arrays, metadata, and provenance |
| per-unit-length matrix artifact | labeled Q2D/FEM terminal-domain matrices with basis, representation, units, frequency, quantity availability, and provenance |

The first three families normalize to a reviewable trace package before fitting.
A per-unit-length matrix artifact is a direct equivalent-circuit input and must
not be forced through an invented S/Y/Z trace.

## Required Normalized Semantics

| Field | Requirement |
| --- | --- |
| frequency | one-dimensional frequency axis with explicit unit, preferably Hz after normalization |
| traces | complex S/Y/Z arrays or named complex trace vectors |
| ports | stable port names, port order, and direction when known |
| reference impedance | required when converting S-parameters |
| units | explicit units for frequency and derived parameters |
| provenance | upstream source, export command or notebook, solver/material/mesh metadata when available |

## Per-Unit-Length Matrix Artifact

A matrix envelope must carry enough evidence to interpret every entry without
producer-specific tribal knowledge.

| Field | Requirement |
| --- | --- |
| identity | schema/version, artifact id, case or parameter point, and source file identity |
| terminal basis | ordered non-reference conductors plus the explicit reference conductor or reference group |
| directions | propagation axis, positive terminal-current direction, and terminal-voltage definition |
| representation | Maxwell/nodal, terminal-domain series, physical branch, Spice, or dimensionless coupling coefficient; never infer from sign alone |
| quantities | values and availability state for each of R/L/G/C: `extracted`, `assumed_zero`, or `unavailable` |
| units | source units and unambiguous SI per-meter normalization |
| frequency | extraction frequency or a declared frequency axis |
| common provenance | geometry, materials, solver, setup, solution, reduction, and distributed-length basis shared by the matrices |
| integrity | ordered row/column labels, square shape, complete finite values, and source hashes or equivalent traceability |
| validation | declared reciprocity/passivity assumptions and the corresponding symmetry, positivity, and representation checks |

Dimensionless solver coupling-coefficient matrices are not RLGC values. A
Maxwell matrix and a Spice/physical-branch matrix are different
representations and require an explicit conversion record.

### Current consumer eligibility

The executable `MTLCoupledRLGCSpec` path currently accepts only a reduced,
reciprocal $2\times2$ lossless $L/C$ model with Maxwell capacitance semantics.
It does not consume $R/G$ matrices or a general $N$-conductor model. An
upstream artifact may contain more information, but the consumer must reject
or explicitly select a supported view; it must not silently discard loss.

## Ownership

Python Analysis Core owns reusable trace normalization and fitting helpers.
Julia Core owns the supported distributed-line matrix model and lowering.
Python notebooks own one-off import inspection and evidence notebooks. Pluto
may consume a validated normalized package, but it should not become the
primary importer for scikit-rf-style external RF files or an unvalidated Q2D
envelope.

## Exclusions

This repo does not own:

- GDSFactory layout construction
- gsim/gplugins/qpdk execution
- mesh generation
- Palace handoff or solver execution
- private layout repo technology files

## Related

- [External FEM Result To Equivalent Circuit](../../workflows/fem-result-to-equivalent-circuit/external-fem-result-to-equivalent-circuit.md)
- [GDSFactory-Compatible Result Workflow](../../workflows/fem-result-to-equivalent-circuit/gdsfactory-compatible-result-workflow.md)
