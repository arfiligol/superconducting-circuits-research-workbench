---
aliases:
  - "Canonical Contract Registry"
  - "正典契約註冊表"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/architecture
status: stable
owner: docs-team
audience: team
scope: current published contracts for the Notebook + Application + Julia Runner architecture
version: v1.1.0
last_updated: 2026-05-28
updated_by: codex
---

# Canonical Contract Registry

This registry names the owner for each active cross-layer contract.

!!! warning "Registry Rule"
    A public workflow, machine-readable payload, runtime behavior, or storage layout must have exactly one owner. If a contract is not listed here, it is not architecture-level SoT yet.

## Registry

| Contract | Owner | Source of truth | Primary consumers |
|---|---|---|---|
| Application Interface | Electron App + Frontend | [Application Interface](../app/application-interface.md), [Frontend Reference](../app/frontend/index.md) | users browsing datasets, tasks, traces, and results |
| Notebook Interface | Pluto + Python notebooks | [Notebook Reference](../notebooks/index.md) | research cockpit, backend/API inspection, migration analysis |
| Backend control/data plane | Python Backend | [Backend Reference](../app/backend/index.md), [Tasks & Execution](../app/backend/tasks-execution.md) | frontend, notebooks, Julia Runner |
| Julia compute plane | Julia Runner | [Julia Runner Compute Plane](julia-runner-compute-plane.md) | backend runner API, Pluto task submission |
| Runner result manifest | Julia Runner writes; Python Backend validates | [Runner Result Manifest](runner-result-manifest.md) | publisher, tests, future runner tasks |
| Canonical TraceStore | Python Backend | [TraceStore Zarr](trace-store-zarr.md), [Datasets & Results](../app/backend/datasets-results.md) | raw data browser, result browser, notebooks |
| Task lifecycle | Python Backend | [Tasks & Execution](../app/backend/tasks-execution.md) | frontend task monitor, runner claim/complete loop |
| Runner task protocol | Python Backend API + Julia Runner client | [Julia Runner Compute Plane](julia-runner-compute-plane.md) | local runner, desktop startup |
| Dataset / Design / Trace metadata | Python Backend | [Datasets & Results](../app/backend/datasets-results.md), [Data Formats](../data-formats/index.md) | dashboard, raw data browser, notebooks |
| Circuit definition metadata | Python Backend | [Circuit Definitions](../app/backend/circuit-definitions.md), [Data Formats / Circuit Netlist](../data-formats/circuit-netlist.md) | design assets, notebooks, future task builders |
| App shell and navigation | Frontend | [Frontend Reference](../app/frontend/index.md), [Sidebar](../app/frontend/shared-shell/sidebar.md) | Electron App |
| Session/workspace/auth context | Python Backend + shared app model | [Session & Workspace](../app/backend/session-workspace.md), [Shared App Model](../app/shared/index.md) | frontend shell, online mode |

## Removed Contracts

These are no longer active contracts:

| Removed surface | Replacement |
|---|---|
| User-facing command workflow | `scripts/` for dev/build/test/maintenance only |
| Retired local queue worker runtime | DB-backed task claim by Julia Runner |
| Retired Python UI runtime | Electron App + Next.js frontend |
| Python Backend in-process Julia simulation | Julia Runner compute plane |
| Simulation Workbench / Characterization Workbench / Schemdraw standalone workflow | Task monitor, result browser, design assets, notebooks |

## Related

* [Architecture Reference](index.md)
* [Parity Matrix](parity-matrix.md)
* [Julia Runner Compute Plane](julia-runner-compute-plane.md)
* [TraceStore Zarr](trace-store-zarr.md)
