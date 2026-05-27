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

## Local Smoke Task

The first implementation supports `julia_runner_smoke`. It writes:

```text
result.zarr/
  axes/frequency
  traces/S11/real
  traces/S11/imag
manifest.json
logs/runner.log
```

This validates the end-to-end boundary without requiring heavy JosephsonCircuits simulation in CI.

## Validation

Run the Runner tests with:

```bash
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```
