---
aliases:
 - Analysis & Fitting
 - Analysis and Fitting
tags:
 - diataxis/how-to
 - audience/user
 - topic/analysis
status: stable
owner: docs-team
audience: user
scope: Python Analysis Core, Analysis Bridge, external FEM-result normalization, equivalent-circuit fitting, quantum-model handoff, resonance fitting, SQUID fitting and flux analysis workflow map.
version: v2.1.0
last_updated: 2026-06-14
updated_by: codex
title: FEM Result To Equivalent Circuit
sidebar:
 label: Overview
 order: 10
---

# FEM Result To Equivalent Circuit

This route answers "How do I turn upstream layout or FEM evidence into a reviewable equivalent circuit?" The workbench consumes trace tables, Touchstone files, or normalized Zarr packages. It does not run GDSFactory, gsim, gplugins, qpdk, mesh generation, or FEM jobs.

```text
external S/Y/Z trace evidence
  -> normalize ports, units, axes, provenance
  -> inspect poles, zeros, residues, residuals
  -> fit RLC, RLGC, coupling, mode, or rational model
  -> export an equivalent-circuit result usable by downstream tools
```

## Page Map

| Page | Use it when |
| --- | --- |
| [External FEM Result To Equivalent Circuit](external-fem-result-to-equivalent-circuit.md) | You need the main artifact-to-model workflow. |
| [GDSFactory-Compatible Result Workflow](gdsfactory-compatible-result-workflow.md) | You want a gsim-style S -> Z/Y -> RLC/RLGC analysis shape without importing gsim here. |
| [Python Notebook Ingestion](python-notebook-ingestion.md) | You need Python-native inspection before reusable fitting code exists. |
| [Resonance Fitting](resonance-fitting.md) | You need compact resonance-parameter extraction from traces. |
| [SQUID Fitting](squid-fitting.mdx) | You need to fit SQUID circuit parameters. |
| [Flux Dependence Analysis](flux-analysis.md) | You need to analyze flux-dependent sweep evidence. |
| [Research Evidence](research-data-evidence.mdx) | You need provenance and evidence rules for fitted results. |

## Owner Model

| Surface | Role |
| --- | --- |
| Python Analysis Core | owns reusable external-result normalization, fitting, preprocessing, matrix analysis, and JSON-friendly result shapes |
| Julia Analysis Bridge | exposes selected Python Analysis Core functions to Pluto through PythonCall |
| Pluto Notebook | selects traces, parameters, plots, and research-facing analysis flow |
| Python Notebook | performs Python-native file inspection, scikit-rf-compatible ingestion, fitting experiments, and report assembly |

## Related

- [Equivalent Circuit Modeling](../../concepts/equivalent-circuit-modeling/index.mdx)
- [GDSFactory-Compatible Artifacts](../../concepts/gdsfactory-compatible-artifacts/index.md)
- [Python Core](../../reference/core/python-core.mdx)
- [Notebook Interface](../../reference/notebooks/index.md)
- [Research Contracts](../../reference/research-contracts/index.md)
