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
scope: Accepted external FEM/simulation result input forms and normalized trace expectations.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: External FEM Result Contract
description: Defines the accepted external result inputs for circuit-first analysis.
sidebar:
 label: External FEM Result Contract
 order: 20
---

# External FEM Result Contract

External FEM and simulation results enter the workbench as artifacts, not as live layout or solver jobs. This contract allows upstream GDSFactory/gsim/gplugins/qpdk-style work to feed circuit research without making this repo own layout, mesh, or Palace execution.

## Accepted Input Families

| Family | Required interpretation |
| --- | --- |
| trace table | table with frequency axis and complex trace columns or real/imaginary columns |
| Touchstone | RF network result that can be interpreted as an S-parameter package with port ordering and reference impedance |
| Zarr package | already-normalized result package with arrays, metadata, and provenance |

All three input families should normalize to the same reviewable trace package before fitting.

## Required Normalized Semantics

| Field | Requirement |
| --- | --- |
| frequency | one-dimensional frequency axis with explicit unit, preferably Hz after normalization |
| traces | complex S/Y/Z arrays or named complex trace vectors |
| ports | stable port names, port order, and direction when known |
| reference impedance | required when converting S-parameters |
| units | explicit units for frequency and derived parameters |
| provenance | upstream source, export command or notebook, solver/material/mesh metadata when available |

## Ownership

Python Analysis Core owns reusable normalization and fitting helpers. Python notebooks own one-off import inspection and evidence notebooks. Pluto may consume a normalized result package, but Pluto should not become the primary importer for scikit-rf-style external RF files.

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
