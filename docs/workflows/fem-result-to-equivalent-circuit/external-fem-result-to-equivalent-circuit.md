---
aliases:
 - External FEM Result To Equivalent Circuit
 - FEM result fitting
tags:
 - diataxis/how-to
 - audience/user
 - topic/analysis
status: stable
owner: docs-team
audience: user
scope: Workflow for turning upstream FEM or simulation result artifacts into normalized traces and equivalent circuit fits.
version: v1.0.0
last_updated: 2026-06-14
updated_by: codex
title: External FEM Result To Equivalent Circuit
description: Normalize trace tables, Touchstone files, or Zarr packages and fit equivalent circuit parameters.
sidebar:
 label: External FEM Result To Equivalent Circuit
 order: 60
---

# External FEM Result To Equivalent Circuit

Use this workflow when the source data was generated outside this repo. The upstream source can be GDSFactory/gsim/gplugins/qpdk, HFSS, Q3D, Palace, a lab export, or another simulator. This repo does not run the layout or FEM job in this route; it consumes the result artifact.

## Inputs

All three input forms should be treated as valid route entrances:

| Input | Use it when |
| --- | --- |
| trace table | the data already has frequency and complex trace columns |
| Touchstone | the result is an RF network export such as `.s1p`, `.s2p`, or `.sNp` |
| Zarr package | the result was already normalized into the workbench package shape |

The workflow should preserve source metadata, units, port labels, frequency axis, trace family, and provenance. A fitted equivalent circuit without source trace references is not reviewable enough for this docs lane.

## Flow

```text
source artifact
  -> normalize frequency axis and complex traces
  -> derive or validate S/Y/Z matrix family
  -> choose fit family
  -> fit RLC, RLGC, coupling, or mode parameters
  -> store fit metrics and model trace
  -> hand off to reusable circuit or quantum model workflow
```

## Fit Families

| Family | Typical output |
| --- | --- |
| RLC | resistance, inductance, capacitance, resonance, quality factor |
| RLGC | distributed line parameters and sectioning assumptions |
| coupling model | mutual capacitance, mutual inductance, or coupling-window parameters |
| mode extraction | mode frequency, loss, linewidth, participation-style descriptors when available |

## Surface Choice

Use a Python notebook for first-pass ingestion, unit checks, scikit-rf-compatible operations, and one-off reports. Move repeated import, normalization, fitting, and matrix transforms into Python Analysis Core. Pluto can consume the normalized package or call selected bridge functions when the analysis needs to sit next to a Julia Core circuit study.

## Related

- [External FEM Result Contract](../../reference/research-contracts/external-fem-result-contract.md)
- [Equivalent Circuit Model Contract](../../reference/research-contracts/equivalent-circuit-model-contract.md)
- [Python Notebook Ingestion](python-notebook-ingestion.md)
- [Equivalent Circuit Modeling](../../concepts/equivalent-circuit-modeling/index.mdx)
