---
title: "Python Notebook Authoring"
aliases:
  - Python Notebook Helpers
  - Python Notebook Surface Rules
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/notebooks
status: stable
owner: docs-team
audience: contributor
scope: Python notebook helper boundaries for data inspection, Backend API usage, and product task submission.
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Python Notebook Authoring

Python notebooks are programmable data-analysis and platform-inspection surfaces. They may directly read local/exported/canonical data files for read-only analysis, and they must use Backend APIs when changing platform state.

## Allowed Helpers

| Helper | Purpose |
| --- | --- |
| `open_trace_zarr_readonly()` | open local/exported/canonical Zarr stores for read-only ad hoc analysis |
| `load_trace_metadata_via_backend()` | load platform-authoritative dataset/design/trace metadata |
| `submit_simulation_request()` | submit `SimulationRequestV1` through the same Backend contract used by the Application |
| `submit_analysis_request()` | submit `AnalysisRequestV1` through the same Backend contract used by Analysis Workbench |
| `fetch_result_view()` | read Backend-owned ResultView bootstrap, preview, projection, or bounded slice payloads |

## Forbidden Helpers

| Helper | Why it is forbidden |
| --- | --- |
| `direct_metadata_db_write()` | bypasses metadata authority, authorization, provenance, and indexing |
| `direct_trace_store_publish()` | bypasses Backend publication and TraceRecord/TraceBatch registration |
| `juliacall_simulation_compute()` | turns Python Notebook into a second simulation compute authority |
| `custom_runner_envelope_builder()` | bypasses Backend compilation of Runner task envelopes |

## Rules

- Read-only file analysis may bypass Backend.
- Platform state changes must use Backend APIs.
- Python Notebook does not define separate request schemas.
- Python Notebook dependencies belong in `notebooks/python/`, not `app/backend/`.
- Python Notebook may read canonical TraceStore files for analysis, but those reads do not create official metadata, provenance, or result records.
- Any notebook write that should become platform state must go through Backend import, publication, task, or result contracts.

## Related

* [Notebook Interface](index.md)
* [Simulation Interface Boundaries](../architecture/simulation-interface-boundaries.md)
* [Product Async Contracts](../architecture/product-async-contracts.md)
* [ResultView API](../app/backend/result-view-api.md)
