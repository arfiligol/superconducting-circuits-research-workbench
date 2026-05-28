# Superconducting Circuits Tutorial

This repository is a notebook-first and app-backed superconducting circuits workbench. The current source of truth is the `Notebook Interface + Electron Application Interface + Julia Runner Compute Plane` architecture.

Python owns task lifecycle, metadata, publication, provenance, and TraceStore APIs. Julia owns simulation, sweeps, heavy analysis, and staged result package generation. Large numeric arrays move through local filesystem Zarr, not HTTP JSON.

## Architecture

This repository has two execution tracks and one data-inspection track.

### Research Direct Track

```text
[Pluto Notebook]
    |
    | using SuperconductingCircuitsCore
    v
[Julia Core]
    - reusable circuit construction
    - direct JosephsonCircuits.jl simulation
    - direct sweep / analysis prototyping
    - local research plots and scratch outputs
```

Pluto Notebook is the direct Julia Core research interface.
Pluto Notebook is not a Backend task submitter in the platform architecture.

### Product Async Track

```text
[Electron Application / Simulation Workbench / Analysis Workbench / Python Notebook when submitting platform tasks]
    |
    | POST /tasks or domain-specific Backend API
    v
[Python Backend]
    - validate dataset/design/session/request
    - create persisted task row
    - prepare local staging directory
    |
    | POST /runner/v1/tasks/claim
    v
[Julia Runner]
    - execute Julia Core / analysis work
    - write result.zarr + manifest.json under staging
    - report manifest locator
    |
    | POST /runner/v1/tasks/{id}/complete
    v
[Python Backend Publisher]
    - validate manifest and Zarr layout
    - publish into canonical TraceStore
    - create trace metadata
    |
    v
[Application Result Viewer / Raw Data Browser / Python Notebook]
```

Application Simulation Workbench and Analysis Workbench are productized surfaces in this track. Electron Application owns the productized workflow. Python Notebook can submit tasks through the same Backend contracts when it needs platform state. Pluto Notebook is not a task submitter.

See [Product Async Contracts](docs/reference/architecture/product-async-contracts.md) for the `SimulationRequestV1`, `AnalysisRequestV1`, `RunnerTaskEnvelopeV1`, `RunnerResultManifestV1`, and `ResultView API` boundary.

### Data / Platform Notebook Track

```text
[Python Notebook]
    |
    | direct read local Zarr / exported data / raw files / canonical TraceStore
    v
[Ad hoc analysis and inspection]

[Python Notebook]
    |
    | Backend API for platform state, task submission, metadata, publication, provenance
    v
[Python Backend]
```

Python Notebook is a programmable data-analysis and inspection surface. It may directly read local Zarr, exported data, raw files, and canonical TraceStore files for ad hoc analysis; any platform mutation, task creation, publication, metadata update, or result registration must go through the Python Backend.

See [Simulation Interface Boundaries](docs/reference/architecture/simulation-interface-boundaries.md) for the source-of-truth split between Pluto, Python Notebook, Application Simulation/Analysis Workbenches, Backend, and Julia Runner.

## Interface Responsibilities

| Interface | Responsibility |
| --- | --- |
| Pluto Notebook | Direct Julia Core research computation |
| Python Notebook | Programmable data-analysis and inspection surface |
| Application Simulation Workbench | Productized simulation request builder, task monitor, and result viewer |
| Application Analysis Workbench | Productized fitting, post-processing, comparison, and derived-parameter workflow |
| Task / Execution Center | Cross-workbench execution history, Runner runtime status summary, task detail, and result handoff |
| Raw Data Browser | Trace browsing and comparison |
| Python Backend | Task lifecycle, metadata, publication, TraceStore APIs |
| Julia Runner | Async compute execution and local Zarr staging |

Application Simulation Workbench and Analysis Workbench remain mandatory as productized workflow surfaces; Pluto is not their replacement.

## Repository Layout

```text
core/
  julia/
    SuperconductingCircuitsCore/
    SuperconductingCircuitsRunner/
  python/
    sc_data_contracts/
notebooks/
  pluto/
  python/
app/
  backend/
  frontend/
    # Simulation Workbench, Analysis Workbench, Task / Execution Center, Raw Data Browser, Dataset UI
  desktop/
scripts/
  dev/
docs/
```

## Local App

Install the active workspaces first:

```bash
cd app/backend && uv sync
npm install --prefix app/frontend
npm install --prefix app/desktop
```

Start the local application stack:

```bash
npm run app:dev
```

Stop it with:

```bash
npm run app:stop
```

The local stack starts:

- Next.js frontend on `http://127.0.0.1:3000`
- Python Backend on `http://127.0.0.1:8000`
- Julia Runner polling the backend runner API

No separate queue service is part of the local runtime.

## Validation

Run the focused checks with:

```bash
npm run backend:test
npm run frontend:typecheck
npm run runner:test
npm run julia:test
npm run build --prefix app/desktop
```

Use targeted tests while iterating:

```bash
cd app/backend && uv run pytest tests/test_runner_api.py -q
julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
```

## Data Layout

Local runtime data follows this contract:

```text
data/
  metadata.db
  trace_store/
    datasets/<dataset_id>/designs/<design_id>/batches/<batch_id>.zarr/
  artifacts/
    tasks/<task_id>/manifest.json
  staging/
    tasks/<task_id>/manifest.json
    tasks/<task_id>/result.zarr/
```

`data/staging/` is non-authoritative Runner workspace. `data/trace_store/` is the numeric authority after the Backend validates and publishes a Runner result.

## Documentation

The docs site uses Zensical:

```bash
./scripts/prepare_docs_locales.sh
uv run --group dev zensical serve
```

Build the static docs with:

```bash
./scripts/build_docs_sites.sh
```

## Current Boundaries

- Pluto Notebook is research direct execution.
- Backend task submission is outside the Pluto role.
- Python Notebook may directly read data files for analysis, but platform state changes must go through Backend contracts.
- Python Notebook read-only file analysis is allowed without Backend APIs; platform state changes must use Backend contracts.
- Application Simulation Workbench remains a first-class product surface.
- Application Analysis Workbench remains a first-class product surface.
- `/tasks` is the Task / Execution Center, not a queue-service product surface.
- Local Mode is the managed local app runtime: frontend + Python Backend + Julia Runner. UI-only shell preview is a developer tool, not a product runtime mode.
- No user-facing command-line workflow surface.
- No retired Python UI runtime.
- No separate local queue worker runtime.
- No large ND arrays over HTTP/JSON.
- No cross-language complex dtype reliance; complex traces are real/imag Zarr arrays.

## License

MIT
