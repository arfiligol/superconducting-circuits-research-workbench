---
aliases:
  - "Extend Julia Functions"
  - "擴充 Julia 函數"
tags:
  - diataxis/how-to
  - status/stable
  - topic/extend
  - topic/contributing
  - topic/julia
status: stable
owner: docs-team
audience: contributor
scope: "貢獻者指南：擴充 Julia Core 與 Julia Runner compute tasks"
version: v0.2.0
last_updated: 2026-05-28
updated_by: codex
---

# 擴充 Julia 函數

新增模擬或分析能力時，先把 reusable compute logic 放進 Julia Core，再用 Julia Runner task 包裝成非同步工作。
Python Backend 只負責 task lifecycle、metadata、publication 與 TraceStore registration。

## Architecture

```text
Pluto Notebook                 Python Backend                  Julia Runner
      |                               |                              |
      | direct research execution      | POST /tasks                  |
      v                               v                              |
Julia Core <------------------- task metadata --------------> task dispatcher
      |                                                              |
      | reusable circuit/sweep/analysis logic                         v
      +------------------------------------------------------ result.zarr + manifest
```

## Step 1: Add Julia Core logic

Add reusable circuit construction, sweep, or analysis code under:

```text
core/julia/SuperconductingCircuitsCore/
```

Keep this layer independent from HTTP, task polling, metadata DB, and frontend concerns.
It should be callable from Pluto and from Runner task dispatch.

## Step 2: Add a Runner task dispatcher

Add the task handler under:

```text
core/julia/SuperconductingCircuitsRunner/
```

The handler receives the claimed task payload and writes a local result package.
For a complex trace, write real and imaginary arrays separately:

```text
result.zarr/
├── axes/
│   └── frequency
└── traces/
    └── S11/
        ├── real
        └── imag
```

Runner result packages use Zarr v2.
Do not send large arrays back through HTTP JSON.

## Step 3: Write the manifest

Write `manifest.json.tmp`, close it, then rename it to `manifest.json`.
The backend only accepts a completed manifest.

The manifest must declare:

- `schema_version`
- `task_id`
- producer versions
- Zarr format and relative URI
- sweep success/failure summary
- trace paths, shapes, chunk shapes, dtype, and axes
- log artifacts

See [Runner Result Manifest](../../reference/architecture/runner-result-manifest.md).

## Step 4: Add backend validation if needed

If the new task produces a new trace family or summary table, extend the Python Backend publisher validation.
The backend must verify every declared Zarr array before publishing it into TraceStore.

## Step 5: Add tests

Use a small fake task before adding heavy JosephsonCircuits coverage.

```bash
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
cd app/backend && uv run pytest tests/test_runner_api.py
```

## Notes

!!! warning "No Python JuliaCall runtime"
    Do not add new Python Backend execution paths that call Julia through JuliaCall.
    Notebook kernels may call Julia directly because they are explicit research execution environments.

!!! warning "No CLI entrypoint"
    Do not register new `sc-*` product commands.
    Developer-only helpers belong under `scripts/dev/`, `scripts/test/`, `scripts/build/`, or `scripts/maintenance/`.

## Related

- [Julia Runner Compute Plane](../../reference/architecture/julia-runner-compute-plane.md)
- [Runner Result Manifest](../../reference/architecture/runner-result-manifest.md)
- [TraceStore Zarr](../../reference/architecture/trace-store-zarr.md)
