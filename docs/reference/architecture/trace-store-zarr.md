---
title: "TraceStore Zarr"
description: "Defines the canonical local Zarr TraceStore managed by the Python Backend."
---

# TraceStore Zarr

TraceStore is the canonical numeric authority after the Backend validates and publishes a Runner result. Runner staging is temporary; published Zarr stores and trace metadata belong to the Backend.

## Runtime Layout

```text
data/
  metadata.db
  trace_store/
    datasets/
      <dataset_id>/
        designs/
          <design_id>/
            batches/
              <batch_id>.zarr/
  artifacts/
    tasks/
      <task_id>/
        manifest.json
        logs/
  staging/
    tasks/
      <task_id>/
        manifest.json
        result.zarr/
        logs/
```

## Publication

When the Runner calls complete, the Backend:

1. marks the task `staging_result`
2. validates the manifest path and schema
3. validates `result.zarr`
4. computes trace metadata
5. copies the Zarr store into `data/trace_store`
6. records published trace metadata
7. copies manifest and logs into `data/artifacts`
8. marks the task `completed`

## Complex Traces

Store complex traces as explicit real/imag arrays:

```text
/traces/S11/real
/traces/S11/imag
```

Do not rely on cross-language complex dtype compatibility.

## Chunking

Default access is fixed sweep point to full frequency trace. For `[frequency, sweep1, sweep2]`, prefer:

```text
[frequency_length, 1, 1]
```
