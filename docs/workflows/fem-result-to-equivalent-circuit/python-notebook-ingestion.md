---
aliases:
 - Python Notebook Ingestion
 - Python external result notebooks
tags:
 - diataxis/how-to
 - audience/user
 - topic/notebooks
status: stable
owner: docs-team
audience: user
scope: Python notebook workflow for external result ingestion, scikit-rf-compatible analysis, local file inspection, fitting sketches, and report evidence.
version: v2.0.0
last_updated: 2026-06-14
updated_by: codex
sidebar:
 label: Python Notebook Ingestion
 order: 40
---

# Python Notebook Ingestion

Use Python notebooks in Route 2 when the work is easier in Python than Pluto: external FEM result ingestion, scikit-rf-compatible network handling, local file inspection, table cleanup, fitting experiments, matrix analysis, or report evidence assembly.

## Use It For

| Need | Recommended surface |
| --- | --- |
| quick array/table inspection | Python notebook |
| trace table, Touchstone, or Zarr ingestion sketch | Python notebook |
| reusable fitting logic | Python Analysis Core |
| Julia simulation exploration | Pluto Notebook |
| final API lookup | Sphinx Python API Reference |

## Workflow

1. Keep source files, units, and axis names visible near the loading cell.
2. Use `superconducting_circuits_analysis` when fitting, preprocessing, or matrix logic is reusable.
3. Keep notebook-only plotting, source inspection, and report narrative in the notebook.
4. Move repeated ingestion, fitting, preprocessing, or matrix transforms into Python Analysis Core.
5. Do not call Julia Core or JuliaCall as the normal simulation compute path.

## Related

- [Python Core](../../reference/core/python-core.mdx)
- [FEM Result To Equivalent Circuit](index.md)
- [Equivalent Circuit To Quantum Model](../equivalent-circuit-to-quantum-model/index.md)
- [Quantum Dynamics / Pulse Simulation](../quantum-dynamics-pulse-simulation/index.md)
- [Notebook Roles](../../reference/research-contracts/notebook-roles.md)
