---
aliases:
  - Python Notebooks
  - Python Notebook Workflows
tags:
  - diataxis/how-to
  - audience/user
  - topic/notebooks
status: stable
owner: docs-team
audience: user
scope: Python notebook workflow for local file inspection, analysis sketches, and report evidence.
version: v1.0.0
last_updated: 2026-06-12
updated_by: codex
sidebar:
  label: Overview
  order: 10
---

# Python Notebooks

Use Python notebooks when the work is easier in Python than Pluto: local file inspection, table cleanup, fitting experiments, matrix analysis, or report evidence assembly.

## Use It For

| Need | Recommended surface |
| --- | --- |
| quick array/table inspection | Python notebook |
| reusable fitting logic | Python Analysis Core |
| Julia simulation exploration | Pluto Notebook |
| final API lookup | Sphinx Python API Reference |

## Workflow

1. Keep source files, units, and axis names visible near the loading cell.
2. Use `superconducting_circuits_analysis` when logic is reusable.
3. Keep notebook-only plotting and narrative in the notebook.
4. Move repeated fitting, preprocessing, or matrix transforms into Python Analysis Core.

## Related

- [Python Notebook Authoring](../../reference/notebooks/python-authoring.md)
- [Python Core](../../reference/core/python-core.mdx)
- [Python Analysis Core](../analysis-fitting/index.md)
