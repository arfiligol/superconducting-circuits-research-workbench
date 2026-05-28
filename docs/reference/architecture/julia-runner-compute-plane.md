---
title: "Julia Runner Compute Plane"
description: "Defines the async Julia compute plane used by the application and notebooks."
icon: lucide/cpu
---

# Julia Runner Compute Plane

Use the Julia Runner for application-triggered simulation, parameter sweeps, post-processing, fitting, and derived parameter extraction. The Runner is a compute plane only: it writes staged result packages and reports manifest locators back to the Python Backend.

## Contract

The Runner owns:

- Julia Core execution
- sweep and analysis dispatch
- local filesystem Zarr staging writes
- manifest generation
- heartbeat, progress, completion, and failure reports

The Runner does not own:

- DatasetRecord, TraceRecord, or TraceBatchRecord tables
- workspace, auth, or session state
- official TraceStore publication
- frontend or notebook data APIs

## Runner API

The Backend exposes the Runner protocol at:

```text
POST /runner/v1/tasks/claim
POST /runner/v1/tasks/{task_id}/heartbeat
POST /runner/v1/tasks/{task_id}/progress
GET  /runner/v1/tasks/{task_id}/cancellation
POST /runner/v1/tasks/{task_id}/complete
POST /runner/v1/tasks/{task_id}/fail
```

Application-triggered work must use this async path. Pluto notebooks may still execute Julia Core directly because the notebook kernel is an explicit research execution environment.

## Test Fixtures Are Not Task Kinds

Small staged Zarr fixtures may be used in tests to validate the Backend publisher and manifest validation path.

These fixtures are not product task kinds. The Runner must not expose fixture output as a normal queue-dispatched workflow.

Real task kinds execute Julia Core, JosephsonCircuits, or analysis logic. Unknown or unsupported task kinds fail clearly and report `/fail`; they never complete with fixture output.

## Task Family Contract

The Runner task families are:

| Task family | Responsibility |
|---|---|
| `julia_simulation_frequency_sweep` | execute a Backend-provided frequency sweep through Julia Core / JosephsonCircuits |
| `julia_simulation_parameter_sweep` | execute a parameterized sweep and write trace arrays with explicit axis order |
| `julia_analysis_trace_summary` | compute summary tables or derived trace metadata from published traces |
| `julia_analysis_resonance_fit` | fit resonator/SQUID model parameters and write result artifacts |
| `julia_analysis_sy_z_compare` | compare S/Y/Z representations through explicit transform and validation logic |
| `julia_postprocess_coordinate_transform` | convert published trace coordinates into another declared coordinate system |
| `julia_extract_derived_parameters` | extract derived scalar/vector parameters and provenance-linked summaries |

Each task family follows the same execution contract:

1. read a Backend-provided simulation setup;
2. execute Julia Core / JosephsonCircuits logic;
3. write local filesystem Zarr real/imag traces;
4. write `manifest.json`;
5. report completion through the Runner API.

Analysis and post-processing tasks may write summary tables or artifacts instead of S-parameter traces, but they still use the same staging and manifest authority boundary.

## Validation

Run the Runner tests with:

```bash
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```
