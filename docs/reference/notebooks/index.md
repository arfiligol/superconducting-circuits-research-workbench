---
title: "Notebook Interface"
description: "Defines Pluto and Python notebook roles across the four research routes."
---

# Notebook Interface

Use notebooks as research surfaces across the four route groups. Pluto is the direct Julia research cockpit for reusable circuit authoring and Julia Core studies. Python notebooks support external FEM result ingestion, scikit-rf-compatible analysis, scqubits/QuTiP/qutip-qip studies, local inspection, Python-side analysis sketches, report evidence, and package-helper validation.

## Pluto

Pluto notebooks own direct Julia exploration:

- circuit construction
- simulation experiments
- analysis sketches
- sweep design
- result inspection before productization
- comparison against normalized external result packages

Pluto may use `SuperconductingCircuitsAnalysisBridge` for explicit research-kernel calls into the shared Python analysis package. The bridge is a notebook/research execution surface; it does not move fitting or matrix-analysis ownership into infrastructure code.

For S-parameter fitting research, use this contract path:

```text
Pluto Notebook
  -> Julia Core simulation
  -> explicit frequency_hz + complex S21 trace extraction
  -> SuperconductingCircuitsAnalysisBridge
  -> Python-owned analysis fitting
```

This path covers Notch Type Fitting, transmission fitting, and Vector Fitting.
The notebook selects the trace, frequency span, and displayed outputs. Julia
Core produces simulation traces. `SuperconductingCircuitsAnalysisBridge` maps
Julia arrays into the Python analysis contract. Python analysis owns the fitting
algorithms and returns plain result shapes for notebook display.

## Python

Python notebooks are research and analysis notebooks when the work is easier in Python than Pluto. They are for:

- trace table, Touchstone, and Zarr ingestion sketches
- scikit-rf-compatible RF network conversion
- local Zarr, CSV/raw file, and exported data inspection
- table cleanup and unit/axis checks
- fitting experiments and matrix-analysis sketches
- scqubits quantum-model experiments
- QuTiP and qutip-qip dynamics or pulse experiments
- report-oriented analysis
- validation of reusable Python Analysis Core helper candidates

Python notebooks may read data files directly for ad hoc analysis. Repeated fitting, preprocessing, or matrix transforms should move into Python Analysis Core.

Python notebooks should not become a second scientific compute authority. They must not define a separate simulation request schema or use JuliaCall / Julia Core as the normal simulation compute path.

If a Python notebook needs heavier analysis dependencies for inspection, scqubits/QuTiP/qutip-qip studies, or emergency work, use `notebooks/python/pyproject.toml` rather than adding them to package runtime dependencies.

Shared Python analysis contracts are exposed through the `superconducting_circuits_analysis` package. Python notebooks may import that package from the root uv workspace for inspection or validation, but Python Analysis Core remains the reusable library owner.

## Handoff

When notebook logic becomes reusable:

1. move reusable Julia logic into `SuperconductingCircuitsCore`
2. move reusable plotting logic into `SuperconductingCircuitsVisualizer`
3. move reusable Python fitting or matrix logic into `superconducting_circuits_analysis`
4. keep notebook narrative, parameter choices, and local report evidence in notebooks
5. move stable quantum-model helpers into a future dedicated quantum package, not Julia Core

## Related

- [Notebook Roles](../research-contracts/notebook-roles.md)
- [Quantum Model Boundary](../research-contracts/quantum-model-boundary.md)
- [Workflows](../../workflows/index.mdx)
