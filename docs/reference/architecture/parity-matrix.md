---
aliases:
  - "Parity Matrix"
  - "架構對齊矩陣"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/architecture
status: stable
owner: docs-team
audience: team
scope: current adoption state for retained app/backend/runner/notebook surfaces
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Parity Matrix

This matrix tracks the retained surfaces after the architecture shrink.

## Status Legend

| Status | Meaning |
|---|---|
| `aligned` | docs, implementation, and tests use the current architecture |
| `partial` | current SoT is clear, but adoption is still incomplete |
| `planned` | contract exists, implementation is intentionally minimal |
| `removed` | not an active surface |

## Matrix

| Concern | Current surface | Authority | State | Note |
|---|---|---|---|---|
| App shell and navigation | Dashboard, Dataset, Tasks, Data Ingestion, Raw Data, Design Assets | [Frontend Reference](../app/frontend/index.md) | `aligned` | main nav no longer exposes simulation, characterization, or Schemdraw workbenches |
| Task lifecycle | Backend task table + runner API | [Tasks & Execution](../app/backend/tasks-execution.md) | `partial` | DB-backed claim/complete path exists for runner smoke and publishing tests |
| Julia Runner | `core/julia/SuperconductingCircuitsRunner` | [Julia Runner Compute Plane](julia-runner-compute-plane.md) | `partial` | fake smoke task writes local Zarr and manifest |
| Runner staging manifest | `data/staging/tasks/<task_id>/manifest.json` | [Runner Result Manifest](runner-result-manifest.md) | `aligned` | backend rejects unsafe manifest paths and verifies declared arrays |
| Canonical TraceStore | `data/trace_store/.../<batch_id>.zarr` | [TraceStore Zarr](trace-store-zarr.md) | `partial` | backend publishes smoke Zarr into canonical store |
| Dataset/design/trace browse | App + Backend | [Datasets & Results](../app/backend/datasets-results.md) | `partial` | retained browser APIs remain the app-facing numeric read path |
| Design assets | Schemas + Schema Editor | [Circuit Definitions](../app/backend/circuit-definitions.md) | `partial` | kept narrowly as source/design metadata, not full simulation UI |
| Pluto research cockpit | `notebooks/pluto/` | [Notebook Reference](../notebooks/index.md) | `planned` | direct Julia execution remains allowed in notebooks |
| Python notebooks | `notebooks/python/` | [Notebook Reference](../notebooks/index.md) | `planned` | heavy inspection deps live outside app backend |
| CLI product surface | none | current architecture | `removed` | helper automation belongs in `scripts/` only |
| NiceGUI runtime | none | current architecture | `removed` | not an active dependency or entrypoint |
| Redis/RQ local workers | none | current architecture | `removed` | local runtime starts frontend, Python Backend, and Julia Runner |
| Python JuliaCall simulation | none in app backend | current architecture | `removed` | compute belongs to Julia Runner or explicit notebook kernel |

## Related

* [Architecture Reference](index.md)
* [Canonical Contract Registry](canonical-contract-registry.md)
* [Application Interface](../app/application-interface.md)
