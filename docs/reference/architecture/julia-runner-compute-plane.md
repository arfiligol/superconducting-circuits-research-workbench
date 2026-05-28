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

For circuit construction tasks, the Runner must call the docs-defined Julia Core Authoring path: components, endpoints, Circuit Plan, compiler, and compiled circuit output. It must not maintain a separate Runner-only construction model.

For HB simulation tasks, the Runner maps Backend payloads into runtime bindings for a compiled HB intent. Julia Core owns the CircuitPlan declarations for ports, pump axes, source slots, observables, and HB compatibility checks. The Runner must not invent HB source or port semantics from task input after compilation.

Runner must reject unknown source slot IDs, unknown pump axis IDs, unknown observable IDs, unknown `optional_hb_kwargs`, and runtime values that do not satisfy compiled HB validation metadata.

## Test Fixtures Are Not Task Kinds

Small staged Zarr fixtures may be used in tests to validate the Backend publisher and manifest validation path.

These fixtures are not product task kinds. The Runner must not expose fixture output as a normal queue-dispatched workflow.

Real task kinds execute Julia Core, JosephsonCircuits, or analysis logic. Unknown or unsupported task kinds fail clearly and report `/fail`; they never complete with fixture output.

## Task Family Contract

The Runner task families are:

| Task family | Responsibility |
|---|---|
| `julia_simulation_frequency_sweep` | execute a Backend-provided frequency sweep through Julia Core / JosephsonCircuits; the first implemented path is the MVP supported design adapter |
| `julia_simulation_parameter_sweep` | parameterized sweep family; fails clearly until the real sweep executor is wired to Runner |
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

The MVP frequency-sweep adapter loads a selected component-library style plan builder, builds a `CircuitPlan`, compiles through Julia Core, runs JosephsonCircuits through `run_frequency_sweep`, and writes Zarr traces. The initial supported design path covers the Local Space resonator seed definition and the internal `runner_mvp_minimal_core_plan` alias. It must not become a separate Runner-owned circuit construction model.

The same boundary applies to solver controls: Runner may bind frequency arrays, source currents, pump frequencies, harmonic counts, and whitelisted solver kwargs, but those values must be checked against the compiled HB intent before execution. `current = 0.0` is valid source-off behavior for an existing source slot.

Runner must not create a default S11 observable, create default ports, create source slots from task payload, or convert ambiguous `amplitude` fields into physical current.

## Validation

Run the Runner tests with:

```bash
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```
