---
title: "Notebook Interface"
description: "Defines Pluto and Python notebook roles in the current architecture."
---

# Notebook Interface

Use notebooks through two distinct roles. Pluto is the direct Julia research cockpit. Python notebooks are Product App prototyping and platform-inspection surfaces.

## Pluto

Pluto notebooks own direct Julia exploration:

- circuit construction
- simulation experiments
- analysis sketches
- sweep design
- result inspection before productization

Direct Pluto execution is allowed. Application-triggered execution must still go through the async Runner path.

Backend task submission is outside the Pluto notebook role. If Pluto outputs should become official platform data, use an explicit import/publication path.

Pluto may use `SuperconductingCircuitsAnalysisBridge` for explicit research-kernel calls into the shared Python analysis package. The bridge is a notebook/research execution surface; it does not make the Python Backend an inline fitting or matrix-analysis worker.

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

Python notebooks are the App development front line when the UI is not mature yet. They are for:

- direct local Zarr, CSV/raw file, exported data, and canonical TraceStore file inspection
- Backend/data API inspection when platform metadata, indexing, provenance, or permissions matter
- task submission through the same Backend contracts used by the Application
- task and result API inspection
- ResultView and bounded-slice validation before Product App UI implementation
- migration checks
- emergency analysis
- local TraceStore investigation

Python notebooks may read data files directly for ad hoc analysis. They must use Backend import, publication, task, and result contracts for any write that should become platform state.

Python notebooks are not required to use Backend APIs for read-only ad hoc file analysis. Backend APIs are required when the notebook changes platform state or needs platform-authoritative metadata/provenance.

Python notebooks should not become a second scientific compute authority. They must not directly mutate the metadata DB, directly publish or overwrite canonical TraceStore records, define a separate simulation request schema, or use JuliaCall / Julia Core as the normal simulation compute path.

If a Python notebook needs heavier analysis dependencies for inspection or emergency work, use `notebooks/python/pyproject.toml` rather than adding them to `app/backend`.

Shared Python analysis contracts are exposed through the `superconducting_circuits_analysis` package. Python notebooks may import that package from the root uv workspace for inspection or validation, but Python Analysis Core remains the reusable library owner and writes to platform state still go through Backend contracts.

See [Python Notebook Authoring](python-authoring.md) for helper boundaries such as `open_trace_zarr_readonly()`, `submit_simulation_request()`, `submit_analysis_request()`, and forbidden direct publication helpers.

## Handoff

When a notebook workflow becomes a product workflow:

1. move reusable Julia logic into `SuperconductingCircuitsCore`
2. add a Runner task dispatcher
3. write staged Zarr plus manifest
4. validate publication through the Backend
5. expose browsing and task monitoring through the application
