---
aliases:
  - Julia Core Reference
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/core-reference
status: stable
owner: docs-team
audience: team
scope: Julia-native core and runner package reference surface.
version: v0.6.1
last_updated: 2026-05-28
updated_by: codex
---

# Julia Core

本頁記錄 Julia-native simulation / analysis runtime 的目前邊界，以及 repo 內正式存在的 Julia package surfaces。

For the reusable Circuit Plan authoring architecture, use [Julia Core Authoring](../julia-core/index.md). This page only records package placement and package-level ownership.

!!! info "Current Julia Surface"
    canonical Julia surface 已收斂到 `core/julia/`。
    目前 repository 內的 Julia packages 是：
    1. `core/julia/SuperconductingCircuitsCore/`
    2. `core/julia/SuperconductingCircuitsRunner/`

!!! warning "Ownership Boundary"
    Julia Core owns reusable compute logic.
    Julia Runner owns asynchronous compute execution and staged result packages.
    Python Backend still owns task lifecycle, canonical TraceStore publication, and provenance records.

## Surface Map

=== "Julia Core"

    | Surface | Role |
    |---|---|
    | `core/julia/SuperconductingCircuitsCore/` | docs-defined Julia Core Authoring model, Circuit Plan, endpoints, compiler concepts, simulation helpers, and analysis helpers |
    | JosephsonCircuits.jl runtime | numerical circuit solve engine called from Julia-owned code |
    | Pluto notebooks | direct research cockpit for explicit Julia execution |

=== "Julia Runner"

    | Surface | Role |
    |---|---|
    | `core/julia/SuperconductingCircuitsRunner/` | backend polling, task dispatch, local Zarr staging writer, manifest generation, complete/fail reporting |
    | `data/staging/tasks/<task_id>/result.zarr/` | temporary local Zarr package written by the runner |
    | `data/staging/tasks/<task_id>/manifest.json` | runner result manifest validated by the backend publisher |

## Current Repository Files

| File | What it means in the current design |
|---|---|
| `core/julia/SuperconductingCircuitsCore/Project.toml` | Julia Core package environment |
| `core/julia/SuperconductingCircuitsRunner/Project.toml` | Julia Runner package environment |
| `core/julia/SuperconductingCircuitsRunner/src/staging/zarr_writer.jl` | local filesystem Zarr v2 staging writer |

## Consumer Pairing

| Consumer | Reads Julia Core through |
|---|---|
| Python Backend | [Julia Compute Boundary](julia-wrapper.md) and runner API docs |
| Advanced Julia users / contributors | [Notebook Interface](../notebooks/index.md) and Pluto notebooks |
| Julia Runner contributors | [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md) |

## Related

- [Julia Core Authoring](../julia-core/index.md)
- [Julia Compute Boundary](julia-wrapper.md)
- [Julia Runner Compute Plane](../architecture/julia-runner-compute-plane.md)
- [Notebook Interface](../notebooks/index.md)
