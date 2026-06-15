---
title: "ResultView API"
aliases:
 - Backend ResultView API
 - Result View API
tags:
 - diataxis/reference
 - audience/team
 - sot/true
 - topic/app-reference
status: stable
owner: docs-team
audience: team
scope: Backend-owned result rendering read model for Application and Python Notebook consumers after publication.
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# ResultView API

ResultView API is the product-facing result rendering contract after Backend publication. It lets the Application and Python Notebook inspect task result availability, published result handles, trace metadata, previews, projections, and bounded slices without moving large ND arrays through HTTP JSON.

ResultView is Backend-owned. Runner manifests and staging Zarr packages are not product results until the Backend validates and publishes them.

## Endpoint Families

Endpoint names are contract families. Exact route names may evolve only through Backend owner docs and the OpenAPI contract.

| Endpoint family | Purpose |
| --- | --- |
| `GET /tasks/{task_id}/results/bootstrap` | return task result status, publication status, result handles, available traces, and default views |
| `GET /tasks/{task_id}/results/view` | return plot-ready projection for a selected result handle, trace, or view |
| `GET /traces/{trace_id}/preview` | return summary-safe preview |
| `GET /traces/{trace_id}/slice` | return selected slice or projection bounded by payload size rules |

## Bootstrap Response

`results/bootstrap` is the first call a workbench makes after a task reaches a published result state.

```json
{
 "task_id": "task_001",
 "status": "completed",
 "publication_status": "published",
 "dataset_id": "ds_001",
 "design_id": "design_001",
 "result_handles": [
  {
   "result_id": "result_001",
   "kind": "trace_batch",
   "label": "Frequency sweep result",
   "default_view": "magnitude_db"
  }
 ],
 "available_traces": [
  {
   "trace_id": "batch_001:S11",
   "family": "s_matrix",
   "parameter": "S11",
   "representation": "complex",
   "shape": [401],
   "axes_summary": [
    {
     "name": "frequency",
     "unit": "Hz",
     "length": 401
    }
   ],
   "available_views": ["magnitude_db", "phase", "real_imag"]
  }
 ]
}
```

## View Request

`results/view` accepts a selected result or trace context plus a bounded projection request.

| Parameter | Meaning |
| --- | --- |
| `task_id` | task result context |
| `result_id` | optional result handle identity |
| `trace_id` | optional trace identity |
| `view` | one of the baseline view names or a Backend-defined extension |
| `axis` / `x_axis` / `y_axis` / `series_axis` | projection axis selection |
| `slice` | selected coordinate, index, or bounded window selector |
| `max_points` | client-requested payload limit; Backend may lower it |

The Backend validates every requested trace, axis, slice, and view against published metadata before reading numeric data.

## Projection Request Shape

For `GET /tasks/{task_id}/results/view` and `GET /traces/{trace_id}/slice`, clients request bounded projections using a structured selection object.

Canonical JSON shape:

```json
{
 "view": "magnitude_db",
 "trace_id": "batch_001:S11",
 "result_id": "result_001",
 "axes": {
  "frequency": {
   "mode": "all"
  },
  "bias": {
   "mode": "index",
   "value": 2
  }
 },
 "max_points": 2000
}
```

### Axis selection modes

| Mode | Meaning |
| --- | --- |
| `all` | include the full axis if payload limits allow |
| `index` | select a single index |
| `index_range` | select a bounded index range |
| `coordinate` | select nearest or exact coordinate, according to Backend axis metadata |
| `coordinate_range` | select bounded coordinate range if coordinate-domain summary exists |

### Query encoding

If using GET query parameters, encode the structured projection request as:

```text
projection=<url-encoded-json>
```

Backend-defined named parameters are allowed only when they are documented in the OpenAPI contract.

### Supported projection constraints

The baseline supported views are:

- 1D `magnitude_db`
- 1D `phase`
- 1D `real_imag`
- 2D `sweep_heatmap`

If a requested arbitrary ND slice, view, or axis selector is not supported, the Backend returns `view_not_supported` or `slice_out_of_bounds` rather than silently returning an incorrect projection.

## Baseline Views

| View | Meaning |
| --- | --- |
| `magnitude_db` | magnitude in decibels for complex trace families |
| `phase` | phase view for complex trace families |
| `real_imag` | paired real and imaginary components |
| `sweep_heatmap` | sweep-aware 2D projection of a selected trace or result |
| `selected_nd_slice` | bounded slice through an ND trace |

## Payload Rules

- ResultView returns bounded preview/projection payloads.
- ResultView never returns full ND arrays by default.
- Frontend does not read canonical Zarr directly.
- Python Notebook may read Zarr directly for read-only ad hoc analysis, but product rendering should use ResultView when platform semantics matter.
- ResultView payloads must carry enough axis and unit metadata for plot-ready rendering.
- Backend may lower `max_points`.
- Backend must reject projections exceeding payload limits with `payload_too_large`.
- Full dense array export is not part of ResultView. It requires a separate export contract.

## Error Semantics

| Error | Meaning |
| --- | --- |
| `result_not_published` | task completed or Runner completed, but Backend publication has not produced a product result |
| `trace_not_found` | requested trace is not visible or does not exist |
| `view_not_supported` | requested view is not available for the trace/result family |
| `slice_out_of_bounds` | requested index, coordinate, or window is outside the published trace axes |
| `payload_too_large` | requested projection exceeds Backend payload limits |
| `task_not_completed` | task is not in a state that can expose published results |
| `permission_denied` | current session cannot read the task, trace, result handle, or dataset |

## Related

* [Product Async Contracts](../architecture/contracts/product-async-contracts.md)
* [Tasks & Execution](tasks-execution.md)
* [Datasets & Results](datasets-results.mdx)
* [TraceStore Zarr](../architecture/contracts/trace-store-zarr.md)
