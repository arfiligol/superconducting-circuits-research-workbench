---
title: "Runner Result Manifest"
description: "Defines the staged result manifest written by the Julia Runner and validated by the Backend."
---

# Runner Result Manifest

The manifest is the only control-plane payload the Runner returns after writing a local result package. It points to staged Zarr arrays and describes their shapes, chunks, dtypes, axes, logs, and producer metadata.

The example below is a minimal manifest shape example. It is not a fixture-task contract and does not define a special Runner task kind.

## Minimum Shape

```json
{
 "schema_version": "sc.runner.result.v1",
 "task_id": "306",
 "producer": {
  "runner": "SuperconductingCircuitsRunner",
  "runner_version": "0.1.0",
  "core_version": "0.1.0",
  "julia_version": "1.12"
 },
 "array_store": {
  "format": "zarr",
  "zarr_format": 2,
  "uri": "result.zarr"
 },
 "traces": [
  {
   "trace_key": "S11",
   "family": "s_matrix",
   "parameter": "S11",
   "representation": "complex",
   "real_path": "/traces/S11/real",
   "imag_path": "/traces/S11/imag",
   "shape": [5],
   "chunk_shape": [5],
   "dtype": "float64",
   "axes": [
    {
     "name": "frequency",
     "unit": "Hz",
     "path": "/axes/frequency"
    }
   ]
  }
 ]
}
```

## Rules

- Use `schema_version = "sc.runner.result.v1"`.
- Runner result packages use Zarr v2.
- Keep `array_store.uri` relative to the staging task directory.
- Keep trace and axis paths inside the Zarr root.
- Store complex arrays as separate real/imag arrays.
- Do not send large arrays through HTTP JSON.
- Write `manifest.json.tmp` first, then rename to `manifest.json`.

## Backend Checks

The Backend rejects:

- absolute manifest paths
- path traversal such as `../`
- a manifest `task_id` that does not match the task row
- missing Zarr arrays
- shape, chunk shape, dtype, or axis length mismatches
